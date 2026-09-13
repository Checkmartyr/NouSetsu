"""Pydantic schemas for agent structured outputs."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from nousetsu.models.bible import ChapterSummary, CharacterProfile, GlossaryItem
from nousetsu.models.metadata import QualityAudit


class ExtractorResult(BaseModel):
    """Structured extraction output from EntityExtractorAgent."""
    new_characters: List[CharacterProfile] = Field(
        default_factory=list,
        description="Newly identified characters appearing in the chapter text"
    )
    new_terms: List[GlossaryItem] = Field(
        default_factory=list,
        description="Newly identified terms, cultivation realms, locations, items, or factions"
    )
    active_terms_in_chapter: List[str] = Field(
        default_factory=list,
        description="Source terms from the known glossary actively present in this chapter"
    )


class CritiqueResult(BaseModel):
    """Structured audit output from CritiqueAgent."""
    fidelity_score: float = Field(
        default=8.0,
        description="Strict translation fidelity score from 0.0 to 10.0 assessing omissions, accuracy, and register"
    )
    style_score: float = Field(
        default=7.8,
        description="Target language prose style score from 0.0 to 10.0 assessing cadence, natural flow, and dialogue voice"
    )
    glossary_compliance_pct: float = Field(
        default=100.0,
        description="Percentage of glossary adherence (0.0 to 100.0)"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Specific errors, ambiguities, dropped clauses, or glossary mismatches"
    )
    critique_notes: str = Field(
        default="",
        description="Granular, line-by-line actionable feedback and diff recommendations for the PolishingAgent"
    )

    def to_quality_audit(self) -> QualityAudit:
        """Convert to internal QualityAudit model."""
        return QualityAudit(
            fidelity_score=self.fidelity_score,
            style_score=self.style_score,
            glossary_compliance_pct=self.glossary_compliance_pct,
            warnings=self.warnings,
            passed=(self.fidelity_score >= 7.5 and self.style_score >= 7.5)
        )


class ChroniclerArcUpdate(BaseModel):
    """Meso-level story arc progression from ChroniclerAgent."""
    title: str = Field(default="", description="Current active story arc title")
    core_conflict: str = Field(default="", description="Central conflict or objective of this arc")
    synopsis: str = Field(default="", description="Cumulative narrative progression of the active arc so far")
    milestones: List[str] = Field(default_factory=list, description="Key milestones achieved during this arc")
    is_completed: bool = Field(default=False, description="Whether this chapter concludes the current arc")


class ChroniclerResult(BaseModel):
    """Structured chapter summary and narrative memory from ChroniclerAgent."""
    chapter_num: int = Field(default=1, description="Sequential chapter index")
    title: str = Field(default="", description="Chapter title")
    synopsis: str = Field(default="", description="Concise 2-3 paragraph overview of plot events")
    key_events: List[str] = Field(default_factory=list, description="Crucial plot points, reveals, and turning points")
    character_state_changes: List[str] = Field(
        default_factory=list,
        description="Injuries, deaths, relationship developments, level-ups, or item acquisitions"
    )
    arc_update: Optional[ChroniclerArcUpdate] = Field(
        default=None,
        description="Optional active story arc progress or conclusion update"
    )
    story_update: Optional[str] = Field(
        default=None,
        description="Optional synthesized whole-story summary update if milestone reached"
    )
    chapter_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Support for nested chapter_summary envelope if model formats hierarchically"
    )

    def to_chapter_summary(
        self,
        default_chapter_num: int,
        default_title: str,
        folder: Optional[str] = None
    ) -> ChapterSummary:
        c_num = default_chapter_num if default_chapter_num is not None else (self.chapter_num or 1)
        c_title = self.title or default_title
        c_synopsis = self.synopsis
        c_key_events = self.key_events
        c_char_changes = self.character_state_changes
        arc_up = self.arc_update.model_dump() if self.arc_update else None
        story_up = self.story_update

        # Handle nested chapter_summary structure if returned
        if self.chapter_summary and isinstance(self.chapter_summary, dict):
            if default_chapter_num is None:
                c_num = self.chapter_summary.get("chapter_num", c_num)
            c_title = self.chapter_summary.get("title", c_title)
            c_synopsis = self.chapter_summary.get("synopsis", c_synopsis)
            c_key_events = self.chapter_summary.get("key_events", c_key_events)
            c_char_changes = self.chapter_summary.get("character_state_changes", c_char_changes)
            if not arc_up and "arc_update" in self.chapter_summary:
                arc_up = self.chapter_summary["arc_update"]
            if not story_up and "story_update" in self.chapter_summary:
                story_up = self.chapter_summary["story_update"]

        return ChapterSummary(
            chapter_num=c_num,
            title=c_title,
            synopsis=c_synopsis,
            key_events=c_key_events,
            character_state_changes=c_char_changes,
            folder=folder,
            arc_update=arc_up,
            story_update=story_up
        )
