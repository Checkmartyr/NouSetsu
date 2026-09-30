"""Project-wide token summaries from recorded trace history."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from nousetsu.analysis.token_metrics import ProjectTokenSummary, compute_token_summary, extract_folder_name
from nousetsu.models.metadata import (
    ChapterMetadata,
    PipelineStage,
    StepTokenUsage,
    TokenUsage,
    TranslationStats,
)

ChapterKey = Tuple[str, int]


class TokenAnalyticsCoverage(BaseModel):
    known_chapters: int = 0
    history_chapters: int = 0
    trace_snapshot_chapters: int = 0
    snapshot_only_chapters: int = 0
    history_complete: bool = True


class ProjectTokenAnalytics(BaseModel):
    selected_folder: str = "ALL"
    available_folders: List[str] = Field(default_factory=list)
    recorded: ProjectTokenSummary = Field(default_factory=ProjectTokenSummary)
    history: ProjectTokenSummary = Field(default_factory=ProjectTokenSummary)
    metadata_snapshot: ProjectTokenSummary = Field(default_factory=ProjectTokenSummary)
    coverage: TokenAnalyticsCoverage = Field(default_factory=TokenAnalyticsCoverage)


def compute_project_token_analytics(
    traces_dir: Path,
    chapters: Dict[str, ChapterMetadata],
    folder_filter: Optional[str] = None,
    default_folder: Optional[str] = None,
) -> ProjectTokenAnalytics:
    """Aggregate trace usage and recorded metadata snapshots without double-counting."""
    traces_dir = Path(traces_dir)
    default_folder_name = Path(default_folder).name.casefold() if default_folder else ""

    def normalize_folder(folder: str) -> str:
        return "default" if default_folder_name and folder.casefold() == default_folder_name else folder

    is_all_folders = not folder_filter or folder_filter.casefold() in {
        "all", "all folders", "all volumes"
    }
    selected_folder = None if is_all_folders else folder_filter.strip()
    trace_chapters: Dict[ChapterKey, List[StepTokenUsage]] = {}
    chapter_ids: Dict[ChapterKey, str] = {}
    jsonl_chapters: set[ChapterKey] = set()
    json_chapters: set[ChapterKey] = set()
    available_folders = {normalize_folder(extract_folder_name(ch)) for ch in chapters.values()}
    seen_records: set[Tuple[ChapterKey, str]] = set()
    had_parse_errors = False

    if traces_dir.is_dir():
        files = sorted(
            path for path in traces_dir.rglob("chapter_*")
            if path.is_file() and path.suffix.lower() in {".json", ".jsonl"}
        )
        for path in files:
            relative_parent = path.parent.relative_to(traces_dir)
            path_folder = "/".join(relative_parent.parts) if relative_parent.parts else "default"
            available_folders.add(path_folder)
            file_match = re.search(r"chapter_(\d+)", path.stem)
            file_chapter_num = int(file_match.group(1)) if file_match else 1
            document_folder = None
            document_chapter_id = None

            def add_record(record: Any) -> None:
                nonlocal had_parse_errors
                if not isinstance(record, dict):
                    had_parse_errors = True
                    return

                folder = normalize_folder(str(record.get("folder") or document_folder or path_folder))
                chapter_num = _safe_int(record.get("chapter_num"), file_chapter_num)
                key = (folder, chapter_num)
                chapter_ids.setdefault(
                    key,
                    str(record.get("chapter_id") or document_chapter_id or f"chapter_{chapter_num:04d}"),
                )
                if path.suffix.lower() == ".jsonl":
                    jsonl_chapters.add(key)
                else:
                    json_chapters.add(key)
                available_folders.add(folder)

                dedupe_id = record.get("trace_id")
                if not dedupe_id:
                    stable_fields = {
                        field: record.get(field)
                        for field in (
                            "timestamp", "chapter_id", "chapter_num", "folder", "stage",
                            "model", "iteration", "chunk_index", "token_usage",
                            "duration_seconds", "status",
                        )
                    }
                    encoded = json.dumps(stable_fields, sort_keys=True, ensure_ascii=False, default=str)
                    dedupe_id = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                dedupe_key = (key, str(dedupe_id))
                if dedupe_key in seen_records:
                    return
                seen_records.add(dedupe_key)

                usage_data = record.get("token_usage")
                usage_data = usage_data if isinstance(usage_data, dict) else {}
                input_tokens = _safe_int(usage_data.get("input_tokens"), 0)
                output_tokens = _safe_int(usage_data.get("output_tokens"), 0)
                thought_tokens = _safe_int(usage_data.get("thought_tokens"), 0)
                cached_tokens = _safe_int(usage_data.get("cached_tokens"), 0)
                total_tokens = _safe_int(usage_data.get("total_tokens"), 0)
                if total_tokens == 0 and (input_tokens or output_tokens or thought_tokens):
                    total_tokens = input_tokens + output_tokens + thought_tokens

                raw_stage = str(record.get("stage") or "none").lower()
                try:
                    stage = PipelineStage(raw_stage)
                except ValueError:
                    stage = PipelineStage.NONE
                duration = _safe_float(record.get("duration_seconds"), 0.0)
                usage = TokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    thought_tokens=thought_tokens,
                    cached_tokens=cached_tokens,
                    total_tokens=total_tokens,
                )
                trace_chapters.setdefault(key, []).append(
                    StepTokenUsage(
                        stage=stage,
                        step_name=raw_stage,
                        iteration=max(1, _safe_int(record.get("iteration"), 1)),
                        model=str(record.get("model") or "unknown"),
                        chunk_count=max(1, _safe_int(record.get("total_chunks"), 1)),
                        duration_seconds=duration,
                        usage=usage,
                        timestamp=str(record.get("timestamp") or ""),
                    )
                )

            if path.suffix.lower() == ".jsonl":
                try:
                    with path.open("r", encoding="utf-8") as trace_file:
                        for line in trace_file:
                            if not line.strip():
                                continue
                            try:
                                add_record(json.loads(line))
                            except (json.JSONDecodeError, TypeError):
                                had_parse_errors = True
                except OSError:
                    had_parse_errors = True
            else:
                try:
                    with path.open("r", encoding="utf-8") as trace_file:
                        document = json.load(trace_file)
                    if isinstance(document, dict):
                        document_folder = document.get("folder")
                        document_chapter_id = document.get("chapter_id")
                        records = document.get("traces", [])
                        if isinstance(records, list):
                            for record in records:
                                add_record(record)
                        else:
                            had_parse_errors = True
                    else:
                        had_parse_errors = True
                except (OSError, json.JSONDecodeError, TypeError):
                    had_parse_errors = True

    metadata_keys = {
        (normalize_folder(extract_folder_name(ch)), ch.chapter_num)
        for ch in chapters.values()
    }
    trace_keys = set(trace_chapters)
    snapshot_chapters = {
        name: chapter
        for name, chapter in chapters.items()
        if (normalize_folder(extract_folder_name(chapter)), chapter.chapter_num) not in trace_keys
    }

    history_metadata = {}
    for (folder, chapter_num), steps in trace_chapters.items():
        history_metadata[f"{folder}/{chapter_num:04d}"] = ChapterMetadata(
            chapter_id=chapter_ids[(folder, chapter_num)],
            chapter_num=chapter_num,
            source_file=(f"{folder}/{chapter_num:04d}.txt" if folder != "default" else f"{chapter_num:04d}.txt"),
            source_sha256="",
            output_file=(f"{folder}/{chapter_num:04d}.md" if folder != "default" else f"{chapter_num:04d}.md"),
            stats=TranslationStats(
                prompt_tokens=sum(step.usage.input_tokens for step in steps),
                completion_tokens=sum(step.usage.output_tokens for step in steps),
                thought_tokens=sum(step.usage.thought_tokens for step in steps),
                cached_tokens=sum(step.usage.cached_tokens for step in steps),
                total_tokens=sum(step.usage.total_tokens for step in steps),
                duration_seconds=sum(step.duration_seconds for step in steps),
                step_usage=steps,
            ),
            prompt_trace_count=len(steps),
        )
    history_summary = compute_token_summary(history_metadata, selected_folder)
    recorded_snapshots = {}
    for name, chapter in snapshot_chapters.items():
        if not _has_recorded_token_usage(chapter):
            continue
        source_folder = extract_folder_name(chapter)
        if normalize_folder(source_folder) == "default" and source_folder.casefold() != "default":
            source_file = chapter.source_file.replace("\\", "/").rsplit("/", 1)[-1]
            output_file = chapter.output_file.replace("\\", "/").rsplit("/", 1)[-1]
            chapter = chapter.model_copy(update={"source_file": source_file, "output_file": output_file})
        recorded_snapshots[name] = chapter
    metadata_summary = compute_token_summary(recorded_snapshots, selected_folder)
    recorded_summary = compute_token_summary(
        {**history_metadata, **recorded_snapshots},
        selected_folder,
    )
    folders = sorted(available_folders)
    for summary in (history_summary, metadata_summary, recorded_summary):
        summary.available_folders = folders
        if selected_folder:
            summary.folder_metrics = [
                metric for metric in summary.folder_metrics
                if metric.folder.casefold() == selected_folder.casefold()
            ]

    in_scope = lambda key: is_all_folders or key[0].casefold() == str(selected_folder).casefold()
    known_keys = {key for key in metadata_keys | trace_keys if in_scope(key)}
    history_keys = {key for key in trace_keys if in_scope(key)}
    trace_snapshot_keys = {key for key in json_chapters - jsonl_chapters if in_scope(key)}
    snapshot_only_keys = {key for key in metadata_keys - trace_keys if in_scope(key)}
    coverage = TokenAnalyticsCoverage(
        known_chapters=len(known_keys),
        history_chapters=len(history_keys),
        trace_snapshot_chapters=len(trace_snapshot_keys),
        snapshot_only_chapters=len(snapshot_only_keys),
        history_complete=not had_parse_errors and known_keys.issubset(history_keys),
    )
    return ProjectTokenAnalytics(
        selected_folder="ALL" if is_all_folders else str(selected_folder),
        available_folders=folders,
        recorded=recorded_summary,
        history=history_summary,
        metadata_snapshot=metadata_summary,
        coverage=coverage,
    )


def _has_recorded_token_usage(chapter: ChapterMetadata) -> bool:
    return any(
        step.usage.input_tokens
        or step.usage.output_tokens
        or step.usage.thought_tokens
        or step.usage.cached_tokens
        or step.usage.total_tokens
        for step in chapter.stats.step_usage
    )


def _safe_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default
