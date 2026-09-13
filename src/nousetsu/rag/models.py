"""Data models for Hybrid Search RAG (LoreVault)."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    SUMMARY = "summary"
    CHUNK = "chunk"
    GLOSSARY = "glossary"
    CHARACTER = "character"


class LoreDocument(BaseModel):
    """A document indexed within the hybrid search knowledge store."""
    doc_id: str = Field(..., description="Unique document ID e.g. 'summary:Villainess_04:012'")
    doc_type: DocumentType = Field(default=DocumentType.SUMMARY, description="Category of lore item")
    chapter_num: int = Field(default=0, description="Associated chapter sequence number")
    folder: Optional[str] = Field(default=None, description="Associated volume/folder scope")
    title: str = Field(default="", description="Headline or title")
    content: str = Field(..., description="Indexed text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extra metadata")


class SearchResult(BaseModel):
    """Ranked retrieval result combining sparse and dense matching."""
    doc_id: str
    doc_type: DocumentType
    chapter_num: int = 0
    folder: Optional[str] = None
    title: str = ""
    content: str
    sparse_rank: Optional[int] = None
    dense_rank: Optional[int] = None
    sparse_score: Optional[float] = None
    dense_score: Optional[float] = None
    rrf_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGConfig(BaseModel):
    """Settings governing hybrid search and context injection."""
    top_k: int = Field(default=2, description="Number of lore snippets to inject into drafting prompt")
    embedding_model: str = Field(default="text-embedding-004", description="Dense embedding model")
    rrf_k: int = Field(default=60, description="Reciprocal Rank Fusion constant (standard 60)")
    chunk_size_lines: int = Field(default=20, description="Lines per scene chunk when indexing chapters")
