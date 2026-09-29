"""
Unit tests for the Novel-Scraper detector, models, bridge, and FastAPI endpoints.
"""

import os
import pytest
from fastapi.testclient import TestClient

from nousetsu.cli.web_server import create_app
from nousetsu.models.config import AgentGenerationSettings, ProjectConfig
from nousetsu.storage.repository import NovelRepository
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
    resolve_scraper_llm_settings,
    scraper_subprocess_environment,
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
        captured.append((args, kwargs["cwd"], kwargs.get("env")))
        return FakeProcess(args)

    monkeypatch.setattr(
        "nousetsu.scraper.bridge.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    bridge = NovelScraperBridge()
    worker_env = {"NOVEL_TEMPERATURE": "0.35"}
    result = await bridge.inspect_url("https://example.com/novel/", env=worker_env)

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
        worker_env,
    )
    assert captured[1] == (
        (str(backend.resolve()), "--scraper-worker", "romanize", "Test Novel"),
        str(app_data.resolve()),
        None,
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


def test_scraper_api_uses_project_route_and_generation_settings(tmp_path, monkeypatch):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Scraper route", "Japanese", "English", model_name="mock-main")
    config = repo.load_config()
    config.scraper_model = "openrouter:anthropic/claude-sonnet-4"
    config.generation_settings = {
        "scraper": AgentGenerationSettings(
            temperature=0.35,
            thinking_level="high",
            thinking_budget=700,
            use_interactions_api=False,
        )
    }
    repo.save_config(config)
    monkeypatch.setenv("NOVEL_TEMPERATURE", "0.9")
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-openrouter-key")
    monkeypatch.setattr("nousetsu.cli.web_server.get_scraper_info", lambda: (True, "scraper", "python"))
    captured = {}

    class FakeBridge:
        def is_available(self):
            return True

        async def inspect_url(self, url, env=None):
            captured["url"] = url
            captured["env"] = env
            return ScraperInspectResponse(success=True, url=url)

    monkeypatch.setattr("nousetsu.cli.web_server.NovelScraperBridge", FakeBridge)
    client = TestClient(create_app())
    project_path = str(repo.root_dir)

    check = client.get(f"/api/scraper/check?project_path={project_path}")
    inspect = client.post(
        "/api/scraper/inspect",
        json={"url": "https://example.com/novel/", "project_path": project_path},
    )

    assert check.status_code == 200
    assert check.json()["llm_model"] == "openrouter:anthropic/claude-sonnet-4"
    assert check.json()["llm_provider"] == "OpenRouter"
    assert inspect.status_code == 200
    assert captured["env"]["NOVEL_TEMPERATURE"] == "0.35"
    assert captured["env"]["NOVEL_THINKING_LEVEL"] == "high"
    assert captured["env"]["NOVEL_THINKING_BUDGET"] == "700"
    assert captured["env"]["NOVEL_USE_INTERACTIONS"] == "0"
    assert os.environ["NOVEL_TEMPERATURE"] == "0.9"
    assert "private-openrouter-key" not in inspect.text


def test_scraper_subprocess_receives_custom_provider_credentials():
    config = ProjectConfig(scraper_model="custom:local-model")
    parent_env = {
        "CUSTOM_API_KEY": "private-custom-key",
        "CUSTOM_API_BASE_URL": "http://127.0.0.1:8000/v1",
    }

    child_env = scraper_subprocess_environment(config, parent_env)
    route = resolve_scraper_llm_settings(child_env)

    assert route.provider == "Custom OpenAI-compatible"
    assert child_env["CUSTOM_API_KEY"] == "private-custom-key"
    assert child_env["CUSTOM_API_BASE_URL"] == "http://127.0.0.1:8000/v1"
    assert parent_env == {
        "CUSTOM_API_KEY": "private-custom-key",
        "CUSTOM_API_BASE_URL": "http://127.0.0.1:8000/v1",
    }


def test_scraper_project_environment_is_resolved_without_mutating_parent():
    config = ProjectConfig(
        model_name="openai:gpt-4.1-mini",
        scraper_model="openrouter:anthropic/claude-sonnet-4",
        fallback_model="openai:gpt-4.1-nano",
        generation_settings={
            "scraper": {
                "temperature": 0.35,
                "thinking_level": "high",
                "thinking_budget": 700,
                "use_interactions_api": False,
            }
        },
    )
    parent_env = {
        "NOVEL_TEMPERATURE": "0.9",
        "NOVEL_THINKING_LEVEL": "low",
        "OPENROUTER_API_KEY": "private-key",
    }

    child_env = scraper_subprocess_environment(config, parent_env)
    route = resolve_scraper_llm_settings(child_env)

    assert child_env["NOVEL_SCRAPER_MODEL"] == "openrouter:anthropic/claude-sonnet-4"
    assert child_env["NOVEL_FALLBACK_MODEL"] == "openai:gpt-4.1-nano"
    assert child_env["NOVEL_TEMPERATURE"] == "0.35"
    assert child_env["NOVEL_THINKING_LEVEL"] == "high"
    assert child_env["NOVEL_THINKING_BUDGET"] == "700"
    assert child_env["NOVEL_USE_INTERACTIONS"] == "0"
    assert route.model == "openrouter:anthropic/claude-sonnet-4"
    assert route.provider == "OpenRouter"
    assert parent_env == {
        "NOVEL_TEMPERATURE": "0.9",
        "NOVEL_THINKING_LEVEL": "low",
        "OPENROUTER_API_KEY": "private-key",
    }


def test_scraper_check_api_endpoint(monkeypatch):
    """Report the effective model route without exposing provider credentials."""
    monkeypatch.setenv("NOVEL_SCRAPER_MODEL", "openrouter:anthropic/claude-3.7-sonnet")
    monkeypatch.setenv("NOVEL_FALLBACK_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/scraper/check")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert "novel_scraper" in data["scraper_dir"]
    assert "python" in data["python_exe"].lower()
    assert data["llm_model"] == "openrouter:anthropic/claude-3.7-sonnet"
    assert data["llm_provider"] == "OpenRouter"
    assert data["llm_fallback_model"] == "openai:gpt-4.1-mini"
    assert data["llm_fallback_provider"] == "OpenAI"
    assert "OPENROUTER_API_KEY" not in response.text


def test_scraper_status_not_found():
    """Test 404 behavior for non-existent scraper task."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/scraper/status/non-existent-task-id")
    assert response.status_code == 404
