"""Unit and integration tests for NOVEL_PROJECTS_DIR configuration and project management."""
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from nousetsu.storage.repository import (
    NovelRepository,
    ProjectRegistry,
    get_projects_root_dir,
    get_new_project_dir,
    resolve_project_dir,
)
from nousetsu.cli.web_server import create_app


def test_get_projects_root_dir_custom_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifies get_projects_root_dir respects NOVEL_PROJECTS_DIR."""
    custom_dir = tmp_path / "custom_novels"
    monkeypatch.setenv("NOVEL_PROJECTS_DIR", str(custom_dir))
    # Unset NOVEL_REGISTRY_DIR so it doesn't take test override branch
    monkeypatch.delenv("NOVEL_REGISTRY_DIR", raising=False)

    root = get_projects_root_dir()
    assert root == custom_dir.resolve()


def test_get_projects_root_dir_test_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifies get_projects_root_dir isolates inside NOVEL_REGISTRY_DIR during tests."""
    reg_dir = tmp_path / "reg"
    monkeypatch.setenv("NOVEL_REGISTRY_DIR", str(reg_dir))

    root = get_projects_root_dir()
    assert root == (reg_dir / "projects").resolve()


def test_get_new_project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifies get_new_project_dir handles sanitization and explicit folder names."""
    monkeypatch.setenv("NOVEL_REGISTRY_DIR", str(tmp_path / "reg"))
    projects_root = get_projects_root_dir()

    # Sanitization of invalid characters
    path1 = get_new_project_dir("Re:Zero / Starting Life? *Special*")
    assert path1.parent == projects_root
    assert path1.name == "Re_Zero _ Starting Life_ _Special_"

    # Explicit folder name override
    path2 = get_new_project_dir("My Novel", folder_name="my_custom_folder")
    assert path2 == projects_root / "my_custom_folder"


def test_resolve_project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifies resolve_project_dir handles direct paths, short names, and creation."""
    reg_dir = tmp_path / "reg"
    monkeypatch.setenv("NOVEL_REGISTRY_DIR", str(reg_dir))
    projects_root = get_projects_root_dir()
    projects_root.mkdir(parents=True, exist_ok=True)

    # 1. Create an existing project inside projects_root
    p1_dir = projects_root / "Villainess"
    repo1 = NovelRepository(p1_dir)
    repo1.initialize_project(title="Villainess LV99")

    # Resolve by short name
    resolved_short = resolve_project_dir("Villainess")
    assert resolved_short == p1_dir.resolve()

    # Resolve by direct path
    resolved_direct = resolve_project_dir(str(p1_dir))
    assert resolved_direct == p1_dir.resolve()

    # Resolve for creation
    creation_path = resolve_project_dir(None, for_creation=True, title="New Adventure")
    assert creation_path.parent == projects_root
    assert creation_path.name == "New Adventure"

    # Resolve fallback to last active project
    reg = ProjectRegistry(storage_dir=reg_dir)
    reg.set_last_active_project(p1_dir)
    assert resolve_project_dir(None) == p1_dir.resolve()


def test_project_registry_autodiscovery_in_projects_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifies ProjectRegistry.list_projects() auto-discovers projects in projects_root."""
    reg_dir = tmp_path / "reg"
    monkeypatch.setenv("NOVEL_REGISTRY_DIR", str(reg_dir))
    projects_root = get_projects_root_dir()

    # Create two projects inside projects_root
    p1 = projects_root / "ProjectAlpha"
    NovelRepository(p1).initialize_project(title="Alpha Series", source_lang="Japanese", target_lang="English")

    p2 = projects_root / "ProjectBeta"
    NovelRepository(p2).initialize_project(title="Beta Chronicle", source_lang="Chinese", target_lang="English")

    reg = ProjectRegistry(storage_dir=reg_dir)
    projects = reg.list_projects()
    titles = [p["title"] for p in projects]

    assert "Alpha Series" in titles
    assert "Beta Chronicle" in titles


def test_web_api_projects_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Tests GET /api/projects and POST /api/projects/create."""
    reg_dir = tmp_path / "reg"
    monkeypatch.setenv("NOVEL_REGISTRY_DIR", str(reg_dir))
    projects_root = get_projects_root_dir()

    # Initialize initial active project
    init_dir = projects_root / "InitialProj"
    repo = NovelRepository(init_dir)
    repo.initialize_project(title="Initial Project")
    reg = ProjectRegistry(storage_dir=reg_dir)
    reg.set_last_active_project(init_dir)

    app = create_app()
    client = TestClient(app)

    # 1. GET /api/projects
    res = client.get("/api/projects")
    assert res.status_code == 200
    data = res.json()
    assert "active_project" in data
    assert "projects" in data
    assert "projects_dir" in data
    assert data["active_project"]["title"] == "Initial Project"
    assert len(data["projects"]) >= 1

    # 2. POST /api/projects/create - Success
    payload = {
        "title": "Slime Tamer",
        "folder_name": "slime_tamer",
        "source_lang": "Japanese",
        "target_lang": "English",
        "genre": "isekai",
        "raw_dir": "raw_chapters",
        "output_dir": "translated_chapters",
    }
    create_res = client.post("/api/projects/create", json=payload)
    assert create_res.status_code == 200
    data = create_res.json()
    assert data["success"] is True
    meta = data["active_project"]
    assert meta["title"] == "Slime Tamer"
    assert "slime_tamer" in meta["path"]

    # Verify project exists on disk and was initialized
    created_path = Path(meta["path"])
    assert (created_path / ".novel" / "config.yaml").exists()
    assert (created_path / ".novel" / "bible" / "bible.yaml").exists()

    # Verify active project switched
    res_after = client.get("/api/active-project")
    assert res_after.json()["active_project"]["title"] == "Slime Tamer"

    # 3. POST /api/projects/create - Conflict (already exists)
    conflict_res = client.post("/api/projects/create", json=payload)
    assert conflict_res.status_code == 409

    # 4. POST /api/projects/create - Empty title error
    bad_res = client.post("/api/projects/create", json={"title": "   "})
    assert bad_res.status_code == 400
