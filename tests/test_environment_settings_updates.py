import os
from pathlib import Path

from fastapi.testclient import TestClient
from dotenv import dotenv_values

import nousetsu.cli.web_server as web_server
from nousetsu.cli.web_server import create_app
from nousetsu.storage.repository import get_projects_root_dir
from nousetsu.utils.env import load_env


API_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "CUSTOM_API_KEY")


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
    env_path.write_text("# Keep this comment\nUNRELATED_SETTING=preserve-me\nOPENAI_API_KEY=old-secret\nCUSTOM_API_KEY=old-custom-secret\n", encoding="utf-8")
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(env_path))
    for key in (*API_KEYS, "NOVEL_MODEL", "NOVEL_SCRAPER_MODEL", "NOVEL_DRAFTER_TEMPERATURE", "NOVEL_SCRAPER_USE_INTERACTIONS"):
        monkeypatch.delenv(key, raising=False)

    client = TestClient(create_app())
    initial = client.get("/api/environment")
    assert initial.status_code == 200
    assert "OPENAI_API_KEY" not in initial.json()["values"]
    assert initial.json()["api_key_status"]["OPENAI_API_KEY"] is True
    assert "CUSTOM_API_KEY" not in initial.json()["values"]
    assert initial.json()["api_key_status"]["CUSTOM_API_KEY"] is True
    assert "CUSTOM_API_BASE_URL" in initial.json()["values"]
    assert "NOVEL_SCRAPER_MODEL" in initial.json()["values"]
    assert "old-secret" not in initial.text
    assert "old-custom-secret" not in initial.text

    response = client.put(
        "/api/environment",
        json={
            "values": {
                "NOVEL_MODEL": "gemini-test-model",
                "NOVEL_SCRAPER_MODEL": "openrouter:anthropic/claude-3.7-sonnet",
                "NOVEL_DRAFTER_TEMPERATURE": "0.75",
                "NOVEL_SCRAPER_USE_INTERACTIONS": "false",
                "CUSTOM_API_BASE_URL": "https://custom.example/v1",
            },
            "api_keys": {
                "OPENAI_API_KEY": "replacement-secret",
                "CUSTOM_API_KEY": "replacement-custom-secret",
            },
            "clear_api_keys": ["GEMINI_API_KEY"],
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "replacement-secret" not in response.text
    assert "replacement-custom-secret" not in response.text

    saved = dotenv_values(env_path)
    assert saved["NOVEL_MODEL"] == "gemini-test-model"
    assert saved["NOVEL_SCRAPER_MODEL"] == "openrouter:anthropic/claude-3.7-sonnet"
    assert saved["NOVEL_DRAFTER_TEMPERATURE"] == "0.75"
    assert saved["NOVEL_SCRAPER_USE_INTERACTIONS"] == "false"
    assert saved["CUSTOM_API_BASE_URL"] == "https://custom.example/v1"
    assert saved["CUSTOM_API_KEY"] == "replacement-custom-secret"
    assert os.environ["NOVEL_SCRAPER_MODEL"] == "openrouter:anthropic/claude-3.7-sonnet"
    assert response.json()["values"]["NOVEL_SCRAPER_MODEL"] == "openrouter:anthropic/claude-3.7-sonnet"
    assert saved["OPENAI_API_KEY"] == "replacement-secret"
    assert saved["UNRELATED_SETTING"] == "preserve-me"
    assert "# Keep this comment" in env_path.read_text(encoding="utf-8")
    assert response.json()["api_key_status"]["OPENAI_API_KEY"] is True
    assert response.json()["api_key_status"]["CUSTOM_API_KEY"] is True
    assert response.json()["api_key_status"]["GEMINI_API_KEY"] is False


def test_model_catalog_endpoint_is_local_and_never_returns_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setenv("OPENAI_API_KEY", "private-openai-key")
    requests = []

    def fake_fetch(provider, api_key):
        requests.append((provider, api_key))
        return ["gpt-4.1-mini"]

    monkeypatch.setattr(web_server, "fetch_model_catalog", fake_fetch)
    client = TestClient(create_app())

    response = client.get("/api/model-catalog?provider=openai")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "openai", "configured": True, "models": ["gpt-4.1-mini"]
    }
    assert "private-openai-key" not in response.text
    assert requests == [("openai", "private-openai-key")]

    denied = client.get(
        "/api/model-catalog?provider=openai",
        headers={"Origin": "https://attacker.example"},
    )
    assert denied.status_code == 403
    assert len(requests) == 1

    monkeypatch.delenv("OPENAI_API_KEY")
    unconfigured = client.get("/api/model-catalog?provider=openai")
    assert unconfigured.status_code == 200
    assert unconfigured.json() == {"provider": "openai", "configured": False, "models": []}


def test_custom_model_catalog_uses_saved_base_url_and_never_returns_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setenv("CUSTOM_API_KEY", "private-custom-key")
    monkeypatch.setenv("CUSTOM_API_BASE_URL", "https://custom.example/v1")
    requests = []

    def fake_fetch(provider, api_key, base_url=None):
        requests.append((provider, api_key, base_url))
        return ["custom-chat-v1"]

    monkeypatch.setattr(web_server, "fetch_model_catalog", fake_fetch)
    client = TestClient(create_app())

    response = client.get("/api/model-catalog?provider=custom")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "custom", "configured": True, "models": ["custom-chat-v1"]
    }
    assert "private-custom-key" not in response.text
    assert requests == [
        ("custom", "private-custom-key", "https://custom.example/v1")
    ]

    monkeypatch.delenv("CUSTOM_API_BASE_URL")
    unconfigured = client.get("/api/model-catalog?provider=custom")
    assert unconfigured.json() == {"provider": "custom", "configured": False, "models": []}


def test_custom_model_catalog_rejects_invalid_base_url(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setenv("CUSTOM_API_KEY", "custom-test-key")
    monkeypatch.setenv("CUSTOM_API_BASE_URL", "file:///tmp/v1")

    response = TestClient(create_app()).get("/api/model-catalog?provider=custom")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid custom provider base URL."


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
