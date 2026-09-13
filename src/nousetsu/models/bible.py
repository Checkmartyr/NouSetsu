"""Novel Bible data models for characters, glossary, style rules, and narrative memory."""
from typing import Any, Dict, List, Optional
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
    folder: Optional[str] = Field(default=None, description="Folder/volume scope for chapter summary")
    arc_update: Optional[Dict[str, Any]] = Field(default=None, description="Optional arc progression or transition update from Chronicler")
    story_update: Optional[str] = Field(default=None, description="Optional synthesized whole story update from Chronicler")


class ArcSummary(BaseModel):
    arc_id: str = Field(default="", description="Unique identifier e.g. arc_0001")
    arc_num: int = Field(default=1, description="Sequential arc number")
    title: str = Field(default="", description="Arc title e.g. 'Royal Academy Entrance'")
    synopsis: str = Field(default="", description="Summary of narrative progression in this arc")
    core_conflict: str = Field(default="", description="Central conflict or goal of this arc")
    status: str = Field(default="active", description="'active' or 'completed'")
    start_chapter: int = Field(default=1, description="Starting chapter number of arc")
    end_chapter: Optional[int] = Field(default=None, description="Ending chapter number if completed")
    folder: Optional[str] = Field(default=None, description="Volume/folder scope")
    key_milestones: List[str] = Field(default_factory=list, description="Key milestones achieved during arc")


class NovelBible(BaseModel):
    title: str = Field(default="Ascendance of a Bookworm", description="Novel title")
    source_language: str = Field(default="English", description="Source text language")
    target_language: str = Field(default="Thai", description="Target text language")
    genre: str = Field(default="general", description="Novel genre (e.g. xianxia, isekai, litrpg, romance, general)")
    characters: List[CharacterProfile] = Field(default_factory=list, description="Roster of known characters")
    glossary: List[GlossaryItem] = Field(default_factory=list, description="Active translation glossary")
    style_guide: StyleGuide = Field(default_factory=StyleGuide, description="Tone, formatting, and translation style rules")
    summaries: List[ChapterSummary] = Field(default_factory=list, description="Rolling narrative summaries of preceding chapters")
    cross_folder_summaries: bool = Field(default=True, description="Enable rolling context backfill across sequential folders")
    whole_story_summary: str = Field(default="", description="Overarching summary of the entire novel so far")
    active_arc: Optional[ArcSummary] = Field(default=None, description="Currently ongoing story arc")
    archived_arcs: List[ArcSummary] = Field(default_factory=list, description="Concluded story arcs")

    def find_character(self, name_or_alias: str) -> Optional[CharacterProfile]:
        for char in self.characters:
            if char.name.lower() == name_or_alias.lower() or char.original_name == name_or_alias:
                return char
            if any(alias.lower() == name_or_alias.lower() for alias in char.aliases):
                return char
        return None

    def find_term(self, source_term: str) -> Optional[GlossaryItem]:
        target = source_term.strip().lower()
        for item in self.glossary:
            if item.source.strip().lower() == target:
                return item
        return None

    def get_all_folders(self) -> List[str]:
        """Return naturally sorted list of unique folder scopes present in summaries."""
        unique_folders = {s.folder for s in self.summaries if s.folder}
        from natsort import natsorted
        return natsorted(list(unique_folders))

    def get_summaries_for_folder(
        self,
        folder: Optional[str] = None,
        cross_folder: bool = False,
        current_chapter_num: Optional[int] = None,
        limit: Optional[int] = None,
        folder_order: Optional[List[str]] = None
    ) -> List[ChapterSummary]:
        """Return summaries filtered for a specific folder. If cross_folder is True, delegates to get_rolling_context."""
        if cross_folder:
            return self.get_rolling_context(
                folder=folder,
                current_chapter_num=current_chapter_num,
                limit=limit or 3,
                cross_folder=True,
                folder_order=folder_order
            )
        if not folder:
            return sorted(self.summaries, key=lambda s: (s.folder or "", s.chapter_num))
        filtered = [s for s in self.summaries if s.folder == folder or s.folder is None]
        return sorted(filtered, key=lambda s: s.chapter_num)

    def get_rolling_context(
        self,
        folder: Optional[str] = None,
        current_chapter_num: Optional[int] = None,
        limit: int = 3,
        cross_folder: bool = True,
        folder_order: Optional[List[str]] = None
    ) -> List[ChapterSummary]:
        """
        Retrieve preceding summaries for rolling context.
        1. Collects summaries in `folder` with `chapter_num < current_chapter_num` (if chapter_num provided).
        2. If count < limit and cross_folder is True, backfills from the previous folder(s)
           in natural volume order.
        """
        if not folder:
            all_sorted = sorted(self.summaries, key=lambda s: (s.folder or "", s.chapter_num))
            if current_chapter_num is not None:
                all_sorted = [s for s in all_sorted if s.chapter_num < current_chapter_num]
            return all_sorted[-limit:] if limit else all_sorted

        # 1. Collect within active folder
        current_folder_summaries = [s for s in self.summaries if s.folder == folder or s.folder is None]
        current_folder_summaries = sorted(current_folder_summaries, key=lambda s: s.chapter_num)
        if current_chapter_num is not None:
            current_folder_summaries = [s for s in current_folder_summaries if s.chapter_num < current_chapter_num]

        result = list(current_folder_summaries)

        # 2. Backfill from preceding folders if needed and cross_folder enabled
        if cross_folder and len(result) < limit:
            needed = limit - len(result)
            order = list(folder_order) if folder_order else self.get_all_folders()
            if folder and folder not in order:
                from natsort import natsorted
                order = natsorted(list(set(order) | {folder}))
            if folder in order:
                idx = order.index(folder)
                # Traverse preceding folders in reverse (immediate predecessor first)
                backfill_candidates: List[ChapterSummary] = []
                for prev_idx in range(idx - 1, -1, -1):
                    prev_folder = order[prev_idx]
                    prev_summaries = [s for s in self.summaries if s.folder == prev_folder]
                    prev_summaries = sorted(prev_summaries, key=lambda s: s.chapter_num)
                    if prev_summaries:
                        backfill_candidates = prev_summaries + backfill_candidates
                        if len(backfill_candidates) >= needed:
                            break
                if backfill_candidates:
                    chosen_backfill = backfill_candidates[-needed:]
                    result = chosen_backfill + result

        return result[-limit:] if limit else result

    def get_all_arcs(self) -> List[ArcSummary]:
        """Return all story arcs (archived + active) sorted by arc_num."""
        arcs = list(self.archived_arcs)
        if self.active_arc and not any(a.arc_num == self.active_arc.arc_num for a in arcs):
            arcs.append(self.active_arc)
        return sorted(arcs, key=lambda a: a.arc_num)

    def get_hierarchical_context(
        self,
        folder: Optional[str] = None,
        current_chapter_num: Optional[int] = None,
        limit: int = 3,
        cross_folder: bool = True,
        folder_order: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Return structured 3-tier narrative context:
        - whole_story: Macro overview
        - active_arc: Meso arc context
        - rolling_summaries: Micro immediate chapter context
        """
        rolling = self.get_rolling_context(
            folder=folder,
            current_chapter_num=current_chapter_num,
            limit=limit,
            cross_folder=cross_folder,
            folder_order=folder_order
        )
        return {
            "whole_story": self.whole_story_summary,
            "active_arc": self.active_arc,
            "archived_arcs": self.archived_arcs,
            "rolling_summaries": rolling
        }


