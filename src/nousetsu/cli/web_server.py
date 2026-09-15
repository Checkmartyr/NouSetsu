"""HTTP Server and REST API for the Nousetsu Web Trace Visualizer."""
from __future__ import annotations

import http.server
import json
import logging
import os
import re
import socketserver
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from nousetsu.storage.repository import NovelRepository, ProjectRegistry

logger = logging.getLogger(__name__)


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
    config_file = novel_dir / "config.json"
    bible_file = novel_dir / "bible.json"
    traces_dir = novel_dir / "traces"

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                title = cfg.get("title", title)
                src_lang = cfg.get("source_language", src_lang)
                tgt_lang = cfg.get("target_language", tgt_lang)
        except Exception:
            pass

    if bible_file.exists():
        try:
            with open(bible_file, "r", encoding="utf-8") as f:
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

    # Map of key -> chapter entry
    chapters_map: Dict[str, Dict[str, Any]] = {}

    # Prefer .json files first, then fallback to .jsonl
    candidate_files = sorted(
        list(traces_dir.rglob("chapter_*.json")) + list(traces_dir.rglob("chapter_*.jsonl")),
        key=lambda p: (0 if p.suffix == ".json" else 1, p.name)
    )

    for tf in candidate_files:
        try:
            # Determine relative folder (e.g. Villainess_05 or None)
            rel_parts = tf.relative_to(traces_dir).parts
            folder = rel_parts[0] if len(rel_parts) > 1 else None

            # Extract chapter number
            m = re.search(r"chapter_(\d+)", tf.stem)
            chapter_num = int(m.group(1)) if m else 1
            key = f"{folder or 'root'}_ch{chapter_num}"

            if key in chapters_map and tf.suffix == ".jsonl":
                continue

            if tf.suffix == ".json":
                with open(tf, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            else:
                # Parse JSONL
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

    # Sort chapters logically
    loaded = list(chapters_map.values())
    loaded.sort(key=lambda c: (c.get("folder") or "", c.get("chapterNum", 0)))
    return loaded


class NousetsuWebHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler serving web static assets and trace REST APIs."""

    def __init__(self, *args, dist_dir: Optional[Path] = None, **kwargs):
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
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # 1. API: Active Project & Registered Projects List
        if path == "/api/active-project":
            registry = ProjectRegistry()
            active_p = registry.get_last_active_project() or NovelRepository().root_dir
            active_meta = _get_project_meta(active_p)
            active_meta["is_active"] = True

            all_paths = registry._load_data()
            projects = []
            seen = set()

            # Include active_p first
            projects.append(active_meta)
            seen.add(str(active_p.resolve()))

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

        # 2. API: Lightweight Sync State for 2.5s Polling
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

        # 3. API: Load Traces for Project
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

        # 4. Static Files & SPA Fallback
        # If path corresponds to an existing file in dist_dir, serve it normally
        clean_path = path.lstrip("/")
        candidate_file = self.dist_dir / clean_path

        if clean_path and candidate_file.exists() and candidate_file.is_file():
            super().do_GET()
            return

        # SPA fallback: serve index.html for root or unknown client routes
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

        # Fallback to standard handler
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
                    self._send_json({"error": f"Invalid project path (missing .novel directory): {new_path}"}, status=400)
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
        # Suppress chatty default request logs
        pass


def run_web_server(
    port: int = 5173,
    host: str = "127.0.0.1",
    open_browser: bool = False,
    dist_dir: Optional[Path] = None
) -> None:
    """Run the Nousetsu web server hosting the visualizer and trace sync API."""
    def handler_factory(*args, **kwargs):
        return NousetsuWebHandler(*args, dist_dir=dist_dir, **kwargs)

    url = f"http://{host}:{port}"
    try:
        with socketserver.TCPServer((host, port), handler_factory) as httpd:
            if open_browser:
                webbrowser.open(url)
            httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError as e:
        logger.error("Failed to bind web server on %s:%d: %s", host, port, e)
