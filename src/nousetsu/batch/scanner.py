import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from natsort import natsorted
from nousetsu.models.metadata import ChapterMetadata, PipelineStage, StageStatus
from nousetsu.storage.repository import NovelRepository
from nousetsu.utils.chapter import LEADING_SEQ_PATTERN, extract_chapter_num

logger = logging.getLogger(__name__)


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
    folder: Optional[str] = None


class ChapterScanner:
    """Discovers and prepares chapter translation tasks from folder."""

    def __init__(self, repository: NovelRepository):
        self.repo = repository
        self._sha256_cache: dict[tuple[str, int, float], str] = {}

    def get_file_sha256(self, src_file: Path) -> str:
        """Compute or retrieve cached SHA256 checksum based on file size and modification time."""
        try:
            st = src_file.stat()
            key = (str(src_file.resolve()), st.st_size, st.st_mtime)
            cached = self._sha256_cache.get(key)
            if cached is not None:
                return cached
            val = self.repo.compute_sha256(src_file)
            self._sha256_cache[key] = val
            return val
        except Exception:
            return self.repo.compute_sha256(src_file)

    def clear_sha256_cache(self) -> None:
        """Clear SHA256 file checksum cache."""
        self._sha256_cache.clear()

    def extract_chapter_num(self, path: Path, default_idx: int) -> int:
        """Extract numeric chapter index from filename using canonical extractor."""
        return extract_chapter_num(path, default_idx)

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
        seen_chapter_nums: dict[int, Path] = {}

        for idx, src_file in enumerate(sorted_files, start=1):
            ch_num = self.extract_chapter_num(src_file, idx)

            # Auto-align duplicate chapter numbers within the same directory scan
            if ch_num in seen_chapter_nums:
                original_ch_num = ch_num
                seq_m = LEADING_SEQ_PATTERN.match(src_file.stem)
                if seq_m and int(seq_m.group(1)) not in seen_chapter_nums:
                    ch_num = int(seq_m.group(1))
                else:
                    max_seen = max(seen_chapter_nums.keys()) if seen_chapter_nums else 0
                    ch_num = max_seen + 1

                logger.warning(
                    f"Chapter collision in '{input_path.name}': '{src_file.name}' (extracted {original_ch_num}) "
                    f"collided with '{seen_chapter_nums[original_ch_num].name}'. Auto-realigned to chapter {ch_num}."
                )

            seen_chapter_nums[ch_num] = src_file
            out_file = output_path / f"{src_file.stem}.md"
            src_sha256 = self.get_file_sha256(src_file)

            # Look up metadata from single project doc (composite key first, fallback to stem and load_metadata)
            composite_key = f"{output_path.name}/{src_file.stem}"
            meta = all_metadata.get(composite_key) or all_metadata.get(src_file.stem) or self.repo.load_metadata(out_file)
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
                resume_stage=resume_stage,
                folder=input_path.name
            ))

        return tasks
