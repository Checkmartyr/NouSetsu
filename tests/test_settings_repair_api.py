"""Correctness regressions for the settings trust boundary and isolated defaults."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from nousetsu.cli.web_server import create_app
from nousetsu.storage.repository import NovelRepository
from nousetsu.utils.env import resolve_env, get_env_settings, save_env_settings, EnvironmentValidationError


@pytest.fixture
def settings_api(tmp_path, monkeypatch):
    env = tmp_path / "settings.env"
    env.write_text("# retained\nUNRELATED=keep\nNOVEL_MAX_REVIEW_LOOPS=4\nNOVEL_POST_POLISH_RECONCILIATION=false\n", encoding="utf-8")
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(env))
    for key in ("NOVEL_MAX_REVIEW_LOOPS", "NOVEL_POST_POLISH_RECONCILIATION", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    repo = NovelRepository(tmp_path / "Project 日本語")
    repo.initialize_project("Repair", "Japanese", "English")
    return TestClient(create_app()), repo, env


def put(client, endpoint, body, revision=None):
    header = revision or client.get(endpoint).headers["etag"]
    return client.put(endpoint, headers={"If-Match": header}, json=body)


def test_two_project_saves_survive_fresh_repository(settings_api, tmp_path):
    import yaml

    client, repo, _ = settings_api
    other = NovelRepository(tmp_path / "Other project")
    other.initialize_project("Other", "Japanese", "English")
    untouched = (other.config_file_path().read_bytes(), other.bible_file_path().read_bytes())
    url = f"/api/settings?project_path={repo.root_dir}"
    created_at = repo.load_config().created_at
    for title, temperature in (("First save", 0.1), ("Second save", 0)):
        response = put(client, url, {
            "title": title, "enable_rag": False, "chunk_overlap_lines": 0,
            "generation_settings": {"drafter": {"temperature": temperature,
                "thinking_budget": 0, "use_interactions_api": False}},
        })
        assert response.status_code == 200, response.text
        disk = yaml.safe_load(repo.config_file_path().read_text(encoding="utf-8"))
        fresh = NovelRepository(repo.root_dir).load_config()
        assert disk["title"] == fresh.title == title
        assert disk["generation_settings"]["drafter"]["temperature"] == temperature
        assert fresh.generation_settings["drafter"].use_interactions_api is False
        assert fresh.created_at == created_at
        assert disk["chunk_overlap_lines"] == fresh.chunk_overlap_lines == 0
        assert (other.config_file_path().read_bytes(), other.bible_file_path().read_bytes()) == untouched
    assert put(client, url, {"generation_settings": {}, "max_review_loops": None}).status_code == 200
    assert NovelRepository(repo.root_dir).load_config().generation_settings == {}


def test_revision_required_exact_and_conflict_preserves_disk(settings_api):
    client, repo, _ = settings_api
    url = f"/api/settings?project_path={repo.root_dir}"
    old = client.get(url)
    assert old.headers["etag"] == '"' + old.json()["revision"] + '"'
    assert client.put(url, json={"title": "missing"}).status_code == 428
    assert client.put(url, headers={"If-Match": "*"}, json={"title": "wildcard"}).status_code == 412
    assert put(client, url, {"title": "winner"}, old.headers["etag"]).status_code == 200
    assert put(client, url, {"genre": "stale"}, old.headers["etag"]).status_code == 412
    assert repo.load_config().title == "winner"
    assert repo.load_config().genre == "general"


@pytest.mark.parametrize("body", [
    {"max_review_loops": 99}, {"quality_threshold": 0}, {"max_tpm": 0},
    {"max_rpm": -1}, {"rag_top_k": 99}, {"chunk_threshold_lines": 0},
    {"target_chunk_lines": -1}, {"chunk_overlap_lines": -1},
    {"filter_scene_characters": "false"}, {"max_review_loops": True},
    {"max_review_loops": "3"}, {"enable_rag": None}, {"title": None},
    {"created_at": "overwrite"}, {"unknown": "private-value"},
    {"generation_settings": {"drafter": {"temperature": 3}}},
    {"generation_settings": {"drafter": {"use_interactions_api": "false"}}},
    {"generation_settings": {"drafter": {"unknown": "private-value"}}},
    {"generation_settings": {"unknown": {}}},
    {"procedural_learning_cadence": "invalid"}, {"procedural_learning_interval": 0},
])
def test_project_invalid_candidate_never_changes_files(settings_api, body):
    client, repo, _ = settings_api
    before = (repo.config_file_path().read_bytes(), repo.bible_file_path().read_bytes())
    response = put(client, f"/api/settings?project_path={repo.root_dir}", body)
    assert response.status_code == 422, response.text
    assert "private-value" not in response.text
    assert (repo.config_file_path().read_bytes(), repo.bible_file_path().read_bytes()) == before


@pytest.mark.parametrize("key,value", [
    ("NOVEL_MAX_REVIEW_LOOPS", "garbage"), ("NOVEL_MAX_REVIEW_LOOPS", "99"),
    ("NOVEL_MAX_TPM", "-1"), ("NOVEL_MAX_RPM", "0"),
    ("NOVEL_QUALITY_THRESHOLD", "NaN"), ("NOVEL_TEMPERATURE", "3"),
    ("NOVEL_THINKING_BUDGET", "-1"), ("NOVEL_USE_INTERACTIONS", "maybe"),
    ("NOVEL_THINKING_LEVEL", "unknown"), ("NOVEL_PROCEDURAL_LEARNING_CADENCE", "never"),
    ("NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES", "0"), ("CUSTOM_API_BASE_URL", "file:///private"),
    ("NOVEL_MODEL", "${UNCLOSED"), ("NOVEL_MODEL", "${NOVEL_MODEL}"),
    ("NOVEL_MODEL", "${HOME}-${UNCLOSED"),
])
def test_global_invalid_candidate_is_atomic(settings_api, key, value):
    client, _, env = settings_api
    before = env.read_bytes()
    response = put(client, "/api/environment", {"values": {key: value}})
    assert response.status_code == 422, response.text
    assert env.read_bytes() == before


def test_nullable_defaults_zero_and_false(settings_api):
    client, repo, _ = settings_api
    url = f"/api/settings?project_path={repo.root_dir}"
    initial = client.get(url).json()
    assert initial["max_review_loops"] is None
    assert initial["effective_config"]["max_review_loops"] == 4
    assert initial["effective_config"]["enable_post_polish_reconciliation"] is False
    body = {"max_review_loops": 2, "chunk_overlap_lines": 0,
            "generation_settings": {"drafter": {"temperature": 0, "thinking_budget": 0, "use_interactions_api": False}},
            "enable_procedural_graph_learning": False, "procedural_learning_interval": 7}
    saved = put(client, url, body).json()
    assert saved["effective_config"]["max_review_loops"] == 2
    assert saved["chunk_overlap_lines"] == 0
    assert saved["effective_generation_settings"]["drafter"]["temperature"] == 0
    assert repo.load_config().procedural_learning_interval == 7
    reset = put(client, url, {"max_review_loops": None, "use_interactions_api": None, "generation_settings": {}})
    assert reset.status_code == 200
    assert reset.json()["effective_config"]["max_review_loops"] == 4


def test_process_override_origin_revision_and_no_publication(settings_api, monkeypatch):
    client, _, env = settings_api
    monkeypatch.setenv("NOVEL_MODEL", "mock-process")
    before = client.get("/api/environment")
    saved = put(client, "/api/environment", {"values": {"NOVEL_MODEL": "mock-saved"}})
    assert saved.status_code == 200
    assert saved.json()["values"]["NOVEL_MODEL"] == "mock-saved"
    assert saved.json()["effective_values"]["NOVEL_MODEL"] == "mock-process"
    assert saved.json()["sources"]["NOVEL_MODEL"] == "process"
    assert os.environ["NOVEL_MODEL"] == "mock-process"
    monkeypatch.setenv("NOVEL_MODEL", "mock-new-process")
    assert put(client, "/api/environment", {"values": {"TARGET_LANG": "French"}}, saved.headers["etag"]).status_code == 412
    assert "# retained" in env.read_text(encoding="utf-8")


def test_project_env_isolation_and_interpolation(settings_api, monkeypatch):
    _, repo, env = settings_api
    monkeypatch.delenv("NOVEL_MODEL", raising=False)
    env.write_text("BASE=machine\nNOVEL_MODEL=${BASE}\n", encoding="utf-8")
    (repo.root_dir / ".env").write_text("BASE=project\nNOVEL_MODEL=${BASE}\nAUX=${MISSING:-fallback}\nBARE\n", encoding="utf-8")
    before = dict(os.environ)
    assert resolve_env(repo.root_dir)["NOVEL_MODEL"] == "project"
    assert resolve_env(repo.root_dir)["AUX"] == "fallback"
    assert resolve_env()["NOVEL_MODEL"] == "machine"
    assert dict(os.environ) == before


def test_secrets_never_escape_via_interpolation(settings_api, monkeypatch):
    client, repo, env = settings_api
    secret = "synthetic-private-key-never-expose"
    monkeypatch.setenv("GEMINI_API_KEY", secret)
    before = env.read_bytes()
    response = put(client, "/api/environment", {"values": {"NOVEL_MODEL": "${GEMINI_API_KEY}"}})
    assert response.status_code == 422
    assert secret not in response.text
    assert env.read_bytes() == before
    monkeypatch.setenv("NOVEL_MODEL", secret)
    assert secret not in client.get("/api/environment").text
    assert secret not in client.get(f"/api/settings?project_path={repo.root_dir}").text


def test_corrupt_project_visible_other_services_usable(settings_api):
    client, repo, _ = settings_api
    repo.config_file_path().write_text("max_review_loops: 99\n", encoding="utf-8")
    response = client.get(f"/api/settings?project_path={repo.root_dir}")
    assert response.status_code == 500
    assert client.get("/api/environment").status_code == 200
    assert client.get("/api/active-project").status_code == 200


def test_global_two_writers_exactly_one_wins(settings_api):
    client, _, _ = settings_api
    revision = client.get("/api/environment").headers["etag"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda language: put(client, "/api/environment", {"values": {"TARGET_LANG": language}}, revision), ["French", "Korean"]))
    assert sorted(reply.status_code for reply in replies) == [200, 412]


def test_reset_to_invalid_inherited_value_rejects_before_writing(settings_api):
    client, repo, env = settings_api
    url = f"/api/settings?project_path={repo.root_dir}"
    assert put(client, url, {"max_review_loops": 2}).status_code == 200
    env.write_text("NOVEL_MAX_REVIEW_LOOPS=99\n", encoding="utf-8")
    before = repo.config_file_path().read_bytes()
    response = put(client, url, {"max_review_loops": None})
    assert response.status_code == 422
    assert repo.config_file_path().read_bytes() == before


def test_overridden_file_credential_is_also_redacted(settings_api, monkeypatch):
    client, repo, env = settings_api
    file_secret = "synthetic-file-private-key"
    env.write_text(f"GEMINI_API_KEY={file_secret}\nNOVEL_MODEL={file_secret}\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-process-private-key")
    assert file_secret not in client.get("/api/environment").text
    monkeypatch.delenv("NOVEL_MODEL", raising=False)
    assert file_secret not in client.get(f"/api/settings?project_path={repo.root_dir}").text


def test_bad_dotenv_does_not_prevent_desktop_readiness(settings_api, monkeypatch):
    client, _, env = settings_api
    monkeypatch.delenv("NOVEL_MODEL", raising=False)
    env.write_text("NOVEL_MODEL=${NOVEL_MODEL}\n", encoding="utf-8")
    response = client.get("/api/desktop-info")
    assert response.status_code == 200
    assert response.json()["storage_error"]
    assert client.get("/api/environment").status_code == 200


def test_explicit_relative_process_projects_directory_wins(settings_api, monkeypatch, tmp_path):
    from nousetsu.storage.repository import get_projects_root_dir
    monkeypatch.setenv("NOUSETSU_DEFAULT_PROJECTS_DIR", str(tmp_path / "desktop"))
    monkeypatch.setenv("NOUSETSU_INSTALL_DIR", str(tmp_path))
    monkeypatch.setenv("NOVEL_PROJECTS_DIR", "./project")
    assert resolve_env()["NOVEL_PROJECTS_DIR"] == "./project"
    assert get_projects_root_dir() == (tmp_path / "project").resolve()
