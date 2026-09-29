"""Resolve the machine-wide LLM route used by the Novel-Scraper sidecar."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ScraperLLMSettings:
    model: str
    fallback_model: str
    provider: str
    fallback_provider: str


def _provider_for_model(model: str) -> str:
    normalized = model.strip().lower()
    google_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if normalized.startswith(("mock", "test")):
        return "Mock / offline"
    if normalized.startswith("openrouter:"):
        return "OpenRouter" if openrouter_key else "Unconfigured"
    if normalized.startswith("openai:"):
        return "OpenAI" if openai_key else "Unconfigured"
    if "gemini" in normalized or "gemma" in normalized:
        return "Gemini" if google_key else "Unconfigured"
    if "/" in normalized:
        if openrouter_key:
            return "OpenRouter"
        if normalized.startswith("openai/") and openai_key:
            return "OpenAI"
        return "Unconfigured"
    if normalized.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-")):
        if openai_key:
            return "OpenAI"
        if openrouter_key:
            return "OpenRouter"
    return "Unconfigured"


def resolve_scraper_llm_settings() -> ScraperLLMSettings:
    """Use the optional scraper override, otherwise inherit NouSetsu's global route."""
    model = (
        os.environ.get("NOVEL_SCRAPER_MODEL", "").strip()
        or os.environ.get("NOVEL_MODEL", "").strip()
        or os.environ.get("DEFAULT_MODEL", "").strip()
        or "gemini-3.1-flash-lite"
    )
    fallback_model = (
        os.environ.get("NOVEL_FALLBACK_MODEL", "").strip()
        or "gemini-3.5-flash-lite"
    )
    return ScraperLLMSettings(
        model=model,
        fallback_model=fallback_model,
        provider=_provider_for_model(model),
        fallback_provider=_provider_for_model(fallback_model),
    )
