"""Batch scanner for discovering, naturally sorting, and inspecting chapters."""
from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Optional
from natsort import natsorted
from src.models.metadata import ChapterMetadata, PipelineStage, StageStatus
from src.storage.repository import NovelRepository


@dataclass
class ChapterTask:
    chapter_num: int
    source_file: Path
    output_file: Path
    source_sha256: str
    existing_meta: Optional[ChapterMetadata] = None
    is_completed: bool = False
    is_failed: bool = False
    is_paused: bool = False
    last_error: Optional[str] = None
    needs_resume: bool = False
    resume_stage: PipelineStage = PipelineStage.NONE


class ChapterScanner:
    """Discovers and prepares chapter translation tasks from folder."""

    def __init__(self, repository: NovelRepository):
        self.repo = repository

    def extract_chapter_num(self, path: Path, default_idx: int) -> int:
        """Extract numeric chapter index from filename using regex or fallback to sequential index."""
        name = path.stem
        match = re.search(r"(?:chapter|ch|ep|第)?\s*(\d+)", name, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return default_idx

    def scan_directory(self, input_dir: Path, output_dir: Path) -> List[ChapterTask]:
        """Scan input directory, sort naturally, pair with metadata, and flag status."""
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if not input_path.exists():
            return []

        # Support both .txt and .md chapter sources
        raw_files = [f for f in input_path.iterdir() if f.is_file() and f.suffix.lower() in [".txt", ".md"]]
        sorted_files = natsorted(raw_files, key=lambda f: f.name)

        # Single I/O read: load all project chapter metadata at once
        all_metadata = self.repo.load_all_metadata()

        tasks: List[ChapterTask] = []

        for idx, src_file in enumerate(sorted_files, start=1):
            ch_num = self.extract_chapter_num(src_file, idx)
            out_file = output_path / f"{src_file.stem}.md"
            src_sha256 = self.repo.compute_sha256(src_file)

            # Look up metadata from single project doc, fallback to load_metadata
            meta = all_metadata.get(src_file.stem) or self.repo.load_metadata(out_file)
            is_done = False
            is_failed = False
            is_paused = False
            last_err = None
            needs_resume = False
            resume_stage = PipelineStage.NONE

            if meta:
                # If completed and hash matches, chapter is up to date!
                if meta.checkpoint.status == StageStatus.COMPLETED and meta.source_sha256 == src_sha256 and out_file.exists():
                    is_done = True
                elif meta.checkpoint.status == StageStatus.FAILED:
                    is_failed = True
                    last_err = meta.checkpoint.last_error
                    if meta.source_sha256 == src_sha256 and meta.checkpoint.is_resumable():
                        needs_resume = True
                        resume_stage = meta.checkpoint.last_completed_stage
                elif meta.checkpoint.status == StageStatus.PAUSED:
                    is_paused = True
                    if meta.source_sha256 == src_sha256 and meta.checkpoint.is_resumable():
                        needs_resume = True
                        resume_stage = meta.checkpoint.last_completed_stage
                elif meta.source_sha256 == src_sha256 and meta.checkpoint.is_resumable():
                    needs_resume = True
                    resume_stage = meta.checkpoint.last_completed_stage

            tasks.append(ChapterTask(
                chapter_num=ch_num,
                source_file=src_file,
                output_file=out_file,
                source_sha256=src_sha256,
                existing_meta=meta,
                is_completed=is_done,
                is_failed=is_failed,
                is_paused=is_paused,
                last_error=last_err,
                needs_resume=needs_resume,
                resume_stage=resume_stage
            ))

        return tasks
