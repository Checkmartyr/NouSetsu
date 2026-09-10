"""Unit tests for chapter scanner and natural sorting."""
from pathlib import Path
from src.batch.scanner import ChapterScanner
from src.storage.repository import NovelRepository


def test_chapter_scanner_extraction(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    scanner = ChapterScanner(repo)

    assert scanner.extract_chapter_num(Path("chapter_001.txt"), 99) == 1
    assert scanner.extract_chapter_num(Path("ch10_battle.md"), 99) == 10
    assert scanner.extract_chapter_num(Path("042 - The Return.txt"), 99) == 42
    assert scanner.extract_chapter_num(Path("prologue.txt"), 99) == 99


def test_chapter_scanner_natural_sort(tmp_path: Path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    # Create files out of order
    for name in ["chapter_10.txt", "chapter_1.txt", "chapter_2.txt"]:
        (input_dir / name).write_text(f"Content of {name}", encoding="utf-8")

    repo = NovelRepository(tmp_path)
    scanner = ChapterScanner(repo)
    tasks = scanner.scan_directory(input_dir, output_dir)

    # Verify natural order: 1, 2, 10
    filenames = [t.source_file.name for t in tasks]
    assert filenames == ["chapter_1.txt", "chapter_2.txt", "chapter_10.txt"]
    assert [t.chapter_num for t in tasks] == [1, 2, 10]
