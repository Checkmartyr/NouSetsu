"""Fidelity, tone, and terminology critique agent."""
import json
import re
from typing import List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, get_llm
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.metadata import QualityAudit
from nousetsu.prompts.templates import CRITIQUE_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.language import detect_language


class CritiqueAgent:
    """Evaluates draft quality, glossary adherence, and zero-anaphora pronoun resolution."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.llm = get_llm(model_name=model_name, temperature=0.1)

    def evaluate(
        self,
        source_text: str,
        draft_text: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        genre: Optional[str] = None
    ) -> Tuple[QualityAudit, str]:
        chars_str = "\n".join([f"- {c.name} ({c.original_name}, {c.gender}, voice: {c.voice})" for c in active_characters]) or "None"
        gloss_str = "\n".join([f"- {g.source} -> {g.target}" for g in active_glossary]) or "None"

        resolved_genre = genre or getattr(bible, "genre", "general")
        skills_text = SkillRegistry.get_instance().build_prompt_section(
            agent="critic",
            source_lang=bible.source_language,
            genre=resolved_genre
        )
        skills_section = f"\n{skills_text}\n" if skills_text else ""

        sys_msg = CRITIQUE_SYSTEM_PROMPT.format(
            source_lang=bible.source_language,
            target_lang=bible.target_language,
            characters=chars_str,
            glossary=gloss_str,
            skills_section=skills_section
        )

        user_content = (
            f"### Original Source Text ({bible.source_language}):\n{source_text[:50000]}\n\n"
            f"### Draft Translation ({bible.target_language}):\n{draft_text[:50000]}"
        )

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_content)
        ])

        raw_content = extract_text_from_message(response.content)
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content)
        content_to_parse = json_match.group(1) if json_match else raw_content

        audit = QualityAudit()
        critique_notes = ""

        try:
            parsed = json.loads(content_to_parse)
            audit.fidelity_score = float(parsed.get("fidelity_score", 9.0))
            audit.style_score = float(parsed.get("style_score", 9.0))
            audit.glossary_compliance_pct = float(parsed.get("glossary_compliance_pct", 100.0))
            audit.warnings = parsed.get("warnings", [])
            audit.passed = (audit.fidelity_score >= 7.5 and audit.style_score >= 7.5)
            critique_notes = str(parsed.get("critique_notes", ""))
        except Exception:
            audit.warnings.append("Critique JSON could not be parsed; default scores assigned.")
            critique_notes = "Review prose for rhythm and verify all proper nouns."

        # Quick programmatic check of active glossary terms in draft
        missing_terms = []
        for item in active_glossary:
            if item.target.lower() not in draft_text.lower():
                missing_terms.append(f"Glossary term '{item.target}' (source: '{item.source}') missing in draft")
        if missing_terms:
            audit.warnings.extend(missing_terms)
            if len(active_glossary) > 0:
                audit.glossary_compliance_pct = max(0.0, 100.0 - (len(missing_terms) / len(active_glossary) * 100.0))

        # Programmatic Target Language Guard:
        # If draft_text reverted to source language while target_language is distinct, fail audit immediately
        if bible.target_language.lower() != bible.source_language.lower():
            detected_lang = detect_language(draft_text)
            if detected_lang and detected_lang.lower() == bible.source_language.lower():
                audit.fidelity_score = 1.0
                audit.style_score = 1.0
                audit.passed = False
                audit.warnings.insert(
                    0,
                    f"CRITICAL LANGUAGE REGRESSION: Text was generated in source language ({bible.source_language}) instead of target language ({bible.target_language})!"
                )
                critique_notes = (
                    f"CRITICAL REJECTION: The text is written in {bible.source_language} instead of {bible.target_language}. "
                    f"You MUST produce the translation and polished text strictly in {bible.target_language}."
                )

        return audit, critique_notes
