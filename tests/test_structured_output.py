"""Unit tests for LangChain Structured Output and Pydantic schemas across pipeline agents."""
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.agents.llm import FallbackChatModel, MockNovelLLM, invoke_structured
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.schemas import (
    ChroniclerArcUpdate,
    ChroniclerResult,
    CritiqueResult,
    ExtractorResult,
)


def test_invoke_structured_extractor():
    """Verify invoke_structured correctly parses ExtractorResult."""
    mock = MockNovelLLM(responses=[
        '```json\n{\n  "new_characters": [{"name": "Celia", "original_name": "セリア", "role": "supporting", "voice": "gentle"}],\n  "new_terms": [{"source": "聖剣", "target": "Holy Sword", "category": "item"}],\n  "active_terms_in_chapter": ["聖剣"]\n}\n```'
    ])

    parsed, raw_msg, err = invoke_structured(
        mock,
        ExtractorResult,
        [SystemMessage(content="Extract"), HumanMessage(content="Text")]
    )

    assert err is None
    assert isinstance(parsed, ExtractorResult)
    assert len(parsed.new_characters) == 1
    assert parsed.new_characters[0].name == "Celia"
    assert len(parsed.new_terms) == 1
    assert parsed.new_terms[0].target == "Holy Sword"
    assert parsed.active_terms_in_chapter == ["聖剣"]
    assert raw_msg.usage_metadata is not None


def test_invoke_structured_critic():
    """Verify invoke_structured correctly parses CritiqueResult."""
    mock = MockNovelLLM(responses=[
        '{\n  "fidelity_score": 8.7,\n  "style_score": 8.4,\n  "glossary_compliance_pct": 98.5,\n  "warnings": ["Minor cadence stiffness in paragraph 2."],\n  "critique_notes": "### 1. Executive Assessment:\\nStrong prose."\n}'
    ])

    parsed, raw_msg, err = invoke_structured(
        mock,
        CritiqueResult,
        [SystemMessage(content="Audit"), HumanMessage(content="Draft")]
    )

    assert err is None
    assert isinstance(parsed, CritiqueResult)
    assert parsed.fidelity_score == 8.7
    assert parsed.style_score == 8.4
    assert parsed.glossary_compliance_pct == 98.5
    assert len(parsed.warnings) == 1
    assert "Strong prose" in parsed.critique_notes

    audit = parsed.to_quality_audit()
    assert audit.fidelity_score == 8.7
    assert audit.style_score == 8.4
    assert audit.passed is True


def test_invoke_structured_chronicler_flat_and_nested():
    """Verify ChroniclerResult handles both flat and nested JSON structures."""
    # Flat structure
    flat_json = (
        '{\n'
        '  "chapter_num": 5,\n'
        '  "title": "The Awakening",\n'
        '  "synopsis": "The hero awakens from a 100-year slumber.",\n'
        '  "key_events": ["Awakening ritual completed", "Ancient seal broken"],\n'
        '  "character_state_changes": ["Hero recovered divine consciousness"],\n'
        '  "arc_update": {\n'
        '    "title": "Rebirth Arc",\n'
        '    "core_conflict": "Reclaim lost memories",\n'
        '    "synopsis": "Hero reclaims initial memories",\n'
        '    "milestones": ["Awakened"],\n'
        '    "is_completed": false\n'
        '  },\n'
        '  "story_update": "The ancient hero returns to the mortal realm."\n'
        '}'
    )

    mock1 = MockNovelLLM(responses=[flat_json])
    parsed1, _, err1 = invoke_structured(
        mock1,
        ChroniclerResult,
        [SystemMessage(content="Summarize"), HumanMessage(content="Text")]
    )
    assert err1 is None
    assert parsed1 is not None
    summary1 = parsed1.to_chapter_summary(default_chapter_num=5, default_title="The Awakening", folder="Vol_01")
    assert summary1.chapter_num == 5
    assert summary1.title == "The Awakening"
    assert summary1.folder == "Vol_01"
    assert summary1.arc_update["title"] == "Rebirth Arc"
    assert summary1.story_update == "The ancient hero returns to the mortal realm."

    # Nested structure
    nested_json = (
        '{\n'
        '  "chapter_summary": {\n'
        '    "chapter_num": 6,\n'
        '    "title": "First Steps",\n'
        '    "synopsis": "Exploring the ruins.",\n'
        '    "key_events": ["Found ancient map"],\n'
        '    "character_state_changes": []\n'
        '  },\n'
        '  "arc_update": {\n'
        '    "title": "Rebirth Arc",\n'
        '    "core_conflict": "Reclaim lost memories",\n'
        '    "synopsis": "Exploring ruins",\n'
        '    "milestones": ["Map found"],\n'
        '    "is_completed": false\n'
        '  }\n'
        '}'
    )

    mock2 = MockNovelLLM(responses=[nested_json])
    parsed2, _, err2 = invoke_structured(
        mock2,
        ChroniclerResult,
        [SystemMessage(content="Summarize"), HumanMessage(content="Text")]
    )
    assert err2 is None
    assert parsed2 is not None
    summary2 = parsed2.to_chapter_summary(default_chapter_num=6, default_title="First Steps")
    assert summary2.chapter_num == 6
    assert summary2.title == "First Steps"
    assert summary2.synopsis == "Exploring the ruins."
    assert summary2.arc_update["title"] == "Rebirth Arc"


