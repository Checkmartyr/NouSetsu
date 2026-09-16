"""Repair and realignment engine for chapter sequence collisions and metadata sync."""
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from nousetsu.batch.scanner import ChapterScanner, ChapterTask
from nousetsu.models.bible import ChapterSummary
from nousetsu.storage.repository import NovelRepository

logger = logging.getLogger(__name__)


@dataclass
class RealignmentReport:
    folder: str
    total_chapters: int = 0
    realigned_chapters: List[Tuple[str, int, int]] = field(default_factory=list)
    summaries_moved: List[Tuple[str, str]] = field(default_factory=list)
    summaries_reconstructed: List[int] = field(default_factory=list)
    traces_migrated: List[Tuple[str, str]] = field(default_factory=list)
    metadata_entries_updated: int = 0
    rag_reindexed: bool = False
    backup_path: Optional[str] = None
    dry_run: bool = False


def _extract_text_synopsis(file_path: Path, max_chars: int = 600) -> Tuple[str, str]:
    """Extract a clean title and opening synopsis snippet from a markdown/text chapter file."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return file_path.stem, f"Content of {file_path.stem}"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return file_path.stem, f"Empty chapter {file_path.stem}"

    # Extract title from markdown heading or first line
    first_line = lines[0]
    title = re.sub(r"^#+\s*", "", first_line).strip() or file_path.stem

    # Extract synopsis from early paragraphs
    body_paras = [l for l in lines[1:10] if not l.startswith("#")]
    synopsis = " ".join(body_paras)[:max_chars].strip()
    if not synopsis:
        synopsis = f"Chapter events for {title}."
    elif len(synopsis) >= max_chars:
        synopsis += "..."

    return title, synopsis


def realign_project_folder(
    repository: NovelRepository,
    folder: str,
    dry_run: bool = False,
    re_chronicle: bool = False,
) -> RealignmentReport:
    """
    Realign chapter numbers, resolve collisions, update metadata.json,
    relocate summaries and traces, and re-index RAG for a novel volume folder.
    """
    report = RealignmentReport(folder=folder, dry_run=dry_run)
    project_dir = repository.root_dir

    # 1. Resolve input and output directories
    input_dir = project_dir / folder
    if not input_dir.exists():
        raise FileNotFoundError(f"Folder '{folder}' does not exist in project '{project_dir}'.")

    cfg = repository.load_config()
    output_dir = project_dir / f"{folder}_th"
    if not output_dir.exists():
        cand_out = cfg.get_output_path(project_dir)
        if cand_out.exists() and cand_out.name == folder:
            output_dir = cand_out
        else:
            output_dir = project_dir / f"{folder}_translated"

    # 2. Scan tasks with collision-aware scanner
    scanner = ChapterScanner(repository)
    tasks = scanner.scan_directory(input_dir, output_dir)
    report.total_chapters = len(tasks)

    # 3. Check for metadata mismatches
    all_metadata = repository.load_all_metadata()
    tasks_to_realign: List[Tuple[ChapterTask, int, int]] = []

    for task in tasks:
        composite_key = f"{output_dir.name}/{task.source_file.stem}"
        for k in (composite_key, task.source_file.stem):
            meta = all_metadata.get(k)
            if meta and meta.chapter_num != task.chapter_num:
                if not any(t[0].chapter_num == task.chapter_num for t in tasks_to_realign):
                    tasks_to_realign.append((task, meta.chapter_num, task.chapter_num))
                    report.realigned_chapters.append((task.source_file.name, meta.chapter_num, task.chapter_num))

    # Also detect if summaries currently contain misplaced extra chapters
    summaries_dir = repository.summaries_dir / folder
    old_to_new_summaries: List[Tuple[int, int]] = []
    for _, old_num, new_num in report.realigned_chapters:
        old_file = summaries_dir / f"chapter_{old_num:04d}.json"
        if old_file.exists():
            old_to_new_summaries.append((old_num, new_num))

    if dry_run:
        return report

    # 4. Create Safety Backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = repository.novel_dir / "backups" / f"realign_{folder}_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    if repository.project_metadata_file_path().exists():
        shutil.copy2(repository.project_metadata_file_path(), backup_dir / "metadata.json")
    if summaries_dir.exists():
        shutil.copytree(summaries_dir, backup_dir / "summaries", dirs_exist_ok=True)
    report.backup_path = str(backup_dir)

    # 5. Relocate and update moved summaries (e.g. Extra Chapters 1..10 -> 35..44)
    if summaries_dir.exists() and old_to_new_summaries:
        summaries_dir.mkdir(parents=True, exist_ok=True)
        # Process in descending order of old_num to prevent accidental self-overwrite
        for old_num, new_num in sorted(old_to_new_summaries, key=lambda x: x[0], reverse=True):
            old_s_path = summaries_dir / f"chapter_{old_num:04d}.json"
            new_s_path = summaries_dir / f"chapter_{new_num:04d}.json"
            if old_s_path.exists():
                try:
                    with open(old_s_path, "r", encoding="utf-8") as sf:
                        s_data = json.load(sf)
                    s_data["chapter_num"] = new_num
                    s_data["folder"] = folder
                    with open(new_s_path, "w", encoding="utf-8") as nf:
                        json.dump(s_data, nf, indent=2, ensure_ascii=False)
                    report.summaries_moved.append((old_s_path.name, new_s_path.name))
                except Exception as e:
                    logger.error(f"Failed to relocate summary {old_s_path.name} to {new_s_path.name}: {e}")

    # 6. Reconstruct missing/overwritten summaries for Chapters 1..10
    chronicler_agent = None
    if re_chronicle:
        try:
            from nousetsu.agents.chronicler import ChroniclerAgent
            chronicler_agent = ChroniclerAgent()
        except Exception as e:
            logger.warning(f"Could not instantiate ChroniclerAgent for re-chronicling: {e}")

    for task in tasks:
        # If this chapter was one of the overwritten old slots (or summary doesn't exist)
        s_path = summaries_dir / f"chapter_{task.chapter_num:04d}.json"
        is_vacated_slot = any(old_num == task.chapter_num for old_num, _ in old_to_new_summaries)

        if is_vacated_slot or not s_path.exists():
            clean_title, synopsis = _extract_text_synopsis(
                task.output_file if task.output_file.exists() else task.source_file
            )

            if chronicler_agent and task.output_file.exists():
                try:
                    translated_text = task.output_file.read_text(encoding="utf-8")
                    ch_summary = chronicler_agent.chronicle(
                        chapter_num=task.chapter_num,
                        chapter_title=clean_title,
                        translated_text=translated_text,
                        genre=cfg.genre,
                        source_lang=cfg.source_language,
                        folder=folder,
                    )
                    with open(s_path, "w", encoding="utf-8") as f:
                        json.dump(ch_summary.model_dump(), f, indent=2, ensure_ascii=False)
                    report.summaries_reconstructed.append(task.chapter_num)
                    continue
                except Exception as e:
                    logger.warning(f"ChroniclerAgent failed for chapter {task.chapter_num}, using fallback: {e}")

            # Fallback structural summary
            fallback_summary = ChapterSummary(
                chapter_num=task.chapter_num,
                title=clean_title,
                synopsis=synopsis,
                key_events=[f"Events of {clean_title}"],
                folder=folder,
            )
            with open(s_path, "w", encoding="utf-8") as f:
                json.dump(fallback_summary.model_dump(), f, indent=2, ensure_ascii=False)
            report.summaries_reconstructed.append(task.chapter_num)

    # 7. Migrate Traces
    traces_dir = repository.traces_dir / folder
    if traces_dir.exists() and old_to_new_summaries:
        for old_num, new_num in sorted(old_to_new_summaries, key=lambda x: x[0], reverse=True):
            old_trace_json = traces_dir / f"chapter_{old_num:04d}.json"
            new_trace_json = traces_dir / f"chapter_{new_num:04d}.json"
            if old_trace_json.exists():
                try:
                    with open(old_trace_json, "r", encoding="utf-8") as tf:
                        t_data = json.load(tf)
                    t_data["chapter_id"] = f"chapter_{new_num:04d}"
                    t_data["chapter_num"] = new_num
                    with open(new_trace_json, "w", encoding="utf-8") as ntf:
                        json.dump(t_data, ntf, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"Could not migrate trace {old_trace_json.name}: {e}")

            old_trace_jsonl = traces_dir / f"chapter_{old_num:04d}.jsonl"
            new_trace_jsonl = traces_dir / f"chapter_{new_num:04d}.jsonl"
            if old_trace_jsonl.exists():
                try:
                    shutil.copy2(old_trace_jsonl, new_trace_jsonl)
                except Exception:
                    pass
            report.traces_migrated.append((f"chapter_{old_num:04d}", f"chapter_{new_num:04d}"))

    # 8. Update metadata.json entries
    for task, _, new_num in tasks_to_realign:
        composite_key = f"{output_dir.name}/{task.source_file.stem}"
        for k in (composite_key, task.source_file.stem):
            meta = all_metadata.get(k)
            if meta and (not meta.source_file or Path(meta.source_file).name == task.source_file.name):
                meta.chapter_num = new_num
                meta.chapter_id = f"chapter_{new_num:04d}"
        report.metadata_entries_updated += 1

    repository.save_all_metadata(all_metadata)

    # 9. Cleanly re-index RAG for this folder
    try:
        from nousetsu.rag.migration import migrate_project_to_rag
        migrate_project_to_rag(
            repository=repository,
            folder_filter=folder,
            embed=False,
            include_summaries=True,
            include_chunks=True,
            include_bible=False,
            include_arcs=False,
        )
        report.rag_reindexed = True
    except Exception as e:
        logger.warning(f"RAG re-indexing skipped or failed during realignment: {e}")

    return report
