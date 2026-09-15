"""Formatting helpers for durations, numbers, and display text."""


def format_duration(seconds: float) -> str:
    """Format duration in seconds into a human-friendly string (compact style).

    Examples:
        0.0 -> "0s"
        0.4 -> "0.4s"
        45.2 -> "45s"
        846.4 -> "14m 6s"
        3665.0 -> "1h 1m 5s"
    """
    if seconds <= 0:
        return "0s"
    if seconds < 1.0:
        return f"{seconds:.1f}s"

    total_seconds = int(round(seconds))
    if total_seconds < 60:
        return f"{total_seconds}s"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        if secs > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{hours}h"
    else:
        return f"{minutes}m {secs}s"


def clamp_sentence_boundary(text: str, max_len: int = 350) -> str:
    """Clamp text to at most max_len characters, breaking cleanly at sentence or paragraph boundaries.

    Searches backwards from max_len for sentence-ending punctuation ('. ', '!', '?', '。', '！', '？', '”', '」', '』', '\n')
    or whitespace so that words/sentences are not abruptly sliced midway.
    """
    if not text or len(text) <= max_len:
        return text or ""

    snippet = text[:max_len]
    min_cutoff = max(int(max_len * 0.2), 1)

    # 1. Check punctuation boundaries
    punct_markers = ["\n", "。”", ".”", "。」", ". ", "! ", "? ", "!", "?", "。", "！", "？", "”", "」", "』"]
    best_idx = -1
    best_len = 0
    for p in punct_markers:
        idx = snippet.rfind(p)
        if idx >= min_cutoff and idx > best_idx:
            best_idx = idx
            best_len = len(p.strip())

    if best_idx != -1:
        return snippet[:best_idx + best_len].rstrip()

    # 2. Whitespace boundary fallback (e.g. Thai or Latin text without punctuation)
    space_idx = snippet.rfind(" ")
    if space_idx >= min_cutoff:
        return snippet[:space_idx].rstrip() + "..."

    # 3. Fallback if no clean delimiter found in upper half
    return snippet.rstrip() + "..."
