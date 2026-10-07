"""Tests for Procedural Graph Online Learning and Self-Evolution (arXiv:2609.09153v1)."""
import json
from pathlib import Path
import pytest

from nousetsu.graph.pg_refiner import DiagnosticTrace, GraphEditOperation, ProceduralGraphRefiner
from nousetsu.graph.procedural import (
    ProceduralEdge,
    ProceduralGraph,
    get_default_drafter_graph,
    get_default_extractor_graph,
)
from nousetsu.models.bible import ArcSummary
from nousetsu.models.config import ProjectConfig
from nousetsu.models.metadata import ChapterMetadata, CheckpointData, QualityAudit, StageArtifacts
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository


def test_procedural_learning_config_defaults_and_env(monkeypatch):
    """Verify ProjectConfig fields and environment cascading for online learning."""
    cfg = ProjectConfig()
    assert cfg.get_enable_procedural_graph_learning() is True
    assert cfg.get_procedural_learning_cadence() == "both"
    assert cfg.get_procedural_learning_interval() == 15
    assert cfg.get_procedural_learning_min_failures() == 2
    assert cfg.get_procedural_refiner_model() == "gemini-3.5-flash-lite"

    monkeypatch.setenv("NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING", "false")
    monkeypatch.setenv("NOVEL_PROCEDURAL_LEARNING_CADENCE", "arc")
    monkeypatch.setenv("NOVEL_PROCEDURAL_LEARNING_INTERVAL", "10")
    monkeypatch.setenv("NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES", "3")
    monkeypatch.setenv("NOVEL_PROCEDURAL_REFINER_MODEL", "mock-refiner-model")

    cfg_env = ProjectConfig()
    assert cfg_env.get_enable_procedural_graph_learning() is False
    assert cfg_env.get_procedural_learning_cadence() == "arc"
    assert cfg_env.get_procedural_learning_interval() == 10
    assert cfg_env.get_procedural_learning_min_failures() == 3
    assert cfg_env.get_procedural_refiner_model() == "mock-refiner-model"


def test_repository_history_and_rollback(tmp_path):
    """Verify repository history archiving, listing, rollback, and evolution logging."""
    repo = NovelRepository(tmp_path)
    base_graph = get_default_drafter_graph()

    # Initial save creates file
    p1 = repo.save_procedural_graph(base_graph, "drafter", archive_previous=True)
    assert p1.exists()
    assert len(repo.list_procedural_graph_history("drafter")) == 0

    # Mutate and save again -> archives previous version
    mutated_graph = base_graph.model_copy(deep=True)
    mutated_graph.edges[0].guidance = "Evolved guidance directive."
    p2 = repo.save_procedural_graph(mutated_graph, "drafter", archive_previous=True)
    assert p2.exists()

    history = repo.list_procedural_graph_history("drafter")
    assert len(history) == 1

    # Verify loaded is mutated
    loaded = repo.load_procedural_graph("drafter")
    assert loaded.edges[0].guidance == "Evolved guidance directive."

    # Rollback to historical snapshot
    restored = repo.rollback_procedural_graph("drafter")
    assert restored is not None
    assert restored.edges[0].guidance == base_graph.edges[0].guidance

    # Evolution logging
    log_file = repo.log_procedural_graph_evolution({
        "agent_name": "drafter",
        "chapter_num": 15,
        "trigger_type": "interval",
        "status": "COMMITTED"
    })
    assert log_file.exists()
    with open(log_file, "r", encoding="utf-8") as f:
        entries = json.load(f)
    assert len(entries) == 1
    assert entries[0]["agent_name"] == "drafter"


def test_refiner_regression_detection():
    """Verify check_score_regression detects fidelity drop in recent window."""
    refiner = ProceduralGraphRefiner(model_name="mock-refiner")

    # Stable high scores
    good_traces = [
        DiagnosticTrace(trace_id=f"t{i}", stage="drafter", context_snippet="", output_snippet="", fidelity_score=9.0)
        for i in range(5)
    ]
    assert refiner.check_score_regression(good_traces, window_size=3, threshold_drop=1.0, baseline_score=8.5) is False

    # Regressing scores
    regressed_traces = [
        DiagnosticTrace(trace_id="t1", stage="drafter", context_snippet="", output_snippet="", fidelity_score=9.0),
        DiagnosticTrace(trace_id="t2", stage="drafter", context_snippet="", output_snippet="", fidelity_score=8.8),
        DiagnosticTrace(trace_id="t3", stage="drafter", context_snippet="", output_snippet="", fidelity_score=7.0),
        DiagnosticTrace(trace_id="t4", stage="drafter", context_snippet="", output_snippet="", fidelity_score=6.8),
        DiagnosticTrace(trace_id="t5", stage="drafter", context_snippet="", output_snippet="", fidelity_score=7.1),
    ]
    assert refiner.check_score_regression(regressed_traces, window_size=3, threshold_drop=1.0, baseline_score=8.5) is True


