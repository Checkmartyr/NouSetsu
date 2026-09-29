import os
from pathlib import Path

from fastapi.testclient import TestClient
from dotenv import dotenv_values

import nousetsu.cli.web_server as web_server
from nousetsu.cli.web_server import create_app
from nousetsu.storage.repository import get_projects_root_dir
from nousetsu.utils.env import load_env


API_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY")


def test_desktop_projects_default_uses_install_project_path(tmp_path: Path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("NOVEL_MODEL=test-model\n", encoding="utf-8")
    projects_dir = tmp_path / "install" / "project"
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(env_path))
    monkeypatch.setenv("NOUSETSU_DEFAULT_PROJECTS_DIR", str(projects_dir))
    monkeypatch.delenv("NOVEL_PROJECTS_DIR", raising=False)

    load_env()

    assert os.environ["NOVEL_PROJECTS_DIR"] == str(projects_dir)
    assert get_projects_root_dir() == projects_dir.resolve()


def test_dotenv_projects_path_overrides_desktop_default(tmp_path: Path, monkeypatch):
    env_path = tmp_path / ".env"
    configured_projects = tmp_path / "my-novels"
    env_path.write_text(f"NOVEL_PROJECTS_DIR={configured_projects}\n", encoding="utf-8")
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(env_path))
    monkeypatch.setenv("NOUSETSU_DEFAULT_PROJECTS_DIR", str(tmp_path / "install" / "project"))
    monkeypatch.delenv("NOVEL_PROJECTS_DIR", raising=False)

    load_env()

    assert Path(os.environ["NOVEL_PROJECTS_DIR"]) == configured_projects


def test_environment_endpoint_saves_allowlisted_values_without_returning_secrets(
    tmp_path: Path, monkeypatch
):
    env_path = tmp_path / "local" / ".env"
    env_path.parent.mkdir()
    env_path.write_text("# Keep this comment\nUNRELATED_SETTING=preserve-me\nOPENAI_API_KEY=old-secret\n", encoding="utf-8")
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(env_path))
    for key in API_KEYS:
        monkeypatch.delenv(key, raising=False)

    client = TestClient(create_app())
    initial = client.get("/api/environment")
    assert initial.status_code == 200
    assert "OPENAI_API_KEY" not in initial.json()["values"]
    assert initial.json()["api_key_status"]["OPENAI_API_KEY"] is True
    assert "NOVEL_SCRAPER_MODEL" in initial.json()["values"]
    assert "old-secret" not in initial.text

    response = client.put(
        "/api/environment",
        json={
            "values": {
                "NOVEL_MODEL": "gemini-test-model",
                "NOVEL_SCRAPER_MODEL": "openrouter:anthropic/claude-3.7-sonnet",
            },
            "api_keys": {"OPENAI_API_KEY": "replacement-secret"},
            "clear_api_keys": ["GEMINI_API_KEY"],
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "replacement-secret" not in response.text

    saved = dotenv_values(env_path)
    assert saved["NOVEL_MODEL"] == "gemini-test-model"
    assert saved["NOVEL_SCRAPER_MODEL"] == "openrouter:anthropic/claude-3.7-sonnet"
    assert os.environ["NOVEL_SCRAPER_MODEL"] == "openrouter:anthropic/claude-3.7-sonnet"
    assert response.json()["values"]["NOVEL_SCRAPER_MODEL"] == "openrouter:anthropic/claude-3.7-sonnet"
    assert saved["OPENAI_API_KEY"] == "replacement-secret"
    assert saved["UNRELATED_SETTING"] == "preserve-me"
    assert "# Keep this comment" in env_path.read_text(encoding="utf-8")
    assert response.json()["api_key_status"]["OPENAI_API_KEY"] is True
    assert response.json()["api_key_status"]["GEMINI_API_KEY"] is False


def test_environment_endpoint_rejects_nonlocal_browser_origins(tmp_path: Path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(env_path))
    client = TestClient(create_app())

    response = client.get("/api/environment", headers={"Origin": "https://attacker.example"})

    assert response.status_code == 403
    assert not env_path.exists()


def test_environment_endpoint_rejects_unapproved_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(tmp_path / ".env"))
    client = TestClient(create_app())

    response = client.put(
        "/api/environment",
        json={"values": {"PYTHONPATH": "unsafe"}, "api_keys": {}, "clear_api_keys": []},
    )

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]
    assert not (tmp_path / ".env").exists()


def test_github_release_endpoint_compares_tags_and_returns_downloads(monkeypatch):
    monkeypatch.setenv("NOUSETSU_DESKTOP_VERSION", "1.2.0")
    monkeypatch.setattr(
        web_server,
        "_fetch_latest_github_release",
        lambda: {
            "tag_name": "v1.3.0",
            "name": "NouSetsu 1.3.0",
            "body": "Release notes",
            "html_url": "https://github.com/Checkmartyr/NouSetsu/releases/tag/v1.3.0",
            "published_at": "2026-09-20T00:00:00Z",
            "assets": [
                {
                    "name": "NouSetsu_1.3.0_x64-setup.exe",
                    "browser_download_url": "https://example.test/setup.exe",
                    "size": 1234,
                }
            ],
        },
    )

    response = TestClient(create_app()).get("/api/updates/latest")

    assert response.status_code == 200
    data = response.json()
    assert data["current_version"] == "1.2.0"
    assert data["latest_version"] == "v1.3.0"
    assert data["update_available"] is True
    assert data["assets"][0]["download_url"] == "https://example.test/setup.exe"


def test_release_version_comparison_handles_prereleases():
    assert web_server._is_newer_release("1.2.0", "1.1.9") is True
    assert web_server._is_newer_release("1.2.0", "1.2.0-rc.1") is True
    assert web_server._is_newer_release("1.2.0-beta.1", "1.2.0") is False
    assert web_server._is_newer_release("not-a-tag", "1.0.0") is False
