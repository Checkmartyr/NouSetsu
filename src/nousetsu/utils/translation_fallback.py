"""Translation fallback utility using Google Translate via deep-translator for safety blocked scenes."""
import logging
import re
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def bisect_text(text: str) -> Tuple[str, str]:
    """Split text into two balanced halves prioritized by paragraph break, line break, sentence boundary, or midpoint."""
    if not text or not text.strip():
        return text, ""
    if len(text) <= 1:
        return text, ""

    mid = len(text) // 2

    # Priority 1: Paragraph break (\r?\n\s*\r?\n) closest to midpoint
    para_matches = list(re.finditer(r"\r?\n\s*\r?\n", text))
    best_match = None
    best_dist = float("inf")
    for m in para_matches:
        start, end = m.start(), m.end()
        left = text[:start].strip()
        right = text[end:].strip()
        if left and right:
            dist = abs(start - mid)
            if dist < best_dist:
                best_dist = dist
                best_match = (left, right)
    if best_match:
        return best_match

    # Priority 2: Line break (\r?\n) closest to midpoint
    line_matches = list(re.finditer(r"\r?\n", text))
    best_match = None
    best_dist = float("inf")
    for m in line_matches:
        start, end = m.start(), m.end()
        left = text[:start].strip()
        right = text[end:].strip()
        if left and right:
            dist = abs(start - mid)
            if dist < best_dist:
                best_dist = dist
                best_match = (left, right)
    if best_match:
        return best_match

    # Priority 3: Sentence boundary ([。！？] or [.!?] + whitespace) closest to midpoint
    sentence_pattern = r"([。！？]+[」』\"'\u201d\u2019]?\s*|[.!?]+[\"'\u201d\u2019]?\s+)"
    sent_matches = list(re.finditer(sentence_pattern, text))
    best_match = None
    best_dist = float("inf")
    for m in sent_matches:
        split_pos = m.end()
        left = text[:split_pos].strip()
        right = text[split_pos:].strip()
        if left and right:
            dist = abs(split_pos - mid)
            if dist < best_dist:
                best_dist = dist
                best_match = (left, right)
    if best_match:
        return best_match

    # Priority 4: Exact character midpoint if unpunctuated
    left = text[:mid].strip()
    right = text[mid:].strip()
    if not left and right:
        return text, ""
    return left, right


def can_subdivide_text(text: str, min_lines: int = 8, min_chars: int = 200) -> bool:
    """Check if text can be recursively subdivided (has enough lines or chars and produces non-empty bisection)."""
    if not text or not text.strip():
        return False
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < min_lines and len(text.strip()) < min_chars:
        return False
    left, right = bisect_text(text)
    return bool(left.strip()) and bool(right.strip())


_LANG_MAP = {
    "japanese": "ja",
    "ja": "ja",
    "english": "en",
    "en": "en",
    "thai": "th",
    "th": "th",
    "chinese": "zh-CN",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh_cn": "zh-CN",
    "chinese (simplified)": "zh-CN",
    "simplified chinese": "zh-CN",
    "chinese (traditional)": "zh-TW",
    "traditional chinese": "zh-TW",
    "zh-tw": "zh-TW",
    "zh_tw": "zh-TW",
    "korean": "ko",
    "ko": "ko",
    "german": "de",
    "de": "de",
    "french": "fr",
    "fr": "fr",
    "spanish": "es",
    "es": "es",
    "vietnamese": "vi",
    "vi": "vi",
    "indonesian": "id",
    "id": "id",
    "russian": "ru",
    "ru": "ru",
    "italian": "it",
    "it": "it",
    "portuguese": "pt",
    "pt": "pt",
    "auto": "auto",
}


