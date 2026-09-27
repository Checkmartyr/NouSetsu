"""
Data models for Novel-Scraper integration in NouSetsu.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScraperChapterItem(BaseModel):
    """Metadata for a single chapter discovered on a novel website."""
    index: int = Field(..., description="1-based chapter sequence index")
    title: str = Field(..., description="Chapter title as found on TOC")
    url: str = Field(..., description="Source URL of the chapter")


class ScraperInspectRequest(BaseModel):
    """Request payload to inspect a webnovel URL."""
    url: str = Field(..., description="Webnovel Table of Contents or chapter URL")


class ScraperInspectResponse(BaseModel):
    """Response payload containing novel metadata and discovered chapter list."""
    success: bool
    url: str
    page_type: Optional[str] = "TOC"
    novel_title: str = "Unknown Novel"
    author: Optional[str] = None
    description: Optional[str] = None
    total_chapters: int = 0
    chapters: List[ScraperChapterItem] = Field(default_factory=list)
    error: Optional[str] = None


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


class ScraperStatusResponse(BaseModel):
    """Status update for an ongoing or completed scraping task."""
    task_id: str
    status: str = Field(..., description="'pending' | 'running' | 'completed' | 'failed'")
    progress_percent: float = 0.0
    current_chapter: int = 0
    total_chapters: int = 0
    current_title: Optional[str] = None
    message: str = ""
    completed_files: List[str] = Field(default_factory=list)
    output_dir: Optional[str] = None
    error: Optional[str] = None
