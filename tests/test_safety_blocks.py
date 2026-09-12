"""Unit tests for Google AI safety block mitigations and pipeline robustness."""
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from rich.console import Console

from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.agents.llm import MockNovelLLM
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.batch.runner import BatchRunner
from nousetsu.batch.scanner import ChapterScanner
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible, StyleGuide
from nousetsu.models.metadata import ChapterMetadata, CheckpointData, PipelineStage, QualityAudit, StageArtifacts, StageStatus
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository
from nousetsu.utils.chunker import LineChunk, LineSemanticChunker


def test_extractor_task_framing():
    """Verify EntityExtractorAgent uses explicit analytical framing instead of bare Chapter Text:."""
    extractor = EntityExtractorAgent(model_name="mock-model")
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"new_characters": [], "new_terms": [], "active_terms_in_chapter": []}'
    mock_llm.invoke.return_value = mock_response
    extractor.llm = mock_llm

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")
    extractor.extract("Chapter text content here", bible=bible)

    assert mock_llm.invoke.called
    call_args = mock_llm.invoke.call_args[0][0]
    human_msg = call_args[1].content

    # Must contain analytical framing and not bare Chapter Text:
    assert "Extract fictional characters, factions, and world terminology from this novel excerpt:" in human_msg
    assert not human_msg.startswith("Chapter Text:\n")


def test_extractor_chunking_and_deduplication():
    """Verify EntityExtractorAgent chunks long text, accumulates usage, and deduplicates items."""
    extractor = EntityExtractorAgent(model_name="mock-model")

    chunk1 = LineChunk(chunk_index=1, total_chunks=2, start_line=1, end_line=3, content="Line 1\nLine 2\nLine 3")
    chunk2 = LineChunk(chunk_index=2, total_chunks=2, start_line=4, end_line=6, content="Line 4\nLine 5\nLine 6")

    # Mock _extract_single_text to return overlapping characters and terms
    call_count = 0
    def mock_single(text, bible, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return (
                [CharacterProfile(name="Alice", original_name="アリス", role="hero")],
                [GlossaryItem(source="魔導炉", target="mana furnace", category="item")],
                ["魔導炉"]
            )
        else:
            return (
                [
                    CharacterProfile(name="Alice", original_name="アリス", role="hero"),
                    CharacterProfile(name="Bob", original_name="ボブ", role="ally")
                ],
                [
                    GlossaryItem(source="魔導炉", target="mana furnace", category="item"),
                    GlossaryItem(source="魔石", target="magic stone", category="item")
                ],
                ["魔導炉", "魔石"]
            )

    extractor._extract_single_text = MagicMock(side_effect=mock_single)

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")
    chars, terms, active = extractor.extract(
        source_text="Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6",
        bible=bible,
        chunks=[chunk1, chunk2]
    )

    assert len(chars) == 2
    assert {c.name for c in chars} == {"Alice", "Bob"}
    assert len(terms) == 2
    assert {t.source for t in terms} == {"魔導炉", "魔石"}
    assert active == ["魔導炉", "魔石"]
    assert extractor._extract_single_text.call_count == 2


def test_critic_task_framing_and_paired_chunking():
    """Verify CritiqueAgent uses analytical task framing and handles paired chunks."""
    chunker = LineSemanticChunker(threshold_lines=5, target_chunk_lines=3)
    critic = CritiqueAgent(model_name="mock-model", chunker=chunker)

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"fidelity_score": 9.5, "style_score": 9.2, "glossary_compliance_pct": 100.0, "warnings": [], "critique_notes": "Clean prose."}'
    mock_llm.invoke.return_value = mock_response
    critic.llm = mock_llm

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")
    source_text = "\n".join([f"Source line {i}" for i in range(1, 10)])
    draft_text = "\n".join([f"Draft line {i}" for i in range(1, 10)])

    audit, notes = critic.evaluate(
        source_text=source_text,
        draft_text=draft_text,
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )

    assert mock_llm.invoke.called
    call_args = mock_llm.invoke.call_args[0][0]
    human_msg = call_args[1].content
    assert "Please evaluate the fidelity, style, and terminology consistency of this fictional translation excerpt" in human_msg
    assert audit.fidelity_score == 9.5
    assert audit.style_score == 9.2