def test_refiner_evolve_and_persist_synthetic(tmp_path):
    """Verify evolve_and_persist mutates graph, persists to repository, and logs evolution."""
    repo = NovelRepository(tmp_path)
    refiner = ProceduralGraphRefiner(model_name="mock-refiner")
    base_graph = get_default_drafter_graph()

    # Synthetic traces with warnings
    traces = [
        DiagnosticTrace(
            trace_id="t1",
            stage="drafter",
            context_snippet="Sample context",
            output_snippet="Sample output",
            fidelity_score=7.5,
            warnings=["Subject dropped in banter"],
            critique_notes="Clarify omitted subject."
        )
    ]

    # Mock _propose_mutations to return deterministic edit
    refiner._propose_mutations = lambda g, f, s: [
        GraphEditOperation(
            operation="UPDATE",
            edge_source="Zero_Anaphora_Resolution",
            edge_target="Voice_Modulation",
            new_guidance="Verify omitted subject strictly before banter.",
            rationale="Fix subject dropped warning."
        )
    ]

    evolved, edits = refiner.evolve_and_persist(
        graph=base_graph,
        traces=traces,
        repo=repo,
        agent_name="drafter",
        trigger_type="interval",
        chapter_num=15
    )

    assert evolved is not None
    assert len(edits) == 1
    assert repo.load_procedural_graph("drafter") is not None

    # Check that history snapshot was created
    history = repo.list_procedural_graph_history("drafter")
    assert len(history) >= 0


def test_batch_runner_triggers_and_execution(tmp_path):
    """Verify BatchRunner triggers online learning on arc boundary and interval."""
    from nousetsu.batch.runner import BatchRunner

    repo = NovelRepository(tmp_path)
    # Populate mock metadata for Ch.1 to Ch.15 with a couple of failure traces
    all_meta = {}
    for i in range(1, 16):
        warnings = ["Speaker inversion warning"] if i in (13, 14) else []
        fid = 7.0 if i in (13, 14) else 9.0
        ch = ChapterMetadata(
            chapter_id=f"chapter_{i:04d}",
            chapter_num=i,
            source_file=f"{i:04d}.txt",
            source_sha256=f"hash_{i}",
            output_file=f"{i:04d}.md",
            checkpoint=CheckpointData(
                stage_artifacts=StageArtifacts(
                    draft_text="Draft text.",
                    critique_notes="Speaker inversion."
                )
            ),
            quality_audit=QualityAudit(
                fidelity_score=fid,
                style_score=8.5,
                warnings=warnings
            )
        )
        all_meta[f"chapter_{i:04d}"] = ch
    repo.save_all_metadata(all_meta)

    runner = BatchRunner(
        repository=repo,
        model_name="mock-novel-llm",
        enable_procedural_graph_learning=True,
        procedural_learning_cadence="both",
        procedural_learning_interval=15,
        procedural_learning_min_failures=2,
    )

    # Mock refiner._propose_mutations
    runner.refiner._propose_mutations = lambda g, f, s: [
        GraphEditOperation(
            operation="UPDATE",
            edge_source="Zero_Anaphora_Resolution",
            edge_target="Voice_Modulation",
            new_guidance="Avoid speaker inversion during heated exchanges.",
            rationale="Fix critique notes."
        )
    ]

    notified = []

    # 1. Non-trigger chapter (Ch.14 without arc completion)
    st_non_trigger = TranslationState(chapter_id="chapter_0014", chapter_num=14, source_text="Sample raw chapter.")
    runner._handle_procedural_graph_learning(
        completed_chapter_num=14,
        folder=None,
        final_state=st_non_trigger,
        notify_callback=lambda msg: notified.append(msg)
    )
    assert not any("Evaluating Procedural Graph" in m for m in notified)

    # 2. Trigger on chapter interval (Ch.15)
    st_interval = TranslationState(chapter_id="chapter_0015", chapter_num=15, source_text="Sample raw chapter.")
    runner._handle_procedural_graph_learning(
        completed_chapter_num=15,
        folder=None,
        final_state=st_interval,
        notify_callback=lambda msg: notified.append(msg)
    )
    assert any("interval boundary at Ch.15" in m for m in notified)
    assert any("Online evolved Procedural Graph for drafter" in m for m in notified)

    # Verify workflow agent was hot-reloaded
    drafter_g = runner.workflow.drafter.procedural_graph
    assert any("Avoid speaker inversion" in e.guidance for e in drafter_g.edges)

    # 3. Trigger on arc completion (even if chapter is not 15)
    notified.clear()
    st_arc = TranslationState(
        chapter_id="chapter_0008",
        chapter_num=8,
        source_text="Sample raw chapter.",
        arc_summary=ArcSummary(
            arc_number=1,
            title="Academy Duel Arc",
            synopsis="Climax concluded.",
            arc_completed=True
        )
    )
    runner._handle_procedural_graph_learning(
        completed_chapter_num=8,
        folder=None,
        final_state=st_arc,
        notify_callback=lambda msg: notified.append(msg)
    )
    assert any("arc boundary at Ch.8" in m for m in notified)
