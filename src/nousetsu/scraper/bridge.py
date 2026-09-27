"""
Scraper Bridge: executes Novel-Scraper commands via subprocess and handles streaming progress.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from nousetsu.scraper.detector import find_scraper_directory, find_scraper_python, get_scraper_info
from nousetsu.scraper.models import (
    ScraperChapterItem,
    ScraperExtractRequest,
    ScraperInspectResponse,
    ScraperStatusResponse,
)

logger = logging.getLogger("nousetsu.scraper.bridge")


class NovelScraperBridge:
    """Manages headless execution of Novel-Scraper submodule/companion repo."""

    def __init__(
        self,
        scraper_dir: Optional[Path] = None,
        python_exe: Optional[Path] = None,
    ):
        self.scraper_dir = scraper_dir or find_scraper_directory()
        self.python_exe = python_exe or find_scraper_python(self.scraper_dir)

    def is_available(self) -> bool:
        """Check if scraper environment and python interpreter are present."""
        return (
            self.scraper_dir is not None
            and self.scraper_dir.is_dir()
            and self.python_exe is not None
            and self.python_exe.is_file()
        )

    async def inspect_url(self, url: str) -> ScraperInspectResponse:
        """Inspect a webnovel URL (TOC or chapter), discovering chapter list and metadata."""
        if not self.is_available():
            return ScraperInspectResponse(
                success=False,
                url=url,
                error="Novel-Scraper is not installed or configured. Please initialize the git submodule or configure NOVEL_SCRAPER_PATH.",
            )

        cmd = [
            str(self.python_exe),
            "-m",
            "src.api_bridge",
            "inspect",
            "--url",
            url,
        ]

        logger.info("Executing inspect: %s in %s", " ".join(cmd), self.scraper_dir)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.scraper_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_data, stderr_data = await proc.communicate()

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
                ScraperChapterItem(index=c["index"], title=c["title"], url=c["url"])
                for c in data.get("chapters", [])
            ]

            return ScraperInspectResponse(
                success=data.get("success", True),
                url=url,
                page_type=data.get("page_type", "TOC"),
                novel_title=data.get("novel_title", "Unknown Novel"),
                author=data.get("author"),
                description=data.get("description"),
                total_chapters=data.get("total_chapters", len(chapters)),
                chapters=chapters,
                error=data.get("error"),
            )
        except Exception as e:
            logger.exception("Failed during scraper inspect: %s", e)
            return ScraperInspectResponse(
                success=False,
                url=url,
                error=str(e),
            )

    async def extract_chapters(
        self,
        req: ScraperExtractRequest,
        dest_dir: Path,
        on_progress: Optional[Callable[[ScraperStatusResponse], None]] = None,
        task_id: Optional[str] = None,
    ) -> ScraperStatusResponse:
        """
        Run batch extraction from webnovel URL, saving chapters directly to dest_dir.
        Streams status updates through on_progress callback.
        """
        task_id = task_id or str(uuid.uuid4())[:8]

        if not self.is_available():
            return ScraperStatusResponse(
                task_id=task_id,
                status="failed",
                message="Novel-Scraper environment is not available.",
                error="Novel-Scraper is not installed or configured.",
            )

        dest_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.python_exe),
            "-m",
            "src.api_bridge",
            "extract",
            "--url",
            req.url,
            "--dest",
            str(dest_dir.resolve()),
            "--concurrency",
            str(req.concurrency),
        ]

        if req.chapter_indices:
            cmd.extend(["--indices", ",".join(str(i) for i in req.chapter_indices)])
        if req.start_chapter is not None:
            cmd.extend(["--start", str(req.start_chapter)])
        if req.end_chapter is not None:
            cmd.extend(["--end", str(req.end_chapter)])
        if req.include_frontmatter:
            cmd.append("--frontmatter")

        logger.info("Starting scraper extraction [%s]: %s in %s", task_id, " ".join(cmd), self.scraper_dir)

        status_obj = ScraperStatusResponse(
            task_id=task_id,
            status="running",
            progress_percent=0.0,
            current_chapter=0,
            total_chapters=0,
            message="Initializing browser and analyzing page layout...",
            output_dir=str(dest_dir),
        )

        if on_progress:
            on_progress(status_obj)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.scraper_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            completed_files: List[str] = []

            # Read streaming JSON lines from stdout
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break

                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue

                try:
                    payload = json.loads(text)
                    evt_type = payload.get("type")

                    if evt_type == "progress":
                        curr = payload.get("current", 0)
                        tot = payload.get("total", 1)
                        pct = payload.get("percent", round((curr / tot) * 100, 1) if tot else 0.0)
                        title = payload.get("title", "")

                        status_obj.progress_percent = pct
                        status_obj.current_chapter = curr
                        status_obj.total_chapters = tot
                        status_obj.current_title = title
                        status_obj.message = f"Scraping chapter {curr}/{tot}: {title}"
                        if on_progress:
                            on_progress(status_obj)

                    elif evt_type == "completed":
                        completed_files = payload.get("files", [])
                        status_obj.status = "completed" if payload.get("success", True) else "failed"
                        status_obj.progress_percent = 100.0
                        status_obj.completed_files = completed_files
                        status_obj.message = f"Successfully downloaded {len(completed_files)} chapters."
                        if on_progress:
                            on_progress(status_obj)

                except json.JSONDecodeError:
                    logger.debug("Non-JSON stdout from scraper: %s", text)

            await proc.wait()

            if proc.returncode != 0 and status_obj.status != "completed":
                stderr_text = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
                status_obj.status = "failed"
                status_obj.error = stderr_text or f"Scraper process exited with code {proc.returncode}"
                status_obj.message = f"Extraction failed: {status_obj.error}"
                if on_progress:
                    on_progress(status_obj)
            else:
                # Scan dest_dir for freshly extracted files if list is empty
                if not status_obj.completed_files:
                    found_files = sorted([f.name for f in dest_dir.glob("*.md")])
                    status_obj.completed_files = found_files
                    status_obj.status = "completed"
                    status_obj.progress_percent = 100.0
                    status_obj.message = f"Completed! {len(found_files)} chapters ready."
                    if on_progress:
                        on_progress(status_obj)

            return status_obj

        except Exception as e:
            logger.exception("Scraper extract task failed: %s", e)
            status_obj.status = "failed"
            status_obj.error = str(e)
            status_obj.message = f"Scraper error: {e}"
            if on_progress:
                on_progress(status_obj)
            return status_obj
