"""Data models and type definitions for eBook ingestion and compilation."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EbookChapter(BaseModel):
    """Represents a single chapter extracted from or compiled into an eBook."""
    index: int = Field(..., description="1-based sequence index")
    title: str = Field(..., description="Chapter title or heading")
    content_text: str = Field(..., description="Markdown or clean plain text of chapter")
    images: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted illustrations: {'name': str, 'ext': str, 'data': bytes/str}")
    source_file: Optional[str] = Field(None, description="Original filename if relevant")

    @property
    def content(self) -> str:
        return self.content_text


class EbookMetadata(BaseModel):
    """Metadata for an entire novel eBook container."""
    title: str = Field(..., description="Novel title")
    author: Optional[str] = Field(None, description="Author name")
    language: str = Field("th", description="Language code (e.g. 'th', 'en', 'ja')")
    description: Optional[str] = Field(None, description="Synopsis or description")
    publisher: Optional[str] = Field("NouSetsu", description="Publisher / Translation team")
    cover_image_bytes: Optional[bytes] = Field(None, description="Raw binary bytes of cover art")
    cover_image_ext: Optional[str] = Field("jpg", description="Cover image extension ('jpg', 'png', etc.)")
    chapters: List[EbookChapter] = Field(default_factory=list, description="Ordered chapter list")


class EbookInspectChapterItem(BaseModel):
    """Lightweight summary of an inspected chapter for UI preview and selection."""
    index: int
    title: str
    word_count: int
    has_images: bool = False


class EbookInspectResult(BaseModel):
    """Result returned by eBook inspector before committing extraction."""
    title: str
    author: Optional[str] = None
    format: str = "epub"  # 'epub' | 'pdf'
    total_chapters: int
    chapters: List[EbookInspectChapterItem]
    has_cover: bool = False
    cover_base64: Optional[str] = None


class EbookImportParams(BaseModel):
    """Parameters passed to import/extract chapters from inspected file into project."""
    project_path: Optional[str] = None
    folder: Optional[str] = None
    chapter_indices: Optional[List[int]] = None
    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None
    overwrite: bool = False
    extract_images: bool = True


class EbookExportOptions(BaseModel):
    """Configuration for exporting translated chapters to EPUB or Printable PDF."""
    project_path: Optional[str] = None
    folder: Optional[str] = None
    chapter_indices: Optional[List[int]] = None
    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None
    format: str = Field("epub", description="'epub' or 'html_print'")
    title: Optional[str] = None
    author: Optional[str] = None
    language: str = "th"
    include_bible_appendix: bool = True
    apply_thai_word_wrap: bool = True
