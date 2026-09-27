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


def test_missing_provider_key_keeps_offline_mock(monkeypatch):
    configure_provider_test(monkeypatch)

    assert isinstance(get_llm(model_name="gpt-4o"), MockNovelLLM)
    assert isinstance(get_llm(model_name="anthropic/claude-3.7-sonnet"), MockNovelLLM)


@pytest.mark.parametrize("model_name", ["mock-test-model", "test-model"])
def test_mock_prefixes_do_not_need_provider_keys(monkeypatch, model_name):
    configure_provider_test(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")

    assert isinstance(get_llm(model_name=model_name), MockNovelLLM)
