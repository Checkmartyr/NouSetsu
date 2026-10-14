import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

import nousetsu.setup as setup
import nousetsu.cli.web_server as server
from nousetsu.agents.llm import get_llm, MockNovelLLM
from nousetsu.models.config import ProjectConfig
from nousetsu.storage.repository import NovelRepository
from nousetsu.utils.env import ENV_CONFIG_KEYS, ENV_SECRET_KEYS, resolve_env


@pytest.fixture
def installation(tmp_path, monkeypatch):
    for key in (*ENV_CONFIG_KEYS, *ENV_SECRET_KEYS):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setattr(setup, "documents_dir", lambda: tmp_path / "Documents")
    return TestClient(server.create_app()), tmp_path


def candidate(root, **extra):
    return {"skip_ai": True, "values": {"SOURCE_LANG": "auto", "TARGET_LANG": "Thai", "NOVEL_PROJECTS_DIR": str(root / "นิยาย")}, **extra}


def finish(client, body):
    initial = client.get("/api/setup")
    return client.post("/api/setup/complete", headers={"If-Match": initial.headers["etag"]}, json=body)


def test_fresh_skip_restart_and_upgrade(installation):
    client, root = installation
    state = client.get("/api/setup").json()
    assert not state["completed"] and not state["existing"]
    assert state["readiness"] == "not_connected"
    assert state["values"]["NOVEL_PROJECTS_DIR"] == str(root / "Documents/NouSetsu")
    assert finish(client, candidate(root, locale="th")).json()["success"]
    restarted = TestClient(server.create_app()).get("/api/setup").json()
    assert restarted["completed"] and restarted["locale"] == "th"
    assert restarted["readiness"] == "not_connected"
    assert json.loads((root / "setup.json").read_text())["version"] == 1
    assert dotenv_values(root / ".env")["TARGET_LANG"] == "Thai"
    assert restarted["values"]["TARGET_LANG"] == "Thai"


@pytest.mark.parametrize("provider,model", [("gemini", "gemini-selected"), ("openai", "gpt-selected"), ("openrouter", "vendor/model"), ("custom", "local-model")])
def test_routes_secrets_and_no_unsaved_write(installation, monkeypatch, provider, model):
    client, root = installation
    body = candidate(root, provider=provider, model=model, skip_ai=False, route_all=True, api_keys={setup.PROVIDER_KEYS[provider]: "private-key"})
    if provider == "custom":
        body["values"]["CUSTOM_API_BASE_URL"] = "http://127.0.0.1:8999/v1"
    monkeypatch.setattr(server, "fetch_model_catalog", lambda *args: [model])
    response = client.post("/api/setup/check", json={"kind": "catalog", "candidate": body})
    assert response.json()["models"] == [model]
    assert not (root / ".env").exists()
    response = finish(client, body)
    assert response.status_code == 200 and "private-key" not in response.text
    route = model if provider == "gemini" else f"{provider}:{model}"
    saved = dotenv_values(root / ".env")
    assert all(saved[key] == route for key in setup.ROUTE_KEYS)
    env = resolve_env()
    cfg = ProjectConfig()
    assert not setup.missing_translation_routes(cfg, env)
    assert cfg.get_rag_reranker_model(env) == route
    assert client.get("/api/setup").json()["semantic_retrieval"] == (provider == "gemini")
    assert "private-key" not in (root / "setup.json").read_text()


def test_explicit_role_overrides_preserved(installation):
    client, root = installation
    body = candidate(root, provider="openai", model="gpt-selected", skip_ai=False, route_all=True, api_keys={"OPENAI_API_KEY": "private-key"})
    body["values"]["NOVEL_CRITIC_MODEL"] = "openai:gpt-other"
    assert finish(client, body).status_code == 200
    assert dotenv_values(root / ".env")["NOVEL_CRITIC_MODEL"] == "openai:gpt-other"


