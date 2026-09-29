"""Tests for model-name-based provider routing."""
import sys
from types import ModuleType
from typing import cast

import pytest

from nousetsu.agents.llm import MockNovelLLM, get_llm


class FakeChatOpenAI:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.instances.append(self)


def configure_provider_test(monkeypatch):
    FakeChatOpenAI.instances.clear()
    for key in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "CUSTOM_API_KEY",
        "CUSTOM_API_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    fake_module = ModuleType("langchain_openai")
    setattr(fake_module, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)


def test_openai_model_uses_openai_even_when_google_key_is_set(monkeypatch):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "google-test-key")

    llm = cast(FakeChatOpenAI, get_llm(model_name="gpt-4o"))

    assert isinstance(llm, FakeChatOpenAI)
    assert llm.kwargs == {
        "model": "gpt-4o",
        "api_key": "openai-test-key",
        "temperature": 1.0,
    }


def test_explicit_openai_prefix_selects_openai(monkeypatch):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")

    llm = cast(FakeChatOpenAI, get_llm(model_name="openai:gpt-4.1-mini"))

    assert isinstance(llm, FakeChatOpenAI)
    assert llm.kwargs["model"] == "gpt-4.1-mini"
    assert llm.kwargs["api_key"] == "openai-test-key"
    assert "base_url" not in llm.kwargs


def test_explicit_openai_does_not_fall_through_to_openrouter(monkeypatch):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-test-key")

    assert isinstance(get_llm(model_name="openai:gpt-4o"), MockNovelLLM)


def test_openrouter_provider_model_id_uses_openrouter(monkeypatch):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "google-test-key")

    llm = cast(FakeChatOpenAI, get_llm(model_name="anthropic/claude-3.7-sonnet"))

    assert isinstance(llm, FakeChatOpenAI)
    assert llm.kwargs == {
        "model": "anthropic/claude-3.7-sonnet",
        "api_key": "router-test-key",
        "temperature": 1.0,
        "base_url": "https://openrouter.ai/api/v1",
    }


def test_openrouter_prefix_and_bare_openai_model(monkeypatch):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-test-key")

    router_model = cast(
        FakeChatOpenAI, get_llm(model_name="openrouter:anthropic/claude-3.7-sonnet")
    )
    assert router_model.kwargs["model"] == "anthropic/claude-3.7-sonnet"

    openai_model = cast(FakeChatOpenAI, get_llm(model_name="gpt-4o"))
    assert openai_model.kwargs["model"] == "openai/gpt-4o"
    assert openai_model.kwargs["base_url"] == "https://openrouter.ai/api/v1"


@pytest.mark.parametrize(
    ("route", "key", "expected_model"),
    [
        ("openai:o1", "OPENAI_API_KEY", "o1"),
        ("openai:o3-mini", "OPENAI_API_KEY", "o3-mini"),
        ("openai:o4-mini", "OPENAI_API_KEY", "o4-mini"),
        ("openrouter:openai/o3-mini", "OPENROUTER_API_KEY", "openai/o3-mini"),
        ("custom:o3-mini", "CUSTOM_API_KEY", "o3-mini"),
    ],
)
def test_openai_reasoning_models_omit_temperature(monkeypatch, route, key, expected_model):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv(key, "provider-test-key")
    if route.startswith("custom:"):
        monkeypatch.setenv("CUSTOM_API_BASE_URL", "https://custom.example/v1")

    llm = cast(FakeChatOpenAI, get_llm(model_name=route, temperature=0.35))

    assert llm.kwargs["model"] == expected_model
    assert "temperature" not in llm.kwargs


def test_custom_provider_uses_its_model_key_and_base_url(monkeypatch):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("CUSTOM_API_KEY", "custom-test-key")
    monkeypatch.setenv("CUSTOM_API_BASE_URL", "https://custom.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")

    llm = cast(FakeChatOpenAI, get_llm(model_name="custom:my-model"))

    assert llm.kwargs == {
        "model": "my-model",
        "api_key": "custom-test-key",
        "temperature": 1.0,
        "base_url": "https://custom.example/v1",
    }


@pytest.mark.parametrize(
    ("api_key", "base_url"),
    [("custom-test-key", ""), ("", "https://custom.example/v1")],
)
def test_custom_route_without_key_or_base_url_stays_offline_mock(monkeypatch, api_key, base_url):
    configure_provider_test(monkeypatch)
    if api_key:
        monkeypatch.setenv("CUSTOM_API_KEY", api_key)
    if base_url:
        monkeypatch.setenv("CUSTOM_API_BASE_URL", base_url)

    assert isinstance(get_llm(model_name="custom:my-model"), MockNovelLLM)


def test_non_openai_model_with_reasoning_like_name_keeps_temperature(monkeypatch):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-test-key")

    llm = cast(
        FakeChatOpenAI,
        get_llm(model_name="openrouter:anthropic/o3-mini", temperature=0.35),
    )

    assert llm.kwargs["temperature"] == 0.35


def test_missing_provider_key_keeps_offline_mock(monkeypatch):
    configure_provider_test(monkeypatch)

    assert isinstance(get_llm(model_name="gpt-4o"), MockNovelLLM)
    assert isinstance(get_llm(model_name="anthropic/claude-3.7-sonnet"), MockNovelLLM)


@pytest.mark.parametrize("model_name", ["mock-test-model", "test-model"])
def test_mock_prefixes_do_not_need_provider_keys(monkeypatch, model_name):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")

    assert isinstance(get_llm(model_name=model_name), MockNovelLLM)
