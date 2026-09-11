"""Unified translation metadata and execution checkpoint models."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from nousetsu.models.bible import CharacterProfile, GlossaryItem


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class PipelineStage(str, Enum):
    NONE = "none"
    EXTRACTION = "extraction"
    DRAFTING = "drafting"
    CRITIQUE = "critique"
    POLISHING = "polishing"
    CHRONICLING = "chronicling"


class StageArtifacts(BaseModel):
    extracted_terms: List[GlossaryItem] = Field(default_factory=list)
    extracted_characters: List[CharacterProfile] = Field(default_factory=list)
    draft_text: Optional[str] = None
    critique_notes: Optional[str] = None
    polished_text: Optional[str] = None


class ErrorLogEntry(BaseModel):
    """Structured record of a single error or failed retry attempt."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stage: PipelineStage = Field(default=PipelineStage.NONE)
    error_type: str = Field(default="", description="Exception class name e.g. InternalServerError")
    message: str = Field(default="", description="Error description or payload string")
    traceback: Optional[str] = Field(default=None, description="Full formatted python stack trace")
    retry_attempt: int = Field(default=0, description="Attempt number when error occurred")
    model: Optional[str] = Field(default=None, description="Model used when failure occurred")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional context or API error dict")


class CheckpointData(BaseModel):
    status: StageStatus = Field(default=StageStatus.PENDING)
    last_completed_stage: PipelineStage = Field(default=PipelineStage.NONE)
    failed_stage: Optional[PipelineStage] = Field(default=None, description="Stage where error occurred")
    retry_count: int = Field(default=0)
    last_error: Optional[str] = None
    last_error_type: Optional[str] = None
    last_error_traceback: Optional[str] = None
    error_logs: List[ErrorLogEntry] = Field(default_factory=list, description="Historical log of errors and retries")
    stage_artifacts: StageArtifacts = Field(default_factory=StageArtifacts)

    def is_resumable(self) -> bool:
        return self.status in [StageStatus.IN_PROGRESS, StageStatus.FAILED, StageStatus.PAUSED] and self.last_completed_stage != PipelineStage.NONE

    def is_completed(self) -> bool:
        return self.status == StageStatus.COMPLETED

    def record_error(
        self,
        stage: PipelineStage,
        err: Exception | str,
        traceback_str: Optional[str] = None,
        retry_attempt: int = 0,
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an error attempt and update checkpoint failure state."""
        self.status = StageStatus.FAILED
        self.failed_stage = stage
        self.retry_count = retry_attempt or (self.retry_count + 1)

        err_msg = str(err)
        err_type = type(err).__name__ if isinstance(err, Exception) else "Error"

        self.last_error = err_msg
        self.last_error_type = err_type
        self.last_error_traceback = traceback_str

        log_entry = ErrorLogEntry(
            stage=stage,
            error_type=err_type,
            message=err_msg,
            traceback=traceback_str,
            retry_attempt=self.retry_count,
            model=model,
            details=details or {}
        )
        self.error_logs.append(log_entry)


class TokenUsage(BaseModel):
    """Detailed token consumption metrics from LLM API (Interactions API / GenAI)."""
    input_tokens: int = Field(default=0, description="Prompt/context input tokens")
    output_tokens: int = Field(default=0, description="Generated completion tokens")
    thought_tokens: int = Field(default=0, description="Reasoning/thought tokens for thinking models")
    cached_tokens: int = Field(default=0, description="Cached prompt tokens")
    total_tokens: int = Field(default=0, description="Grand total tokens")

    def add(self, other: "TokenUsage") -> "TokenUsage":
        """Sum two TokenUsage instances."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            thought_tokens=self.thought_tokens + other.thought_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class StepTokenUsage(BaseModel):
    """Token usage recorded for a specific pipeline stage or review loop step."""
    stage: PipelineStage = Field(default=PipelineStage.NONE)
    step_name: str = Field(default="", description="Human-readable step name e.g. Extraction, Drafting, Critique (Pass 1)")
    iteration: int = Field(default=1, description="Iteration or review pass number")
    model: str = Field(default="", description="Model name used for this step")
    chunk_count: int = Field(default=1, description="Number of text chunks processed for this step")
    duration_seconds: float = Field(default=0.0, description="Duration of this specific pipeline stage execution in seconds")
    usage: TokenUsage = Field(default_factory=TokenUsage)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TranslationStats(BaseModel):
    source_char_count: int = Field(default=0)
    target_word_count: int = Field(default=0)
    prompt_tokens: int = Field(default=0, description="Cumulative input tokens across all steps")
    completion_tokens: int = Field(default=0, description="Cumulative output tokens across all steps")
    thought_tokens: int = Field(default=0, description="Cumulative reasoning thought tokens across all steps")
    cached_tokens: int = Field(default=0, description="Cumulative cached tokens across all steps")
    total_tokens: int = Field(default=0, description="Cumulative total tokens across all steps")
    duration_seconds: float = Field(default=0.0)
    step_usage: List[StepTokenUsage] = Field(default_factory=list, description="Per-step breakdown of token usage")


class QualityAudit(BaseModel):
    fidelity_score: float = Field(default=10.0, description="0.0 to 10.0 scale")
    style_score: float = Field(default=10.0, description="0.0 to 10.0 scale")
    glossary_compliance_pct: float = Field(default=100.0, description="Percentage of glossary adherence")
    warnings: List[str] = Field(default_factory=list, description="Anomalies, zero-pronoun uncertainties, untranslated lines")
    passed: bool = Field(default=True)


class ParagraphAlignment(BaseModel):
    src_id: int
    src_text: str
    tgt_text: str


class ChapterMetadata(BaseModel):
    chapter_id: str = Field(..., description="Unique chapter identifier e.g. chapter_001")
    chapter_num: int = Field(default=1, description="Sequential integer number")
    source_file: str = Field(..., description="Path to source raw file")
    source_sha256: str = Field(..., description="SHA256 hash of source content for delta detection")
    output_file: str = Field(..., description="Path to translated output file")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model: str = Field(default="gemini-2.5-pro")
    checkpoint: CheckpointData = Field(default_factory=CheckpointData)
    stats: TranslationStats = Field(default_factory=TranslationStats)
    quality_audit: QualityAudit = Field(default_factory=QualityAudit)
    entities_present: List[str] = Field(default_factory=list)
    glossary_terms_applied: List[GlossaryItem] = Field(default_factory=list)
    paragraph_alignments: List[ParagraphAlignment] = Field(default_factory=list)
    review_status: str = Field(default="draft", description="draft, reviewed, approved")


class ProjectMetadataDocument(BaseModel):
    """Consolidated project-level metadata document (.novel/metadata.json)."""
    project_id: str = Field(default="default_project")
    version: int = Field(default=1)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    chapters: Dict[str, ChapterMetadata] = Field(default_factory=dict)
