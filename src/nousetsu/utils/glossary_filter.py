"""Script-aware word-boundary glossary filter utility."""
import re
from typing import List, Optional
from nousetsu.models.bible import GlossaryItem

LATIN_WORD_REGEX = re.compile(r"^[A-Za-z0-9_\s'-]+$")


def is_term_present(term: str, text: str) -> bool:
    """Checks whether a glossary term exists in text with script-aware word boundaries.

    - For Latin/alphanumeric scripts (e.g. English), enforces \\b word boundaries
      to avoid substring false positives (e.g. 'Villa' matching 'Villainess' or 'Fia' matching 'Ifia').
    - For non-Latin scripts (CJK ideographs, Kana, Hangul, Thai), uses case-insensitive substring search.
    """
    if not term or not text:
        return False
    term_clean = term.strip()
    if not term_clean:
        return False

    if LATIN_WORD_REGEX.match(term_clean):
        pattern = r"\b" + re.escape(term_clean) + r"\b"
        return bool(re.search(pattern, text, re.IGNORECASE))

    return term_clean.lower() in text.lower()


def filter_glossary_for_scene(
    glossary: List[GlossaryItem],
    source_text: Optional[str] = None,
    target_text: Optional[str] = None,
    fallback_on_empty: bool = True,
    max_fallback: int = 15,
) -> List[GlossaryItem]:
    """Filters glossary to items whose source appears in source_text or target appears in target_text.

    Args:
        glossary: Full active glossary item list.
        source_text: Raw source language text.
        target_text: Optional drafted / translated target language text.
        fallback_on_empty: If True and zero items match, returns top max_fallback items.
                           If False (e.g. for audit or metadata serialization), returns empty list.
        max_fallback: Maximum fallback terms when zero match.
    """
    if not glossary:
        return []

    matched: List[GlossaryItem] = []
    seen_keys = set()

    for item in glossary:
        item_key = (item.source.strip().lower(), item.target.strip().lower())
        if item_key in seen_keys:
            continue

        in_source = bool(source_text and is_term_present(item.source, source_text))
        in_target = bool(target_text and is_term_present(item.target, target_text))

        if in_source or in_target:
            seen_keys.add(item_key)
            matched.append(item)

    if not matched and fallback_on_empty:
        return glossary[:max_fallback]

    return matched
