"""Project configuration schema."""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    """Configuration settings for a novel translation project."""

    project_id: str = Field(default="default_project")
    title: str = Field(default="Ascendance of a Bookworm")
    source_language: str = Field(default="English")
    target_language: str = Field(default="Thai")
    raw_dir: str = Field(default="raw_chapters", description="Path to input raw chapter files")
    output_dir: str = Field(default="translated_chapters", description="Path to output translated files")
    model_name: Optional[str] = Field(default=None, description="Default LLM model override (defaults to .env NOVEL_MODEL)")
    fallback_model: Optional[str] = Field(default=None, description="Global fallback LLM model override (defaults to .env NOVEL_FALLBACK_MODEL)")
    extractor_model: Optional[str] = Field(default=None, description="LLM model override for Entity Extractor Agent")
    drafter_model: Optional[str] = Field(default=None, description="LLM model override for Drafter Agent")
    critic_model: Optional[str] = Field(default=None, description="LLM model override for Critique Agent")
    polisher_model: Optional[str] = Field(default=None, description="LLM model override for Polisher Agent")
    chronicler_model: Optional[str] = Field(default=None, description="LLM model override for Chronicler Agent")
    use_interactions_api: bool = Field(default=True, description="Use Gemini Interactions API for Gemini models")
    auto_update_bible: bool = Field(default=True, description="Automatically merge newly discovered characters, terms, and summaries into Novel Bible")
    max_tpm: int = Field(default=32000, description="Max tokens per minute rate limit quota")
    max_rpm: int = Field(default=60, description="Max requests per minute rate limit quota")
    max_review_loops: int = Field(default=3, ge=1, le=5, description="Maximum review loops for translation refinement")
    quality_threshold: float = Field(default=8.5, ge=5.0, le=10.0, description="Quality score threshold (fidelity & style) to exit review loop")
    genre: str = Field(default="general", description="Novel genre (e.g. xianxia, isekai, litrpg, romance, general)")
    enable_chunking: bool = Field(default=True, description="Enable line-based semantic chunking for long chapters")
    chunk_threshold_lines: int = Field(default=85, description="Minimum non-empty lines to trigger chunked drafting and polishing")
    target_chunk_lines: int = Field(default=70, description="Target line count per chunk")
    chunk_overlap_lines: int = Field(default=3, description="Lines of preceding translated context passed to next chunk")
    cross_folder_summaries: bool = Field(default=True, description="Enable rolling context backfill across sequential folders")
    safety_recursive_subdivision: bool = Field(default=True, description="Enable recursive bisection of safety-blocked chunks")
    safety_subdivision_min_lines: int = Field(default=8, description="Minimum non-empty lines before terminating subdivision")
    safety_subdivision_max_depth: int = Field(default=4, description="Maximum recursion depth for bisection")
    enable_rag: bool = Field(default=True, description="Enable hybrid search episodic lore retrieval (Tier 4 Memory)")
    rag_top_k: int = Field(default=2, ge=1, le=10, description="Top N historical lore snippets to retrieve per chapter")
    rag_embedding_model: Optional[str] = Field(default=None, description="Dense embedding model override (defaults to text-multilingual-embedding-002)")
    enable_rag_reranker: bool = Field(default=True, description="Enable Cross-Encoder reranking stage after hybrid retrieval")
    rag_reranker_model: Optional[str] = Field(default=None, description="Model override for Cross-Encoder reranker (defaults to gemini-3.5-flash-lite)")
    filter_scene_characters: bool = Field(default=True, description="Filter character roster per scene/chunk based on textual presence and core roles")
    max_scene_characters: int = Field(default=15, ge=1, le=50, description="Maximum characters retained in per-scene filter fallback")
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

    def get_model_name(self) -> str:
        """Resolve effective model_name: config override -> .env NOVEL_MODEL -> .env DEFAULT_MODEL -> default."""
        return (
            self.model_name
            or os.environ.get("NOVEL_MODEL")
            or os.environ.get("DEFAULT_MODEL")
            or "gemini-3.1-flash-lite"
        )

    def get_fallback_model(self) -> Optional[str]:
        """Resolve effective fallback_model: config override -> .env NOVEL_FALLBACK_MODEL -> default."""
        return self.fallback_model or os.environ.get("NOVEL_FALLBACK_MODEL") or "gemini-3.5-flash-lite"

    def get_agent_model(self, role: str) -> str:
        """Return configured model for agent role with priority: project override -> .env -> global model."""
        role_map = {
            "extractor": self.extractor_model,
            "drafter": self.drafter_model,
            "critic": self.critic_model,
            "polisher": self.polisher_model,
            "chronicler": self.chronicler_model,
        }
        override = role_map.get(role)
        if override:
            return override
        if self.model_name:
            return self.model_name
        env_val = os.environ.get(f"NOVEL_{role.upper()}_MODEL")
        if env_val:
            return env_val
        return self.get_model_name()

    def get_agent_fallback_model(self, role: Optional[str] = None) -> Optional[str]:
        """Return fallback model for agent role or global fallback_model."""
        return self.get_fallback_model()

    def get_rag_embedding_model(self) -> str:
        """Resolve effective rag_embedding_model: config override -> .env NOVEL_RAG_EMBEDDING_MODEL -> default."""
        return (
            self.rag_embedding_model
            or os.environ.get("NOVEL_RAG_EMBEDDING_MODEL")
            or "text-multilingual-embedding-002"
        )

    def get_rag_reranker_model(self) -> str:
        """Resolve effective rag_reranker_model: config override -> .env NOVEL_RAG_RERANKER_MODEL -> default."""
        return (
            self.rag_reranker_model
            or os.environ.get("NOVEL_RAG_RERANKER_MODEL")
            or "gemini-3.5-flash-lite"
        )


