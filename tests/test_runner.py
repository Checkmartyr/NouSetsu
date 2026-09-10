"""Integration tests for BatchRunner and LangGraph pipeline with MockNovelLLM."""
from pathlib import Path
from rich.console import Console
from nousetsu.batch.runner import BatchRunner
from nousetsu.models.metadata import StageStatus
from nousetsu.storage.repository import NovelRepository


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


def test_update_bible_memory_evolution(tmp_path: Path):
    from nousetsu.models.bible import CharacterProfile, GlossaryItem, ChapterSummary

    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test Novel", "Japanese", "English")

    # Initial character with generic attributes
    c1 = CharacterProfile(
        name="Clara",
        original_name="クララ",
        aliases=["Lady C"],
        role="minor",
        voice="neutral",
        gender="unspecified",
        relationships={"Raymond": "acquaintance"}
    )
    g1 = GlossaryItem(
        source="魔導炉",
        target="mana furnace",
        category="term",
        notes=""
    )
    repo.update_bible_memory([c1], [g1], None)

    # Later chapter reveals new alias, specific voice, and deeper role
    c1_evolved = CharacterProfile(
        name="Clara",
        original_name="クララ",
        aliases=["Lady C", "The Silver Witch"],
        role="protagonist",
        voice="Sharp, aristocratic, slightly cynical internal monologue",
        gender="female",
        relationships={"Raymond": "ally", "Boris": "enemy"}
    )
    g1_evolved = GlossaryItem(
        source="魔導炉",
        target="mana furnace",
        category="item",
        notes="High-output ancient engine powering flying fortresses"
    )
    summary = ChapterSummary(
        chapter_num=1,
        title="Prologue",
        synopsis="Clara reveals her magic.",
        key_events=["Awakening"],
        character_state_changes=[]
    )

    repo.update_bible_memory([c1_evolved], [g1_evolved], summary)

    bible = repo.load_bible()
    char = bible.find_character("Clara")
    assert char is not None
    assert "Lady C" in char.aliases
    assert "The Silver Witch" in char.aliases
    assert char.role == "protagonist"
    assert char.voice == "Sharp, aristocratic, slightly cynical internal monologue"
    assert char.gender == "female"
    assert char.relationships["Raymond"] == "ally"
    assert char.relationships["Boris"] == "enemy"

    term = bible.find_term("魔導炉")
    assert term is not None
    assert term.category == "item"
    assert "High-output" in term.notes


def test_batch_runner_no_auto_update_bible(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test Novel", "Japanese", "English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    (input_dir / "ch_01.txt").write_text("第一章：少年の旅立ち。\n少年は剣を手に取った。", encoding="utf-8")

    console = Console(record=True)
    # Runner with auto_update_bible=False
    runner = BatchRunner(repo, model_name="mock-model", auto_update_bible=False, console=console)
    results = runner.run_batch(input_dir=input_dir, output_dir=output_dir)

    assert len(results) == 1
    assert results[0].checkpoint.status == StageStatus.COMPLETED

    # Characters and glossary should NOT have been auto-added
    bible = repo.load_bible()
    assert len(bible.characters) == 0
    assert len(bible.glossary) == 0
    # Summaries should still be tracked
    assert len(bible.summaries) == 1

