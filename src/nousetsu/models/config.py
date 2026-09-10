"""Project configuration schema."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    """Configuration settings for a novel translation project."""

    project_id: str = Field(default="default_project")
    title: str = Field(default="Untitled Novel")
    source_language: str = Field(default="Japanese")
    target_language: str = Field(default="English")
    raw_dir: str = Field(default="raw_chapters", description="Path to input raw chapter files")
    output_dir: str = Field(default="translated_chapters", description="Path to output translated files")
    model_name: str = Field(default="gemini-2.5-pro", description="Default LLM model name")
    auto_update_bible: bool = Field(default=True, description="Automatically merge newly discovered characters, terms, and summaries into Novel Bible")
    max_tpm: int = Field(default=16000, description="Max tokens per minute rate limit quota")
    max_rpm: int = Field(default=60, description="Max requests per minute rate limit quota")
    max_review_loops: int = Field(default=3, ge=1, le=5, description="Maximum review loops for translation refinement")
    quality_threshold: float = Field(default=8.5, ge=5.0, le=10.0, description="Quality score threshold (fidelity & style) to exit review loop")
    genre: str = Field(default="general", description="Novel genre (e.g. xianxia, isekai, litrpg, romance, general)")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def get_raw_path(self, base_dir: Path) -> Path:
        p = Path(self.raw_dir).expanduser()
        if p.is_absolute():
            return p.resolve()
        candidate = (base_dir / p).resolve()
        if candidate.exists():
            return candidate
        try:
            base_dir.resolve().relative_to(Path.cwd().resolve())
            cwd_candidate = (Path.cwd() / p).resolve()
            if cwd_candidate.exists():
                return cwd_candidate
        except ValueError:
            pass
        return candidate

    def get_output_path(self, base_dir: Path) -> Path:
        p = Path(self.output_dir).expanduser()
        if p.is_absolute():
            return p.resolve()
        candidate = (base_dir / p).resolve()
        if candidate.exists():
            return candidate
        try:
            base_dir.resolve().relative_to(Path.cwd().resolve())
            cwd_candidate = (Path.cwd() / p).resolve()
            if cwd_candidate.exists():
                return cwd_candidate
        except ValueError:
            pass
        return candidate
