"""Hermetic settings audit. ``observed`` tests document defects, not desired contracts.

No production behavior is changed. Provider boundaries are replaced with local
MockNovelLLM instances; settings requests use the actual FastAPI handlers.
"""

import importlib
import json
import os
import stat
import subprocess
import sys
import threading
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

import nousetsu.utils.env as env_module
from nousetsu.agents.llm import MockNovelLLM, get_llm
from nousetsu.batch.runner import BatchRunner
from nousetsu.cli.web_server import create_app
from nousetsu.models.config import GENERATION_ROLES, ProjectConfig
from nousetsu.models.bible import CharacterProfile, NovelBible
from nousetsu.models.metadata import QualityAudit
from nousetsu.models.metadata import TokenUsage
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository


@pytest.fixture
def audit(tmp_path, monkeypatch):
    for key in (*env_module.ENV_CONFIG_KEYS, *env_module.ENV_SECRET_KEYS):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(tmp_path / "machine.env"))
    monkeypatch.setenv("NOVEL_MODEL", "mock-audit")
    monkeypatch.setenv("NOVEL_FALLBACK_MODEL", "mock-audit")
    monkeypatch.setenv("NOVEL_MAX_TPM", "10000000")
    monkeypatch.setenv("NOVEL_MAX_RPM", "10000")
    repositories = []
    for name in ("A 日本語", "B"):
        repo = NovelRepository(tmp_path / name)
        repo.initialize_project(name, "Japanese", "English")
        repositories.append(repo)
    client = TestClient(create_app())
    repo = repositories[0]
    return SimpleNamespace(
        client=client, repo=repo, other=repositories[1], root=tmp_path,
        params={"project_path": str(repo.root_dir)},
    )


VALID_FIELDS = {
    "title": "Changed title", "genre": "romance", "source_language": "Chinese",
    "target_language": "Thai", "project_id": "audit-id", "raw_dir": "原稿 with spaces",
    "output_dir": "translated with spaces", "model_name": "test-shared",
    "fallback_model": "test-fallback", **{f"{role}_model": f"test-{role}" for role in GENERATION_ROLES},
    "use_interactions_api": False, "auto_update_bible": False,
    "max_tpm": 12345, "max_rpm": 45, "cross_folder_summaries": False,
    "safety_recursive_subdivision": False, "safety_subdivision_min_lines": 5,
    "safety_subdivision_max_depth": 2, "max_review_loops": 2, "quality_threshold": 9.0,
    "enable_chunking": False, "chunk_threshold_lines": 20, "target_chunk_lines": 10,
    "chunk_overlap_lines": 0, "enable_rag": False, "rag_top_k": 4,
    "rag_embedding_model": "test-embedding", "enable_rag_reranker": False,
    "rag_reranker_model": "test-reranker", "filter_scene_characters": False,
    "filter_extractor_entities": False, "enable_patch_polishing": False,
    "enable_post_polish_reconciliation": False,
}


@pytest.mark.parametrize("field,value", VALID_FIELDS.items())
def test_valid_project_field_persists_and_isolates_other_project(audit, field, value):
    response = audit.client.put("/api/settings", params=audit.params, json={field: value})
    assert response.status_code == 200
    assert audit.repo.load_config().model_dump()[field] == value
    # A fresh app/client proves handler state is not the source of persistence.
    reloaded = TestClient(create_app()).get("/api/settings", params=audit.params).json()
    assert reloaded["config"][field] == value
    assert audit.other.load_config().model_dump()[field] != value


@pytest.mark.parametrize("field,value", [("max_review_loops", 0), ("quality_threshold", 11), ("rag_top_k", 0)])
def test_observed_invalid_constrained_values_poison_entire_config(audit, field, value):
    response = audit.client.put("/api/settings", params=audit.params, json={field: value})
    assert response.status_code == 200  # Observed defect: schema validation bypassed.
    assert yaml.safe_load(audit.repo.config_file_path().read_text(encoding="utf-8"))[field] == value
    assert audit.repo.load_config().title == "Untitle"  # Entire project silently defaults.
    assert audit.repo.load_bible().title == "A 日本語"


@pytest.mark.parametrize("field", [name for name, value in VALID_FIELDS.items() if isinstance(value, bool)])
def test_observed_project_string_false_becomes_true(audit, field):
    response = audit.client.put("/api/settings", params=audit.params, json={field: "false"})
    assert response.status_code == 200
    assert audit.repo.load_config().model_dump()[field] is True


