"""Literary prose polisher and style editor agent."""
import logging
from typing import Any, Callable, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.models.bible import GlossaryItem, NovelBible
from nousetsu.models.metadata import TokenUsage
from nousetsu.prompts.templates import POLISHING_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.language import detect_language
from nousetsu.utils.translation_fallback import is_safety_block_exception

logger = logging.getLogger(__name__)


class PolishingAgent:
    """Refines drafted prose into natural, immersive literary target-language fiction based on critique notes."""

    def __init__(
        self,
        model_name: str = "gemini-3.5-flash-lite",
        fallback_model: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.llm = get_llm(model_name=model_name, fallback_model=fallback_model, temperature=temperature)
        self.last_usage: TokenUsage = TokenUsage()
        self.safety_fallbacks_used: int = 0

    @property
    def last_model_used(self) -> str:
        if hasattr(self.llm, "last_model_used") and self.llm.last_model_used:
            return self.llm.last_model_used
        return self.model_name

    def polish(
        self,
        draft_text: str,
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible,
        genre: Optional[str] = None,
        source_text: Optional[str] = None,
        draft_chunks: Optional[List[Any]] = None,
        notify_callback: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        stop_event: Optional[Any] = None,
        **kwargs: Any
    ) -> str:
        if draft_chunks and len(draft_chunks) > 1:
            return self.polish_chunked(
                draft_chunks=draft_chunks,
                critique_notes=critique_notes,
                active_glossary=active_glossary,
                bible=bible,
                genre=genre,
                source_text=source_text,
                notify_callback=notify_callback,
                rate_limiter=rate_limiter,
                stop_event=stop_event,
                **kwargs
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

        try:
            response = self.llm.invoke([
                SystemMessage(content=sys_msg),
                HumanMessage(content=user_content)
            ])
            self.last_usage = extract_usage_from_message(response)
        except Exception as e:
            if is_safety_block_exception(e):
                self.safety_fallbacks_used += 1
                logger.warning("⚠️ Polisher blocked by safety filter - retaining draft text.")
                return draft_text
            raise

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
        notify_callback: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        stop_event: Optional[Any] = None,
        **kwargs: Any
    ) -> str:
        """Polishes a long draft chunk-by-chunk with sliding context to avoid output limits and TPM stalls."""
        from nousetsu.utils.rate_limiter import estimate_tokens

        polished_parts = []
        prev_polished_tail = ""
        total_usage = TokenUsage()

        for chunk in draft_chunks:
            if stop_event and stop_event.is_set():
                break

            chunk_idx = getattr(chunk, "chunk_index", 1)
            total_chunks = getattr(chunk, "total_chunks", len(draft_chunks))
            start_line = getattr(chunk, "start_line", 1)
            end_line = getattr(chunk, "end_line", 1)

            if notify_callback:
                try:
                    notify_callback(f"Polishing chunk {chunk_idx}/{total_chunks} (lines {start_line}-{end_line})...")
                except Exception:
                    pass

            chunk_content = getattr(chunk, "content", str(chunk))
            chunk_source = getattr(chunk, "source_content", None)
            if not chunk_source and source_text:
                # Sliced source lines per chunk instead of leaking the full unchunked source text
                raw_src_lines = source_text.splitlines(keepends=True)
                src_start = max(0, int((chunk_idx - 1) / total_chunks * len(raw_src_lines)) - 2)
                src_end = min(len(raw_src_lines), int(chunk_idx / total_chunks * len(raw_src_lines)) + 2)
                chunk_source = "".join(raw_src_lines[src_start:src_end])

            if rate_limiter:
                est_tokens = estimate_tokens(chunk_content) * 2 + 1000
                rate_limiter.acquire(
                    estimated_tokens=est_tokens,
                    stop_event=stop_event,
                    notify_callback=notify_callback
                )

            chunk_polished = self._polish_single_chunk(
                chunk_draft=chunk_content,
                preceding_context=prev_polished_tail,
                critique_notes=critique_notes,
                active_glossary=active_glossary,
                bible=bible,
                genre=genre,
                source_text=chunk_source,
                chunk_idx=chunk_idx,
                total_chunks=total_chunks
            )
            polished_parts.append(chunk_polished)
            total_usage = total_usage.add(self.last_usage)

            if rate_limiter and hasattr(rate_limiter, "record_usage") and self.last_usage.total_tokens > 0:
                rate_limiter.record_usage(self.last_usage.total_tokens)

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

        try:
            response = self.llm.invoke([
                SystemMessage(content=sys_msg),
                HumanMessage(content=user_content)
            ])
            self.last_usage = extract_usage_from_message(response)
        except Exception as e:
            if is_safety_block_exception(e):
                self.safety_fallbacks_used += 1
                logger.warning("⚠️ Polisher chunk blocked by safety filter - retaining chunk draft.")
                return chunk_draft
            raise

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
