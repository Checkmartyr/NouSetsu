"""Unit tests verifying code review remediations for vulnerability, performance, and logic errors."""
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.llm import FallbackChatModel, MockNovelLLM
from nousetsu.batch.scanner import ChapterScanner
from nousetsu.models.bible import GlossaryItem, NovelBible
from nousetsu.models.exceptions import BatchStoppedException
from nousetsu.models.metadata import ChapterMetadata, ProjectMetadataDocument
from nousetsu.storage.repository import NovelRepository, atomic_write_file, atomic_write_json, atomic_write_yaml
from nousetsu.utils.chunker import LineSemanticChunker
from nousetsu.utils.rate_limiter import SlidingWindowRateLimiter


def test_atomic_file_writes(tmp_path: Path):
    """Verify atomic file writes create files cleanly and atomically replace them."""
    test_file = tmp_path / "sub" / "data.json"
    data = {"novel": "Ascendance of a Bookworm", "chapters": 100}
    atomic_write_json(test_file, data)

    assert test_file.exists()
    loaded = json.loads(test_file.read_text(encoding="utf-8"))
    assert loaded == data

    # Overwrite atomically
    updated_data = {"novel": "Ascendance of a Bookworm", "chapters": 101}
    atomic_write_json(test_file, updated_data)
    loaded_again = json.loads(test_file.read_text(encoding="utf-8"))
    assert loaded_again["chapters"] == 101


def test_atomic_metadata_save(tmp_path: Path):
    """Verify save_project_metadata_doc uses atomic file replacement."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Atomic Test", "Japanese", "English")

    doc = ProjectMetadataDocument(project_id="test_atomic")
    out_file = tmp_path / "translated_chapters" / "0001.md"
    meta = ChapterMetadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file=str(tmp_path / "raw_chapters" / "0001.txt"),
        source_sha256="fake_sha",
        output_file=str(out_file)
    )
    doc.chapters["translated_chapters/0001"] = meta
    repo.save_project_metadata_doc(doc)

    loaded_doc = repo.load_project_metadata_doc()
    assert "translated_chapters/0001" in loaded_doc.chapters
    assert loaded_doc.chapters["translated_chapters/0001"].chapter_num == 1


def test_scanner_chapter_number_extraction(tmp_path: Path):
    """Verify ChapterScanner correctly extracts chapter numbers and does not confuse volume prefixes."""
    repo = NovelRepository(tmp_path)
    scanner = ChapterScanner(repo)

    # Volume and chapter composite filenames
    assert scanner.extract_chapter_num(Path("vol1_chapter05.txt"), 99) == 5
    assert scanner.extract_chapter_num(Path("novel_v2_ch10.txt"), 99) == 10
    assert scanner.extract_chapter_num(Path("volume_02_ch_003.txt"), 99) == 3
    assert scanner.extract_chapter_num(Path("Vol_04_ch48_battle.md"), 99) == 48

    # Standard chapter names
    assert scanner.extract_chapter_num(Path("0001.txt"), 99) == 1
    assert scanner.extract_chapter_num(Path("042.txt"), 99) == 42
    assert scanner.extract_chapter_num(Path("chapter_99.md"), 99) == 99
    assert scanner.extract_chapter_num(Path("第48話.txt"), 99) == 48

    # Fallback to default index on non-numeric stem
    assert scanner.extract_chapter_num(Path("prologue.txt"), 99) == 99


def test_case_insensitive_glossary_term_lookup():
    """Verify NovelBible.find_term matches case-insensitively to prevent duplicates."""
    bible = NovelBible(
        title="Test Novel",
        source_language="Japanese",
        target_language="English",
        glossary=[
            GlossaryItem(source="Mana", target="Mana", category="term"),
            GlossaryItem(source="myne", target="Myne", category="character")
        ]
    )

    assert bible.find_term("mana") is not None
    assert bible.find_term("MANA") is not None
    assert bible.find_term("Myne") is not None
    assert bible.find_term("MYNE") is not None
    assert bible.find_term("Nonexistent") is None


def test_fallback_chat_model_does_not_swallow_cancellation():
    """Verify FallbackChatModel immediately propagates BatchStoppedException without calling fallback."""
    primary_mock = MockNovelLLM()
    fallback_mock = MockNovelLLM()

    primary_mock._generate = MagicMock(side_effect=BatchStoppedException("User stopped batch"))
    fallback_mock._generate = MagicMock()

    model = FallbackChatModel(
        primary=primary_mock,
        fallback=fallback_mock,
        primary_model_name="primary-test",
        fallback_model_name="fallback-test"
    )

    with pytest.raises(BatchStoppedException):
        model.invoke("Translate this text")

    # Fallback model should NEVER be called when BatchStoppedException occurs
    assert fallback_mock._generate.call_count == 0


def test_critique_json_parse_failure_assigns_conservative_failing_score():
    """Verify CritiqueAgent assigns failing score on completely broken JSON rather than 10.0/10 bypass."""
    agent = CritiqueAgent(model_name="mock-model")

    # Return completely malformed non-JSON output
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="I cannot provide a JSON response because the text is strange.")
    agent.llm = mock_llm

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")
    audit, notes = agent.evaluate(
        source_text="テスト",
        draft_text="Test",
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )

    # Conservative failing scores should be assigned (passed = False)
    assert not audit.passed
    assert audit.fidelity_score == 6.0
    assert audit.style_score == 6.0
    assert any("conservative" in w.lower() for w in audit.warnings)


def test_critique_regex_recovery_on_semi_structured_text():
    """Verify CritiqueAgent recovers scores via regex if LLM outputs markdown text with embedded scores."""
    agent = CritiqueAgent(model_name="mock-model")

    # Semi-structured response with embedded scores but broken JSON brackets
    raw_text = (
        "Here is my analysis:\n"
        "fidelity_score: 8.8\n"
        "style_score: 8.5\n"
        "glossary_compliance_pct: 100.0\n"
        "critique_notes: 'Prose is mostly clean.'\n"
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=raw_text)
    agent.llm = mock_llm

    bible = NovelBible(source_language="Japanese", target_language="English")
    audit, notes = agent.evaluate(
        source_text="Some text",
        draft_text="Some translation",
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )

    assert audit.fidelity_score == 8.8
    assert audit.style_score == 8.5
    assert audit.passed is True
    assert any("regex fallback" in w for w in audit.warnings)


def test_chunker_double_quote_nesting_no_drift():
    """Verify LineSemanticChunker does not drift quote_depth on multi-line western double quotes."""
    chunker = LineSemanticChunker(threshold_lines=5, target_chunk_lines=3, boundary_window=2)

    # Line 1 opens double quote, Line 2 closes double quote
    delta1, in_dq1 = chunker._quote_delta('She said, "Hello world,', in_double_quote=False)
    assert in_dq1 is True
    assert delta1 == 1

    delta2, in_dq2 = chunker._quote_delta('and how are you today?"', in_double_quote=in_dq1)
    assert in_dq2 is False
    assert delta2 == -1  # Net change brings total back to 0


def test_rate_limiter_oversized_token_request():
    """Verify SlidingWindowRateLimiter handles requests where estimated_tokens > max_tpm without deadlocking."""
    limiter = SlidingWindowRateLimiter(max_tpm=1000, max_rpm=10, window_seconds=1.0)

    # Insert an existing record
    now = limiter.acquire(estimated_tokens=500)
    assert len(limiter.token_records) == 1

    # Now request 1500 tokens (which exceeds max_tpm 1000)
    # It must wait for window to clear rather than returning 0.0s immediately
    wait_time = limiter.acquire(estimated_tokens=1500)
    assert wait_time > 0.0