@pytest.mark.parametrize("field", ["max_review_loops", "quality_threshold", "rag_top_k", "max_tpm"])
def test_malformed_project_number_rejected_without_disk_change(audit, field):
    before = audit.repo.config_file_path().read_bytes()
    response = audit.client.put("/api/settings", params=audit.params, json={field: "not-a-number"})
    assert response.status_code == 400
    assert audit.repo.config_file_path().read_bytes() == before


def test_generation_settings_all_roles_validation_zero_false_and_clear(audit, monkeypatch):
    monkeypatch.setenv("NOVEL_TEMPERATURE", "0.9")
    controls = {role: {"temperature": 0, "thinking_budget": 0, "thinking_level": "high", "use_interactions_api": False} for role in GENERATION_ROLES}
    assert audit.client.put("/api/settings", params=audit.params, json={"generation_settings": controls}).status_code == 200
    cfg = audit.repo.load_config()
    for role in GENERATION_ROLES:
        assert cfg.get_agent_generation_settings(role) == controls[role]
    before = audit.repo.config_file_path().read_bytes()
    for payload in ({"drafter": {"temperature": 3}}, {"drafter": {"thinking_budget": -1}}, {"unknown": {}}, {"drafter": None}):
        assert audit.client.put("/api/settings", params=audit.params, json={"generation_settings": payload}).status_code == 400
        assert audit.repo.config_file_path().read_bytes() == before
    assert audit.client.put("/api/settings", params=audit.params, json={"generation_settings": {}}).status_code == 200
    assert audit.repo.load_config().get_agent_generation_settings("drafter")["temperature"] == 0.9


@pytest.mark.parametrize("value", [None, "", "   "])
def test_model_clear_and_extractor_nullable_inheritance(audit, monkeypatch, value):
    monkeypatch.setenv("NOVEL_DRAFTER_MODEL", "test-env-drafter")
    monkeypatch.setenv("NOVEL_FILTER_EXTRACTOR_ENTITIES", "false")
    audit.client.put("/api/settings", params=audit.params, json={"drafter_model": "test-override", "filter_extractor_entities": True})
    audit.client.put("/api/settings", params=audit.params, json={"drafter_model": value, "filter_extractor_entities": None})
    cfg = audit.repo.load_config()
    assert cfg.drafter_model is None
    assert cfg.get_agent_model("drafter") == "test-env-drafter"
    assert cfg.get_filter_extractor_entities() is False


def test_observed_legacy_interactions_null_cannot_restore_inheritance(audit, monkeypatch):
    monkeypatch.setenv("NOVEL_USE_INTERACTIONS", "true")
    audit.client.put("/api/settings", params=audit.params, json={"use_interactions_api": False})
    audit.client.put("/api/settings", params=audit.params, json={"use_interactions_api": None})
    assert audit.repo.load_config().use_interactions_api is False
    assert audit.repo.load_config().get_agent_generation_settings("drafter")["use_interactions_api"] is False


def test_observed_unsupported_schema_fields_ignored(audit):
    fields = {"enable_procedural_graph_learning": False, "procedural_learning_cadence": "arc", "procedural_learning_interval": 2, "procedural_learning_min_failures": 5, "procedural_refiner_model": "test-refiner", "created_at": "changed", "unknown_setting": True}
    response = audit.client.put("/api/settings", params=audit.params, json=fields)
    assert response.status_code == 200
    cfg = audit.repo.load_config()
    assert cfg.enable_procedural_graph_learning is None
    assert cfg.procedural_learning_cadence is None
    assert cfg.procedural_learning_interval is None
    assert cfg.procedural_learning_min_failures is None
    assert cfg.procedural_refiner_model is None
    assert cfg.created_at != "changed"


def test_alias_and_nested_payload_precedence(audit):
    payload = {"config": {"title": "Nested", "target_chunk_lines": 17}, "title": "Top", "translated_dir": "alias-out", "output_dir": "ignored-out", "chunk_size_lines": 11}
    assert audit.client.put("/api/settings", params=audit.params, json=payload).status_code == 200
    cfg = audit.repo.load_config()
    assert (cfg.title, cfg.output_dir, cfg.target_chunk_lines) == ("Top", "alias-out", 11)
    assert audit.repo.load_bible().title == "Top"


def test_observed_config_bible_sync_failure_still_returns_success(audit, monkeypatch):
    def denied(*args):
        raise PermissionError("audit injected Bible save failure")
    monkeypatch.setattr(NovelRepository, "save_bible", denied)
    response = audit.client.put("/api/settings", params=audit.params, json={"target_language": "Thai"})
    assert response.status_code == 200
    assert audit.repo.load_config().target_language == "Thai"
    assert audit.repo.load_bible().target_language == "English"


