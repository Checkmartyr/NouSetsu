"""Tests for the scraper's inherited machine-wide model route."""

from nousetsu.scraper.llm_config import resolve_scraper_llm_settings


def test_scraper_model_override_and_global_fallback(monkeypatch):
    monkeypatch.setenv("NOVEL_SCRAPER_MODEL", "openrouter:anthropic/claude-3.7-sonnet")
    monkeypatch.setenv("NOVEL_MODEL", "openai:gpt-4.1")
    monkeypatch.setenv("NOVEL_FALLBACK_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    settings = resolve_scraper_llm_settings()

    assert settings.model == "openrouter:anthropic/claude-3.7-sonnet"
    assert settings.fallback_model == "openai:gpt-4.1-mini"
    assert settings.provider == "OpenRouter"
    assert settings.fallback_provider == "OpenAI"


def test_scraper_inherits_primary_model_when_override_is_blank(monkeypatch):
    monkeypatch.delenv("NOVEL_SCRAPER_MODEL", raising=False)
    monkeypatch.setenv("NOVEL_MODEL", "openai:gpt-4.1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("NOVEL_FALLBACK_MODEL", raising=False)

    settings = resolve_scraper_llm_settings()

    assert settings.model == "openai:gpt-4.1"
    assert settings.fallback_model == "gemini-3.5-flash-lite"
    assert settings.provider == "OpenAI"
    assert settings.fallback_provider == "Unconfigured"


def test_bare_openai_model_uses_openrouter_when_it_is_the_available_provider(monkeypatch):
    monkeypatch.delenv("NOVEL_SCRAPER_MODEL", raising=False)
    monkeypatch.setenv("NOVEL_MODEL", "gpt-4.1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    settings = resolve_scraper_llm_settings()

    assert settings.provider == "OpenRouter"


def test_custom_provider_route_is_reported_as_configured_for_scraper(monkeypatch):
    monkeypatch.setenv("NOVEL_SCRAPER_MODEL", "custom:local-model")
    monkeypatch.setenv("CUSTOM_API_KEY", "custom-test-key")
    monkeypatch.setenv("CUSTOM_API_BASE_URL", "https://custom.example/v1")

    settings = resolve_scraper_llm_settings()

    assert settings.model == "custom:local-model"
    assert settings.provider == "Custom OpenAI-compatible"


def test_scraper_model_route_uses_safe_defaults(monkeypatch):
    monkeypatch.delenv("NOVEL_SCRAPER_MODEL", raising=False)
    monkeypatch.delenv("NOVEL_MODEL", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("NOVEL_FALLBACK_MODEL", raising=False)
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    settings = resolve_scraper_llm_settings()

    assert settings.model == "gemini-3.1-flash-lite"
    assert settings.fallback_model == "gemini-3.5-flash-lite"
    assert settings.provider == "Unconfigured"
    assert settings.fallback_provider == "Unconfigured"
