"""Novel Bible data models for characters, glossary, style rules, and narrative memory."""
import re
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class CharacterNameDetail(BaseModel):
    """Linguistic components of a character's personal name."""
    name: str = Field(default="", description="Given / first name (e.g. 'Mary' or 'メアリィ' or '炎')")
    m_name: str = Field(default="", description="Middle name or noble connector (e.g. 'Lukia' or 'ルクア' or 'von')")
    s_name: str = Field(default="", description="Surname / family / clan name (e.g. 'Legalia' or 'レガリヤ' or '萧')")

    def full_name(self, separator: Optional[str] = None, order: str = "given_first") -> str:
        """Constructs canonical full name from components.
        order: 'given_first' ([name, m_name, s_name]) or 'surname_first' ([s_name, m_name, name]).
        """
        parts = [self.name, self.m_name, self.s_name] if order == "given_first" else [self.s_name, self.m_name, self.name]
        valid_parts = [str(p).strip() for p in parts if p and str(p).strip()]
        if not valid_parts:
            return ""
        if separator is None:
            # Auto-detect Japanese Katakana or CJK script
            is_cjk = any(re.search(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]", p) for p in valid_parts)
            separator = "・" if is_cjk else " "
        return separator.join(valid_parts)

    def is_empty(self) -> bool:
        return not bool((self.name or "").strip() or (self.m_name or "").strip() or (self.s_name or "").strip())


class CharacterNames(BaseModel):
    """Structured name components mapped across source and target languages."""
    source: CharacterNameDetail = Field(
        default_factory=CharacterNameDetail,
        description="Name components in source language native script"
    )
    target: CharacterNameDetail = Field(
        default_factory=CharacterNameDetail,
        description="Name components in target translation language"
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_names(cls, data: Any) -> Any:
        if isinstance(data, dict):
            src = data.get("source")
            tgt = data.get("target")
            if isinstance(src, str):
                data["source"] = {"name": src}
            if isinstance(tgt, str):
                data["target"] = {"name": tgt}
        return data


class CharacterPronouns(BaseModel):
    source: str = Field(default="", description="Source language pronoun(s) (e.g. 'she/her', 'watashi', 'I')")
    target: str = Field(default="", description="Target language pronoun(s) (e.g. 'เธอ', 'ฉัน', 'เขา', 'ผม')")
    relational: Dict[str, str] = Field(
        default_factory=dict,
        description="Relational pronouns/address with specific characters e.g. {'Amelia Barlen': 'หนู/พี่'}"
    )

    @field_validator("source", "target", mode="before")
    @classmethod
    def _coerce_pronouns(cls, v: Any) -> str:
        if isinstance(v, list):
            return ", ".join(str(item).strip() for item in v if str(item).strip())
        return str(v or "").strip()


class CharacterProfile(BaseModel):
    name: str = Field(default="", description="Standard translated character name")
    original_name: str = Field(default="", description="Original raw name in source text")
    names: Optional[CharacterNames] = Field(
        default=None,
        description="Structured name components (name, m_name, s_name) in source and target languages"
    )
    aliases: List[str] = Field(default_factory=list, description="Known nicknames, aliases, titles")
    gender: str = Field(default="unspecified", description="Gender identity for pronoun consistency")
    role: str = Field(default="supporting", description="Role e.g. protagonist, antagonist, supporting, mentor")
    voice: str = Field(default="neutral", description="Tone register, speech quirks, formality level")
    relationships: Dict[str, str] = Field(default_factory=dict, description="Relationship map e.g. {'Elena': 'sister'}")
    pronouns: Optional[CharacterPronouns] = Field(
        default=None,
        description="Source and target language pronouns for zero-anaphora and dialogue consistency"
    )

    @classmethod
    def _parse_name_components(cls, full_name: str) -> Dict[str, str]:
        """Heuristically infers name, m_name, s_name from full name strings for legacy migration."""
        if not full_name:
            return {"name": "", "m_name": "", "s_name": ""}
        parts = [p.strip() for p in re.split(r"[・·\s]+", str(full_name).strip()) if p.strip()]
        if len(parts) == 1:
            return {"name": parts[0], "m_name": "", "s_name": ""}
        elif len(parts) == 2:
            return {"name": parts[0], "m_name": "", "s_name": parts[1]}
        elif len(parts) >= 3:
            return {"name": parts[0], "m_name": " ".join(parts[1:-1]), "s_name": parts[-1]}
        return {"name": "", "m_name": "", "s_name": ""}

    @model_validator(mode="before")
    @classmethod
    def _migrate_and_sync_character(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # 1. Pronoun migration
        if "pronouns" in data:
            p = data["pronouns"]
            if isinstance(p, str):
                data["pronouns"] = {"source": p, "target": ""}
        elif any(k in data for k in ("source_pronoun", "target_pronoun", "source_pronouns", "target_pronouns")):
            src = data.pop("source_pronoun", None) or data.pop("source_pronouns", "")
            tgt = data.pop("target_pronoun", None) or data.pop("target_pronouns", "")
            data["pronouns"] = {"source": src, "target": tgt}

        # 2. Structured name components synchronization
        raw_name = str(data.get("name") or "").strip()
        raw_orig = str(data.get("original_name") or "").strip()
        names_data = data.get("names")

        if names_data:
            if isinstance(names_data, dict):
                src_obj = names_data.get("source") or {}
                tgt_obj = names_data.get("target") or {}
            else:
                src_obj = getattr(names_data, "source", None) or {}
                tgt_obj = getattr(names_data, "target", None) or {}

            def _get_val(obj, fld):
                if isinstance(obj, dict):
                    return str(obj.get(fld) or "")
                return str(getattr(obj, fld, "") or "")

            if not raw_orig and src_obj:
                parts = [_get_val(src_obj, "name"), _get_val(src_obj, "m_name"), _get_val(src_obj, "s_name")]
                v_parts = [p.strip() for p in parts if p and p.strip()]
                if v_parts:
                    sep = "・" if any(re.search(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]", p) for p in v_parts) else " "
                    data["original_name"] = sep.join(v_parts)

            if not raw_name and tgt_obj:
                parts = [_get_val(tgt_obj, "name"), _get_val(tgt_obj, "m_name"), _get_val(tgt_obj, "s_name")]
                v_parts = [p.strip() for p in parts if p and p.strip()]
                if v_parts:
                    data["name"] = " ".join(v_parts)
        elif not names_data and (raw_name or raw_orig):
            src_detail = cls._parse_name_components(raw_orig)
            tgt_detail = cls._parse_name_components(raw_name)
            data["names"] = {
                "source": src_detail,
                "target": tgt_detail,
            }

        return data


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
    ignored_alias_tokens: List[str] = Field(default_factory=list, description="Optional novel-specific tokens/titles to ignore as aliases")


class ChapterSummary(BaseModel):
    chapter_num: int = Field(..., description="Sequential chapter index")
    title: str = Field(default="", description="Chapter title")
    synopsis: str = Field(..., description="Concise overview of plot progression")
    key_events: List[str] = Field(default_factory=list, description="Crucial plot points and reveals")
    character_state_changes: List[str] = Field(default_factory=list, description="Deaths, injuries, rank advances, relationship shifts")
    folder: Optional[str] = Field(default=None, description="Folder/volume scope for chapter summary")
    arc_update: Optional[Dict[str, Any]] = Field(default=None, description="Optional arc progression or transition update from Chronicler")
    story_update: Optional[str] = Field(default=None, description="Optional synthesized whole story update from Chronicler")
    reconciled_characters: Optional[List[CharacterProfile]] = Field(
        default=None,
        description="Refined character profiles reconciled against final publication text"
    )
    reconciled_terms: Optional[List[GlossaryItem]] = Field(
        default=None,
        description="Refined glossary items reconciled against final publication text"
    )


class ArcSummary(BaseModel):
    arc_id: str = Field(default="", description="Unique identifier e.g. arc_0001")
    arc_num: int = Field(default=1, description="Sequential arc number")
    title: str = Field(default="", description="Arc title e.g. 'Royal Academy Entrance'")
    synopsis: str = Field(default="", description="Summary of narrative progression in this arc")
    core_conflict: str = Field(default="", description="Central conflict or goal of this arc")
    status: str = Field(default="active", description="'active' or 'completed'")
    arc_completed: Optional[bool] = Field(default=None, description="Optional boolean flag for completed arc")
    start_chapter: int = Field(default=1, description="Starting chapter number of arc")
    end_chapter: Optional[int] = Field(default=None, description="Ending chapter number if completed")
    folder: Optional[str] = Field(default=None, description="Volume/folder scope")
    key_milestones: List[str] = Field(default_factory=list, description="Key milestones achieved during arc")


ROMAN_NUMERAL_OR_NUMBER_RE = re.compile(r"^(\d+|[ivxlcdm]+)$", re.IGNORECASE)


GRAMMATICAL_PARTICLES: Set[str] = {
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "with", "on", "at", "by", "from", "as", "is", "it"
}


def is_valid_alias_string(alias: str, min_len: int = 2, ignored_tokens: Optional[Set[str]] = None) -> bool:
    """Validate if a string is structurally acceptable as an alias without hardcoded language dictionaries.

    Rejects:
    - Empty strings or pure whitespace
    - Strings shorter than min_len
    - Closed-class grammatical particles ('the', 'a', 'an', 'of', 'in', 'to', etc.)
    - Pure numbers or Roman numerals ('13', 'III', 'IV')
    - Tokens explicitly declared in novel-specific ignored_tokens
    """
    if not alias:
        return False
    s = alias.strip()
    if len(s) < min_len:
        return False
    s_lower = s.lower()
    if s_lower in GRAMMATICAL_PARTICLES:
        return False
    if ignored_tokens and s_lower in ignored_tokens:
        return False
    if ROMAN_NUMERAL_OR_NUMBER_RE.match(s_lower):
        return False
    if s.isascii() and len(s) <= 2:
        return False
    return True


# Backward-compatibility alias (empty set; language-agnostic validation used instead)
GENERIC_STOPWORDS_TITLES: Set[str] = set()


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
        if not name_or_alias or not str(name_or_alias).strip():
            return None
        target = str(name_or_alias).strip()
        target_lower = target.lower()

        # 1. Exact match on name or original_name
        for char in self.characters:
            if char.name.lower() == target_lower or char.original_name.lower() == target_lower:
                return char

        ignored = set(t.lower() for t in self.style_guide.ignored_alias_tokens) if self.style_guide else None

        # 2. Match on aliases (ambiguity-guarded: unique match only)
        if is_valid_alias_string(target, ignored_tokens=ignored):
            alias_matches = [
                char for char in self.characters
                if any(alias.strip().lower() == target_lower for alias in char.aliases)
            ]
            if len(alias_matches) == 1:
                return alias_matches[0]

        # 3. Match structured name components (source & target: given, middle, surname)
        if is_valid_alias_string(target, ignored_tokens=ignored):
            for char in self.characters:
                if char.names:
                    src = char.names.source
                    tgt = char.names.target
                    src_parts = [p.strip().lower() for p in [src.name, src.m_name, src.s_name] if p and p.strip()]
                    tgt_parts = [p.strip().lower() for p in [tgt.name, tgt.m_name, tgt.s_name] if p and p.strip()]
                    if target_lower in (src_parts + tgt_parts):
                        matches = [
                            c for c in self.characters
                            if c.names and (
                                target_lower in [c.names.source.s_name.strip().lower(), c.names.target.s_name.strip().lower()]
                            )
                        ]
                        if len(matches) <= 1:
                            return char

        # 4. Match Japanese/CJK name components (e.g. 'メアリィ' in 'メアリィ・レガリヤ')
        if len(target_lower) >= 2 and is_valid_alias_string(target, min_len=2, ignored_tokens=ignored):
            cjk_matches = []
            for char in self.characters:
                orig = char.original_name.strip()
                if "・" in orig:
                    parts = [p.strip().lower() for p in orig.split("・") if p.strip()]
                    if target_lower in parts:
                        cjk_matches.append(char)
                elif " " in orig and re.search(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]", orig):
                    parts = [p.strip().lower() for p in orig.split() if p.strip()]
                    if target_lower in parts:
                        cjk_matches.append(char)
            if len(cjk_matches) == 1:
                return cjk_matches[0]

        # 5. Match target language compound name components (e.g. given name prefix)
        if len(target_lower) >= 3 and is_valid_alias_string(target, min_len=3, ignored_tokens=ignored):
            tgt_matches = []
            for char in self.characters:
                c_name = char.name.strip()
                if " " in c_name:
                    parts = [p.strip().lower() for p in c_name.split() if p.strip()]
                    if parts and target_lower == parts[0]:
                        tgt_matches.append(char)
            if len(tgt_matches) == 1:
                return tgt_matches[0]

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


