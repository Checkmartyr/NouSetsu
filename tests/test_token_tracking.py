"""Unit tests for granular per-task and per-step token usage tracking."""
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from nousetsu.batch.runner import BatchRunner
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import NovelBible
from nousetsu.models.metadata import PipelineStage, QualityAudit, StepTokenUsage, TokenUsage
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository


def test_token_usage_addition():
    u1 = TokenUsage(input_tokens=100, output_tokens=50, thought_tokens=20, cached_tokens=10, total_tokens=170)
    u2 = TokenUsage(input_tokens=200, output_tokens=100, thought_tokens=40, cached_tokens=0, total_tokens=340)

    u_sum = u1.add(u2)
    assert u_sum.input_tokens == 300
    assert u_sum.output_tokens == 150
    assert u_sum.thought_tokens == 60
    assert u_sum.cached_tokens == 10
    assert u_sum.total_tokens == 510


def test_workflow_records_all_pipeline_steps():
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=1)

    initial_state = TranslationState(
        chapter_id="ch_tokens_001",
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

    # Check each step has non-zero tokens
    for step in stats.step_usage:
        assert step.usage.total_tokens > 0
        assert step.usage.input_tokens > 0

    # Check cumulative total matches exact sum of steps
    expected_total = sum(s.usage.total_tokens for s in stats.step_usage)
    expected_prompt = sum(s.usage.input_tokens for s in stats.step_usage)
    expected_comp = sum(s.usage.output_tokens for s in stats.step_usage)

    assert stats.total_tokens == expected_total
    assert stats.prompt_tokens == expected_prompt
    assert stats.completion_tokens == expected_comp


def test_multi_pass_review_loop_logs_each_iteration():
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=2, quality_threshold=9.0)

    # Force 2 critique passes
    audit1 = QualityAudit(fidelity_score=8.0, style_score=8.0, passed=True)
    audit2 = QualityAudit(fidelity_score=9.5, style_score=9.5, passed=True)
    workflow.critic.evaluate = MagicMock(side_effect=[
        (audit1, "Good draft, improve prose cadence."),
        (audit2, "Polished prose is excellent.")
    ])

    initial_state = TranslationState(
        chapter_id="ch_review_tokens",
        chapter_num=1,
        source_text="第二章：洞窟の中へ足を踏み入れる。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English"),
        max_review_loops=2,
        quality_threshold=9.0
    )

    result = workflow.run(initial_state)
    stats = result.metadata.stats

    # Filter steps
    critique_steps = [s for s in stats.step_usage if s.stage == PipelineStage.CRITIQUE]
    polish_steps = [s for s in stats.step_usage if s.stage == PipelineStage.POLISHING]

    assert len(critique_steps) == 2
    assert "Pass 1" in critique_steps[0].step_name
    assert "Pass 2" in critique_steps[1].step_name

    assert len(polish_steps) >= 1
    assert "Pass 1" in polish_steps[0].step_name


def test_batch_runner_tracks_task_and_batch_totals(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project(title="Token Test Novel", source_lang="Japanese", target_lang="English")

    raw_dir = tmp_path / "raw_chapters"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "001.txt").write_text("第1話：冒険が始まった。", encoding="utf-8")
    (raw_dir / "002.txt").write_text("第2話：新たな仲間と出会う。", encoding="utf-8")

    out_dir = tmp_path / "translated_chapters"

    runner = BatchRunner(repo, model_name="mock-model")
    results = runner.run_batch(input_dir=raw_dir, output_dir=out_dir)

    assert len(results) == 2
    assert runner.batch_token_usage.total_tokens > 0
    assert "001.txt" in runner.task_token_usage
    assert "002.txt" in runner.task_token_usage

    task1_usage = runner.task_token_usage["001.txt"]
    task2_usage = runner.task_token_usage["002.txt"]

    assert task1_usage.total_tokens > 0
    assert task2_usage.total_tokens > 0
    assert runner.batch_token_usage.total_tokens == task1_usage.total_tokens + task2_usage.total_tokens
