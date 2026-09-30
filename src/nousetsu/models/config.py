"""Project configuration schema."""
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from pydantic import BaseModel, Field


GENERATION_ROLES = ("extractor", "drafter", "critic", "polisher", "chronicler", "scraper")
DEFAULT_AGENT_MODELS = {
    "extractor": "gemini-3.1-flash-lite",
    "drafter": "gemini-3.5-flash-lite",
    "critic": "gemma-4-26b-a4b-it",
    "polisher": "gemini-3.5-flash-lite",
    "chronicler": "gemma-4-26b-a4b-it",
    "scraper": "gemini-3.1-flash-lite",
}
DEFAULT_AGENT_TEMPERATURES = {
    "extractor": 0.1,
    "drafter": 1.0,
    "critic": 0.1,
    "polisher": 1.0,
    "chronicler": 0.2,
    "scraper": 1.0,
}
LANGUAGE_FOLDER_CODES = {
    "arabic": "ar", "ar": "ar", "bengali": "bn", "bn": "bn",
    "chinese": "zh", "zh": "zh", "zh_cn": "zh", "zh_tw": "zh",
    "danish": "da", "da": "da", "dutch": "nl", "nl": "nl",
    "english": "en", "en": "en", "finnish": "fi", "fi": "fi",
    "french": "fr", "fr": "fr", "german": "de", "de": "de",
    "greek": "el", "el": "el", "hindi": "hi", "hi": "hi",
    "indonesian": "id", "id": "id", "italian": "it", "it": "it",
    "japanese": "ja", "ja": "ja", "jp": "ja", "korean": "ko", "ko": "ko",
    "malay": "ms", "ms": "ms", "norwegian": "no", "no": "no",
    "polish": "pl", "pl": "pl", "portuguese": "pt", "pt": "pt",
    "russian": "ru", "ru": "ru", "spanish": "es", "es": "es",
    "swedish": "sv", "sv": "sv", "thai": "th", "th": "th",
    "turkish": "tr", "tr": "tr", "ukrainian": "uk", "uk": "uk",
    "vietnamese": "vi", "vi": "vi",
}


class AgentGenerationSettings(BaseModel):
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    thinking_level: Optional[str] = None
    thinking_budget: Optional[int] = Field(default=None, ge=0)
    use_interactions_api: Optional[bool] = None


