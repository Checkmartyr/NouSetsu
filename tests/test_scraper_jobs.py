"""Protocol and restart regressions use real pipes, isolated projects, and no websites."""
import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nousetsu.scraper.bridge import NovelScraperBridge, _inspection_timeout
from nousetsu.scraper.models import ScraperExtractRequest, ScraperStatusResponse
from nousetsu.scraper.jobs import write_json, job_path
from nousetsu.storage.repository import NovelRepository
from nousetsu.models.config import ProjectConfig
from nousetsu.scraper.llm_config import scraper_subprocess_environment
from nousetsu.cli import web_server


@pytest.mark.parametrize("env,expected", [
    ({}, 620),
    ({"NOVEL_SCRAPER_RECOVERY_MODE": "maximum"}, 920),
    ({"NOVEL_SCRAPER_RECOVERY_MODE": "maximum", "NOVEL_SCRAPER_DISCOVERY_SECONDS": "17",
      "NOVEL_SCRAPER_CLEANUP_SECONDS": "7"}, 39),
])
def test_inspection_timeout_matches_worker_profile(env, expected):
    assert _inspection_timeout(env) == expected


def test_inspection_timeout_inherits_worker_environment(monkeypatch):
    monkeypatch.setenv("NOVEL_SCRAPER_RECOVERY_MODE", "maximum")
    monkeypatch.delenv("NOVEL_SCRAPER_DISCOVERY_SECONDS", raising=False)
    monkeypatch.delenv("NOVEL_SCRAPER_CLEANUP_SECONDS", raising=False)
    assert _inspection_timeout(None) == 920
    assert _inspection_timeout({}) == 620


@pytest.mark.parametrize("env", [
    {"NOVEL_SCRAPER_RECOVERY_MODE": "unknown"},
    {"NOVEL_SCRAPER_DISCOVERY_SECONDS": "nan"},
    {"NOVEL_SCRAPER_DISCOVERY_SECONDS": "inf"},
    {"NOVEL_SCRAPER_DISCOVERY_SECONDS": "0"},
    {"NOVEL_SCRAPER_CLEANUP_SECONDS": "-1"},
])
def test_inspection_timeout_rejects_invalid_budgets(env):
    with pytest.raises(ValueError):
        _inspection_timeout(env)


@pytest.mark.parametrize("legacy", [False, True])
def test_inspection_metadata_survives_api_snapshot_and_extraction(tmp_path, monkeypatch, legacy):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Fixture", "Japanese", "English", model_name="mock-model")
    url = "https://fixture.test/book"
    metadata = {} if legacy else {
        "final_url": "https://fixture.test/novel/book",
        "source_scope": {"catalogs": [url], "approved_links": [url + "/chapter-1"]},
        "linked_entry_count": 1, "observed_linked_entry_count": 2,
        "highest_chapter_number": 3.5, "highest_observed_chapter_number": 5.5,
        "numbered_chapter_ranges": [{"url": url + "/chapter-1", "start": 1, "end": 3.5}],
    }
    payload = {"success": True, "url": url, "novel_title": "Fixture", "is_complete": True,
                   "chapters": [{"index": 1, "title": "Chapters 1–3.5", "url": url + "/chapter-1"}], **metadata}
    script = tmp_path / "worker.py"
    script.write_text(
        "import sys,json\nfrom pathlib import Path\n"
        "if sys.argv[1] == 'inspect':\n print(json.dumps(" + repr(payload) + "))\n"
        "else:\n snapshot=json.loads(Path(sys.argv[sys.argv.index('--snapshot-file')+1]).read_text(encoding='utf-8'))\n"
        " print(json.dumps({'type':'completed','status':'partial','success':False,'metrics':{'snapshot':snapshot},'files':[]}))\n",
        encoding="utf-8")
    bridge = NovelScraperBridge(scraper_dir=tmp_path, python_exe=Path(sys.executable))
    bridge._api_bridge_command = lambda operation, *args: [sys.executable, str(script), operation, *args]

    async def romanize(title):
        return title

    monkeypatch.setattr(bridge, "romanize_title", romanize)
    monkeypatch.setattr(web_server, "NovelScraperBridge", lambda: bridge)
    with TestClient(web_server.create_app()) as client:
        response = client.post("/api/scraper/inspect", json={"url": url, "project_path": str(tmp_path)})
    assert response.status_code == 200
    inspected = response.json()
    snapshot_path = tmp_path / ".novel" / "scraper" / "inspections" / (inspected["inspection_id"] + ".json")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot == inspected
    if legacy:
        assert snapshot["final_url"] is None
        assert snapshot["source_scope"] == {}
        assert snapshot["linked_entry_count"] is None
        assert snapshot["numbered_chapter_ranges"] == []
    else:
        assert {key: snapshot[key] for key in metadata} == metadata
    request = ScraperExtractRequest(url=url, project_path=str(tmp_path), inspection_id=inspected["inspection_id"])
    result = asyncio.run(bridge.extract_chapters(request, tmp_path / "raw_chapters"))
    assert result.metrics["snapshot"] == snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,expected", [("partial", "partial"), ("missing", "failed"), ("nonzero", "failed"), ("complete", "completed"), ("invalid_complete", "failed")])
