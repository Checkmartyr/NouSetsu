"""Context-aware novelistic translation drafter agent."""
import logging
from typing import Any, Callable, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.graph.procedural import ProceduralGraph, get_default_drafter_graph
from nousetsu.models.bible import CharacterProfile, ChapterSummary, GlossaryItem, NovelBible
from nousetsu.models.metadata import TokenUsage
from nousetsu.prompts.templates import DRAFTING_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.translation_fallback import (
    bisect_text,
    can_subdivide_text,
    is_safety_block_exception,
    translate_via_google,
)

logger = logging.getLogger(__name__)


class ContextAwareDrafterAgent:
    """Produces initial novelistic translation draft with character voice and zero-anaphora context via Procedural Graph."""

    def __init__(
        self,
        model_name: str = "gemini-3.5-flash-lite",
        fallback_model: Optional[str] = None,
        procedural_graph: Optional[ProceduralGraph] = None,
        temperature: Optional[float] = None,
        polisher: Optional[Any] = None,
        enable_recursive_subdivision: bool = True,
        subdivision_min_lines: int = 8,
        subdivision_max_depth: int = 4,
    ):
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.llm = get_llm(model_name=model_name, fallback_model=fallback_model, temperature=temperature)
        self.last_usage: TokenUsage = TokenUsage()
        self.procedural_graph = procedural_graph or get_default_drafter_graph()
        self.polisher = polisher
        self.safety_fallbacks_used: int = 0
        self.enable_recursive_subdivision: bool = enable_recursive_subdivision
        self.subdivision_min_lines: int = subdivision_min_lines
        self.subdivision_max_depth: int = subdivision_max_depth
        self.subdivisions_count: int = 0

    @property
    def last_model_used(self) -> str:
        if hasattr(self.llm, "last_model_used") and self.llm.last_model_used:
            return self.llm.last_model_used
        return self.model_name

    @staticmethod
    def format_summaries(
        rolling_summaries: List[ChapterSummary],
        limit: int = 3,
        bible: Optional[NovelBible] = None,
        rag_results: Optional[List[Any]] = None
    ) -> str:
        """Format 4-tier narrative context (Macro Whole Story > Meso Story Arc > Micro Situation > Episodic RAG Lore)."""
        selected = rolling_summaries[-limit:] if limit else rolling_summaries
        micro_str = "\n".join([
            f"[{s.folder}] Chapter {s.chapter_num} ({s.title}): {s.synopsis}" if getattr(s, "folder", None) else f"Chapter {s.chapter_num} ({s.title}): {s.synopsis}"
            for s in selected
        ]) if selected else "This is the first chapter."

        sections = ["### 3. Immediate Preceding Situation (Micro):", micro_str]

        arc = getattr(bible, "active_arc", None) if bible else None
        if arc and (arc.title or arc.synopsis or arc.core_conflict):
            arc_lines = [f"### 2. Active Story Arc (Meso - Arc {arc.arc_num}: '{arc.title or 'Ongoing Arc'}'):"]
            if arc.core_conflict:
                arc_lines.append(f"- Central Conflict: {arc.core_conflict}")
            if arc.synopsis:
                arc_lines.append(f"- Arc Progress: {arc.synopsis}")
            if arc.key_milestones:
                arc_lines.append(f"- Milestones: {', '.join(arc.key_milestones)}")
            sections = ["\n".join(arc_lines)] + sections

        story = getattr(bible, "whole_story_summary", "") if bible else ""
        if story:
            sections = [f"### 1. Global Story Progression (Macro):\n{story}"] + sections

        if rag_results:
            lore_lines = ["### 4. Relevant Historical Lore & Past Canon (Episodic Hybrid RAG):"]
            for r in rag_results:
                loc = f"[{r.folder}] " if getattr(r, "folder", None) else ""
                ch_str = f"Chapter {r.chapter_num}" if getattr(r, "chapter_num", None) else "Lore Entry"
                t_str = f" ({r.title})" if getattr(r, "title", None) else ""
                content_snip = getattr(r, "content", str(r)).strip()
                lore_lines.append(f"- {loc}{ch_str}{t_str}: {content_snip[:350]}")
            sections.append("\n".join(lore_lines))

        if not bible and not rag_results:
            return micro_str

        return "## HIERARCHICAL NARRATIVE CONTEXT:\n" + "\n\n".join(sections)

    def _get_polisher(self) -> Any:
        if self.polisher is not None:
            return self.polisher
        from nousetsu.agents.polisher import PolishingAgent
        self.polisher = PolishingAgent(
            model_name=self.model_name,
            fallback_model=self.fallback_model
        )
        return self.polisher

    def _handle_safety_fallback(
        self,
        source_chunk_text: str,
        bible: NovelBible,
        active_glossary: List[GlossaryItem],
        genre: Optional[str] = None,
        polisher: Optional[Any] = None
    ) -> str:
        """Translate blocked sensitive chunk using Google Translate fallback and attempt literary polish."""
        self.safety_fallbacks_used += 1
        logger.warning("⚠️ Drafter encountered safety block on chunk - falling back to Google Translate and Feinschliff polishing.")
        gt_text = translate_via_google(
            text=source_chunk_text,
            source_lang=bible.source_language,
            target_lang=bible.target_language
        )
        if not gt_text or not gt_text.strip():
            return gt_text

        active_pol = polisher or self._get_polisher()
        try:
            polished = active_pol.polish(
                draft_text=gt_text,
                critique_notes="Preserve clarity, natural cadence, and smooth literary flow.",
                active_glossary=active_glossary,
                bible=bible,
                genre=genre,
                source_text=None
            )
            return polished if (polished and polished.strip()) else gt_text
        except Exception as pe:
            if is_safety_block_exception(pe):
                logger.warning("⚠️ Polisher also blocked on sensitive chunk - retaining raw Google Translate output.")
            else:
                logger.warning(f"⚠️ Polisher failed on fallback chunk ({pe}) - retaining raw Google Translate output.")
            return gt_text

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
        procedural_graph: Optional[ProceduralGraph] = None,
        polisher: Optional[Any] = None,
        **kwargs: Any
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
                procedural_graph=procedural_graph,
                polisher=polisher,
                **kwargs
            )

        self.last_usage = TokenUsage()
        return self._draft_with_recursive_subdivision(
            chunk_text=source_text,
            preceding_context="",
            bible=bible,
            active_characters=active_characters,
            active_glossary=active_glossary,
            rolling_summaries=rolling_summaries,
            genre=genre,
            chunk_idx=1,
            total_chunks=1,
            depth=0,
            procedural_graph=procedural_graph,
            polisher=polisher,
            **kwargs
        )

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
        procedural_graph: Optional[ProceduralGraph] = None,
        polisher: Optional[Any] = None,
        **kwargs: Any
    ) -> str:
        """Drafts novel chunks sequentially with sliding translation context for pronoun/voice continuity."""
        from nousetsu.utils.rate_limiter import estimate_tokens

        drafted_parts = []
        prev_draft_tail = ""
        total_usage = TokenUsage()

        for chunk in chunks:
            if stop_event and stop_event.is_set():
                from nousetsu.models.exceptions import BatchStoppedException
                raise BatchStoppedException("Drafting cancelled by user request.")

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
                procedural_graph=procedural_graph,
                polisher=polisher,
                **kwargs
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

    def _invoke_llm_draft(
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
        procedural_graph: Optional[ProceduralGraph] = None,
        **kwargs: Any
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

        rag_results = kwargs.get("rag_results")
        summaries_str = self.format_summaries(rolling_summaries, limit=3, bible=bible, rag_results=rag_results)

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

        chunk_header = f"### Fictional Novel Excerpt to Translate (Chunk {chunk_idx} of {total_chunks}):\n\n" if total_chunks > 1 else "Translate this fictional novel excerpt into literary prose:\n\n"
        user_parts.append(f"{chunk_header}{chunk_text}")
        user_content = "\n\n".join(user_parts)

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_content)
        ])
        self.last_usage = self.last_usage.add(extract_usage_from_message(response))
        return extract_text_from_message(response.content)

    def _draft_with_recursive_subdivision(
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
        depth: int = 0,
        procedural_graph: Optional[ProceduralGraph] = None,
        polisher: Optional[Any] = None,
        **kwargs: Any
    ) -> str:
        try:
            return self._invoke_llm_draft(
                chunk_text=chunk_text,
                preceding_context=preceding_context,
                bible=bible,
                active_characters=active_characters,
                active_glossary=active_glossary,
                rolling_summaries=rolling_summaries,
                genre=genre,
                chunk_idx=chunk_idx,
                total_chunks=total_chunks,
                procedural_graph=procedural_graph,
                **kwargs
            )
        except Exception as e:
            if not is_safety_block_exception(e):
                raise

            can_sub = (
                self.enable_recursive_subdivision
                and depth < self.subdivision_max_depth
                and can_subdivide_text(chunk_text, min_lines=self.subdivision_min_lines)
            )

            if can_sub:
                self.subdivisions_count += 1
                left_text, right_text = bisect_text(chunk_text)
                line_count = len([l for l in chunk_text.splitlines() if l.strip()])
                logger.warning(
                    f"⚠️ Safety block on chunk ({line_count} lines) - "
                    f"subdividing (depth {depth + 1}/{self.subdivision_max_depth})..."
                )
                left_draft = self._draft_with_recursive_subdivision(
                    chunk_text=left_text,
                    preceding_context=preceding_context,
                    bible=bible,
                    active_characters=active_characters,
                    active_glossary=active_glossary,
                    rolling_summaries=rolling_summaries,
                    genre=genre,
                    chunk_idx=chunk_idx,
                    total_chunks=total_chunks,
                    depth=depth + 1,
                    procedural_graph=procedural_graph,
                    polisher=polisher,
                    **kwargs
                )
                left_tail_lines = [l.strip() for l in left_draft.splitlines() if l.strip()]
                left_tail = "\n".join(left_tail_lines[-3:]) if left_tail_lines else preceding_context
                right_draft = self._draft_with_recursive_subdivision(
                    chunk_text=right_text,
                    preceding_context=left_tail,
                    bible=bible,
                    active_characters=active_characters,
                    active_glossary=active_glossary,
                    rolling_summaries=rolling_summaries,
                    genre=genre,
                    chunk_idx=chunk_idx,
                    total_chunks=total_chunks,
                    depth=depth + 1,
                    procedural_graph=procedural_graph,
                    polisher=polisher,
                    **kwargs
                )
                draft_parts = [p.strip() for p in (left_draft, right_draft) if p and p.strip()]
                return "\n\n".join(draft_parts)

            # Base case: reached minimum lines or max depth -> isolated sensitive snippet
            relevant_glossary = [
                item for item in active_glossary
                if item.source.lower() in chunk_text.lower()
            ]
            eval_glossary = relevant_glossary if relevant_glossary else (active_glossary[:15] if active_glossary else [])
            resolved_genre = genre or getattr(bible, "genre", "general")
            return self._handle_safety_fallback(
                source_chunk_text=chunk_text,
                bible=bible,
                active_glossary=eval_glossary,
                genre=resolved_genre,
                polisher=polisher
            )

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
        procedural_graph: Optional[ProceduralGraph] = None,
        polisher: Optional[Any] = None,
        **kwargs: Any
    ) -> str:
        self.last_usage = TokenUsage()
        return self._draft_with_recursive_subdivision(
            chunk_text=chunk_text,
            preceding_context=preceding_context,
            bible=bible,
            active_characters=active_characters,
            active_glossary=active_glossary,
            rolling_summaries=rolling_summaries,
            genre=genre,
            chunk_idx=chunk_idx,
            total_chunks=total_chunks,
            depth=0,
            procedural_graph=procedural_graph,
            polisher=polisher,
            **kwargs
        )
