"""Unit and integration tests for Nousetsu Web Server and TUI Sync APIs."""
import json
import io
import socketserver
import threading
import urllib.request
from urllib.parse import urlencode
from pathlib import Path
import pytest

from nousetsu.cli.web_server import (
    _get_project_meta,
    _load_project_traces,
    NousetsuWebHandler,
    run_web_server,
)
from nousetsu.storage.repository import NovelRepository, ProjectRegistry


@pytest.fixture
def sample_web_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a temporary project with novel config, bible, and sample traces."""
    monkeypatch.setenv("NOVEL_REGISTRY_DIR", str(tmp_path / "registry"))
    reg = ProjectRegistry(storage_dir=tmp_path / "registry")

    proj_dir = tmp_path / "TestNovel"
    proj_dir.mkdir(parents=True)
    novel_dir = proj_dir / ".novel"
    novel_dir.mkdir(parents=True)
    traces_dir = novel_dir / "traces"
    traces_dir.mkdir(parents=True)

    # Config & Bible
    config_file = novel_dir / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump({
            "title": "Test Novel Project",
            "source_language": "Japanese",
            "target_language": "English",
        }, f)

    bible_file = novel_dir / "bible.json"
    with open(bible_file, "w", encoding="utf-8") as f:
        json.dump({
            "title": "Test Novel Project",
            "genre": "fantasy",
        }, f)

    # Sample trace JSON
    sample_trace_doc = {
        "chapter_id": "ch_001",
        "chapter_num": 1,
        "folder": None,
        "total_interactions": 1,
        "total_duration_seconds": 2.5,
        "total_token_usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "thought_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 150
        },
        "stage_breakdown": {"drafting": 1},
        "traces": [
            {
                "trace_id": "tr_1",
                "timestamp": "2026-09-13T10:00:00Z",
                "chapter_id": "ch_001",
                "chapter_num": 1,
                "folder": None,
                "stage": "drafting",
                "agent": "drafter",
                "model": "mock-model",
                "iteration": 1,
                "chunk_index": 1,
                "total_chunks": 1,
                "depth": 0,
                "system_prompt": "You are a translator.",
                "user_prompt": "Translate chapter 1",
                "raw_output": "Chapter 1 in English",
                "parsed_output": {},
                "token_usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "thought_tokens": 0,
                    "cached_tokens": 0,
                    "total_tokens": 150
                },
                "duration_seconds": 2.5,
                "status": "success",
                "error_message": None,
                "metadata": {}
            }
        ]
    }

    trace_file = traces_dir / "chapter_0001.json"
    with open(trace_file, "w", encoding="utf-8") as f:
        json.dump(sample_trace_doc, f)

    # Volume folder with trace
    vol_dir = traces_dir / "Volume_01"
    vol_dir.mkdir(parents=True)
    vol_trace_file = vol_dir / "chapter_0002.json"
    with open(vol_trace_file, "w", encoding="utf-8") as f:
        json.dump({**sample_trace_doc, "chapter_num": 2, "folder": "Volume_01"}, f)

    # Register project
    reg.register_project(proj_dir)
    reg.set_last_active_project(proj_dir)

    return {
        "proj_dir": proj_dir,
        "registry": reg,
        "traces_dir": traces_dir,
    }


def test_get_project_meta(sample_web_project):
    proj_dir = sample_web_project["proj_dir"]
    meta = _get_project_meta(proj_dir)

    assert meta["title"] == "Test Novel Project"
    assert meta["genre"] == "fantasy"
    assert meta["source_language"] == "Japanese"
    assert meta["target_language"] == "English"
    assert meta["has_traces"] is True
    assert meta["trace_count"] == 2
    assert meta["latest_trace_mtime"] > 0


def test_load_project_traces(sample_web_project):
    proj_dir = sample_web_project["proj_dir"]
    chapters = _load_project_traces(proj_dir)

    assert len(chapters) == 2
    # Should contain chapter 1 (root) and chapter 2 (Volume_01)
    ch1 = next(c for c in chapters if c["chapterNum"] == 1)
    assert ch1["folder"] is None
    assert ch1["document"]["total_interactions"] == 1

    ch2 = next(c for c in chapters if c["chapterNum"] == 2)
    assert ch2["folder"] == "Volume_01"


class LiveServerFixture:
    def __init__(self, port: int, dist_dir: Path):
        self.port = port
        self.dist_dir = dist_dir
        self.httpd = None
        self.thread = None

    def start(self):
        def handler_factory(*args, **kwargs):
            return NousetsuWebHandler(*args, dist_dir=self.dist_dir, **kwargs)

        self.httpd = socketserver.TCPServer(("127.0.0.1", self.port), handler_factory)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


@pytest.fixture
def live_server(sample_web_project, tmp_path: Path):
    # Dummy dist dir with index.html
    dist_dir = tmp_path / "fake_dist"
    dist_dir.mkdir(parents=True)
    index_file = dist_dir / "index.html"
    index_file.write_text("<!DOCTYPE html><html><body>Visualizer</body></html>", encoding="utf-8")

    # Pick an available port
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = LiveServerFixture(port, dist_dir)
    server.start()
    yield f"http://127.0.0.1:{port}"
    server.stop()


def test_api_active_project(live_server, sample_web_project):
    url = f"{live_server}/api/active-project"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        assert res.headers.get("Access-Control-Allow-Origin") == "*"
        data = json.loads(res.read().decode("utf-8"))
        assert "active_project" in data
        assert data["active_project"]["title"] == "Test Novel Project"
        assert len(data["projects"]) >= 1


def test_api_sync_state(live_server, sample_web_project):
    url = f"{live_server}/api/sync-state"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["active_project_title"] == "Test Novel Project"
        assert data["traces_count"] == 2
        assert data["latest_trace_mtime"] > 0


def test_api_traces(live_server, sample_web_project):
    url = f"{live_server}/api/traces"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["project_title"] == "Test Novel Project"
        assert len(data["chapters"]) == 2


def test_api_token_analytics_aggregates_trace_history_and_separates_snapshots(live_server, sample_web_project):
    from nousetsu.models.metadata import (
        ChapterMetadata,
        CheckpointData,
        PipelineStage,
        StageStatus,
        StepTokenUsage,
        TokenUsage,
        TranslationStats,
    )

    project_dir = sample_web_project["proj_dir"]
    traces_dir = sample_web_project["traces_dir"]

    def trace(trace_id, chapter_id, chapter_num, folder, stage, model, usage, duration):
        return {
            "trace_id": trace_id,
            "chapter_id": chapter_id,
            "chapter_num": chapter_num,
            "folder": folder,
            "stage": stage,
            "model": model,
            "token_usage": usage,
            "duration_seconds": duration,
        }

    first = trace("root-first", "ch_001", 1, None, "drafting", "mock-drafter", {
        "input_tokens": 100, "output_tokens": 50, "thought_tokens": 10, "cached_tokens": 20, "total_tokens": 160,
    }, 2.0)
    retry = trace("root-retry", "ch_001", 1, None, "drafting", "mock-drafter", {
        "input_tokens": 40, "output_tokens": 20, "thought_tokens": 0, "cached_tokens": 10, "total_tokens": 60,
    }, 1.0)
    volume = trace("volume-first", "ch_002", 2, "Volume_01", "critique", "mock-critic", {
        "input_tokens": 30, "output_tokens": 20, "thought_tokens": 5, "cached_tokens": 0, "total_tokens": 55,
    }, 3.0)

    root_doc = traces_dir / "chapter_0001.json"
    root_doc.write_text(json.dumps({"chapter_id": "ch_001", "chapter_num": 1, "folder": None, "traces": [first]}), encoding="utf-8")
    (traces_dir / "chapter_0001.jsonl").write_text(
        chr(10).join(json.dumps(record) for record in (first, retry)) + chr(10),
        encoding="utf-8",
    )

    volume_dir = traces_dir / "Volume_01"
    volume_json = volume_dir / "chapter_0002.json"
    volume_json.write_text(json.dumps({"chapter_id": "ch_002", "chapter_num": 2, "folder": "Volume_01", "traces": [volume]}), encoding="utf-8")
    (volume_dir / "chapter_0002.jsonl").write_text(json.dumps(volume) + chr(10), encoding="utf-8")

    metadata = ChapterMetadata(
        chapter_id="ch_003",
        chapter_num=3,
        source_file="Volume_02/0003.txt",
        source_sha256="test-hash",
        output_file="Volume_02_en/0003.md",
        checkpoint=CheckpointData(status=StageStatus.PAUSED),
        stats=TranslationStats(
            prompt_tokens=8,
            completion_tokens=2,
            total_tokens=10,
            duration_seconds=0.5,
            step_usage=[StepTokenUsage(
                stage=PipelineStage.DRAFTING,
                step_name="Drafting",
                model="mock-drafter",
                duration_seconds=0.5,
                usage=TokenUsage(input_tokens=8, output_tokens=2, total_tokens=10),
            )],
        ),
    )
    estimate_only = ChapterMetadata(
        chapter_id="ch_004",
        chapter_num=4,
        source_file="Volume_03/0004.txt",
        source_sha256="test-hash",
        output_file="Volume_03_en/0004.md",
        checkpoint=CheckpointData(status=StageStatus.PAUSED),
        stats=TranslationStats(prompt_tokens=9, completion_tokens=2, total_tokens=11),
    )
    zero_usage = ChapterMetadata(
        chapter_id="ch_005",
        chapter_num=5,
        source_file="Volume_04/0005.txt",
        source_sha256="test-hash",
        output_file="Volume_04_en/0005.md",
        checkpoint=CheckpointData(status=StageStatus.PAUSED),
        stats=TranslationStats(step_usage=[StepTokenUsage(stage=PipelineStage.DRAFTING)]),
    )
    root_metadata = ChapterMetadata(
        chapter_id="ch_001",
        chapter_num=1,
        source_file="raw_chapters/0001.txt",
        source_sha256="test-hash",
        output_file="translated_chapters/0001.md",
        checkpoint=CheckpointData(status=StageStatus.PAUSED),
        stats=TranslationStats(
            prompt_tokens=140,
            completion_tokens=70,
            thought_tokens=10,
            cached_tokens=30,
            total_tokens=220,
            duration_seconds=3.0,
            step_usage=[StepTokenUsage(
                stage=PipelineStage.DRAFTING,
                step_name="Drafting",
                model="mock-drafter",
                duration_seconds=3.0,
                usage=TokenUsage(
                    input_tokens=140,
                    output_tokens=70,
                    thought_tokens=10,
                    cached_tokens=30,
                    total_tokens=220,
                ),
            )],
        ),
    )
    repository = NovelRepository(project_dir)
    repository.save_metadata(root_metadata, project_dir / "translated_chapters" / "0001.md")
    repository.save_metadata(metadata, project_dir / "Volume_02_en" / "0003.md")
    repository.save_metadata(estimate_only, project_dir / "Volume_03_en" / "0004.md")
    repository.save_metadata(zero_usage, project_dir / "Volume_04_en" / "0005.md")

    def get_analytics(**query):
        url = f"{live_server}/api/token-analytics?{urlencode({'project_path': str(project_dir), **query})}"
        with urllib.request.urlopen(url) as response:
            assert response.status == 200
            assert response.headers.get("Content-Type", "").startswith("application/json")
            return json.loads(response.read().decode("utf-8"))

    all_data = get_analytics()
    assert all_data["history"]["total_tokens"] == 275
    assert all_data["history"]["prompt_tokens"] == 170
    assert all_data["history"]["completion_tokens"] == 90
    assert all_data["history"]["thought_tokens"] == 15
    assert all_data["history"]["cached_tokens"] == 30
    assert all_data["history"]["total_duration_seconds"] == 6.0
    assert all_data["history"]["stage_metrics"][0]["total_tokens"] == 220
    assert all_data["history"]["model_metrics"][0]["total_tokens"] == 220
    assert all_data["recorded"]["total_tokens"] == 285
    assert all_data["recorded"]["prompt_tokens"] == 178
    assert all_data["recorded"]["completion_tokens"] == 92
    assert all_data["recorded"]["stage_metrics"][0]["total_tokens"] == 230
    assert all_data["recorded"]["model_metrics"][0]["total_tokens"] == 230
    assert all_data["recorded"]["total_duration_seconds"] == 6.5
    assert {item["chapter_num"] for item in all_data["recorded"]["chapter_rankings"]} == {1, 2, 3}
    assert all_data["metadata_snapshot"]["total_tokens"] == 10
    assert all_data["metadata_snapshot"]["total_chapters"] == 1
    assert all_data["metadata_snapshot"]["chapter_rankings"][0]["chapter_num"] == 3
    assert all_data["coverage"]["history_chapters"] == 2
    assert all_data["coverage"]["snapshot_only_chapters"] == 3
    assert all_data["coverage"]["history_complete"] is False

    volume_data = get_analytics(folder="Volume_01")
    assert volume_data["recorded"]["total_tokens"] == 55
    assert volume_data["history"]["total_tokens"] == 55
    assert volume_data["metadata_snapshot"]["total_tokens"] == 0
    assert volume_data["history"]["chapter_rankings"][0]["chapter_num"] == 2
    assert volume_data["history"]["chapter_rankings"][0]["chapter_id"] == "ch_002"
    assert len(volume_data["history"]["folder_metrics"]) == 1
    assert volume_data["history"]["folder_metrics"][0]["folder"] == "Volume_01"

    from fastapi.testclient import TestClient
    from nousetsu.cli.web_server import app

    app_response = TestClient(app).get(
        "/api/token-analytics",
        params={"project_path": str(project_dir)},
    )
    assert app_response.status_code == 200
    assert app_response.json()["history"]["total_tokens"] == 275


def test_api_switch_active_project(live_server, sample_web_project, tmp_path: Path):
    # Create second project
    proj2 = tmp_path / "NovelTwo"
    proj2.mkdir(parents=True)
    (proj2 / ".novel").mkdir()
    with open(proj2 / ".novel" / "config.json", "w", encoding="utf-8") as f:
        json.dump({"title": "Novel Two Project"}, f)

    reg = sample_web_project["registry"]
    reg.register_project(proj2)

    url = f"{live_server}/api/active-project"
    payload = json.dumps({"project_path": str(proj2)}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["success"] is True
        assert data["active_project"]["title"] == "Novel Two Project"

    # Verify registry updated
    assert reg.get_last_active_project().resolve() == proj2.resolve()


def test_spa_fallback(live_server):
    url = f"{live_server}/some/random/route"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        content = res.read().decode("utf-8")
        assert "Visualizer" in content


def test_cmd_web_panel_renders(sample_web_project):
    """Ensure the launch banner renders with Rich console without MissingStyle error."""
    from rich.panel import Panel
    from nousetsu.cli.app import console

    proj_dir = sample_web_project["proj_dir"]
    url = "http://localhost:5173"
    dist_dir = proj_dir / "dist"

    # This should not raise rich.errors.MissingStyle
    panel = Panel.fit(
        f"[bold green]🐾 Nousetsu Trace Visualizer Running![/]\n\n"
        f"URL: [link={url}][cyan]{url}[/link][/]\n"
        f"Active TUI Project: [bold cyan]{proj_dir.name}[/] ([dim]{proj_dir}[/])\n"
        f"Serving: [dim]{dist_dir}[/]\n\n"
        f"[magenta]Press Ctrl+C to stop the server (=^･ω･^=)[/]",
        title="Web Visualizer Active",
        border_style="cyan"
    )
    console.print(panel)


def test_chapter_metadata_duration_and_token_properties():
    """Verify ChapterMetadata provides direct duration_seconds and total_token_usage properties."""
    from nousetsu.models.metadata import ChapterMetadata, TranslationStats

    meta = ChapterMetadata(
        chapter_id="ch_001",
        chapter_num=1,
        source_file="0001.txt",
        source_sha256="abc",
        output_file="0001.md",
        stats=TranslationStats(
            duration_seconds=12.34,
            prompt_tokens=150,
            completion_tokens=80,
            thought_tokens=20,
            cached_tokens=50,
            total_tokens=250,
        )
    )

    # Both properties must be accessible directly without AttributeError
    assert meta.duration_seconds == 12.34
    assert meta.total_token_usage.input_tokens == 150
    assert meta.total_token_usage.output_tokens == 80
    assert meta.total_token_usage.thought_tokens == 20
    assert meta.total_token_usage.cached_tokens == 50
    assert meta.total_token_usage.total_tokens == 250

    dumped = meta.total_token_usage.model_dump()
    assert dumped["input_tokens"] == 150
    assert dumped["total_tokens"] == 250


def test_translate_start_request_chapter_filter():
    """Verify TranslateStartRequest parses string chapter filters without validation errors."""
    from nousetsu.cli.web_server import TranslateStartRequest

    # Single integer
    req1 = TranslateStartRequest(chapter_num=5)
    assert req1.get_chapter_filter() == 5

    # String integer
    req2 = TranslateStartRequest(chapter="48")
    assert req2.get_chapter_filter() == "48"

    # Range string
    req3 = TranslateStartRequest(chapter="5-58")
    assert req3.get_chapter_filter() == "5-58"

    # Plus string via chapter_filter field
    req4 = TranslateStartRequest(chapter_filter="5+")
    assert req4.get_chapter_filter() == "5+"

    # None
    req5 = TranslateStartRequest()
    assert req5.get_chapter_filter() is None


def test_bible_arc_normalization_and_compatibility(sample_web_project):
    """Verify /api/bible populates arc UI aliases and PUT /api/bible normalizes them back."""
    from fastapi.testclient import TestClient
    from nousetsu.cli.web_server import app
    from nousetsu.models.bible import ArcSummary, NovelBible
    from nousetsu.storage.repository import NovelRepository

    proj_dir = sample_web_project["proj_dir"]
    repo = NovelRepository(proj_dir)
    bible = NovelBible(
        title="Arc Test Novel",
        source_language="Japanese",
        target_language="English",
        archived_arcs=[
            ArcSummary(
                arc_id="arc_0001",
                arc_num=1,
                title="Awakening Arc",
                synopsis="The hero awakens in the ruins.",
                core_conflict="Escape the beast",
                status="completed",
                start_chapter=1,
                end_chapter=5,
                key_milestones=["Defeated beast", "Found sword"],
            )
        ],
        active_arc=ArcSummary(
            arc_id="arc_0002",
            arc_num=2,
            title="Academy Arc",
            synopsis="The hero joins the academy.",
            core_conflict="Pass the trial",
            status="active",
            start_chapter=6,
            key_milestones=["Passed entrance exam"],
        ),
    )
    repo.save_bible(bible)

    client = TestClient(app)

    # 1. GET /api/bible must populate both title & arc_title, arc_num & arc_number, synopsis & summary
    res = client.get(f"/api/bible?project_path={proj_dir}")
    assert res.status_code == 200
    data = res.json()
    archived = data["archived_arcs"][0]
    assert archived["title"] == "Awakening Arc"
    assert archived["arc_title"] == "Awakening Arc"
    assert archived["arc_num"] == 1
    assert archived["arc_number"] == 1
    assert archived["synopsis"] == "The hero awakens in the ruins."
    assert archived["summary"] == "The hero awakens in the ruins."
    assert archived["core_conflict"] == "Escape the beast"
    assert archived["key_milestones"] == ["Defeated beast", "Found sword"]

    active = data["active_arc"]
    assert active["title"] == "Academy Arc"
    assert active["arc_title"] == "Academy Arc"
    assert active["arc_num"] == 2
    assert active["arc_number"] == 2
    assert active["synopsis"] == "The hero joins the academy."
    assert active["summary"] == "The hero joins the academy."

    # 2. PUT /api/bible accepts arc_title, arc_number, summary from frontend and normalizes back
    incoming_data = {
        "title": "Arc Test Novel",
        "source_language": "Japanese",
        "target_language": "English",
        "genre": "fantasy",
        "characters": [],
        "glossary": [],
        "archived_arcs": [
            {
                "arc_id": "arc_0001",
                "arc_number": 1,
                "arc_title": "Awakening Arc (Updated)",
                "summary": "Updated synopsis.",
                "core_conflict": "Escape the beast",
                "status": "completed",
                "start_chapter": 1,
                "end_chapter": 5,
            }
        ],
        "active_arc": {
            "arc_id": "arc_0002",
            "arc_number": 2,
            "arc_title": "Academy Arc (Updated)",
            "summary": "Updated academy synopsis.",
            "status": "active",
            "start_chapter": 6,
        },
    }
    put_res = client.put(f"/api/bible?project_path={proj_dir}", json=incoming_data)
    assert put_res.status_code == 200
    assert put_res.json()["success"] is True

    # Reload from repo to confirm persisted NovelBible
    saved_bible = repo.load_bible()
    assert saved_bible.archived_arcs[0].title == "Awakening Arc (Updated)"
    assert saved_bible.archived_arcs[0].arc_num == 1
    assert saved_bible.archived_arcs[0].synopsis == "Updated synopsis."
    assert saved_bible.active_arc.title == "Academy Arc (Updated)"
    assert saved_bible.active_arc.arc_num == 2
    assert saved_bible.active_arc.synopsis == "Updated academy synopsis."


def test_project_meta_caching_and_fast_scan(sample_web_project):
    """Verify that _get_project_meta memoizes results into _PROJECT_META_CACHE."""
    from nousetsu.cli.web_server import _get_project_meta, _PROJECT_META_CACHE, _invalidate_chapter_caches

    proj_dir = sample_web_project["proj_dir"]
    _invalidate_chapter_caches(str(proj_dir))

    # First call populates cache
    meta1 = _get_project_meta(proj_dir)
    assert meta1["trace_count"] == 2
    p_str = str(proj_dir.resolve())
    assert p_str in _PROJECT_META_CACHE

    # Second call returns from cache
    meta2 = _get_project_meta(proj_dir)
    assert meta2 == meta1

    # Invalidation clears the cache
    _invalidate_chapter_caches(str(proj_dir))
    assert p_str not in _PROJECT_META_CACHE


def test_api_traces_filtering_and_single_chapter(live_server, sample_web_project):
    """Verify that /api/traces supports single-chapter filtering for lazy loading."""
    # Query specific chapter 1
    url = f"{live_server}/api/traces?chapter=1"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert len(data["chapters"]) == 1
        assert data["chapters"][0]["chapterNum"] == 1
        assert len(data["chapters"][0]["document"]["traces"]) == 1


def test_desktop_runtime_version_endpoint_reports_launcher_version(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from nousetsu.cli.web_server import create_app

    monkeypatch.setenv("NOUSETSU_DESKTOP_VERSION", "0.5.0-test")
    response = TestClient(create_app(dist_dir=tmp_path)).get("/api/desktop-info")

    assert response.status_code == 200
    assert response.json() == {"version": "0.5.0-test"}


def test_load_project_traces_active_chapter_retention(tmp_path):
    """Verify that active_chapter retains full traces for the designated chapter when total > 5."""
    from fastapi.testclient import TestClient
    from nousetsu.cli.web_server import _load_project_traces, create_app

    proj_dir = tmp_path / "multi_chapter_proj"
    proj_dir.mkdir(parents=True)
    traces_dir = proj_dir / ".novel" / "traces"
    traces_dir.mkdir(parents=True)

    # Create 7 chapters of traces
    for ch_idx in range(1, 8):
        doc = {
            "chapter_id": f"chapter_{str(ch_idx).zfill(4)}",
            "chapter_num": ch_idx,
            "folder": None,
            "total_interactions": 1,
            "total_duration_seconds": 1.0,
            "total_token_usage": {"total_tokens": 100},
            "traces": [
                {
                    "trace_id": f"trace_ch{ch_idx}_01",
                    "stage": "drafting",
                    "prompt": f"Draft chapter {ch_idx}",
                    "response": f"Response chapter {ch_idx}",
                }
            ],
        }
        with open(traces_dir / f"chapter_{str(ch_idx).zfill(4)}.json", "w", encoding="utf-8") as f:
            json.dump(doc, f)

    # 1. Default load without active_chapter or all: only chapter 1 has traces, others stripped
    loaded_default = _load_project_traces(proj_dir)
    assert len(loaded_default) == 7
    ch1 = next(c for c in loaded_default if c["chapterNum"] == 1)
    ch4 = next(c for c in loaded_default if c["chapterNum"] == 4)
    assert len(ch1["document"]["traces"]) == 1
    assert len(ch4["document"]["traces"]) == 0

    # 2. Load with active_chapter=4: both chapter 1 and chapter 4 have full traces, others stripped
    loaded_with_active = _load_project_traces(proj_dir, active_chapter=4)
    ch1_active = next(c for c in loaded_with_active if c["chapterNum"] == 1)
    ch4_active = next(c for c in loaded_with_active if c["chapterNum"] == 4)
    ch3_active = next(c for c in loaded_with_active if c["chapterNum"] == 3)
    assert len(ch1_active["document"]["traces"]) == 1
    assert len(ch4_active["document"]["traces"]) == 1
    assert len(ch3_active["document"]["traces"]) == 0

    # 3. Test through FastAPI route /api/traces?active_chapter=4
    app = create_app(dist_dir=tmp_path)
    client = TestClient(app)
    resp = client.get(f"/api/traces?project_path={proj_dir}&active_chapter=4")
    assert resp.status_code == 200
    data = resp.json()
    resp_ch4 = next(c for c in data["chapters"] if c["chapterNum"] == 4)
    assert len(resp_ch4["document"]["traces"]) == 1
    assert resp_ch4["document"]["traces"][0]["trace_id"] == "trace_ch4_01"
