"""Unit tests for central .env model configuration and precedence cascade."""
import os
from pathlib import Path
import pytest
from nousetsu.batch.runner import BatchRunner
from nousetsu.models.config import ProjectConfig
from nousetsu.storage.repository import NovelRepository


def test_project_config_defaults_from_env(monkeypatch):
    monkeypatch.setenv("NOVEL_MODEL", "env-primary-model")
    monkeypatch.setenv("NOVEL_FALLBACK_MODEL", "env-fallback-model")
    monkeypatch.setenv("NOVEL_EXTRACTOR_MODEL", "env-extractor-model")
    monkeypatch.setenv("NOVEL_DRAFTER_MODEL", "env-drafter-model")
    monkeypatch.setenv("NOVEL_CRITIC_MODEL", "env-critic-model")
    monkeypatch.setenv("NOVEL_POLISHER_MODEL", "env-polisher-model")
    monkeypatch.setenv("NOVEL_CHRONICLER_MODEL", "env-chronicler-model")

    cfg = ProjectConfig()
    # Fields are None by default, indicating inheritance from .env
    assert cfg.model_name is None
    assert cfg.fallback_model is None
    assert cfg.extractor_model is None

    # Dynamic getters resolve directly to .env values
    assert cfg.get_model_name() == "env-primary-model"
    assert cfg.get_fallback_model() == "env-fallback-model"
    assert cfg.get_agent_model("extractor") == "env-extractor-model"
    assert cfg.get_agent_model("drafter") == "env-drafter-model"
    assert cfg.get_agent_model("critic") == "env-critic-model"
    assert cfg.get_agent_model("polisher") == "env-polisher-model"
    assert cfg.get_agent_model("chronicler") == "env-chronicler-model"


def test_project_config_override_takes_precedence_over_env(monkeypatch):
    monkeypatch.setenv("NOVEL_MODEL", "env-primary-model")
    monkeypatch.setenv("NOVEL_EXTRACTOR_MODEL", "env-extractor-model")

    cfg = ProjectConfig(
        model_name="project-override-model",
        extractor_model="project-override-extractor"
    )

    # Config overrides take precedence over .env
    assert cfg.get_model_name() == "project-override-model"
    assert cfg.get_agent_model("extractor") == "project-override-extractor"
    # Unset agent models fall back to config's model_name override, then .env
    assert cfg.get_agent_model("drafter") == "project-override-model"


def test_batch_runner_precedence_cascade(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NOVEL_MODEL", "env-primary")
    monkeypatch.setenv("NOVEL_EXTRACTOR_MODEL", "env-extractor")
    monkeypatch.setenv("NOVEL_DRAFTER_MODEL", "env-drafter")

    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test Hierarchy", "Japanese", "English")

    # Case 1: Pure .env fallback when config has no model overrides
    runner1 = BatchRunner(repo)
    assert runner1.model_name == "env-primary"
    assert runner1.extractor_model == "env-extractor"
    assert runner1.drafter_model == "env-drafter"

    # Case 2: Config override takes precedence over .env
    cfg = repo.load_config()
    cfg.extractor_model = "cfg-override-extractor"
    repo.save_config(cfg)

    runner2 = BatchRunner(repo)
    assert runner2.extractor_model == "cfg-override-extractor"
    assert runner2.drafter_model == "env-drafter"

    # Case 3: Explicit constructor argument takes precedence over both config and .env
    runner3 = BatchRunner(repo, extractor_model="arg-override-extractor")
    assert runner3.extractor_model == "arg-override-extractor"


def test_initialize_project_does_not_save_hardcoded_models(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Clean Config Test", "Japanese", "English")

    config_path = repo.config_file_path()
    raw_content = config_path.read_text(encoding="utf-8")

    # The serialized YAML should not hardcode production or mock model names
    assert "gemini-3.1-flash-lite" not in raw_content
    assert "gemini-3.5-flash-lite" not in raw_content
    assert "gemma-4-26b-a4b-it" not in raw_content

    # Loading config should still yield correct effective models
    loaded_cfg = repo.load_config()
    assert loaded_cfg.model_name is None
    assert loaded_cfg.get_model_name() is not None
