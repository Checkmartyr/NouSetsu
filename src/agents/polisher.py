"""Literary prose polisher and style editor agent."""
from typing import List
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.llm import extract_text_from_message, get_llm
from src.models.bible import GlossaryItem, NovelBible
from src.prompts.templates import POLISHING_SYSTEM_PROMPT


class PolishingAgent:
    """Refines drafted prose into natural, immersive literary English based on critique notes."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.llm = get_llm(model_name=model_name, temperature=0.3)

    def polish(
        self,
        draft_text: str,
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible
    ) -> str:
        gloss_str = "\n".join([f"- {g.source} -> {g.target}" for g in active_glossary]) or "None"

        sys_msg = POLISHING_SYSTEM_PROMPT.format(
            critique_notes=critique_notes or "Preserve meaning and enhance natural rhythm.",
            glossary=gloss_str
        )

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=f"Draft Translation to Polish:\n\n{draft_text}")
        ])

        text = extract_text_from_message(response.content).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
                text = "\n".join(lines[1:-1]).strip()
        return text
