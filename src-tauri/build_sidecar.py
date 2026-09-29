"""Build the self-contained Python backend bundled with Tauri installers."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
FRONTEND_DIST = WEB_DIR / "dist"
ENTRY_POINT = ROOT / "src" / "nousetsu" / "desktop_backend.py"
SCRAPER_ROOT = ROOT / "modules" / "novel_scraper"
SCRAPER_RECIPES = SCRAPER_ROOT / "src" / "recipes"
TAURI_BINARIES = ROOT / "src-tauri" / "binaries"
PYINSTALLER_DIST = ROOT / "src-tauri" / "target" / "backend-dist"
PYINSTALLER_WORK = ROOT / "src-tauri" / "target" / "backend-work"
SCRAPER_HIDDEN_IMPORTS = ("src.api_bridge", "src.config")
SCRAPER_SUBMODULES = (
    "src.agent",
    "src.core",
    "src.handlers",
    "src.scraper",
    "src.utils",
)
COLLECT_ALL = (
    "nousetsu",
    "uvicorn",
    "langchain",
    "langchain_core",
    "langchain_google_genai",
    "langchain_openai",
    "langgraph",
    "playwright",
    "bs4",
    "lxml",
    "aiofiles",
    "google.genai",
    "pykakasi",
    "anyascii",
    "cryptography",
)


def _ensure_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        return

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = project["dependency-groups"]["desktop-build"]
    subprocess.run(
        ["uv", "pip", "install", "--python", sys.executable, *requirements],
        cwd=ROOT,
        check=True,
    )


def _smoke_test_scraper_worker(backend: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="nousetsu-scraper-smoke-") as data_dir:
        environment = os.environ.copy()
        environment["NOUSETSU_APP_DATA_DIR"] = data_dir
        environment["NOUSETSU_ENV_FILE"] = str(Path(data_dir) / "settings.env")
        environment["PYTHON_DOTENV_DISABLED"] = "1"
        for key in (
            "DEFAULT_MODEL",
            "NOVEL_MODEL",
            "NOVEL_SCRAPER_MODEL",
            "NOVEL_FALLBACK_MODEL",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
        ):
            environment.pop(key, None)
        environment["NOVEL_SCRAPER_MODEL"] = "openrouter:smoke-test-model"
        environment["NOVEL_FALLBACK_MODEL"] = "openai:smoke-fallback-model"
        process = subprocess.run(
            [str(backend), "--scraper-worker", "inspect", "--help"],
            cwd=data_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        provider_process = subprocess.run(
            [str(backend), "--scraper-worker", "provider-info"],
            cwd=data_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        romanize_process = subprocess.run(
            [str(backend), "--scraper-worker", "romanize", "悪役貴族"],
            cwd=data_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    if process.returncode != 0:
        raise RuntimeError(
            "Frozen scraper worker failed its import smoke test:\n"
            f"{process.stdout[-4000:]}\n{process.stderr[-4000:]}"
        )
    if "--url" not in process.stdout:
        raise RuntimeError(
            "Frozen scraper worker did not display the inspect command help:\n"
            f"{process.stdout[-4000:]}"
        )
    if provider_process.returncode != 0:
        raise RuntimeError(
            "Frozen scraper worker could not initialize NouSetsu model routing:\n"
            f"{provider_process.stdout[-4000:]}\n{provider_process.stderr[-4000:]}"
        )
    try:
        provider_info = json.loads(provider_process.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Frozen scraper worker returned invalid model-routing diagnostics:\n"
            f"{provider_process.stdout[-4000:]}\n{provider_process.stderr[-4000:]}"
        ) from error
    expected_provider_info = {
        "model": "openrouter:smoke-test-model",
        "provider": "Unconfigured",
        "fallback_model": "openai:smoke-fallback-model",
        "fallback_provider": "Unconfigured",
        "available": False,
    }
    if provider_info != expected_provider_info:
        raise RuntimeError(f"Frozen scraper worker has unexpected model-routing state: {provider_info}")
    if romanize_process.returncode != 0 or not romanize_process.stdout.strip():
        raise RuntimeError(
            "Frozen scraper worker failed its romanizer smoke test:\n"
            f"{romanize_process.stdout[-4000:]}\n{romanize_process.stderr[-4000:]}"
        )


def _smoke_test_backend(backend: Path) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    process = subprocess.Popen(
        [str(backend), "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output, _ = process.communicate()
                raise RuntimeError(
                    f"Frozen backend exited during smoke test ({process.returncode}):\n{output[-4000:]}"
                )
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/sync-state", timeout=1
                ) as response:
                    if response.status == 200:
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/api/scraper/check", timeout=5
                        ) as scraper_response:
                            scraper_info = json.load(scraper_response)
                        if (
                            not scraper_info.get("available")
                            or scraper_info.get("scraper_dir") != "Bundled Novel-Scraper sidecar"
                        ):
                            raise RuntimeError(
                                f"Frozen backend did not detect its bundled scraper: {scraper_info}"
                            )
                        return
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.2)
        process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
        raise TimeoutError(
            f"Frozen backend did not serve its API within 90 seconds:\n{output[-4000:]}"
        )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main() -> None:
    _ensure_pyinstaller()

    if not (FRONTEND_DIST / "index.html").is_file():
        raise FileNotFoundError(f"Build the web frontend before freezing the backend: {FRONTEND_DIST}")
    if not ENTRY_POINT.is_file():
        raise FileNotFoundError(f"Backend entry point is missing: {ENTRY_POINT}")
    scraper_bridge = SCRAPER_ROOT / "src" / "api_bridge.py"
    if not scraper_bridge.is_file():
        raise FileNotFoundError(
            f"Novel-Scraper API bridge is missing: {scraper_bridge}. "
            "Initialize the scraper submodule with git submodule update --init --recursive."
        )
    if not SCRAPER_RECIPES.is_dir():
        raise FileNotFoundError(f"Novel-Scraper recipe directory is missing: {SCRAPER_RECIPES}")

    TAURI_BINARIES.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_DIST.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_WORK.mkdir(parents=True, exist_ok=True)

    extension = ".exe" if os.name == "nt" else ""
    packaged_backend_dir = TAURI_BINARIES / "nousetsu-backend"
    for stale_binary in TAURI_BINARIES.glob("nousetsu-backend*"):
        if stale_binary.is_dir():
            shutil.rmtree(stale_binary)
        else:
            stale_binary.unlink()

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "nousetsu-backend",
        "--distpath",
        str(PYINSTALLER_DIST),
        "--workpath",
        str(PYINSTALLER_WORK),
        "--specpath",
        str(PYINSTALLER_WORK),
        "--paths",
        str(ROOT / "src"),
        "--paths",
        str(SCRAPER_ROOT),
        "--add-data",
        f"{FRONTEND_DIST}{os.pathsep}web/dist",
        "--add-data",
        f"{SCRAPER_RECIPES}{os.pathsep}scraper-data/recipes",
    ]
    for module in SCRAPER_HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module])
    for package in SCRAPER_SUBMODULES:
        command.extend(["--collect-submodules", package])
    for package in COLLECT_ALL:
        command.extend(["--collect-all", package])
    command.append(str(ENTRY_POINT))

    subprocess.run(command, cwd=ROOT, check=True)
    built_backend_dir = PYINSTALLER_DIST / "nousetsu-backend"
    built_backend = built_backend_dir / f"nousetsu-backend{extension}"
    if not built_backend.is_file():
        raise FileNotFoundError(f"PyInstaller did not produce {built_backend}")
    shutil.copytree(built_backend_dir, packaged_backend_dir)

    packaged_executable = packaged_backend_dir / f"nousetsu-backend{extension}"
    _smoke_test_scraper_worker(packaged_executable)
    _smoke_test_backend(packaged_executable)
    print(f"Built and smoke-tested Tauri backend sidecar: {packaged_executable}")


if __name__ == "__main__":
    main()
