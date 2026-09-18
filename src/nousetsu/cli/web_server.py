"""FastAPI HTTP Server and REST + SSE API for the Nousetsu Web Dashboard and Tauri Desktop App."""
from __future__ import annotations

import asyncio
import http.server
import json
import logging
import os
import re
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import uvicorn
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from nousetsu.batch.runner import BatchRunner
from nousetsu.batch.scanner import ChapterScanner, ChapterTask
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.config import ProjectConfig
from nousetsu.models.metadata import StageStatus
from nousetsu.storage.repository import (
    NovelRepository,
    ProjectRegistry,
    get_projects_root_dir,
    resolve_project_dir,
    get_new_project_dir,
)
from nousetsu.utils.language import detect_language

logger = logging.getLogger(__name__)


# ============================================================================
# SSE Event Bus & Active Job Manager
# ============================================================================


class SSEEventBus:
    """Thread-safe Server-Sent Events bus for publishing agent events to web clients."""

    def __init__(self) -> None:
        self.subscribers: List[asyncio.Queue] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        with self._lock:
            q: asyncio.Queue = asyncio.Queue(maxsize=100)
            self.subscribers.append(q)
            return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def publish_sync(self, event_type: str, data: Any) -> None:
        """Called from worker threads to safely broadcast to async SSE queues."""
        with self._lock:
            if not self.subscribers or not self._loop:
                return
            msg = {"event": event_type, "data": data}
            for q in list(self.subscribers):
                try:
                    self._loop.call_soon_threadsafe(
                        lambda queue=q, m=msg: queue.put_nowait(m) if not queue.full() else None
                    )
                except Exception:
                    pass


