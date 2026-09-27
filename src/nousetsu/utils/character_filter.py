import re
from typing import List, Optional, Set
from nousetsu.models.bible import CharacterProfile

CORE_ROLES: Set[str] = {
    "protagonist",
    "main",
    "lead",
    "hero",
    "heroine",
}


def filter_characters_for_scene(
    characters: List[CharacterProfile],
    source_text: Optional[str] = None,
    target_text: Optional[str] = None,
    always_include_roles: Optional[Set[str]] = None,
    fallback_on_empty: bool = True,
    max_characters: int = 15,
) -> List[CharacterProfile]:
    """Filters character roster to characters relevant to a specific scene or chunk.

    Inclusion rules:
    1. Characters with core roles (e.g. protagonist, main) are always included to safeguard
       zero-anaphora pronoun resolution where subject names are omitted in East Asian prose.
    2. Characters whose `original_name` appears in the source or target text.
    3. Characters whose translated `name` appears in the source or target text.
    4. Characters whose `aliases` appear in the source or target text.

    Fallback:
    If zero characters match and fallback_on_empty is True, returns the first `max_characters`
    from the input roster to ensure the model still receives a valid character roster for
    general scene context. If fallback_on_empty is False, returns an empty list.
    """
    if not characters:
        return []

    core_roles = {r.lower() for r in always_include_roles} if always_include_roles is not None else CORE_ROLES

    # Build lower-cased search corpus
    search_corpus = ""
    if source_text and source_text.strip():
        search_corpus += source_text.lower() + " "
    if target_text and target_text.strip():
        search_corpus += target_text.lower()

    # If no text was provided, fallback to top characters
    if not search_corpus.strip():
        return characters[:max_characters] if fallback_on_empty else []

    core_matches: List[CharacterProfile] = []
    scene_matches: List[CharacterProfile] = []
    seen_names: Set[tuple] = set()

    for c in characters:
        c_key = (c.name.strip().lower(), c.original_name.strip().lower())
        if c_key in seen_names:
            continue

        role_lower = (c.role or "").strip().lower()
        is_core = role_lower in core_roles

        # Check textual presence
        has_text_mention = False

        orig = (c.original_name or "").strip().lower()
        if orig and orig in search_corpus:
            has_text_mention = True

        # Check CJK / compound components of original_name (e.g. "サフィナ" from "サフィナ・カルシャナ")
        if not has_text_mention and orig and any(delim in orig for delim in ("・", "·", " ", "　", "/", "_", "-")):
            orig_parts = re.split(r"[・·\s/_\-]+", orig)
            for part in orig_parts:
                part_clean = part.strip()
                if len(part_clean) >= 2 and part_clean in search_corpus:
                    has_text_mention = True
                    break

        # Check structured name components in source language (e.g. given name or surname in source text)
        if not has_text_mention and c.names and source_text:
            src_n = c.names.source
            src_corpus = source_text.lower()
            for part in (src_n.name, src_n.m_name, src_n.s_name):
                p_clean = (part or "").strip().lower()
                if len(p_clean) >= 2 and p_clean in src_corpus:
                    has_text_mention = True
                    break

        name = (c.name or "").strip().lower()
        if not has_text_mention and name and len(name) >= 2 and name in search_corpus:
            has_text_mention = True

        if not has_text_mention and c.aliases:
            for alias in c.aliases:
                alias_clean = (alias or "").strip().lower()
                if alias_clean and len(alias_clean) >= 2 and alias_clean in search_corpus:
                    has_text_mention = True
                    break

        if is_core:
            seen_names.add(c_key)
            core_matches.append(c)
        elif has_text_mention:
            seen_names.add(c_key)
            scene_matches.append(c)

    combined = core_matches + scene_matches
    if not combined:
        return characters[:max_characters] if fallback_on_empty else []

    return combined[:max_characters] if max_characters > 0 else combined
