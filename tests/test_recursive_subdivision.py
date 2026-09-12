"""Unit and integration tests for recursive subdivision (bisection) of sensitive scenes."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.config import ProjectConfig
from nousetsu.models.metadata import PipelineStage, QualityAudit, StageArtifacts, TranslationStats
from nousetsu.models.state import TranslationState
from nousetsu.utils.chunker import LineChunk
from nousetsu.utils.translation_fallback import bisect_text, can_subdivide_text


class TestBisectionUtility:
    """Tests for bisect_text and can_subdivide_text functions."""

    def test_bisect_empty_and_single_char(self):
        assert bisect_text("") == ("", "")
        assert bisect_text("a") == ("a", "")
        assert bisect_text("   ") == ("   ", "")

    def test_bisect_priority1_paragraph_break(self):
        text = "Paragraph 1\nLine 1b\n\nParagraph 2\nLine 2b\n\nParagraph 3\nLine 3b"
        left, right = bisect_text(text)
        assert "Paragraph 1" in left
        assert "Paragraph 3" in right
        assert left != right

    def test_bisect_priority2_line_break(self):
        lines = [f"Line {i}" for i in range(1, 11)]
        text = "\n".join(lines)
        left, right = bisect_text(text)
        assert left == "\n".join(lines[:5])
        assert right == "\n".join(lines[5:])

    def test_bisect_priority3_cjk_sentence_boundary(self):
        text = "吾輩は猫である。名前はまだ無い。どこで生れたかとんと見当がつかぬ。"
        left, right = bisect_text(text)
        assert left.endswith("。")
        assert right.startswith("どこで") or right.startswith("名前は")
        assert f"{left}{right}" == text.replace(" ", "")

    def test_bisect_priority3_latin_sentence_boundary(self):
        text = "Alice was beginning to get very tired of sitting by her sister on the bank. Once or twice she had peeped into the book her sister was reading."
        left, right = bisect_text(text)
        assert left.endswith(".")
        assert right.startswith("Once")

    def test_bisect_priority4_unpunctuated_midpoint(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        left, right = bisect_text(text)
        assert left == "abcdefghijklm"
        assert right == "nopqrstuvwxyz"

    def test_can_subdivide_text_thresholds(self):
        assert can_subdivide_text("") is False
        assert can_subdivide_text("   ") is False
        assert can_subdivide_text("short text", min_lines=8, min_chars=200) is False

        # 10 lines, 100 chars -> satisfies min_lines=8
        ten_lines = "\n".join([f"Line {i}" for i in range(10)])
        assert can_subdivide_text(ten_lines, min_lines=8, min_chars=200) is True

        # 1 line, 250 chars -> satisfies min_chars=200
        long_line = "A" * 250
        assert can_subdivide_text(long_line, min_lines=8, min_chars=200) is True

        # 4 lines, 50 chars -> fails both
        short_lines = "\n".join([f"Line {i}" for i in range(4)])
        assert can_subdivide_text(short_lines, min_lines=8, min_chars=200) is False


class TestDrafterRecursiveSubdivision:
    """Tests for ContextAwareDrafterAgent recursive bisection on safety blocks."""

    def test_drafter_recursive_subdivision_partial_block(self):
        """Simulate 20-line chunk where first half is clean and second half triggers safety block."""
        drafter = ContextAwareDrafterAgent(
            model_name="mock-model",
            subdivision_min_lines=4,
            subdivision_max_depth=3,
        )

        bible = NovelBible(title="Test Novel", source_language="Japanese", target_language="English")

        clean_lines = [f"Clean safe dialogue line {i}." for i in range(1, 11)]
        sensitive_lines = [f"Explicit sensitive action line {i}." for i in range(1, 11)]
        full_source = "\n".join(clean_lines + sensitive_lines)

        def mock_llm_invoke(messages):
            prompt = messages[1].content
            # If the prompt contains any sensitive lines, raise safety block
            if "Explicit sensitive action" in prompt:
                raise RuntimeError("GoogleGenerativeAIError: 400 Bad Request: prohibited_content safety block")
            resp = MagicMock()
            resp.content = "Literary English translation of clean safe lines."
            return resp

        drafter.llm = MagicMock()
        drafter.llm.invoke.side_effect = mock_llm_invoke

        mock_polisher = MagicMock()
        mock_polisher.polish.return_value = "Polished sensitive English prose."
        drafter.polisher = mock_polisher

        with patch("nousetsu.agents.drafter.translate_via_google") as mock_gt:
            mock_gt.return_value = "Google Translated raw sensitive snippet."

            draft = drafter.draft(
                source_text=full_source,
                bible=bible,
                active_characters=[],
                active_glossary=[],
                rolling_summaries=[]
            )

            # Drafter should have subdivided
            assert drafter.subdivisions_count >= 1
            # Clean part must be translated by LLM
            assert "Literary English translation of clean safe lines." in draft
            # Sensitive part must have triggered fallback
            assert "Polished sensitive English prose." in draft
            assert mock_gt.called
            assert drafter.safety_fallbacks_used >= 1

    def test_drafter_max_depth_termination(self):
        """Verify that recursion stops at max_depth and invokes fallback for entire remaining piece."""
        drafter = ContextAwareDrafterAgent(
            model_name="mock-model",
            subdivision_min_lines=2,
            subdivision_max_depth=2,
        )

        bible = NovelBible(title="Test Novel", source_language="Japanese", target_language="English")
        source_text = "\n".join([f"Sensitive content line {i}." for i in range(1, 17)])

        # Every call raises safety block
        drafter.llm = MagicMock()
        drafter.llm.invoke.side_effect = RuntimeError("400 Bad Request: prohibited_content")

        mock_polisher = MagicMock()
        mock_polisher.polish.side_effect = lambda draft_text, **kw: f"Polished: {draft_text}"
        drafter.polisher = mock_polisher

        with patch("nousetsu.agents.drafter.translate_via_google") as mock_gt:
            mock_gt.return_value = "Google Translated sensitive piece."

            draft = drafter.draft(
                source_text=source_text,
                bible=bible,
                active_characters=[],
                active_glossary=[],
                rolling_summaries=[]
            )

            assert "Polished: Google Translated sensitive piece." in draft
            # Depth 0 subdivides, sub-blocks subdivide until max_depth
            assert drafter.subdivisions_count > 0
            assert drafter.safety_fallbacks_used >= 1

    def test_drafter_sliding_context_continuity(self):
        """Verify that left half's draft tail is passed as preceding context to the right half."""
        drafter = ContextAwareDrafterAgent(
            model_name="mock-model",
            subdivision_min_lines=4,
            subdivision_max_depth=2,
        )

        bible = NovelBible(title="Test", source_language="Japanese", target_language="English")
        clean_half = "\n".join([f"Safe line {i}." for i in range(1, 6)])
        sensitive_half = "\n".join([f"Sensitive line {i}." for i in range(1, 6)])
        source = f"{clean_half}\n\n{sensitive_half}"

        captured_contexts = []
        call_count = 0

        def mock_llm_invoke(messages):
            nonlocal call_count
            call_count += 1
            user_msg = messages[1].content
            # Capture preceding context if present
            if "### Preceding Scene Context" in user_msg:
                captured_contexts.append(user_msg)
            if "Sensitive line" in user_msg:
                raise RuntimeError("400: prohibited_content")
            resp = MagicMock()
            resp.content = "Draft line 1\nDraft line 2\nDraft line 3 (end of left)"
            return resp

        drafter.llm = MagicMock()
        drafter.llm.invoke.side_effect = mock_llm_invoke

        mock_polisher = MagicMock()
        mock_polisher.polish.side_effect = lambda draft_text, **kw: f"Polished: {draft_text}"
        drafter.polisher = mock_polisher

        with patch("nousetsu.agents.drafter.translate_via_google") as mock_gt:
            mock_gt.return_value = "GT sensitive text."

            res = drafter.draft(
                source_text=source,
                bible=bible,
                active_characters=[],
                active_glossary=[],
                rolling_summaries=[]
            )

            assert "Draft line 3 (end of left)" in res
            assert "Polished: GT sensitive text." in res
            assert drafter.subdivisions_count >= 1
            # Verify sliding context was passed to the right half
            assert any("Draft line 3 (end of left)" in ctx for ctx in captured_contexts)


