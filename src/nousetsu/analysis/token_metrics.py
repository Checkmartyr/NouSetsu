"""Token consumption and execution performance analytics."""
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from nousetsu.models.metadata import ChapterMetadata, PipelineStage
from nousetsu.utils.formatting import format_duration


def extract_folder_name(ch: ChapterMetadata) -> str:
    """Extract volume or folder name from ChapterMetadata source_file or output_file."""
    src = ch.source_file or ""
    out = ch.output_file or ""

    if src:
        p = Path(str(src).replace("\\", "/"))
        if p.parent and p.parent.name and p.parent.name not in [".", ""]:
            return p.parent.name

    if out:
        p = Path(str(out).replace("\\", "/"))
        if p.parent and p.parent.name and p.parent.name not in [".", ""]:
            clean_name = re.sub(r"_(?:th|trans|out)$", "", p.parent.name, flags=re.IGNORECASE)
            return clean_name

    return "default"


class StageMetric(BaseModel):
    """Aggregate token usage and latency metrics for a specific pipeline stage."""
    stage: str
    calls: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    cached_tokens: int = 0
    duration_seconds: float = 0.0

    @property
    def avg_duration(self) -> float:
        return self.duration_seconds / self.calls if self.calls > 0 else 0.0

    @property
    def formatted_duration(self) -> str:
        return format_duration(self.duration_seconds)


class ModelMetric(BaseModel):
    """Aggregate token usage and latency metrics for a specific LLM model."""
    model: str
    calls: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    cached_tokens: int = 0
    duration_seconds: float = 0.0

    @property
    def avg_duration(self) -> float:
        return self.duration_seconds / self.calls if self.calls > 0 else 0.0

    @property
    def formatted_duration(self) -> str:
        return format_duration(self.duration_seconds)


class FolderMetric(BaseModel):
    """Aggregate token usage and latency metrics for a specific volume or folder."""
    folder: str
    chapter_count: int = 0
    analyzed_chapters: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    cached_tokens: int = 0
    duration_seconds: float = 0.0

    @property
    def avg_tokens(self) -> float:
        count = self.analyzed_chapters or self.chapter_count
        return self.total_tokens / count if count > 0 else 0.0

    @property
    def avg_duration(self) -> float:
        count = self.analyzed_chapters or self.chapter_count
        return self.duration_seconds / count if count > 0 else 0.0

    @property
    def formatted_duration(self) -> str:
        return format_duration(self.duration_seconds)


class ChapterMetric(BaseModel):
    """Per-chapter summary metric for ranking and drill-down inspection."""
    chapter_id: str
    chapter_num: int
    source_file: str
    folder: str = "default"
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thought_tokens: int = 0
    cached_tokens: int = 0
    duration_seconds: float = 0.0
    status: str = "pending"

    @property
    def formatted_duration(self) -> str:
        return format_duration(self.duration_seconds)


class ProjectTokenSummary(BaseModel):
    """Comprehensive token analytics summary across all chapters in a project."""
    total_chapters: int = 0
    analyzed_chapters: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thought_tokens: int = 0
    cached_tokens: int = 0
    total_duration_seconds: float = 0.0
    selected_folder: Optional[str] = None
    available_folders: List[str] = Field(default_factory=list)
    stage_metrics: List[StageMetric] = Field(default_factory=list)
    model_metrics: List[ModelMetric] = Field(default_factory=list)
    folder_metrics: List[FolderMetric] = Field(default_factory=list)
    chapter_rankings: List[ChapterMetric] = Field(default_factory=list)

    @property
    def avg_tokens_per_chapter(self) -> float:
        count = self.analyzed_chapters or self.total_chapters
        return self.total_tokens / count if count > 0 else 0.0

    @property
    def avg_duration_per_chapter(self) -> float:
        count = self.analyzed_chapters or self.total_chapters
        return self.total_duration_seconds / count if count > 0 else 0.0

    @property
    def formatted_duration(self) -> str:
        return format_duration(self.total_duration_seconds)


