"""Entity and terminology extraction agent."""
import json
import logging
import re
from typing import Any, List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.graph.procedural import ProceduralGraph, get_default_extractor_graph
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.metadata import TokenUsage
from nousetsu.prompts.templates import EXTRACTION_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.translation_fallback import (
    bisect_text,
    can_subdivide_text,
    is_safety_block_exception,
)

logger = logging.getLogger(__name__)


class EntityExtractorAgent:
    """Extracts unknown characters and terms from novel chapters using Procedural Graph steering."""

    def __init__(
        self,
        model_name: str = "gemini-3.1-flash-lite",
        fallback_model: Optional[str] = None,
        procedural_graph: Optional[ProceduralGraph] = None,
        chunker: Optional[Any] = None,
        enable_recursive_subdivision: bool = True,
        subdivision_min_lines: int = 8,
        subdivision_max_depth: int = 3,
    ):
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.llm = get_llm(model_name=model_name, fallback_model=fallback_model, temperature=0.1)
        self.last_usage: TokenUsage = TokenUsage()
        self.procedural_graph = procedural_graph or get_default_extractor_graph()
        self.chunker = chunker
        self.safety_fallbacks_used: int = 0
        self.enable_recursive_subdivision = enable_recursive_subdivision
        self.subdivision_min_lines = subdivision_min_lines
        self.subdivision_max_depth = subdivision_max_depth
        self.subdivisions_count: int = 0

    @property
    def last_model_used(self) -> str:
        if hasattr(self.llm, "last_model_used") and self.llm.last_model_used:
            return self.llm.last_model_used
        return self.model_name

    def _extract_single_text(
        self,
        text: str,
        bible: NovelBible,
        genre: Optional[str] = None,
        procedural_graph: Optional[ProceduralGraph] = None,
        known_characters: Optional[List[CharacterProfile]] = None,
        known_glossary: Optional[List[GlossaryItem]] = None,
        depth: int = 0
    ) -> Tuple[List[CharacterProfile], List[GlossaryItem], List[str]]:
        all_chars = list(bible.characters) + (known_characters or [])
        all_gloss = list(bible.glossary) + (known_glossary or [])

        known_chars_str = "\n".join([f"- {c.original_name} -> {c.name} ({c.role}, {c.voice})" for c in all_chars]) or "None yet."
        known_gloss_str = "\n".join([f"- {g.source} -> {g.target} ({g.category})" for g in all_gloss]) or "None yet."

        resolved_genre = genre or getattr(bible, "genre", "general")
        skills_text = SkillRegistry.get_instance().build_prompt_section(
            agent="extractor",
            source_lang=bible.source_language,
            genre=resolved_genre
        )
        skills_section = f"\n{skills_text}\n" if skills_text else ""

        # Procedural Graph guidance (Lu et al., arXiv:2609.09153v1)
        active_pg = procedural_graph or self.procedural_graph
        guidance_text = active_pg.to_compact_guidance("Scan_Candidates", max_hops=2) if active_pg else ""
        procedural_section = f"\n{guidance_text}\n" if guidance_text else ""

        sys_msg = EXTRACTION_SYSTEM_PROMPT.format(
            source_lang=bible.source_language,
            target_lang=bible.target_language,
            known_characters=known_chars_str,
            known_glossary=known_gloss_str,
            skills_section=skills_section,
            procedural_guidance=procedural_section
        )

        # Analytical task framing to avoid AI safety false positives on novel excerpts
        try:
            response = self.llm.invoke([
                SystemMessage(content=sys_msg),
                HumanMessage(content=f"Extract fictional characters, factions, and world terminology from this novel excerpt:\n{text[:100000]}")
            ])
            self.last_usage = extract_usage_from_message(response)
        except Exception as e:
            if is_safety_block_exception(e):
                can_sub = (
                    self.enable_recursive_subdivision
                    and depth < self.subdivision_max_depth
                    and can_subdivide_text(text, min_lines=self.subdivision_min_lines)
                )
                if can_sub:
                    self.subdivisions_count += 1
                    left_text, right_text = bisect_text(text)
                    line_count = len([l for l in text.splitlines() if l.strip()])
                    logger.warning(
                        f"⚠️ Extractor chunk blocked by safety filter ({line_count} lines) - "
                        f"subdividing (depth {depth + 1}/{self.subdivision_max_depth})..."
                    )
                    c_left, t_left, a_left = self._extract_single_text(
                        text=left_text,
                        bible=bible,
                        genre=genre,
                        procedural_graph=procedural_graph,
                        known_characters=known_characters,
                        known_glossary=known_glossary,
                        depth=depth + 1
                    )
                    left_usage = self.last_usage
                    c_right, t_right, a_right = self._extract_single_text(
                        text=right_text,
                        bible=bible,
                        genre=genre,
                        procedural_graph=procedural_graph,
                        known_characters=(known_characters or []) + c_left,
                        known_glossary=(known_glossary or []) + t_left,
                        depth=depth + 1
                    )
                    self.last_usage = left_usage.add(self.last_usage)
                    merged_chars = []
                    seen_names = set()
                    for c in c_left + c_right:
                        if c.name.lower() not in seen_names:
                            seen_names.add(c.name.lower())
                            merged_chars.append(c)

                    merged_terms = []
                    seen_sources = set()
                    for t in t_left + t_right:
                        if t.source.lower() not in seen_sources:
                            seen_sources.add(t.source.lower())
                            merged_terms.append(t)

                    return merged_chars, merged_terms, list(dict.fromkeys(a_left + a_right))

                self.safety_fallbacks_used += 1
                logger.warning("⚠️ Extractor chunk blocked by safety filter - bypassing entity extraction for this chunk.")
                self.last_usage = TokenUsage()
                return [], [], []
            raise

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

    def extract(
        self,
        source_text: str,
        bible: NovelBible,
        genre: Optional[str] = None,
        procedural_graph: Optional[ProceduralGraph] = None,
        chunks: Optional[List[Any]] = None,
        notify_callback: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        stop_event: Optional[Any] = None,
        **kwargs: Any
    ) -> Tuple[List[CharacterProfile], List[GlossaryItem], List[str]]:
        if chunks is None and self.chunker and hasattr(self.chunker, "should_chunk") and self.chunker.should_chunk(source_text):
            chunks = self.chunker.split_lines(source_text)

        if chunks and len(chunks) > 1:
            return self.extract_chunked(
                chunks=chunks,
                bible=bible,
                genre=genre,
                procedural_graph=procedural_graph,
                notify_callback=notify_callback,
                rate_limiter=rate_limiter,
                stop_event=stop_event,
                **kwargs
            )

        self.last_usage = TokenUsage()
        return self._extract_single_text(
            text=source_text,
            bible=bible,
            genre=genre,
            procedural_graph=procedural_graph
        )

    def extract_chunked(
        self,
        chunks: List[Any],
        bible: NovelBible,
        genre: Optional[str] = None,
        procedural_graph: Optional[ProceduralGraph] = None,
        notify_callback: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        stop_event: Optional[Any] = None,
        **kwargs: Any
    ) -> Tuple[List[CharacterProfile], List[GlossaryItem], List[str]]:
        """Extracts entities across chapter chunks with rate limiting and deduplication."""
        from nousetsu.utils.rate_limiter import estimate_tokens

        all_chars: List[CharacterProfile] = []
        all_terms: List[GlossaryItem] = []
        all_active: List[str] = []
        total_usage = TokenUsage()

        for chunk in chunks:
            if stop_event and stop_event.is_set():
                break

            chunk_idx = getattr(chunk, "chunk_index", 1)
            total_chunks = getattr(chunk, "total_chunks", len(chunks))
            chunk_content = getattr(chunk, "content", str(chunk))

            if notify_callback:
                try:
                    notify_callback(f"Extracting entities from chunk {chunk_idx}/{total_chunks}...")
                except Exception:
                    pass

            if rate_limiter:
                est_tokens = estimate_tokens(chunk_content[:12000]) + 600
                rate_limiter.acquire(
                    estimated_tokens=est_tokens,
                    stop_event=stop_event,
                    notify_callback=notify_callback
                )

            c_list, t_list, a_list = self._extract_single_text(
                text=chunk_content,
                bible=bible,
                genre=genre,
                procedural_graph=procedural_graph,
                known_characters=all_chars,
                known_glossary=all_terms
            )
            all_chars.extend(c_list)
            all_terms.extend(t_list)
            all_active.extend(a_list)
            total_usage = total_usage.add(self.last_usage)

            if rate_limiter and hasattr(rate_limiter, "record_usage") and self.last_usage.total_tokens > 0:
                rate_limiter.record_usage(self.last_usage.total_tokens)

        # Deduplicate extracted characters
        seen_chars = set()
        unique_chars: List[CharacterProfile] = []
        for c in all_chars:
            key = (c.name.strip().lower(), c.original_name.strip().lower())
            if key not in seen_chars:
                seen_chars.add(key)
                unique_chars.append(c)

        # Deduplicate extracted glossary items
        seen_terms = set()
        unique_terms: List[GlossaryItem] = []
        for t in all_terms:
            key = t.source.strip().lower()
            if key not in seen_terms:
                seen_terms.add(key)
                unique_terms.append(t)

        # Deduplicate active terms in order
        seen_active = set()
        unique_active: List[str] = []
        for act in all_active:
            norm = act.strip()
            if norm and norm.lower() not in seen_active:
                seen_active.add(norm.lower())
                unique_active.append(norm)

        self.last_usage = total_usage
        return unique_chars, unique_terms, unique_active