def test_placeholders_and_missing_keys_never_mock(installation):
    client, root = installation
    (root / ".env").write_text("GEMINI_API_KEY=your_gemini_api_key_here\n")
    assert not client.get("/api/setup").json()["existing"]
    assert not client.get("/api/environment").json()["api_key_status"]["GEMINI_API_KEY"]
    with pytest.raises(ValueError, match="Connect AI"):
        get_llm("gemini-real", environ={"GEMINI_API_KEY": "your_gemini_api_key_here"}).invoke("Translate this")
    assert isinstance(get_llm("mock-model", environ={}), MockNovelLLM)
    assert finish(client, candidate(root, skip_ai=False)).status_code == 422


def test_existing_paths_comments_and_process_precedence(installation, monkeypatch):
    client, root = installation
    (root / ".env").write_text(f"# preserve me\nOPENAI_API_KEY=existing-key\nNOVEL_MODEL=openai:gpt-old\nNOVEL_PROJECTS_DIR='{root / 'existing'}'\nTARGET_LANG=Japanese\nUNRELATED=keep\n")
    state = client.get("/api/setup").json()
    assert state["existing"] and state["values"]["TARGET_LANG"] == "Japanese"
    assert state["values"]["NOVEL_PROJECTS_DIR"] == str(root / "existing")
    monkeypatch.setenv("TARGET_LANG", "Korean")
    checked = client.post("/api/setup/check", json={"kind": "local", "candidate": candidate(root)})
    assert "TARGET_LANG" in checked.json()["overridden_fields"]
    assert finish(client, candidate(root)).json()["success"]
    assert resolve_env()["TARGET_LANG"] == "Korean"
    assert "# preserve me" in (root / ".env").read_text()
    assert dotenv_values(root / ".env")["UNRELATED"] == "keep"


def test_conflict_invalid_fields_and_partial_save_retry(installation, monkeypatch):
    client, root = installation
    initial = client.get("/api/setup")
    assert client.post("/api/setup/complete", json=candidate(root)).status_code == 428
    (root / ".env").write_text("TARGET_LANG=English\n")
    assert client.post("/api/setup/complete", headers={"If-Match": initial.headers["etag"]}, json=candidate(root)).status_code == 412
    invalid = candidate(root, api_keys={"NOT_A_KEY": "do-not-display"})
    response = finish(client, invalid)
    assert response.status_code == 422 and "do-not-display" not in response.text
    write = setup.atomic_write_file
    monkeypatch.setattr(setup, "atomic_write_file", Mock(side_effect=PermissionError()))
    failed = finish(client, candidate(root)).json()
    assert failed["settings_saved"] and not failed["success"]
    assert not (root / "setup.json").exists()
    monkeypatch.setattr(setup, "atomic_write_file", write)
    retry = client.post("/api/setup/complete", headers={"If-Match": f'"{failed["revision"]}"'}, json=candidate(root))
    assert retry.json()["success"]


def test_tested_state_invalidates_after_credentials_change(installation, monkeypatch):
    client, root = installation
    body = candidate(root, provider="openai", model="gpt-selected", skip_ai=False, route_all=True, api_keys={"OPENAI_API_KEY": "private-key"})
    monkeypatch.setattr(setup, "test_connection", lambda *args: None)
    checked = client.post("/api/setup/check", json={"kind": "connection", "candidate": body})
    assert checked.json()["readiness"] == "tested"
    assert not (root / ".env").exists()
    assert finish(client, body).json()["success"]
    assert client.get("/api/setup").json()["readiness"] == "tested"
    (root / ".env").write_text((root / ".env").read_text().replace("private-key", "changed-key"))
    assert client.get("/api/setup").json()["readiness"] == "configured"


