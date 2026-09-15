"""Data models for tracking agent LLM input prompts and generated outputs."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field
from nousetsu.models.metadata import PipelineStage, TokenUsage


class AgentPromptTrace(BaseModel):
    """Execution trace of a single agent LLM prompt and response interaction."""
    trace_id: str = Field(default_factory=lambda: f"tr_{uuid.uuid4().hex[:12]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    chapter_id: str = Field(default="unknown")
    chapter_num: int = Field(default=1)
    folder: Optional[str] = Field(default=None)
    stage: PipelineStage = Field(default=PipelineStage.NONE)
    agent: str = Field(default="", description="Agent role name: extractor, drafter, critic, polisher, chronicler")
    model: str = Field(default="")
    iteration: int = Field(default=1, description="Review loop pass number (1-indexed)")
    chunk_index: int = Field(default=1, description="Chunk number being processed")
    total_chunks: int = Field(default=1, description="Total chunks in this stage")
    depth: int = Field(default=0, description="Recursive subdivision depth")
    system_prompt: str = Field(default="", description="Complete system instructions sent to LLM")
    user_prompt: str = Field(default="", description="Complete user prompt content sent to LLM")
    raw_output: str = Field(default="", description="Raw response text returned by LLM")
    parsed_output: Optional[Any] = Field(default=None, description="Structured parsed result e.g. quality audit, summary")
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    duration_seconds: float = Field(default=0.0)
    status: str = Field(default="success", description="success, error, safety_blocked, retry")
    error_message: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChapterTraceDocument(BaseModel):
    """Consolidated document of all prompt/output traces for a chapter."""
    chapter_id: str
    chapter_num: int
    folder: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_interactions: int = 0
    total_duration_seconds: float = 0.0
    total_token_usage: TokenUsage = Field(default_factory=TokenUsage)
    stage_breakdown: Dict[str, int] = Field(default_factory=dict)
    traces: List[AgentPromptTrace] = Field(default_factory=list)
