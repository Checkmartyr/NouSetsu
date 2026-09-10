"""LangGraph state schema for novel translation workflow."""
from typing import List, Optional
from pydantic import BaseModel, Field
from src.models.bible import CharacterProfile, ChapterSummary, GlossaryItem, NovelBible
from src.models.metadata import ChapterMetadata, PipelineStage, QualityAudit


class TranslationState(BaseModel):
    chapter_id: str = Field(..., description="Chapter identifier")
    chapter_num: int = Field(default=1)
    source_file: str = Field(default="")
    source_sha256: str = Field(default="")
    output_file: str = Field(default="")
    source_text: str = Field(..., description="Raw text of chapter")
    model_name: str = Field(default="gemini-2.5-pro")

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

    metadata: Optional[ChapterMetadata] = None
    error: Optional[str] = None
