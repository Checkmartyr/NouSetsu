"""Prompt and output tracking engine for novel translation agents."""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from nousetsu.models.metadata import PipelineStage, TokenUsage
from nousetsu.models.trace import AgentPromptTrace, ChapterTraceDocument

logger = logging.getLogger(__name__)


class PromptTracker:
    """Tracks every prompt sent to an LLM and raw output generated across pipeline states.

    Persists traces in real-time to streaming JSONL format (.novel/traces/chapter_XXXX.jsonl)
    for crash-resilience, and writes a consolidated ChapterTraceDocument (.json) upon completion.
    """

    def __init__(
        self,
        traces_dir: Path | str,
        chapter_id: str,
        chapter_num: int,
        folder: Optional[str] = None,
        enabled: bool = True
    ):
        self.traces_dir = Path(traces_dir).resolve()
        self.chapter_id = chapter_id
        self.chapter_num = chapter_num
        self.folder = folder
        self.enabled = enabled
        self.traces: List[AgentPromptTrace] = []

        # Target directory structure: .novel/traces/<folder>/ or .novel/traces/
        target_dir = self.traces_dir / folder if folder else self.traces_dir
        base_name = f"chapter_{chapter_num:04d}" if chapter_num > 0 else chapter_id
        self.jsonl_path = target_dir / f"{base_name}.jsonl"
        self.json_path = target_dir / f"{base_name}.json"

    def record(
        self,
        stage: PipelineStage,
        agent: str,
        system_prompt: str,
        user_prompt: str,
        raw_output: str,
        model: str,
        token_usage: Optional[TokenUsage] = None,
        duration_seconds: float = 0.0,
        iteration: int = 1,
        chunk_index: int = 1,
        total_chunks: int = 1,
        depth: int = 0,
        parsed_output: Optional[Any] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentPromptTrace:
        """Record a single LLM prompt & output interaction and append immediately to disk."""
        usage = token_usage or TokenUsage()
        trace = AgentPromptTrace(
            chapter_id=self.chapter_id,
            chapter_num=self.chapter_num,
            folder=self.folder,
            stage=stage,
            agent=agent,
            model=model,
            iteration=iteration,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            depth=depth,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_output=raw_output,
            parsed_output=parsed_output,
            token_usage=usage,
            duration_seconds=round(duration_seconds, 2),
            status=status,
            error_message=error_message,
            metadata=metadata or {}
        )
        self.traces.append(trace)

        if self.enabled:
            self._append_to_jsonl(trace)

        return trace

    def record_error(
        self,
        stage: PipelineStage,
        agent: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        err: Exception | str,
        duration_seconds: float = 0.0,
        iteration: int = 1,
        chunk_index: int = 1,
        total_chunks: int = 1,
        depth: int = 0,
        status: str = "error",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentPromptTrace:
        """Record a failed LLM prompt invocation or safety block."""
        err_msg = str(err)
        return self.record(
            stage=stage,
            agent=agent,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_output="",
            model=model,
            duration_seconds=duration_seconds,
            iteration=iteration,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            depth=depth,
            status=status,
            error_message=err_msg,
            metadata=metadata
        )

    def _append_to_jsonl(self, trace: AgentPromptTrace) -> None:
        """Atomically append a single trace record as a JSON line to the jsonl file."""
        try:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(trace.model_dump(), ensure_ascii=False)
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            logger.warning(f"Failed to append trace to {self.jsonl_path}: {e}")

    def finalize(self) -> ChapterTraceDocument:
        """Aggregate all recorded traces and persist consolidated ChapterTraceDocument."""
        total_tok = TokenUsage()
        total_dur = 0.0
        stage_counts: Dict[str, int] = {}

        for t in self.traces:
            total_tok = total_tok.add(t.token_usage)
            total_dur += t.duration_seconds
            st_key = t.stage.value if hasattr(t.stage, "value") else str(t.stage)
            stage_counts[st_key] = stage_counts.get(st_key, 0) + 1

        doc = ChapterTraceDocument(
            chapter_id=self.chapter_id,
            chapter_num=self.chapter_num,
            folder=self.folder,
            total_interactions=len(self.traces),
            total_duration_seconds=round(total_dur, 2),
            total_token_usage=total_tok,
            stage_breakdown=stage_counts,
            traces=self.traces
        )

        if self.enabled and self.traces:
            try:
                self.json_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.json_path, "w", encoding="utf-8") as f:
                    json.dump(doc.model_dump(), f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Failed to write consolidated trace document to {self.json_path}: {e}")

        return doc

    @staticmethod
    def load_from_json(path: Path | str) -> Optional[ChapterTraceDocument]:
        """Load a consolidated ChapterTraceDocument from a JSON file."""
        p = Path(path)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ChapterTraceDocument.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load trace document from {p}: {e}")
            return None

    @staticmethod
    def load_from_jsonl(path: Path | str) -> List[AgentPromptTrace]:
        """Load all traces from a streaming JSONL file."""
        p = Path(path)
        if not p.exists():
            return []
        traces = []
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        traces.append(AgentPromptTrace.model_validate(json.loads(line_str)))
        except Exception as e:
            logger.warning(f"Failed to load traces from {p}: {e}")
        return traces
