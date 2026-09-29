"""Fetch chat-capable model IDs from supported LLM providers."""

import json
import urllib.parse
import urllib.request
from typing import Any

_TIMEOUT_SECONDS = 10
_ENDPOINTS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
    "openai": "https://api.openai.com/v1/models",
    "openrouter": "https://openrouter.ai/api/v1/models",
}


def _text_generation_architecture(architecture: Any) -> bool:
    if not isinstance(architecture, dict):
        return False

    inputs = architecture.get("input_modalities")
    outputs = architecture.get("output_modalities")
    if isinstance(inputs, list) and isinstance(outputs, list):
        return "text" in inputs and "text" in outputs

    modality = architecture.get("modality")
    if isinstance(modality, str):
        input_side, separator, output_side = modality.casefold().partition("->")
        if separator:
            return (
                "text" in input_side.split("+")
                and "text" in output_side.split("+")
            )
    return False


def _custom_models_url(base_url: str | None) -> str:
    if not base_url:
        raise ValueError("Valid custom API base URL is required.")
    parsed = urllib.parse.urlsplit(base_url.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Valid custom API base URL is required.")
    return urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.netloc,
        f"{parsed.path.rstrip('/')}/models",
        "",
        "",
    ))


def _parse_models(provider: str, payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        raise ValueError("Invalid model catalog response.")

    if provider == "gemini":
        entries = payload.get("models")
        if not isinstance(entries, list):
            raise ValueError("Invalid model catalog response.")
        models = {
            entry["name"].removeprefix("models/")
            for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("name"), str)
            and "generateContent" in entry.get("supportedGenerationMethods", [])
        }
    else:
        entries = payload.get("data")
        if not isinstance(entries, list):
            raise ValueError("Invalid model catalog response.")
        if provider == "openai":
            prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt-")
            models = {
                entry["id"]
                for entry in entries
                if isinstance(entry, dict)
                and isinstance(entry.get("id"), str)
                and entry["id"].casefold().startswith(prefixes)
            }
        elif provider == "openrouter":
            models = {
                entry["id"]
                for entry in entries
                if isinstance(entry, dict)
                and isinstance(entry.get("id"), str)
                and _text_generation_architecture(entry.get("architecture"))
            }
        else:
            models = {
                entry["id"]
                for entry in entries
                if isinstance(entry, dict) and isinstance(entry.get("id"), str)
            }

    return sorted(models)


def fetch_model_catalog(
    provider: str, api_key: str, base_url: str | None = None
) -> list[str]:
    """Return unique, sorted chat/generation model IDs for one provider.

    Provider and response errors intentionally omit underlying details so API
    keys and provider response bodies cannot leak through exception messages.
    """
    provider = provider.casefold()
    if provider not in _ENDPOINTS and provider != "custom":
        raise ValueError("Unsupported model catalog provider.")
    if not api_key or not api_key.strip():
        raise ValueError("API key is required.")

    headers = {"Accept": "application/json"}
    if provider == "gemini":
        headers["x-goog-api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    page_url = (
        _custom_models_url(base_url) if provider == "custom" else _ENDPOINTS[provider]
    )
    try:
        models: set[str] = set()
        seen_urls: set[str] = set()
        while page_url and page_url not in seen_urls:
            seen_urls.add(page_url)
            request = urllib.request.Request(page_url, headers=headers)
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
            models.update(_parse_models(provider, payload))

            entries_key = "models" if provider == "gemini" else "data"
            entries = payload[entries_key]
            if provider == "gemini":
                token = payload.get("nextPageToken")
                page_url = (
                    f"{_ENDPOINTS[provider]}?{urllib.parse.urlencode({'pageToken': token})}"
                    if isinstance(token, str) and token
                    else ""
                )
            elif provider == "openai" and payload.get("has_more") is True and entries:
                after = entries[-1].get("id") if isinstance(entries[-1], dict) else None
                page_url = (
                    f"{_ENDPOINTS[provider]}?{urllib.parse.urlencode({'after': after})}"
                    if isinstance(after, str) and after
                    else ""
                )
            else:
                page_url = ""
        return sorted(models)
    except Exception:
        raise RuntimeError("Unable to retrieve model catalog.") from None