def test_fallback_chat_model_structured_failover():
    """Verify FallbackChatModel seamlessly falls back to secondary model on structured call failure."""
    class FailingModel(MockNovelLLM):
        def with_structured_output(self, schema, include_raw=False, **kwargs):
            from langchain_core.runnables import RunnableLambda
            def _fail(inp):
                raise RuntimeError("Primary 429 Quota Hit!")
            return RunnableLambda(_fail)

    primary_mock = FailingModel(model_name="primary-model")

    fallback_mock = MockNovelLLM(model_name="fallback-model", responses=[
        '{"fidelity_score": 9.0, "style_score": 8.8, "glossary_compliance_pct": 100.0, "warnings": [], "critique_notes": "Polished and faithful."}'
    ])

    fallback_events = []
    def on_fb(model_name, exc):
        fallback_events.append((model_name, str(exc)))

    fb_model = FallbackChatModel(
        primary=primary_mock,
        fallback=fallback_mock,
        primary_model_name="primary-model",
        fallback_model_name="fallback-model",
        on_fallback=on_fb
    )

    parsed, raw_msg, err = invoke_structured(
        fb_model,
        CritiqueResult,
        [HumanMessage(content="Test audit")]
    )

    assert err is None
    assert parsed is not None
    assert parsed.fidelity_score == 9.0
    assert fb_model.last_model_used == "fallback-model"
    assert len(fallback_events) == 1
    assert fallback_events[0][0] == "fallback-model"
    assert "Primary 429 Quota Hit!" in fallback_events[0][1]


def test_invoke_structured_magic_mock_backward_compatibility():
    """Verify standard MagicMock objects mocking only .invoke() are supported without errors."""
    mock_llm = MagicMock()
    # Mock only .invoke returning an AIMessage with JSON text
    mock_llm.invoke.return_value = AIMessage(
        content='{"new_characters": [], "new_terms": [], "active_terms_in_chapter": ["TestTerm"]}',
        usage_metadata={"input_tokens": 10, "output_tokens": 15, "total_tokens": 25}
    )
    # Ensure with_structured_output does not exist or raises
    del mock_llm.with_structured_output

    parsed, raw_msg, err = invoke_structured(
        mock_llm,
        ExtractorResult,
        [HumanMessage(content="Extract")]
    )

    assert err is None
    assert parsed is not None
    assert parsed.active_terms_in_chapter == ["TestTerm"]
    assert raw_msg.usage_metadata["total_tokens"] == 25


def test_invoke_structured_malformed_json_returns_error_safely():
    """Verify that unrecoverable malformed JSON does not crash invoke_structured, returning error for fallback."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Sorry, I am an AI and cannot process this request.")
    del mock_llm.with_structured_output

    parsed, raw_msg, err = invoke_structured(
        mock_llm,
        CritiqueResult,
        [HumanMessage(content="Evaluate")]
    )

    assert parsed is None
    assert raw_msg.content == "Sorry, I am an AI and cannot process this request."
    assert err is not None