def test_failed_config_save_returns_error_without_changing_bible(audit, monkeypatch):
    def denied(*args):
        raise PermissionError("audit injected config save failure")
    monkeypatch.setattr(NovelRepository, "save_config", denied)
    response = audit.client.put("/api/settings", params=audit.params, json={"title": "not saved"})
    assert response.status_code == 400
    assert audit.repo.load_config().title == audit.repo.load_bible().title == "A 日本語"


def test_observed_full_form_stale_save_overwrites_other_editor(audit):
    old = audit.client.get("/api/settings", params=audit.params).json()["config"]
    audit.client.put("/api/settings", params=audit.params, json={"title": "Editor A"})
    old["genre"] = "romance"
    audit.client.put("/api/settings", params=audit.params, json={"config": old})
    assert audit.repo.load_config().title == "A 日本語"
    assert audit.repo.load_config().genre == "romance"


def test_observed_cross_folder_config_does_not_update_runtime_bible(audit):
    audit.client.put("/api/settings", params=audit.params, json={"cross_folder_summaries": False})
    assert audit.repo.load_config().cross_folder_summaries is False
    assert audit.repo.load_bible().cross_folder_summaries is True


def test_observed_review_quota_env_precedes_project_but_constructor_wins(audit, monkeypatch):
    cfg = audit.repo.load_config()
    cfg.max_review_loops, cfg.quality_threshold, cfg.max_tpm, cfg.max_rpm = 2, 9.5, 12345, 12
    cfg.enable_rag = False
    audit.repo.save_config(cfg)
    for key, value in {"NOVEL_MAX_REVIEW_LOOPS": "4", "NOVEL_QUALITY_THRESHOLD": "8", "NOVEL_MAX_TPM": "30000", "NOVEL_MAX_RPM": "40"}.items():
        monkeypatch.setenv(key, value)
    runner = BatchRunner(audit.repo)
    assert (runner.max_review_loops, runner.quality_threshold, runner.rate_limiter.max_tpm, runner.rate_limiter.max_rpm) == (4, 8, 30000, 40)
    runner = BatchRunner(audit.repo, max_review_loops=1, quality_threshold=10, max_tpm=12000, max_rpm=10)
    assert (runner.max_review_loops, runner.quality_threshold, runner.rate_limiter.max_tpm, runner.rate_limiter.max_rpm) == (1, 10, 12000, 10)


def test_observed_reconciliation_default_masks_environment(audit, monkeypatch):
    monkeypatch.setenv("NOVEL_POST_POLISH_RECONCILIATION", "false")
    assert audit.repo.load_config().get_post_polish_reconciliation() is True
    assert BatchRunner(audit.repo, enable_rag=False).workflow.enable_post_polish_reconciliation is True
    assert BatchRunner(audit.repo, enable_rag=False, enable_post_polish_reconciliation=False).workflow.enable_post_polish_reconciliation is False


def test_boolean_overrides_and_observed_numeric_zero_constructor_fallback(audit):
    runner = BatchRunner(audit.repo, enable_chunking=False, enable_rag=False, auto_update_bible=False, filter_extractor_entities=False, enable_post_polish_reconciliation=False)
    assert runner.workflow.chunker is None
    assert runner.workflow.rag_engine is None
    assert runner.auto_update_bible is False
    assert runner.workflow.extractor.enable_entity_filtering is False
    assert runner.workflow.enable_post_polish_reconciliation is False
    runner = BatchRunner(audit.repo, enable_rag=False, chunk_overlap_lines=0)
    assert runner.workflow.chunker.overlap_lines == 3  # Explicit 0 lost to ``or``.
    audit.client.put("/api/settings", params=audit.params, json={"chunk_overlap_lines": 0})
    assert BatchRunner(audit.repo, enable_rag=False).workflow.chunker.overlap_lines == 0


def test_observed_runner_snapshot_changes_only_for_new_runner(audit):
    first = BatchRunner(audit.repo, enable_rag=False)
    audit.client.put("/api/settings", params=audit.params, json={"target_chunk_lines": 23, "enable_chunking": False, "enable_patch_polishing": False})
    assert first.workflow.chunker.target_chunk_lines == 400
    assert first.workflow.enable_patch_polishing is True
    second = BatchRunner(audit.repo, enable_rag=False)
    assert second.workflow.chunker is None
    assert second.workflow.enable_patch_polishing is False


