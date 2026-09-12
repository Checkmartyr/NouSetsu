"""Unit tests for summary system migration."""
from argparse import Namespace
from pathlib import Path
import pytest
from nousetsu.cli.app import cmd_migrate_summaries
from nousetsu.models.bible import ChapterSummary, NovelBible
from nousetsu.storage.migration import migrate_novel_summaries
from nousetsu.storage.repository import NovelRepository


def _create_dummy_summary(num: int, folder: str, title: str = "") -> ChapterSummary:
    return ChapterSummary(
        chapter_num=num,
        title=title or f"Chapter {num}",
        synopsis=f"Synopsis for {folder} chapter {num}.",
        key_events=[f"Event {num}"],
        character_state_changes=[],
        folder=folder
    )


def test_migrate_novel_summaries_generic(tmp_path: Path):
    """Test generic migration for a multi-volume project."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project(title="Generic Epic", raw_dir="Vol_02", output_dir="Vol_02_out")

    # Add 3 chapters to Vol_01
    for i in range(1, 4):
        repo.update_bible_memory(
            new_characters=[],
            new_terms=[],
            summary=_create_dummy_summary(i, "Vol_01"),
            folder="Vol_01"
        )

    # Add 2 chapters to Vol_02
    for i in range(1, 3):
        repo.update_bible_memory(
            new_characters=[],
            new_terms=[],
            summary=_create_dummy_summary(i, "Vol_02"),
            folder="Vol_02"
        )

    res = migrate_novel_summaries(repo=repo, dry_run=False)

    assert len(res["archived_arcs"]) == 1
    assert res["archived_arcs"][0]["arc_num"] == 1
    assert res["archived_arcs"][0]["status"] == "completed"
    assert res["archived_arcs"][0]["folder"] == "Vol_01"
    assert res["archived_arcs"][0]["start_chapter"] == 1
    assert res["archived_arcs"][0]["end_chapter"] == 3

    assert res["active_arc"] is not None
    assert res["active_arc"]["arc_num"] == 2
    assert res["active_arc"]["status"] == "active"
    assert res["active_arc"]["folder"] == "Vol_02"
    assert res["active_arc"]["start_chapter"] == 1

    assert res["whole_story_summary"] != ""
    assert (tmp_path / ".novel" / "summaries" / "arcs" / "arc_0001.json").exists()
    assert (tmp_path / ".novel" / "summaries" / "arcs" / "arc_0002.json").exists()


def test_migrate_novel_summaries_villainess_profile(tmp_path: Path):
    """Test migration with known Villainess profile."""
    villainess_dir = tmp_path / "Villainess"
    villainess_dir.mkdir(parents=True, exist_ok=True)
    repo = NovelRepository(villainess_dir)
    repo.initialize_project(title="Ascendance of a Bookworm", raw_dir="Villainess_05", output_dir="Villainess_05_th")

    # Add 2 chapters to Villainess_04
    for i in range(1, 3):
        repo.update_bible_memory(
            new_characters=[],
            new_terms=[],
            summary=_create_dummy_summary(i, "Villainess_04"),
            folder="Villainess_04"
        )

    # Add 1 chapter to Villainess_05
    repo.update_bible_memory(
        new_characters=[],
        new_terms=[],
        summary=_create_dummy_summary(1, "Villainess_05"),
        folder="Villainess_05"
    )

    res = migrate_novel_summaries(repo=repo, dry_run=False)

    assert res["title"] == "The Villainess"
    assert "Ifia strives to survive" in res["whole_story_summary"]
    assert len(res["archived_arcs"]) == 1
    assert res["archived_arcs"][0]["title"] == "Homeland Return & Royal Strife"
    assert res["archived_arcs"][0]["status"] == "completed"

    assert res["active_arc"]["title"] == "The Duller Exorcism"
    assert res["active_arc"]["status"] == "active"


def test_migrate_cli_command(tmp_path: Path, capsys):
    """Test nousetsu migrate-summaries CLI execution."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project(title="Old Novel", raw_dir="Vol_01", output_dir="out")

    repo.update_bible_memory(
        new_characters=[],
        new_terms=[],
        summary=_create_dummy_summary(1, "Vol_01"),
        folder="Vol_01"
    )

    args = Namespace(project_dir=str(tmp_path), title="New Novel", dry_run=False)
    cmd_migrate_summaries(args)

    captured = capsys.readouterr()
    assert "Migration Complete: New Novel" in captured.out
    assert "Story Arcs" in captured.out
