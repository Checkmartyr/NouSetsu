"""Unit tests for configurable per-chunk character and glossary filtering in EntityExtractorAgent."""
import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.batch.runner import BatchRunner
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.config import ProjectConfig
from nousetsu.storage.repository import NovelRepository


def _build_test_bible(num_chars: int = 25, num_terms: int = 30) -> NovelBible:
    """Helper to generate a rich NovelBible for filtering tests."""
    bible = NovelBible(
        title="Test Novel",
        source_language="Japanese",
        target_language="English"
    )
    # Core protagonist
    bible.characters.append(CharacterProfile(
        name="Bob",
        original_name="ボブ",
        role="protagonist",
        voice="casual hero"
    ))
    # Character to appear in scene
    bible.characters.append(CharacterProfile(
        name="Elise",
        original_name="エリーゼ",
        role="supporting",
        voice="polite lady"
    ))
    # Characters that do not appear
    for i in range(1, num_chars + 1):
        bible.characters.append(CharacterProfile(
            name=f"ExtraChar_{i:02d}",
            original_name=f"エキストラ_{i:02d}",
            role="minor",
            voice="neutral"
        ))

    # Terms
    bible.glossary.append(GlossaryItem(
        source="竜剣",
        target="Dragon Sword",
        category="item"
    ))
    for i in range(1, num_terms + 1):
        bible.glossary.append(GlossaryItem(
            source=f"用語_{i:02d}",
            target=f"Term_{i:02d}",
            category="term"
        ))
    return bible


def test_extractor_filtering_enabled():
    """Verify that when filtering is enabled, only scene-present entities and core roles enter prompt."""
    bible = _build_test_bible(num_chars=20, num_terms=30)
    agent = EntityExtractorAgent(model_name="mock-model", enable_entity_filtering=True)

    captured_sys_prompt = []

    def mock_invoke(messages):
        sys_msg = messages[0].content
        captured_sys_prompt.append(sys_msg)
        return AIMessage(content='{"new_characters": [], "new_terms": [], "active_terms_in_chapter": []}')

    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(side_effect=mock_invoke)
    mock_llm.last_model_used = "mock-model"
    agent.llm = mock_llm

    source_text = "エリーゼは竜剣を握りしめた。"  # Mentions Elise and Dragon Sword, but not Bob or ExtraChar
    agent.extract(source_text=source_text, bible=bible)

    assert len(captured_sys_prompt) == 1
    prompt = captured_sys_prompt[0]

    # Elise should be present (text match)
    assert "エリーゼ -> Elise" in prompt
    # Bob should be present (core role: protagonist)
    assert "ボブ -> Bob" in prompt
    # Extra characters should NOT be present (filtered out!)
    assert "エキストラ_01" not in prompt
    assert "エキストラ_15" not in prompt

    # Dragon Sword should be present (text match)
    assert "竜剣 -> Dragon Sword" in prompt
    # Unmentioned terms should NOT be present
    assert "用語_01" not in prompt
    assert "用語_15" not in prompt


def test_extractor_filtering_disabled():
    """Verify that when filtering is disabled, all characters and terms are included in prompt."""
    bible = _build_test_bible(num_chars=10, num_terms=10)
    agent = EntityExtractorAgent(model_name="mock-model", enable_entity_filtering=False)

    captured_sys_prompt = []

    def mock_invoke(messages):
        captured_sys_prompt.append(messages[0].content)
        return AIMessage(content='{"new_characters": [], "new_terms": [], "active_terms_in_chapter": []}')

    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(side_effect=mock_invoke)
    mock_llm.last_model_used = "mock-model"
    agent.llm = mock_llm

    source_text = "エリーゼは立ち上がった。"
    agent.extract(source_text=source_text, bible=bible)

    prompt = captured_sys_prompt[0]
    # In unfiltered mode, all extra characters and terms are included
    assert "エキストラ_01" in prompt
    assert "エキストラ_10" in prompt
    assert "用語_01" in prompt
    assert "用語_10" in prompt


