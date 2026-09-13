"""Unit tests for Gemini Embedding 2 and Cross-Encoder Reranker."""
from pathlib import Path
import pytest
from langchain_core.messages import AIMessage
from nousetsu.rag.embeddings import EmbeddingClient, resolve_embedding_model_name
from nousetsu.rag.engine import HybridSearchEngine
from nousetsu.rag.models import DocumentType, LoreDocument, SearchResult
from nousetsu.rag.reranker import (
    BaseCrossEncoderReranker,
    LLMCrossEncoderReranker,
    MockCrossEncoderReranker,
    get_reranker,
)


def test_resolve_embedding_model_name():
    """Verify model aliases for Gemini Embedding 2 resolve to canonical Google model paths."""
    assert resolve_embedding_model_name("gemini-embedding-2") == "models/text-multilingual-embedding-002"
    assert resolve_embedding_model_name("gemini-embedding-002") == "models/text-multilingual-embedding-002"
    assert resolve_embedding_model_name("text-multilingual-embedding-002") == "models/text-multilingual-embedding-002"
    assert resolve_embedding_model_name("text-embedding-004") == "models/text-embedding-004"
    assert resolve_embedding_model_name("models/custom-emb") == "models/custom-emb"


def test_mock_cross_encoder_reranking():
    """Verify MockCrossEncoderReranker scores and re-sorts documents based on query overlap and RRF."""
    reranker = MockCrossEncoderReranker()

    d1 = SearchResult(
        doc_id="d1",
        doc_type=DocumentType.SUMMARY,
        title="Royal Academy Breakfast",
        content="The students enjoyed fresh pastries and coffee in the courtyard.",
        rrf_score=0.030
    )
    d2 = SearchResult(
        doc_id="d2",
        doc_type=DocumentType.CHUNK,
        title="Training Grounds",
        content="Sir Roderick drew his legendary silver sword and began the combat duel.",
        rrf_score=0.015
    )

    # In Stage 1, d1 had a higher RRF score (0.030 > 0.015).
    # But query specifically asks for "silver sword combat duel".
    reranked = reranker.rerank(query="silver sword combat duel", documents=[d1, d2], top_k=2)

    assert len(reranked) == 2
    # Cross-encoder should boost d2 to #1 because of heavy token interaction
    assert reranked[0].doc_id == "d2"
    assert reranked[0].rerank_rank == 1
    assert reranked[0].rerank_score > reranked[1].rerank_score
    assert reranked[1].doc_id == "d1"
    assert reranked[1].rerank_rank == 2


def test_llm_cross_encoder_with_mock_response():
    """Verify LLMCrossEncoderReranker parses structured JSON responses and assigns scores."""
    reranker = LLMCrossEncoderReranker(model_name="mock-model")

    # Mock the LLM invoke
    class DummyLLM:
        def invoke(self, messages):
            return AIMessage(content="""
```json
[
  {"doc_id": "doc_b", "score": 0.95, "reason": "Direct reference to secret identity"},
  {"doc_id": "doc_a", "score": 0.20, "reason": "Irrelevant casual chat"}
]
```
""")

    reranker.llm = DummyLLM()

    d_a = SearchResult(doc_id="doc_a", doc_type=DocumentType.SUMMARY, content="General chat.", rrf_score=0.030)
    d_b = SearchResult(doc_id="doc_b", doc_type=DocumentType.SUMMARY, content="Secret identity reveal.", rrf_score=0.015)

    results = reranker.rerank(query="Who discovered the secret identity?", documents=[d_a, d_b], top_k=2)

    assert len(results) == 2
    assert results[0].doc_id == "doc_b"
    assert results[0].rerank_score == 0.95
    assert results[0].rerank_rank == 1
    assert results[1].doc_id == "doc_a"
    assert results[1].rerank_score == 0.20
    assert results[1].rerank_rank == 2


def test_llm_cross_encoder_fallback_on_error():
    """Verify LLMCrossEncoderReranker gracefully falls back to Stage 1 RRF ranking on failure."""
    reranker = LLMCrossEncoderReranker(model_name="mock-model")

    class FailingLLM:
        def invoke(self, messages):
            raise RuntimeError("API Rate Limit or Network Error")

    reranker.llm = FailingLLM()

    d1 = SearchResult(doc_id="d1", doc_type=DocumentType.SUMMARY, content="Content A", rrf_score=0.040)
    d2 = SearchResult(doc_id="d2", doc_type=DocumentType.SUMMARY, content="Content B", rrf_score=0.020)

    results = reranker.rerank(query="Any query", documents=[d1, d2], top_k=2)

    assert len(results) == 2
    assert results[0].doc_id == "d1"  # Preserved RRF order
    assert results[1].doc_id == "d2"


def test_hybrid_search_with_cross_encoder(tmp_path: Path):
    """Verify HybridSearchEngine integrates Cross-Encoder reranking in hybrid_search()."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    doc1 = LoreDocument(
        doc_id="d1",
        title="Royal Academy Breakfast",
        content="Commoner students ate toast in the dining hall."
    )
    doc2 = LoreDocument(
        doc_id="d2",
        title="Knight Order",
        content="Sir Roderick demonstrated the sacred flame technique with his greatsword."
    )
    engine.index_documents([doc1, doc2])

    reranker = MockCrossEncoderReranker()
    results = engine.hybrid_search(
        query="sacred flame greatsword technique",
        limit=1,
        reranker=reranker,
        enable_rerank=True
    )

    assert len(results) == 1
    assert results[0].doc_id == "d2"
    assert results[0].rerank_score is not None
    assert results[0].rerank_rank == 1


def test_get_reranker_factory():
    """Verify get_reranker factory returns MockCrossEncoderReranker under test/mock environment."""
    r_mock = get_reranker(is_mock=True)
    assert isinstance(r_mock, MockCrossEncoderReranker)

    r_test = get_reranker("test-reranker")
    assert isinstance(r_test, MockCrossEncoderReranker)