class ActiveTranslationJob:
    """Singleton tracking running batch translation background thread and cancellation."""

    def __init__(self) -> None:
        self.is_running: bool = False
        self.active_chapter: Optional[int] = None
        self.active_folder: Optional[str] = None
        self.active_stage: Optional[str] = None
        self.stop_event: Optional[threading.Event] = None
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

    def start(self, target_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        with self.lock:
            if self.is_running:
                raise RuntimeError("A translation task is already in progress.")
            self.is_running = True
            self.stop_event = threading.Event()
            self.thread = threading.Thread(
                target=target_fn,
                args=args,
                kwargs={"stop_event": self.stop_event, **kwargs},
                daemon=True
            )
            self.thread.start()

    def stop(self) -> bool:
        with self.lock:
            if not self.is_running or not self.stop_event:
                return False
            self.stop_event.set()
            return True

    def finish(self) -> None:
        with self.lock:
            self.is_running = False
            self.active_chapter = None
            self.active_folder = None
            self.active_stage = None
            self.stop_event = None
            self.thread = None


# Singletons
event_bus = SSEEventBus()
active_job = ActiveTranslationJob()


# ============================================================================
# Pydantic Request & Response Schemas
# ============================================================================

class SwitchProjectRequest(BaseModel):
    project_path: str


class CreateProjectRequest(BaseModel):
    title: str = Field(..., description="Novel title")
    folder_name: Optional[str] = Field(None, description="Optional folder name inside NOVEL_PROJECTS_DIR")
    source_language: Optional[str] = Field("Japanese", description="Source language")
    target_language: Optional[str] = Field("Thai", description="Target language")
    genre: Optional[str] = Field("general", description="Novel genre")
    model: Optional[str] = Field(None, description="Primary model override")


class TranslateStartRequest(BaseModel):
    project_path: Optional[str] = None
    folder: Optional[str] = None
    chapter: Optional[int] = None
    chapter_num: Optional[int] = None
    limit: Optional[int] = None
    force: bool = False
    force_retranslate: bool = False
    model: Optional[str] = None
    fallback_model: Optional[str] = None
    max_loops: Optional[int] = None
    quality_threshold: Optional[float] = None

    def get_chapter(self) -> Optional[int]:
        return self.chapter if self.chapter is not None else self.chapter_num

    def get_force(self) -> bool:
        return self.force or self.force_retranslate


class RawYamlRequest(BaseModel):
    raw: Optional[str] = None
    raw_yaml: Optional[str] = None

    def get_content(self) -> str:
        return self.raw if self.raw is not None else (self.raw_yaml or "")


class UploadFileItem(BaseModel):
    name: str = Field(..., description="File name (e.g. 0001.txt or ch01.md)")
    content: str = Field(..., description="Text content of the file")


class UploadChaptersRequest(BaseModel):
    project_path: Optional[str] = None
    folder: Optional[str] = Field(None, description="Target volume or subfolder name (default: raw_chapters)")
    files: List[UploadFileItem] = Field(..., description="Files to upload")
    overwrite: bool = Field(False, description="Whether to overwrite existing files")


# ============================================================================
# Metadata & Trace Extraction Helpers (Legacy & New)
# ============================================================================

def _get_project_meta(project_path: Path) -> Dict[str, Any]:
    """Extract metadata (title, genre, languages, trace stats) for a project directory."""
    title = project_path.name
    genre = "general"
    src_lang = "auto"
    tgt_lang = "English"
    has_traces = False
    trace_count = 0
    latest_mtime = 0.0

    novel_dir = project_path / ".novel"
    config_file = novel_dir / "config.yaml"
    config_json = novel_dir / "config.json"
    bible_file = novel_dir / "bible" / "bible.yaml"
    bible_json = novel_dir / "bible.json"
    traces_dir = novel_dir / "traces"

    # Try YAML config first, then json
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                title = cfg.get("title", title)
                src_lang = cfg.get("source_language", src_lang)
                tgt_lang = cfg.get("target_language", tgt_lang)
        except Exception:
            pass
    elif config_json.exists():
        try:
            with open(config_json, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                title = cfg.get("title", title)
                src_lang = cfg.get("source_language", src_lang)
                tgt_lang = cfg.get("target_language", tgt_lang)
        except Exception:
            pass

    if bible_file.exists():
        try:
            with open(bible_file, "r", encoding="utf-8") as f:
                b = yaml.safe_load(f) or {}
                title = b.get("title", title)
                genre = b.get("genre", genre)
        except Exception:
            pass
    elif bible_json.exists():
        try:
            with open(bible_json, "r", encoding="utf-8") as f:
                b = json.load(f)
                title = b.get("title", title)
                genre = b.get("genre", genre)
        except Exception:
            pass

    if traces_dir.exists() and traces_dir.is_dir():
        for tf in traces_dir.rglob("*"):
            if tf.is_file() and (tf.name.endswith(".json") or tf.name.endswith(".jsonl")):
                has_traces = True
                trace_count += 1
                try:
                    mtime = tf.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                except Exception:
                    pass

    return {
        "path": str(project_path.resolve()),
        "name": project_path.name,
        "title": title,
        "genre": genre,
        "source_language": src_lang,
        "target_language": tgt_lang,
        "has_traces": has_traces,
        "trace_count": trace_count,
        "latest_trace_mtime": latest_mtime,
    }


def _load_project_traces(project_path: Path) -> List[Dict[str, Any]]:
    """Scan and parse all chapter trace documents (.json and .jsonl) for a project."""
    traces_dir = project_path / ".novel" / "traces"
    if not traces_dir.exists() or not traces_dir.is_dir():
        return []

    chapters_map: Dict[str, Dict[str, Any]] = {}
    candidate_files = sorted(
        list(traces_dir.rglob("chapter_*.json")) + list(traces_dir.rglob("chapter_*.jsonl")),
        key=lambda p: (0 if p.suffix == ".json" else 1, p.name)
    )

    for tf in candidate_files:
        try:
            rel_parts = tf.relative_to(traces_dir).parts
            folder = rel_parts[0] if len(rel_parts) > 1 else None

            m = re.search(r"chapter_(\d+)", tf.stem)
            chapter_num = int(m.group(1)) if m else 1
            key = f"{folder or 'root'}_ch{chapter_num}"

            if key in chapters_map and tf.suffix == ".jsonl":
                continue

            if tf.suffix == ".json":
                with open(tf, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            else:
                traces = []
                with open(tf, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                traces.append(json.loads(line))
                            except Exception:
                                pass

                total_duration = sum(t.get("duration_seconds", 0) for t in traces)
                tok = {"input_tokens": 0, "output_tokens": 0, "thought_tokens": 0, "cached_tokens": 0, "total_tokens": 0}
                stage_bd = {}
                for t in traces:
                    st = t.get("stage", "unknown")
                    stage_bd[st] = stage_bd.get(st, 0) + 1
                    tu = t.get("token_usage", {})
                    for k in tok:
                        tok[k] += tu.get(k, 0)

                doc = {
                    "chapter_id": f"chapter_{str(chapter_num).zfill(4)}",
                    "chapter_num": chapter_num,
                    "folder": folder,
                    "total_interactions": len(traces),
                    "total_duration_seconds": round(total_duration, 3),
                    "total_token_usage": tok,
                    "stage_breakdown": stage_bd,
                    "traces": traces,
                }

            chapters_map[key] = {
                "id": key,
                "fileName": tf.name,
                "folder": folder,
                "chapterNum": doc.get("chapter_num", chapter_num),
                "document": doc,
            }
        except Exception as e:
            logger.warning("Failed to load trace file %s: %s", tf, e)

    loaded = list(chapters_map.values())
    loaded.sort(key=lambda c: (c.get("folder") or "", c.get("chapterNum", 0)))
    return loaded


def _scan_project_tasks(repo: NovelRepository, folder: Optional[str] = None) -> List[ChapterTask]:
    """Scan and resolve chapter tasks for a project and optional subfolder."""
    cfg = repo.load_config()
    scanner = ChapterScanner(repo)

    if folder and folder != "all":
        # Check if the folder exists directly in repo.root_dir
        folder_cand = repo.root_dir / folder
        if folder_cand.exists() and folder_cand.is_dir():
            raw_path = folder_cand
            out_cand_th = repo.root_dir / f"{folder}_th"
            out_cand_tr = repo.root_dir / f"{folder}_trans"
            if out_cand_th.exists():
                output_path = out_cand_th
            elif out_cand_tr.exists():
                output_path = out_cand_tr
            else:
                output_path = cfg.get_output_path(repo.root_dir)
        else:
            raw_path = cfg.get_raw_path(repo.root_dir)
            output_path = cfg.get_output_path(repo.root_dir)
        return scanner.scan_directory(raw_path, output_path)

    # When folder is None or "all": scan primary path and discover all volume folders
    raw_path = cfg.get_raw_path(repo.root_dir)
    output_path = cfg.get_output_path(repo.root_dir)
    primary_tasks = scanner.scan_directory(raw_path, output_path)

    all_tasks = list(primary_tasks)
    seen_files = {str(t.source_file.resolve()) for t in primary_tasks}

    ignored_dir_names = {
        "node_modules", "web", "src-tauri", "dist", ".git", ".novel", ".venv",
        "__pycache__", "translated_chapters", "raw_chapters"
    }

    try:
        for child in sorted(repo.root_dir.iterdir()):
            if (
                child.is_dir()
                and not child.name.startswith(".")
                and not child.name.endswith("_th")
                and not child.name.endswith("_trans")
                and child.name not in ignored_dir_names
            ):
                if child.resolve() != raw_path.resolve():
                    has_chapters = any(f.suffix.lower() in (".txt", ".md") for f in child.iterdir() if f.is_file())
                    if has_chapters:
                        out_th = repo.root_dir / f"{child.name}_th"
                        out_tr = repo.root_dir / f"{child.name}_trans"
                        sub_out = out_th if out_th.exists() else (out_tr if out_tr.exists() else output_path)
                        sub_tasks = scanner.scan_directory(child, sub_out)
                        for st in sub_tasks:
                            if str(st.source_file.resolve()) not in seen_files:
                                all_tasks.append(st)
                                seen_files.add(str(st.source_file.resolve()))
    except Exception as e:
        logger.warning("Error auto-discovering volume subfolders: %s", e)

    return all_tasks


# ============================================================================
# Background Worker Function
# ============================================================================

def _run_batch_worker(
    repo: NovelRepository,
    folder: Optional[str],
    chapter_num: Optional[int],
    limit: Optional[int],
    force_retranslate: bool,
    model: Optional[str],
    fallback_model: Optional[str],
    max_loops: Optional[int],
    quality_threshold: Optional[float],
    event_bus: SSEEventBus,
    job: ActiveTranslationJob,
    stop_event: threading.Event
) -> None:
    try:
        runner = BatchRunner(
            repository=repo,
            model_name=model,
            fallback_model=fallback_model,
            max_review_loops=max_loops,
            quality_threshold=quality_threshold,
        )

        def on_notify(msg: str) -> None:
            # Parse stage tags or reflection indicators
            stage_name = job.active_stage or "TRANSLATION"
            if "Stage 1" in msg or "Extracted" in msg:
                stage_name = "EXTRACTION"
            elif "Stage 2" in msg or "Drafting" in msg:
                stage_name = "DRAFTING"
            elif "Stage 3" in msg or "Critique" in msg:
                stage_name = "CRITIQUE"
            elif "Stage 4" in msg or "Polishing" in msg or "Polished" in msg:
                stage_name = "POLISHING"
            elif "Stage 5" in msg or "Chronicler" in msg:
                stage_name = "CHRONICLING"
            job.active_stage = stage_name

            event_bus.publish_sync("stage_progress", {
                "chapter_num": job.active_chapter,
                "folder": job.active_folder,
                "stage": stage_name,
                "message": msg,
                "timestamp": time.time(),
            })
            event_bus.publish_sync("log_message", {
                "level": "INFO",
                "message": msg,
                "timestamp": time.time(),
            })

        tasks = _scan_project_tasks(repo, folder=folder)
        if chapter_num is not None:
            tasks = [t for t in tasks if t.chapter_num == chapter_num]
        if limit:
            tasks = tasks[:limit]

        completed_count = 0
        for idx, task in enumerate(tasks, 1):
            if stop_event.is_set():
                break

            if task.is_completed and not force_retranslate:
                continue

            job.active_chapter = task.chapter_num
            job.active_folder = task.folder
            job.active_stage = "EXTRACTION"

            event_bus.publish_sync("stage_start", {
                "chapter_num": task.chapter_num,
                "folder": task.folder,
                "title": task.source_file.stem,
                "total_chapters": len(tasks),
                "index": idx,
            })

            meta = runner.run_chapter(
                task,
                force_retranslate=force_retranslate,
                stop_event=stop_event,
                notify_callback=on_notify,
            )

            if meta:
                completed_count += 1
                audit_dict = meta.quality_audit.model_dump() if meta.quality_audit else {}
                event_bus.publish_sync("chapter_completed", {
                    "chapter_num": task.chapter_num,
                    "folder": task.folder,
                    "duration": meta.duration_seconds,
                    "tokens": meta.total_token_usage.model_dump() if meta.total_token_usage else {},
                    "audit": audit_dict,
                })

        if stop_event.is_set():
            event_bus.publish_sync("batch_stopped", {"message": "Batch translation safely paused by user."})
        else:
            event_bus.publish_sync("batch_completed", {"completed_chapters": completed_count})

    except Exception as e:
        logger.exception("Batch worker failed: %s", e)
        event_bus.publish_sync("batch_error", {"error": str(e)})
    finally:
        job.finish()


# File stats in-memory cache for fast /api/chapters response
_FILE_STATS_CACHE: Dict[Tuple[str, float, int], Tuple[int, int]] = {}


def _get_raw_file_stats(file_path: Path) -> Tuple[int, int]:
    """Return (line_count, word_count) cached by (path, mtime, size)."""
    try:
        if not file_path.exists():
            return (0, 0)
        st = file_path.stat()
        key = (str(file_path.resolve()), st.st_mtime, st.st_size)
        if key in _FILE_STATS_CACHE:
            return _FILE_STATS_CACHE[key]
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            line_cnt = len(lines)
            word_cnt = sum(len(l.split()) if l.isascii() else len(l.strip()) for l in lines)
            _FILE_STATS_CACHE[key] = (line_cnt, word_cnt)
            return (line_cnt, word_cnt)
    except Exception:
        return (0, 0)


def _get_translated_word_count(file_path: Path) -> int:
    """Return word count of output file cached by (path, mtime, size)."""
    try:
        if not file_path.exists():
            return 0
        st = file_path.stat()
        key = (str(file_path.resolve()), st.st_mtime, st.st_size)
        if key in _FILE_STATS_CACHE:
            return _FILE_STATS_CACHE[key][1]
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            words = len(content.split())
            _FILE_STATS_CACHE[key] = (0, words)
            return words
    except Exception:
        return 0


def _process_chapter_files(
    repo: NovelRepository,
    folder: Optional[str],
    files: List[Tuple[str, str]],
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Save uploaded chapter text files to target raw directory or volume subfolder."""
    cfg = repo.load_config()
    raw_dir_name = cfg.raw_dir or "raw_chapters"

    # Resolve target directory
    if not folder or folder.strip() in ("", "default", raw_dir_name, "raw_chapters"):
        dest_dir = cfg.get_raw_path(repo.root_dir)
        target_folder_name = raw_dir_name
    else:
        # Sanitize folder path
        clean_folder = os.path.normpath(folder.strip()).lstrip("/\\")
        if not clean_folder or ".." in clean_folder.split(os.sep):
            raise HTTPException(status_code=400, detail="Invalid folder name.")
        dest_dir = (repo.root_dir / clean_folder).resolve()
        # Security check: must reside inside project root
        try:
            dest_dir.relative_to(repo.root_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Target folder outside of project root is not permitted.")
        target_folder_name = clean_folder

    dest_dir.mkdir(parents=True, exist_ok=True)

    uploaded: List[str] = []
    skipped: List[str] = []

    for name, content in files:
        safe_name = Path(name).name
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", safe_name).strip()
        if not safe_name or safe_name.startswith("."):
            continue

        target_file = dest_dir / safe_name
        if target_file.exists() and not overwrite:
            skipped.append(safe_name)
            continue

        target_file.write_text(content, encoding="utf-8")
        uploaded.append(safe_name)

    # Invalidate file stats and sha256 caches
    _FILE_STATS_CACHE.clear()
    scanner = ChapterScanner(repo)
    scanner.clear_sha256_cache()

    return {
        "success": True,
        "folder": target_folder_name,
        "uploaded": uploaded,
        "skipped": skipped,
        "total_uploaded": len(uploaded),
        "total_skipped": len(skipped),
        "message": f"Successfully uploaded {len(uploaded)} file(s) to '{target_folder_name}'" + (f" ({len(skipped)} skipped)" if skipped else "") + ".",
    }


# ============================================================================
# FastAPI Application Factory
# ============================================================================

def create_app(dist_dir: Optional[Path] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    dist_path = dist_dir or (Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist")

    app = FastAPI(
        title="NouSetsu Web Dashboard & API",
        description="REST and SSE API for agentic novel translation, trace inspection, and Novel Bible management.",
        version="0.3.0",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _resolve_repo(project_path: Optional[str] = None) -> NovelRepository:
        target_path = resolve_project_dir(project_path)
        if not target_path.exists() or not (target_path / ".novel").exists():
            raise HTTPException(status_code=400, detail=f"Invalid project path: {target_path}")
        return NovelRepository(target_path)

    # ------------------------------------------------------------------------
    # 1. Projects & Sync State Endpoints
    # ------------------------------------------------------------------------

    @app.get("/api/active-project")
    async def get_active_project() -> Dict[str, Any]:
        registry = ProjectRegistry()
        active_p = registry.get_last_active_project() or resolve_project_dir(None)
        active_meta = _get_project_meta(active_p)
        active_meta["is_active"] = True

        discovered = registry.list_projects()
        projects = []
        seen = set()

        projects.append(active_meta)
        seen.add(str(active_p.resolve()))

        for d in discovered:
            p_str = d.get("path")
            if p_str and p_str not in seen:
                p = Path(p_str)
                if p.exists() and (p / ".novel").exists():
                    meta = _get_project_meta(p)
                    meta["is_active"] = (str(p.resolve()) == str(active_p.resolve()))
                    projects.append(meta)
                    seen.add(str(p.resolve()))

        return {
            "active_project": active_meta,
            "projects": projects,
            "projects_dir": str(get_projects_root_dir()),
        }

    @app.post("/api/active-project")
    async def set_active_project(body: SwitchProjectRequest) -> Dict[str, Any]:
        new_path = resolve_project_dir(body.project_path)
        if not new_path.exists() or not (new_path / ".novel").exists():
            raise HTTPException(status_code=400, detail=f"Invalid project path: {new_path}")

        registry = ProjectRegistry()
        registry.register_project(new_path)
        registry.set_last_active_project(new_path)
        meta = _get_project_meta(new_path)
        meta["is_active"] = True

        return {
            "success": True,
            "active_project": meta,
        }

    @app.post("/api/projects/create")
    async def create_project(body: CreateProjectRequest) -> Dict[str, Any]:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Novel title cannot be empty")

        target_dir = get_new_project_dir(title=title, folder_name=body.folder_name)
        if (target_dir / ".novel").exists():
            raise HTTPException(status_code=409, detail=f"Project already exists at {target_dir.name}")

        target_dir.mkdir(parents=True, exist_ok=True)
        repo = NovelRepository(target_dir)
        repo.initialize_project(
            title=title,
            source_lang=body.source_language or "Japanese",
            target_lang=body.target_language or "Thai",
            model_name=body.model,
            genre=body.genre or "general",
        )

        registry = ProjectRegistry()
        registry.register_project(target_dir)
        registry.set_last_active_project(target_dir)

        meta = _get_project_meta(target_dir)
        meta["is_active"] = True

        return {
            "success": True,
            "active_project": meta,
        }

    @app.get("/api/projects")
    async def get_all_projects() -> Dict[str, Any]:
        registry = ProjectRegistry()
        active_p = registry.get_last_active_project() or resolve_project_dir(None)
        discovered = registry.list_projects()
        projects = []
        for d in discovered:
            p = Path(d["path"])
            meta = _get_project_meta(p)
            meta["is_active"] = (str(p.resolve()) == str(active_p.resolve()))
            projects.append(meta)

        return {
            "projects_dir": str(get_projects_root_dir()),
            "active_project_path": str(active_p.resolve()) if active_p else None,
            "active_project": _get_project_meta(active_p) if active_p and active_p.exists() else None,
            "projects": projects,
        }

    @app.get("/api/sync-state")
    async def get_sync_state() -> Dict[str, Any]:
        registry = ProjectRegistry()
        active_p = registry.get_last_active_project() or NovelRepository().root_dir
        meta = _get_project_meta(active_p)
        return {
            "active_project_path": meta["path"],
            "active_project_title": meta["title"],
            "traces_count": meta["trace_count"],
            "latest_trace_mtime": meta["latest_trace_mtime"],
        }

    @app.get("/api/traces")
    async def get_traces(project_path: Optional[str] = Query(None)) -> Dict[str, Any]:
        repo = _resolve_repo(project_path)
        meta = _get_project_meta(repo.root_dir)
        chapters = _load_project_traces(repo.root_dir)
        return {
            "project_path": meta["path"],
            "project_title": meta["title"],
            "genre": meta["genre"],
            "chapters": chapters,
        }

    # ------------------------------------------------------------------------
    # 2. Translation Studio & Chapter Endpoints
    # ------------------------------------------------------------------------

    @app.get("/api/chapters")
    async def get_chapters(
        project_path: Optional[str] = Query(None),
        folder: Optional[str] = Query(None)
    ) -> List[Dict[str, Any]]:
        repo = _resolve_repo(project_path)
        tasks = _scan_project_tasks(repo, folder=folder)

        results = []
        for t in tasks:
            raw_lines, raw_words = _get_raw_file_stats(t.source_file)
            trans_words = _get_translated_word_count(t.output_file)

            if t.is_completed:
                status_str = "COMPLETED"
            elif t.is_failed:
                status_str = "FAILED"
            elif t.is_paused:
                status_str = "PAUSED"
            elif t.needs_resume:
                status_str = "RESUME"
            else:
                status_str = "PENDING"

            if t.existing_meta and hasattr(t.existing_meta, "current_stage"):
                current_stage_str = t.existing_meta.current_stage.value
            elif t.needs_resume or t.is_paused:
                current_stage_str = t.resume_stage.value
            elif t.is_completed:
                current_stage_str = "completed"
            else:
                current_stage_str = "none"

            results.append({
                "chapter_num": t.chapter_num,
                "title": t.source_file.stem,
                "file_name": t.source_file.name,
                "folder": t.folder,
                "status": status_str,
                "current_stage": current_stage_str,
                "raw_exists": t.source_file.exists(),
                "raw_lines": raw_lines,
                "raw_words": raw_words,
                "translated_exists": t.output_file.exists(),
                "translated_words": trans_words,
                "is_completed": t.is_completed,
                "has_checkpoint": bool(t.existing_meta and t.existing_meta.checkpoint),
                "quality_audit": t.existing_meta.quality_audit.model_dump() if (t.existing_meta and t.existing_meta.quality_audit) else None,
            })

        return results

    @app.get("/api/chapters/{chapter_num}/content")
    async def get_chapter_content(
        chapter_num: int,
        project_path: Optional[str] = Query(None),
        folder: Optional[str] = Query(None)
    ) -> Dict[str, Any]:
        repo = _resolve_repo(project_path)
        tasks = _scan_project_tasks(repo, folder=folder)
        task = next((t for t in tasks if t.chapter_num == chapter_num), None)

        if not task and folder:
            all_tasks = _scan_project_tasks(repo, folder=None)
            task = next((t for t in all_tasks if t.chapter_num == chapter_num), None)

        source_text = ""
        translated_text = ""

        if task:
            if task.source_file.exists():
                try:
                    source_text = task.source_file.read_text(encoding="utf-8", errors="replace")
                except Exception as e:
                    source_text = f"Error reading source file: {e}"
            if task.output_file.exists():
                try:
                    translated_text = task.output_file.read_text(encoding="utf-8", errors="replace")
                except Exception as e:
                    translated_text = f"Error reading output file: {e}"

        return {
            "chapter_num": chapter_num,
            "folder": task.folder if task else folder,
            "source_file": str(task.source_file) if task else "",
            "output_file": str(task.output_file) if task else "",
            "source_text": source_text,
            "translated_text": translated_text,
            "has_source": bool(source_text.strip()),
            "has_translated": bool(translated_text.strip()),
            "title": task.source_file.stem if task else f"Chapter {chapter_num}",
        }

    @app.post("/api/translate/start")
    async def start_translation(body: TranslateStartRequest) -> Dict[str, Any]:
        if active_job.is_running:
            raise HTTPException(status_code=409, detail="A translation job is already in progress.")

        repo = _resolve_repo(body.project_path)
        try:
            active_job.start(
                _run_batch_worker,
                repo=repo,
                folder=body.folder,
                chapter_num=body.get_chapter(),
                limit=body.limit,
                force_retranslate=body.get_force(),
                model=body.model,
                fallback_model=body.fallback_model,
                max_loops=body.max_loops,
                quality_threshold=body.quality_threshold,
                event_bus=event_bus,
                job=active_job,
            )
            return {"success": True, "message": "Translation task started successfully."}
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @app.post("/api/translate/stop")
    async def stop_translation() -> Dict[str, Any]:
        stopped = active_job.stop()
        if not stopped:
            return {"success": False, "message": "No active translation job to stop."}
        return {"success": True, "message": "Stopping translation task gracefully..."}

    @app.get("/api/translate/status")
    async def get_translation_status() -> Dict[str, Any]:
        return {
            "is_running": active_job.is_running,
            "active_chapter": active_job.active_chapter,
            "active_folder": active_job.active_folder,
            "active_stage": active_job.active_stage,
        }

    @app.get("/api/folders")
    async def get_project_folders(project_path: Optional[str] = Query(None)) -> Dict[str, Any]:
        """List all available chapter folders in the active project."""
        repo = _resolve_repo(project_path)
        cfg = repo.load_config()
        raw_dir_name = cfg.raw_dir or "raw_chapters"

        ignored_dir_names = {
            "node_modules", "web", "src-tauri", "dist", ".git", ".novel", ".venv",
            "__pycache__", "translated_chapters", raw_dir_name, cfg.output_dir
        }

        folders = [raw_dir_name]
        try:
            for child in sorted(repo.root_dir.iterdir()):
                if (
                    child.is_dir()
                    and not child.name.startswith(".")
                    and not child.name.endswith("_th")
                    and not child.name.endswith("_trans")
                    and child.name not in ignored_dir_names
                ):
                    folders.append(child.name)
        except Exception as e:
            logger.warning("Error listing project folders: %s", e)

        return {
            "default_folder": raw_dir_name,
            "folders": folders,
        }

    @app.post("/api/chapters/upload")
    async def upload_chapters(body: UploadChaptersRequest) -> Dict[str, Any]:
        """Upload raw chapter text files into project raw directory or subfolder (JSON payload)."""
        repo = _resolve_repo(body.project_path)
        file_tuples = [(f.name, f.content) for f in body.files]
        if not file_tuples:
            raise HTTPException(status_code=400, detail="No files provided for upload.")
        return _process_chapter_files(
            repo=repo,
            folder=body.folder,
            files=file_tuples,
            overwrite=body.overwrite,
        )

    @app.post("/api/chapters/upload-form")
    async def upload_chapters_form(
        files: List[UploadFile] = File(...),
        project_path: Optional[str] = Form(None),
        folder: Optional[str] = Form(None),
        overwrite: bool = Form(False),
    ) -> Dict[str, Any]:
        """Upload raw chapter text files into project raw directory or subfolder (Multipart form)."""
        repo = _resolve_repo(project_path)
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded.")

        file_tuples: List[Tuple[str, str]] = []
        for uf in files:
            try:
                raw_bytes = await uf.read()
                content = raw_bytes.decode("utf-8", errors="replace")
                file_tuples.append((uf.filename or "chapter.txt", content))
            except Exception as e:
                logger.warning("Error reading uploaded file %s: %s", uf.filename, e)

        return _process_chapter_files(
            repo=repo,
            folder=folder,
            files=file_tuples,
            overwrite=overwrite,
        )

    # ------------------------------------------------------------------------
    # 3. Server-Sent Events (SSE) Bus
    # ------------------------------------------------------------------------

    @app.get("/api/stream/events")
    async def stream_events(request: Request) -> StreamingResponse:
        event_bus.set_loop(asyncio.get_running_loop())
        q = event_bus.subscribe()

        async def event_generator():
            try:
                yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        msg = await asyncio.wait_for(q.get(), timeout=15.0)
                        ev = msg["event"]
                        data_json = json.dumps(msg["data"], ensure_ascii=False)
                        yield f"event: {ev}\ndata: {data_json}\n\n"
                    except asyncio.TimeoutError:
                        # Keep-alive heartbeat ping
                        yield "event: ping\ndata: {}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                event_bus.unsubscribe(q)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    # ------------------------------------------------------------------------
    # 4. Novel Bible & 3-Tier Memory Endpoints
    # ------------------------------------------------------------------------

    @app.get("/api/bible")
    async def get_bible(project_path: Optional[str] = Query(None)) -> Dict[str, Any]:
        repo = _resolve_repo(project_path)
        bible = repo.load_bible()
        data = bible.model_dump()

        # Add UI compatibility aliases for glossary and characters
        for g in data.get("glossary", []):
            if "source" in g and "term" not in g:
                g["term"] = g["source"]
            if "target" in g and "translation" not in g:
                g["translation"] = g["target"]

        for c in data.get("characters", []):
            if "voice" in c and "speaking_style" not in c:
                c["speaking_style"] = c["voice"]

        return data

    @app.put("/api/bible")
    async def update_bible(bible_data: Dict[str, Any], project_path: Optional[str] = Query(None)) -> Dict[str, Any]:
        repo = _resolve_repo(project_path)
        try:
            # Normalize glossary items: term -> source, translation -> target
            if "glossary" in bible_data and isinstance(bible_data["glossary"], list):
                for item in bible_data["glossary"]:
                    if isinstance(item, dict):
                        if "term" in item and "source" not in item:
                            item["source"] = item["term"]
                        if "translation" in item and "target" not in item:
                            item["target"] = item["translation"]

            # Normalize characters: speaking_style -> voice
            if "characters" in bible_data and isinstance(bible_data["characters"], list):
                for char in bible_data["characters"]:
                    if isinstance(char, dict):
                        if "speaking_style" in char and "voice" not in char:
                            char["voice"] = char["speaking_style"]

            bible = NovelBible.model_validate(bible_data)
            repo.save_bible(bible)
            return {"success": True, "bible": bible.model_dump()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {e}")

    @app.get("/api/bible/raw")
    async def get_bible_raw(project_path: Optional[str] = Query(None)) -> Dict[str, Any]:
        repo = _resolve_repo(project_path)
        bible_path = repo.bible_file_path()
        if not bible_path.exists():
            return {"raw": "", "raw_yaml": ""}
        content = bible_path.read_text(encoding="utf-8", errors="replace")
        return {"raw": content, "raw_yaml": content}

    @app.put("/api/bible/raw")
    async def update_bible_raw(body: RawYamlRequest, project_path: Optional[str] = Query(None)) -> Dict[str, Any]:
        repo = _resolve_repo(project_path)
        try:
            raw_text = body.get_content()
            parsed = yaml.safe_load(raw_text)
            if not isinstance(parsed, dict):
                raise ValueError("YAML must represent a dictionary document.")
            bible = NovelBible.model_validate(parsed)
            repo.save_bible(bible)
            return {"success": True, "bible": bible.model_dump()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML content: {e}")

    # ------------------------------------------------------------------------
    # 5. Project Settings Endpoints
    # ------------------------------------------------------------------------

    @app.get("/api/settings")
    async def get_settings(project_path: Optional[str] = Query(None)) -> Dict[str, Any]:
        repo = _resolve_repo(project_path)
        cfg = repo.load_config()
        return {
            "title": cfg.title,
            "genre": cfg.genre,
            "source_language": cfg.source_language,
            "target_language": cfg.target_language,
            "raw_dir": cfg.raw_dir,
            "translated_dir": cfg.output_dir,
            "output_dir": cfg.output_dir,
            "model_name": cfg.model_name or os.environ.get("NOVEL_MODEL", "gemini-3.1-flash-lite"),
            "fallback_model": cfg.fallback_model or os.environ.get("NOVEL_FALLBACK_MODEL", "gemini-3.5-flash-lite"),
            "max_review_loops": cfg.max_review_loops,
            "quality_threshold": cfg.quality_threshold,
            "chunk_threshold_lines": cfg.chunk_threshold_lines,
            "chunk_size_lines": cfg.target_chunk_lines,
            "chunk_overlap_lines": cfg.chunk_overlap_lines,
            "config": cfg.model_dump(),
            "env": {
                "NOVEL_MODEL": os.environ.get("NOVEL_MODEL", "gemini-3.1-flash-lite"),
                "NOVEL_FALLBACK_MODEL": os.environ.get("NOVEL_FALLBACK_MODEL", "gemini-3.5-flash-lite"),
                "NOVEL_EXTRACTOR_MODEL": os.environ.get("NOVEL_EXTRACTOR_MODEL", ""),
                "NOVEL_DRAFTER_MODEL": os.environ.get("NOVEL_DRAFTER_MODEL", ""),
                "NOVEL_CRITIC_MODEL": os.environ.get("NOVEL_CRITIC_MODEL", "gemma-4-26b-a4b-it"),
                "NOVEL_POLISHER_MODEL": os.environ.get("NOVEL_POLISHER_MODEL", ""),
                "NOVEL_CHRONICLER_MODEL": os.environ.get("NOVEL_CHRONICLER_MODEL", "gemma-4-26b-a4b-it"),
                "SOURCE_LANG": os.environ.get("SOURCE_LANG", "auto"),
                "TARGET_LANG": os.environ.get("TARGET_LANG", "English"),
                "NOVEL_MAX_TPM": os.environ.get("NOVEL_MAX_TPM", "32000"),
                "NOVEL_MAX_RPM": os.environ.get("NOVEL_MAX_RPM", "60"),
            }
        }

    @app.put("/api/settings")
    async def update_settings(body: Dict[str, Any], project_path: Optional[str] = Query(None)) -> Dict[str, Any]:
        repo = _resolve_repo(project_path)
        try:
            cfg = repo.load_config()
            src = body.get("config") if isinstance(body.get("config"), dict) else body

            if "title" in src and src["title"] is not None:
                cfg.title = str(src["title"])
            if "genre" in src and src["genre"] is not None:
                cfg.genre = str(src["genre"])
            if "source_language" in src and src["source_language"] is not None:
                cfg.source_language = str(src["source_language"])
            if "target_language" in src and src["target_language"] is not None:
                cfg.target_language = str(src["target_language"])
            if "raw_dir" in src and src["raw_dir"] is not None:
                cfg.raw_dir = str(src["raw_dir"])
            if "translated_dir" in src and src["translated_dir"] is not None:
                cfg.output_dir = str(src["translated_dir"])
            elif "output_dir" in src and src["output_dir"] is not None:
                cfg.output_dir = str(src["output_dir"])
            if "model_name" in src:
                cfg.model_name = str(src["model_name"]).strip() or None
            if "fallback_model" in src:
                cfg.fallback_model = str(src["fallback_model"]).strip() or None
            if "max_review_loops" in src and src["max_review_loops"] is not None:
                cfg.max_review_loops = int(src["max_review_loops"])
            if "quality_threshold" in src and src["quality_threshold"] is not None:
                cfg.quality_threshold = float(src["quality_threshold"])
            if "chunk_threshold_lines" in src and src["chunk_threshold_lines"] is not None:
                cfg.chunk_threshold_lines = int(src["chunk_threshold_lines"])
            if "chunk_size_lines" in src and src["chunk_size_lines"] is not None:
                cfg.target_chunk_lines = int(src["chunk_size_lines"])
            elif "target_chunk_lines" in src and src["target_chunk_lines"] is not None:
                cfg.target_chunk_lines = int(src["target_chunk_lines"])
            if "chunk_overlap_lines" in src and src["chunk_overlap_lines"] is not None:
                cfg.chunk_overlap_lines = int(src["chunk_overlap_lines"])

            repo.save_config(cfg)
            return {"success": True, "config": cfg.model_dump()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid settings payload: {e}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid settings payload: {e}")

    # ------------------------------------------------------------------------
    # 6. Static File Serving & SPA Fallback
    # ------------------------------------------------------------------------

    if dist_path.exists() and dist_path.is_dir():
        # Mount assets directory
        assets_dir = dist_path / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> Response:
            # Skip API paths
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API endpoint not found")

            # Try direct file in dist
            candidate = dist_path / full_path
            if candidate.is_file():
                return FileResponse(candidate)

            # Otherwise return index.html for client-side routing
            index_file = dist_path / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)
            return JSONResponse({"message": "Frontend not built yet. Run npm run build in web/"})

    return app


# Module-level default app instance for Uvicorn
app = create_app()


class NousetsuWebHandler(http.server.SimpleHTTPRequestHandler):
    """Legacy HTTP handler serving web static assets and trace REST APIs for tests and simple scripts."""

    def __init__(self, *args: Any, dist_dir: Optional[Path] = None, **kwargs: Any) -> None:
        self.dist_dir = dist_dir or (Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist")
        super().__init__(*args, directory=str(self.dist_dir), **kwargs)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data: Any, status: int = 200) -> None:
        encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/active-project":
            registry = ProjectRegistry()
            active_p = registry.get_last_active_project() or NovelRepository().root_dir
            active_meta = _get_project_meta(active_p)
            active_meta["is_active"] = True

            all_paths = registry._load_data()
            projects = [active_meta]
            seen = {str(active_p.resolve())}

            for p_str in all_paths:
                p = Path(p_str)
                if p.exists() and (p / ".novel").exists() and str(p.resolve()) not in seen:
                    meta = _get_project_meta(p)
                    meta["is_active"] = (str(p.resolve()) == str(active_p.resolve()))
                    projects.append(meta)
                    seen.add(str(p.resolve()))

            self._send_json({
                "active_project": active_meta,
                "projects": projects,
            })
            return

        if path == "/api/sync-state":
            registry = ProjectRegistry()
            active_p = registry.get_last_active_project() or NovelRepository().root_dir
            meta = _get_project_meta(active_p)

            self._send_json({
                "active_project_path": meta["path"],
                "active_project_title": meta["title"],
                "traces_count": meta["trace_count"],
                "latest_trace_mtime": meta["latest_trace_mtime"],
            })
            return

        if path == "/api/traces":
            proj_arg = query.get("project_path", [None])[0]
            if proj_arg:
                target_p = Path(proj_arg).resolve()
            else:
                registry = ProjectRegistry()
                target_p = registry.get_last_active_project() or NovelRepository().root_dir

            if not target_p.exists():
                self._send_json({"error": f"Project directory not found: {target_p}"}, status=404)
                return

            meta = _get_project_meta(target_p)
            chapters = _load_project_traces(target_p)

            self._send_json({
                "project_path": meta["path"],
                "project_title": meta["title"],
                "genre": meta["genre"],
                "chapters": chapters,
            })
            return

        clean_path = path.lstrip("/")
        candidate_file = self.dist_dir / clean_path

        if clean_path and candidate_file.exists() and candidate_file.is_file():
            super().do_GET()
            return

        index_file = self.dist_dir / "index.html"
        if index_file.exists():
            with open(index_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/active-project":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(length)
                payload = json.loads(body_bytes.decode("utf-8"))
                new_path_str = payload.get("project_path")

                if not new_path_str:
                    self._send_json({"error": "Missing 'project_path' parameter"}, status=400)
                    return

                new_path = Path(new_path_str).resolve()
                if not new_path.exists() or not (new_path / ".novel").exists():
                    self._send_json({"error": f"Invalid project path: {new_path}"}, status=400)
                    return

                registry = ProjectRegistry()
                registry.set_last_active_project(new_path)
                meta = _get_project_meta(new_path)
                meta["is_active"] = True

                self._send_json({
                    "success": True,
                    "active_project": meta,
                })
            except Exception as e:
                self._send_json({"error": f"Failed to switch project: {e}"}, status=500)
            return

        self._send_json({"error": f"Not found: {path}"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        pass


def run_web_server(
    port: int = 5173,
    host: str = "127.0.0.1",
    open_browser: bool = False,
    dist_dir: Optional[Path] = None
) -> None:
    """Run the Nousetsu web server hosting the dashboard and trace sync API."""
    server_app = create_app(dist_dir=dist_dir)
    url = f"http://{host}:{port}"

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    logger.info("Starting Nousetsu Web Dashboard on %s", url)
    uvicorn.run(server_app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_web_server(port=5173, open_browser=True)
