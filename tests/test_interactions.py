"""Unit tests for Gemini Interactions API client and chat model adapter."""
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from nousetsu.agents.interactions import (
    GeminiInteractionsChatModel,
    GeminiInteractionsClient,
    InteractionResult,
)
from nousetsu.agents.llm import extract_usage_from_message, get_llm
from nousetsu.models.metadata import TokenUsage


def test_parse_usage_payload_from_dict():
    client = GeminiInteractionsClient(api_key="test-key")

    raw_usage = {
        "total_input_tokens": 120,
        "total_output_tokens": 85,
        "total_thought_tokens": 40,
        "total_cached_tokens": 15,
        "total_tokens": 260
    }
    usage = client._parse_usage_payload(raw_usage)
    assert usage.input_tokens == 120
    assert usage.output_tokens == 85
    assert usage.thought_tokens == 40
    assert usage.cached_tokens == 15
    assert usage.total_tokens == 260


def test_parse_usage_payload_from_object():
    client = GeminiInteractionsClient(api_key="test-key")

    mock_obj = MagicMock()
    mock_obj.total_input_tokens = 50
    mock_obj.total_output_tokens = 100
    mock_obj.total_thought_tokens = 25
    mock_obj.total_cached_tokens = 0
    mock_obj.total_tokens = 175

    usage = client._parse_usage_payload(mock_obj)
    assert usage.input_tokens == 50
    assert usage.output_tokens == 100
    assert usage.thought_tokens == 25
    assert usage.cached_tokens == 0
    assert usage.total_tokens == 175


def test_extract_text_from_steps():
    client = GeminiInteractionsClient(api_key="test-key")

    steps = [
        {
            "type": "model_output",
            "content": [
                {"type": "text", "text": "Translated prose part 1.\n"},
                {"type": "text", "text": "Translated prose part 2."}
            ]
        }
    ]
    text = client._extract_text_from_steps(steps)
    assert "Translated prose part 1." in text
    assert "Translated prose part 2." in text


def test_gemini_interactions_chat_model_generate():
    mock_client = MagicMock(spec=GeminiInteractionsClient)
    mock_result = InteractionResult(
        id="v1_test123",
        model="gemini-2.5-pro",
        output_text="# Translated Chapter\n\nThe hero walked forward.",
        usage=TokenUsage(
            input_tokens=150,
            output_tokens=75,
            thought_tokens=20,
            cached_tokens=10,
            total_tokens=255
        )
    )
    mock_client.create.return_value = mock_result

    chat_model = GeminiInteractionsChatModel(
        model_name="gemini-2.5-pro",
        api_key="fake-key",
        client=mock_client
    )

    messages = [
        SystemMessage(content="You are an expert novel translator."),
        HumanMessage(content="Original Text: 第一章")
    ]

    result = chat_model.invoke(messages)
    assert isinstance(result, AIMessage)
    assert "# Translated Chapter" in result.content
    assert result.usage_metadata is not None
    assert result.usage_metadata["input_tokens"] == 150
    assert result.usage_metadata["output_tokens"] == 75
    assert result.usage_metadata["total_tokens"] == 255
    assert result.response_metadata["interaction_id"] == "v1_test123"

    usage = extract_usage_from_message(result)
    assert usage.input_tokens == 150
    assert usage.output_tokens == 75
    assert usage.thought_tokens == 20
    assert usage.cached_tokens == 10
    assert usage.total_tokens == 255


def test_get_llm_interactions_factory(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-gemini-key")
    monkeypatch.setenv("NOVEL_USE_INTERACTIONS", "1")

    llm = get_llm(model_name="gemini-2.5-pro")
    assert isinstance(llm, GeminiInteractionsChatModel)
    assert llm._llm_type == "gemini_interactions"


def test_get_llm_opt_out_interactions(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-gemini-key")
    monkeypatch.setenv("NOVEL_USE_INTERACTIONS", "0")

    llm = get_llm(model_name="gemini-2.5-pro")
    # When opted out of interactions, returns ChatGoogleGenerativeAI or fallback
    assert not isinstance(llm, GeminiInteractionsChatModel)
