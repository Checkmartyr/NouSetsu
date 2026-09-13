"""Hybrid Search RAG (Tier 4 Episodic & Associative Memory) for NouSetsu."""
from nousetsu.rag.embeddings import EmbeddingClient, generate_mock_embedding
from nousetsu.rag.engine import HybridSearchEngine
from nousetsu.rag.models import DocumentType, LoreDocument, RAGConfig, SearchResult
from nousetsu.rag.reranker import (
    BaseCrossEncoderReranker,
    LLMCrossEncoderReranker,
    MockCrossEncoderReranker,
    get_reranker,
)

__all__ = [
    "BaseCrossEncoderReranker",
    "DocumentType",
    "EmbeddingClient",
    "HybridSearchEngine",
    "LLMCrossEncoderReranker",
    "LoreDocument",
    "MockCrossEncoderReranker",
    "RAGConfig",
    "SearchResult",
    "generate_mock_embedding",
    "get_reranker",
]
