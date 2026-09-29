"""Resolve the machine-wide LLM route used by the Novel-Scraper sidecar."""

from dataclasses import dataclass
import os
from typing import Mapping, Optional

from nousetsu.models.config import ProjectConfig


@dataclass(frozen=True)
class ScraperLLMSettings:
    model: str
    fallback_model: str
    provider: str
    fallback_provider: str


def _provider_for_model(model: str, environ: Optional[Mapping[str, str]] = None) -> str:
    normalized = model.strip().lower()
    env = os.environ if environ is None else environ
    google_key = env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY")
    openai_key = env.get("OPENAI_API_KEY")
    openrouter_key = env.get("OPENROUTER_API_KEY")
    custom_key = env.get("CUSTOM_API_KEY")
    custom_base_url = env.get("CUSTOM_API_BASE_URL", "").strip()

    if normalized.startswith(("mock", "test")):
        return "Mock / offline"
    if normalized.startswith("custom:"):
        return "Custom OpenAI-compatible" if custom_key and custom_base_url else "Unconfigured"
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


def resolve_scraper_llm_settings(
    environ: Optional[Mapping[str, str]] = None,
) -> ScraperLLMSettings:
    """Resolve the scraper's provider route without changing process environment."""
    env = os.environ if environ is None else environ
    model = (
        env.get("NOVEL_SCRAPER_MODEL", "").strip()
        or env.get("NOVEL_MODEL", "").strip()
        or env.get("DEFAULT_MODEL", "").strip()
        or "gemini-3.1-flash-lite"
    )
    fallback_model = env.get("NOVEL_FALLBACK_MODEL", "").strip() or "gemini-3.5-flash-lite"
    return ScraperLLMSettings(
        model=model,
        fallback_model=fallback_model,
        provider=_provider_for_model(model, env),
        fallback_provider=_provider_for_model(fallback_model, env),
    )


def scraper_subprocess_environment(
    config: ProjectConfig, environ: Optional[Mapping[str, str]] = None
) -> dict[str, str]:
    """Build an isolated child-process environment with resolved project scraper settings."""
    env = dict(os.environ if environ is None else environ)
    env["NOVEL_SCRAPER_MODEL"] = config.get_agent_model("scraper", environ=env)
    env["NOVEL_FALLBACK_MODEL"] = config.get_fallback_model(environ=env) or "gemini-3.5-flash-lite"
    generation = config.get_agent_generation_settings("scraper", environ=env)
    env["NOVEL_TEMPERATURE"] = str(generation["temperature"])
    env["NOVEL_USE_INTERACTIONS"] = "1" if generation["use_interactions_api"] else "0"
    for env_key, setting_key in (
        ("NOVEL_THINKING_LEVEL", "thinking_level"),
        ("NOVEL_THINKING_BUDGET", "thinking_budget"),
    ):
        value = generation[setting_key]
        if value is None:
            env.pop(env_key, None)
        else:
            env[env_key] = str(value)
    return env
