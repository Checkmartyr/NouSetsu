"""
Unit tests for the Novel-Scraper detector, models, bridge, and FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from nousetsu.cli.web_server import create_app
import nousetsu.scraper.detector as scraper_detector
from nousetsu.scraper import (
    NovelScraperBridge,
    ScraperChapterItem,
    ScraperExtractRequest,
    ScraperInspectRequest,
    ScraperInspectResponse,
    ScraperStatusResponse,
    find_scraper_directory,
    find_scraper_python,
    get_scraper_info,
)


def test_frozen_scraper_detector_ignores_external_checkout(tmp_path, monkeypatch):
    backend = tmp_path / "nousetsu-backend.exe"
    backend.touch()
    external_scraper = tmp_path / "external-scraper"
    external_scraper.mkdir()
    external_python = tmp_path / "external-python.exe"
    external_python.touch()
    monkeypatch.setenv("NOVEL_SCRAPER_PATH", str(external_scraper))
    monkeypatch.setenv("NOVEL_SCRAPER_PYTHON", str(external_python))
    monkeypatch.setattr(scraper_detector.sys, "frozen", True, raising=False)
    monkeypatch.setattr(scraper_detector.sys, "executable", str(backend))

    available, scraper_dir, python_exe = get_scraper_info()

    assert available is True
    assert scraper_dir == "Bundled Novel-Scraper sidecar"
    assert python_exe == str(backend.resolve())
    assert find_scraper_directory() == tmp_path
    assert find_scraper_python() == backend.resolve()


def test_scraper_detector_and_submodule():
    """Verify that scraper detector finds the git submodule and python executable."""
    available, s_dir, py_exe = get_scraper_info()
    assert available is True
    assert s_dir is not None
    assert "novel_scraper" in s_dir
    assert py_exe is not None
    assert "python" in py_exe.lower()

    bridge = NovelScraperBridge()
    assert bridge.is_available() is True


@pytest.mark.asyncio
async def test_packaged_scraper_bridge_uses_sidecar_worker(tmp_path, monkeypatch):
    backend = tmp_path / "nousetsu-backend.exe"
    backend.touch()
    external_scraper = tmp_path / "external-scraper"
    (external_scraper / "src").mkdir(parents=True)
    (external_scraper / "src" / "api_bridge.py").touch()
    external_python = tmp_path / "external-python.exe"
    external_python.touch()
    app_data = tmp_path / "app-data"
    app_data.mkdir()
    monkeypatch.setenv("NOVEL_SCRAPER_PATH", str(external_scraper))
    monkeypatch.setenv("NOVEL_SCRAPER_PYTHON", str(external_python))
    monkeypatch.setenv("NOUSETSU_APP_DATA_DIR", str(app_data))
    monkeypatch.setattr(scraper_detector.sys, "frozen", True, raising=False)
    monkeypatch.setattr(scraper_detector.sys, "executable", str(backend))
    captured = []

    class FakeProcess:
        returncode = 0

        def __init__(self, command):
            self.command = command

        async def communicate(self):
            if "romanize" in self.command:
                return b"Test Novel", b""
            return b'{"success":true,"novel_title":"Test Novel","chapters":[]}', b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured.append((args, kwargs["cwd"]))
        return FakeProcess(args)

    monkeypatch.setattr(
        "nousetsu.scraper.bridge.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    bridge = NovelScraperBridge()
    result = await bridge.inspect_url("https://example.com/novel/")

    assert result.success is True
    assert bridge.is_available() is True
    assert captured[0] == (
        (
            str(backend.resolve()),
            "--scraper-worker",
            "inspect",
            "--url",
            "https://example.com/novel/",
        ),
        str(app_data.resolve()),
    )
    assert captured[1] == (
        (str(backend.resolve()), "--scraper-worker", "romanize", "Test Novel"),
        str(app_data.resolve()),
    )


@pytest.mark.asyncio
async def test_scraper_bridge_uses_bundled_adapter_for_older_checkout(tmp_path, monkeypatch):
    scraper_dir = tmp_path / "legacy_scraper"
    (scraper_dir / "src").mkdir(parents=True)
    (scraper_dir / "src" / "main.py").touch()
    python_exe = tmp_path / "python.exe"
    python_exe.touch()
    bundled_adapter = tmp_path / "bundled" / "api_bridge.py"
    bridge = NovelScraperBridge(scraper_dir=scraper_dir, python_exe=python_exe)
    monkeypatch.setattr(bridge, "_bundled_api_bridge_path", lambda: bundled_adapter)
    captured = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return (
                b'{"success":true,"novel_title":"Test Novel","chapters":[]}',
                b"",
            )

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["cwd"] = kwargs["cwd"]
        return FakeProcess()

    async def fake_romanize_title(title):
        return title

    monkeypatch.setattr(
        "nousetsu.scraper.bridge.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(bridge, "romanize_title", fake_romanize_title)

    url = "https://example.com/novel/"
    result = await bridge.inspect_url(url)

    assert result.success is True
    assert result.novel_title == "Test Novel"
    assert captured["args"][:2] == (str(python_exe), "-c")
    assert "runpy.run_path" in captured["args"][2]
    assert captured["args"][3:] == (
        str(scraper_dir),
        str(bundled_adapter),
        "inspect",
        "--url",
        url,
    )
    assert captured["cwd"] == str(scraper_dir)


@pytest.mark.asyncio
async def test_scraper_bridge_romanizes_title_with_submodule(tmp_path, monkeypatch):
    scraper_dir = tmp_path / "novel_scraper"
    scraper_dir.mkdir()
    python_exe = tmp_path / "python.exe"
    python_exe.touch()
    bridge = NovelScraperBridge(scraper_dir=scraper_dir, python_exe=python_exe)
    captured = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"Akuyaku Kizoku", b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["cwd"] = kwargs["cwd"]
        return FakeProcess()

    monkeypatch.setattr(
        "nousetsu.scraper.bridge.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    romanized = await bridge.romanize_title("悪役貴族")

    assert romanized == "Akuyaku Kizoku"
    assert captured["args"][0] == str(python_exe)
    assert captured["args"][-1] == "悪役貴族"
    assert captured["cwd"] == str(scraper_dir)


def test_scraper_models_serialization():
    """Test validation and serialization of scraper request and response schemas."""
    # Test Inspect Request & Response
    inspect_req = ScraperInspectRequest(url="https://ncode.syosetu.com/n2273dh/")
    assert inspect_req.url == "https://ncode.syosetu.com/n2273dh/"

    chapters = [
        ScraperChapterItem(index=1, title="Chapter 1: The Beginning", url="https://example.com/1"),
        ScraperChapterItem(index=2, title="Chapter 2: The Next Step", url="https://example.com/2"),
    ]
    inspect_res = ScraperInspectResponse(
        success=True,
        url=inspect_req.url,
        novel_title="Test Slime Isekai",
        romanized_title="Test Slime Isekai",
        author="Test Author",
        description="A great adventure.",
        total_chapters=2,
        chapters=chapters,
    )
    dumped = inspect_res.model_dump()
    assert dumped["total_chapters"] == 2
    assert dumped["romanized_title"] == "Test Slime Isekai"
    assert dumped["chapters"][0]["title"] == "Chapter 1: The Beginning"

    # Test Extract Request
    extract_req = ScraperExtractRequest(
        url="https://ncode.syosetu.com/n2273dh/",
        start_chapter=1,
        end_chapter=5,
        concurrency=4,
    )
    assert extract_req.concurrency == 4
    assert extract_req.start_chapter == 1
    assert extract_req.end_chapter == 5

    # Test Status Response
    status = ScraperStatusResponse(
        task_id="abc12345",
        status="running",
        progress_percent=50.0,
        current_chapter=1,
        total_chapters=2,
        message="Scraping chapter 1",
    )
    assert status.task_id == "abc12345"
    assert status.progress_percent == 50.0


def test_scraper_check_api_endpoint():
    """Test the /api/scraper/check endpoint in FastAPI app."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/scraper/check")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert "novel_scraper" in data["scraper_dir"]
    assert "python" in data["python_exe"].lower()


def test_scraper_status_not_found():
    """Test 404 behavior for non-existent scraper task."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/scraper/status/non-existent-task-id")
    assert response.status_code == 404
