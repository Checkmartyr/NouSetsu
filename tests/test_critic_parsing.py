"""Unit tests for robust JSON and regex parsing in CritiqueAgent (Zensor)."""
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.models.bible import NovelBible


def test_critic_parses_multiline_critique_notes_with_unescaped_newlines():
    """Verify that unescaped literal newlines in critique_notes string are parsed cleanly via strict=False."""
    agent = CritiqueAgent(model_name="mock-model")
    bible = NovelBible(source_language="English", target_language="Thai")

    raw_llm_json = (
        '```json\n'
        '{\n'
        '  "fidelity_score": 8.5,\n'
        '  "style_score": 8.0,\n'
        '  "glossary_compliance_pct": 100.0,\n'
        '  "warnings": [],\n'
        '  "critique_notes": "### 1. Executive Assessment:\n'
        "The translation is faithful, capturing Ifia's playful/clingy nature and Amelia's intensity.\n\n"
        '### 2. Line-Level & Phrasing Critiques:\n'
        '- Line/Excerpt: \\"เฟียทั้งดูไร้เดียงสา\\"\n'
        '  * Issue: Clunky phrasing.\n'
        '  * Recommendation: Revise to: \\"ขับเน้นให้เธองดงาม\\".\n\n'
        '### 3. Rhythm, Tone & Cadence Directives:\n'
        '- Ensure inner monologues maintain comedic panic."\n'
        '}\n'
        '```'
    )

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=raw_llm_json)
    mock_llm.last_model_used = "mock-model"
    agent.llm = mock_llm

    audit, notes = agent.evaluate(
        source_text="Source chapter text.",
        draft_text="บทที่ 1: การเดินทางเริ่มต้นขึ้นแล้ว ท้องฟ้าแจ่มใส",
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )

    assert audit.fidelity_score == 8.5
    assert audit.style_score == 8.0
    assert "### 1. Executive Assessment:" in notes
    assert "Ifia's playful/clingy nature" in notes
    assert "### 2. Line-Level & Phrasing Critiques:" in notes
    assert "### 3. Rhythm, Tone & Cadence Directives:" in notes
    assert "Ensure inner monologues maintain comedic panic." in notes


def test_critic_regex_fallback_preserves_multiline_with_apostrophes():
    """Verify that even when raw JSON syntax is broken, regex fallback does not terminate on apostrophes like Ifia's."""
    agent = CritiqueAgent(model_name="mock-model")
    bible = NovelBible(source_language="English", target_language="Thai")

    # Broken JSON (missing quotes or invalid syntax) that forces regex recovery
    raw_broken_output = (
        'fidelity_score: 8.2\n'
        'style_score: 7.9\n'
        'critique_notes: "### 1. Executive Assessment:\n'
        "The voice of Ifia's character and Amelia's possessive gaze need sharper contrast.\n"
        '### 2. Line-Level:\n'
        '- Quote: \\"Don\'t go alone!\\"\n'
        '### 3. Cadence:\n'
        'Vary sentence lengths."\n'
        '}\n'
    )

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=raw_broken_output)
    mock_llm.last_model_used = "mock-model"
    agent.llm = mock_llm

    audit, notes = agent.evaluate(
        source_text="Source chapter text.",
        draft_text="บทที่ 1: การเดินทางเริ่มต้นขึ้นแล้ว ท้องฟ้าแจ่มใส",
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )

    assert audit.fidelity_score == 8.2
    assert audit.style_score == 7.9
    assert "Ifia's character" in notes
    assert "Amelia's possessive gaze" in notes
    assert "Vary sentence lengths." in notes
