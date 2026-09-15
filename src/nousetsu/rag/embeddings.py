"""Embedding provider for Hybrid Search RAG with Google Generative AI and Hermetic Mocking."""
import hashlib
import logging
import math
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


def generate_mock_embedding(text: str, dim: int = 64) -> List[float]:
    """Generate deterministic, unit-normalized pseudo-embedding for testing and offline environments."""
    if not text:
        return [0.0] * dim
    vec = [0.0] * dim
    words = text.lower().split()
    if not words:
        words = [text.lower()]
    for word in words:
        h = int(hashlib.md5(word.encode("utf-8", errors="ignore")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        return [round(x / norm, 6) for x in vec]
    vec[0] = 1.0
    return vec


def resolve_embedding_model_name(name: str) -> str:
    """Resolve user-friendly model alias to canonical Google model string."""
    clean = name.strip()
    if clean.startswith("models/"):
        return clean
    alias_map = {
        "gemini-embedding-2": "models/gemini-embedding-2",
        "gemini-embedding-002": "models/gemini-embedding-2",
        "gemini-embedding-2-preview": "models/gemini-embedding-2-preview",
        "text-multilingual-embedding-002": "models/gemini-embedding-2",
        "text-embedding-004": "models/gemini-embedding-2",
        "gemini-embedding-001": "models/gemini-embedding-001",
        "embedding-001": "models/gemini-embedding-001",
    }
    return alias_map.get(clean.lower(), f"models/{clean}")


class EmbeddingClient:
    """Provides vector embeddings using Google GenAI or offline deterministic mocking."""

    def __init__(
        self,
        model_name: str = "text-multilingual-embedding-002",
        api_key: Optional[str] = None
    ):
        self.raw_model_name = model_name
        self.is_mock = (
            model_name.lower().startswith(("mock", "test"))
            or bool(os.environ.get("PYTEST_CURRENT_TEST"))
            or os.environ.get("NOVEL_USE_MOCK_EMBEDDINGS", "").lower() in ("1", "true")
        )

        resolved_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )

        self._client = None
        if not self.is_mock and resolved_key:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                model_str = resolve_embedding_model_name(model_name)
                self._client = GoogleGenerativeAIEmbeddings(
                    model=model_str,
                    google_api_key=resolved_key
                )
            except Exception as e:
                logger.warning(f"Failed to initialize GoogleGenerativeAIEmbeddings ({e}). Falling back to mock/offline embeddings.")
                self._client = None

    @property
    def is_available(self) -> bool:
        """Return True if embeddings can be generated (either live or mock)."""
        return self.is_mock or self._client is not None

    def embed_text(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for single query or document string."""
        if not text or not text.strip():
            return None
        if self.is_mock:
            return generate_mock_embedding(text)
        if self._client is not None:
            try:
                return self._client.embed_query(text)
            except Exception as e:
                logger.warning(f"Live embedding API call failed: {e}. Falling back to deterministic embedding.")
                return generate_mock_embedding(text)
        return None

    def embed_documents(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embedding vectors for batch of documents."""
        if not texts:
            return []
        if self.is_mock:
            return [generate_mock_embedding(t) if t and t.strip() else None for t in texts]
        if self._client is not None:
            try:
                # langchain embed_documents returns list of embeddings
                results = self._client.embed_documents(texts)
                return results
            except Exception as e:
                logger.warning(f"Live batch embedding API call failed: {e}. Falling back to mock embeddings.")
                return [generate_mock_embedding(t) if t and t.strip() else None for t in texts]
        return [None] * len(texts)
