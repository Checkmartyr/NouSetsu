"""Central environment discovery and dotenv cascade management."""
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Union
import dotenv

logger = logging.getLogger(__name__)


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

    return loaded_any


def get_env_snapshot() -> Dict[str, str]:
    """Return a dictionary snapshot of key NouSetsu environment variables."""
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
    }
