"""Context-aware novelistic translation drafter agent."""
from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, get_llm
from nousetsu.models.bible import CharacterProfile, ChapterSummary, GlossaryItem, NovelBible
from nousetsu.prompts.templates import DRAFTING_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry


class ContextAwareDrafterAgent:
    """Produces initial novelistic translation draft with character voice and zero-anaphora context."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.llm = get_llm(model_name=model_name, temperature=0.3)

    def draft(
        self,
        source_text: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        rolling_summaries: List[ChapterSummary],
        genre: Optional[str] = None
    ) -> str:
        chars_str = "\n".join([
            f"- {c.name} (Original: {c.original_name}, Gender: {c.gender}, Role: {c.role}): Voice={c.voice}"
            for c in active_characters
        ]) or "No explicit character cards registered."

        gloss_str = "\n".join([
            f"- '{g.source}' MUST be translated as '{g.target}' ({g.category})"
            for g in active_glossary
        ]) or "No specific glossary terms."

        summaries_str = "\n".join([
            f"Chapter {s.chapter_num} ({s.title}): {s.synopsis}"
            for s in rolling_summaries[-3:]
        ]) or "This is the first chapter."

        custom_rules_str = "\n".join([f"   - {r}" for r in bible.style_guide.custom_rules])

        resolved_genre = genre or getattr(bible, "genre", "general")
        skills_text = SkillRegistry.get_instance().build_prompt_section(
            agent="drafter",
            source_lang=bible.source_language,
            genre=resolved_genre
        )
        skills_section = f"\n{skills_text}\n" if skills_text else ""

        sys_msg = DRAFTING_SYSTEM_PROMPT.format(
            source_lang=bible.source_language,
            target_lang=bible.target_language,
            reading_level=bible.style_guide.target_reading_level,
            tense=bible.style_guide.tense,
            pov=bible.style_guide.pov,
            honorific_mode=bible.style_guide.honorific_mode,
            custom_rules=custom_rules_str,
            rolling_summaries=summaries_str,
            characters=chars_str,
            glossary=gloss_str,
            skills_section=skills_section
        )

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=f"Original Text to Translate:\n\n{source_text}")
        ])

        return extract_text_from_message(response.content)