class TestExtractorRecursiveSubdivision:
    """Tests for EntityExtractorAgent recursive bisection on safety blocks."""

    def test_extractor_recovers_entities_from_safe_half(self):
        extractor = EntityExtractorAgent(
            model_name="mock-model",
            subdivision_min_lines=4,
            subdivision_max_depth=2,
        )

        safe_text = "アリスは剣を抜いた。\n彼女は聖騎士だった。\n魔法陣が輝いた。\n宝剣エクスカリバー。"
        sensitive_text = "過激な描写の文章。\n不適切な表現。\n非常に危険な内容。\n規制対象の文字列。"
        combined = f"{safe_text}\n\n{sensitive_text}"

        bible = NovelBible(title="Test", source_language="Japanese", target_language="English")

        def mock_invoke(messages):
            prompt = messages[1].content
            if "過激な描写" in prompt or "不適切な表現" in prompt or "非常に危険な内容" in prompt or "規制対象" in prompt:
                raise RuntimeError("GoogleGenerativeAIError: 400 Bad Request: prohibited_content")
            resp = MagicMock()
            resp.content = (
                '{"new_characters": [{"name": "Alice", "original_name": "アリス", "role": "hero"}],'
                ' "new_terms": [{"source": "宝剣エクスカリバー", "target": "Holy Sword Excalibur", "category": "item"}],'
                ' "active_terms_in_chapter": ["宝剣エクスカリバー"]}'
            )
            return resp

        extractor.llm = MagicMock()
        extractor.llm.invoke.side_effect = mock_invoke

        chars, terms, active = extractor.extract(combined, bible=bible)

        assert len(chars) == 1
        assert chars[0].name == "Alice"
        assert len(terms) == 1
        assert terms[0].source == "宝剣エクスカリバー"
        assert extractor.subdivisions_count >= 1
        assert extractor.safety_fallbacks_used >= 1


