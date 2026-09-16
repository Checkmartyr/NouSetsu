"""Tests verifying that prompt templates are organized with invariant static prefixes for KV cache hits."""
import pytest
from nousetsu.prompts.templates import (
    CHRONICLER_SYSTEM_PROMPT,
    CRITIQUE_SYSTEM_PROMPT,
    DRAFTING_SYSTEM_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    PATCH_POLISHING_SYSTEM_PROMPT,
    POLISHING_SYSTEM_PROMPT,
)


def test_extraction_prompt_prefix_alignment():
    formatted = EXTRACTION_SYSTEM_PROMPT.format(
        source_lang="Japanese",
        target_lang="English",
        known_characters="- Alice (Original: アリス, Role: lead)",
        known_glossary="- 魔剣 -> Magic Sword",
        skills_section="[Skill: Honorifics]",
        procedural_guidance="[PG Step 1]"
    )
    # Static instructions and schema appear before dynamic characters/glossary
    assert formatted.index("You are a master literary analyst") < formatted.index("Existing Known Characters:")
    assert formatted.index("new_characters") < formatted.index("Existing Known Characters:")
    assert formatted.index("Existing Known Characters:") < formatted.index("Existing Known Glossary:")


def test_drafting_prompt_prefix_alignment():
    formatted = DRAFTING_SYSTEM_PROMPT.format(
        source_lang="Japanese",
        target_lang="English",
        reading_level="YA",
        tense="past",
        pov="third",
        honorific_mode="preserve",
        custom_rules="- Keep Japanese tone",
        skills_section="[Skill: Voice]",
        procedural_guidance="[PG Step 2]",
        rolling_summaries="Previous chapter summary",
        characters="- Bob",
        glossary="- Katana"
    )
    # Directives, style guide, and skills come before dynamic roster and summaries
    assert formatted.index("CRITICAL TRANSLATION DIRECTIVES") < formatted.index("## NARRATIVE CONTEXT:")
    assert formatted.index("[Skill: Voice]") < formatted.index("## ACTIVE CHARACTER ROSTER:")
    assert formatted.index("## NARRATIVE CONTEXT:") < formatted.index("## ACTIVE CHARACTER ROSTER:")


def test_critique_prompt_prefix_alignment():
    formatted = CRITIQUE_SYSTEM_PROMPT.format(
        source_lang="Japanese",
        target_lang="English",
        glossary="- Katana -> Katana",
        characters="- Bob",
        rag_canon_section="[Lore: Royal Guard]",
        skills_section="[Skill: QA]"
    )
    # Evaluation rubric and JSON schema appear before dynamic glossary/characters
    assert formatted.index("EVALUATION CRITERIA") < formatted.index("Active Glossary:")
    assert formatted.index("fidelity_score") < formatted.index("Active Glossary:")
    assert formatted.index("Active Glossary:") < formatted.index("Active Characters:")


def test_polishing_and_patch_prompt_prefix_alignment():
    for template in [POLISHING_SYSTEM_PROMPT, PATCH_POLISHING_SYSTEM_PROMPT]:
        formatted = template.format(
            target_lang="English",
            source_lang="Japanese",
            critique_notes="Smooth rhythm",
            glossary="- Katana -> Katana",
            skills_section="[Skill: Prose]"
        )
        assert formatted.index("elite novelist") < formatted.index("Active Glossary:")
        assert formatted.index("Active Glossary:") < formatted.index("Critique Notes:")


def test_chronicler_prompt_prefix_alignment():
    formatted = CHRONICLER_SYSTEM_PROMPT.format(
        chapter_num=5,
        chapter_title="Battle of Dawn",
        skills_section="[Skill: Lore]",
        provisional_entities_section="[Provisional Entities]",
        rag_context_section="[Prior Lore]"
    )
    assert formatted.index("master lorekeeper") < formatted.index("Chapter Number: 5")
    assert formatted.index("synopsis") < formatted.index("Chapter Title: Battle of Dawn")
    assert formatted.index("master lorekeeper") < formatted.index("[Provisional Entities]")
