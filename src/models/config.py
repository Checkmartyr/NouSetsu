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
