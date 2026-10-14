"""
Scraper Bridge: executes Novel-Scraper commands via subprocess and handles streaming progress.
"""

from nousetsu.utils.env import resolve_env
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from nousetsu.scraper.detector import (
    find_scraper_directory,
    find_scraper_python,
    get_repo_root,
    get_scraper_info,
    is_bundled_scraper_runtime,
)
from nousetsu.scraper.models import (
    ScraperChapterItem,
    ScraperExtractRequest,
    ScraperInspectResponse,
    ScraperStatusResponse,
)

logger = logging.getLogger("nousetsu.scraper.bridge")

_BUNDLED_BRIDGE_RUNNER = (
    "import runpy, sys; "
    "scraper_root, bridge_path = sys.argv[1:3]; "
    "sys.path.insert(0, scraper_root); "
    "sys.argv = [bridge_path, *sys.argv[3:]]; "
    "runpy.run_path(bridge_path, run_name='__main__')"
)


class NovelScraperBridge:
    """Manages headless execution of Novel-Scraper submodule/companion repo."""

    def __init__(
        self,
        scraper_dir: Optional[Path] = None,
        python_exe: Optional[Path] = None,
    ):
        self._bundled_worker = (
            scraper_dir is None
            and python_exe is None
            and is_bundled_scraper_runtime()
        )
        self.scraper_dir = scraper_dir or find_scraper_directory()
        self.python_exe = python_exe or find_scraper_python(self.scraper_dir)

    def is_available(self) -> bool:
        """Check that the bundled worker or external scraper environment is present."""
        if self._bundled_worker:
            return self.python_exe is not None and self.python_exe.is_file()
        return (
            self.scraper_dir is not None
            and self.scraper_dir.is_dir()
            and self.python_exe is not None
            and self.python_exe.is_file()
        )

    def _working_directory(self) -> Path:
        if self._bundled_worker:
            app_data_dir = resolve_env().get("NOUSETSU_APP_DATA_DIR")
            if app_data_dir:
                return Path(app_data_dir).resolve()
        if self.scraper_dir is None:
            raise RuntimeError("Novel-Scraper is not available.")
        return self.scraper_dir

    def _bundled_api_bridge_path(self) -> Optional[Path]:
        """Find NouSetsu's packaged adapter for companion checkouts without api_bridge.py."""
        if getattr(sys, "frozen", False):
            extraction_dir = getattr(sys, "_MEIPASS", None)
            if extraction_dir:
                packaged_bridge = Path(extraction_dir) / "nousetsu" / "scraper" / "api_bridge.py"
                if packaged_bridge.is_file():
                    return packaged_bridge

        source_bridge = get_repo_root() / "modules" / "novel_scraper" / "src" / "api_bridge.py"
        return source_bridge if source_bridge.is_file() else None

    def _api_bridge_command(self, operation: str, *args: str) -> List[str]:
        if self.python_exe is None:
            raise RuntimeError("Novel-Scraper is not available.")

        if self._bundled_worker:
            return [str(self.python_exe), "--scraper-worker", operation, *args]

        if self.scraper_dir is None:
            raise RuntimeError("Novel-Scraper is not available.")

        companion_bridge = self.scraper_dir / "src" / "api_bridge.py"
        if companion_bridge.is_file():
            return [str(self.python_exe), "-m", "src.api_bridge", operation, *args]

        bundled_bridge = self._bundled_api_bridge_path()
        if bundled_bridge is None:
            raise FileNotFoundError(
                "The Novel-Scraper checkout is missing src/api_bridge.py and NouSetsu's bundled adapter is unavailable."
            )

        logger.info("Using bundled scraper adapter for companion checkout at %s", self.scraper_dir)
        return [
            str(self.python_exe),
            "-c",
            _BUNDLED_BRIDGE_RUNNER,
            str(self.scraper_dir),
            str(bundled_bridge),
            operation,
            *args,
        ]

    async def romanize_title(self, title: str) -> str:
        """Romanize a title with the Novel-Scraper's language-aware utility."""
        cleaned_title = title.strip()
        if not cleaned_title or not self.is_available():
            return cleaned_title

        if self._bundled_worker:
            command = [str(self.python_exe), "--scraper-worker", "romanize", cleaned_title]
        else:
            script = (
                "from src.utils.romanizer import romanize_text; "
                "import sys; print(romanize_text(sys.argv[1]))"
            )
            command = [str(self.python_exe), "-c", script, cleaned_title]
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self._working_directory()),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                err_text = stderr_data.decode("utf-8", errors="replace").strip()
                logger.warning("Novel title romanization failed: %s", err_text)
                return cleaned_title

            return stdout_data.decode("utf-8", errors="replace").strip() or cleaned_title
        except Exception:
            logger.exception("Failed to romanize novel title")
            return cleaned_title

    async def inspect_url(
        self, url: str, env: Optional[Dict[str, str]] = None
    ) -> ScraperInspectResponse:
        """Inspect a webnovel URL (TOC or chapter), discovering chapter list and metadata."""
        if not self.is_available():
            return ScraperInspectResponse(
                success=False,
                url=url,
                error="Novel-Scraper is not installed or configured. Please initialize the git submodule or configure NOVEL_SCRAPER_PATH.",
            )

        cmd = self._api_bridge_command("inspect", "--url", url)

        working_dir = self._working_directory()
        logger.info("Executing inspect: %s in %s", " ".join(cmd), working_dir)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **({"env": env} if env is not None else {}),
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=float((env or {}).get("NOVEL_SCRAPER_DISCOVERY_SECONDS", "600")) + 15)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                proc.kill()
                await proc.wait()
                raise

            if proc.returncode != 0:
                err_text = stderr_data.decode("utf-8", errors="replace").strip()
                logger.error("Scraper inspect failed (exit code %d): %s", proc.returncode, err_text)
                return ScraperInspectResponse(
                    success=False,
                    url=url,
                    error=f"Scraper error (code {proc.returncode}): {err_text or 'Unknown failure'}",
                )

            out_text = stdout_data.decode("utf-8", errors="replace").strip()
            # api_bridge inspect outputs JSON on stdout
            data = json.loads(out_text)

            chapters = [
                ScraperChapterItem(index=c["index"], title=c["title"], url=c["url"], volume=c.get("volume"))
                for c in data.get("chapters", [])
            ]
            novel_title = data.get("novel_title", "Unknown Novel")
            romanized_title = await self.romanize_title(novel_title)

            return ScraperInspectResponse(
                success=data.get("success", True),
                url=url,
                page_type=data.get("page_type", "TOC"),
                toc_url=data.get("toc_url"),
                novel_title=novel_title,
                romanized_title=romanized_title,
                author=data.get("author"),
                description=data.get("description"),
                total_chapters=data.get("total_chapters", len(chapters)),
                chapters=chapters,
                error=data.get("error"),
                is_complete=data.get("is_complete", False),
                claimed_chapter_count=data.get("claimed_chapter_count"),
                confidence_score=data.get("confidence_score", 0),
                completeness_evidence=data.get("completeness_evidence", []),
                issues=data.get("issues", []),
                metrics=data.get("metrics", {}),
            )
        except Exception as e:
            logger.exception("Failed during scraper inspect: %s", e)
            return ScraperInspectResponse(
                success=False,
                url=url,
                error=str(e),
            )

    async def extract_chapters(
        self, req: ScraperExtractRequest, dest_dir: Path, on_progress=None,
        task_id: Optional[str] = None, env: Optional[Dict[str, str]] = None,
    ) -> ScraperStatusResponse:
        """Consume a bounded JSON-lines protocol; an exit or old file is not success."""
        task_id = task_id or uuid.uuid4().hex
        status_obj = ScraperStatusResponse(task_id=task_id, status="running", url=req.url,
            stage="discovery", output_dir=str(dest_dir), message="Discovering accessible catalog")
        if not self.is_available():
            status_obj.status, status_obj.error = "failed", "Scraper environment unavailable"
            return status_obj
        worker_env = dict(env if env is not None else resolve_env())
        if req.budgets:
            worker_env.update({f"NOVEL_SCRAPER_{name.upper()}": str(value)
                              for name, value in req.budgets.model_dump(exclude_none=True).items()})
        if req.session_state:
            if not Path(req.session_state).is_file():
                raise ValueError("Authorized browser state file does not exist")
            worker_env["NOVEL_SCRAPER_STORAGE_STATE"] = req.session_state
        root = Path(req.project_path).resolve() if req.project_path else None
        state_dir = root / ".novel" / "scraper" if root else dest_dir / ".scraper"
        cmd = self._api_bridge_command("extract", "--url", req.url, "--dest", str(dest_dir.resolve()),
            "--concurrency", str(req.concurrency), "--state-dir", str(state_dir), "--job-id", task_id)
        if req.chapter_indices is not None:
            cmd.extend(["--indices", ",".join(str(i) for i in req.chapter_indices)])
        for value, flag in ((req.start_chapter, "--start"), (req.end_chapter, "--end")):
            if value is not None:
                cmd.extend([flag, str(value)])
        if req.include_frontmatter:
            cmd.append("--frontmatter")
        if req.overwrite:
            cmd.append("--overwrite")
        if req.inspection_id:
            snapshot = state_dir / "inspections" / f"{req.inspection_id}.json"
            if not snapshot.is_file():
                raise ValueError("Inspection snapshot is missing or belongs to another project")
            cmd.extend(["--snapshot-file", str(snapshot)])
        if on_progress:
            on_progress(status_obj)
        proc = None
        stderr_task = watcher = None
        stderr_tail = bytearray()
        terminal = None
        cancelled = False
        async def consume_stderr():
            while True:
                chunk = await proc.stderr.read(4096)
                if not chunk:
                    return
                stderr_tail.extend(chunk)
                if len(stderr_tail) > 65536:
                    del stderr_tail[:-65536]
        async def stop_process():
            if proc is not None and proc.returncode is None:
                if os.name == "nt":
                    killer = await asyncio.create_subprocess_exec("taskkill", "/PID", str(proc.pid), "/T", "/F",
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                    await killer.wait()
                else:
                    proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), 5)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
        async def observe_cancel():
            nonlocal cancelled
            marker = state_dir / "jobs" / f"{task_id}.cancel"
            while proc.returncode is None:
                if marker.exists():
                    cancelled = True
                    # Give the worker time to checkpoint pending outcomes.
                    await asyncio.sleep(1)
                    await stop_process()
                    return
                await asyncio.sleep(0.1)
        async def consume_stdout():
            nonlocal terminal
            while True:
                line = await asyncio.wait_for(proc.stdout.readline(),
                    timeout=float(worker_env.get("NOVEL_SCRAPER_DISCOVERY_SECONDS", "600")) + 600)
                if not line:
                    break
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "progress":
                    status_obj.stage = payload.get("stage", "downloading")
                    status_obj.current_chapter = payload.get("current", 0)
                    status_obj.total_chapters = payload.get("total", 0)
                    status_obj.progress_percent = max(0, min(100, payload.get("percent", 0)))
                    status_obj.current_title = payload.get("title") or payload.get("message")
                    status_obj.message = payload.get("message", "")
                    if on_progress:
                        on_progress(status_obj)
                elif payload.get("type") == "completed":
                    if terminal is not None:
                        raise RuntimeError("Worker emitted multiple terminal results")
                    if payload.get("result_file"):
                        expected = (state_dir / "results" / f"{task_id}.json").resolve()
                        if Path(payload["result_file"]).resolve() != expected:
                            raise RuntimeError("Worker result file is outside this job")
                        terminal = json.loads(expected.read_text(encoding="utf-8"))
                    else:
                        terminal = payload
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(self._working_directory()),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=worker_env)
            if proc.stdout is None or proc.stderr is None:
                raise RuntimeError("Worker streams unavailable")
            stderr_task = asyncio.create_task(consume_stderr())
            watcher = asyncio.create_task(observe_cancel())
            await consume_stdout()
            await proc.wait()
            await stderr_task
            if cancelled:
                status_obj.status = "cancelled"
                status_obj.message = "Extraction cancelled; verified chapters retained for resume"
                snapshot_path = state_dir / "snapshots" / f"{task_id}.json"
                checkpoint_path = state_dir / "checkpoints" / f"{task_id}.json"
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.is_file() else {}
                records = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.is_file() else {}
                for record_path in (state_dir / "checkpoints" / task_id).glob("*.json"):
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                    records[record["url"]] = record
                records = {record.get("url", key): record for key, record in records.items()}
                import hashlib
                for chapter in snapshot.get("chapters", []):
                    index = chapter["index"]
                    if req.chapter_indices is not None and index not in req.chapter_indices:
                        continue
                    if req.chapter_indices is None and ((req.start_chapter is not None and index < req.start_chapter) or (req.end_chapter is not None and index > req.end_chapter)):
                        continue
                    record = records.get(chapter["url"], {})
                    path = dest_dir / record.get("file", "")
                    if record.get("success") and path.parent == dest_dir and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == record.get("sha256"):
                        status_obj.outcomes.append(record)
                        status_obj.completed_files.append(path.name)
                    else:
                        status_obj.outcomes.append({**chapter, "status": "cancelled", "success": False})
                status_obj.saved = sum(record.get("status") == "saved" for record in status_obj.outcomes)
                status_obj.skipped = sum(record.get("status") == "skipped" for record in status_obj.outcomes)
                status_obj.cancelled = len(status_obj.outcomes) - len(status_obj.completed_files)
                status_obj.current_chapter = status_obj.total_chapters = len(status_obj.outcomes)
                status_obj.stage = "cancelled"
            elif proc.returncode != 0 or terminal is None:
                raise RuntimeError(f"Worker exited with code {proc.returncode} without a valid terminal result")
            else:
                state = terminal.get("status")
                if state not in {"completed", "partial", "paused", "failed", "cancelled"}:
                    state = "completed" if terminal.get("success") and not terminal.get("failed") and not terminal.get("blocked") else "failed"
                if state == "completed":
                    if not terminal.get("success") or not terminal.get("is_complete") or any(terminal.get(field, 0) for field in ("failed", "blocked", "cancelled")):
                        raise RuntimeError("Worker claimed completion without resolved coverage and successful chapters")
                    selected_count = terminal.get("total_selected", 0)
                    if not selected_count or len(terminal.get("files", [])) != selected_count or len(terminal.get("outcomes", [])) != selected_count:
                        raise RuntimeError("Worker completion counts do not match selected chapter outcomes")
                    if any(outcome.get("status") not in {"saved", "skipped"} for outcome in terminal["outcomes"]):
                        raise RuntimeError("Worker completed with unsuccessful chapter outcomes")
                status_obj.status = state
                status_obj.completed_files = terminal.get("files", [])
                for field in ("saved", "skipped", "failed", "blocked", "cancelled", "is_complete",
                              "completeness_evidence", "issues", "metrics", "outcomes"):
                    if field in terminal:
                        setattr(status_obj, field, terminal[field])
                status_obj.error = terminal.get("error")
                if status_obj.outcomes:
                    for field in ("saved", "skipped", "failed", "blocked", "cancelled"):
                        setattr(status_obj, field, sum(outcome.get("status") == field for outcome in status_obj.outcomes))
                status_obj.total_chapters = terminal.get("total_selected", status_obj.total_chapters)
                status_obj.current_chapter = len(status_obj.outcomes) or terminal.get("completed", 0)
                status_obj.progress_percent = round(status_obj.current_chapter / max(status_obj.total_chapters, 1) * 100, 1)
                status_obj.stage = state
                status_obj.message = (f"Saved {status_obj.saved}, skipped {status_obj.skipped}, "
                    f"failed {status_obj.failed}, blocked {status_obj.blocked}. Status: {state}.")
            if on_progress:
                on_progress(status_obj)
            return status_obj
        except asyncio.CancelledError:
            await stop_process()
            raise
        except Exception as error:
            await stop_process()
            status_obj.status, status_obj.stage = "failed", "failed"
            status_obj.error = str(error)
            diagnostic = stderr_tail.decode("utf-8", errors="replace")[-2000:]
            for key, value in worker_env.items():
                if any(term in key.upper() for term in ("KEY", "TOKEN", "SECRET", "PASSWORD")) and len(value) > 5:
                    diagnostic = diagnostic.replace(value, "[redacted]")
            status_obj.message = status_obj.error + (": " + diagnostic if diagnostic else "")
            if on_progress:
                on_progress(status_obj)
            return status_obj
        finally:
            for task in (watcher, stderr_task):
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(*(task for task in (watcher, stderr_task) if task), return_exceptions=True)
