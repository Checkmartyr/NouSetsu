"""Unit and integration tests for Google Translate safety fallback and sensitive scene handling."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.metadata import PipelineStage, QualityAudit, StageArtifacts, TranslationStats
from nousetsu.models.state import TranslationState
from nousetsu.utils.chunker import LineChunk
from nousetsu.utils.translation_fallback import (
    is_safety_block_exception,
    resolve_lang_code,
    translate_via_google,
)


def test_resolve_lang_code():
    """Verify language name mapping to ISO codes."""
    assert resolve_lang_code("Japanese") == "ja"
    assert resolve_lang_code("JA") == "ja"
    assert resolve_lang_code("English") == "en"
    assert resolve_lang_code("en") == "en"
    assert resolve_lang_code("Thai") == "th"
    assert resolve_lang_code("th") == "th"
    assert resolve_lang_code("Chinese") == "zh-CN"
    assert resolve_lang_code("Simplified Chinese") == "zh-CN"
    assert resolve_lang_code("Traditional Chinese") == "zh-TW"
    assert resolve_lang_code("zh-tw") == "zh-TW"
    assert resolve_lang_code("Korean") == "ko"
    assert resolve_lang_code("ko") == "ko"
    assert resolve_lang_code("German") == "de"
    assert resolve_lang_code("French") == "fr"
    assert resolve_lang_code("Spanish") == "es"
    assert resolve_lang_code("auto") == "auto"
    assert resolve_lang_code("") == "auto"
    assert resolve_lang_code("unknown_lang") == "unknown_lang"


def test_is_safety_block_exception():
    """Verify detection of various safety block exception patterns."""
    # Positive matches
    assert is_safety_block_exception(RuntimeError("GoogleGenerativeAIError: 400 Bad Request: prohibited_content safety block"))
    assert is_safety_block_exception(Exception("Input blocked due to safety policies"))
    assert is_safety_block_exception(ValueError("Response blocked by safety filters"))
    assert is_safety_block_exception("finish_reason: safety")
    assert is_safety_block_exception("400 Bad Request: prohibited content")
    assert is_safety_block_exception(Exception("400: sensitive content blocked by provider"))
    assert is_safety_block_exception("safety_rating violation")

    # Negative matches (other errors should NOT be treated as safety blocks)
    assert not is_safety_block_exception(RuntimeError("500 Internal Server Error"))
    assert not is_safety_block_exception(TimeoutError("Connection timed out after 30s"))
    assert not is_safety_block_exception(ValueError("Invalid JSON in response"))
    assert not is_safety_block_exception(KeyError("missing key"))


def test_translate_via_google_basic():
    """Verify translate_via_google handles blank text and calls GoogleTranslator."""
    # Blank text
    assert translate_via_google("") == ""
    assert translate_via_google("   ") == "   "

    # Mock GoogleTranslator
    with patch("deep_translator.GoogleTranslator") as mock_gt_cls:
        mock_instance = MagicMock()
        mock_instance.translate.return_value = "Translated English text"
        mock_gt_cls.return_value = mock_instance

        res = translate_via_google("日本語のテキスト", source_lang="Japanese", target_lang="English")

        assert res == "Translated English text"
        mock_gt_cls.assert_called_once_with(source="ja", target="en")
        mock_instance.translate.assert_called_once_with("日本語のテキスト")


def test_translate_via_google_chunking_long_text():
    """Verify translate_via_google splits text exceeding character limits."""
    with patch("deep_translator.GoogleTranslator") as mock_gt_cls:
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = lambda t: f"Translated: {t[:20]}"
        mock_gt_cls.return_value = mock_instance

        # Create a text with lines totaling > 5000 characters
        lines = [f"Line {i}: " + ("x" * 100) for i in range(60)]
        long_text = "\n".join(lines)
        assert len(long_text) > 6000

        res = translate_via_google(long_text, source_lang="Japanese", target_lang="English")

        assert mock_instance.translate.call_count >= 2
        assert "Translated:" in res


def test_drafter_safety_block_google_translate_and_polish_success():
    """Verify Drafter intercepts safety block, calls Google Translate, and polishes result."""
    drafter = ContextAwareDrafterAgent(model_name="mock-model")

    # Make Drafter LLM raise safety block
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("400 Bad Request: prohibited_content")
    drafter.llm = mock_llm

    # Mock Polisher
    mock_polisher = MagicMock()
    mock_polisher.polish.return_value = "Literary polished sensitive scene."
    drafter.polisher = mock_polisher

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")

    with patch("nousetsu.agents.drafter.translate_via_google") as mock_gt:
        mock_gt.return_value = "Raw Google translated draft."

        result = drafter.draft(
            source_text="エッチなシーンのテキスト",
            bible=bible,
            active_characters=[],
            active_glossary=[],
            rolling_summaries=[]
        )

        assert mock_gt.called
        assert mock_polisher.polish.called
        assert result == "Literary polished sensitive scene."
        assert drafter.safety_fallbacks_used == 1


def test_drafter_secondary_safety_block_preserves_raw_google_translate():
    """Verify Drafter returns raw Google Translate draft if Polisher also raises safety block."""
    drafter = ContextAwareDrafterAgent(model_name="mock-model")

    # Drafter LLM raises safety block
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("GoogleGenerativeAIError: 400 Bad Request: prohibited_content")
    drafter.llm = mock_llm

    # Polisher ALSO raises safety block
    mock_polisher = MagicMock()
    mock_polisher.polish.side_effect = RuntimeError("Input blocked due to safety policies")
    drafter.polisher = mock_polisher

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")

    with patch("nousetsu.agents.drafter.translate_via_google") as mock_gt:
        mock_gt.return_value = "Raw Google translated text that must be preserved."

        result = drafter.draft(
            source_text="激しい過激なシーン",
            bible=bible,
            active_characters=[],
            active_glossary=[],
            rolling_summaries=[]
        )

        assert result == "Raw Google translated text that must be preserved."
        assert drafter.safety_fallbacks_used == 1


def test_drafter_chunked_safety_fallback():
    """Verify Drafter handles safety block within chunked drafting cleanly."""
    drafter = ContextAwareDrafterAgent(model_name="mock-model")

    call_count = 0
    def mock_invoke(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("400 Bad Request: prohibited_content")
        resp = MagicMock()
        resp.content = f"Drafted normal chunk {call_count}"
        return resp

    drafter.llm = MagicMock()
    drafter.llm.invoke.side_effect = mock_invoke

    mock_polisher = MagicMock()
    mock_polisher.polish.return_value = "Polished fallback chunk 2"
    drafter.polisher = mock_polisher

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")

    chunk1 = LineChunk(chunk_index=1, total_chunks=2, start_line=1, end_line=3, content="Normal 1")
    chunk2 = LineChunk(chunk_index=2, total_chunks=2, start_line=4, end_line=6, content="Sensitive 2")

    with patch("nousetsu.agents.drafter.translate_via_google") as mock_gt:
        mock_gt.return_value = "Google Translated chunk 2"

        result = drafter.draft_chunked(
            chunks=[chunk1, chunk2],
            bible=bible,
            active_characters=[],
            active_glossary=[],
            rolling_summaries=[]
        )

        assert "Drafted normal chunk 1" in result
        assert "Polished fallback chunk 2" in result
        assert drafter.safety_fallbacks_used == 1


def test_extractor_safety_block_graceful_bypass():
    """Verify EntityExtractorAgent returns empty lists on safety block without crashing."""
    extractor = EntityExtractorAgent(model_name="mock-model")
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("GoogleGenerativeAIError: 400 Bad Request: prohibited_content")
    extractor.llm = mock_llm

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")
    chars, terms, active = extractor.extract("過激な描写のシーン", bible=bible)

    assert chars == []
    assert terms == []
    assert active == []


def test_critic_safety_block_graceful_bypass():
    """Verify CritiqueAgent returns passing score and audit warning on safety block."""
    critic = CritiqueAgent(model_name="mock-model")
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("400 Bad Request: prohibited_content")
    critic.llm = mock_llm

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")
    audit, notes = critic.evaluate(
        source_text="センシティブな原文",
        draft_text="Sensitive draft prose",
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )

    assert audit.passed is True
    assert audit.fidelity_score == 8.5
    assert audit.style_score == 8.0
    assert any("Sensitive scene safety block bypassed during critique" in w for w in audit.warnings)
    assert "Critique bypassed due to provider content filter" in notes


def test_polisher_safety_block_graceful_fallback():
    """Verify PolishingAgent retains draft text when safety block is encountered."""
    polisher = PolishingAgent(model_name="mock-model")
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("GoogleGenerativeAIError: 400 Bad Request: prohibited_content")
    polisher.llm = mock_llm

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")
    result = polisher.polish(
        draft_text="The intimate moment was tender and quiet.",
        critique_notes="Polish rhythm.",
        active_glossary=[],
        bible=bible
    )

    assert result == "The intimate moment was tender and quiet."


def test_workflow_end_to_end_safety_block_handling(tmp_path: Path):
    """Verify end-to-end workflow handles safety block in drafting, runs through critic, and records telemetry."""
    workflow = NovelTranslationWorkflow(
        model_name="mock-model",
        max_review_loops=1
    )

    bible = NovelBible(title="E2E Test", source_language="Japanese", target_language="English")
    state = TranslationState(
        chapter_id="ch_sensitive",
        chapter_num=1,
        source_file=str(tmp_path / "sensitive.txt"),
        output_file=str(tmp_path / "sensitive.md"),
        source_text="第一話：禁断の愛抚。\n熱い吐息が重なる。",
        novel_bible=bible
    )

    # Mock drafter to simulate safety block and Google Translate fallback
    drafter_mock = MagicMock()
    def mock_drafter_call(*args, **kwargs):
        workflow.drafter.safety_fallbacks_used = 1
        return "Chapter 1: Forbidden Embrace.\nWarm breaths intermingled."

    drafter_mock.side_effect = mock_drafter_call
    workflow.drafter.draft = drafter_mock

    # Run workflow
    final_state = workflow.run(state)

    assert final_state.current_stage == PipelineStage.CHRONICLING
    assert final_state.safety_fallbacks_used >= 1
    assert any("Sensitive scene safety block triggered fallback" in w for w in final_state.quality_audit.warnings)
    assert final_state.metadata is not None
    assert final_state.metadata.stats.safety_fallbacks_used >= 1


def test_is_safety_block_exception_harm_categories_and_content_filters():
    """Verify detection of Gemini harm categories, OpenAI/Azure content filters, and finish_reason."""
    assert is_safety_block_exception(RuntimeError("Candidate was blocked due to HARM_CATEGORY_SEXUALLY_EXPLICIT"))
    assert is_safety_block_exception("Blocked by content filter: prompt violated content_policy")
    assert is_safety_block_exception(ValueError("Response blocked due to sensitive content"))
    assert is_safety_block_exception("finish_reason: finishreason.safety")

    # Negative matches
    assert not is_safety_block_exception(RuntimeError("502 Bad Gateway"))
    assert not is_safety_block_exception(RuntimeError("503 Service Unavailable"))
    assert not is_safety_block_exception(RuntimeError("429 ResourceExhausted"))


def test_translate_via_google_long_single_line_without_newlines():
    """Verify translate_via_google splits a 8000-char single line without crashing."""
    with patch("deep_translator.GoogleTranslator") as mock_gt_cls:
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = lambda t: f"EN: {t[:20]}"
        mock_gt_cls.return_value = mock_instance

        # Single continuous line of >7000 chars with Japanese periods
        sentences = ["彼女の柔らかな肌に触れた。" * 20 for _ in range(30)]
        huge_line = "".join(sentences)
        assert len(huge_line) > 6000

        res = translate_via_google(huge_line, source_lang="Japanese", target_lang="English")

        assert mock_instance.translate.call_count >= 2
        for call in mock_instance.translate.call_args_list:
            arg = call[0][0]
            assert len(arg) <= 4500
        assert "EN:" in res


def test_translate_via_google_network_exception_fallback():
    """Verify translate_via_google returns source text without crashing when request fails."""
    with patch("deep_translator.GoogleTranslator") as mock_gt_cls:
        mock_instance = MagicMock()
        mock_instance.translate.side_effect = Exception("Connection reset by peer")
        mock_gt_cls.return_value = mock_instance

        res = translate_via_google("テスト文章", source_lang="Japanese", target_lang="English")
        assert res == "テスト文章"


def test_drafter_fallback_does_not_pass_blocked_source_to_polisher():
    """Verify that drafter safety fallback passes source_text=None to polisher to prevent tripping filters."""
    drafter = ContextAwareDrafterAgent(model_name="mock-model")
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("400 Bad Request: prohibited_content")
    drafter.llm = mock_llm

    mock_polisher = MagicMock()
    mock_polisher.polish.return_value = "Literary polished text"
    drafter.polisher = mock_polisher

    bible = NovelBible(title="Test", source_language="Japanese", target_language="English")

    with patch("nousetsu.agents.drafter.translate_via_google") as mock_gt:
        mock_gt.return_value = "Google Translated English"

        res = drafter.draft(
            source_text="秘密のベッドシーン",
            bible=bible,
            active_characters=[],
            active_glossary=[],
            rolling_summaries=[]
        )

        assert res == "Literary polished text"
        assert mock_polisher.polish.called
        # Verify source_text was passed as None, NOT the blocked Japanese text
        _, kwargs = mock_polisher.polish.call_args
        assert kwargs.get("source_text") is None


def test_workflow_safety_bypass_avoids_wasteful_review_loops(tmp_path: Path):
    """Verify that a critique safety bypass exits immediately to chronicle after pass 1 polish instead of 3 loops."""
    workflow = NovelTranslationWorkflow(
        model_name="mock-model",
        max_review_loops=3,
        quality_threshold=8.5
    )

    state = TranslationState(
        chapter_id="ch_bypass_loop",
        chapter_num=1,
        source_file=str(tmp_path / "ch.txt"),
        source_text="過激な情景",
        draft_text="Sensitive scene draft",
        polished_text="Polished sensitive scene",
        review_iteration=2,  # After pass 1 polish
        quality_audit=QualityAudit(
            fidelity_score=8.5,
            style_score=8.0,
            warnings=["⚠️ Sensitive scene safety block bypassed during critique."],
            passed=True
        )
    )

    route = workflow._route_after_critique(state)
    assert route == "chronicle"


def test_chronicler_safety_block_graceful_fallback():
    """Verify ChroniclerAgent returns default summary and increments safety counter on safety block."""
    chronicler = ChroniclerAgent(model_name="mock-model")
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("400 Bad Request: prohibited_content")
    chronicler.llm = mock_llm

    summary = chronicler.chronicle(
        chapter_num=5,
        translated_text="Explicit intimate scene concluded.",
        chapter_title="Chapter 5"
    )

    assert summary.chapter_num == 5
    assert "concluded" in summary.synopsis
    assert chronicler.safety_fallbacks_used == 1


def test_checkpoint_preserves_safety_fallbacks_used():
    """Verify StageArtifacts serializes safety_fallbacks_used and assemble_metadata populates it."""
    artifacts = StageArtifacts(safety_fallbacks_used=2)
    assert artifacts.safety_fallbacks_used == 2

    chronicler = ChroniclerAgent(model_name="mock-model")
    meta = chronicler.assemble_metadata(
        chapter_id="ch_01",
        chapter_num=1,
        source_file="ch01.txt",
        source_sha256="abc",
        output_file="ch01.md",
        source_text="source",
        final_text="translated",
        model_name="mock-model",
        duration_seconds=1.5,
        quality_audit=QualityAudit(),
        active_characters=[],
        active_glossary=[],
        draft_text="draft",
        critique_notes="notes",
        polished_text="polished",
        safety_fallbacks_used=3
    )

    assert meta.checkpoint.stage_artifacts.safety_fallbacks_used == 3
    assert meta.stats.safety_fallbacks_used == 3