async def test_worker_terminal_contract_and_stderr_drain(tmp_path, mode, expected):
    script = tmp_path / "worker.py"
    script.write_text(
        "import sys,json\n"
        "sys.stderr.write('diagnostic '*100000);sys.stderr.flush()\n"
        "print(json.dumps({'type':'progress','current':1,'total':2,'percent':50}),flush=True)\n"
        + ("" if mode == "missing" else "print(json.dumps(" + repr({
            "type": "completed", "success": mode in {"complete", "invalid_complete"}, "status": "partial" if mode == "partial" else "completed",
            "failed": int(mode in {"partial", "invalid_complete"}), "files": ["chapter1.md", "chapter2.md"] if mode == "complete" else [], "total_selected": 2,
            "is_complete": True,
            "outcomes": [{"index": 1, "status": "saved"}, {"index": 2, "status": "saved"}],
        }) + "),flush=True)\n")
        + ("sys.exit(2)\n" if mode == "nonzero" else ""), encoding="utf-8")
    (tmp_path / "stale.md").write_text("old chapter", encoding="utf-8")
    bridge = NovelScraperBridge(scraper_dir=tmp_path, python_exe=Path(sys.executable))
    bridge._api_bridge_command = lambda *args: [sys.executable, str(script)]
    result = await asyncio.wait_for(bridge.extract_chapters(ScraperExtractRequest(url="https://fixture.test/book"), tmp_path), 15)
    assert result.status == expected
    assert result.completed_files == (["chapter1.md", "chapter2.md"] if mode == "complete" else [])
    assert "stale.md" not in result.message


@pytest.mark.asyncio
async def test_overwrite_and_request_budgets_reach_worker(tmp_path):
    script = tmp_path / "worker.py"
    script.write_text("import os,json,sys\nprint(json.dumps({'type':'completed','status':'partial','success':False,'metrics':{'overwrite':'--overwrite' in sys.argv,'attempts':os.environ['NOVEL_SCRAPER_REQUEST_ATTEMPTS']},'files':[]}))", encoding="utf-8")
    bridge = NovelScraperBridge(scraper_dir=tmp_path, python_exe=Path(sys.executable))
    bridge._api_bridge_command = lambda operation, *args: [sys.executable, str(script), *args]
    result = await bridge.extract_chapters(ScraperExtractRequest(url="https://fixture.test", overwrite=True, budgets={"request_attempts": 2}), tmp_path)
    assert result.metrics == {"overwrite": True, "attempts": "2"}


def test_project_budget_precedence():
    config = ProjectConfig(model_name="mock-model", scraper_budgets={"toc_pages": 77})
    env = scraper_subprocess_environment(config, {"NOVEL_SCRAPER_TOC_PAGES": "12"})
    assert env["NOVEL_SCRAPER_TOC_PAGES"] == "77"


@pytest.mark.asyncio
async def test_scraper_async_provider_fallback_accepts_langchain_callback_argument():
    from nousetsu.agents.llm import FallbackChatModel, MockNovelLLM
    model = FallbackChatModel(primary=MockNovelLLM(model_name="mock-primary"),
        fallback=MockNovelLLM(model_name="mock-fallback"), primary_model_name="mock-primary", fallback_model_name="mock-fallback")
    result = await model.ainvoke("Extract a chapter selector")
    assert result.content