def test_source_provider_factory_spies_record_real_resolution_without_live_calls(audit, monkeypatch):
    calls = {}
    for role, module_name in {"extractor": "extractor", "drafter": "drafter", "critic": "critic", "polisher": "polisher", "chronicler": "chronicler"}.items():
        def fake_get_llm(*args, _role=role, **kwargs):
            calls[_role] = kwargs
            return get_llm(model_name="mock-audit-factory", temperature=kwargs.get("temperature", 1))
        monkeypatch.setattr(importlib.import_module(f"nousetsu.agents.{module_name}"), "get_llm", fake_get_llm)
    cfg = audit.repo.load_config()
    cfg.model_name = "custom:project-shared"  # Spy avoids mock propagation and provider construction.
    cfg.fallback_model = "custom:project-fallback"
    cfg.critic_model = "custom:project-critic"
    cfg.enable_rag = False
    cfg.generation_settings = {role: {"temperature": 0.4, "thinking_level": "high", "thinking_budget": 0, "use_interactions_api": False} for role in GENERATION_ROLES if role != "scraper"}
    # Validate nested models before assignment, as the actual API does.
    cfg = ProjectConfig.model_validate(cfg.model_dump())
    audit.repo.save_config(cfg)
    runner = BatchRunner(audit.repo, drafter_model="custom:constructor-drafter")
    assert runner.critic_model == calls["critic"]["model_name"] == "custom:project-critic"
    assert calls["drafter"]["model_name"] == "custom:constructor-drafter"
    for role in calls:
        assert calls[role]["fallback_model"] == "custom:project-fallback"
        assert calls[role]["temperature"] == 0.4
        assert calls[role]["thinking_budget"] == 0
        assert calls[role]["use_interactions"] is False
        assert calls[role]["thinking_level"] == "high"


def test_observed_disabled_scene_filter_still_filters_actual_draft(audit, monkeypatch):
    audit.client.put("/api/settings", params=audit.params, json={"filter_scene_characters": False, "enable_rag": False, "cross_folder_summaries": False})
    drafter_module = importlib.import_module("nousetsu.agents.drafter")
    filter_spy = MagicMock(wraps=drafter_module.filter_characters_for_scene)
    monkeypatch.setattr(drafter_module, "filter_characters_for_scene", filter_spy)
    rolling_calls = []
    def rolling_context(self, **kwargs):
        rolling_calls.append(kwargs)
        return []
    monkeypatch.setattr(NovelBible, "get_rolling_context", rolling_context)
    runner = BatchRunner(audit.repo)
    chars = [CharacterProfile(name="Alice", original_name="アリス", role="supporting"), CharacterProfile(name="Bob", original_name="ボブ", role="supporting")]
    state = TranslationState(chapter_id="audit-1", source_text="アリスは本を読んだ。", novel_bible=audit.repo.load_bible(), active_characters=chars)
    result = runner.workflow._draft_step(state)
    assert result["draft_text"]
    assert filter_spy.call_count == 1
    assert filter_spy.call_args.kwargs["characters"] == chars
    assert drafter_module.filter_characters_for_scene._mock_wraps(characters=chars, source_text=state.source_text) == [chars[0]]
    assert rolling_calls[0]["cross_folder"] is True  # Config false ignored by Bible consumer.


def test_saved_chunk_boundary_rag_and_safety_controls_reach_runtime(audit):
    payload = {"chunk_threshold_lines": 20, "target_chunk_lines": 10, "chunk_overlap_lines": 0, "enable_rag": True, "rag_top_k": 4, "enable_rag_reranker": False, "safety_recursive_subdivision": False, "safety_subdivision_min_lines": 5, "safety_subdivision_max_depth": 2, "enable_patch_polishing": False, "enable_post_polish_reconciliation": False, "filter_extractor_entities": False}
    assert audit.client.put("/api/settings", params=audit.params, json=payload).status_code == 200
    workflow = BatchRunner(audit.repo).workflow
    exact = "\n".join(f"Line {i}." for i in range(20))
    longer = exact + "\nAnother line."
    assert workflow.chunker.should_chunk(exact) is False
    assert workflow.chunker.should_chunk(longer) is True
    assert "".join(chunk.content for chunk in workflow.chunker.split_lines(longer)) == longer
    for agent in (workflow.extractor, workflow.drafter, workflow.critic, workflow.polisher):
        assert agent.enable_recursive_subdivision is False
        assert agent.subdivision_min_lines == 5
        assert agent.subdivision_max_depth == 2
    assert workflow.extractor.enable_entity_filtering is False
    assert workflow.enable_patch_polishing is False
    assert workflow.enable_post_polish_reconciliation is False
    search_spy = MagicMock(return_value=[])
    workflow.rag_engine = SimpleNamespace(hybrid_search=search_spy)
    workflow._draft_step(TranslationState(chapter_id="audit-rag", chapter_num=2, source_text="アリスは本を読んだ。", novel_bible=audit.repo.load_bible()))
    assert search_spy.call_count == 1
    assert search_spy.call_args.kwargs["limit"] == 4
    assert search_spy.call_args.kwargs["enable_rerank"] is False
    assert search_spy.call_args.kwargs["reranker"] is None


