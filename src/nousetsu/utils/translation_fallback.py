"""Translation fallback utility using Google Translate via deep-translator for safety blocked scenes."""
import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

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
    "auto": "auto",
}


def is_safety_block_exception(err: Any) -> bool:
    """Check if an exception or message indicates a Google AI safety block / prohibited content filter."""
    msg = str(err).lower()
    if "prohibited_content" in msg:
        return True
    if "input blocked" in msg:
        return True
    if "safety block" in msg or "blocked by safety" in msg:
        return True
    if "safety" in msg and any(k in msg for k in ["block", "filter", "violation", "prohibited", "policy", "rating", "reason"]):
        return True
    if "400" in msg and any(k in msg for k in ["prohibited", "safety", "blocked", "content filter"]):
        return True
    return False


def resolve_lang_code(lang: str) -> str:
    """Convert language name or code to ISO format recognized by Google Translator."""
    if not lang:
        return "auto"
    clean = lang.strip().lower()
    return _LANG_MAP.get(clean, clean)


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
        res = translator.translate(text)
        return res if res is not None else text

    # Batch lines for larger texts to avoid exceeding character limits
    lines = text.split("\n")
    batches: List[str] = []
    current_batch: List[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > 4000 and current_batch:
            batches.append("\n".join(current_batch))
            current_batch = [line]
            current_len = line_len
        else:
            current_batch.append(line)
            current_len += line_len

    if current_batch:
        batches.append("\n".join(current_batch))

    translated_batches = []
    for b in batches:
        translated_b = translator.translate(b)
        translated_batches.append(translated_b if translated_b is not None else b)

    return "\n".join(translated_batches)
