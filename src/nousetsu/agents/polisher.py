"""Literary prose polisher and style editor agent."""
from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, get_llm
from nousetsu.models.bible import GlossaryItem, NovelBible
from nousetsu.prompts.templates import POLISHING_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.language import detect_language


class PolishingAgent:
    """Refines drafted prose into natural, immersive literary target-language fiction based on critique notes."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.llm = get_llm(model_name=model_name, temperature=0.3)

    def polish(
        self,
        draft_text: str,
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible,
        genre: Optional[str] = None
    ) -> str:
        gloss_str = "\n".join([f"- {g.source} -> {g.target}" for g in active_glossary]) or "None"

        resolved_genre = genre or getattr(bible, "genre", "general")
        skills_text = SkillRegistry.get_instance().build_prompt_section(
            agent="polisher",
            source_lang=bible.source_language,
            genre=resolved_genre
        )
        skills_section = f"\n{skills_text}\n" if skills_text else ""

        sys_msg = POLISHING_SYSTEM_PROMPT.format(
            target_lang=bible.target_language,
            source_lang=bible.source_language,
            critique_notes=critique_notes or "Preserve meaning and enhance natural rhythm.",
            glossary=gloss_str,
            skills_section=skills_section
        )

        user_content = (
            f"Draft Translation in {bible.target_language} to Polish "
            f"(CRITICAL: Output MUST remain 100% in {bible.target_language}, DO NOT translate back to {bible.source_language}):\n\n"
            f"{draft_text}"
        )

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_content)
        ])

        text = extract_text_from_message(response.content).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
                text = "\n".join(lines[1:-1]).strip()

        # Programmatic Language Regression Guard:
        # If output reverted to source language while draft was in target language (or different), reject regression
        if bible.target_language.lower() != bible.source_language.lower():
            detected_polished = detect_language(text)
            if detected_polished and detected_polished.lower() == bible.source_language.lower():
                # Reverted to source language! Fall back to draft_text to preserve target language translation
                return draft_text

        return text
