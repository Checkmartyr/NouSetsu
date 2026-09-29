"""Central environment discovery and dotenv cascade management."""
import logging
import os
import stat
from pathlib import Path
from typing import Dict, Optional, Union
import dotenv

logger = logging.getLogger(__name__)

ENV_CONFIG_KEYS = (
    "DEFAULT_MODEL",
    "NOVEL_MODEL",
    "NOVEL_FALLBACK_MODEL",
    "NOVEL_SCRAPER_MODEL",
    "NOVEL_SCRAPER_TEMPERATURE",
    "NOVEL_SCRAPER_THINKING_LEVEL",
    "NOVEL_SCRAPER_THINKING_BUDGET",
    "NOVEL_SCRAPER_USE_INTERACTIONS",
    "NOVEL_EXTRACTOR_MODEL",
    "NOVEL_EXTRACTOR_TEMPERATURE",
    "NOVEL_EXTRACTOR_USE_INTERACTIONS",
    "NOVEL_DRAFTER_MODEL",
    "NOVEL_DRAFTER_TEMPERATURE",
    "NOVEL_DRAFTER_USE_INTERACTIONS",
    "NOVEL_CRITIC_MODEL",
    "NOVEL_CRITIC_TEMPERATURE",
    "NOVEL_CRITIC_USE_INTERACTIONS",
    "NOVEL_POLISHER_MODEL",
    "NOVEL_POLISHER_TEMPERATURE",
    "NOVEL_POLISHER_USE_INTERACTIONS",
    "NOVEL_CHRONICLER_MODEL",
    "NOVEL_CHRONICLER_TEMPERATURE",
    "NOVEL_CHRONICLER_USE_INTERACTIONS",
    "SOURCE_LANG",
    "TARGET_LANG",
    "NOVEL_MAX_TPM",
    "NOVEL_MAX_RPM",
    "NOVEL_MAX_REVIEW_LOOPS",
    "NOVEL_QUALITY_THRESHOLD",
    "NOVEL_PROJECTS_DIR",
    "NOVEL_THINKING_LEVEL",
    "NOVEL_EXTRACTOR_THINKING_LEVEL",
    "NOVEL_DRAFTER_THINKING_LEVEL",
    "NOVEL_CRITIC_THINKING_LEVEL",
    "NOVEL_POLISHER_THINKING_LEVEL",
    "NOVEL_CHRONICLER_THINKING_LEVEL",
    "NOVEL_THINKING_BUDGET",
    "NOVEL_EXTRACTOR_THINKING_BUDGET",
    "NOVEL_DRAFTER_THINKING_BUDGET",
    "NOVEL_CRITIC_THINKING_BUDGET",
    "NOVEL_POLISHER_THINKING_BUDGET",
    "NOVEL_CHRONICLER_THINKING_BUDGET",
    "NOVEL_TEMPERATURE",
    "NOVEL_USE_INTERACTIONS",
    "NOVEL_FILTER_EXTRACTOR_ENTITIES",
    "NOVEL_POST_POLISH_RECONCILIATION",
    "NOVEL_RAG_EMBEDDING_MODEL",
    "NOVEL_RAG_RERANKER_MODEL",
    "NOVEL_SCRAPER_PATH",
    "NOVEL_SCRAPER_PYTHON",
    "CUSTOM_API_BASE_URL",
)
ENV_SECRET_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "CUSTOM_API_KEY",
)


def resolve_env_file() -> Path:
    """Resolve the user-editable environment file for this process."""
    configured_path = os.environ.get("NOUSETSU_ENV_FILE")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return find_repo_root() / ".env"


def _apply_desktop_projects_default() -> None:
    """Use the Tauri-provided projects directory unless the user configured one."""
    default_dir = os.environ.get("NOUSETSU_DEFAULT_PROJECTS_DIR")
    if default_dir:
        os.environ.setdefault("NOVEL_PROJECTS_DIR", default_dir)