def test_polisher_sliced_source_and_condensed_thai_activation(tmp_path: Path):
    """Verify polisher chunking activates on condensed Thai text and slices source lines without leaks."""
    workflow = NovelTranslationWorkflow(
        model_name="mock-model",
        chunk_threshold_lines=10,
        target_chunk_lines=6
    )

    # 20 source lines (exceeds threshold 10)
    source_lines = [f"Japanese source line {i}." for i in range(1, 21)]
    source_text = "\n".join(source_lines)

    # 12 condensed Thai lines (exceeds condensed threshold max(25, 10//2) = 25? No, but source_lines > threshold!)
    draft_lines = [f"Thai draft line {i}." for i in range(1, 13)]
    draft_text = "\n".join(draft_lines)

    bible = NovelBible(title="Thai Test", source_language="Japanese", target_language="Thai")
    state = TranslationState(
        chapter_id="ch_01",
        chapter_num=1,
        source_file=str(tmp_path / "ch01.txt"),
        source_text=source_text,
        draft_text=draft_text,
        novel_bible=bible
    )

    polisher_mock = MagicMock(return_value="Polished Thai prose.")
    workflow.polisher.polish = polisher_mock

    res = workflow._polish_step(state)

    assert polisher_mock.called
    kwargs = polisher_mock.call_args[1]
    draft_chunks = kwargs.get("draft_chunks")
    assert draft_chunks is not None
    assert len(draft_chunks) > 1

    # Verify that each draft chunk has sliced source_content that is NOT the entire 20 lines
    for chunk in draft_chunks:
        assert chunk.source_content is not None
        assert len(chunk.source_content) > 0
        assert chunk.source_content != source_text
        assert len(chunk.source_content.splitlines()) < len(source_lines)


def test_polisher_polish_chunked_slices_source_fallback():
    """Verify polisher.polish_chunked slices source_text proportionally if source_content is missing."""
    polisher = PolishingAgent(model_name="mock-model")
    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")

    chunks = [
        LineChunk(chunk_index=1, total_chunks=2, start_line=1, end_line=5, content="Draft 1\nDraft 2"),
        LineChunk(chunk_index=2, total_chunks=2, start_line=6, end_line=10, content="Draft 3\nDraft 4"),
    ]
    # Deliberately do not set source_content on chunks
    for c in chunks:
        c.source_content = None

    source_text = "\n".join([f"Source line {i}" for i in range(1, 20)])
    captured_sources = []

    def mock_single(chunk_draft, preceding_context, critique_notes, active_glossary, bible, genre=None, source_text=None, **kwargs):
        captured_sources.append(source_text)
        return "Polished chunk"

    polisher._polish_single_chunk = MagicMock(side_effect=mock_single)

    res = polisher.polish_chunked(
        draft_chunks=chunks,
        critique_notes="Polish well",
        active_glossary=[],
        bible=bible,
        source_text=source_text
    )

    assert len(captured_sources) == 2
    # Neither should equal the full unchunked source text
    assert captured_sources[0] != source_text
    assert captured_sources[1] != source_text
    assert len(captured_sources[0].splitlines()) < 20
    assert len(captured_sources[1].splitlines()) < 20


def test_workflow_fallback_model_propagation():
    """Verify NovelTranslationWorkflow propagates fallback_model to all sub-agents."""
    workflow = NovelTranslationWorkflow(
        model_name="mock-primary",
        fallback_model="mock-fallback-target"
    )

    assert workflow.fallback_model == "mock-fallback-target"
    assert workflow.extractor.fallback_model == "mock-fallback-target"
    assert workflow.drafter.fallback_model == "mock-fallback-target"
    assert workflow.critic.fallback_model == "mock-fallback-target"
    assert workflow.polisher.fallback_model == "mock-fallback-target"
    assert workflow.chronicler.fallback_model == "mock-fallback-target"


