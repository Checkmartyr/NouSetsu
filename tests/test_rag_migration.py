"""Unit and integration tests for RAG data migration engine."""
import argparse
from pathlib import Path
from unittest.mock import patch
import pytest

from nousetsu.cli.app import main
from nousetsu.models.bible import ArcSummary, ChapterSummary, CharacterProfile, GlossaryItem, NovelBible
from nousetsu.rag.migration import MigrationStats, migrate_project_to_rag
from nousetsu.storage.repository import NovelRepository


def test_migrate_chapter_summaries_and_arcs(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Migration Test", "English", "Thai")

    # Create folder-scoped summaries
    vol_dir = repo.summaries_dir / "Vol_01"
    vol_dir.mkdir(parents=True, exist_ok=True)
    s1 = ChapterSummary(
        chapter_num=1,
        title="Solemn Oath",
        synopsis="Sir Roderick swore to protect Princess Amelia at the royal courtyard.",
        key_events=["Roderick swore oath", "Amelia accepted fealty"],
        character_state_changes=["Roderick bound by honor"],
        folder="Vol_01"
    )
    (vol_dir / "chapter_0001.json").write_text(s1.model_dump_json(), encoding="utf-8")

    s2 = ChapterSummary(
        chapter_num=2,
        title="Obsidian Blade",
        synopsis="The dark cult attacked the inner palace with obsidian daggers.",
        key_events=["Palace attacked", "Obsidian dagger revealed"],
        folder="Vol_01"
    )
    (vol_dir / "chapter_0002.json").write_text(s2.model_dump_json(), encoding="utf-8")

    # Create arc summary
    repo.arcs_dir.mkdir(parents=True, exist_ok=True)
    arc = ArcSummary(
        arc_id="arc_0001",
        arc_num=1,
        title="The Royal Infiltration",
        synopsis="Amelia defends the palace against obsidian assassins.",
        core_conflict="Neutralize the obsidian cult",
        status="active",
        start_chapter=1,
        end_chapter=20,
        folder="Vol_01",
        key_milestones=["Palace alerted", "First assassin captured"]
    )
    (repo.arcs_dir / "arc_0001.json").write_text(arc.model_dump_json(), encoding="utf-8")

    # Run migration without live embeddings for hermetic speed
    stats = migrate_project_to_rag(repo, embed=False)

    assert stats.summaries_indexed == 2
    assert stats.arcs_indexed == 1
    assert stats.total_indexed >= 3
    assert "Vol_01" in stats.folders_scanned

    # Verify documents exist in SQLite and FTS5
    engine = repo.get_rag_engine()
    assert engine.count_documents() >= 3

    # Search for Roderick's oath
    res = engine.hybrid_search("Roderick oath", limit=2, enable_rerank=False)
    assert len(res) > 0
    assert any("Roderick" in r.content for r in res)


def test_migrate_bible_entities(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    bible = repo.initialize_project("Bible Entity Test", "English", "Thai")

    # Add characters and terms
    bible.characters.append(CharacterProfile(
        name="Amelia Barlen",
        original_name="Amelia",
        role="protagonist",
        voice="calm and authoritative",
        relationships={"Roderick": "loyal knight"}
    ))
    bible.glossary.append(GlossaryItem(
        source="Obsidian Dagger",
        target="กริชออบซิเดียน",
        category="weapon",
        notes="Ancient cursed relic of the dark cult"
    ))
    repo.save_bible(bible)

    stats = migrate_project_to_rag(
        repo,
        include_summaries=False,
        include_arcs=False,
        include_chunks=False,
        embed=False
    )

    assert stats.characters_indexed >= 1
    assert stats.glossary_indexed >= 1

    engine = repo.get_rag_engine()
    res = engine.hybrid_search("Obsidian Dagger relic", limit=1, enable_rerank=False)
    assert len(res) == 1
    assert "Obsidian Dagger" in res[0].title


def test_migrate_translated_scene_chunks(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Chunk Migration Test", "English", "Thai")

    # Create output directory and translated markdown file
    out_dir = tmp_path / "Vol_01_th"
    out_dir.mkdir()

    # 45 lines of prose
    lines = [f"This is line number {i} of the translated Thai prose story." for i in range(1, 46)]
    (out_dir / "001_Chapter 1 - The Awakening.md").write_text("\n".join(lines), encoding="utf-8")

    stats = migrate_project_to_rag(
        repo,
        include_summaries=False,
        include_arcs=False,
        include_bible=False,
        include_chunks=True,
        folder_filter="Vol_01",
        chunk_size_lines=20,
        embed=False
    )

    # 45 lines / 20 = 3 chunks (20, 20, 5)
    assert stats.chunks_indexed == 3

    engine = repo.get_rag_engine()
    assert engine.count_documents() == 3
    doc = engine.get_document("chunk:Vol_01:0001:001")
    assert doc is not None
    assert doc.chapter_num == 1
    assert "The Awakening" in doc.title


def test_migrate_rag_dry_run(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Dry Run Test", "English", "Thai")

    vol_dir = repo.summaries_dir / "Vol_01"
    vol_dir.mkdir(parents=True, exist_ok=True)
    s1 = ChapterSummary(chapter_num=1, synopsis="Test Synopsis", folder="Vol_01")
    (vol_dir / "chapter_0001.json").write_text(s1.model_dump_json(), encoding="utf-8")

    stats = migrate_project_to_rag(repo, dry_run=True)

    assert stats.summaries_indexed == 1
    assert stats.total_indexed >= 1
    # Dry run should not write to lore.db
    assert not repo.rag_db_path.exists()


def test_cli_migrate_rag_command(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("CLI Migrate Test", "English", "Thai")

    vol_dir = repo.summaries_dir / "Vol_01"
    vol_dir.mkdir(parents=True, exist_ok=True)
    s1 = ChapterSummary(chapter_num=1, synopsis="CLI Synopsis", folder="Vol_01")
    (vol_dir / "chapter_0001.json").write_text(s1.model_dump_json(), encoding="utf-8")

    # Test CLI invocation with --no-embed and --dry-run
    test_args = ["nousetsu", "migrate-rag", "-p", str(tmp_path), "--no-embed", "--dry-run"]
    with patch("sys.argv", test_args):
        main()

    # Test actual live execution
    test_args_live = ["nousetsu", "migrate-rag", "-p", str(tmp_path), "--no-embed"]
    with patch("sys.argv", test_args_live):
        main()

    engine = repo.get_rag_engine()
    assert engine.count_documents() >= 1