@pytest.mark.parametrize("fidelity,style,expected", [(9, 9, "chronicle"), (9, 8, "polish"), (8, 9, "polish")])
def test_saved_review_threshold_requires_both_scores(audit, monkeypatch, fidelity, style, expected):
    monkeypatch.delenv("NOVEL_MAX_REVIEW_LOOPS", raising=False)
    monkeypatch.delenv("NOVEL_QUALITY_THRESHOLD", raising=False)
    audit.client.put("/api/settings", params=audit.params, json={"quality_threshold": 9, "max_review_loops": 2})
    workflow = BatchRunner(audit.repo, enable_rag=False).workflow
    state = TranslationState(chapter_id="audit-review", source_text="Test", polished_text="Test prose", novel_bible=audit.repo.load_bible(), review_iteration=2, max_review_loops=workflow.max_review_loops, quality_threshold=workflow.quality_threshold, quality_audit=QualityAudit(fidelity_score=fidelity, style_score=style, passed=True))
    assert workflow._route_after_critique(state) == expected
    state.review_iteration = 3
    assert workflow._route_after_critique(state) == "chronicle"


def test_observed_chunk_overlap_zero_still_supplies_three_draft_context_lines(audit, monkeypatch):
    audit.client.put("/api/settings", params=audit.params, json={"chunk_overlap_lines": 0, "chunk_threshold_lines": 20, "target_chunk_lines": 10, "enable_rag": False})
    workflow = BatchRunner(audit.repo).workflow
    contexts = []
    def draft_chunk(*args, **kwargs):
        contexts.append(kwargs["preceding_context"])
        return "First\nSecond\nThird\nFourth"
    monkeypatch.setattr(workflow.drafter, "_invoke_llm_draft", draft_chunk)
    text = "\n".join(f"Line {i}." for i in range(35))
    chunks = workflow.chunker.split_lines(text)
    assert len(chunks) > 1
    workflow.drafter.draft(source_text=text, bible=audit.repo.load_bible(), active_characters=[], active_glossary=[], rolling_summaries=[], chunks=chunks)
    assert workflow.chunker.overlap_lines == 0
    assert contexts[0] == ""
    assert contexts[1] == "Second\nThird\nFourth"


def test_observed_unvalidated_global_numeric_reaches_runner_failure(audit):
    response = audit.client.put("/api/environment", json={"values": {"NOVEL_MAX_REVIEW_LOOPS": "garbage"}})
    assert response.status_code == 200
    with pytest.raises(ValueError):
        BatchRunner(audit.repo, enable_rag=False)


def test_environment_all_keys_roundtrip_clear_and_secret_preservation(audit):
    values = {}
    for key in env_module.ENV_CONFIG_KEYS:
        if key.endswith("TEMPERATURE"):
            value = "0.4"
        elif key.endswith("THINKING_BUDGET"):
            value = "0"
        elif key.endswith("THINKING_LEVEL"):
            value = "high"
        elif key.endswith("USE_INTERACTIONS") or key in ("NOVEL_FILTER_EXTRACTOR_ENTITIES", "NOVEL_POST_POLISH_RECONCILIATION"):
            value = "false"
        elif key in ("NOVEL_MAX_TPM", "NOVEL_MAX_RPM", "NOVEL_MAX_REVIEW_LOOPS", "NOVEL_QUALITY_THRESHOLD"):
            value = {"NOVEL_MAX_TPM": "10000000", "NOVEL_MAX_RPM": "10000", "NOVEL_MAX_REVIEW_LOOPS": "2", "NOVEL_QUALITY_THRESHOLD": "9"}[key]
        elif key == "SOURCE_LANG":
            value = "Japanese"
        elif key == "TARGET_LANG":
            value = "Thai"
        elif key == "CUSTOM_API_BASE_URL":
            value = "http://127.0.0.1:15590/v1"
        elif key in ("NOVEL_PROJECTS_DIR", "NOVEL_SCRAPER_PATH", "NOVEL_SCRAPER_PYTHON"):
            value = str(audit.root / "audit 日本語 path")
        else:
            value = "mock-audit"
        values[key] = value
    keys = {key: "audit-placeholder-secret" for key in env_module.ENV_SECRET_KEYS}
    response = audit.client.put("/api/environment", json={"values": values, "api_keys": keys})
    assert response.status_code == 200
    assert "audit-placeholder-secret" not in response.text
    saved = dotenv_values(audit.root / "machine.env")
    assert all(saved[key] == value for key, value in values.items())
    assert all(saved[key] == value for key, value in keys.items())
    response = audit.client.put("/api/environment", json={"values": {key: "" for key in values}, "api_keys": {key: "" for key in keys}})
    assert response.status_code == 200
    saved = dotenv_values(audit.root / "machine.env")
    assert not any(key in saved for key in values)
    assert all(saved[key] == "audit-placeholder-secret" for key in keys)
    response = audit.client.put("/api/environment", json={"clear_api_keys": list(keys)})
    assert response.status_code == 200
    assert not any(response.json()["api_key_status"].values())


