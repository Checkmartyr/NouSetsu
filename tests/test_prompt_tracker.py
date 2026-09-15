"""Comprehensive unit and integration tests for PromptTracker and CLI traces."""
import argparse
import json
from pathlib import Path
import pytest
from rich.console import Console

from nousetsu.analysis.tracker import PromptTracker
from nousetsu.batch.runner import BatchRunner
from nousetsu.cli.app import cmd_traces
from nousetsu.models.metadata import PipelineStage, StageStatus, TokenUsage
from nousetsu.models.trace import AgentPromptTrace, ChapterTraceDocument
from nousetsu.storage.repository import NovelRepository


def test_prompt_tracker_record_and_streaming_jsonl(tmp_path: Path):
    """Test PromptTracker streaming JSONL append and finalize."""
    traces_dir = tmp_path / ".novel" / "traces"
    tracker = PromptTracker(traces_dir, chapter_id="ch_01", chapter_num=1, folder="Vol_01")

    # Initially files shouldn't exist
    assert not tracker.jsonl_path.exists()
    assert not tracker.json_path.exists()

    # Record first interaction
    tracker.record(
        stage=PipelineStage.EXTRACTION,
        agent="extractor",
        system_prompt="System instructions for extraction",
        user_prompt="Novel chapter text to extract",
        raw_output='{"new_characters": [], "new_terms": []}',
        parsed_output={"new_characters": 0, "new_terms": 0},
        model="mock-model",
        token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        duration_seconds=1.23,
        chunk_index=1,
        total_chunks=1
    )

    # Real-time JSONL file must be created immediately
    assert tracker.jsonl_path.exists()
    assert len(tracker.traces) == 1

    # Verify JSONL content on disk
    with open(tracker.jsonl_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["agent"] == "extractor"
        assert entry["stage"] == "extraction"
        assert entry["token_usage"]["total_tokens"] == 150

    # Record error interaction
    tracker.record_error(
        stage=PipelineStage.DRAFTING,
        agent="drafter",
        system_prompt="System instructions for drafting",
        user_prompt="Novel chapter text to draft",
        model="mock-model",
        err=ValueError("Safety filter triggered mock"),
        duration_seconds=0.45,
        status="safety_blocked"
    )

    assert len(tracker.traces) == 2
    with open(tracker.jsonl_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 2
        entry2 = json.loads(lines[1])
        assert entry2["status"] == "safety_blocked"
        assert "Safety filter triggered mock" in entry2["error_message"]

    # Finalize writes consolidated JSON
    doc = tracker.finalize()
    assert tracker.json_path.exists()
    assert doc.total_interactions == 2
    assert doc.chapter_num == 1
    assert doc.folder == "Vol_01"

    # Verify static loading
    loaded_doc = PromptTracker.load_from_json(tracker.json_path)
    assert loaded_doc is not None
    assert loaded_doc.total_interactions == 2
    assert len(loaded_doc.traces) == 2

    loaded_from_jsonl = PromptTracker.load_from_jsonl(tracker.jsonl_path)
    assert len(loaded_from_jsonl) == 2


def test_repository_trace_integration(tmp_path: Path):
    """Test NovelRepository trace listing and loading methods."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Trace Test", "Japanese", "English")

    # Create dummy traces in two folders
    tracker1 = PromptTracker(repo.traces_dir, chapter_id="ch_01", chapter_num=1, folder="Arc1")
    tracker1.record(
        stage=PipelineStage.EXTRACTION,
        agent="extractor",
        system_prompt="Sys 1",
        user_prompt="User 1",
        raw_output="Out 1",
        model="mock-model",
        token_usage=TokenUsage(input_tokens=50, output_tokens=25, total_tokens=75),
        duration_seconds=1.0
    )
    tracker1.finalize()

    tracker2 = PromptTracker(repo.traces_dir, chapter_id="ch_02", chapter_num=2, folder="Arc2")
    tracker2.record(
        stage=PipelineStage.DRAFTING,
        agent="drafter",
        system_prompt="Sys 2",
        user_prompt="User 2",
        raw_output="Out 2",
        model="mock-model",
        token_usage=TokenUsage(input_tokens=60, output_tokens=30, total_tokens=90),
        duration_seconds=1.5
    )
    tracker2.finalize()

    # List traces across all folders
    all_traces = repo.list_chapter_traces()
    assert len(all_traces) == 2

    # List traces in specific folder
    arc1_traces = repo.list_chapter_traces(folder="Arc1")
    assert len(arc1_traces) == 1

    # Load chapter trace doc
    doc1 = repo.load_chapter_traces(chapter_num=1, folder="Arc1")
    assert doc1 is not None
    assert doc1.chapter_num == 1
    assert doc1.folder == "Arc1"
    assert doc1.traces[0].agent == "extractor"


def test_batch_runner_captures_all_agent_traces(tmp_path: Path):
    """Test that running BatchRunner automatically instruments and persists traces for all 5 agents."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Trace End-to-End", "Japanese", "English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / "ch_01.txt").write_text("第一章：異世界への扉。\n主人公は立ち上がった。", encoding="utf-8")

    console = Console(record=True)
    runner = BatchRunner(repo, model_name="mock-model", console=console)
    results = runner.run_batch(input_dir=input_dir, output_dir=output_dir)

    assert len(results) == 1
    assert results[0].checkpoint.status == StageStatus.COMPLETED

    # Check that trace file was created in repository traces_dir
    trace_files = repo.list_chapter_traces()
    assert len(trace_files) >= 1

    # Load trace document
    doc = repo.load_chapter_traces(chapter_num=1)
    assert doc is not None
    assert doc.total_interactions >= 5  # extractor, drafter, critic, polisher, chronicler

    agents_captured = {t.agent for t in doc.traces}
    assert "extractor" in agents_captured
    assert "drafter" in agents_captured
    assert "critic" in agents_captured
    assert "polisher" in agents_captured
    assert "chronicler" in agents_captured

    # Verify metadata contains trace file reference and count
    meta = repo.load_metadata(output_dir / "ch_01.md")
    assert meta is not None
    assert meta.trace_file is not None
    assert meta.prompt_trace_count == doc.total_interactions
    assert meta.prompt_trace_count >= 5

    # Check that system prompt and user prompt are not empty
    for t in doc.traces:
        assert len(t.system_prompt) > 0
        assert len(t.user_prompt) > 0
        assert t.duration_seconds >= 0.0


def test_cli_traces_command(tmp_path: Path, capsys):
    """Test CLI nousetsu traces listing and detailed inspection."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("CLI Trace Test", "Japanese", "English")

    # Create trace
    tracker = PromptTracker(repo.traces_dir, chapter_id="ch_01", chapter_num=1)
    tracker.record(
        stage=PipelineStage.DRAFTING,
        agent="drafter",
        system_prompt="You are a professional literary translator.",
        user_prompt="Translate the excerpt.",
        raw_output="The hero stepped forward into the darkness.",
        model="mock-model",
        token_usage=TokenUsage(input_tokens=150, output_tokens=75, total_tokens=225),
        duration_seconds=1.45
    )
    tracker.finalize()

    # 1. Test listing traces (no chapter specified)
    args_list = argparse.Namespace(
        project_dir=str(tmp_path),
        folder=None,
        chapter=None,
        agent=None,
        stage=None,
        show_prompts=False,
        show_outputs=False,
        export=None
    )
    cmd_traces(args_list)

    # 2. Test inspecting chapter 1 traces
    args_inspect = argparse.Namespace(
        project_dir=str(tmp_path),
        folder=None,
        chapter="1",
        agent=None,
        stage=None,
        show_prompts=True,
        show_outputs=True,
        export=None
    )
    cmd_traces(args_inspect)

    # 3. Test export to custom JSON file
    export_file = tmp_path / "exported_traces.json"
    args_export = argparse.Namespace(
        project_dir=str(tmp_path),
        folder=None,
        chapter="1",
        agent="drafter",
        stage="drafting",
        show_prompts=False,
        show_outputs=False,
        export=str(export_file)
    )
    cmd_traces(args_export)
    assert export_file.exists()
    with open(export_file, "r", encoding="utf-8") as ef:
        exported_data = json.load(ef)
        assert len(exported_data) == 1
        assert exported_data[0]["agent"] == "drafter"
