"""Source-root discovery, mirrored volume outputs, and nested chapter isolation."""
from fastapi.testclient import TestClient

from nousetsu.batch.scanner import ChapterScanner
from nousetsu.batch.runner import BatchRunner
from nousetsu.cli.web_server import create_app
from nousetsu.models.bible import ChapterSummary
from nousetsu.models.metadata import ChapterMetadata
from nousetsu.storage.repository import NovelRepository


def make_project(tmp_path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Volumes", "Japanese", "English", model_name="mock-model")
    for folder in ("Volume_2", "Volume_10", "Arc_A/Volume_1", "Arc_B/Volume_1"):
        source = tmp_path / "raw_chapters" / folder / "0001.txt"
        source.parent.mkdir(parents=True)
        source.write_text(folder, encoding="utf-8")
    return repo


def test_source_root_discovers_nested_volumes_and_mirrors_outputs(tmp_path):
    repo = make_project(tmp_path)
    pairs = repo.discover_folders()
    assert ("raw_chapters/Volume_2", "translated_chapters/Volume_2", 1) in pairs
    assert ("raw_chapters/Arc_A/Volume_1", "translated_chapters/Arc_A/Volume_1", 1) in pairs
    assert [raw for raw, _, _ in pairs].index("raw_chapters/Volume_2") < [raw for raw, _, _ in pairs].index("raw_chapters/Volume_10")
    scanner = ChapterScanner(repo)
    tasks = scanner.scan_project(parallel=False)
    assert len(tasks) == 4
    assert len({task.folder for task in tasks}) == 4
    for task in tasks:
        relative = task.source_file.relative_to(tmp_path / "raw_chapters")
        assert task.output_file == tmp_path / "translated_chapters" / relative.with_suffix(".md")
    chosen = scanner.scan_project(folder="raw_chapters/Arc_B/Volume_1", parallel=False)
    assert len(chosen) == 1
    assert chosen[0].folder == "raw_chapters/Arc_B/Volume_1"


def test_translated_and_hidden_subtrees_are_not_sources(tmp_path):
    repo = make_project(tmp_path)
    cfg = repo.load_config()
    cfg.output_dir = "raw_chapters/translated"
    repo.save_config(cfg)
    for folder in ("translated/Volume_3", ".cache/Volume_3"):
        file = tmp_path / "raw_chapters" / folder / "0002.md"
        file.parent.mkdir(parents=True)
        file.write_text("Not source", encoding="utf-8")
    assert len(ChapterScanner(repo).scan_project(parallel=False)) == 4


def test_nested_metadata_and_summaries_keep_same_number_volumes_separate(tmp_path):
    repo = make_project(tmp_path)
    tasks = ChapterScanner(repo).scan_project(parallel=False)
    first = next(t for t in tasks if t.folder == "raw_chapters/Arc_A/Volume_1")
    second = next(t for t in tasks if t.folder == "raw_chapters/Arc_B/Volume_1")
    for task in (first, second):
        meta = ChapterMetadata(chapter_id=task.folder, chapter_num=1, source_file=str(task.source_file), source_sha256="hash", output_file=str(task.output_file))
        repo.save_metadata(meta, task.output_file)
        summary = ChapterSummary(chapter_num=1, title=task.folder, synopsis=task.folder, folder=task.folder)
        repo.update_bible_memory([], [], summary, folder=task.folder)
    assert repo.load_metadata(first.output_file).chapter_id == first.folder
    assert repo.load_metadata(second.output_file).chapter_id == second.folder
    scanned = {t.folder: t for t in ChapterScanner(repo).scan_project(parallel=False)}
    assert scanned[first.folder].existing_meta.chapter_id == first.folder
    assert scanned[second.folder].existing_meta.chapter_id == second.folder
    assert scanned["raw_chapters/Volume_2"].existing_meta is None
    summaries = repo.load_bible().summaries
    assert {s.folder for s in summaries} == {first.folder, second.folder}
    first.source_file.unlink()
    second.source_file.unlink()
    assert {first.folder, second.folder}.issubset(repo.get_folder_order())


def test_workspace_settings_folders_content_and_nested_upload(tmp_path):
    repo = make_project(tmp_path)
    client = TestClient(create_app())
    params = {"project_path": str(tmp_path)}
    settings = client.get("/api/settings", params=params).json()
    assert {p["raw_dir"] for p in settings["workspace_folders"]} == {raw for raw, _, _ in repo.discover_folders()}
    folders = client.get("/api/folders", params=params).json()
    assert "raw_chapters/Arc_A/Volume_1" in folders["folders"]
    output = tmp_path / "translated_chapters/Arc_A/Volume_1/0001.md"
    output.parent.mkdir(parents=True)
    output.write_text("Translated A", encoding="utf-8")
    content = client.get("/api/chapters/1/content", params={**params, "folder": "raw_chapters/Arc_A/Volume_1"}).json()
    assert content["source_text"] == "Arc_A/Volume_1"
    assert content["translated_text"] == "Translated A"
    folders = client.get("/api/folders", params=params).json()
    assert "translated_chapters/Arc_A/Volume_1" in {f["folder"] for f in folders["translated_folders"]}
    upload = client.post("/api/chapters/upload", json={**params, "folder": "raw_chapters/Volume_3", "files": [{"name": "0001.txt", "content": "New volume"}]})
    assert upload.status_code == 200
    assert (tmp_path / "translated_chapters/Volume_3").is_dir()
    revision = client.get("/api/settings", params=params).headers["etag"]
    saved = client.put("/api/settings", params=params, headers={"If-Match": revision}, json={"raw_dir": "raw_chapters/Arc_A", "output_dir": "published"})
    assert saved.status_code == 200
    assert saved.json()["workspace_folders"] == [{"raw_dir": "raw_chapters/Arc_A/Volume_1", "output_dir": "published/Volume_1", "chapter_count": 1}]
    tasks = ChapterScanner(repo).scan_project(parallel=False)
    assert len(tasks) == 1
    assert tasks[0].output_file == tmp_path / "published/Volume_1/0001.md"


def test_nested_volume_translation_keeps_memory_and_traces_scoped(tmp_path):
    repo = make_project(tmp_path)
    tasks = [task for task in ChapterScanner(repo).scan_project(parallel=False) if "/Arc_" in task.folder]
    runner = BatchRunner(repo, model_name="mock-model", max_review_loops=1, enable_rag=False, enable_procedural_graph_learning=False)
    for task in tasks:
        runner.run_chapter(task)
        assert repo.get_trace_file_path(1, task.folder).is_file()
    assert {summary.folder for summary in repo.load_bible().summaries} == {task.folder for task in tasks}
    client = TestClient(create_app())
    traces = client.get("/api/traces", params={"project_path": str(tmp_path)}).json()
    assert {chapter["folder"] for chapter in traces["chapters"]} == {task.folder for task in tasks}


def test_absolute_roots_outside_project_discover_and_select_volumes(tmp_path):
    repo = NovelRepository(tmp_path / "Project")
    repo.initialize_project("External", "Japanese", "English", model_name="mock-model")
    cfg = repo.load_config()
    cfg.raw_dir = str(tmp_path / "Inputs")
    cfg.output_dir = str(tmp_path / "Published")
    repo.save_config(cfg)
    source = tmp_path / "Inputs/Arc_A/Volume_1/0001.txt"
    source.parent.mkdir(parents=True)
    source.write_text("External chapter", encoding="utf-8")
    tasks = ChapterScanner(repo).scan_project(parallel=False)
    assert len(tasks) == 1
    assert tasks[0].folder == "Inputs/Arc_A/Volume_1"
    assert tasks[0].output_file == tmp_path / "Published/Arc_A/Volume_1/0001.md"
    chosen = ChapterScanner(repo).scan_project(folder=tasks[0].folder, parallel=False)
    assert len(chosen) == 1
    assert chosen[0].source_file == source
    client = TestClient(create_app())
    params = {"project_path": str(repo.root_dir), "folder": tasks[0].folder}
    assert client.get("/api/chapters/1/content", params=params).json()["source_text"] == "External chapter"
    upload = client.post("/api/chapters/upload", json={"project_path": str(repo.root_dir), "folder": "Inputs/Volume_2", "files": [{"name": "0001.txt", "content": "Second volume"}]})
    assert upload.status_code == 200
    assert (tmp_path / "Inputs/Volume_2/0001.txt").is_file()
    assert (tmp_path / "Published/Volume_2").is_dir()
    output = tasks[0].output_file
    output.parent.mkdir(parents=True)
    output.write_text("Translated external", encoding="utf-8")
    from nousetsu.ebook.writer import _resolve_export_output_dir
    assert _resolve_export_output_dir(repo, folder="Published/Arc_A/Volume_1")[0] == output.parent
