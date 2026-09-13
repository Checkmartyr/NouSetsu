"""Hybrid Search Engine combining SQLite FTS5 (BM25) and Vector Embeddings via SQLAlchemy 2.0 ORM."""
import json
import logging
import math
from pathlib import Path
import re
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nousetsu.rag.db_models import Base, LoreDocumentORM
from nousetsu.rag.models import DocumentType, LoreDocument, SearchResult

logger = logging.getLogger(__name__)


def _sanitize_fts_query(query: str) -> str:
    """Sanitize user query for SQLite FTS5 syntax, extracting alphanumeric and multilingual word tokens."""
    cleaned = "".join(c if (c.isalnum() or c.isspace()) else " " for c in query)
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    if not tokens:
        return '""'
    # Use OR to maximize recall across multiple terms
    return " OR ".join(f'"{t}"' for t in tokens[:12])


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if len(v1) != len(v2):
        return 0.0
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm1) * math.sqrt(norm2))


class HybridSearchEngine:
    """Zero-daemon hybrid search engine backed by SQLite FTS5 and SQLAlchemy 2.0 ORM."""

    def __init__(self, db_path: Path | str = ":memory:"):
        self.db_path = Path(db_path) if isinstance(db_path, str) and db_path != ":memory:" else db_path
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_str = str(self.db_path.resolve())
            self.engine = create_engine(
                f"sqlite:///{self._db_str}",
                connect_args={"check_same_thread": False}
            )
        else:
            self._db_str = ":memory:"
            self.engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
        self.SessionFactory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._init_db()

    def _init_db(self) -> None:
        """Create relational tables via SQLAlchemy metadata and FTS5 virtual table."""
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as con:
            con.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS lore_fts USING fts5(
                    doc_id UNINDEXED,
                    content,
                    title,
                    folder,
                    doc_type,
                    tokenize = 'unicode61'
                )
            """))

    def index_document(self, doc: LoreDocument, embedding: Optional[List[float]] = None) -> None:
        """Index a single document with optional vector embedding."""
        self.index_documents([doc], [embedding] if embedding is not None else None)

    def index_documents(
        self,
        docs: List[LoreDocument],
        embeddings: Optional[List[Optional[List[float]]]] = None
    ) -> None:
        """Index a batch of documents atomically using SQLAlchemy SQLite upsert and FTS5 synchronization."""
        if not docs:
            return

        with self.SessionFactory() as session:
            for idx, doc in enumerate(docs):
                emb = embeddings[idx] if embeddings and idx < len(embeddings) else None
                emb_blob = struct.pack(f"{len(emb)}f", *emb) if emb else None
                meta_str = json.dumps(doc.metadata, ensure_ascii=False) if doc.metadata else None

                values_dict: Dict[str, Any] = {
                    "doc_id": doc.doc_id,
                    "doc_type": doc.doc_type.value,
                    "chapter_num": doc.chapter_num,
                    "folder": doc.folder,
                    "title": doc.title,
                    "content": doc.content,
                    "metadata_json": meta_str,
                    "embedding": emb_blob,
                    "created_at": time.time()
                }

                update_dict: Dict[str, Any] = {
                    "doc_type": doc.doc_type.value,
                    "chapter_num": doc.chapter_num,
                    "folder": doc.folder,
                    "title": doc.title,
                    "content": doc.content,
                    "metadata_json": meta_str,
                    "created_at": time.time()
                }
                if emb_blob is not None:
                    update_dict["embedding"] = emb_blob

                stmt = (
                    sqlite_insert(LoreDocumentORM)
                    .values(**values_dict)
                    .on_conflict_do_update(
                        index_elements=[LoreDocumentORM.doc_id],
                        set_=update_dict
                    )
                )
                session.execute(stmt)

                # Sync SQLite FTS5 index
                session.execute(
                    text("DELETE FROM lore_fts WHERE doc_id = :doc_id"),
                    {"doc_id": doc.doc_id}
                )
                session.execute(
                    text("""
                        INSERT INTO lore_fts (doc_id, content, title, folder, doc_type)
                        VALUES (:doc_id, :content, :title, :folder, :doc_type)
                    """),
                    {
                        "doc_id": doc.doc_id,
                        "content": doc.content,
                        "title": doc.title or "",
                        "folder": doc.folder or "",
                        "doc_type": doc.doc_type.value
                    }
                )
            session.commit()

    def delete_document(self, doc_id: str) -> None:
        """Remove a document from both table and FTS index."""
        with self.SessionFactory() as session:
            session.execute(delete(LoreDocumentORM).where(LoreDocumentORM.doc_id == doc_id))
            session.execute(text("DELETE FROM lore_fts WHERE doc_id = :doc_id"), {"doc_id": doc_id})
            session.commit()

    def delete_chapter(self, chapter_num: int, folder: Optional[str] = None) -> None:
        """Delete all indexed documents belonging to a specific chapter."""
        with self.SessionFactory() as session:
            stmt = select(LoreDocumentORM.doc_id).where(LoreDocumentORM.chapter_num == chapter_num)
            if folder:
                stmt = stmt.where(LoreDocumentORM.folder == folder)
            doc_ids = list(session.scalars(stmt))
            if doc_ids:
                session.execute(delete(LoreDocumentORM).where(LoreDocumentORM.doc_id.in_(doc_ids)))
                for d_id in doc_ids:
                    session.execute(text("DELETE FROM lore_fts WHERE doc_id = :doc_id"), {"doc_id": d_id})
            session.commit()

    def count_documents(self) -> int:
        """Return total number of indexed documents."""
        with self.SessionFactory() as session:
            return session.scalar(select(func.count()).select_from(LoreDocumentORM)) or 0

    def get_document(self, doc_id: str) -> Optional[LoreDocument]:
        """Fetch a document by its ID."""
        with self.SessionFactory() as session:
            orm_doc = session.get(LoreDocumentORM, doc_id)
            return orm_doc.to_domain() if orm_doc else None

    def search_sparse(
        self,
        query: str,
        limit: int = 10,
        folder: Optional[str] = None,
        doc_type: Optional[DocumentType] = None
    ) -> List[Tuple[LoreDocument, int, float]]:
        """Perform lexical BM25 search using SQLite FTS5."""
        if not query or not query.strip():
            return []

        fts_query = _sanitize_fts_query(query)
        if not fts_query:
            return []

        with self.SessionFactory() as session:
            sql_str = """
                SELECT f.doc_id, bm25(lore_fts) as score, d.doc_type, d.chapter_num,
                       d.folder, d.title, d.content, d.metadata_json
                FROM lore_fts f
                JOIN lore_documents d ON f.doc_id = d.doc_id
                WHERE lore_fts MATCH :query
            """
            params: Dict[str, Any] = {"query": fts_query, "limit": limit}
            if folder:
                sql_str += " AND d.folder = :folder"
                params["folder"] = folder
            if doc_type:
                sql_str += " AND d.doc_type = :doc_type"
                params["doc_type"] = doc_type.value
            sql_str += " ORDER BY score ASC LIMIT :limit"

            try:
                result_proxy = session.execute(text(sql_str), params)
                rows = result_proxy.mappings().all()
            except Exception as e:
                logger.warning(f"FTS5 search failed on query '{fts_query}': {e}")
                return []

            results = []
            for rank, r in enumerate(rows, start=1):
                meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
                doc = LoreDocument(
                    doc_id=r["doc_id"],
                    doc_type=DocumentType(r["doc_type"]),
                    chapter_num=r["chapter_num"],
                    folder=r["folder"],
                    title=r["title"] or "",
                    content=r["content"],
                    metadata=meta
                )
                score = abs(float(r["score"]))
                results.append((doc, rank, score))
            return results

    def search_dense(
        self,
        query_vector: List[float],
        limit: int = 10,
        folder: Optional[str] = None,
        doc_type: Optional[DocumentType] = None
    ) -> List[Tuple[LoreDocument, int, float]]:
        """Perform dense vector search computing cosine similarity against stored embeddings."""
        if not query_vector:
            return []

        with self.SessionFactory() as session:
            stmt = select(LoreDocumentORM).where(LoreDocumentORM.embedding.isnot(None))
            if folder:
                stmt = stmt.where(LoreDocumentORM.folder == folder)
            if doc_type:
                stmt = stmt.where(LoreDocumentORM.doc_type == doc_type.value)

            orm_docs = session.scalars(stmt).all()
            scored: List[Tuple[float, LoreDocumentORM]] = []

            for orm_doc in orm_docs:
                blob = orm_doc.embedding
                if not blob:
                    continue
                dim = len(blob) // 4
                vec = list(struct.unpack(f"{dim}f", blob))
                sim = _cosine_similarity(query_vector, vec)
                scored.append((sim, orm_doc))

            # Sort descending by cosine similarity
            scored.sort(key=lambda x: x[0], reverse=True)
            top_matches = scored[:limit]

            results = []
            for rank, (sim, orm_doc) in enumerate(top_matches, start=1):
                results.append((orm_doc.to_domain(), rank, sim))
            return results

    def hybrid_search(
        self,
        query: str,
        query_vector: Optional[List[float]] = None,
        limit: int = 2,
        rrf_k: int = 60,
        folder: Optional[str] = None,
        doc_type: Optional[DocumentType] = None,
        reranker: Optional[Any] = None,
        enable_rerank: bool = True
    ) -> List[SearchResult]:
        """Combine sparse and dense rankings using Reciprocal Rank Fusion (RRF), with optional Cross-Encoder reranking."""
        candidate_k = max(limit * 5, 20)
        sparse_hits = self.search_sparse(query=query, limit=candidate_k, folder=folder, doc_type=doc_type)
        dense_hits = (
            self.search_dense(query_vector=query_vector, limit=candidate_k, folder=folder, doc_type=doc_type)
            if query_vector else []
        )

        doc_map: Dict[str, LoreDocument] = {}
        sparse_ranks: Dict[str, Tuple[int, float]] = {}
        dense_ranks: Dict[str, Tuple[int, float]] = {}

        for doc, rank, score in sparse_hits:
            doc_map[doc.doc_id] = doc
            sparse_ranks[doc.doc_id] = (rank, score)

        for doc, rank, score in dense_hits:
            doc_map[doc.doc_id] = doc
            dense_ranks[doc.doc_id] = (rank, score)

        if not doc_map:
            return []

        # Reciprocal Rank Fusion (RRF)
        scored_results: List[SearchResult] = []
        for doc_id, doc in doc_map.items():
            s_rank, s_score = sparse_ranks.get(doc_id, (None, None))
            d_rank, d_score = dense_ranks.get(doc_id, (None, None))

            rrf = 0.0
            if s_rank is not None:
                rrf += 1.0 / (rrf_k + s_rank)
            if d_rank is not None:
                rrf += 1.0 / (rrf_k + d_rank)

            scored_results.append(SearchResult(
                doc_id=doc.doc_id,
                doc_type=doc.doc_type,
                chapter_num=doc.chapter_num,
                folder=doc.folder,
                title=doc.title,
                content=doc.content,
                sparse_rank=s_rank,
                dense_rank=d_rank,
                sparse_score=s_score,
                dense_score=d_score,
                rrf_score=round(rrf, 6),
                metadata=doc.metadata
            ))

        scored_results.sort(key=lambda x: x.rrf_score, reverse=True)

        # Stage 2: Cross-Encoder Reranking
        if enable_rerank and reranker is not None and scored_results:
            candidate_pool = scored_results[:max(limit * 5, 10)]
            reranked = reranker.rerank(query=query, documents=candidate_pool, top_k=limit)
            return reranked

        return scored_results[:limit]
