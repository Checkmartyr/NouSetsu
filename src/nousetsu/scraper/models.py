"""
Data models for Novel-Scraper integration in NouSetsu.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator, field_validator
from urllib.parse import urlsplit
from nousetsu.models.config import ScraperBudgets


class ScraperChapterItem(BaseModel):
    """Metadata for a single chapter discovered on a novel website."""
    index: int = Field(..., description="1-based chapter sequence index")
    title: str = Field(..., description="Chapter title as found on TOC")
    url: str = Field(..., description="Source URL of the chapter")
    volume: Optional[str] = None


class ScraperInspectRequest(BaseModel):
    """Request payload to inspect a webnovel URL."""
    url: str = Field(..., description="Webnovel Table of Contents or chapter URL")
    project_path: Optional[str] = Field(None, description="Project whose scraper model settings should be used")

    @field_validator("url")
    @classmethod
    def web_url(cls, value):
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Use an HTTP(S) website URL without embedded credentials")
        return value.strip()


class ScraperChapterRange(BaseModel):
    """Source chapter labels; one linked entry may contain a bundled range."""
    url: str
    start: float
    end: float


class ScraperInspectResponse(BaseModel):
    """Response payload containing novel metadata and discovered chapter list."""
    success: bool
    url: str
    page_type: Optional[str] = "TOC"
    toc_url: Optional[str] = None
    final_url: Optional[str] = None
    source_scope: Dict[str, Any] = Field(default_factory=dict)
    linked_entry_count: Optional[int] = None
    observed_linked_entry_count: Optional[int] = None
    highest_observed_chapter_number: Optional[float] = None
    highest_chapter_number: Optional[float] = None
    numbered_chapter_ranges: List[ScraperChapterRange] = Field(default_factory=list)
    novel_title: str = "Unknown Novel"
    romanized_title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    total_chapters: int = 0
    chapters: List[ScraperChapterItem] = Field(default_factory=list)
    error: Optional[str] = None
    inspection_id: Optional[str] = None
    is_complete: bool = False
    claimed_chapter_count: Optional[int] = None
    confidence_score: float = 0
    completeness_evidence: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


class ScraperExtractRequest(BaseModel):
    """Request payload to extract chapters from a webnovel URL into a project."""
    url: str = Field(..., description="Webnovel URL to scrape")
    project_path: Optional[str] = Field(None, description="Target project root directory")
    folder: Optional[str] = Field(None, description="Destination subfolder or volume (e.g. raw_chapters or Vol_01)")
    chapter_indices: Optional[List[int]] = Field(None, description="Specific chapter indices to extract")
    start_chapter: Optional[int] = Field(None, description="Start chapter index for range extraction")
    end_chapter: Optional[int] = Field(None, description="End chapter index for range extraction")
    concurrency: int = Field(3, ge=1, le=10, description="Concurrent download workers")
    include_frontmatter: bool = Field(False, description="Whether to include YAML frontmatter in markdown files")
    overwrite: bool = Field(False, description="Whether to overwrite existing chapter files")
    inspection_id: Optional[str] = Field(None, pattern=r"^[a-f0-9]{32}$")
    session_state: Optional[str] = None
    budgets: Optional[ScraperBudgets] = None

    @model_validator(mode="after")
    def validate_selection(self):
        self.url = ScraperInspectRequest.web_url(self.url)
        if self.chapter_indices is not None and (not self.chapter_indices or any(i < 1 for i in self.chapter_indices)):
            raise ValueError("Explicit chapter selection must contain positive indices")
        if any(i is not None and i < 1 for i in (self.start_chapter, self.end_chapter)):
            raise ValueError("Chapter range must contain positive indices")
        if self.start_chapter is not None and self.end_chapter is not None and self.start_chapter > self.end_chapter:
            raise ValueError("Chapter range start exceeds end")
        return self


class ScraperStatusResponse(BaseModel):
    """Status update for an ongoing or completed scraping task."""
    task_id: str
    url: Optional[str] = None
    folder: Optional[str] = None
    status: str = Field(..., description="'pending' | 'running' | 'completed' | 'failed'")
    progress_percent: float = 0.0
    current_chapter: int = 0
    total_chapters: int = 0
    current_title: Optional[str] = None
    message: str = ""
    completed_files: List[str] = Field(default_factory=list)
    output_dir: Optional[str] = None
    error: Optional[str] = None
    stage: str = "pending"
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    blocked: int = 0
    cancelled: int = 0
    is_complete: bool = False
    completeness_evidence: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    outcomes: List[Dict[str, Any]] = Field(default_factory=list)
