"""Unit tests for active glossary filtering in Critic and Polisher."""

from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.models.bible import GlossaryItem, NovelBible, StyleGuide


def test_critic_filters_glossary_to_source_present_terms():
    critic = CritiqueAgent(model_name="mock-novel-llm")
    bible = NovelBible(
        title="Test Novel",
        source_language="Japanese",
        target_language="English",
        style_guide=StyleGuide()
    )

    # 3 glossary terms, but only 1 appears in source_text
    glossary = [
        GlossaryItem(source="魔剣", target="Magic Sword"),
        GlossaryItem(source="勇者", target="Hero"),
        GlossaryItem(source="魔王", target="Demon Lord"),
    ]

    source_text = "少年は魔剣を手に入れた。"  # Only 魔剣 appears
    draft_text = "The boy obtained the Magic Sword."

    audit, notes = critic.evaluate(
        source_text=source_text,
        draft_text=draft_text,
        bible=bible,
        active_characters=[],
        active_glossary=glossary
    )

    # Since 魔剣 appeared in source and Magic Sword appeared in draft,
    # compliance should be 100%, NOT penalized for 勇者 or 魔王!
    assert audit.glossary_compliance_pct == 100.0
    assert not any("missing in draft" in w for w in audit.warnings)


def test_polisher_runs_with_filtered_glossary():
    polisher = PolishingAgent(model_name="mock-novel-llm")
    bible = NovelBible(
        title="Test Novel",
        source_language="Japanese",
        target_language="English",
        style_guide=StyleGuide()
    )

    glossary = [
        GlossaryItem(source="魔剣", target="Magic Sword"),
        GlossaryItem(source="勇者", target="Hero"),
    ]

    source_text = "少年は魔剣を手に入れた。"
    draft_text = "The boy obtained the Magic Sword."

    result = polisher.polish(
        draft_text=draft_text,
        critique_notes="Smooth rhythm",
        active_glossary=glossary,
        bible=bible,
        source_text=source_text
    )

    assert result is not None
    assert len(result) > 0
