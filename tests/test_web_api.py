"""Unit tests for FastAPI Web Dashboard endpoints and SSE event streaming."""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from nousetsu.cli.web_server import create_app, event_bus, active_job
from nousetsu.storage.repository import NovelRepository


@pytest.fixture
def web_test_repo(tmp_path: Path) -> NovelRepository:
    """Creates an isolated mock novel project for API testing."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project(
        title="Web Test Novel",
        source_lang="Japanese",
        target_lang="English",
        raw_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model",
        genre="general",
    )

    # Add dummy chapter 1
    raw_dir = tmp_path / "raw_chapters"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ch1 = raw_dir / "0001.txt"
    ch1.write_text("第1章 はじめに。\n彼女は微笑んだ。", encoding="utf-8")

    out_dir = tmp_path / "translated_chapters"
    out_dir.mkdir(parents=True, exist_ok=True)
    trans1 = out_dir / "0001.md"
    trans1.write_text("# Chapter 1: Prologue\n\nShe smiled gently.", encoding="utf-8")

    return repo


@pytest.fixture
def client(web_test_repo: NovelRepository) -> TestClient:
    app = create_app()
    return TestClient(app)


def test_active_project_and_sync_state(client: TestClient, web_test_repo: NovelRepository):
    # GET /api/active-project
    res = client.get("/api/active-project")
    assert res.status_code == 200
    data = res.json()
    assert "active_project" in data
    assert "projects" in data

    # GET /api/sync-state
    res_sync = client.get("/api/sync-state")
    assert res_sync.status_code == 200
    sync_data = res_sync.json()
    assert "active_project_path" in sync_data


def test_chapters_and_content_endpoints(client: TestClient, web_test_repo: NovelRepository):
    proj_param = str(web_test_repo.root_dir)

    # GET /api/chapters
    res = client.get(f"/api/chapters?project_path={proj_param}")
    assert res.status_code == 200
    chapters = res.json()
    assert len(chapters) == 1
    assert chapters[0]["chapter_num"] == 1
    assert chapters[0]["raw_exists"] is True
    assert chapters[0]["translated_exists"] is True

    # GET /api/chapters/1/content
    res_content = client.get(f"/api/chapters/1/content?project_path={proj_param}")
    assert res_content.status_code == 200
    content = res_content.json()
    assert content["chapter_num"] == 1
    assert "はじめに" in content["source_text"]
    assert "Chapter 1: Prologue" in content["translated_text"]


def test_bible_endpoints(client: TestClient, web_test_repo: NovelRepository):
    proj_param = str(web_test_repo.root_dir)

    # GET /api/bible
    res = client.get(f"/api/bible?project_path={proj_param}")
    assert res.status_code == 200
    bible = res.json()
    assert bible["title"] == "Web Test Novel"

    # PUT /api/bible
    bible["genre"] = "isekai"
    bible["characters"].append({
        "name": "Clara",
        "original_name": "クララ",
        "gender": "female",
        "role": "protagonist",
        "voice": "calm",
        "relationships": {},
    })
    res_put = client.put(f"/api/bible?project_path={proj_param}", json=bible)
    assert res_put.status_code == 200
    assert res_put.json()["success"] is True

    # Verify updated
    res_check = client.get(f"/api/bible?project_path={proj_param}")
    assert res_check.json()["genre"] == "isekai"
    assert len(res_check.json()["characters"]) == 1

    # GET /api/bible/raw
    res_raw = client.get(f"/api/bible/raw?project_path={proj_param}")
    assert res_raw.status_code == 200
    assert "Clara" in res_raw.json()["raw"]


def test_settings_endpoints(client: TestClient, web_test_repo: NovelRepository):
    proj_param = str(web_test_repo.root_dir)

    # GET /api/settings
    res = client.get(f"/api/settings?project_path={proj_param}")
    assert res.status_code == 200
    data = res.json()
    assert "config" in data
    assert "env" in data

    # PUT /api/settings
    cfg = data["config"]
    cfg["max_review_loops"] = 4
    res_put = client.put(f"/api/settings?project_path={proj_param}", json=cfg)
    assert res_put.status_code == 200
    assert res_put.json()["success"] is True


def test_translation_controls(client: TestClient, web_test_repo: NovelRepository):
    proj_param = str(web_test_repo.root_dir)

    # Check status
    res_status = client.get("/api/translate/status")
    assert res_status.status_code == 200
    assert res_status.json()["is_running"] is False

    # Start translation with mock model
    res_start = client.post("/api/translate/start", json={
        "project_path": proj_param,
        "chapter": 1,
        "force": True,
        "model": "mock-model",
    })
    assert res_start.status_code == 200
    assert res_start.json()["success"] is True

    # Stop translation
    res_stop = client.post("/api/translate/stop")
    assert res_stop.status_code == 200
