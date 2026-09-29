"""Tests for provider model catalog parsing and error handling."""

import json
from http.client import HTTPMessage
from io import BytesIO
from urllib.error import HTTPError

import pytest

from nousetsu.utils.model_catalog import fetch_model_catalog


def mock_response(monkeypatch, payload):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return BytesIO(body)

    monkeypatch.setattr("nousetsu.utils.model_catalog.urllib.request.urlopen", fake_urlopen)
    return requests


def test_gemini_catalog_filters_generation_models_and_strips_prefix(monkeypatch):
    requests = mock_response(
        monkeypatch,
        {
            "models": [
                {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-embedding", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
            ]
        },
    )

    assert fetch_model_catalog("gemini", "secret-key") == [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ]
    request, timeout = requests[0]
    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/models"
    assert request.get_header("X-goog-api-key") == "secret-key"
    assert timeout == 10


def test_gemini_catalog_follows_page_tokens(monkeypatch):
    calls = []
    pages = {
        "https://generativelanguage.googleapis.com/v1beta/models": {
            "models": [
                {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}
            ],
            "nextPageToken": "next-page",
        },
        "https://generativelanguage.googleapis.com/v1beta/models?pageToken=next-page": {
            "models": [
                {"name": "models/gemini-3.1-pro", "supportedGenerationMethods": ["generateContent"]}
            ]
        },
    }

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return BytesIO(json.dumps(pages[request.full_url]).encode())

    monkeypatch.setattr("nousetsu.utils.model_catalog.urllib.request.urlopen", fake_urlopen)

    assert fetch_model_catalog("gemini", "secret-key") == [
        "gemini-2.5-flash",
        "gemini-3.1-pro",
    ]
    assert calls == list(pages)


def test_openai_catalog_filters_chat_and_reasoning_families(monkeypatch):
    mock_response(
        monkeypatch,
        {
            "data": [
                {"id": "gpt-4o"},
                {"id": "o1-mini"},
                {"id": "o3"},
                {"id": "o4-mini"},
                {"id": "chatgpt-4o-latest"},
                {"id": "text-embedding-3-large"},
                {"id": "whisper-1"},
            ]
        },
    )

    assert fetch_model_catalog("openai", "secret-key") == [
        "chatgpt-4o-latest",
        "gpt-4o",
        "o1-mini",
        "o3",
        "o4-mini",
    ]


def test_custom_catalog_uses_openai_compatible_models_endpoint(monkeypatch):
    requests = mock_response(
        monkeypatch,
        {"data": [{"id": "custom-chat-v1"}, {"id": "local-model"}]},
    )

    models = fetch_model_catalog(
        "custom", "custom-secret", base_url="https://custom.example/v1/"
    )

    assert models == ["custom-chat-v1", "local-model"]
    request, timeout = requests[0]
    assert request.full_url == "https://custom.example/v1/models"
    assert request.get_header("Authorization") == "Bearer custom-secret"
    assert timeout == 10


def test_custom_catalog_requires_http_base_url():
    with pytest.raises(ValueError, match="Valid custom API base URL is required"):
        fetch_model_catalog("custom", "custom-secret", base_url="file:///tmp/v1")


def test_openrouter_catalog_requires_text_input_and_output(monkeypatch):
    mock_response(
        monkeypatch,
        {
            "data": [
                {
                    "id": "anthropic/claude-sonnet",
                    "architecture": {
                        "input_modalities": ["text", "image"],
                        "output_modalities": ["text"],
                    },
                },
                {"id": "openai/gpt-4o", "architecture": {"modality": "text->text"}},
                {"id": "google/gemini-image", "architecture": {"modality": "text->image"}},
                {"id": "audio/model", "architecture": {"modality": "audio->text"}},
                {"id": "unknown/model", "architecture": {}},
            ]
        },
    )

    assert fetch_model_catalog("openrouter", "secret-key") == [
        "anthropic/claude-sonnet",
        "openai/gpt-4o",
    ]


def test_unsupported_provider_is_rejected_without_request():
    with pytest.raises(ValueError, match="Unsupported model catalog provider") as error:
        fetch_model_catalog("other", "secret-key")
    assert "secret-key" not in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        b"not-json",
        {"unexpected": []},
    ],
)
def test_malformed_response_error_is_sanitized(monkeypatch, response):
    mock_response(monkeypatch, response)

    with pytest.raises(RuntimeError, match="Unable to retrieve model catalog") as error:
        fetch_model_catalog("openai", "secret-key")
    assert "secret-key" not in str(error.value)


def test_provider_error_is_sanitized(monkeypatch):
    def fail_urlopen(request, timeout):
        raise HTTPError(request.full_url, 403, "secret-key rejected", HTTPMessage(), None)

    monkeypatch.setattr("nousetsu.utils.model_catalog.urllib.request.urlopen", fail_urlopen)

    with pytest.raises(RuntimeError, match="Unable to retrieve model catalog") as error:
        fetch_model_catalog("openai", "secret-key")
    assert "secret-key" not in str(error.value)


def test_empty_api_key_is_rejected_before_request(monkeypatch):
    def fail_urlopen(request, timeout):
        pytest.fail("urlopen must not be called without an API key")

    monkeypatch.setattr("nousetsu.utils.model_catalog.urllib.request.urlopen", fail_urlopen)

    with pytest.raises(ValueError, match="API key is required"):
        fetch_model_catalog("gemini", " ")
