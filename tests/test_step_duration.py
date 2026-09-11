"""Unit tests for pipeline stage execution duration tracking in step_usage metadata."""
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import NovelBible
from nousetsu.models.metadata import PipelineStage, QualityAudit, StepTokenUsage, TokenUsage
from nousetsu.models.state import TranslationState


def test_step_token_usage_duration_default_and_custom():
    step = StepTokenUsage(
        stage=PipelineStage.DRAFTING,
        step_name="Drafting",
        iteration=1
    )
    assert step.duration_seconds == 0.0

    step_custom = StepTokenUsage(
        stage=PipelineStage.POLISHING,
        step_name="Polishing",
        iteration=1,
        duration_seconds=3.45
    )
    assert step_custom.duration_seconds == 3.45


def test_workflow_records_duration_for_all_pipeline_steps():
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=1)

    initial_state = TranslationState(
        chapter_id="ch_duration_001",
        chapter_num=1,
        source_text="第一章：旅立ちの合図。少年は歩き出した。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English"),
        max_review_loops=1
    )

    result = workflow.run(initial_state)
    assert result.metadata is not None
    stats = result.metadata.stats

    # Check step-level tracking
    assert len(stats.step_usage) >= 5

    stages_present = [s.stage for s in stats.step_usage]
    assert PipelineStage.EXTRACTION in stages_present
    assert PipelineStage.DRAFTING in stages_present
    assert PipelineStage.CRITIQUE in stages_present
    assert PipelineStage.POLISHING in stages_present
    assert PipelineStage.CHRONICLING in stages_present

    # Check each step has duration_seconds attribute >= 0.0
    for step in stats.step_usage:
        assert isinstance(step.duration_seconds, float)
        assert step.duration_seconds >= 0.0

    # Total duration should match sum of steps
    expected_sum = round(sum(s.duration_seconds for s in stats.step_usage), 2)
    assert stats.duration_seconds >= expected_sum or stats.duration_seconds == expected_sum


def test_multi_pass_review_duration_tracking():
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=2, quality_threshold=9.0)

    audit1 = QualityAudit(fidelity_score=8.0, style_score=8.0, passed=True)
    audit2 = QualityAudit(fidelity_score=9.5, style_score=9.5, passed=True)
    workflow.critic.evaluate = MagicMock(side_effect=[
        (audit1, "Good draft, improve prose cadence."),
        (audit2, "Polished prose is excellent.")
    ])

    initial_state = TranslationState(
        chapter_id="ch_review_duration",
        chapter_num=1,
        source_text="第二章：洞窟の中へ足を踏み入れる。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English"),
        max_review_loops=2,
        quality_threshold=9.0
    )

    result = workflow.run(initial_state)
    stats = result.metadata.stats

    critique_steps = [s for s in stats.step_usage if s.stage == PipelineStage.CRITIQUE]
    assert len(critique_steps) == 2
    for s in critique_steps:
        assert s.duration_seconds >= 0.0

    polish_steps = [s for s in stats.step_usage if s.stage == PipelineStage.POLISHING]
    assert len(polish_steps) >= 1
    for s in polish_steps:
        assert s.duration_seconds >= 0.0
