"""Context-aware novelistic translation drafter agent."""
from typing import Any, Callable, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.graph.procedural import ProceduralGraph, get_default_drafter_graph
from nousetsu.models.bible import CharacterProfile, ChapterSummary, GlossaryItem, NovelBible
from nousetsu.models.metadata import TokenUsage
from nousetsu.prompts.templates import DRAFTING_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry


class ContextAwareDrafterAgent:
    """Produces initial novelistic translation draft with character voice and zero-anaphora context via Procedural Graph."""

    def __init__(
        self,
        model_name: str = "gemini-3.5-flash-lite",
        fallback_model: Optional[str] = None,
        procedural_graph: Optional[ProceduralGraph] = None,
        temperature: Optional[float] = None
    ):
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.llm = get_llm(model_name=model_name, fallback_model=fallback_model, temperature=temperature)
        self.last_usage: TokenUsage = TokenUsage()
        self.procedural_graph = procedural_graph or get_default_drafter_graph()

    @property
    def last_model_used(self) -> str:
        if hasattr(self.llm, "last_model_used") and self.llm.last_model_used:
            return self.llm.last_model_used
        return self.model_name

    def draft(
        self,
        source_text: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        rolling_summaries: List[ChapterSummary],
        genre: Optional[str] = None,
        chunks: Optional[List[Any]] = None,
        notify_callback: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        stop_event: Optional[Any] = None,
        procedural_graph: Optional[ProceduralGraph] = None
    ) -> str:
        if chunks and len(chunks) > 1:
            return self.draft_chunked(
                chunks=chunks,
                bible=bible,
                active_characters=active_characters,
                active_glossary=active_glossary,
                rolling_summaries=rolling_summaries,
                genre=genre,
                notify_callback=notify_callback,
                rate_limiter=rate_limiter,
                stop_event=stop_event,
                procedural_graph=procedural_graph
            )

        chars_str = "\n".join([
            f"- {c.name} (Original: {c.original_name}, Gender: {c.gender}, Role: {c.role}): Voice={c.voice}"
            for c in active_characters
        ]) or "No explicit character cards registered."

        # Filter glossary to terms actually present in this chapter to avoid prompt bloat
        relevant_glossary = [
            item for item in active_glossary
            if item.source.lower() in source_text.lower()
        ]
        eval_glossary = relevant_glossary if relevant_glossary else (active_glossary[:20] if active_glossary else [])

        gloss_str = "\n".join([
            f"- '{g.source}' MUST be translated as '{g.target}' ({g.category})"
            for g in eval_glossary
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

        # Procedural Graph guidance (Lu et al., arXiv:2609.09153v1)
        active_pg = procedural_graph or self.procedural_graph
        guidance_text = active_pg.to_compact_guidance("Scene_Init", max_hops=3) if active_pg else ""
        procedural_section = f"\n{guidance_text}\n" if guidance_text else ""

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
            skills_section=skills_section,
            procedural_guidance=procedural_section
        )

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=f"Original Text to Translate:\n\n{source_text}")
        ])
        self.last_usage = extract_usage_from_message(response)

        return extract_text_from_message(response.content)

    def draft_chunked(
        self,
        chunks: List[Any],
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        rolling_summaries: List[ChapterSummary],
        genre: Optional[str] = None,
        notify_callback: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        stop_event: Optional[Any] = None,
        procedural_graph: Optional[ProceduralGraph] = None
    ) -> str:
        """Drafts novel chunks sequentially with sliding translation context for pronoun/voice continuity."""
        from nousetsu.utils.rate_limiter import estimate_tokens

        drafted_parts = []
        prev_draft_tail = ""
        total_usage = TokenUsage()

        for chunk in chunks:
            if stop_event and stop_event.is_set():
                break

            chunk_idx = getattr(chunk, "chunk_index", 1)
            total_chunks = getattr(chunk, "total_chunks", len(chunks))
            start_line = getattr(chunk, "start_line", 1)
            end_line = getattr(chunk, "end_line", 1)
            chunk_content = getattr(chunk, "content", str(chunk))

            if notify_callback:
                try:
                    notify_callback(f"Drafting chunk {chunk_idx}/{total_chunks} (lines {start_line}-{end_line})...")
                except Exception:
                    pass

            # Acquire rate-limiter capacity for this specific chunk (typically ~3k-4k tokens)
            if rate_limiter:
                est_chunk_tokens = int(estimate_tokens(chunk_content) * 1.5) + 1500
                rate_limiter.acquire(
                    estimated_tokens=est_chunk_tokens,
                    stop_event=stop_event,
                    notify_callback=notify_callback
                )

            chunk_draft = self._draft_single_chunk(
                chunk_text=chunk_content,
                preceding_context=prev_draft_tail,
                bible=bible,
                active_characters=active_characters,
                active_glossary=active_glossary,
                rolling_summaries=rolling_summaries,
                genre=genre,
                chunk_idx=chunk_idx,
                total_chunks=total_chunks,
                procedural_graph=procedural_graph
            )
            drafted_parts.append(chunk_draft)
            total_usage = total_usage.add(self.last_usage)

            # Record actual usage if rate limiter supports it
            if rate_limiter and hasattr(rate_limiter, "record_usage") and self.last_usage.total_tokens > 0:
                rate_limiter.record_usage(self.last_usage.total_tokens)

            # Extract last 3 non-empty lines of draft for next chunk's sliding context
            lines = [l.strip() for l in chunk_draft.splitlines() if l.strip()]
            prev_draft_tail = "\n".join(lines[-3:]) if lines else ""

        self.last_usage = total_usage
        return "\n\n".join(drafted_parts)

    def _draft_single_chunk(
        self,
        chunk_text: str,
        preceding_context: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        rolling_summaries: List[ChapterSummary],
        genre: Optional[str] = None,
        chunk_idx: int = 1,
        total_chunks: int = 1,
        procedural_graph: Optional[ProceduralGraph] = None
    ) -> str:
        chars_str = "\n".join([
            f"- {c.name} (Original: {c.original_name}, Gender: {c.gender}, Role: {c.role}): Voice={c.voice}"
            for c in active_characters
        ]) or "No explicit character cards registered."

        relevant_glossary = [
            item for item in active_glossary
            if item.source.lower() in chunk_text.lower()
        ]
        eval_glossary = relevant_glossary if relevant_glossary else (active_glossary[:15] if active_glossary else [])

        gloss_str = "\n".join([
            f"- '{g.source}' MUST be translated as '{g.target}' ({g.category})"
            for g in eval_glossary
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

        # Procedural Graph guidance (Lu et al., arXiv:2609.09153v1)
        active_pg = procedural_graph or self.procedural_graph
        active_node = "Scene_Init" if chunk_idx == 1 else "Boundary_Continuity"
        guidance_text = active_pg.to_compact_guidance(active_node, max_hops=2) if active_pg else ""
        procedural_section = f"\n{guidance_text}\n" if guidance_text else ""

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
            skills_section=skills_section,
            procedural_guidance=procedural_section
        )

        user_parts = []
        if preceding_context and preceding_context.strip():
            user_parts.append(
                f"### Preceding Scene Context ({bible.target_language} - Read-Only for narrative flow & pronoun continuity):\n"
                f"{preceding_context.strip()}\n"
                f"(CRITICAL: DO NOT re-translate or repeat the above preceding context. Resume translating immediately from the lines below.)"
            )

        chunk_header = f"### Chapter Lines to Translate (Chunk {chunk_idx} of {total_chunks}):\n\n" if total_chunks > 1 else "Original Text to Translate:\n\n"
        user_parts.append(f"{chunk_header}{chunk_text}")
        user_content = "\n\n".join(user_parts)

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_content)
        ])
        self.last_usage = extract_usage_from_message(response)

        return extract_text_from_message(response.content)
