"""Script-aware word-boundary glossary filter utility."""
import re
import unicodedata
from typing import List, Optional, Set, Tuple
from nousetsu.models.bible import GlossaryItem

# Matches Unicode letters, numbers, underscores, apostrophes, hyphens, and whitespace
LATIN_UNICODE_REGEX = re.compile(r"^[\w\s'-]+$", re.UNICODE)
LATIN_WORD_REGEX = re.compile(r"^[A-Za-z0-9_\s'-]+$")


def is_term_present(term: str, text: str) -> bool:
    """Checks whether a glossary term exists in text with script-aware word boundaries.

    - For Latin/alphanumeric scripts (e.g. English), enforces \b word boundaries
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
        return bool(re.search(pattern, text, re.IGNORECASE | re.ASCII))

    return term_clean.lower() in text.lower()


def _is_latin_term(term: str) -> bool:
    """Checks if a term consists primarily of Latin-script characters."""
    if not LATIN_UNICODE_REGEX.match(term):
        return False
    # Verifies script base character falls in Latin Unicode range
    for char in term:
        if char.isalpha():
            name = unicodedata.name(char, "")
            if "LATIN" not in name:
                return False
    return True


def _build_batched_pattern(terms: List[str]) -> Optional[re.Pattern]:
    """Compiles multiple terms into a single-pass regex alternation sorted by length."""
    if not terms:
        return None
    # Sort longer terms first to prioritize maximal matches in alternation
    sorted_terms = sorted(terms, key=len, reverse=True)
    escaped = [re.escape(t) for t in sorted_terms]
    # Uses lookarounds or word boundaries to prevent substring overlaps
    pattern = rf"(?<!\w)(?:{'|'.join(escaped)})(?!\w)"
    return re.compile(pattern, re.IGNORECASE | re.ASCII)


def filter_glossary_for_scene(
    glossary: List[GlossaryItem],
    source_text: Optional[str] = None,
    target_text: Optional[str] = None,
    fallback_on_empty: bool = True,
    max_fallback: int = 15,
) -> List[GlossaryItem]:
    """Filters glossary to items whose source appears in source_text or target in target_text.

    Optimized for O(Text Length) matching using single-pass regex compilation,
    pre-allocated lowercase buffers, and deduplicated fallback lists.
    """
    if not glossary:
        return []

    # Prepare case-folded text buffers once
    src_clean = source_text.strip() if source_text else None
    tgt_clean = target_text.strip() if target_text else None

    src_lower = src_clean.lower() if src_clean else None
    tgt_lower = tgt_clean.lower() if tgt_clean else None

    # Step 1: Deduplicate glossary entries while partitioning
    unique_items: List[GlossaryItem] = []
    seen_keys: Set[Tuple[str, str]] = set()

    src_latin_terms: List[str] = []
    src_non_latin_terms: List[str] = []
    tgt_latin_terms: List[str] = []
    tgt_non_latin_terms: List[str] = []

    for item in glossary:
        src_key = item.source.strip()
        tgt_key = item.target.strip()
        key = (src_key.lower(), tgt_key.lower())
        if key in seen_keys or not (src_key or tgt_key):
            continue

        seen_keys.add(key)
        unique_items.append(item)

        if src_clean and src_key:
            if _is_latin_term(src_key):
                src_latin_terms.append(src_key)
            else:
                src_non_latin_terms.append(src_key.lower())

        if tgt_clean and tgt_key:
            if _is_latin_term(tgt_key):
                tgt_latin_terms.append(tgt_key)
            else:
                tgt_non_latin_terms.append(tgt_key.lower())

    # Step 2: Compile batched regular expressions for single-pass matching
    src_pattern = _build_batched_pattern(src_latin_terms) if src_latin_terms else None
    tgt_pattern = _build_batched_pattern(tgt_latin_terms) if tgt_latin_terms else None

    matched_src_terms: Set[str] = set()
    if src_pattern and src_clean:
        matched_src_terms.update(m.group(0).lower() for m in src_pattern.finditer(src_clean))
    if src_lower and src_non_latin_terms:
        for t in src_non_latin_terms:
            if t in src_lower:
                matched_src_terms.add(t)

    matched_tgt_terms: Set[str] = set()
    if tgt_pattern and tgt_clean:
        matched_tgt_terms.update(m.group(0).lower() for m in tgt_pattern.finditer(tgt_clean))
    if tgt_lower and tgt_non_latin_terms:
        for t in tgt_non_latin_terms:
            if t in tgt_lower:
                matched_tgt_terms.add(t)

    # Step 3: Filter deduplicated items against matched sets
    matched: List[GlossaryItem] = [
        item for item in unique_items
        if item.source.strip().lower() in matched_src_terms
        or item.target.strip().lower() in matched_tgt_terms
    ]

    if not matched and fallback_on_empty:
        return unique_items[:max_fallback]

    return matched