def test_environment_rejects_bad_payload_before_any_write(audit):
    for payload in ({"values": {"UNKNOWN": "x"}}, {"values": {"NOVEL_MODEL": "x\nEVIL=y"}}, {"values": {"NOVEL_MODEL": []}}, {"api_keys": {"OPENAI_API_KEY": "x"}, "clear_api_keys": ["OPENAI_API_KEY"]}):
        assert audit.client.put("/api/environment", json=payload).status_code == 400
        assert not (audit.root / "machine.env").exists()


def test_observed_environment_write_failure_partially_updates_disk(audit, monkeypatch):
    real_set = env_module.dotenv.set_key
    def fail_second(path, key, value, **kwargs):
        if key == "NOVEL_QUALITY_THRESHOLD":
            raise PermissionError("audit injected second-key write failure")
        return real_set(path, key, value, **kwargs)
    monkeypatch.setattr(env_module.dotenv, "set_key", fail_second)
    response = audit.client.put("/api/environment", json={"values": {"NOVEL_MAX_REVIEW_LOOPS": "4", "NOVEL_QUALITY_THRESHOLD": "9"}})
    assert response.status_code == 500
    assert dotenv_values(audit.root / "machine.env")["NOVEL_MAX_REVIEW_LOOPS"] == "4"
    assert "NOVEL_MAX_REVIEW_LOOPS" not in os.environ


def test_observed_dotenv_first_loaded_wins_and_leaks_between_projects(audit, monkeypatch):
    monkeypatch.delenv("NOUSETSU_ENV_FILE")
    monkeypatch.delenv("NOVEL_MODEL")
    monkeypatch.setattr(env_module, "find_repo_root", lambda: audit.root)
    monkeypatch.chdir(audit.root)
    (audit.repo.root_dir / ".env").write_text("NOVEL_MODEL=test-A\n", encoding="utf-8")
    (audit.other.root_dir / ".env").write_text("NOVEL_MODEL=test-B\n", encoding="utf-8")
    env_module.load_env(audit.repo.root_dir)
    env_module.load_env(audit.other.root_dir)
    assert os.environ["NOVEL_MODEL"] == "test-A"
    monkeypatch.delenv("NOVEL_MODEL")
    (audit.root / ".env").write_text("NOVEL_MODEL=test-central\n", encoding="utf-8")
    env_module.load_env(audit.repo.root_dir)
    assert os.environ["NOVEL_MODEL"] == "test-central"  # Docstring declares project > central.


def test_explicit_environment_path_skips_project_dotenv(audit, monkeypatch):
    monkeypatch.delenv("NOVEL_MODEL")
    (audit.root / "machine.env").write_text("NOVEL_MODEL=test-machine\n", encoding="utf-8")
    (audit.repo.root_dir / ".env").write_text("NOVEL_MODEL=test-project\n", encoding="utf-8")
    env_module.load_env(audit.repo.root_dir)
    assert os.environ["NOVEL_MODEL"] == "test-machine"


def test_observed_external_dotenv_edits_show_new_saved_value_but_old_effective_value(audit, monkeypatch):
    monkeypatch.delenv("NOVEL_MODEL")
    env_file = audit.root / "machine.env"
    env_file.write_text("NOVEL_MODEL=test-original\n", encoding="utf-8")
    env_module.load_env()
    env_file.write_text("NOVEL_MODEL=test-external-edit\n", encoding="utf-8")
    assert audit.client.get("/api/environment").json()["values"]["NOVEL_MODEL"] == "test-external-edit"
    assert audit.client.get("/api/settings", params=audit.params).json()["effective_model_name"] == "test-original"


