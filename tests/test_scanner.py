"""Unit tests for chapter scanner and natural sorting."""
from pathlib import Path
from nousetsu.batch.scanner import ChapterScanner
from nousetsu.storage.repository import NovelRepository


def test_chapter_scanner_extraction(tmp_path: Path):
    repo = NovelRepository(tmp_path)
    scanner = ChapterScanner(repo)

    assert scanner.extract_chapter_num(Path("chapter_001.txt"), 99) == 1
    assert scanner.extract_chapter_num(Path("ch10_battle.md"), 99) == 10
    assert scanner.extract_chapter_num(Path("042 - The Return.txt"), 99) == 42
    assert scanner.extract_chapter_num(Path("prologue.txt"), 99) == 99

    # Modifier and volume sequence tests
    assert scanner.extract_chapter_num(Path("035_Extra Chapter 1 - Don't Live Your Past.txt"), 99) == 35
    assert scanner.extract_chapter_num(Path("036_Side Story 2 - Encounter.md"), 99) == 36
    assert scanner.extract_chapter_num(Path("040_番外編 3.txt"), 99) == 40
    assert scanner.extract_chapter_num(Path("044_Special 10.txt"), 99) == 44
    assert scanner.extract_chapter_num(Path("Vol 2 Chapter 15.txt"), 99) == 15


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


def test_chapter_scanner_collision_resolution(tmp_path: Path):
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    output_dir.mkdir()

    # Files with colliding chapter numbers (no leading sequence prefix)
    for name in ["Chapter 1.txt", "Chapter 2.txt", "Extra Chapter 1.txt"]:
        (input_dir / name).write_text(f"Content of {name}", encoding="utf-8")

    repo = NovelRepository(tmp_path)
    scanner = ChapterScanner(repo)
    tasks = scanner.scan_directory(input_dir, output_dir)

    # Natural sort order: Chapter 1, Chapter 2, Extra Chapter 1
    # Extra Chapter 1 initially extracts 1, collides with Chapter 1, and auto-realigns to 3
    assert [t.source_file.name for t in tasks] == ["Chapter 1.txt", "Chapter 2.txt", "Extra Chapter 1.txt"]
    assert [t.chapter_num for t in tasks] == [1, 2, 3]


def test_scanner_projects_dir_resolution(tmp_path: Path, monkeypatch):
    """Verify ChapterScanner resolves project short names from NOVEL_PROJECTS_DIR."""
    projects_dir = tmp_path / "my_novels"
    projects_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NOVEL_PROJECTS_DIR", str(projects_dir))

    # Initialize a project inside NOVEL_PROJECTS_DIR
    proj_dir = projects_dir / "Ascendance"
    repo = NovelRepository(proj_dir)
    repo.initialize_project(title="Ascendance of a Bookworm")

    # Raw chapter in Ascendance
    raw_dir = proj_dir / "raw_chapters"
    (raw_dir / "0001.txt").write_text("第1章 本が好き。", encoding="utf-8")

    # 1. Resolve by short name
    scanner = ChapterScanner("Ascendance")
    assert scanner.repo.root_dir.resolve() == proj_dir.resolve()
    tasks = scanner.scan_project()
    assert len(tasks) == 1
    assert tasks[0].chapter_num == 1

    # 2. Resolve default active project
    from nousetsu.storage.repository import ProjectRegistry
    ProjectRegistry().set_last_active_project(proj_dir)
    scanner_default = ChapterScanner()
    assert scanner_default.repo.root_dir.resolve() == proj_dir.resolve()


def test_scanner_scan_project_multi_volume(tmp_path: Path):
    """Verify ChapterScanner.scan_project handles both default and volume subdirectories."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project()

    # Volume 1 in default raw_chapters
    raw_dir = tmp_path / "raw_chapters"
    (raw_dir / "0001.txt").write_text("Ch 1", encoding="utf-8")
    (raw_dir / "0002.txt").write_text("Ch 2", encoding="utf-8")

    # Volume 2 in subfolder
    vol2_dir = tmp_path / "Volume_02"
    vol2_dir.mkdir()
    (vol2_dir / "0050.txt").write_text("Ch 50", encoding="utf-8")

    scanner = ChapterScanner(repo)

    # 1. Scan all (default)
    all_tasks = scanner.scan_project()
    assert len(all_tasks) == 3
    task_folders = {t.folder for t in all_tasks}
    assert "raw_chapters" in task_folders
    assert "Volume_02" in task_folders

    # 2. Scan specific volume
    vol2_tasks = scanner.scan_project(folder="Volume_02")
    assert len(vol2_tasks) == 1
    assert vol2_tasks[0].chapter_num == 50
    assert vol2_tasks[0].folder == "Volume_02"


def test_scanner_scan_all_projects(tmp_path: Path):
    """Verify ChapterScanner.scan_all_projects discovers and scans multiple novel projects."""
    p1 = tmp_path / "Novel_Alpha"
    p2 = tmp_path / "Novel_Beta"

    repo1 = NovelRepository(p1)
    repo1.initialize_project(title="Alpha")
    (p1 / "raw_chapters" / "0001.txt").write_text("Alpha Ch 1", encoding="utf-8")

    repo2 = NovelRepository(p2)
    repo2.initialize_project(title="Beta")
    (p2 / "raw_chapters" / "0001.txt").write_text("Beta Ch 1", encoding="utf-8")
    (p2 / "raw_chapters" / "0002.txt").write_text("Beta Ch 2", encoding="utf-8")

    res = ChapterScanner.scan_all_projects(projects_root=tmp_path)
    assert "Novel_Alpha" in res
    assert "Novel_Beta" in res
    assert len(res["Novel_Alpha"]) == 1
    assert len(res["Novel_Beta"]) == 2


def test_scanner_speed_and_lazy_sha256(tmp_path: Path):
    """Verify fast scanning and lazy SHA-256 computation for uncompleted chapters."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project()
    raw_dir = tmp_path / "raw_chapters"
    out_dir = tmp_path / "translated_chapters"

    # Create 50 chapters
    for i in range(1, 51):
        (raw_dir / f"{i:04d}.txt").write_text(f"Chapter {i} text line\nSecond line", encoding="utf-8")

    scanner = ChapterScanner(repo)
    scanner.clear_sha256_cache()

    import time
    t0 = time.perf_counter()
    tasks = scanner.scan_directory(raw_dir, out_dir)
    elapsed = time.perf_counter() - t0

    assert len(tasks) == 50
    # 50 chapters should scan in well under 250ms (typically ~5ms)
    assert elapsed < 0.25

    # Check lazy sha256 computation
    t = tasks[0]
    assert t._source_sha256 == ""  # Was not hashed upfront during scan
    sha = t.source_sha256  # Trigger lazy computation
    assert len(sha) == 64
    assert t._source_sha256 == sha


