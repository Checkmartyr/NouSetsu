"""Unit tests for the automated Critic-Polish review loop."""
import os
from pathlib import Path
import threading
from unittest.mock import MagicMock
import pytest

from nousetsu.batch.runner import BatchRunner
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import NovelBible
from nousetsu.models.config import ProjectConfig
from nousetsu.models.exceptions import BatchStoppedException
from nousetsu.models.metadata import PipelineStage, QualityAudit
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository


def test_default_review_loop_early_exit(tmp_path: Path):
    """When default mock critic returns score >= 8.5, review loop exits early after Pass 1 audit."""
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=3, quality_threshold=8.5)

    initial_state = TranslationState(
        chapter_id="ch_001",
        chapter_num=1,
        source_text="第一章：旅立ちの合図。少年は歩き出した。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English"),
        max_review_loops=3,
        quality_threshold=8.5
    )

    result = workflow.run(initial_state)
    assert result.polished_text
    assert result.quality_audit.fidelity_score >= 8.5
    assert result.quality_audit.style_score >= 8.5
    assert result.review_iteration <= 2


def test_multi_pass_review_loop_until_threshold_met():
    """Verify loop iterates through multiple polish passes until quality threshold is met."""
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=3, quality_threshold=8.5)

    # Call 1 (draft): fidelity=7.0, style=7.2 (< 8.5)
    audit1 = QualityAudit(fidelity_score=7.0, style_score=7.2, passed=False)
    # Call 2 (polish 1): fidelity=8.0, style=8.2 (< 8.5)
    audit2 = QualityAudit(fidelity_score=8.0, style_score=8.2, passed=True)
    # Call 3 (polish 2): fidelity=8.9, style=9.0 (>= 8.5) -> should trigger early exit
    audit3 = QualityAudit(fidelity_score=8.9, style_score=9.0, passed=True)

    workflow.critic.evaluate = MagicMock(side_effect=[
        (audit1, "Draft needs better rhythm."),
        (audit2, "Polished v1 improved, but needs tighter cadence."),
        (audit3, "Polished v2 is literary perfection.")
    ])

    polish_calls = []
    def mock_polish(draft_text, critique_notes, active_glossary, bible, **kwargs):
        idx = len(polish_calls) + 1
        out = f"Polished text version {idx} (Notes: {critique_notes})"
        polish_calls.append(out)
        return out

    workflow.polisher.polish = MagicMock(side_effect=mock_polish)

    initial_state = TranslationState(
        chapter_id="ch_001",
        chapter_num=1,
        source_text="第一章：旅立ちの合図。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English"),
        max_review_loops=3,
        quality_threshold=8.5
    )

    result = workflow.run(initial_state)

    # Critic called 3 times: Draft -> Polish v1 -> Polish v2
    assert workflow.critic.evaluate.call_count == 3
    # Polisher called 2 times: Pass 1 on draft, Pass 2 on Polish v1
    assert workflow.polisher.polish.call_count == 2
    assert "Polished text version 2" in result.polished_text
    assert result.quality_audit.fidelity_score == 8.9
    assert result.quality_audit.style_score == 9.0


def test_max_review_loops_cap():
    """Verify review loop respects max_review_loops cap and does not loop indefinitely."""
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=2, quality_threshold=8.5)

    low_audit = QualityAudit(fidelity_score=6.0, style_score=6.5, passed=False)
    workflow.critic.evaluate = MagicMock(return_value=(low_audit, "Persistent issues."))
    workflow.polisher.polish = MagicMock(return_value="Attempted polish.")

    initial_state = TranslationState(
        chapter_id="ch_001",
        chapter_num=1,
        source_text="第一章：旅立ちの合図。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English"),
        max_review_loops=2,
        quality_threshold=8.5
    )

    result = workflow.run(initial_state)

    # For max_review_loops=2:
    # 1. Draft critique
    # 2. Polish 1
    # 3. Polish 1 critique
    # 4. Polish 2
    # 5. Polish 2 critique -> iteration 3 > max (2) -> chronicle
    assert workflow.polisher.polish.call_count == 2
    assert workflow.critic.evaluate.call_count == 3
    assert result.metadata is not None


def test_best_candidate_regression_guard():
    """Verify regression guard keeps highest-scoring candidate even if later passes score lower."""
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=2, quality_threshold=8.5)

    # Pass 1 draft audit: avg 7.0
    audit_draft = QualityAudit(fidelity_score=7.0, style_score=7.0)
    # Pass 2 audit on polish 1: avg 8.35 (fidelity 8.4, style 8.3)
    audit_pass1 = QualityAudit(fidelity_score=8.4, style_score=8.3)
    # Pass 3 audit on polish 2: avg 7.1 (fidelity 7.2, style 7.0) -> regression!
    audit_pass2 = QualityAudit(fidelity_score=7.2, style_score=7.0)

    workflow.critic.evaluate = MagicMock(side_effect=[
        (audit_draft, "Draft issues"),
        (audit_pass1, "Good pass 1"),
        (audit_pass2, "Regression in pass 2")
    ])

    workflow.polisher.polish = MagicMock(side_effect=[
        "Polished Text Pass 1 (Best Quality)",
        "Polished Text Pass 2 (Degraded Quality)"
    ])

    initial_state = TranslationState(
        chapter_id="ch_001",
        chapter_num=1,
        source_text="第一章：旅立ちの合図。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English"),
        max_review_loops=2,
        quality_threshold=8.5
    )

    result = workflow.run(initial_state)

    # Regression guard should ensure Pass 1 text and audit are selected for final output
    assert result.polished_text == "Polished Text Pass 1 (Best Quality)"
    assert result.quality_audit.fidelity_score == 8.4
    assert result.quality_audit.style_score == 8.3


def test_stop_event_during_review_loop():
    """Verify stop_event mid-loop interrupts gracefully."""
    workflow = NovelTranslationWorkflow(model_name="mock-model", max_review_loops=3, quality_threshold=8.5)
    stop_event = threading.Event()

    low_audit = QualityAudit(fidelity_score=7.0, style_score=7.0, passed=False)
    workflow.critic.evaluate = MagicMock(return_value=(low_audit, "Needs work"))

    # Stop after pass 1 polish
    def mock_polish_and_stop(*args, **kwargs):
        stop_event.set()
        return "Polish 1 text"

    workflow.polisher.polish = MagicMock(side_effect=mock_polish_and_stop)

    initial_state = TranslationState(
        chapter_id="ch_001",
        chapter_num=1,
        source_text="第一章：旅立ちの合図。",
        novel_bible=NovelBible(source_language="Japanese", target_language="English"),
        max_review_loops=3,
        quality_threshold=8.5
    )

    with pytest.raises(BatchStoppedException):
        workflow.run(initial_state, stop_event=stop_event)

    assert workflow.last_state is not None
    assert workflow.last_state.best_polished_text == "Polish 1 text"


def test_batch_runner_review_loop_config(tmp_path: Path, monkeypatch):
    """Verify BatchRunner initializes review loop parameters from env and config."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Review Loop Config Test", "Japanese", "English")

    monkeypatch.setenv("NOVEL_MAX_REVIEW_LOOPS", "4")
    monkeypatch.setenv("NOVEL_QUALITY_THRESHOLD", "9.2")

    runner = BatchRunner(repo, model_name="mock-model")

    assert runner.max_review_loops == 4
    assert runner.quality_threshold == 9.2
    assert runner.workflow.max_review_loops == 4
    assert runner.workflow.quality_threshold == 9.2