def _parse_env_float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _parse_env_int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _parse_env_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or not value.strip():
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_agent_generation_settings(
    role: str,
    project_settings: Optional[AgentGenerationSettings | Mapping[str, Any]] = None,
    legacy_use_interactions: Optional[bool] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Resolve a role's controls from project overrides, role env, and shared defaults."""
    if role not in GENERATION_ROLES:
        raise ValueError(f"Unknown generation role: {role}")
    env = os.environ if environ is None else environ
    if isinstance(project_settings, AgentGenerationSettings):
        project_values = project_settings.model_dump()
    else:
        project_values = dict(project_settings or {})
    prefix = f"NOVEL_{role.upper()}"

    def project_value(name: str) -> Any:
        value = project_values.get(name)
        if isinstance(value, str):
            return value.strip() or None
        return value

    temperature = project_value("temperature")
    if temperature is None:
        temperature = _parse_env_float(env.get(f"{prefix}_TEMPERATURE"))
    if temperature is None:
        temperature = _parse_env_float(env.get("NOVEL_TEMPERATURE"))
    if temperature is None:
        temperature = DEFAULT_AGENT_TEMPERATURES[role]

    thinking_level = (
        project_value("thinking_level")
        or env.get(f"{prefix}_THINKING_LEVEL")
        or env.get("NOVEL_THINKING_LEVEL")
        or ("medium" if role == "critic" else None)
    )
    thinking_budget = project_value("thinking_budget")
    if thinking_budget is None:
        thinking_budget = _parse_env_int(env.get(f"{prefix}_THINKING_BUDGET"))
    if thinking_budget is None:
        thinking_budget = _parse_env_int(env.get("NOVEL_THINKING_BUDGET"))

    use_interactions = project_value("use_interactions_api")
    if use_interactions is None:
        use_interactions = legacy_use_interactions
    if use_interactions is None:
        use_interactions = _parse_env_bool(env.get(f"{prefix}_USE_INTERACTIONS"))
    if use_interactions is None:
        use_interactions = _parse_env_bool(env.get("NOVEL_USE_INTERACTIONS"))
    if use_interactions is None:
        use_interactions = True

    return {
        "temperature": float(temperature),
        "thinking_level": thinking_level,
        "thinking_budget": thinking_budget,
        "use_interactions_api": use_interactions,
    }


class ProjectConfig(BaseModel):
    """Configuration settings for a novel translation project."""

    project_id: str = Field(default="default_project")
    title: str = Field(default="Untitle")
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
    scraper_model: Optional[str] = Field(default=None, description="LLM model override for Novel Scraper")
    generation_settings: Dict[str, AgentGenerationSettings] = Field(default_factory=dict)
    use_interactions_api: Optional[bool] = Field(default=None, description="Legacy project-wide Gemini Interactions override")
    auto_update_bible: bool = Field(default=True, description="Automatically merge newly discovered characters, terms, and summaries into Novel Bible")
    max_tpm: int = Field(default=32000, description="Max tokens per minute rate limit quota")
    max_rpm: int = Field(default=60, description="Max requests per minute rate limit quota")
    max_review_loops: int = Field(default=3, ge=1, le=5, description="Maximum review loops for translation refinement")
    quality_threshold: float = Field(default=8.5, ge=5.0, le=10.0, description="Quality score threshold (fidelity & style) to exit review loop")
    genre: str = Field(default="general", description="Novel genre (e.g. xianxia, isekai, litrpg, romance, general)")
    enable_chunking: bool = Field(default=True, description="Enable line-based semantic chunking for long chapters")
    chunk_threshold_lines: int = Field(default=800, description="Minimum non-empty lines to trigger chunked drafting and polishing")
    target_chunk_lines: int = Field(default=400, description="Target line count per chunk")
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
    filter_extractor_entities: Optional[bool] = Field(default=None, description="Filter known characters and glossary per chunk/chapter in Entity Extractor to save tokens and avoid quota exhaustion")
    enable_patch_polishing: bool = Field(default=True, description="Enable search/replace diff patching for secondary polish passes to save output tokens")
    enable_post_polish_reconciliation: bool = Field(default=True, description="Enable post-polish term and entity reconciliation by Chronicler Agent")
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

    @property
    def target_language_code(self) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", self.target_language.strip().lower()).strip("_")
        base_name = normalized.split("_", 1)[0]
        return LANGUAGE_FOLDER_CODES.get(normalized) or LANGUAGE_FOLDER_CODES.get(base_name) or normalized or "target"

    def get_volume_output_path(
        self,
        base_dir: Path,
        raw_folder: str,
        default_output_path: Optional[Path] = None,
    ) -> Path:
        target_path = Path(base_dir) / f"{raw_folder}_{self.target_language_code}"
        suffixes = dict.fromkeys((self.target_language_code, "trans"))
        for suffix in suffixes:
            candidate = Path(base_dir) / f"{raw_folder}_{suffix}"
            if candidate.exists():
                return candidate
        return Path(default_output_path) if default_output_path is not None else target_path

    def is_volume_output_folder_name(self, name: str) -> bool:
        normalized = name.lower()
        suffix = normalized.rsplit("_", 1)[-1]
        known_codes = set(LANGUAGE_FOLDER_CODES.values())
        return (
            normalized == "translated_chapters"
            or suffix in known_codes | {"trans", "out"}
            or normalized.endswith(f"_{self.target_language_code}")
        )

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

    def get_model_name(self, environ: Optional[Mapping[str, str]] = None) -> str:
        """Resolve primary route from project, machine defaults, then the built-in default."""
        env = os.environ if environ is None else environ
        return self.model_name or env.get("NOVEL_MODEL") or env.get("DEFAULT_MODEL") or "gemini-3.1-flash-lite"

    def get_fallback_model(self, environ: Optional[Mapping[str, str]] = None) -> Optional[str]:
        """Resolve the shared fallback route from project and machine defaults."""
        env = os.environ if environ is None else environ
        return self.fallback_model or env.get("NOVEL_FALLBACK_MODEL") or "gemini-3.5-flash-lite"

    def get_agent_model(self, role: str, environ: Optional[Mapping[str, str]] = None) -> str:
        """Resolve a route consistently for the settings UI and batch runtime."""
        if role not in GENERATION_ROLES:
            raise ValueError(f"Unknown model role: {role}")
        env = os.environ if environ is None else environ
        project_route = getattr(self, f"{role}_model", None)
        if project_route:
            return project_route
        env_route = env.get(f"NOVEL_{role.upper()}_MODEL")
        if role == "scraper" and env_route:
            return env_route
        if self.model_name:
            return self.model_name
        if env_route:
            return env_route
        env_primary = env.get("NOVEL_MODEL") or env.get("DEFAULT_MODEL")
        if env_primary:
            return env_primary
        return DEFAULT_AGENT_MODELS[role]

    def get_agent_generation_settings(
        self, role: str, environ: Optional[Mapping[str, str]] = None
    ) -> Dict[str, Any]:
        """Resolve project or machine generation controls for one role."""
        return resolve_agent_generation_settings(
            role,
            project_settings=self.generation_settings.get(role),
            legacy_use_interactions=self.use_interactions_api,
            environ=environ,
        )

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

    def get_filter_extractor_entities(self) -> bool:
        """Resolve effective filter_extractor_entities: config override -> .env -> default (True)."""
        if self.filter_extractor_entities is not None:
            return self.filter_extractor_entities
        env_val = os.environ.get("NOVEL_FILTER_EXTRACTOR_ENTITIES")
        if env_val is not None:
            return env_val.strip().lower() in ("true", "1", "yes")
        return True

    def get_post_polish_reconciliation(self) -> bool:
        """Resolve effective enable_post_polish_reconciliation: config override -> .env -> default (True)."""
        if self.enable_post_polish_reconciliation is not None:
            return self.enable_post_polish_reconciliation
        env_val = os.environ.get("NOVEL_POST_POLISH_RECONCILIATION")
        if env_val is not None:
            return env_val.strip().lower() in ("true", "1", "yes")
        return True