def test_observed_web_creation_ignores_saved_default_languages(audit, monkeypatch):
    monkeypatch.setenv("NOVEL_PROJECTS_DIR", str(audit.root / "creation projects"))
    response = audit.client.put("/api/environment", json={"values": {"SOURCE_LANG": "Chinese", "TARGET_LANG": "French"}})
    assert response.status_code == 200
    response = audit.client.post("/api/projects/create", json={"title": "Language defaults audit", "folder_name": "creation-audit"})
    assert response.status_code == 200
    cfg = NovelRepository(response.json()["active_project"]["path"]).load_config()
    assert (cfg.source_language, cfg.target_language) == ("Japanese", "Thai")
    assert os.environ["SOURCE_LANG"] == "Chinese"
    assert os.environ["TARGET_LANG"] == "French"


def test_google_transport_spy_disabled_interactions_and_zero_budget(audit, monkeypatch):
    calls = []
    def fake_google(**kwargs):
        calls.append(kwargs)
        return MockNovelLLM(model_name="mock-google-transport", temperature=kwargs["temperature"])
    fake_module = ModuleType("langchain_google_genai")
    fake_module.ChatGoogleGenerativeAI = fake_google
    monkeypatch.setitem(sys.modules, "langchain_google_genai", fake_module)
    monkeypatch.setenv("GEMINI_API_KEY", "audit-placeholder-key")
    monkeypatch.setenv("NOVEL_USE_INTERACTIONS", "true")
    llm = get_llm(model_name="gemini-2.5-flash", fallback_model="gemini-2.5-pro", temperature=0, use_interactions=False, thinking_level="high", thinking_budget=0)
    assert llm.invoke([HumanMessage(content="Controlled audit")]).content
    assert len(calls) == 2
    assert [call["model"] for call in calls] == ["gemini-2.5-flash", "gemini-2.5-pro"]
    for call in calls:
        assert call["temperature"] == 0
        assert call["thinking_budget"] == 0
        assert call["thinking_config"] == {"thinking_level": "HIGH"}


def test_observed_interactions_payload_omits_configured_budget(audit, monkeypatch):
    from nousetsu.agents import interactions
    mock_client = MagicMock(spec=interactions.GeminiInteractionsClient)
    mock_client.create.return_value = interactions.InteractionResult(id="audit-id", model="gemini-2.5-flash", output_text="Audit response", usage=TokenUsage())
    real_chat = interactions.GeminiInteractionsChatModel
    def fake_chat(**kwargs):
        return real_chat(client=mock_client, **kwargs)
    monkeypatch.setattr(interactions, "GeminiInteractionsChatModel", fake_chat)
    monkeypatch.setenv("GEMINI_API_KEY", "audit-placeholder-key")
    llm = get_llm(model_name="gemini-2.5-flash", use_interactions=True, temperature=0.4, thinking_level="high", thinking_budget=0)
    assert llm.thinking_budget == 0
    assert llm.invoke([HumanMessage(content="Controlled audit")]).content == "Audit response"
    config = mock_client.create.call_args.kwargs["generation_config"]
    assert config == {"temperature": 0.4, "thinking_level": "high"}
    assert "thinking_budget" not in config


def test_fallback_transfers_controls_and_uses_secondary_on_primary_error(audit, monkeypatch):
    import nousetsu.agents.llm as llm_module
    calls = []
    def local_factory(**kwargs):
        calls.append(kwargs)
        return MockNovelLLM(model_name=kwargs["model_name"], temperature=kwargs["temperature"])
    monkeypatch.setattr(llm_module, "_create_single_llm", local_factory)
    original_generate = MockNovelLLM._generate
    def fail_primary(self, *args, **kwargs):
        if self.model_name == "test-primary":
            raise RuntimeError("audit injected primary failure")
        return original_generate(self, *args, **kwargs)
    monkeypatch.setattr(MockNovelLLM, "_generate", fail_primary)
    llm = get_llm(model_name="test-primary", fallback_model="test-secondary", temperature=0, thinking_level="low", thinking_budget=0, use_interactions=False)
    assert llm.invoke([HumanMessage(content="Controlled audit")]).content
    assert llm.last_model_used == "test-secondary"
    assert [call["model_name"] for call in calls] == ["test-primary", "test-secondary"]
    for call in calls:
        assert call["temperature"] == 0
        assert call["thinking_budget"] == 0
        assert call["thinking_level"] == "low"
        assert call["use_interactions"] is False


