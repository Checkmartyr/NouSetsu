"""Chapter extraction, alignment, and filename parsing utilities."""
from pathlib import Path
import re
from typing import Union

MODIFIER_PATTERN = re.compile(
    r"\b(?:extra|side[\s_-]*story|special|sp|ex|omake|gaiden|afterword|interlude)\b|番外|外伝|特典|後書き",
    re.IGNORECASE,
)
CHAPTER_PREFIX_PATTERN = re.compile(r"(?:chapter|ch|ep|第)[\s_\.]*(\d+)", re.IGNORECASE)
VOLUME_PATTERN = re.compile(r"(?:vol|volume|v)[\s_\.]*\d+", re.IGNORECASE)
LEADING_SEQ_PATTERN = re.compile(r"^(\d+)[\s_\-\.]+")


def extract_chapter_num(path: Union[Path, str], default_idx: int = 1) -> int:
    """Extract numeric chapter index from filename with modifier and sequence awareness."""
    name = Path(path).stem
    normalized = re.sub(r"[_.-]", " ", name)

    has_modifier = bool(MODIFIER_PATTERN.search(normalized))
    seq_match = LEADING_SEQ_PATTERN.match(name)

    # 1. If file has a leading sequence number AND a modifier (e.g. '035_Extra Chapter 1'),
    # the sequence number represents its volume/folder chapter order.
    if seq_match and has_modifier:
        try:
            return int(seq_match.group(1))
        except ValueError:
            pass

    # 2. Match explicit chapter prefixes (e.g. 'Chapter 34', 'ch. 5', '第10章')
    # If no modifier is present, the explicit chapter number takes precedence
    if not has_modifier:
        match = CHAPTER_PREFIX_PATTERN.search(name)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    # 3. If file starts with a leading sequence number without explicit 'chapter' keyword (e.g. '001_Title'), use it
    if seq_match:
        try:
            return int(seq_match.group(1))
        except ValueError:
            pass

    # 4. If modifier was present and had an inner chapter number (e.g. 'Extra Chapter 1' without sequence prefix)
    match = CHAPTER_PREFIX_PATTERN.search(name)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    # 5. Strip volume indicators so volume numbers aren't mistaken for chapter numbers
    cleaned = VOLUME_PATTERN.sub("", name)
    m = re.search(r"(\d+)", cleaned)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass

    return default_idx
