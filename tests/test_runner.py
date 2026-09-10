"""Integration tests for BatchRunner and LangGraph pipeline with MockNovelLLM."""
from pathlib import Path
from rich.console import Console
from src.batch.runner import BatchRunner
from src.models.metadata import StageStatus
from src.storage.repository import NovelRepository


def test_batch_runner_end_to_end(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test Novel", "Japanese", "English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    # Create two chapters
    (input_dir / "ch_01.txt").write_text("第一章：少年の旅立ち。\n少年は剣を手に取った。", encoding="utf-8")
    (input_dir / "ch_02.txt").write_text("第二章：森の魔導具。\n彼は怪しい光を見つけた。", encoding="utf-8")

    console = Console(record=True)
    runner = BatchRunner(repo, model_name="mock-model", console=console)

    results = runner.run_batch(input_dir=input_dir, output_dir=output_dir)

    assert len(results) == 2
    assert results[0].checkpoint.status == StageStatus.COMPLETED
    assert results[1].checkpoint.status == StageStatus.COMPLETED

    # Check output translation files exist
    assert (output_dir / "ch_01.md").exists()
    assert (output_dir / "ch_02.md").exists()
    # Output directory should be clean with no polluting .meta.json files
    assert not (output_dir / "ch_01.meta.json").exists()
    assert not (output_dir / "ch_02.meta.json").exists()

    # Single project metadata document should contain both chapters
    assert (tmp_path / ".novel" / "metadata.json").exists()
    all_meta = repo.load_all_metadata()
    assert "ch_01" in all_meta
    assert "ch_02" in all_meta
    assert all_meta["ch_01"].checkpoint.status == StageStatus.COMPLETED
    assert all_meta["ch_02"].checkpoint.status == StageStatus.COMPLETED

    # Verify Bible updated with summaries
    updated_bible = repo.load_bible()
    assert len(updated_bible.summaries) == 2

    # Second run without force should skip both
    results_second = runner.run_batch(input_dir=input_dir, output_dir=output_dir)
    assert len(results_second) == 2