def test_settings_during_real_source_job_affect_subsequent_job_only(audit, monkeypatch):
    import nousetsu.cli.web_server as web_module
    initialized = threading.Event()
    release = threading.Event()
    runners = []
    def observed_runner(*args, **kwargs):
        runner = BatchRunner(*args, **kwargs)
        runners.append(runner)
        if len(runners) == 1:
            initialized.set()
            assert release.wait(10), "audit gate release timed out"
        return runner
    job = web_module.ActiveTranslationJob()
    monkeypatch.setattr(web_module, "active_job", job)
    monkeypatch.setattr(web_module, "BatchRunner", observed_runner)
    audit.client.put("/api/settings", params=audit.params, json={"enable_rag": False, "generation_settings": {"drafter": {"temperature": 0.3}}})
    upload = audit.client.post("/api/chapters/upload", json={"project_path": str(audit.repo.root_dir), "files": [{"name": "0001.txt", "content": "旅人は歩き始めた。"}, {"name": "0002.txt", "content": "旅人は本を読んだ。"}]})
    assert upload.status_code == 200
    try:
        assert audit.client.post("/api/translate/start", json={"project_path": str(audit.repo.root_dir), "chapter": 1}).status_code == 200
        assert initialized.wait(10)
        assert audit.client.get("/api/translate/status").json()["is_running"] is True
        saved = audit.client.put("/api/settings", params=audit.params, json={"generation_settings": {"drafter": {"temperature": 0.7}}, "enable_patch_polishing": False})
        assert saved.status_code == 200
        assert runners[0].workflow.drafter.llm.temperature == 0.3
        assert runners[0].workflow.enable_patch_polishing is True
        release.set()
        first_thread = job.thread
        assert first_thread is not None
        first_thread.join(timeout=15)
        assert not job.is_running
        assert (audit.repo.root_dir / "translated_chapters" / "0001.md").is_file()
        assert audit.client.post("/api/translate/start", json={"project_path": str(audit.repo.root_dir), "chapter": 2}).status_code == 200
        deadline = time.monotonic() + 15
        while job.is_running and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not job.is_running
        assert (audit.repo.root_dir / "translated_chapters" / "0002.md").is_file()
        assert len(runners) == 2
        assert runners[1].workflow.drafter.llm.temperature == 0.7
        assert runners[1].workflow.enable_patch_polishing is False
    finally:
        release.set()
        if job.thread is not None:
            job.stop()
            job.thread.join(timeout=15)


def test_clean_process_restart_reads_external_defaults_change(audit, monkeypatch):
    monkeypatch.delenv("NOVEL_MODEL")
    env_file = audit.root / "machine.env"
    env_file.write_text("NOVEL_MODEL=test-before-restart\n", encoding="utf-8")
    env_module.load_env()
    env_file.write_text("NOVEL_MODEL=test-after-restart\n", encoding="utf-8")
    assert audit.repo.load_config().get_model_name() == "test-before-restart"
    child_env = {key: value for key, value in os.environ.items() if key not in (*env_module.ENV_CONFIG_KEYS, *env_module.ENV_SECRET_KEYS)}
    child_env["NOUSETSU_ENV_FILE"] = str(env_file)
    script = "import json; from nousetsu.utils.env import load_env; from nousetsu.models.config import ProjectConfig; load_env(); print(json.dumps({'model': ProjectConfig().get_model_name()}))"
    completed = subprocess.run([sys.executable, "-c", script], env=child_env, cwd=audit.root, capture_output=True, text=True, check=True, timeout=15)
    assert json.loads(completed.stdout)["model"] == "test-after-restart"


@pytest.mark.skipif(os.name != "nt", reason="Windows read-only attribute behavior is the audit target")
def test_windows_readonly_environment_file_refuses_save_without_state_drift(audit, monkeypatch):
    env_file = audit.root / "machine.env"
    env_file.write_text("NOVEL_MODEL=test-readonly-before\n", encoding="utf-8")
    monkeypatch.setenv("NOVEL_MODEL", "test-readonly-before")
    before = env_file.read_bytes()
    original_mode = stat.S_IMODE(env_file.stat().st_mode)
    try:
        env_file.chmod(stat.S_IREAD)
        response = audit.client.put("/api/environment", json={"values": {"NOVEL_MODEL": "test-readonly-after"}})
        assert response.status_code == 500
        assert env_file.read_bytes() == before
        assert os.environ["NOVEL_MODEL"] == "test-readonly-before"
    finally:
        env_file.chmod(original_mode)


def test_observed_inherited_extractor_false_get_exposes_raw_null(audit, monkeypatch):
    monkeypatch.setenv("NOVEL_FILTER_EXTRACTOR_ENTITIES", "false")
    settings = audit.client.get("/api/settings", params=audit.params).json()
    assert settings["filter_extractor_entities"] is None
    assert settings["config"]["filter_extractor_entities"] is None
    assert settings["env"]["NOVEL_FILTER_EXTRACTOR_ENTITIES"] == "false"
    assert audit.repo.load_config().get_filter_extractor_entities() is False
    assert BatchRunner(audit.repo, enable_rag=False).workflow.extractor.enable_entity_filtering is False
