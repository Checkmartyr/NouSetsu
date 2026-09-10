"""Unit tests for batch translation stop and cancellation mechanisms."""
from pathlib import Path
from rich.console import Console
import pytest

from src.batch.runner import BatchRunner
from src.batch.scanner import ChapterScanner
from src.models.metadata import PipelineStage, StageStatus
from src.storage.repository import NovelRepository


def test_batch_runner_stop_between_chapters(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Stop Test Novel", "Japanese", "English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    # Create 3 chapters
    (input_dir / "ch_01.txt").write_text("第一章：最初の冒険。", encoding="utf-8")
    (input_dir / "ch_02.txt").write_text("第二章：旅の途中。", encoding="utf-8")
    (input_dir / "ch_03.txt").write_text("第三章：魔王城へ。", encoding="utf-8")

    console = Console(record=True)
    runner = BatchRunner(repo, model_name="mock-model", console=console)

    # Stop after the first chapter completes
    def on_progress(fn: str, idx: int, total: int, status: str):
        if idx == 1 and status == "COMPLETED":
            runner.stop()

    results = runner.run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        progress_callback=on_progress
    )

    assert runner.is_stopped is True
    # Only Chapter 1 should have run
    assert len(results) == 1
    assert (output_dir / "ch_01.md").exists()
    assert not (output_dir / "ch_02.md").exists()
    assert not (output_dir / "ch_03.md").exists()


def test_batch_runner_stop_mid_chapter_and_resume(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Pause and Resume Test", "Japanese", "English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / "ch_01.txt").write_text("第一章：魔導の目覚め。\n少年は力を得た。", encoding="utf-8")

    console = Console(record=True)
    runner = BatchRunner(repo, model_name="mock-model", console=console)

    # Trigger stop when DRAFTING stage is reached
    def on_stage(fn: str, stage: PipelineStage, msg: str, pct: float):
        if stage == PipelineStage.DRAFTING:
            runner.stop()

    results = runner.run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        stage_callback=on_stage
    )

    assert runner.is_stopped is True
    assert len(results) == 1
    # Checkpoint should be PAUSED and resumable
    assert results[0].checkpoint.status == StageStatus.PAUSED
    assert results[0].checkpoint.is_resumable() is True

    # Scanner should flag the chapter as paused and needing resume
    scanner = ChapterScanner(repo)
    tasks = scanner.scan_directory(input_dir, output_dir)
    assert len(tasks) == 1
    assert tasks[0].is_paused is True
    assert tasks[0].needs_resume is True

    # Now re-run batch without stop signal -> should resume and complete
    runner.reset_stop()
    resumed_results = runner.run_batch(input_dir=input_dir, output_dir=output_dir)

    assert len(resumed_results) == 1
    assert resumed_results[0].checkpoint.status == StageStatus.COMPLETED
    assert (output_dir / "ch_01.md").exists()