def test_checkpoint_preservation_on_exception_and_resumption(tmp_path: Path):
    """Verify that when an exception occurs, stage artifacts and last_completed_stage are preserved and resumed."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Safety Resumption Novel", "Japanese", "English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    raw_file = input_dir / "ch_01.txt"
    raw_file.write_text("第一章：危険な試練。\n少年は立ち向かった。", encoding="utf-8")

    console = Console(record=True)
    runner = BatchRunner(repo, model_name="mock-model", console=console)

    # Simulate workflow execution where Extraction and Drafting succeeded, but Critique fails with safety block
    def failing_workflow_run(initial_state, stage_callback=None, stop_event=None):
        # Populate intermediate artifacts into workflow
        runner.workflow.current_stage = PipelineStage.CRITIQUE
        initial_state.extracted_characters = [CharacterProfile(name="Hero", original_name="主人公")]
        initial_state.extracted_terms = [GlossaryItem(source="魔導", target="sorcery")]
        initial_state.draft_text = "Chapter 1: The Perilous Trial.\nThe boy stood firm."
        runner.workflow.last_state = initial_state
        raise RuntimeError("GoogleGenerativeAIError: 400 Bad Request: prohibited_content safety block")

    runner.workflow.run = MagicMock(side_effect=failing_workflow_run)

    results = runner.run_batch(input_dir=input_dir, output_dir=output_dir)

    assert len(results) == 0  # No completed chapters

    # Verify failed checkpoint saved into metadata.json
    all_meta = repo.load_all_metadata()
    assert "ch_01" in all_meta
    failed_meta = all_meta["ch_01"]

    assert failed_meta.checkpoint.status == StageStatus.FAILED
    assert failed_meta.checkpoint.failed_stage == PipelineStage.CRITIQUE
    # Completed stage should be DRAFTING!
    assert failed_meta.checkpoint.last_completed_stage == PipelineStage.DRAFTING
    # Stage artifacts must be preserved!
    artifacts = failed_meta.checkpoint.stage_artifacts
    assert artifacts.draft_text == "Chapter 1: The Perilous Trial.\nThe boy stood firm."
    assert len(artifacts.extracted_characters) == 1
    assert artifacts.extracted_characters[0].name == "Hero"
    assert len(artifacts.extracted_terms) == 1
    assert artifacts.extracted_terms[0].source == "魔導"
    assert failed_meta.checkpoint.is_resumable() is True

    # Scanner should flag chapter as needing resumption from drafting stage
    scanner = ChapterScanner(repo)
    tasks = scanner.scan_directory(input_dir, output_dir)
    assert len(tasks) == 1
    assert tasks[0].needs_resume is True
    assert tasks[0].resume_stage == PipelineStage.DRAFTING

    # Now simulate a second run where the issue is mitigated and workflow completes
    def succeeding_workflow_run(initial_state, stage_callback=None, stop_event=None):
        # Verify initial_state received the resumed artifacts!
        assert initial_state.draft_text == "Chapter 1: The Perilous Trial.\nThe boy stood firm."
        assert len(initial_state.extracted_characters) == 1
        assert len(initial_state.extracted_terms) == 1

        initial_state.polished_text = "Chapter 1: The Perilous Trial.\nThe boy stood firm against the darkness."
        initial_state.quality_audit = QualityAudit(fidelity_score=9.2, style_score=9.0)
        initial_state.metadata = ChapterMetadata(
            chapter_id=initial_state.chapter_id,
            chapter_num=initial_state.chapter_num,
            source_file=initial_state.source_file,
            source_sha256=initial_state.source_sha256,
            output_file=initial_state.output_file,
            model="mock-model",
            checkpoint=CheckpointData(status=StageStatus.COMPLETED, last_completed_stage=PipelineStage.CHRONICLING)
        )
        return initial_state

    runner.workflow.run = MagicMock(side_effect=succeeding_workflow_run)
    resumed_results = runner.run_batch(input_dir=input_dir, output_dir=output_dir)

    assert len(resumed_results) == 1
    assert resumed_results[0].checkpoint.status == StageStatus.COMPLETED
    assert (output_dir / "ch_01.md").exists()
