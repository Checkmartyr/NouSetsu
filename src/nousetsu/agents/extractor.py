"""Entity and terminology extraction agent."""
import json
import re
from typing import List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.metadata import TokenUsage
from nousetsu.prompts.templates import EXTRACTION_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry


class EntityExtractorAgent:
    """Extracts unknown characters and terms from novel chapters."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.llm = get_llm(model_name=model_name, temperature=0.1)
        self.last_usage: TokenUsage = TokenUsage()

    def extract(
        self,
        source_text: str,
        bible: NovelBible,
        genre: Optional[str] = None
    ) -> Tuple[List[CharacterProfile], List[GlossaryItem], List[str]]:
        known_chars_str = "\n".join([f"- {c.original_name} -> {c.name} ({c.role}, {c.voice})" for c in bible.characters]) or "None yet."
        known_gloss_str = "\n".join([f"- {g.source} -> {g.target} ({g.category})" for g in bible.glossary]) or "None yet."

        resolved_genre = genre or getattr(bible, "genre", "general")
        skills_text = SkillRegistry.get_instance().build_prompt_section(
            agent="extractor",
            source_lang=bible.source_language,
            genre=resolved_genre
        )
        skills_section = f"\n{skills_text}\n" if skills_text else ""

        sys_msg = EXTRACTION_SYSTEM_PROMPT.format(
            source_lang=bible.source_language,
            target_lang=bible.target_language,
            known_characters=known_chars_str,
            known_glossary=known_gloss_str,
            skills_section=skills_section
        )

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=f"Chapter Text:\n{source_text[:12000]}")
        ])
        self.last_usage = extract_usage_from_message(response)

        raw_content = extract_text_from_message(response.content)
        # Extract JSON substring if wrapped in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content)
        content_to_parse = json_match.group(1) if json_match else raw_content

        new_chars: List[CharacterProfile] = []
        new_terms: List[GlossaryItem] = []
        active_terms: List[str] = []

        try:
            parsed = json.loads(content_to_parse)
            for c in parsed.get("new_characters", []):
                new_chars.append(CharacterProfile.model_validate(c))
            for t in parsed.get("new_terms", []):
                new_terms.append(GlossaryItem.model_validate(t))
            active_terms = parsed.get("active_terms_in_chapter", [])
        except Exception:
            # Fallback if json parsing fails
            pass

        return new_chars, new_terms, active_terms