def compute_token_summary(
    chapters: Dict[str, ChapterMetadata],
    folder_filter: Optional[str] = None
) -> ProjectTokenSummary:
    """Compute project-wide token usage, per-folder metrics, and stage/model performance."""
    if not chapters:
        return ProjectTokenSummary(total_chapters=0)

    # 1. Deduplicate chapters to eliminate double-counting between composite (folder/stem) and bare stem keys
    seen_sources = set()
    unique_entries: List[tuple[str, ChapterMetadata, str]] = []

    for name, ch in chapters.items():
        src_key = ch.source_file or ch.chapter_id or name
        if src_key in seen_sources:
            continue
        seen_sources.add(src_key)
        folder = extract_folder_name(ch)
        unique_entries.append((name, ch, folder))

    # 2. Extract and sort available folders
    available_folders = sorted(list(set(f for _, _, f in unique_entries)))

    # 3. Compute per-folder metrics across all unique chapters (series-wide)
    folder_map = defaultdict(lambda: {
        "chapter_count": 0, "analyzed": 0, "total": 0, "input": 0, "output": 0, "thought": 0, "cached": 0, "duration": 0.0
    })

    for _, ch, folder in unique_entries:
        f_entry = folder_map[folder]
        f_entry["chapter_count"] += 1
        stats = ch.stats
        tot = stats.total_tokens
        if tot == 0 and (stats.prompt_tokens > 0 or stats.completion_tokens > 0):
            tot = stats.prompt_tokens + stats.completion_tokens

        dur = stats.duration_seconds
        prompt = stats.prompt_tokens
        comp = stats.completion_tokens
        thought = stats.thought_tokens
        cached = stats.cached_tokens

        if tot > 0 or dur > 0 or stats.step_usage:
            f_entry["analyzed"] += 1

        f_entry["total"] += tot
        f_entry["input"] += prompt
        f_entry["output"] += comp
        f_entry["thought"] += thought
        f_entry["cached"] += cached
        f_entry["duration"] += dur

    folder_metrics = [
        FolderMetric(
            folder=f,
            chapter_count=data["chapter_count"],
            analyzed_chapters=data["analyzed"],
            total_tokens=data["total"],
            input_tokens=data["input"],
            output_tokens=data["output"],
            thought_tokens=data["thought"],
            cached_tokens=data["cached"],
            duration_seconds=data["duration"],
        )
        for f, data in folder_map.items()
    ]
    folder_metrics.sort(key=lambda fm: fm.total_tokens, reverse=True)

    # 4. Filter active entries if a specific folder is requested
    is_filtered = bool(folder_filter and folder_filter not in ["ALL", "all", "All Folders"])
    if is_filtered:
        active_entries = [e for e in unique_entries if e[2].lower() == str(folder_filter).lower()]
        selected_folder = folder_filter
    else:
        active_entries = unique_entries
        selected_folder = "ALL"

    summary = ProjectTokenSummary(
        total_chapters=len(active_entries),
        selected_folder=selected_folder,
        available_folders=available_folders,
        folder_metrics=folder_metrics,
    )

    stage_map = defaultdict(lambda: {
        "calls": 0, "total": 0, "input": 0, "output": 0, "thought": 0, "cached": 0, "duration": 0.0
    })
    model_map = defaultdict(lambda: {
        "calls": 0, "total": 0, "input": 0, "output": 0, "thought": 0, "cached": 0, "duration": 0.0
    })
    chapter_list: List[ChapterMetric] = []

    for name, ch, folder in active_entries:
        stats = ch.stats
        checkpoint = ch.checkpoint
        status_str = checkpoint.status.value if checkpoint else "pending"

        tot = stats.total_tokens
        if tot == 0 and (stats.prompt_tokens > 0 or stats.completion_tokens > 0):
            tot = stats.prompt_tokens + stats.completion_tokens

        dur = stats.duration_seconds
        prompt = stats.prompt_tokens
        comp = stats.completion_tokens
        thought = stats.thought_tokens
        cached = stats.cached_tokens

        if tot > 0 or dur > 0 or stats.step_usage:
            summary.analyzed_chapters += 1

        summary.total_tokens += tot
        summary.prompt_tokens += prompt
        summary.completion_tokens += comp
        summary.thought_tokens += thought
        summary.cached_tokens += cached
        summary.total_duration_seconds += dur

        src_name = ch.source_file.replace("\\", "/").split("/")[-1] if ch.source_file else name

        chapter_list.append(ChapterMetric(
            chapter_id=ch.chapter_id,
            chapter_num=ch.chapter_num,
            source_file=src_name,
            folder=folder,
            total_tokens=tot,
            prompt_tokens=prompt,
            completion_tokens=comp,
            thought_tokens=thought,
            cached_tokens=cached,
            duration_seconds=dur,
            status=status_str
        ))

        # Aggregate step usages
        for step in stats.step_usage:
            st = step.stage.value if isinstance(step.stage, PipelineStage) else str(step.stage)
            md = step.model or "unknown"
            u = step.usage
            d = step.duration_seconds

            step_tot = u.total_tokens
            if step_tot == 0 and (u.input_tokens > 0 or u.output_tokens > 0):
                step_tot = u.input_tokens + u.output_tokens + u.thought_tokens

            # Stage stats
            stage_entry = stage_map[st]
            stage_entry["calls"] += 1
            stage_entry["total"] += step_tot
            stage_entry["input"] += u.input_tokens
            stage_entry["output"] += u.output_tokens
            stage_entry["thought"] += u.thought_tokens
            stage_entry["cached"] += u.cached_tokens
            stage_entry["duration"] += d

            # Model stats
            model_entry = model_map[md]
            model_entry["calls"] += 1
            model_entry["total"] += step_tot
            model_entry["input"] += u.input_tokens
            model_entry["output"] += u.output_tokens
            model_entry["thought"] += u.thought_tokens
            model_entry["cached"] += u.cached_tokens
            model_entry["duration"] += d

    stage_metrics = [
        StageMetric(
            stage=st,
            calls=v["calls"],
            total_tokens=v["total"],
            input_tokens=v["input"],
            output_tokens=v["output"],
            thought_tokens=v["thought"],
            cached_tokens=v["cached"],
            duration_seconds=v["duration"]
        )
        for st, v in stage_map.items()
    ]
    stage_metrics.sort(key=lambda m: m.total_tokens, reverse=True)
    summary.stage_metrics = stage_metrics

    model_metrics = [
        ModelMetric(
            model=md,
            calls=v["calls"],
            total_tokens=v["total"],
            input_tokens=v["input"],
            output_tokens=v["output"],
            thought_tokens=v["thought"],
            cached_tokens=v["cached"],
            duration_seconds=v["duration"]
        )
        for md, v in model_map.items()
    ]
    model_metrics.sort(key=lambda m: m.total_tokens, reverse=True)
    summary.model_metrics = model_metrics

    chapter_list.sort(key=lambda c: (c.total_tokens, c.duration_seconds), reverse=True)
    summary.chapter_rankings = chapter_list

    return summary
