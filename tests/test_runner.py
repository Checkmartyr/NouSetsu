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


def test_batch_runner_chapter_filter(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test Novel", "Japanese", "English")

    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    # Create multiple chapters
    (input_dir / "001_Chapter 1 - Awakening.txt").write_text("第一章：覚醒。\n少年は目覚めた。", encoding="utf-8")
    (input_dir / "002_Chapter 2 - Journey.txt").write_text("第二章：旅立ち。\n少年は歩き出した。", encoding="utf-8")
    (input_dir / "048_Chapter 48 - Displaying True Skills.txt").write_text("第四十八章：実力発揮。\n少女は戦った。", encoding="utf-8")

    console = Console(record=True)
    runner = BatchRunner(repo, model_name="mock-model", console=console)

    # Filter by numeric int
    results = runner.run_batch(input_dir=input_dir, output_dir=output_dir, chapter_filter=48)
    assert len(results) == 1
    assert results[0].chapter_num == 48
    assert (output_dir / "048_Chapter 48 - Displaying True Skills.md").exists()
    assert not (output_dir / "001_Chapter 1 - Awakening.md").exists()
    assert not (output_dir / "002_Chapter 2 - Journey.md").exists()

    # Filter by string pattern
    results_pattern = runner.run_batch(input_dir=input_dir, output_dir=output_dir, chapter_filter="Journey")
    assert len(results_pattern) == 1
    assert results_pattern[0].chapter_num == 2
    assert (output_dir / "002_Chapter 2 - Journey.md").exists()

    # Filter by common chapter prefixes like "ch 48", "ch. 1", "Chapter 1", "048"
    results_prefix1 = runner.run_batch(input_dir=input_dir, output_dir=output_dir, chapter_filter="ch 48", force_retranslate=True)
    assert len(results_prefix1) == 1
    assert results_prefix1[0].chapter_num == 48

    results_prefix2 = runner.run_batch(input_dir=input_dir, output_dir=output_dir, chapter_filter="ch. 1", force_retranslate=True)
    assert len(results_prefix2) == 1
    assert results_prefix2[0].chapter_num == 1

    results_prefix3 = runner.run_batch(input_dir=input_dir, output_dir=output_dir, chapter_filter="048", force_retranslate=True)
    assert len(results_prefix3) == 1
    assert results_prefix3[0].chapter_num == 48

    # Non-matching chapter filter returns empty list cleanly
    results_none = runner.run_batch(input_dir=input_dir, output_dir=output_dir, chapter_filter=999)
    assert len(results_none) == 0


def test_cli_chapter_filter_argument():
    import argparse
    from unittest.mock import patch
    import sys
    from nousetsu.cli.app import main

    # Verify --chapter and -c flag parse properly in CLI subparser
    test_args = ["nousetsu", "batch", "-p", "dummy", "--chapter", "48"]
    with patch.object(sys, "argv", test_args):
        with patch("nousetsu.cli.app.cmd_batch") as mock_cmd:
            main()
            mock_cmd.assert_called_once()
            assert mock_cmd.call_args[0][0].chapter == "48"

    test_args_short = ["nousetsu", "batch", "-p", "dummy", "-c", "048"]
    with patch.object(sys, "argv", test_args_short):
        with patch("nousetsu.cli.app.cmd_batch") as mock_cmd:
            main()
            mock_cmd.assert_called_once()
            assert mock_cmd.call_args[0][0].chapter == "048"


def test_batch_runner_rag_flag_propagation(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test RAG Flags", "Japanese", "English")

    # 1. Default inherits enabled RAG and Reranker
    runner_default = BatchRunner(repo, model_name="mock-model")
    assert runner_default.workflow.enable_rag is True
    assert runner_default.workflow.enable_rag_reranker is True

    # 2. Explicit enable_rag=False disables RAG in workflow
    runner_no_rag = BatchRunner(repo, model_name="mock-model", enable_rag=False)
    assert runner_no_rag.workflow.enable_rag is False
    assert runner_no_rag.workflow.rag_engine is None

    # 3. Explicit enable_rag_reranker=False disables reranker in workflow
    runner_no_rerank = BatchRunner(repo, model_name="mock-model", enable_rag=True, enable_rag_reranker=False)
    assert runner_no_rerank.workflow.enable_rag is True
    assert runner_no_rerank.workflow.enable_rag_reranker is False


def test_cli_batch_rag_and_rerank_arguments():
    from unittest.mock import patch
    import sys
    from nousetsu.cli.app import main

    test_args = ["nousetsu", "batch", "-p", "dummy", "--no-rag", "--no-rerank"]
    with patch.object(sys, "argv", test_args):
        with patch("nousetsu.cli.app.cmd_batch") as mock_cmd:
            main()
            mock_cmd.assert_called_once()
            parsed_args = mock_cmd.call_args[0][0]
            assert parsed_args.rag is False
            assert parsed_args.rerank is False


