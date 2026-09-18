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

    # 1. GET /api/settings
    res = client.get(f"/api/settings?project_path={proj_param}")
    assert res.status_code == 200
    data = res.json()
    assert "config" in data
    assert "env" in data
    assert data["title"] == "Web Test Novel"

    # 2. PUT /api/settings with top-level fields (like UI sends)
    payload = {
        "title": "Renamed Test Novel",
        "genre": "isekai",
        "source_language": "Japanese",
        "target_language": "English",
        "model_name": "test-gemini-pro",
        "fallback_model": "test-gemini-flash",
        "max_review_loops": 4,
        "quality_threshold": 9.2,
        "chunk_threshold_lines": 100,
        "chunk_size_lines": 80,
        "chunk_overlap_lines": 5,
    }
    res_put = client.put(f"/api/settings?project_path={proj_param}", json=payload)
    assert res_put.status_code == 200
    assert res_put.json()["success"] is True

    # 3. Verify disk config.yaml is updated
    cfg_disk = web_test_repo.load_config()
    assert cfg_disk.title == "Renamed Test Novel"
    assert cfg_disk.genre == "isekai"
    assert cfg_disk.source_language == "Japanese"
    assert cfg_disk.target_language == "English"
    assert cfg_disk.model_name == "test-gemini-pro"
    assert cfg_disk.fallback_model == "test-gemini-flash"
    assert cfg_disk.max_review_loops == 4
    assert cfg_disk.quality_threshold == 9.2
    assert cfg_disk.chunk_threshold_lines == 100
    assert cfg_disk.target_chunk_lines == 80
    assert cfg_disk.chunk_overlap_lines == 5

    # 4. Verify bible.yaml is synced
    bible_disk = web_test_repo.load_bible()
    assert bible_disk.title == "Renamed Test Novel"
    assert bible_disk.genre == "isekai"
    assert bible_disk.source_language == "Japanese"
    assert bible_disk.target_language == "English"

    # 5. Verify subsequent GET /api/settings returns new values
    res_get2 = client.get(f"/api/settings?project_path={proj_param}")
    assert res_get2.status_code == 200
    data2 = res_get2.json()
    assert data2["title"] == "Renamed Test Novel"
    assert data2["genre"] == "isekai"
    assert data2["model_name"] == "test-gemini-pro"
    assert data2["max_review_loops"] == 4

    # 6. Verify payload with nested config (backward compatibility)
    res_put2 = client.put(f"/api/settings?project_path={proj_param}", json={"config": {"max_review_loops": 2}})
    assert res_put2.status_code == 200
    assert web_test_repo.load_config().max_review_loops == 2


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


def test_folders_and_upload_endpoints(client: TestClient, web_test_repo: NovelRepository):
    proj_param = str(web_test_repo.root_dir)

    # 1. GET /api/folders
    res_folders = client.get(f"/api/folders?project_path={proj_param}")
    assert res_folders.status_code == 200
    folders_data = res_folders.json()
    assert folders_data["default_folder"] == "raw_chapters"
    assert "raw_chapters" in folders_data["folders"]

    # 2. POST /api/chapters/upload (JSON) to default raw_chapters
    res_up = client.post("/api/chapters/upload", json={
        "project_path": proj_param,
        "files": [
            {"name": "0002.txt", "content": "第2章 冒険の始まり。\n剣を抜いた。"},
            {"name": "0003.txt", "content": "第3章 静かな森。\n風が吹いた。"},
        ],
        "overwrite": False,
    })
    assert res_up.status_code == 200
    up_data = res_up.json()
    assert up_data["success"] is True
    assert up_data["total_uploaded"] == 2
    assert "0002.txt" in up_data["uploaded"]
    assert "0003.txt" in up_data["uploaded"]

    # Verify files exist on disk in raw_chapters
    raw_dir = web_test_repo.root_dir / "raw_chapters"
    assert (raw_dir / "0002.txt").exists()
    assert "冒険の始まり" in (raw_dir / "0002.txt").read_text(encoding="utf-8")

    # Verify duplicate upload with overwrite=False skips existing files
    res_skip = client.post("/api/chapters/upload", json={
        "project_path": proj_param,
        "files": [
            {"name": "0002.txt", "content": "Changed content"},
            {"name": "0004.txt", "content": "第4章 新たな仲間。"},
        ],
        "overwrite": False,
    })
    assert res_skip.status_code == 200
    skip_data = res_skip.json()
    assert skip_data["total_uploaded"] == 1
    assert skip_data["total_skipped"] == 1
    assert "0002.txt" in skip_data["skipped"]
    assert "0004.txt" in skip_data["uploaded"]
    # Check 0002.txt wasn't overwritten
    assert "冒険の始まり" in (raw_dir / "0002.txt").read_text(encoding="utf-8")

    # Verify duplicate upload with overwrite=True updates files
    res_ov = client.post("/api/chapters/upload", json={
        "project_path": proj_param,
        "files": [
            {"name": "0002.txt", "content": "Updated content: 冒険第2章。"},
        ],
        "overwrite": True,
    })
    assert res_ov.status_code == 200
    ov_data = res_ov.json()
    assert ov_data["total_uploaded"] == 1
    assert "Updated content" in (raw_dir / "0002.txt").read_text(encoding="utf-8")

    # 3. POST /api/chapters/upload (JSON) to subfolder (e.g. Villainess_05)
    res_vol = client.post("/api/chapters/upload", json={
        "project_path": proj_param,
        "folder": "Villainess_05",
        "files": [
            {"name": "0121.txt", "content": "第121章 舞踏会の夜。\n悪役令嬢は微笑んだ。"},
        ],
        "overwrite": False,
    })
    assert res_vol.status_code == 200
    vol_data = res_vol.json()
    assert vol_data["folder"] == "Villainess_05"
    assert vol_data["total_uploaded"] == 1
    vol_file = web_test_repo.root_dir / "Villainess_05" / "0121.txt"
    assert vol_file.exists()
    assert "悪役令嬢" in vol_file.read_text(encoding="utf-8")

    # Verify GET /api/folders now includes Villainess_05
    res_folders_after = client.get(f"/api/folders?project_path={proj_param}")
    assert "Villainess_05" in res_folders_after.json()["folders"]

    # 4. POST /api/chapters/upload-form (multipart)
    res_form = client.post(
        "/api/chapters/upload-form",
        data={"project_path": proj_param, "folder": "raw_chapters", "overwrite": "true"},
        files={"files": ("0005.txt", b"Chapter 5 via multipart form", "text/plain")},
    )
    assert res_form.status_code == 200
    form_data = res_form.json()
    assert form_data["total_uploaded"] == 1
    assert (raw_dir / "0005.txt").exists()

    # 5. Security test: Directory traversal attempt rejected
    res_bad = client.post("/api/chapters/upload", json={
        "project_path": proj_param,
        "folder": "../../secret_dir",
        "files": [{"name": "evil.txt", "content": "hack"}],
    })
    assert res_bad.status_code == 400

