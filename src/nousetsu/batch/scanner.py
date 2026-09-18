import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
from natsort import natsorted

from nousetsu.models.metadata import ChapterMetadata, PipelineStage, StageStatus
from nousetsu.storage.repository import (
    NovelRepository,
    get_projects_root_dir,
    resolve_project_dir,
)
from nousetsu.utils.chapter import LEADING_SEQ_PATTERN, extract_chapter_num

logger = logging.getLogger(__name__)

_GLOBAL_SHA256_CACHE: dict[tuple[str, int, float], str] = {}


class ChapterTask:
    """Represents a discovered chapter unit ready for pipeline translation."""

    def __init__(
        self,
        chapter_num: int,
        source_file: Path,
        output_file: Path,
        source_sha256: str = "",
        existing_meta: Optional[ChapterMetadata] = None,
        is_completed: bool = False,
        is_failed: bool = False,
        is_paused: bool = False,
        last_error: Optional[str] = None,
        needs_resume: bool = False,
        resume_stage: PipelineStage = PipelineStage.NONE,
        folder: Optional[str] = None,
    ) -> None:
        self.chapter_num = chapter_num
        self.source_file = Path(source_file)
        self.output_file = Path(output_file)
        self._source_sha256: str = source_sha256
        self.existing_meta = existing_meta
        self.is_completed = is_completed
        self.is_failed = is_failed
        self.is_paused = is_paused
        self.last_error = last_error
        self.needs_resume = needs_resume
        self.resume_stage = resume_stage
        self.folder = folder

    @property
    def source_sha256(self) -> str:
        """Lazily compute and cache source file SHA-256 on demand if not already populated."""
        if not self._source_sha256 and self.source_file.exists():
            self._source_sha256 = ChapterScanner.compute_file_sha256(self.source_file)
        return self._source_sha256 or ""

    @source_sha256.setter
    def source_sha256(self, value: str) -> None:
        self._source_sha256 = value

    def __repr__(self) -> str:
        return (
            f"ChapterTask(chapter_num={self.chapter_num}, source_file={self.source_file!r}, "
            f"output_file={self.output_file!r}, is_completed={self.is_completed}, folder={self.folder!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChapterTask):
            return False
        return (
            self.chapter_num == other.chapter_num
            and self.source_file == other.source_file
            and self.output_file == other.output_file
            and self.is_completed == other.is_completed
            and self.folder == other.folder
        )


class ChapterScanner:
    """Discovers, prepares, and optimizes chapter translation tasks from novel directories.
    
    Supports single-volume folders, multi-volume projects, and cross-project discovery
    via NOVEL_PROJECTS_DIR.
    """

    def __init__(self, repository: Optional[Union[NovelRepository, str, Path]] = None) -> None:
        if isinstance(repository, NovelRepository):
            self.repo = repository
        else:
            resolved_path = resolve_project_dir(repository)
            self.repo = NovelRepository(resolved_path)
        self._sha256_cache: dict[tuple[str, int, float], str] = _GLOBAL_SHA256_CACHE

    @classmethod
    def compute_file_sha256(
        cls,
        src_file: Path,
        st_size: Optional[int] = None,
        st_mtime: Optional[float] = None
    ) -> str:
        """Compute or retrieve cached SHA256 checksum based on file size and modification time."""
        try:
            if not src_file.exists():
                return ""
            if st_size is None or st_mtime is None:
                st = src_file.stat()
                st_size = st.st_size
                st_mtime = st.st_mtime
            key = (str(src_file.resolve()), st_size, st_mtime)
            cached = _GLOBAL_SHA256_CACHE.get(key)
            if cached is not None:
                return cached
            val = NovelRepository.compute_sha256(src_file)
            _GLOBAL_SHA256_CACHE[key] = val
            return val
        except Exception:
            try:
                return NovelRepository.compute_sha256(src_file)
            except Exception:
                return ""

    def get_file_sha256(
        self,
        src_file: Path,
        st_size: Optional[int] = None,
        st_mtime: Optional[float] = None
    ) -> str:
        """Compute or retrieve cached SHA256 checksum (instance method delegate)."""
        return self.compute_file_sha256(src_file, st_size=st_size, st_mtime=st_mtime)

    @classmethod
    def clear_sha256_cache(cls) -> None:
        """Clear global SHA256 file checksum cache."""
        _GLOBAL_SHA256_CACHE.clear()

    def extract_chapter_num(self, path: Path, default_idx: int) -> int:
        """Extract numeric chapter index from filename using canonical extractor."""
        return extract_chapter_num(path, default_idx)

    def scan_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        all_metadata: Optional[Dict[str, ChapterMetadata]] = None
    ) -> List[ChapterTask]:
        """High-speed scan of an input directory, matching against metadata and flagging status.
        
        Optimizations applied:
        1. Fast OS directory stream reading via os.scandir (eliminates redundant stat syscalls).
        2. Pre-indexed output directory file existence set (O(1) lookups instead of N disk checks).
        3. Single read of ProjectMetadataDocument reused across all calls.
        4. Lazy SHA-256 computation: untranslated chapters avoid upfront hashing overhead.
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if not input_path.exists():
            return []

        # 1. Fast directory listing using os.scandir
        raw_entries: List[Tuple[str, Path, os.stat_result]] = []
        try:
            with os.scandir(input_path) as it:
                for entry in it:
                    if entry.is_file():
                        name_lower = entry.name.lower()
                        if name_lower.endswith(".txt") or name_lower.endswith(".md"):
                            try:
                                raw_entries.append((entry.name, Path(entry.path), entry.stat()))
                            except Exception:
                                pass
        except Exception as e:
            logger.warning("Failed scanning input directory %s: %s", input_path, e)
            return []

        if not raw_entries:
            return []

        sorted_entries = natsorted(raw_entries, key=lambda x: x[0])

        # 2. Pre-index existing output files to eliminate N disk stat syscalls in the loop
        existing_outputs: Set[str] = set()
        if output_path.exists():
            try:
                with os.scandir(output_path) as it:
                    for entry in it:
                        if entry.is_file():
                            existing_outputs.add(entry.name)
            except Exception:
                pass

        # 3. Single I/O read: load all project chapter metadata if not already passed
        if all_metadata is None:
            all_metadata = self.repo.load_all_metadata()

        tasks: List[ChapterTask] = []
        seen_chapter_nums: dict[int, Path] = {}
        out_parent_name = output_path.name

        for idx, (filename, src_file, st) in enumerate(sorted_entries, start=1):
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

            out_filename = f"{src_file.stem}.md"
            out_file = output_path / out_filename
            out_exists = out_filename in existing_outputs

            # Fast in-memory metadata lookup
            stem = src_file.stem
            composite_key = f"{out_parent_name}/{stem}"
            meta = all_metadata.get(composite_key) or all_metadata.get(stem) or all_metadata.get(out_filename)

            # Fallback only if metadata is missing and a legacy file exists on disk
            if meta is None and out_exists:
                legacy_meta_name = f"{stem}.meta.json"
                if legacy_meta_name in existing_outputs:
                    meta = self.repo.load_metadata(out_file)

            is_done = False
            is_failed = False
            is_paused = False
            last_err = None
            needs_resume = False
            resume_stage = PipelineStage.NONE
            src_sha256 = ""

            if meta:
                # Check SHA256 only when metadata exists to verify completion or resumption
                src_sha256 = self.get_file_sha256(src_file, st_size=st.st_size, st_mtime=st.st_mtime)
                if meta.checkpoint.status == StageStatus.COMPLETED and meta.source_sha256 == src_sha256 and out_exists:
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

    def scan_project(self, folder: Optional[str] = None) -> List[ChapterTask]:
        """Scan and resolve chapter tasks for this project, supporting multi-folder and volume subdirectories.
        
        If folder is specified and not 'all', scans only that subfolder / volume.
        If folder is None or 'all', scans primary raw chapters and all discovered volume folders.
        """
        cfg = self.repo.load_config()

        if folder and folder != "all":
            folder_cand = self.repo.root_dir / folder
            if folder_cand.exists() and folder_cand.is_dir():
                raw_path = folder_cand
                out_cand_th = self.repo.root_dir / f"{folder}_th"
                out_cand_tr = self.repo.root_dir / f"{folder}_trans"
                if out_cand_th.exists():
                    output_path = out_cand_th
                elif out_cand_tr.exists():
                    output_path = out_cand_tr
                else:
                    output_path = cfg.get_output_path(self.repo.root_dir)
            else:
                raw_path = cfg.get_raw_path(self.repo.root_dir)
                output_path = cfg.get_output_path(self.repo.root_dir)
            return self.scan_directory(raw_path, output_path)

        # Multi-volume scan: single I/O read of metadata document shared across all subfolders!
        all_metadata = self.repo.load_all_metadata()

        raw_path = cfg.get_raw_path(self.repo.root_dir)
        output_path = cfg.get_output_path(self.repo.root_dir)
        primary_tasks = self.scan_directory(raw_path, output_path, all_metadata=all_metadata)

        all_tasks = list(primary_tasks)
        seen_files = {str(t.source_file.resolve()) for t in primary_tasks}

        ignored_dir_names = {
            "node_modules", "web", "src-tauri", "dist", ".git", ".novel", ".venv",
            "__pycache__", "translated_chapters", "raw_chapters", raw_path.name, output_path.name
        }

        try:
            with os.scandir(self.repo.root_dir) as it:
                for entry in it:
                    if (
                        entry.is_dir()
                        and not entry.name.startswith(".")
                        and not entry.name.endswith("_th")
                        and not entry.name.endswith("_trans")
                        and entry.name not in ignored_dir_names
                    ):
                        child = Path(entry.path)
                        # Fast check if directory has any chapter files
                        has_chapters = False
                        try:
                            with os.scandir(child) as sub_it:
                                for sub_entry in sub_it:
                                    if sub_entry.is_file() and sub_entry.name.lower().endswith((".txt", ".md")):
                                        has_chapters = True
                                        break
                        except Exception:
                            pass

                        if has_chapters:
                            out_th = self.repo.root_dir / f"{entry.name}_th"
                            out_tr = self.repo.root_dir / f"{entry.name}_trans"
                            sub_out = out_th if out_th.exists() else (out_tr if out_tr.exists() else output_path)
                            sub_tasks = self.scan_directory(child, sub_out, all_metadata=all_metadata)
                            for st in sub_tasks:
                                f_key = str(st.source_file.resolve())
                                if f_key not in seen_files:
                                    all_tasks.append(st)
                                    seen_files.add(f_key)
        except Exception as e:
            logger.warning("Error auto-discovering volume subfolders during scan: %s", e)

        return all_tasks

    @classmethod
    def scan_all_projects(
        cls,
        projects_root: Optional[Union[str, Path]] = None,
        folder: Optional[str] = None
    ) -> Dict[str, List[ChapterTask]]:
        """Scan chapters across all novel projects located in NOVEL_PROJECTS_DIR or specified root.

        Returns a dictionary mapping project directory name to its chapter tasks.
        """
        root = Path(projects_root).resolve() if projects_root else get_projects_root_dir()
        results: Dict[str, List[ChapterTask]] = {}
        if not root.exists() or not root.is_dir():
            return results

        try:
            with os.scandir(root) as it:
                for entry in it:
                    if entry.is_dir() and not entry.name.startswith("."):
                        child_path = Path(entry.path)
                        if (child_path / ".novel").exists() or (child_path / "config.yaml").exists():
                            scanner = cls(child_path)
                            results[entry.name] = scanner.scan_project(folder=folder)
        except Exception as e:
            logger.warning("Error scanning projects directory %s: %s", root, e)

        return results
