"""Deterministic Unicode script and heuristic language detection for novel text."""
from pathlib import Path
import re
from typing import List, Optional


def detect_language(text: str, default: Optional[str] = None) -> Optional[str]:
    """
    Detect language from novel text sample using deterministic Unicode script analysis
    and Latin stop-word heuristics. Runs offline in <1ms without heavy dependencies.

    Supported output:
    - Japanese
    - Korean
    - Chinese
    - Thai
    - Russian
    - Spanish
    - French
    - German
    - English
    """
    if not text or not text.strip():
        return default

    # Sample up to first 8,000 characters to ensure fast, representative detection
    sample = text[:8000]

    # 1. Check Korean (Hangul syllables & Jamo)
    hangul_chars = re.findall(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]", sample)
    if len(hangul_chars) >= 4 or (len(hangul_chars) > 0 and len(hangul_chars) / max(len(sample.strip()), 1) > 0.03):
        return "Korean"

    # 2. Check Japanese (Hiragana & Katakana)
    kana_chars = re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", sample)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", sample)

    # Japanese novel prose almost always contains Hiragana particles (の, は, が, を, た, です)
    if len(kana_chars) >= 3 or (len(cjk_chars) > 0 and len(kana_chars) / max(len(cjk_chars), 1) > 0.015):
        return "Japanese"

    # 3. Check Chinese (CJK Unified Ideographs with zero or negligible Kana/Hangul)
    if len(cjk_chars) >= 8 and len(kana_chars) == 0:
        return "Chinese"

    # 4. Check Thai script
    thai_chars = re.findall(r"[\u0e00-\u0e7f]", sample)
    if len(thai_chars) >= 5:
        return "Thai"

    # 5. Check Cyrillic (Russian)
    cyrillic_chars = re.findall(r"[\u0400-\u04ff]", sample)
    if len(cyrillic_chars) >= 8:
        return "Russian"

    # 6. Latin-based languages (English, Spanish, French, German)
    words = [w.lower() for w in re.findall(r"\b[a-zA-Záéíóúüñäößàèìòùâêîôûç]{2,}\b", sample)]
    if words:
        word_set = set(words)

        es_stops = {"de", "la", "que", "el", "en", "los", "del", "las", "por", "un", "una", "con", "para"}
        fr_stops = {"de", "la", "le", "et", "les", "des", "en", "une", "du", "dans", "est", "pour", "avec"}
        de_stops = {"der", "die", "das", "und", "den", "von", "mit", "sich", "nicht", "ist", "dem", "ein", "eine", "zu"}

        es_score = len(word_set & es_stops)
        fr_score = len(word_set & fr_stops)
        de_score = len(word_set & de_stops)

        max_score = max(es_score, fr_score, de_score)
        if max_score >= 3:
            if de_score == max_score:
                return "German"
            if es_score == max_score and es_score > fr_score:
                return "Spanish"
            if fr_score == max_score and fr_score > es_score:
                return "French"

        # Default Latin text to English
        return "English"

    return default


def detect_language_from_file(file_path: Path, default: Optional[str] = None) -> Optional[str]:
    """Read initial portion of a raw chapter file and detect its language."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return default
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            sample_content = f.read(8000)
            return detect_language(sample_content, default=default)
    except Exception:
        return default


def detect_language_from_dir(dir_path: Path, default: Optional[str] = None) -> Optional[str]:
    """
    Sample up to 3 raw chapter files (.txt, .md) in a directory
    and return the consensus language.
    """
    path = Path(dir_path)
    if not path.exists() or not path.is_dir():
        return default

    raw_files = [f for f in path.iterdir() if f.is_file() and f.suffix.lower() in [".txt", ".md"]]
    if not raw_files:
        return default

    # Sample up to 3 files
    detected_list: List[str] = []
    for f in raw_files[:3]:
        lang = detect_language_from_file(f, default=None)
        if lang:
            detected_list.append(lang)

    if not detected_list:
        return default

    # Return most frequent language
    from collections import Counter
    counts = Counter(detected_list)
    return counts.most_common(1)[0][0]


def is_cjk_language(lang: str) -> bool:
    """Return True if language is Chinese, Japanese, or Korean (where zero-anaphora applies)."""
    normalized = (lang or "").strip().lower()
    return normalized in ["japanese", "chinese", "korean", "cjk", "jp", "zh", "ko", "cn", "kr"]
