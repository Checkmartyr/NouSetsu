"""
Unit tests for the Novel-Scraper detector, models, bridge, and FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from nousetsu.cli.web_server import create_app
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
        author="Test Author",
        description="A great adventure.",
        total_chapters=2,
        chapters=chapters,
    )
    dumped = inspect_res.model_dump()
    assert dumped["total_chapters"] == 2
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
