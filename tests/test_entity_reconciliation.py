"""Tests for Post-Polish Term and Character Reconciliation via Chronicler Agent (Stage 5)."""
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.llm import MockNovelLLM, invoke_structured
from nousetsu.batch.runner import BatchRunner
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.config import ProjectConfig
from nousetsu.models.schemas import ChroniclerResult
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository
from langchain_core.messages import HumanMessage, SystemMessage


def test_chronicler_result_reconciled_entities_flat_and_nested():
    """Verify ChroniclerResult correctly deserializes reconciled_characters and reconciled_terms."""
    flat_json = (
        '{\n'
        '  "chapter_num": 1,\n'
        '  "title": "Chapter 1",\n'
        '  "synopsis": "Hero acquires a new blade.",\n'
        '  "key_events": ["Sword acquired"],\n'
        '  "character_state_changes": [],\n'
        '  "reconciled_characters": [\n'
        '    {\n'
        '      "name": "Kaelen Voss",\n'
        '      "original_name": "カエル",\n'
        '      "aliases": ["Shadow Walker", "Kael"],\n'
        '      "role": "protagonist",\n'
        '      "description": "Exiled shadow mage",\n'
        '      "gender": "male"\n'
        '    }\n'
        '  ],\n'
        '  "reconciled_terms": [\n'
        '    {\n'
        '      "source": "蒼雷剣",\n'
        '      "target": "Azure Thunder Blade",\n'
        '      "category": "weapon",\n'
        '      "notes": "Upgraded from Cyan Lightning Sword"\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    mock_llm = MockNovelLLM(responses=[flat_json])
    parsed, _, err = invoke_structured(
        mock_llm,
        ChroniclerResult,
        [SystemMessage(content="Summarize"), HumanMessage(content="Text")]
    )
    assert err is None
    assert parsed is not None
    assert len(parsed.reconciled_characters) == 1
    assert parsed.reconciled_characters[0].name == "Kaelen Voss"
    assert parsed.reconciled_characters[0].aliases == ["Shadow Walker", "Kael"]
    assert len(parsed.reconciled_terms) == 1
    assert parsed.reconciled_terms[0].source == "蒼雷剣"
    assert parsed.reconciled_terms[0].target == "Azure Thunder Blade"

    # Verify to_chapter_summary propagation
    summary = parsed.to_chapter_summary(default_chapter_num=1, default_title="Chapter 1")
    assert len(summary.reconciled_characters) == 1
    assert summary.reconciled_characters[0].name == "Kaelen Voss"
    assert len(summary.reconciled_terms) == 1
    assert summary.reconciled_terms[0].target == "Azure Thunder Blade"


def test_chronicler_agent_injects_provisional_entities():
    """Verify ChroniclerAgent injects Stage 1 provisional entities into the system prompt."""
    agent = ChroniclerAgent(model_name="mock-model")

    provisional_chars = [
        CharacterProfile(name="Kael", original_name="カエル", role="protagonist", aliases=["Boy"])
    ]
    provisional_terms = [
        GlossaryItem(source="蒼雷剣", target="Cyan Lightning Sword", category="weapon", notes="Provisional")
    ]

    captured_messages = []
    def fake_invoke(messages):
        captured_messages.extend(messages)
        return MagicMock(content=(
            '{\n'
            '  "chapter_num": 1,\n'
            '  "title": "Chapter 1",\n'
            '  "synopsis": "Kael wields the blade.",\n'
            '  "key_events": ["Wielded blade"],\n'
            '  "character_state_changes": [],\n'
            '  "reconciled_characters": [\n'
            '    {\n'
            '      "name": "Kaelen Voss",\n'
            '      "original_name": "カエル",\n'
            '      "aliases": ["Kael", "Boy"],\n'
            '      "role": "protagonist"\n'
            '    }\n'
            '  ],\n'
            '  "reconciled_terms": [\n'
            '    {\n'
            '      "source": "蒼雷剣",\n'
            '      "target": "Azure Thunder Blade",\n'
            '      "category": "weapon",\n'
            '      "notes": "Polished refinement"\n'
            '    }\n'
            '  ]\n'
            '}'
        ))

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke
    agent.llm = mock_llm

    summary = agent.chronicle(
        chapter_num=1,
        chapter_title="Chapter 1",
        translated_text="Kaelen Voss raised the Azure Thunder Blade high.",
        extracted_characters=provisional_chars,
        extracted_terms=provisional_terms
    )

    assert summary is not None
    assert len(captured_messages) == 2
    sys_prompt = captured_messages[0].content
    assert "Stage 1 Provisional Entities for Reconciliation:" in sys_prompt
    assert "Kael" in sys_prompt
    assert "蒼雷剣 -> Cyan Lightning Sword [weapon]" in sys_prompt

    # Verify recorded reconciled entities
    assert len(agent.last_reconciled_characters) == 1
    assert agent.last_reconciled_characters[0].name == "Kaelen Voss"
    assert len(agent.last_reconciled_terms) == 1
    assert agent.last_reconciled_terms[0].target == "Azure Thunder Blade"


def test_chronicler_agent_assemble_metadata_preserves_reconciled():
    """Verify assemble_metadata records reconciled_characters and reconciled_terms in StageArtifacts."""
    agent = ChroniclerAgent(model_name="mock-model")

    provisional_chars = [CharacterProfile(name="Kael", original_name="カエル", role="protagonist")]
    provisional_terms = [GlossaryItem(source="蒼雷剣", target="Cyan Lightning Sword")]
    reconciled_chars = [CharacterProfile(name="Kaelen Voss", original_name="カエル", aliases=["Kael"], role="protagonist")]
    reconciled_terms = [GlossaryItem(source="蒼雷剣", target="Azure Thunder Blade")]

    from nousetsu.models.metadata import QualityAudit
    meta = agent.assemble_metadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="raw/0001.txt",
        source_sha256="abc",
        output_file="trans/0001.md",
        source_text="raw",
        final_text="polished",
        model_name="mock-model",
        duration_seconds=5.0,
        quality_audit=QualityAudit(fidelity_score=9.0, style_score=9.0, passed=True),
        active_characters=[],
        active_glossary=[],
        draft_text="draft",
        critique_notes="notes",
        polished_text="polished",
        extracted_characters=provisional_chars,
        extracted_terms=provisional_terms,
        reconciled_characters=reconciled_chars,
        reconciled_terms=reconciled_terms
    )

    artifacts = meta.checkpoint.stage_artifacts
    assert len(artifacts.extracted_characters) == 1
    assert artifacts.extracted_characters[0].name == "Kael"
    assert len(artifacts.extracted_terms) == 1
    assert artifacts.extracted_terms[0].target == "Cyan Lightning Sword"

    assert len(artifacts.reconciled_characters) == 1
    assert artifacts.reconciled_characters[0].name == "Kaelen Voss"
    assert len(artifacts.reconciled_terms) == 1
    assert artifacts.reconciled_terms[0].target == "Azure Thunder Blade"


