"""Hybrid Search Engine combining SQLite FTS5 (BM25) and Vector Embeddings with Reciprocal Rank Fusion."""
import json
import logging
import math
from pathlib import Path
import re
import sqlite3
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

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
    """Zero-daemon hybrid search engine backed by SQLite FTS5 and embedded vector blobs."""

    def __init__(self, db_path: Path | str = ":memory:"):
        self.db_path = Path(db_path) if isinstance(db_path, str) and db_path != ":memory:" else db_path
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_str = str(self.db_path.resolve())
        else:
            self._db_str = ":memory:"
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_str)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        """Create relational, FTS5, and metadata tables if they do not exist."""
        with self._get_connection() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS lore_documents (
                    doc_id TEXT PRIMARY KEY,
                    doc_type TEXT NOT NULL,
                    chapter_num INTEGER DEFAULT 0,
                    folder TEXT,
                    title TEXT,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    embedding BLOB,
                    created_at REAL
                )
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_lore_chapter 
                ON lore_documents(chapter_num, folder)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_lore_type 
                ON lore_documents(doc_type)
            """)

            # SQLite FTS5 virtual table for BM25 lexical search
            con.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS lore_fts USING fts5(
                    doc_id UNINDEXED,
                    content,
                    title,
                    folder,
                    doc_type,
                    tokenize = 'unicode61'
                )
            """)
            con.commit()

    def index_document(self, doc: LoreDocument, embedding: Optional[List[float]] = None) -> None:
        """Index a single document with optional vector embedding."""
        self.index_documents([doc], [embedding] if embedding is not None else None)

    def index_documents(
        self,
        docs: List[LoreDocument],
        embeddings: Optional[List[Optional[List[float]]]] = None
    ) -> None:
        """Index a batch of documents atomically."""
        if not docs:
            return

        with self._get_connection() as con:
            for idx, doc in enumerate(docs):
                emb = embeddings[idx] if embeddings and idx < len(embeddings) else None
                emb_blob = struct.pack(f"{len(emb)}f", *emb) if emb else None
                meta_str = json.dumps(doc.metadata, ensure_ascii=False)

                # 1. Upsert document into main table
                con.execute("""
                    INSERT INTO lore_documents 
                    (doc_id, doc_type, chapter_num, folder, title, content, metadata_json, embedding, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(doc_id) DO UPDATE SET
                        doc_type = excluded.doc_type,
                        chapter_num = excluded.chapter_num,
                        folder = excluded.folder,
                        title = excluded.title,
                        content = excluded.content,
                        metadata_json = excluded.metadata_json,
                        embedding = coalesce(excluded.embedding, lore_documents.embedding),
                        created_at = excluded.created_at
                """, (
                    doc.doc_id,
                    doc.doc_type.value,
                    doc.chapter_num,
                    doc.folder,
                    doc.title,
                    doc.content,
                    meta_str,
                    emb_blob,
                    time.time()
                ))

                # 2. Update FTS5 virtual index
                con.execute("DELETE FROM lore_fts WHERE doc_id = ?", (doc.doc_id,))
                con.execute("""
                    INSERT INTO lore_fts (doc_id, content, title, folder, doc_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    doc.doc_id,
                    doc.content,
                    doc.title or "",
                    doc.folder or "",
                    doc.doc_type.value
                ))
            con.commit()

    def delete_document(self, doc_id: str) -> None:
        """Remove a document from both table and FTS index."""
        with self._get_connection() as con:
            con.execute("DELETE FROM lore_documents WHERE doc_id = ?", (doc_id,))
            con.execute("DELETE FROM lore_fts WHERE doc_id = ?", (doc_id,))
            con.commit()

    def delete_chapter(self, chapter_num: int, folder: Optional[str] = None) -> None:
        """Delete all indexed documents belonging to a specific chapter."""
        with self._get_connection() as con:
            if folder:
                rows = con.execute(
                    "SELECT doc_id FROM lore_documents WHERE chapter_num = ? AND folder = ?",
                    (chapter_num, folder)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT doc_id FROM lore_documents WHERE chapter_num = ?",
                    (chapter_num,)
                ).fetchall()
            doc_ids = [r["doc_id"] for r in rows]
            for d_id in doc_ids:
                con.execute("DELETE FROM lore_documents WHERE doc_id = ?", (d_id,))
                con.execute("DELETE FROM lore_fts WHERE doc_id = ?", (d_id,))
            con.commit()

    def count_documents(self) -> int:
        """Return total number of indexed documents."""
        with self._get_connection() as con:
            row = con.execute("SELECT count(*) as c FROM lore_documents").fetchone()
            return row["c"] if row else 0

    def get_document(self, doc_id: str) -> Optional[LoreDocument]:
        """Fetch a document by its ID."""
        with self._get_connection() as con:
            row = con.execute("SELECT * FROM lore_documents WHERE doc_id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            return LoreDocument(
                doc_id=row["doc_id"],
                doc_type=DocumentType(row["doc_type"]),
                chapter_num=row["chapter_num"],
                folder=row["folder"],
                title=row["title"] or "",
                content=row["content"],
                metadata=meta
            )

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

        with self._get_connection() as con:
            sql = """
                SELECT f.doc_id, bm25(lore_fts) as score, d.doc_type, d.chapter_num,
                       d.folder, d.title, d.content, d.metadata_json
                FROM lore_fts f
                JOIN lore_documents d ON f.doc_id = d.doc_id
                WHERE lore_fts MATCH ?
            """
            params: List[Any] = [fts_query]

            if folder:
                sql += " AND d.folder = ?"
                params.append(folder)
            if doc_type:
                sql += " AND d.doc_type = ?"
                params.append(doc_type.value)

            sql += " ORDER BY score ASC LIMIT ?"
            params.append(limit)

            try:
                rows = con.execute(sql, params).fetchall()
            except sqlite3.OperationalError as e:
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
                # In FTS5, bm25 is negative; invert for positive score representation
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

        with self._get_connection() as con:
            sql = "SELECT * FROM lore_documents WHERE embedding IS NOT NULL"
            params: List[Any] = []
            if folder:
                sql += " AND folder = ?"
                params.append(folder)
            if doc_type:
                sql += " AND doc_type = ?"
                params.append(doc_type.value)

            rows = con.execute(sql, params).fetchall()
            scored: List[Tuple[float, sqlite3.Row]] = []

            for r in rows:
                blob = r["embedding"]
                dim = len(blob) // 4
                vec = list(struct.unpack(f"{dim}f", blob))
                sim = _cosine_similarity(query_vector, vec)
                scored.append((sim, r))

            # Sort descending by cosine similarity
            scored.sort(key=lambda x: x[0], reverse=True)
            top_matches = scored[:limit]

            results = []
            for rank, (sim, r) in enumerate(top_matches, start=1):
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
                results.append((doc, rank, sim))
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