def test_restart_recovery_cancel_and_resume(tmp_path, monkeypatch):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Fixture", "Japanese", "English", model_name="mock-model")
    monkeypatch.setattr(web_server, "_ACTIVE_SCRAPER_JOBS", {})
    monkeypatch.setattr(web_server, "_SCRAPER_TASKS", {})
    job_id = "f" * 32
    destination = tmp_path / "raw_chapters"
    destination.mkdir(exist_ok=True)
    request = ScraperExtractRequest(url="https://fixture.test/book", project_path=str(tmp_path))
    document = {"task_id": job_id, "request": request.model_dump(), "destination": str(destination), "folder": "raw_chapters",
                "status": ScraperStatusResponse(task_id=job_id, status="running").model_dump()}
    write_json(job_path(tmp_path, job_id), document)
    resumed = []
    async def run(*args, **kwargs):
        resumed.append((args, kwargs))
    monkeypatch.setattr(web_server, "_run_scraper_task", run)
    with TestClient(web_server.create_app()) as client:
        query = {"project_path": str(tmp_path)}
        restored = client.get(f"/api/scraper/status/{job_id}", params=query)
        assert restored.status_code == 200
        assert restored.json()["status"] == "paused"
        assert client.post(f"/api/scraper/cancel/{job_id}", params=query).status_code == 200
        assert client.get(f"/api/scraper/status/{job_id}", params=query).json()["status"] == "cancelled"
        assert client.post(f"/api/scraper/resume/{job_id}", params=query).status_code == 200
    assert resumed[0][0][5] == job_id
    assert not job_path(tmp_path, job_id).with_suffix(".cancel").exists()


@pytest.mark.parametrize("location,expected_status", [
    ("project", 200),
    ("external", 200),
    ("external_volume", 200),
    ("unrelated", 400),
    ("previous_root", 400),
])
def test_resume_validates_current_source_roots(tmp_path, monkeypatch, location, expected_status):
    project = tmp_path / "project"
    repo = NovelRepository(project)
    repo.initialize_project("Fixture", "Japanese", "English", model_name="mock-model")
    cfg = repo.load_config()
    source = project / "raw_chapters" if location == "project" else tmp_path / ("previous_sources" if location == "previous_root" else "sources")
    source.mkdir(parents=True, exist_ok=True)
    cfg.raw_dir = str(source)
    repo.save_config(cfg)
    destinations = {
        "project": source,
        "external": source,
        "external_volume": source / "Vol_01",
        "unrelated": tmp_path / "unrelated",
        "previous_root": source / "Vol_01",
    }
    destination = destinations[location]
    destination.mkdir(parents=True, exist_ok=True)
    job_id = "e" * 32
    request = ScraperExtractRequest(url="https://fixture.test/book", project_path=str(project))
    document = {
        "task_id": job_id, "request": request.model_dump(), "destination": str(destination),
        "folder": source.name,
        "status": ScraperStatusResponse(task_id=job_id, status="paused").model_dump(),
    }
    write_json(job_path(project, job_id), document)
    if location == "previous_root":
        cfg.raw_dir = str(tmp_path / "current_sources")
        repo.save_config(cfg)
    marker = job_path(project, job_id).with_suffix(".cancel")
    marker.touch()
    monkeypatch.setattr(web_server, "_ACTIVE_SCRAPER_JOBS", {})
    monkeypatch.setattr(web_server, "_SCRAPER_TASKS", {})
    resumed = []

    async def run(*args, **kwargs):
        resumed.append(args)

    monkeypatch.setattr(web_server, "_run_scraper_task", run)
    with TestClient(web_server.create_app()) as client:
        response = client.post(f"/api/scraper/resume/{job_id}", params={"project_path": str(project)})
        assert response.status_code == expected_status
    if expected_status == 200:
        assert resumed[0][2] == destination.resolve()
        assert not marker.exists()
    else:
        assert resumed == []
        assert marker.exists()
        assert json.loads(job_path(project, job_id).read_text(encoding="utf-8"))["status"]["status"] == "paused"


@pytest.mark.parametrize("selection", [{"chapter_indices": []}, {"start_chapter": 4, "end_chapter": 2}, {"start_chapter": 0}])
def test_invalid_selections_are_rejected(selection):
    with pytest.raises(ValueError):
        ScraperExtractRequest(url="https://fixture.test/book", **selection)


@pytest.mark.asyncio
async def test_large_result_uses_a_job_scoped_terminal_file(tmp_path):
    job_id = "a" * 32
    state_dir = tmp_path / ".scraper"
    path = state_dir / "results" / f"{job_id}.json"
    result = {"status": "completed", "success": True, "is_complete": True,
              "total_selected": 400, "files": [f"{i}.md" for i in range(400)],
              "outcomes": [{"index": i, "status": "saved", "message": "x" * 200} for i in range(400)]}
    write_json(path, result)
    script = tmp_path / "worker.py"
    script.write_text("import json\nprint(json.dumps(" + repr({"type": "completed", "result_file": str(path)}) + "))", encoding="utf-8")
    bridge = NovelScraperBridge(scraper_dir=tmp_path, python_exe=Path(sys.executable))
    bridge._api_bridge_command = lambda *args: [sys.executable, str(script)]
    status = await bridge.extract_chapters(ScraperExtractRequest(url="https://fixture.test/book"), tmp_path, task_id=job_id)
    assert status.status == "completed" and len(status.outcomes) == 400
