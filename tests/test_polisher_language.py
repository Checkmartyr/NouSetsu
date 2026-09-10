"""Unit tests for PolishingAgent language retention and anti-regression guards."""
from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import NovelBible
from nousetsu.models.metadata import PipelineStage, QualityAudit
from nousetsu.models.state import TranslationState
from nousetsu.prompts.templates import CRITIQUE_SYSTEM_PROMPT, POLISHING_SYSTEM_PROMPT
from nousetsu.utils.language import detect_language


def test_polishing_prompt_target_language_directive():
    """Verify POLISHING_SYSTEM_PROMPT formats target_lang and includes strict directives."""
    formatted = POLISHING_SYSTEM_PROMPT.format(
        target_lang="Thai",
        source_lang="English",
        critique_notes="Make it smoother",
        glossary="None",
        skills_section=""
    )
    assert "Thai" in formatted
    assert "English" in formatted
    assert "CRITICAL LANGUAGE DIRECTIVES" in formatted
    assert "DO NOT translate the chapter back to English" in formatted


def test_polisher_language_regression_fallback():
    """Verify PolishingAgent rejects English reversion when target language is Thai."""
    polisher = PolishingAgent(model_name="mock-model")
    
    # Mock LLM returning English text (language regression)
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="This is an English rewrite that accidentally reverted from Thai."
    )
    polisher.llm = mock_llm

    thai_draft = "บทที่ 2 - เล่นพิเรนทร์! อิเฟียรู้สึกทันทีว่าหูของเธอต้องมีอะไรผิดปกติแน่ๆ"
    bible = NovelBible(source_language="English", target_language="Thai")

    result = polisher.polish(
        draft_text=thai_draft,
        critique_notes="Polish rhythm",
        active_glossary=[],
        bible=bible
    )

    # Must reject the English reversion and fall back to the valid Thai draft!
    assert result == thai_draft
    assert detect_language(result) == "Thai"


def test_polisher_accepts_valid_target_language():
    """Verify PolishingAgent accepts valid polished text in target language."""
    polisher = PolishingAgent(model_name="mock-model")
    
    polished_thai = "บทที่ 2 - เล่นพิเรนทร์! อิเฟียสัมผัสได้ถึงความผิดปกติในทันทีอย่างชัดเจน"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=polished_thai)
    polisher.llm = mock_llm

    thai_draft = "บทที่ 2 - เล่นพิเรนทร์! อิเฟียรู้สึกทันทีว่าหูของเธอต้องมีอะไรผิดปกติแน่ๆ"
    bible = NovelBible(source_language="English", target_language="Thai")

    result = polisher.polish(
        draft_text=thai_draft,
        critique_notes="Polish rhythm",
        active_glossary=[],
        bible=bible
    )

    assert result == polished_thai
    assert detect_language(result) == "Thai"


def test_critic_penalizes_source_language_draft():
    """Verify CritiqueAgent forces failure when draft is in source language instead of target language."""
    critic = CritiqueAgent(model_name="mock-model")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="""```json
{
  "fidelity_score": 10.0,
  "style_score": 9.5,
  "glossary_compliance_pct": 100.0,
  "warnings": [],
  "critique_notes": "Well written in English."
}
```""")
    critic.llm = mock_llm

    english_draft = "Ifia was convinced her senses were betraying her. There was no other explanation."
    bible = NovelBible(source_language="English", target_language="Thai")

    audit, notes = critic.evaluate(
        source_text="Ifia was convinced her senses were betraying her.",
        draft_text=english_draft,
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )

    # Language regression guard should trigger
    assert audit.fidelity_score == 1.0
    assert audit.style_score == 1.0
    assert audit.passed is False
    assert any("CRITICAL LANGUAGE REGRESSION" in w for w in audit.warnings)
    assert "CRITICAL REJECTION" in notes


def test_workflow_route_blocks_on_language_regression():
    """Verify workflow _route_after_critique blocks chronicle when language regression occurred."""
    wf = NovelTranslationWorkflow(max_review_loops=3, quality_threshold=8.5)

    state = TranslationState(
        chapter_id="ch2",
        chapter_num=2,
        source_file="ch2.txt",
        source_sha256="abc",
        output_file="ch2.md",
        source_text="Hello world",
        review_iteration=2,
        polished_text="Polished text",
        quality_audit=QualityAudit(
            fidelity_score=9.5,
            style_score=9.5,
            passed=False,
            warnings=["CRITICAL LANGUAGE REGRESSION: Text was generated in source language!"]
        )
    )

    route = wf._route_after_critique(state)
    # Even though fidelity & style >= 8.5, language regression must force re-polishing / re-eval
    assert route == "polish"


def test_polisher_includes_source_text_as_reference():
    """Verify PolishingAgent includes source text in prompt when provided."""
    polisher = PolishingAgent(model_name="mock-model")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="บทที่ 1: การเดินทางเริ่มต้นขึ้นอย่างสง่างาม"
    )
    polisher.llm = mock_llm

    source = "Chapter 1: The journey begins with resolute steps."
    draft = "บทที่ 1: การเดินทางเริ่มต้นขึ้น"
    bible = NovelBible(source_language="English", target_language="Thai")

    polisher.polish(
        draft_text=draft,
        critique_notes="Enhance elegance",
        active_glossary=[],
        bible=bible,
        source_text=source
    )

    # Verify message sent to LLM contains the source text reference
    invoked_msgs = mock_llm.invoke.call_args[0][0]
    human_msg = invoked_msgs[1].content
    assert "Original Source Text (English - Reference Only)" in human_msg
    assert source in human_msg
    assert draft in human_msg


def test_critic_full_length_comparison():
    """Verify CritiqueAgent passes full chapter (up to 50k chars) without 6k truncation."""
    critic = CritiqueAgent(model_name="mock-model")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="""```json
{
  "fidelity_score": 9.5,
  "style_score": 9.5,
  "glossary_compliance_pct": 100.0,
  "warnings": [],
  "critique_notes": "All good."
}
```""")
    critic.llm = mock_llm

    # Chapter of 15,000 characters
    long_source = "A" * 15000
    long_draft = "ก" * 15000
    bible = NovelBible(source_language="English", target_language="Thai")

    critic.evaluate(
        source_text=long_source,
        draft_text=long_draft,
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )

    invoked_msgs = mock_llm.invoke.call_args[0][0]
    human_msg = invoked_msgs[1].content
    # The full 15,000 chars should be present, not truncated at 6,000!
    assert "A" * 15000 in human_msg
    assert "ก" * 15000 in human_msg