def find_repo_root() -> Path:
    """Locate the codebase root directory containing pyproject.toml, .git, or central .env."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").is_file() or (parent / ".git").exists() or (parent / ".env").is_file():
            return parent
    return current


def load_env(
    project_dir: Optional[Union[str, Path]] = None,
    override: bool = False,
) -> Optional[Path]:
    """Load environment variables from central repo .env and optional project-level .env.

    Cascade precedence:
    1. System / process environment variables (preserved when override=False)
    2. Project-level .env (e.g. project/Villainess/.env) if project_dir provided
    3. Central repo .env (e.g. D:/Code/novel_translation_Agent/.env)
    4. CWD .env if running from custom working directory
    """
    loaded_any: Optional[Path] = None

    configured_env = os.environ.get("NOUSETSU_ENV_FILE")
    if configured_env:
        env_path = Path(configured_env).expanduser()
        if env_path.is_file():
            dotenv.load_dotenv(env_path, override=override)
            _apply_desktop_projects_default()
            return env_path
        _apply_desktop_projects_default()
        return None

    # 1. Central repository .env
    repo_root = find_repo_root()
    central_env = repo_root / ".env"
    if central_env.is_file():
        dotenv.load_dotenv(central_env, override=override)
        loaded_any = central_env

    # 2. CWD .env if different from repo root
    cwd_env = Path.cwd() / ".env"
    if cwd_env.is_file() and cwd_env.resolve() != central_env.resolve():
        dotenv.load_dotenv(cwd_env, override=override)
        if not loaded_any:
            loaded_any = cwd_env

    # 3. Project-specific .env override if provided
    if project_dir:
        proj_path = Path(project_dir)
        proj_env = proj_path / ".env"
        if proj_env.is_file():
            dotenv.load_dotenv(proj_env, override=override)
            loaded_any = proj_env

    _apply_desktop_projects_default()
    return loaded_any


def get_env_snapshot() -> Dict[str, str]:
    """Return a non-secret snapshot of supported NouSetsu environment variables."""
    return {
        "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL", ""),
        "NOVEL_MODEL": os.environ.get("NOVEL_MODEL", os.environ.get("DEFAULT_MODEL", "gemini-3.1-flash-lite")),
        "NOVEL_FALLBACK_MODEL": os.environ.get("NOVEL_FALLBACK_MODEL", "gemini-3.5-flash-lite"),
        "NOVEL_EXTRACTOR_MODEL": os.environ.get("NOVEL_EXTRACTOR_MODEL", ""),
        "NOVEL_DRAFTER_MODEL": os.environ.get("NOVEL_DRAFTER_MODEL", ""),
        "NOVEL_CRITIC_MODEL": os.environ.get("NOVEL_CRITIC_MODEL", "gemma-4-26b-a4b-it"),
        "NOVEL_POLISHER_MODEL": os.environ.get("NOVEL_POLISHER_MODEL", ""),
        "NOVEL_CHRONICLER_MODEL": os.environ.get("NOVEL_CHRONICLER_MODEL", "gemma-4-26b-a4b-it"),
        "SOURCE_LANG": os.environ.get("SOURCE_LANG", "auto"),
        "TARGET_LANG": os.environ.get("TARGET_LANG", "English"),
        "NOVEL_MAX_TPM": os.environ.get("NOVEL_MAX_TPM", "32000"),
        "NOVEL_MAX_RPM": os.environ.get("NOVEL_MAX_RPM", "60"),
        "NOVEL_MAX_REVIEW_LOOPS": os.environ.get("NOVEL_MAX_REVIEW_LOOPS", "3"),
        "NOVEL_QUALITY_THRESHOLD": os.environ.get("NOVEL_QUALITY_THRESHOLD", "8.5"),
        "NOVEL_PROJECTS_DIR": os.environ.get("NOVEL_PROJECTS_DIR", "project"),
        "NOVEL_THINKING_LEVEL": os.environ.get("NOVEL_THINKING_LEVEL", ""),
        "NOVEL_CRITIC_THINKING_LEVEL": os.environ.get("NOVEL_CRITIC_THINKING_LEVEL", ""),
        "NOVEL_POLISHER_THINKING_LEVEL": os.environ.get("NOVEL_POLISHER_THINKING_LEVEL", ""),
        **{
            key: os.environ.get(key, "")
            for key in ENV_CONFIG_KEYS
            if key not in {
                "DEFAULT_MODEL", "NOVEL_MODEL", "NOVEL_FALLBACK_MODEL",
                "NOVEL_EXTRACTOR_MODEL", "NOVEL_DRAFTER_MODEL", "NOVEL_CRITIC_MODEL",
                "NOVEL_POLISHER_MODEL", "NOVEL_CHRONICLER_MODEL", "SOURCE_LANG",
                "TARGET_LANG", "NOVEL_MAX_TPM", "NOVEL_MAX_RPM",
                "NOVEL_MAX_REVIEW_LOOPS", "NOVEL_QUALITY_THRESHOLD", "NOVEL_PROJECTS_DIR",
                "NOVEL_THINKING_LEVEL", "NOVEL_CRITIC_THINKING_LEVEL",
                "NOVEL_POLISHER_THINKING_LEVEL",
            }
        },
    }


def get_env_settings() -> Dict[str, object]:
    """Read editable environment settings without exposing any secret values."""
    env_path = resolve_env_file()
    parsed = dotenv.dotenv_values(env_path) if env_path.is_file() else {}
    return {
        "env_file_path": str(env_path),
        "values": {
            key: parsed.get(key) or (os.environ.get(key, "") if key == "NOVEL_PROJECTS_DIR" else "")
            for key in ENV_CONFIG_KEYS
        },
        "api_key_status": {key: bool(parsed.get(key)) for key in ENV_SECRET_KEYS},
    }


def save_env_settings(
    values: Dict[str, object],
    api_keys: Dict[str, object],
    clear_api_keys: list[str],
) -> Dict[str, object]:
    """Persist allowlisted settings and API keys without returning secret material."""
    unknown_values = set(values) - set(ENV_CONFIG_KEYS)
    unknown_keys = set(api_keys) - set(ENV_SECRET_KEYS)
    invalid_clear_keys = set(clear_api_keys) - set(ENV_SECRET_KEYS)
    if unknown_values or unknown_keys or invalid_clear_keys:
        raise ValueError("Unsupported environment setting key.")

    updates: Dict[str, str] = {}
    for key, raw_value in {**values, **api_keys}.items():
        if raw_value is None:
            value = ""
        elif isinstance(raw_value, (str, int, float, bool)):
            value = str(raw_value)
        else:
            raise ValueError(f"Invalid value for {key}.")
        if "\n" in value or "\r" in value or "\0" in value or len(value) > 8192:
            raise ValueError(f"Invalid value for {key}.")
        updates[key] = value

    if any(key in clear_api_keys and updates.get(key) for key in clear_api_keys):
        raise ValueError("A key cannot be replaced and cleared in the same request.")

    env_path = resolve_env_file()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.touch(exist_ok=True)
    if os.name != "nt":
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    for key, value in updates.items():
        if key in ENV_SECRET_KEYS and not value:
            continue
        if value:
            dotenv.set_key(env_path, key, value, quote_mode="always", encoding="utf-8")
        else:
            dotenv.unset_key(env_path, key, encoding="utf-8")

    for key in clear_api_keys:
        dotenv.unset_key(env_path, key, encoding="utf-8")

    if os.name != "nt":
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    for key, value in updates.items():
        if key in ENV_SECRET_KEYS and not value:
            continue
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    for key in clear_api_keys:
        os.environ.pop(key, None)

    return get_env_settings()
