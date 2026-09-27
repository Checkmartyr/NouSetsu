"""
Detection and environment resolution for Novel-Scraper integration.
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple


def get_repo_root() -> Path:
    """Return root directory of the NouSetsu project."""
    # This file is src/nousetsu/scraper/detector.py -> 3 levels up from src is repo root
    return Path(__file__).resolve().parent.parent.parent.parent


def find_scraper_directory() -> Optional[Path]:
    """
    Locate Novel-Scraper directory using 4-tier resolution hierarchy:
    1. Git submodule in `modules/novel_scraper`
    2. Environment variable `NOVEL_SCRAPER_PATH`
    3. Sibling repositories (`../Novel_scraping_agent`, `../-Novel-Scraper`)
    """
    repo_root = get_repo_root()

    # Tier 1: Git Submodule
    submodule_path = repo_root / "modules" / "novel_scraper"
    if submodule_path.is_dir() and (submodule_path / "src" / "agent").is_dir():
        return submodule_path

    # Tier 2: Explicit environment variable
    env_path = os.environ.get("NOVEL_SCRAPER_PATH")
    if env_path:
        p = Path(env_path).resolve()
        if p.is_dir() and (p / "src" / "agent").is_dir():
            return p

    # Tier 3: Sibling directories
    sibling_candidates = [
        repo_root.parent / "Novel_scraping_agent",
        repo_root.parent / "-Novel-Scraper",
        Path("D:/Code/Novel_scraping_agent"),
    ]
    for cand in sibling_candidates:
        if cand.is_dir() and (cand / "src" / "agent").is_dir():
            return cand.resolve()

    return None


def find_scraper_python(scraper_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Locate the Python executable suited for running Novel-Scraper:
    1. Environment variable `NOVEL_SCRAPER_PYTHON`
    2. `.venv` inside `scraper_dir`
    3. Current running Python interpreter (`sys.executable`)
    """
    # 1. Explicit environment variable
    env_py = os.environ.get("NOVEL_SCRAPER_PYTHON")
    if env_py:
        p = Path(env_py).resolve()
        if p.is_file():
            return p

    target_dir = scraper_dir or find_scraper_directory()
    if target_dir:
        # Check standard venv locations
        if sys.platform == "win32":
            venv_candidates = [
                target_dir / ".venv" / "Scripts" / "python.exe",
                target_dir / "venv" / "Scripts" / "python.exe",
            ]
        else:
            venv_candidates = [
                target_dir / ".venv" / "bin" / "python",
                target_dir / "venv" / "bin" / "python",
            ]

        for cand in venv_candidates:
            if cand.is_file():
                return cand.resolve()

    # Fallback to sys.executable
    return Path(sys.executable).resolve()


def get_scraper_info() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if Novel-Scraper is available and configured.
    Returns (is_available, scraper_dir_path, python_path).
    """
    s_dir = find_scraper_directory()
    if not s_dir:
        return (False, None, None)

    py_exe = find_scraper_python(s_dir)
    if not py_exe or not py_exe.is_file():
        return (False, str(s_dir), None)

    # Check for bridge module or entrypoint
    has_bridge = (s_dir / "src" / "api_bridge.py").is_file() or (s_dir / "src" / "main.py").is_file()
    return (has_bridge, str(s_dir), str(py_exe))
