"""Unit tests for chapter alignment and collision repair engine."""
import json
from pathlib import Path
import pytest

from nousetsu.models.bible import ChapterSummary
from nousetsu.models.metadata import ChapterMetadata, CheckpointData, PipelineStage, StageStatus
from nousetsu.storage.repository import NovelRepository
from nousetsu.storage.repair import realign_project_folder


def test_realign_project_folder_collided_chapters(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project()

    folder = "Volume_01"
    raw_dir = tmp_path / folder
    out_dir = tmp_path / f"{folder}_th"
    raw_dir.mkdir()
    out_dir.mkdir()

    # Create 3 regular chapters + 2 extra chapters
    for i in range(1, 4):
        (raw_dir / f"{i:03d}_Chapter {i}.txt").write_text(f"Chapter {i} raw content", encoding="utf-8")
        (out_dir / f"{i:03d}_Chapter {i}.md").write_text(f"# Chapter {i}\nTranslated content {i}", encoding="utf-8")

    # Extra chapters 1 and 2 (numbered 004 and 005)
    (raw_dir / "004_Extra Chapter 1 - Side.txt").write_text("Extra 1 raw content", encoding="utf-8")
    (out_dir / "004_Extra Chapter 1 - Side.md").write_text("# Special Chapter 1\nExtra 1 translated", encoding="utf-8")
    (raw_dir / "005_Extra Chapter 2 - Side.txt").write_text("Extra 2 raw content", encoding="utf-8")
    (out_dir / "005_Extra Chapter 2 - Side.md").write_text("# Special Chapter 2\nExtra 2 translated", encoding="utf-8")

    # Set up metadata.json with old collided entries (Extra 1 had chapter_num=1, Extra 2 had chapter_num=2)
    all_metadata = {}
    for i in range(1, 4):
        key = f"{out_dir.name}/{i:03d}_Chapter {i}"
        all_metadata[key] = ChapterMetadata(
            chapter_id=f"chapter_{i:04d}",
            chapter_num=i,
            source_file=str(raw_dir / f"{i:03d}_Chapter {i}.txt"),
            output_file=str(out_dir / f"{i:03d}_Chapter {i}.md"),
            source_sha256="dummy_sha256",
            checkpoint=CheckpointData(status=StageStatus.COMPLETED, last_completed_stage=PipelineStage.CHRONICLING)
        )
    # Collided extra chapters:
    all_metadata[f"{out_dir.name}/004_Extra Chapter 1 - Side"] = ChapterMetadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file=str(raw_dir / "004_Extra Chapter 1 - Side.txt"),
        output_file=str(out_dir / "004_Extra Chapter 1 - Side.md"),
        source_sha256="dummy_sha256",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED, last_completed_stage=PipelineStage.CHRONICLING)
    )
    all_metadata[f"{out_dir.name}/005_Extra Chapter 2 - Side"] = ChapterMetadata(
        chapter_id="chapter_0002",
        chapter_num=2,
        source_file=str(raw_dir / "005_Extra Chapter 2 - Side.txt"),
        output_file=str(out_dir / "005_Extra Chapter 2 - Side.md"),
        source_sha256="dummy_sha256",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED, last_completed_stage=PipelineStage.CHRONICLING)
    )
    repo.save_all_metadata(all_metadata)

    # Place summaries where Extra 1 and Extra 2 overwrote chapter_0001 and chapter_0002
    sums_dir = repo.summaries_dir / folder
    sums_dir.mkdir(parents=True, exist_ok=True)
    with open(sums_dir / "chapter_0001.json", "w", encoding="utf-8") as f:
        json.dump({"chapter_num": 1, "title": "Special Chapter 1", "synopsis": "Extra 1 synopsis"}, f)
    with open(sums_dir / "chapter_0002.json", "w", encoding="utf-8") as f:
        json.dump({"chapter_num": 2, "title": "Special Chapter 2", "synopsis": "Extra 2 synopsis"}, f)
    with open(sums_dir / "chapter_0003.json", "w", encoding="utf-8") as f:
        json.dump({"chapter_num": 3, "title": "Chapter 3", "synopsis": "Ch 3 synopsis"}, f)

    # 1. Test Dry Run
    dry_report = realign_project_folder(repo, folder=folder, dry_run=True)
    assert dry_report.total_chapters == 5
    assert len(dry_report.realigned_chapters) == 2
    assert ("004_Extra Chapter 1 - Side.txt", 1, 4) in dry_report.realigned_chapters
    assert ("005_Extra Chapter 2 - Side.txt", 2, 5) in dry_report.realigned_chapters

    # 2. Test Real Alignment Run
    report = realign_project_folder(repo, folder=folder, dry_run=False, re_chronicle=False)
    assert report.total_chapters == 5
    assert report.metadata_entries_updated == 2
    assert report.backup_path is not None
    assert Path(report.backup_path).exists()

    # Verify summaries were relocated to chapter_0004.json and chapter_0005.json
    assert (sums_dir / "chapter_0004.json").exists()
    assert (sums_dir / "chapter_0005.json").exists()
    extra1_data = json.load(open(sums_dir / "chapter_0004.json", "r", encoding="utf-8"))
    assert extra1_data["chapter_num"] == 4
    assert extra1_data["title"] == "Special Chapter 1"

    # Verify original chapter_0001.json and chapter_0002.json were reconstructed
    assert (sums_dir / "chapter_0001.json").exists()
    assert (sums_dir / "chapter_0002.json").exists()
    ch1_data = json.load(open(sums_dir / "chapter_0001.json", "r", encoding="utf-8"))
    assert ch1_data["chapter_num"] == 1
    assert "Chapter 1" in ch1_data["title"]

    # Verify metadata.json was updated
    updated_meta = repo.load_all_metadata()
    meta_extra1 = updated_meta[f"{out_dir.name}/004_Extra Chapter 1 - Side"]
    assert meta_extra1.chapter_num == 4
    assert meta_extra1.chapter_id == "chapter_0004"

    meta_extra2 = updated_meta[f"{out_dir.name}/005_Extra Chapter 2 - Side"]
    assert meta_extra2.chapter_num == 5
    assert meta_extra2.chapter_id == "chapter_0005"