@pytest.mark.parametrize("reason,code", [("401 secret-provider-body", "key_rejected"), ("429 private-key", "quota"), ("404 private-key", "model_unavailable"), ("timeout private-key", "connection_failed")])
def test_upstream_failures_redacted(installation, monkeypatch, reason, code):
    client, root = installation
    body = candidate(root, provider="openai", model="gpt-selected", skip_ai=False, route_all=True, api_keys={"OPENAI_API_KEY": "private-key"})
    monkeypatch.setattr(setup, "test_connection", Mock(side_effect=RuntimeError(reason)))
    response = client.post("/api/setup/check", json={"kind": "connection", "candidate": body})
    assert response.status_code == 502 and response.json()["code"] == code
    assert "private-key" not in response.text and "secret-provider-body" not in response.text
    assert finish(client, body).json()["success"]
    assert client.get("/api/setup").json()["readiness"] == "needs_attention"


def test_origin_restrictions_and_unwritable_folder(installation):
    client, root = installation
    for path in ("/api/setup", "/api/setup/check", "/api/setup/complete"):
        response = client.get(path, headers={"Origin": "https://evil.example"}) if path == "/api/setup" else client.post(path, headers={"Origin": "https://evil.example"}, json={"kind": "local", "candidate": candidate(root)} if path.endswith("check") else candidate(root))
        assert response.status_code == 403
    obstacle = root / "file"
    obstacle.write_text("x")
    body = candidate(root)
    body["values"]["NOVEL_PROJECTS_DIR"] = str(obstacle / "nested")
    assert finish(client, body).status_code == 422


def test_translation_exploration_guard(installation, monkeypatch):
    client, root = installation
    novel = root / "novel"
    repo = NovelRepository(novel)
    repo.save_config(ProjectConfig(title="Novel"))
    # The API refuses before it starts a worker or emits any translation output.
    monkeypatch.setattr(server.active_job, "start", Mock())
    response = client.post("/api/translate/start", json={"project_path": str(novel)})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "connect_ai"
    server.active_job.start.assert_not_called()


def test_production_sample_uses_structured_output_without_fallback(installation, monkeypatch):
    _, root = installation
    body = setup.SetupCandidate(**candidate(root, provider="custom", model="local", route_all=True, skip_ai=False, api_keys={"CUSTOM_API_KEY": "private-key"}))
    body.values["CUSTOM_API_BASE_URL"] = "http://localhost:8999/v1"
    _, env, _ = setup.candidate_environment(body)
    fake = Mock()
    fake.with_structured_output.return_value.invoke.return_value = {"parsed": setup.ConnectionSample(translation="Good morning.")}
    factory = Mock(return_value=fake)
    monkeypatch.setattr("nousetsu.agents.llm.get_llm", factory)
    setup.test_connection(body, env)
    assert factory.call_args.args[0] == "custom:local"
    assert "fallback_model" not in factory.call_args.kwargs
    assert fake.max_retries == 0
    fake.with_structured_output.assert_called_once_with(setup.ConnectionSample, include_raw=True)
    fake.with_structured_output.return_value.invoke.return_value = {"parsed": None}
    with pytest.raises(ValueError, match="structured"):
        setup.test_connection(body, env)


def test_terminal_exploration_uses_same_writer_and_thai_prompts(installation, monkeypatch):
    client, root = installation
    from rich.console import Console
    import io
    answers = iter(["th", "auto", "Thai", str(root / "terminal-novels")])
    confirmations = iter([False, False, True])
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *args, **kwargs: next(confirmations))
    output = io.StringIO()
    setup.run_terminal_setup(Console(file=output, force_terminal=False))
    assert "ตั้งค่าเสร็จแล้ว" in output.getvalue()
    assert client.get("/api/setup").json()["completed"]
    assert client.get("/api/setup").json()["locale"] == "th"


def test_offline_project_invitation_and_language_preferences_preserved(installation):
    client, root = installation
    from nousetsu.storage.repository import ProjectRegistry
    project = root / "offline-project"
    NovelRepository(project).initialize_project("Offline novel", "Japanese", "French")
    ProjectRegistry().register_project(project)
    (root / ".env").write_text("SOURCE_LANG=Japanese\nTARGET_LANG=French\n")
    snapshot = client.get("/api/setup").json()
    assert snapshot["existing"] and not snapshot["completed"]
    assert snapshot["values"]["TARGET_LANG"] == "French"
