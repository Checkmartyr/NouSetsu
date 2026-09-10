"""Novel Bible data models for characters, glossary, style rules, and narrative memory."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CharacterProfile(BaseModel):
    name: str = Field(..., description="Standard translated character name")
    original_name: str = Field(..., description="Original raw name in source text")
    aliases: List[str] = Field(default_factory=list, description="Known nicknames, aliases, titles")
    gender: str = Field(default="unspecified", description="Gender identity for pronoun consistency")
    role: str = Field(default="supporting", description="Role e.g. protagonist, antagonist, supporting, mentor")
    voice: str = Field(default="neutral", description="Tone register, speech quirks, formality level")
    relationships: Dict[str, str] = Field(default_factory=dict, description="Relationship map e.g. {'Elena': 'sister'}")


class GlossaryItem(BaseModel):
    source: str = Field(..., description="Original term in source language")
    target: str = Field(..., description="Canonical translated term")
    category: str = Field(default="term", description="Category: character, faction, location, skill, item, rank, term")
    notes: str = Field(default="", description="Contextual guidance or etymology")


class StyleGuide(BaseModel):
    target_reading_level: str = Field(default="literary_fiction", description="Tone target: literary_fiction, light_novel, webnovel")
    tense: str = Field(default="past", description="Narrative tense: past or present")
    pov: str = Field(default="third_person", description="Point of view: first_person, third_person, limited, omniscient")
    honorific_mode: str = Field(default="retain", description="Honorific handling: retain (-san/-sama), adapt (Lord/Lady), or drop")
    custom_rules: List[str] = Field(default_factory=list, description="Specialized stylistic directives")


class ChapterSummary(BaseModel):
    chapter_num: int = Field(..., description="Sequential chapter index")
    title: str = Field(default="", description="Chapter title")
    synopsis: str = Field(..., description="Concise overview of plot progression")
    key_events: List[str] = Field(default_factory=list, description="Crucial plot points and reveals")
    character_state_changes: List[str] = Field(default_factory=list, description="Deaths, injuries, rank advances, relationship shifts")


class NovelBible(BaseModel):
    title: str = Field(default="Untitled Novel", description="Novel title")
    source_language: str = Field(default="Japanese", description="Source text language")
    target_language: str = Field(default="English", description="Target text language")
    genre: str = Field(default="general", description="Novel genre (e.g. xianxia, isekai, litrpg, romance, general)")
    characters: List[CharacterProfile] = Field(default_factory=list, description="Roster of known characters")
    glossary: List[GlossaryItem] = Field(default_factory=list, description="Active translation glossary")
    style_guide: StyleGuide = Field(default_factory=StyleGuide, description="Tone, formatting, and translation style rules")
    summaries: List[ChapterSummary] = Field(default_factory=list, description="Rolling narrative summaries of preceding chapters")

    def find_character(self, name_or_alias: str) -> Optional[CharacterProfile]:
        for char in self.characters:
            if char.name.lower() == name_or_alias.lower() or char.original_name == name_or_alias:
                return char
            if any(alias.lower() == name_or_alias.lower() for alias in char.aliases):
                return char
        return None

    def find_term(self, source_term: str) -> Optional[GlossaryItem]:
        for item in self.glossary:
            if item.source == source_term:
                return item
        return None
