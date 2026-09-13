"""SQLAlchemy 2.0 ORM models for RAG knowledge store (LoreVault)."""
import json
import time
from typing import Any, Dict, Optional

from sqlalchemy import Float, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nousetsu.rag.models import DocumentType, LoreDocument


class Base(DeclarativeBase):
    """Base declarative class for RAG relational tables."""
    pass


class LoreDocumentORM(Base):
    """SQLAlchemy 2.0 declarative model representing an indexed lore document."""
    __tablename__ = "lore_documents"

    doc_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    chapter_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    folder: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, nullable=False)

    __table_args__ = (
        Index("idx_lore_chapter", "chapter_num", "folder"),
        Index("idx_lore_type", "doc_type"),
    )

    def to_domain(self) -> LoreDocument:
        """Convert SQLAlchemy ORM entity to Pydantic LoreDocument domain model."""
        meta: Dict[str, Any] = {}
        if self.metadata_json:
            try:
                meta = json.loads(self.metadata_json)
            except Exception:
                meta = {}

        return LoreDocument(
            doc_id=self.doc_id,
            doc_type=DocumentType(self.doc_type),
            chapter_num=self.chapter_num or 0,
            folder=self.folder,
            title=self.title or "",
            content=self.content,
            metadata=meta
        )

    @classmethod
    def from_domain(
        cls,
        doc: LoreDocument,
        embedding_blob: Optional[bytes] = None
    ) -> "LoreDocumentORM":
        """Construct SQLAlchemy ORM entity from Pydantic LoreDocument domain model."""
        meta_str = json.dumps(doc.metadata, ensure_ascii=False) if doc.metadata else None
        return cls(
            doc_id=doc.doc_id,
            doc_type=doc.doc_type.value,
            chapter_num=doc.chapter_num,
            folder=doc.folder,
            title=doc.title,
            content=doc.content,
            metadata_json=meta_str,
            embedding=embedding_blob,
            created_at=time.time()
        )
