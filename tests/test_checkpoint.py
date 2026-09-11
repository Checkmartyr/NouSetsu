"""Unit tests for checkpoint persistence and metadata loading."""
from pathlib import Path
from nousetsu.batch.scanner import ChapterScanner
from nousetsu.models.metadata import ChapterMetadata, CheckpointData, PipelineStage, StageStatus
from nousetsu.storage.repository import NovelRepository


def test_checkpoint_saving_and_status(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    raw_file = input_dir / "ch_01.txt"
    raw_file.write_text("少年は立ち上がった。", encoding="utf-8")
    out_file = output_dir / "ch_01.md"
    sha = repo.compute_sha256(raw_file)

    meta = ChapterMetadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file=str(raw_file),
        source_sha256=sha,
        output_file=str(out_file),
        checkpoint=CheckpointData(status=StageStatus.COMPLETED, last_completed_stage=PipelineStage.CHRONICLING)
    )

    # Save metadata to single project metadata file
    meta_path = repo.save_metadata(meta, out_file)
    assert meta_path.exists()
    assert meta_path.name == "metadata.json"

    # Also create output file so scanner treats it as completed
    out_file.write_text("# Translated Chapter 1", encoding="utf-8")

    scanner = ChapterScanner(repo)
    tasks = scanner.scan_directory(input_dir, output_dir)
    assert len(tasks) == 1
    assert tasks[0].is_completed is True
    assert tasks[0].needs_resume is False
    assert tasks[0].is_failed is False


def test_checkpoint_error_logging_and_failed_state(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    raw_file = input_dir / "001_Chapter 1.txt"
    raw_file.write_text("Hello world", encoding="utf-8")
    out_file = output_dir / "001_Chapter 1.md"
    sha = repo.compute_sha256(raw_file)

    meta = ChapterMetadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file=str(raw_file),
        source_sha256=sha,
        output_file=str(out_file),
        checkpoint=CheckpointData(status=StageStatus.IN_PROGRESS, last_completed_stage=PipelineStage.DRAFTING)
    )

    try:
        raise ConnectionError("500 INTERNAL server error occurred")
    except Exception as exc:
        import traceback
        meta.checkpoint.record_error(
            stage=PipelineStage.CRITIQUE,
            err=exc,
            traceback_str=traceback.format_exc(),
            model="gemma-4-31b-it"
        )

    assert meta.checkpoint.status == StageStatus.FAILED
    assert meta.checkpoint.failed_stage == PipelineStage.CRITIQUE
    assert meta.checkpoint.last_error_type == "ConnectionError"
    assert "500 INTERNAL" in meta.checkpoint.last_error
    assert meta.checkpoint.retry_count == 1
    assert len(meta.checkpoint.error_logs) == 1
    assert meta.checkpoint.error_logs[0].model == "gemma-4-31b-it"
    assert "ConnectionError" in (meta.checkpoint.last_error_traceback or "")

    # Save to single project metadata file
    repo.save_metadata(meta, out_file)

    # Scanner should flag chapter as failed and resumable from drafting
    scanner = ChapterScanner(repo)
    tasks = scanner.scan_directory(input_dir, output_dir)
    assert len(tasks) == 1
    task = tasks[0]
    assert task.is_failed is True
    assert task.needs_resume is True
    assert task.resume_stage == PipelineStage.DRAFTING
    assert "500 INTERNAL" in (task.last_error or "")


def test_legacy_metadata_migration(tmp_path: Path):
    import json
    repo = NovelRepository(tmp_path)
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    out_file = output_dir / "chapter_05.md"
    legacy_meta_file = output_dir / "chapter_05.meta.json"

    legacy_data = {
        "chapter_id": "chapter_0005",
        "chapter_num": 5,
        "source_file": "raw/05.txt",
        "source_sha256": "abcdef123456",
        "output_file": str(out_file),
        "checkpoint": {
            "status": "completed",
            "last_completed_stage": "chronicling",
            "retry_count": 0,
            "stage_artifacts": {}
        }
    }
    legacy_meta_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    # Load should find legacy file and auto-migrate to .novel/metadata.json
    loaded = repo.load_metadata(out_file)
    assert loaded is not None
    assert loaded.chapter_num == 5
    assert loaded.checkpoint.status == StageStatus.COMPLETED

    # Verify migration into project metadata document
    all_meta = repo.load_all_metadata()
    assert "chapter_05" in all_meta
    assert all_meta["chapter_05"].chapter_num == 5


def test_repository_set_languages(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    bible = repo.initialize_project("Test", "Japanese", "English")
    assert bible.source_language == "Japanese"
    assert bible.target_language == "English"

    updated = repo.set_languages(source_lang="Chinese", target_lang="Spanish")
    assert updated.source_language == "Chinese"
    assert updated.target_language == "Spanish"

    reloaded = repo.load_bible()
    assert reloaded.source_language == "Chinese"
    assert reloaded.target_language == "Spanish"

    # Verify config.yaml was also synchronized
    cfg = repo.load_config()
    assert cfg.source_language == "Chinese"
    assert cfg.target_language == "Spanish"
