"""Literary prose polisher and style editor agent."""
from typing import Any, Callable, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.models.bible import GlossaryItem, NovelBible
from nousetsu.models.metadata import TokenUsage
from nousetsu.prompts.templates import POLISHING_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.language import detect_language


class PolishingAgent:
    """Refines drafted prose into natural, immersive literary target-language fiction based on critique notes."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.llm = get_llm(model_name=model_name, temperature=0.3)
        self.last_usage: TokenUsage = TokenUsage()

    def polish(
        self,
        draft_text: str,
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible,
        genre: Optional[str] = None,
        source_text: Optional[str] = None,
        draft_chunks: Optional[List[Any]] = None,
        notify_callback: Optional[Any] = None
    ) -> str:
        if draft_chunks and len(draft_chunks) > 1:
            return self.polish_chunked(
                draft_chunks=draft_chunks,
                critique_notes=critique_notes,
                active_glossary=active_glossary,
                bible=bible,
                genre=genre,
                source_text=source_text,
                notify_callback=notify_callback
            )

        # Filter glossary to terms actually present in this chapter to avoid prompt bloat
        relevant_glossary = [
            item for item in active_glossary
            if (source_text and item.source.lower() in source_text.lower()) or item.target.lower() in draft_text.lower()
        ]
        eval_glossary = relevant_glossary if relevant_glossary else (active_glossary[:15] if active_glossary else [])
        gloss_str = "\n".join([f"- {g.source} -> {g.target}" for g in eval_glossary]) or "None"

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

        user_parts = []
        if source_text and source_text.strip():
            user_parts.append(
                f"### Original Source Text ({bible.source_language} - Reference Only):\n"
                f"{source_text.strip()[:50000]}"
            )
        user_parts.append(
            f"### Draft Translation in {bible.target_language} to Polish "
            f"(CRITICAL: Output MUST remain 100% in {bible.target_language}, DO NOT translate back to {bible.source_language}):\n"
            f"{draft_text}"
        )
        user_content = "\n\n".join(user_parts)

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_content)
        ])
        self.last_usage = extract_usage_from_message(response)

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

    def polish_chunked(
        self,
        draft_chunks: List[Any],
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible,
        genre: Optional[str] = None,
        source_text: Optional[str] = None,
        notify_callback: Optional[Any] = None
    ) -> str:
        """Polishes a long draft chunk-by-chunk with sliding context to avoid output limits and TPM stalls."""
        polished_parts = []
        prev_polished_tail = ""
        total_usage = TokenUsage()

        for chunk in draft_chunks:
            if notify_callback:
                try:
                    notify_callback(f"Polishing chunk {chunk.chunk_index}/{chunk.total_chunks} (lines {chunk.start_line}-{chunk.end_line})...")
                except Exception:
                    pass

            chunk_content = getattr(chunk, "content", str(chunk))
            chunk_source = getattr(chunk, "source_content", None) or source_text

            chunk_polished = self._polish_single_chunk(
                chunk_draft=chunk_content,
                preceding_context=prev_polished_tail,
                critique_notes=critique_notes,
                active_glossary=active_glossary,
                bible=bible,
                genre=genre,
                source_text=chunk_source,
                chunk_idx=getattr(chunk, "chunk_index", 1),
                total_chunks=getattr(chunk, "total_chunks", len(draft_chunks))
            )
            polished_parts.append(chunk_polished)
            total_usage = total_usage.add(self.last_usage)

            # Extract last 3 non-empty lines for sliding context
            lines = [l.strip() for l in chunk_polished.splitlines() if l.strip()]
            prev_polished_tail = "\n".join(lines[-3:]) if lines else ""

        self.last_usage = total_usage
        return "\n\n".join(polished_parts)

    def _polish_single_chunk(
        self,
        chunk_draft: str,
        preceding_context: str,
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible,
        genre: Optional[str] = None,
        source_text: Optional[str] = None,
        chunk_idx: int = 1,
        total_chunks: int = 1
    ) -> str:
        relevant_glossary = [
            item for item in active_glossary
            if (source_text and item.source.lower() in source_text.lower()) or item.target.lower() in chunk_draft.lower()
        ]
        eval_glossary = relevant_glossary if relevant_glossary else (active_glossary[:15] if active_glossary else [])
        gloss_str = "\n".join([f"- {g.source} -> {g.target}" for g in eval_glossary]) or "None"

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

        user_parts = []
        if preceding_context and preceding_context.strip():
            user_parts.append(
                f"### Preceding Polished Context ({bible.target_language} - Reference Only):\n"
                f"{preceding_context.strip()}\n"
                f"(CRITICAL: DO NOT duplicate or re-polish the above text. Seamlessly continue polishing from the draft chunk below.)"
            )

        if source_text and source_text.strip():
            user_parts.append(
                f"### Original Source Text ({bible.source_language} - Reference Only):\n"
                f"{source_text.strip()[:25000]}"
            )

        chunk_header = f"### Draft Translation in {bible.target_language} to Polish (Chunk {chunk_idx} of {total_chunks}):\n" if total_chunks > 1 else f"### Draft Translation in {bible.target_language} to Polish:\n"
        user_parts.append(f"{chunk_header}{chunk_draft}")
        user_content = "\n\n".join(user_parts)

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_content)
        ])
        self.last_usage = extract_usage_from_message(response)

        text = extract_text_from_message(response.content).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
                text = "\n".join(lines[1:-1]).strip()

        if bible.target_language.lower() != bible.source_language.lower():
            detected_polished = detect_language(text)
            if detected_polished and detected_polished.lower() == bible.source_language.lower():
                return chunk_draft

        return text
