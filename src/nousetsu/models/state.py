"""LangGraph state schema for novel translation workflow."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from nousetsu.models.bible import CharacterProfile, ChapterSummary, GlossaryItem, NovelBible
from nousetsu.models.metadata import ChapterMetadata, PipelineStage, QualityAudit, StepTokenUsage


class TranslationState(BaseModel):
    chapter_id: str = Field(..., description="Chapter identifier")
    chapter_num: int = Field(default=1)
    source_file: str = Field(default="")
    source_sha256: str = Field(default="")
    output_file: str = Field(default="")
    source_text: str = Field(..., description="Raw text of chapter")
    model_name: str = Field(default="gemini-2.5-pro")
    genre: str = Field(default="general", description="Novel genre")
    active_skills: Dict[str, List[str]] = Field(default_factory=dict, description="Active skills used per stage")

    novel_bible: NovelBible = Field(default_factory=NovelBible)
    active_glossary: List[GlossaryItem] = Field(default_factory=list)
    active_characters: List[CharacterProfile] = Field(default_factory=list)
    rolling_summaries: List[str] = Field(default_factory=list)

    current_stage: PipelineStage = Field(default=PipelineStage.NONE)
    extracted_terms: List[GlossaryItem] = Field(default_factory=list)
    extracted_characters: List[CharacterProfile] = Field(default_factory=list)

    draft_text: str = Field(default="")
    critique_notes: str = Field(default="")
    quality_audit: QualityAudit = Field(default_factory=QualityAudit)
    polished_text: str = Field(default="")
    new_chapter_summary: Optional[ChapterSummary] = None

    review_iteration: int = Field(default=1, description="Current review loop iteration (1-indexed)")
    max_review_loops: int = Field(default=3, description="Maximum review passes allowed")
    quality_threshold: float = Field(default=8.5, description="Target fidelity and style score threshold")
    best_polished_text: str = Field(default="", description="Polished text candidate with highest score")
    best_audit: Optional[QualityAudit] = Field(default=None, description="Quality audit of best candidate")

    metadata: Optional[ChapterMetadata] = None
    step_token_records: List[StepTokenUsage] = Field(default_factory=list, description="Granular token metrics recorded for each pipeline step")
    error: Optional[str] = None

