"""Unit tests for multi-folder translation support, folder-scoped summaries, and folder switching."""
from pathlib import Path
import pytest
from nousetsu.models.bible import ChapterSummary, NovelBible
from nousetsu.models.metadata import ChapterMetadata, CheckpointData, PipelineStage, StageStatus
from nousetsu.storage.repository import NovelRepository
from nousetsu.tui.app import NovelAgentApp
from nousetsu.tui.widgets.folder_select_modal import FolderSelectModal


def test_discover_folders(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test Multi-Folder Novel", "Japanese", "English")

    # Create folder structure with multiple volumes
    vol4 = tmp_path / "Villainess_04"
    vol4_out = tmp_path / "Villainess_04_th"
    vol5 = tmp_path / "Villainess_05"
    vol5_out = tmp_path / "Villainess_05_th"
    ignored = tmp_path / ".git"

    vol4.mkdir()
    vol4_out.mkdir()
    vol5.mkdir()
    vol5_out.mkdir()
    ignored.mkdir()

    # Add dummy files
    (vol4 / "001.txt").write_text("Ch 1 text", encoding="utf-8")
    (vol4 / "002.txt").write_text("Ch 2 text", encoding="utf-8")
    (vol5 / "001.txt").write_text("Ch 1 text v5", encoding="utf-8")
    (ignored / "config.txt").write_text("git stuff", encoding="utf-8")

    folders = repo.discover_folders()
    raw_names = [f[0] for f in folders]
    assert "Villainess_04" in raw_names
    assert "Villainess_05" in raw_names
    assert "Villainess_04_th" not in raw_names
    assert ".git" not in raw_names

    v4_info = next(f for f in folders if f[0] == "Villainess_04")
    assert v4_info[1] == "Villainess_04_th"
    assert v4_info[2] == 2

    v5_info = next(f for f in folders if f[0] == "Villainess_05")
    assert v5_info[1] == "Villainess_05_th"
    assert v5_info[2] == 1


def test_folder_scoped_summaries_and_replacement(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    bible = repo.initialize_project("Test Multi-Folder Novel", "Japanese", "English")

    # 1. Add Chapter 1 and 2 for FolderA (e.g. Volume 4)
    summary_v4_1 = ChapterSummary(
        chapter_num=1,
        title="V4 Chapter 1",
        synopsis="Volume 4 events start.",
        folder="Villainess_04"
    )
    summary_v4_2 = ChapterSummary(
        chapter_num=2,
        title="V4 Chapter 2",
        synopsis="Volume 4 events continue.",
        folder="Villainess_04"
    )
    repo.update_bible_memory(new_characters=[], new_terms=[], summary=summary_v4_1, folder="Villainess_04")
    repo.update_bible_memory(new_characters=[], new_terms=[], summary=summary_v4_2, folder="Villainess_04")

    # Verify summaries are saved in Villainess_04 subfolder
    v4_dir = repo.summaries_dir / "Villainess_04"
    assert (v4_dir / "chapter_0001.json").exists()
    assert (v4_dir / "chapter_0002.json").exists()

    # 2. Add Chapter 1 for FolderB (e.g. Volume 5)
    summary_v5_1 = ChapterSummary(
        chapter_num=1,
        title="V5 Chapter 1",
        synopsis="Volume 5 initial event.",
        folder="Villainess_05"
    )
    repo.update_bible_memory(new_characters=[], new_terms=[], summary=summary_v5_1, folder="Villainess_05")

    # Verify summaries are saved in Villainess_05 subfolder without corrupting Villainess_04
    v5_dir = repo.summaries_dir / "Villainess_05"
    assert (v5_dir / "chapter_0001.json").exists()
    assert (v4_dir / "chapter_0001.json").exists()

    # 3. Reload fresh Bible and check scoped queries
    loaded_bible = repo.load_bible()
    v4_summaries = loaded_bible.get_summaries_for_folder("Villainess_04")
    v5_summaries = loaded_bible.get_summaries_for_folder("Villainess_05")

    assert len(v4_summaries) == 2
    assert v4_summaries[0].title == "V4 Chapter 1"
    assert v4_summaries[1].title == "V4 Chapter 2"

    assert len(v5_summaries) == 1
    assert v5_summaries[0].title == "V5 Chapter 1"

    # 4. Replace Chapter 1 in FolderB with revised version
    revised_v5_1 = ChapterSummary(
        chapter_num=1,
        title="V5 Chapter 1 (Revised)",
        synopsis="Volume 5 revised plot synopsis.",
        folder="Villainess_05"
    )
    repo.update_bible_memory(new_characters=[], new_terms=[], summary=revised_v5_1, folder="Villainess_05")

    # Check that replacement happened cleanly in FolderB, but FolderA remains untouched
    reloaded = repo.load_bible()
    v5_after = reloaded.get_summaries_for_folder("Villainess_05")
    assert len(v5_after) == 1
    assert v5_after[0].title == "V5 Chapter 1 (Revised)"

    v4_after = reloaded.get_summaries_for_folder("Villainess_04")
    assert len(v4_after) == 2
    assert v4_after[0].title == "V4 Chapter 1"


def test_metadata_isolation_between_folders(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test Novel", "Japanese", "English")

    out_v4 = tmp_path / "Villainess_04_th" / "001_Chapter 1.md"
    out_v5 = tmp_path / "Villainess_05_th" / "001_Chapter 1.md"
    out_v4.parent.mkdir()
    out_v5.parent.mkdir()

    meta_v4 = ChapterMetadata(
        chapter_id="v4_ch1",
        chapter_num=1,
        source_file="Villainess_04/001_Chapter 1.txt",
        source_sha256="hash_v4",
        output_file=str(out_v4),
        model="mock-model",
        checkpoint=CheckpointData(status=StageStatus.COMPLETED, last_completed_stage=PipelineStage.CHRONICLING)
    )
    meta_v5 = ChapterMetadata(
        chapter_id="v5_ch1",
        chapter_num=1,
        source_file="Villainess_05/001_Chapter 1.txt",
        source_sha256="hash_v5",
        output_file=str(out_v5),
        model="mock-model",
        checkpoint=CheckpointData(status=StageStatus.PAUSED, last_completed_stage=PipelineStage.DRAFTING)
    )

    repo.save_metadata(meta_v4, out_v4)
    repo.save_metadata(meta_v5, out_v5)

    loaded_v4 = repo.load_metadata(out_v4)
    loaded_v5 = repo.load_metadata(out_v5)

    assert loaded_v4 is not None
    assert loaded_v4.chapter_id == "v4_ch1"
    assert loaded_v4.checkpoint.status == StageStatus.COMPLETED

    assert loaded_v5 is not None
    assert loaded_v5.chapter_id == "v5_ch1"
    assert loaded_v5.checkpoint.status == StageStatus.PAUSED


@pytest.mark.asyncio
async def test_tui_folder_selector_modal(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test TUI Multi-Folder", "Japanese", "English")

    vol4 = tmp_path / "Villainess_04"
    vol4_out = tmp_path / "Villainess_04_th"
    vol5 = tmp_path / "Villainess_05"
    vol5_out = tmp_path / "Villainess_05_th"
    vol4.mkdir()
    vol4_out.mkdir()
    vol5.mkdir()
    vol5_out.mkdir()

    (vol4 / "001.txt").write_text("Vol 4 ch 1", encoding="utf-8")
    (vol5 / "001.txt").write_text("Vol 5 ch 1", encoding="utf-8")
    (vol5 / "002.txt").write_text("Vol 5 ch 2", encoding="utf-8")

    app = NovelAgentApp(
        input_dir=str(vol4),
        output_dir=str(vol4_out),
        model_name="mock-model",
        project_dir=tmp_path
    )

    async with app.run_test() as pilot:
        # Initially on vol4 (1 chapter)
        assert len(app.current_tasks) == 1

        # Open folder selector modal via action
        app.action_open_folder_selector()
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, FolderSelectModal)

        # Switch folder to vol5
        app.switch_folder("Villainess_05", "Villainess_05_th")
        await pilot.pause()

        # Check tasks reloaded with vol5 (2 chapters)
        assert len(app.current_tasks) == 2
        assert app.input_dir == vol5