class TestCriticRecursiveSubdivision:
    """Tests for CritiqueAgent recursive bisection on safety blocks."""

    def test_critic_subdivides_and_audits_safe_half(self):
        critic = CritiqueAgent(
            model_name="mock-model",
            subdivision_min_lines=4,
            subdivision_max_depth=2,
        )

        safe_src = "安全な原文。\n通常の会話文。\n情景描写。\n日常の風景。"
        sens_src = "過激な原文 1。\n過激な原文 2。\n過激な原文 3。\n過激な原文 4。"
        full_src = f"{safe_src}\n\n{sens_src}"

        safe_draft = "Safe source text.\nNormal dialogue.\nScene description.\nDaily scenery."
        sens_draft = "Explicit draft 1.\nExplicit draft 2.\nExplicit draft 3.\nExplicit draft 4."
        full_draft = f"{safe_draft}\n\n{sens_draft}"

        bible = NovelBible(title="Test", source_language="Japanese", target_language="English")

        def mock_invoke(messages):
            prompt = messages[1].content
            if "過激な原文" in prompt or "Explicit draft" in prompt:
                raise RuntimeError("400 Bad Request: prohibited_content")
            resp = MagicMock()
            resp.content = '{"fidelity_score": 9.5, "style_score": 9.5, "glossary_compliance_pct": 100.0, "warnings": [], "critique_notes": "Great flow."}'
            return resp

        critic.llm = MagicMock()
        critic.llm.invoke.side_effect = mock_invoke

        audit, notes = critic.evaluate(
            source_text=full_src,
            draft_text=full_draft,
            bible=bible,
            active_characters=[],
            active_glossary=[]
        )

        assert audit.passed is True
        # Safe half got 9.5, sensitive half got 8.5/8.0 bypass score -> combined around 9.0 / 8.8
        assert audit.fidelity_score == round((9.5 + 8.5) / 2.0, 1)
        assert audit.style_score == round((9.5 + 8.0) / 2.0, 1)
        assert critic.subdivisions_count >= 1
        assert critic.safety_fallbacks_used >= 1


class TestConfigAndWorkflowIntegration:
    """Tests for ProjectConfig fields and NovelTranslationWorkflow subdivision telemetry."""

    def test_project_config_subdivision_defaults(self):
        cfg = ProjectConfig()
        assert cfg.safety_recursive_subdivision is True
        assert cfg.safety_subdivision_min_lines == 8
        assert cfg.safety_subdivision_max_depth == 4

    def test_workflow_wires_subdivision_to_agents(self):
        workflow = NovelTranslationWorkflow(
            model_name="mock-model",
            safety_recursive_subdivision=True,
            safety_subdivision_min_lines=12,
            safety_subdivision_max_depth=5,
        )

        assert workflow.safety_recursive_subdivision is True
        assert workflow.extractor.enable_recursive_subdivision is True
        assert workflow.extractor.subdivision_min_lines == 12
        assert workflow.extractor.subdivision_max_depth == 5

        assert workflow.drafter.enable_recursive_subdivision is True
        assert workflow.drafter.subdivision_min_lines == 12
        assert workflow.drafter.subdivision_max_depth == 5

        assert workflow.critic.enable_recursive_subdivision is True
        assert workflow.critic.subdivision_min_lines == 12
        assert workflow.critic.subdivision_max_depth == 5

    def test_workflow_records_subdivisions_count_telemetry(self, tmp_path: Path):
        workflow = NovelTranslationWorkflow(
            model_name="mock-model",
            max_review_loops=1,
        )

        bible = NovelBible(title="Subdivision Telemetry Test", source_language="Japanese", target_language="English")
        state = TranslationState(
            chapter_id="ch_subdiv_telemetry",
            chapter_num=1,
            source_file=str(tmp_path / "telemetry.txt"),
            output_file=str(tmp_path / "telemetry.md"),
            source_text="1行目\n2行目\n3行目\n4行目\n5行目\n6行目\n7行目\n8行目\n9行目\n10行目",
            novel_bible=bible
        )

        # Simulate drafter performing 2 subdivisions
        def mock_drafter(*args, **kwargs):
            workflow.drafter.subdivisions_count = 2
            workflow.drafter.safety_fallbacks_used = 1
            return "Translated line 1 to 10."

        workflow.drafter.draft = MagicMock(side_effect=mock_drafter)

        final_state = workflow.run(state)
        assert final_state.current_stage == PipelineStage.CHRONICLING
        assert final_state.subdivisions_count == 2
        assert final_state.safety_fallbacks_used >= 1
        assert final_state.metadata is not None
        assert final_state.metadata.stats.subdivisions_count == 2
        assert final_state.metadata.checkpoint.stage_artifacts.subdivisions_count == 2