def test_workflow_reconciliation_integration(tmp_path: Path):
    """Verify NovelTranslationWorkflow forwards extracted entities and receives reconciled entities."""
    wf = NovelTranslationWorkflow(
        model_name="mock-model",
        enable_post_polish_reconciliation=True
    )

    state = TranslationState(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="0001.txt",
        source_sha256="hash123",
        output_file="0001.md",
        source_text="蒼雷剣を持つカエル。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English")
    )

    final_state = wf.run(state)
    assert final_state.current_stage.value == "chronicling"
    assert isinstance(final_state.reconciled_characters, list)
    assert isinstance(final_state.reconciled_terms, list)
    assert final_state.metadata is not None
    assert hasattr(final_state.metadata.checkpoint.stage_artifacts, "reconciled_terms")


def test_batch_runner_commits_reconciled_entities(tmp_path: Path):
    """Verify BatchRunner writes reconciled entities to NovelBible rather than provisional ones."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project(title="Reconciliation Test", source_lang="Japanese", target_lang="English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    raw_file = input_dir / "0001.txt"
    raw_file.write_text("カエルは蒼雷剣を抜いた。", encoding="utf-8")

    runner = BatchRunner(
        repository=repo,
        model_name="mock-model",
        auto_update_bible=True,
        enable_post_polish_reconciliation=True
    )

    # Custom mock workflow returning reconciled entities
    reconciled_char = CharacterProfile(name="Kaelen Voss", original_name="カエル", aliases=["Kael"], role="protagonist")
    reconciled_term = GlossaryItem(source="蒼雷剣", target="Azure Thunder Blade", category="weapon")

    def mock_workflow_run(initial_state, stage_callback=None, stop_event=None):
        initial_state.extracted_characters = [CharacterProfile(name="Kael", original_name="カエル", role="protagonist")]
        initial_state.extracted_terms = [GlossaryItem(source="蒼雷剣", target="Cyan Lightning Sword")]
        initial_state.reconciled_characters = [reconciled_char]
        initial_state.reconciled_terms = [reconciled_term]
        initial_state.polished_text = "Kaelen Voss drew the Azure Thunder Blade."
        initial_state.best_polished_text = initial_state.polished_text

        from nousetsu.models.schemas import ChroniclerResult
        from nousetsu.models.metadata import QualityAudit
        res = ChroniclerResult(
            chapter_num=1,
            title="Chapter 1",
            synopsis="Kaelen drew blade.",
            key_events=["Drew blade"],
            character_state_changes=[],
            reconciled_characters=[reconciled_char],
            reconciled_terms=[reconciled_term]
        )
        initial_state.new_chapter_summary = res.to_chapter_summary(1, "Chapter 1")
        initial_state.metadata = runner.workflow.chronicler.assemble_metadata(
            chapter_id="chapter_0001",
            chapter_num=1,
            source_file=str(initial_state.source_file),
            source_sha256="test_sha",
            output_file=str(initial_state.output_file),
            source_text=initial_state.source_text,
            final_text=initial_state.polished_text,
            model_name="mock-model",
            duration_seconds=1.0,
            quality_audit=QualityAudit(fidelity_score=9.0, style_score=9.0, passed=True),
            active_characters=[],
            active_glossary=[],
            draft_text="draft",
            critique_notes="notes",
            polished_text=initial_state.polished_text,
            extracted_characters=initial_state.extracted_characters,
            extracted_terms=initial_state.extracted_terms,
            reconciled_characters=initial_state.reconciled_characters,
            reconciled_terms=initial_state.reconciled_terms
        )
        return initial_state

    runner.workflow.run = mock_workflow_run

    results = runner.run_batch(input_dir=input_dir, output_dir=output_dir)
    assert len(results) == 1

    # Inspect Novel Bible
    bible = repo.load_bible()
    char_names = [c.name for c in bible.characters]
    assert "Kaelen Voss" in char_names
    assert "Kael" not in char_names  # Reconciled canonical name was saved

    term_translations = {t.source: t.target for t in bible.glossary}
    assert term_translations.get("蒼雷剣") == "Azure Thunder Blade"  # Reconciled translation was saved


def test_config_post_polish_reconciliation_cascade(monkeypatch):
    """Verify ProjectConfig.get_post_polish_reconciliation honors config override, env, and default."""
    cfg = ProjectConfig()
    assert cfg.get_post_polish_reconciliation() is True

    # Config override
    cfg.enable_post_polish_reconciliation = False
    assert cfg.get_post_polish_reconciliation() is False

    # Env override when config is None
    cfg.enable_post_polish_reconciliation = None
    monkeypatch.setenv("NOVEL_POST_POLISH_RECONCILIATION", "false")
    assert cfg.get_post_polish_reconciliation() is False

    monkeypatch.setenv("NOVEL_POST_POLISH_RECONCILIATION", "true")
    assert cfg.get_post_polish_reconciliation() is True


def test_update_bible_memory_merges_pronouns_and_relational(tmp_path: Path):
    """Verify update_bible_memory merges general and relational pronouns into NovelBible."""
    repo = NovelRepository(tmp_path)
    initial_char = CharacterProfile(
        name="Ifia",
        original_name="Ifia",
        gender="female",
        role="protagonist",
        source_pronoun="she/her",
        target_pronoun="เธอ"
    )
    repo.save_bible(NovelBible(characters=[initial_char]))

    # Reconciled character brings updated target pronouns and new relational pronouns
    from nousetsu.models.bible import CharacterPronouns
    reconciled_char = CharacterProfile(
        name="Ifia",
        original_name="Ifia",
        pronouns=CharacterPronouns(
            source="she/her, I",
            target="เธอ, ฉัน",
            relational={"Amelia Barlen": "หนู/พี่"}
        )
    )

    repo.update_bible_memory(
        new_characters=[reconciled_char],
        new_terms=[],
        summary=None
    )

    updated_bible = repo.load_bible()
    char = updated_bible.find_character("Ifia")
    assert char is not None
    assert char.pronouns.source == "she/her, I"
    assert char.pronouns.target == "เธอ, ฉัน"
    assert char.pronouns.relational == {"Amelia Barlen": "หนู/พี่"}


