"""Build the self-contained Python backend bundled with Tauri installers."""

from __future__ import annotations

import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
FRONTEND_DIST = WEB_DIR / "dist"
ENTRY_POINT = ROOT / "src" / "nousetsu" / "desktop_backend.py"
TAURI_BINARIES = ROOT / "src-tauri" / "binaries"
PYINSTALLER_DIST = ROOT / "src-tauri" / "target" / "backend-dist"
PYINSTALLER_WORK = ROOT / "src-tauri" / "target" / "backend-work"
COLLECT_ALL = (
    "nousetsu",
    "uvicorn",
    "langchain",
    "langchain_core",
    "langchain_google_genai",
    "langchain_openai",
    "langgraph",
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
        "--add-data",
        f"{FRONTEND_DIST}{os.pathsep}web/dist",
    ]
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
    _smoke_test_backend(packaged_executable)
    print(f"Built and smoke-tested Tauri backend sidecar: {packaged_executable}")


if __name__ == "__main__":
    main()
