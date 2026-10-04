"""Central logging configuration and persistent file logger for NouSetsu backend and frontend."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

_BACKEND_LOG_INITIALIZED = False
_FRONTEND_LOGGER: Optional[logging.Logger] = None
_FRONTEND_LOCK = threading.Lock()

MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


def get_logs_dir() -> Path:
    """Resolve the directory where application log files are stored.

    Resolution precedence:
    1. NOUSETSU_LOGS_DIR environment variable
    2. NOUSETSU_INSTALL_DIR/logs (if running under desktop install)
    3. NOUSETSU_DEFAULT_PROJECTS_DIR parent / logs
    4. PyInstaller frozen binary install root / logs
    5. Repository root / logs (in development)
    """
    env_logs = os.environ.get("NOUSETSU_LOGS_DIR")
    if env_logs:
        p = Path(env_logs).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    install_dir = os.environ.get("NOUSETSU_INSTALL_DIR")
    if install_dir:
        p = (Path(install_dir) / "logs").resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass

    default_projects = os.environ.get("NOUSETSU_DEFAULT_PROJECTS_DIR")
    if default_projects:
        p = (Path(default_projects).resolve().parent / "logs").resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass

    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        # In sidecar layout: <install>/binaries/nousetsu-backend/nousetsu-backend.exe
        if exe.parent.name == "nousetsu-backend" and exe.parent.parent.name == "binaries":
            base = exe.parent.parent.parent
        elif exe.parent.name == "binaries":
            base = exe.parent.parent
        else:
            base = exe.parent
        p = (base / "logs").resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass

    # Source dev fallback: repo root / logs
    from nousetsu.storage.repository import get_codebase_root
    p = (get_codebase_root() / "logs").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def setup_backend_file_logging(
    logs_dir: Optional[Path] = None,
    log_level: int = logging.INFO,
) -> Path:
    """Initialize rotating file logging for the Python backend into backend.log."""
    global _BACKEND_LOG_INITIALIZED
    target_dir = (logs_dir or get_logs_dir()).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "backend.log"

    root_logger = logging.getLogger()
    if not any(
        isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == str(log_file.resolve())
        for h in root_logger.handlers
    ):
        try:
            file_handler = RotatingFileHandler(
                filename=log_file,
                maxBytes=MAX_LOG_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
                delay=False,
            )
            formatter = logging.Formatter(
                fmt="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)

            # Ensure root logger level captures at least log_level
            if root_logger.level > log_level or root_logger.level == logging.NOTSET:
                root_logger.setLevel(log_level)

            _BACKEND_LOG_INITIALIZED = True
            logger.info("Initialized backend file logging: %s", log_file)
        except Exception as e:
            logger.warning("Could not setup backend file logging at %s: %s", log_file, e)

    # Install uncaught exception handler to capture fatal Python errors
    _install_excepthook(log_file)
    return target_dir


def _install_excepthook(log_file: Path) -> None:
    original_hook = sys.excepthook

    def custom_excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            original_hook(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("fatal").critical(
            "Uncaught Python exception:\n",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        original_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = custom_excepthook


def _get_frontend_logger(logs_dir: Path) -> logging.Logger:
    global _FRONTEND_LOGGER
    with _FRONTEND_LOCK:
        target_dir = logs_dir.resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        frontend_log_path = target_dir / "frontend.log"

        fl = logging.getLogger("nousetsu.frontend")
        fl.setLevel(logging.INFO)
        fl.propagate = False

        # Check if already configured with this exact log file
        for h in list(fl.handlers):
            if isinstance(h, RotatingFileHandler):
                if getattr(h, "baseFilename", None) == str(frontend_log_path):
                    return fl
                # Old handler for a different logs directory
                fl.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    pass

        try:
            handler = RotatingFileHandler(
                filename=frontend_log_path,
                maxBytes=MAX_LOG_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
                delay=False,
            )
            formatter = logging.Formatter(
                fmt="%(message)s",
            )
            handler.setFormatter(formatter)
            fl.addHandler(handler)
        except Exception as e:
            logger.warning("Could not initialize frontend log file at %s: %s", frontend_log_path, e)

        _FRONTEND_LOGGER = fl
        return fl


def append_frontend_log(
    entry: Dict[str, Any],
    logs_dir: Optional[Path] = None,
) -> None:
    """Write a formatted frontend log entry to frontend.log."""
    target_dir = logs_dir or get_logs_dir()
    fl = _get_frontend_logger(target_dir)

    ts = entry.get("timestamp") or ""
    level = str(entry.get("level", "INFO")).upper()
    source = entry.get("source") or "ui"
    message = str(entry.get("message") or "").strip()
    stack = entry.get("stack")

    formatted = f"[{ts}] [{level}] [{source}] {message}"
    if stack:
        formatted += f"\n  Stack: {stack.strip()}"

    fl.info(formatted)


def get_logs_info(logs_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Return summary information and status of all log files."""
    target_dir = logs_dir or get_logs_dir()
    files_info = {}

    for name in ("backend.log", "frontend.log", "desktop.log"):
        p = target_dir / name
        if p.exists() and p.is_file():
            try:
                size_bytes = p.stat().st_size
                mtime = p.stat().st_mtime
                files_info[name] = {
                    "exists": True,
                    "path": str(p),
                    "size_bytes": size_bytes,
                    "size_display": _format_size(size_bytes),
                    "modified_time": mtime,
                }
            except Exception:
                files_info[name] = {"exists": True, "path": str(p), "size_bytes": 0, "size_display": "0 B"}
        else:
            files_info[name] = {
                "exists": False,
                "path": str(p),
                "size_bytes": 0,
                "size_display": "0 B",
            }

    return {
        "logs_dir": str(target_dir),
        "files": files_info,
    }


def open_logs_folder(logs_dir: Optional[Path] = None) -> bool:
    """Open the logs directory in the operating system's native file explorer."""
    target_dir = (logs_dir or get_logs_dir()).resolve()
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)

    try:
        if sys.platform == "win32":
            os.startfile(str(target_dir))
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target_dir)])
            return True
        else:
            subprocess.Popen(["xdg-open", str(target_dir)])
            return True
    except Exception as e:
        logger.warning("Failed to open logs folder %s: %s", target_dir, e)
        return False


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