def test_extractor_filtering_no_truncation():
    """Verify max_characters=0 prevents 15-character truncation when 20+ characters appear."""
    bible = NovelBible(title="Banquet", source_language="Japanese", target_language="English")
    for i in range(25):
        bible.characters.append(CharacterProfile(
            name=f"Noble_{i:02d}",
            original_name=f"貴族_{i:02d}",
            role="minor",
            voice="polite"
        ))

    agent = EntityExtractorAgent(model_name="mock-model", enable_entity_filtering=True)

    captured_sys_prompt = []

    def mock_invoke(messages):
        captured_sys_prompt.append(messages[0].content)
        return AIMessage(content='{"new_characters": [], "new_terms": [], "active_terms_in_chapter": []}')

    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(side_effect=mock_invoke)
    mock_llm.last_model_used = "mock-model"
    agent.llm = mock_llm

    # Source text mentions all 25 nobles
    source_text = " ".join([f"貴族_{i:02d}" for i in range(25)])
    agent.extract(source_text=source_text, bible=bible)

    prompt = captured_sys_prompt[0]
    # Verify all 25 nobles are retained (not capped at 15)
    for i in range(25):
        assert f"貴族_{i:02d} -> Noble_{i:02d}" in prompt


def test_extractor_filtering_empty_fallback():
    """Verify that when 0 terms match, fallback_on_empty=False leaves glossary empty rather than injecting random terms."""
    bible = _build_test_bible(num_chars=2, num_terms=20)
    agent = EntityExtractorAgent(model_name="mock-model", enable_entity_filtering=True)

    captured_sys_prompt = []

    def mock_invoke(messages):
        captured_sys_prompt.append(messages[0].content)
        return AIMessage(content='{"new_characters": [], "new_terms": [], "active_terms_in_chapter": []}')

    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(side_effect=mock_invoke)
    mock_llm.last_model_used = "mock-model"
    agent.llm = mock_llm

    source_text = "ただの静かな部屋。"  # Completely unrelated text with 0 term matches
    agent.extract(source_text=source_text, bible=bible)

    prompt = captured_sys_prompt[0]
    assert "Existing Known Glossary:\nNone yet." in prompt
    # Dummy terms must NOT appear
    assert "用語_01" not in prompt


def test_config_cascade_extractor_filter(tmp_path: Path):
    """Verify configuration precedence: constructor arg > ProjectConfig > .env > default."""
    cfg = ProjectConfig()
    assert cfg.filter_extractor_entities is True
    assert cfg.get_filter_extractor_entities() is True

    # ProjectConfig override
    cfg.filter_extractor_entities = False
    assert cfg.get_filter_extractor_entities() is False

    # Environment variable override
    os.environ["NOVEL_FILTER_EXTRACTOR_ENTITIES"] = "false"
    try:
        cfg2 = ProjectConfig()
        assert cfg2.get_filter_extractor_entities() is False
    finally:
        del os.environ["NOVEL_FILTER_EXTRACTOR_ENTITIES"]


def test_workflow_and_runner_filter_wiring(tmp_path: Path):
    """Verify NovelTranslationWorkflow and BatchRunner pass filter_extractor_entities properly."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Wiring Test", "Japanese", "English")

    # Workflow default
    wf_default = NovelTranslationWorkflow(model_name="mock-model")
    assert wf_default.filter_extractor_entities is True
    assert wf_default.extractor.enable_entity_filtering is True

    # Workflow disabled
    wf_disabled = NovelTranslationWorkflow(model_name="mock-model", filter_extractor_entities=False)
    assert wf_disabled.filter_extractor_entities is False
    assert wf_disabled.extractor.enable_entity_filtering is False

    # BatchRunner with config override
    cfg = repo.load_config()
    cfg.filter_extractor_entities = False
    repo.save_config(cfg)

    runner = BatchRunner(repo, model_name="mock-model")
    assert runner.workflow.filter_extractor_entities is False
    assert runner.workflow.extractor.enable_entity_filtering is False
