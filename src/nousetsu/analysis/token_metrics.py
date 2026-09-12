"""Token consumption and execution performance analytics."""
from collections import defaultdict
from typing import Dict, List
from pydantic import BaseModel, Field
from nousetsu.models.metadata import ChapterMetadata, PipelineStage
from nousetsu.utils.formatting import format_duration


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


class ChapterMetric(BaseModel):
    """Per-chapter summary metric for ranking and drill-down inspection."""
    chapter_id: str
    chapter_num: int
    source_file: str
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
    stage_metrics: List[StageMetric] = Field(default_factory=list)
    model_metrics: List[ModelMetric] = Field(default_factory=list)
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


def compute_token_summary(chapters: Dict[str, ChapterMetadata]) -> ProjectTokenSummary:
    """Compute project-wide token usage and stage/model performance metrics."""
    summary = ProjectTokenSummary(total_chapters=len(chapters))
    if not chapters:
        return summary

    stage_map = defaultdict(lambda: {
        "calls": 0, "total": 0, "input": 0, "output": 0, "thought": 0, "cached": 0, "duration": 0.0
    })
    model_map = defaultdict(lambda: {
        "calls": 0, "total": 0, "input": 0, "output": 0, "thought": 0, "cached": 0, "duration": 0.0
    })
    chapter_list: List[ChapterMetric] = []

    for name, ch in chapters.items():
        stats = ch.stats
        checkpoint = ch.checkpoint
        status_str = checkpoint.status.value if checkpoint else "pending"

        # Check total tokens with fallback for legacy data where total_tokens was 0
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

    # Convert stage map to sorted StageMetric list (sorted by total_tokens desc)
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

    # Convert model map to sorted ModelMetric list (sorted by total_tokens desc)
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

    # Sort chapter rankings by total_tokens desc
    chapter_list.sort(key=lambda c: (c.total_tokens, c.duration_seconds), reverse=True)
    summary.chapter_rankings = chapter_list

    return summary
