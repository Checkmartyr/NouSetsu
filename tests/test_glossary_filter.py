"""Unit tests for active glossary filtering in Critic, Drafter, and Polisher."""

from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.models.bible import GlossaryItem, NovelBible, StyleGuide
from nousetsu.utils.glossary_filter import filter_glossary_for_scene, is_term_present


def test_is_term_present_word_boundaries():
    # Word boundary prevents substring false-positives
    assert not is_term_present("Villa", "the villainess absolutely cannot discover us.")
    assert is_term_present("Villa", "they arrived at the private villa.")
    assert is_term_present("Villainess", "the villainess was furious.")
    assert not is_term_present("Fia", "she warned Ifia about the danger.")
    assert is_term_present("Fia", "Fia was preparing the meal.")

    # CJK substring matching works without word boundaries
    assert is_term_present("魔剣", "少年は魔剣を手に入れた。")
    assert is_term_present("ระบบ", "ระบบแจ้งเตือนขึ้นมา")


def test_critic_compliance_not_penalized_by_substring_words():
    critic = CritiqueAgent(model_name="mock-novel-llm")
    bible = NovelBible(
        title="Test Novel",
        source_language="English",
        target_language="Thai",
        style_guide=StyleGuide()
    )

    # Both Villainess and Villa exist in the glossary
    glossary = [
        GlossaryItem(source="Villainess", target="นางร้าย"),
        GlossaryItem(source="Villa", target="วิลล่า"),
    ]

    # Source text only contains "villainess", NOT "Villa"!
    source_text = "The villainess stepped forward with a cold smile."
    draft_text = "นางร้ายก้าวไปข้างหน้าด้วยรอยยิ้มเย็นชา"

    audit, notes = critic.evaluate(
        source_text=source_text,
        draft_text=draft_text,
        bible=bible,
        active_characters=[],
        active_glossary=glossary
    )

    # Since only Villainess appeared and was translated as นางร้าย,
    # compliance must be 100.0%, with ZERO false missing warning for "Villa"!
    assert audit.glossary_compliance_pct == 100.0
    assert not any("วิลล่า" in w for w in audit.warnings)


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


def test_filter_glossary_for_scene_fallback_and_no_fallback():
    glossary = [
        GlossaryItem(source="Sword", target="ดาบ"),
        GlossaryItem(source="Shield", target="โล่"),
    ]
    # No matches
    text = "The sky is blue."
    # With fallback: returns top items
    assert len(filter_glossary_for_scene(glossary, source_text=text, fallback_on_empty=True)) == 2
    # Without fallback: returns empty list
    assert len(filter_glossary_for_scene(glossary, source_text=text, fallback_on_empty=False)) == 0