def is_safety_block_exception(err: Any) -> bool:
    """Check if an exception or message indicates a Google AI / provider safety block or content policy filter."""
    msg = str(err).lower()

    # Never treat transient server / network / parse errors as safety blocks
    if any(k in msg for k in ["500 internal server error", "502 bad gateway", "503 service unavailable", "504 gateway timeout"]):
        return False

    if "prohibited_content" in msg or "prohibited content" in msg:
        return True
    if any(k in msg for k in ["input blocked", "response blocked", "prompt blocked", "blocked by safety", "safety block"]):
        return True
    if "harm_category" in msg or "harm category" in msg:
        return True
    if any(k in msg for k in ["content_filter", "content filter", "content policy", "content_policy"]):
        return True
    if "sexually_explicit" in msg or "sensitive content" in msg:
        return True
    if "safety" in msg and any(k in msg for k in ["block", "filter", "violation", "prohibited", "policy", "rating", "reason", "flag", "exception"]):
        return True
    if "finish_reason" in msg and "safety" in msg:
        return True
    if "400" in msg and any(k in msg for k in ["prohibited", "safety", "blocked", "content", "filter", "policy", "sensitive"]):
        return True

    # Check object attributes if present (e.g. FinishReason enum or response_metadata)
    finish_reason = getattr(err, "finish_reason", None)
    if finish_reason and "safety" in str(finish_reason).lower():
        return True

    return False


def resolve_lang_code(lang: str) -> str:
    """Convert language name or code to ISO format recognized by Google Translator."""
    if not lang:
        return "auto"
    clean = lang.strip().lower()
    return _LANG_MAP.get(clean, clean)


def _split_into_chunks(text: str, max_chars: int = 4000) -> List[str]:
    """Split text into chunks under max_chars without breaking mid-sentence where possible."""
    if len(text) <= max_chars:
        return [text]

    lines = text.split("\n")
    batches: List[str] = []
    current_batch: List[str] = []
    current_len = 0

    for line in lines:
        if len(line) > max_chars:
            if current_batch:
                batches.append("\n".join(current_batch))
                current_batch = []
                current_len = 0
            # Split long line by sentence endings (CJK and Latin)
            subparts = re.split(r"([。！？.!?]+[\s]*)", line)
            current_sub = ""
            for part in subparts:
                if len(current_sub) + len(part) > max_chars:
                    if current_sub:
                        batches.append(current_sub)
                        current_sub = ""
                    if len(part) > max_chars:
                        for i in range(0, len(part), max_chars):
                            batches.append(part[i:i + max_chars])
                    else:
                        current_sub = part
                else:
                    current_sub += part
            if current_sub:
                batches.append(current_sub)
        else:
            line_len = len(line) + 1
            if current_len + line_len > max_chars and current_batch:
                batches.append("\n".join(current_batch))
                current_batch = [line]
                current_len = line_len
            else:
                current_batch.append(line)
                current_len += line_len

    if current_batch:
        batches.append("\n".join(current_batch))

    return batches


def translate_via_google(text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
    """Fallback translator using Google Translate via deep-translator for sensitive scenes."""
    if not text or not text.strip():
        return text

    src = resolve_lang_code(source_lang)
    tgt = resolve_lang_code(target_lang)

    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        logger.error("deep-translator is not installed; returning original text.")
        return text

    translator = GoogleTranslator(source=src, target=tgt)

    # Free Google Translate endpoint limit is ~5000 chars per request
    if len(text) <= 4500:
        try:
            res = translator.translate(text)
            return res if res is not None else text
        except Exception as e:
            logger.error(f"Google translate request failed: {e}; returning source text.")
            return text

    # Batch lines for larger texts to avoid exceeding character limits
    batches = _split_into_chunks(text, max_chars=4000)

    translated_batches = []
    for b in batches:
        try:
            translated_b = translator.translate(b)
            translated_batches.append(translated_b if translated_b is not None else b)
        except Exception as e:
            logger.error(f"Google translate batch request failed: {e}; retaining raw batch text.")
            translated_batches.append(b)

    return "\n".join(translated_batches)
