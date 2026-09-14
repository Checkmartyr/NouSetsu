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


def test_gemini_interactions_thinking_config_generation():
    mock_client = MagicMock(spec=GeminiInteractionsClient)
    mock_result = InteractionResult(
        id="v1_test_think",
        model="gemini-3.5-flash-lite",
        output_text="Result text",
        usage=TokenUsage(input_tokens=10, output_tokens=10, thought_tokens=50, total_tokens=70)
    )
    mock_client.create.return_value = mock_result

    # 1. Test default reasoning model gets medium thinking_level in generation_config
    chat_model = GeminiInteractionsChatModel(
        model_name="gemini-3.5-flash-lite",
        temperature=0.3,
        client=mock_client
    )
    chat_model.invoke([HumanMessage(content="Hello")])
    call_kwargs = mock_client.create.call_args.kwargs
    gen_cfg = call_kwargs["generation_config"]
    assert gen_cfg["temperature"] == 0.3
    assert gen_cfg["thinking_level"] == "medium"
    assert "thinking_config" not in gen_cfg

    # 2. Test explicit thinking_level
    chat_model2 = GeminiInteractionsChatModel(
        model_name="gemini-3.5-flash-lite",
        thinking_level="high",
        client=mock_client
    )
    chat_model2.invoke([HumanMessage(content="Hello")])
    gen_cfg2 = mock_client.create.call_args.kwargs["generation_config"]
    assert gen_cfg2["thinking_level"] == "high"

    # 3. Test disabling thinking maps to 'minimal'
    chat_model3 = GeminiInteractionsChatModel(
        model_name="gemini-3.5-flash-lite",
        thinking_level="off",
        client=mock_client
    )
    chat_model3.invoke([HumanMessage(content="Hello")])
    gen_cfg3 = mock_client.create.call_args.kwargs["generation_config"]
    assert gen_cfg3["thinking_level"] == "minimal"


def test_extract_usage_with_token_details():
    msg = AIMessage(
        content="Testing details",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "output_token_details": {"reasoning": 35},
            "input_token_details": {"cache_read": 20},
        }
    )
    usage = extract_usage_from_message(msg)
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.thought_tokens == 35
    assert usage.cached_tokens == 20
    assert usage.total_tokens == 150


def test_critic_agent_thinking_defaults(monkeypatch):
    from nousetsu.agents.critic import CritiqueAgent

    created_llms = []
    def fake_get_llm(**kwargs):
        created_llms.append(kwargs)
        mock_llm = MagicMock()
        mock_llm.last_model_used = kwargs.get("model_name")
        return mock_llm

    monkeypatch.setattr("nousetsu.agents.critic.get_llm", fake_get_llm)
    monkeypatch.delenv("NOVEL_CRITIC_THINKING_LEVEL", raising=False)
    monkeypatch.delenv("NOVEL_THINKING_LEVEL", raising=False)

    # Default should be "medium"
    _ = CritiqueAgent(model_name="gemini-3.5-flash-lite")
    assert created_llms[-1]["thinking_level"] == "medium"

    # Environment override
    monkeypatch.setenv("NOVEL_CRITIC_THINKING_LEVEL", "high")
    _ = CritiqueAgent(model_name="gemini-3.5-flash-lite")
    assert created_llms[-1]["thinking_level"] == "high"


def test_rest_create_interaction_sanitizes_generation_config():
    client = GeminiInteractionsClient(api_key="test-key")
    mock_http = MagicMock()
    mock_http.is_closed = False
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "v1_rest_test",
        "model": "gemini-3.5-flash-lite",
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": "OK"}]}],
        "usage": {"total_tokens": 10}
    }
    mock_http.post.return_value = mock_resp
    client._http_client = mock_http

    # Pass messy generation_config with invalid keys like thinking_config and thinking_budget
    res = client._rest_create_interaction(
        model="gemini-3.5-flash-lite",
        input_data="Hello",
        generation_config={
            "temperature": 0.7,
            "thinking_level": "medium",
            "thinking_config": {"thinking_level": "MEDIUM"},
            "thinking_budget": 1024,
            "invalid_extra_param": True
        }
    )

    assert res.output_text == "OK"
    posted_payload = mock_http.post.call_args.kwargs["json"]
    gen_cfg = posted_payload["generation_config"]
    assert gen_cfg["temperature"] == 0.7
    assert gen_cfg["thinking_level"] == "medium"
    assert "thinking_config" not in gen_cfg
    assert "thinking_budget" not in gen_cfg
    assert "invalid_extra_param" not in gen_cfg

