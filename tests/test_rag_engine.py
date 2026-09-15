"""Unit tests for Hybrid Search RAG (SQLite FTS5, Vectors, and RRF)."""
from pathlib import Path
import pytest
from nousetsu.rag.embeddings import EmbeddingClient, generate_mock_embedding
from nousetsu.rag.engine import HybridSearchEngine, _sanitize_fts_query
from nousetsu.rag.models import DocumentType, LoreDocument, RAGConfig, SearchResult


def test_sanitize_fts_query():
    """Verify FTS query sanitizer strips dangerous syntax and creates OR-joined tokens."""
    assert _sanitize_fts_query("") == '""'
    q = _sanitize_fts_query("Claire François (magic sword)!")
    assert '"Claire"' in q
    assert '"François"' in q
    assert '"magic"' in q
    assert '"sword"' in q
    assert " OR " in q


def test_rag_models():
    """Verify RAG data models instantiate and serialize correctly."""
    doc = LoreDocument(
        doc_id="summary:Vol_01:001",
        doc_type=DocumentType.SUMMARY,
        chapter_num=1,
        folder="Vol_01",
        title="Chapter 1 - Arrival",
        content="Rei Taylor entered the royal academy.",
        metadata={"key": "val"}
    )
    assert doc.doc_id == "summary:Vol_01:001"
    assert doc.doc_type == DocumentType.SUMMARY

    config = RAGConfig(top_k=3, embedding_model="test-embedding")
    assert config.top_k == 3
    assert config.embedding_model == "test-embedding"


def test_rag_engine_sparse_bm25_search(tmp_path: Path):
    """Verify SQLite FTS5 lexical BM25 indexing and retrieval."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    doc1 = LoreDocument(
        doc_id="summary:Vol_01:001",
        doc_type=DocumentType.SUMMARY,
        chapter_num=1,
        folder="Vol_01",
        title="The Royal Academy",
        content="Claire François confronted the commoner student in the academy hallway."
    )
    doc2 = LoreDocument(
        doc_id="summary:Vol_01:002",
        doc_type=DocumentType.SUMMARY,
        chapter_num=2,
        folder="Vol_01",
        title="Tea and Scones",
        content="Lene served warm black tea and scones in the noble dormitory."
    )
    engine.index_documents([doc1, doc2])
    assert engine.count_documents() == 2

    # Query for Claire
    results = engine.search_sparse("Claire", limit=5)
    assert len(results) == 1
    doc, rank, score = results[0]
    assert doc.doc_id == "summary:Vol_01:001"
    assert rank == 1

    # Query for tea
    results_tea = engine.search_sparse("tea", limit=5)
    assert len(results_tea) == 1
    assert results_tea[0][0].doc_id == "summary:Vol_01:002"


def test_rag_engine_dense_vector_search(tmp_path: Path):
    """Verify dense vector storage and cosine similarity ranking."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    v1 = [1.0, 0.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0, 0.0]
    v3 = [0.8, 0.6, 0.0, 0.0]

    doc1 = LoreDocument(doc_id="d1", content="Topic Alpha")
    doc2 = LoreDocument(doc_id="d2", content="Topic Beta")
    doc3 = LoreDocument(doc_id="d3", content="Topic Alpha-Beta Hybrid")

    engine.index_documents([doc1, doc2, doc3], [v1, v2, v3])

    # Search with query vector closest to v1
    query_vec = [0.95, 0.05, 0.0, 0.0]
    hits = engine.search_dense(query_vec, limit=2)
    assert len(hits) == 2
    assert hits[0][0].doc_id == "d1"  # Highest cosine similarity
    assert hits[1][0].doc_id == "d3"  # Second highest


def test_rag_engine_hybrid_rrf_fusion(tmp_path: Path):
    """Verify Reciprocal Rank Fusion combines sparse and dense ranks."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    # doc1: high lexical match for 'swordsman', orthogonal vector
    doc1 = LoreDocument(doc_id="doc_sword", content="Master swordsman Roderick drew his blade.")
    v1 = [0.0, 1.0, 0.0]

    # doc2: high semantic match (vector close to [1, 0, 0]), but does not mention swordsman explicitly
    doc2 = LoreDocument(doc_id="doc_duel", content="A fierce combat took place in the courtyard.")
    v2 = [0.9, 0.1, 0.0]

    # doc3: matches both!
    doc3 = LoreDocument(doc_id="doc_both", content="The elite swordsman clashed in fierce combat.")
    v3 = [0.8, 0.6, 0.0]

    engine.index_documents([doc1, doc2, doc3], [v1, v2, v3])

    query_text = "swordsman combat"
    query_vector = [0.85, 0.15, 0.0]

    hybrid_results = engine.hybrid_search(query=query_text, query_vector=query_vector, limit=3)
    assert len(hybrid_results) == 3

    # doc_both should rank #1 because it has strong ranks in both sparse and dense
    assert hybrid_results[0].doc_id == "doc_both"
    assert hybrid_results[0].rrf_score > hybrid_results[1].rrf_score


def test_rag_engine_delete_chapter(tmp_path: Path):
    """Verify delete_chapter cleans up documents from both tables."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    d1 = LoreDocument(doc_id="s:1", chapter_num=1, folder="Vol_01", content="Ch 1 summary")
    d2 = LoreDocument(doc_id="c:1:1", chapter_num=1, folder="Vol_01", content="Ch 1 chunk")
    d3 = LoreDocument(doc_id="s:2", chapter_num=2, folder="Vol_01", content="Ch 2 summary")

    engine.index_documents([d1, d2, d3])
    assert engine.count_documents() == 3

    engine.delete_chapter(1, folder="Vol_01")
    assert engine.count_documents() == 1
    assert engine.get_document("s:1") is None
    assert engine.get_document("c:1:1") is None
    assert engine.get_document("s:2") is not None


def test_embedding_client_mock():
    """Verify EmbeddingClient generates deterministic normalized mock vectors."""
    client = EmbeddingClient(model_name="mock-model")
    assert client.is_available

    v1 = client.embed_text("Claire François")
    v2 = client.embed_text("Claire François")
    v3 = client.embed_text("Completely Different Topic")

    assert v1 == v2
    assert v1 != v3
    assert len(v1) == 64
