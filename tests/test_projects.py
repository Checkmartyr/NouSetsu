"""Unit tests for ProjectConfig and ProjectRegistry."""
from pathlib import Path
import pytest
from nousetsu.models.config import ProjectConfig
from nousetsu.storage.repository import NovelRepository, ProjectRegistry


def test_project_config_defaults(tmp_path: Path):
    cfg = ProjectConfig()
    assert cfg.title == "Ascendance of a Bookworm"
    assert cfg.source_language == "English"
    assert cfg.target_language == "Thai"
    # Model fields default to None, indicating inheritance from .env
    assert cfg.model_name is None
    assert cfg.fallback_model is None
    assert cfg.extractor_model is None
    assert cfg.drafter_model is None
    assert cfg.critic_model is None
    assert cfg.polisher_model is None
    assert cfg.chronicler_model is None
    # Effective models resolve dynamically via getters
    assert cfg.get_model_name() is not None
    assert cfg.get_agent_model("extractor") is not None
    assert cfg.max_tpm == 32000
    assert cfg.chunk_threshold_lines == 85
    assert cfg.raw_dir == "raw_chapters"
    assert cfg.output_dir == "translated_chapters"
    assert cfg.get_raw_path(tmp_path) == (tmp_path / "raw_chapters").resolve()
    assert cfg.get_output_path(tmp_path) == (tmp_path / "translated_chapters").resolve()


def test_project_config_external_paths(tmp_path: Path):
    proj_dir = tmp_path / "project_root"
    external_raw = tmp_path / "external_source_raw"
    external_raw.mkdir(parents=True, exist_ok=True)

    # 1. Absolute path
    cfg = ProjectConfig(raw_dir=str(external_raw))
    assert cfg.get_raw_path(proj_dir) == external_raw.resolve()

    # 2. Relative to base_dir
    local_raw = proj_dir / "my_local_raw"
    local_raw.mkdir(parents=True, exist_ok=True)
    cfg2 = ProjectConfig(raw_dir="my_local_raw")
    assert cfg2.get_raw_path(proj_dir) == local_raw.resolve()


def test_project_registry_and_initialization(tmp_path: Path):
    registry_file = tmp_path / "registry"
    reg = ProjectRegistry(storage_dir=registry_file)

    proj_a = tmp_path / "novels" / "project_a"
    repo_a = NovelRepository(proj_a)
    repo_a.initialize_project(
        title="Isekai Sword",
        source_lang="Japanese",
        target_lang="Spanish",
        raw_dir="inputs",
        output_dir="outputs",
        model_name="gemini-2.5-pro"
    )
    reg.register_project(proj_a)
    reg.set_last_active_project(proj_a)

    projects = reg.list_projects()
    assert len(projects) >= 1
    p = next(x for x in projects if x["title"] == "Isekai Sword")
    assert p["source_language"] == "Japanese"
    assert p["target_language"] == "Spanish"
    assert p["raw_dir"] == str((proj_a / "inputs").resolve())
    assert p["output_dir"] == str((proj_a / "outputs").resolve())

    # Verify last active
    assert reg.get_last_active_project() == proj_a.resolve()


def test_repository_load_and_save_config(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    cfg = repo.load_config()
    assert cfg.title == "Ascendance of a Bookworm"

    cfg.title = "Overlord Saga"
    cfg.source_language = "Japanese"
    cfg.target_language = "German"
    cfg.raw_dir = "raw_source"
    cfg.output_dir = "german_out"
    repo.save_config(cfg)

    reloaded = repo.load_config()
    assert reloaded.title == "Overlord Saga"
    assert reloaded.target_language == "German"
    assert reloaded.raw_dir == "raw_source"
    assert reloaded.output_dir == "german_out"
