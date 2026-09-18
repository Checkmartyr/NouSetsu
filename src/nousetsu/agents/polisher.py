"""Literary prose polisher and style editor agent."""
import logging
import os
import re
import time
from typing import Any, Callable, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.graph.procedural import ProceduralGraph, get_default_polisher_graph
from nousetsu.models.bible import GlossaryItem, NovelBible
from nousetsu.models.metadata import SubdividedBlock, TokenUsage
from nousetsu.models.trace import PipelineStage
from nousetsu.prompts.templates import PATCH_POLISHING_SYSTEM_PROMPT, POLISHING_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.diff_patcher import apply_search_replace_patches, is_patch_format
from nousetsu.utils.glossary_filter import filter_glossary_for_scene
from nousetsu.utils.language import detect_language
from nousetsu.utils.translation_fallback import (
    bisect_text,
    can_subdivide_text,
    is_safety_block_exception,
)

logger = logging.getLogger(__name__)

CHAPTER_HEADER_PATTERNS = [
    r"^(?:#+\s*)?(?:\*\*)?(?:\d+[\s_.-]+)?(?:Chapter|Chapitre|Capítulo|Kapitel|Hoofdstuk|Глава)\s+\d+",
    r"^(?:#+\s*)?(?:\*\*)?(?:\d+[\s_.-]+)?บทที่\s*\d+",
    r"^(?:#+\s*)?(?:\*\*)?(?:\d+[\s_.-]+)?第\s*[\d一二三四五六七八九十百千]+\s*[章回节話话]",
    r"^(?:#+\s*)?(?:\*\*)?(?:\d+[\s_.-]+)?제\s*\d+\s*장",
    r"^(?:#+\s*)?(?:\*\*)?(?:\d+[\s_.-]+)?Episode\s+\d+",
    r"^(?:#+\s*)?(?:\*\*)?(?:\d+[\s_.-]+)?Ep\.\s*\d+",
    r"^#+\s+.+",
]
CHAPTER_HEADER_RE = re.compile("|".join(CHAPTER_HEADER_PATTERNS), re.IGNORECASE)



class PolishingAgent:
    """Refines drafted prose into natural, immersive literary target-language fiction based on critique notes."""

    def __init__(
        self,
        model_name: str = "gemini-3.5-flash-lite",
        fallback_model: Optional[str] = None,
        procedural_graph: Optional[ProceduralGraph] = None,
        temperature: Optional[float] = None,
        thinking_level: Optional[str] = None,
        thinking_budget: Optional[int] = None,
        enable_recursive_subdivision: bool = True,
        subdivision_min_lines: int = 8,
        subdivision_max_depth: int = 4,
    ):
        self.model_name = model_name
        self.fallback_model = fallback_model

        polisher_thinking_level = (
            thinking_level
            or os.environ.get("NOVEL_POLISHER_THINKING_LEVEL")
            or os.environ.get("NOVEL_THINKING_LEVEL")
        )
        polisher_thinking_budget = None
        if thinking_budget is not None:
            polisher_thinking_budget = thinking_budget
        elif os.environ.get("NOVEL_POLISHER_THINKING_BUDGET"):
            try:
                polisher_thinking_budget = int(os.environ["NOVEL_POLISHER_THINKING_BUDGET"])
            except ValueError:
                pass
        elif os.environ.get("NOVEL_THINKING_BUDGET"):
            try:
                polisher_thinking_budget = int(os.environ["NOVEL_THINKING_BUDGET"])
            except ValueError:
                pass

        self.llm = get_llm(
            model_name=model_name,
            fallback_model=fallback_model,
            temperature=temperature,
            thinking_level=polisher_thinking_level,
            thinking_budget=polisher_thinking_budget,
        )
        self.last_usage: TokenUsage = TokenUsage()
        self.procedural_graph = procedural_graph or get_default_polisher_graph()
        self.safety_fallbacks_used: int = 0
        self.enable_recursive_subdivision: bool = enable_recursive_subdivision
        self.subdivision_min_lines: int = subdivision_min_lines
        self.subdivision_max_depth: int = subdivision_max_depth
        self.subdivisions_count: int = 0
        self.last_subdivided_blocks: List[SubdividedBlock] = []
        self.prompt_tracker: Optional[Any] = None

    @property
    def last_model_used(self) -> str:
        if hasattr(self.llm, "last_model_used") and self.llm.last_model_used:
            return self.llm.last_model_used
        return self.model_name

    @staticmethod
    def _extract_draft_chapter_header(draft_text: str) -> Optional[str]:
        """Extracts leading chapter heading or title block from draft text if present."""
        if not draft_text:
            return None
        lines = draft_text.splitlines()
        non_empty_indices = [i for i, l in enumerate(lines[:8]) if l.strip()]
        if not non_empty_indices:
            return None

        first_idx = non_empty_indices[0]
        first_line = lines[first_idx].strip()

        if CHAPTER_HEADER_RE.search(first_line):
            return first_line

        # Check if first non-empty line is a page/raw number (e.g. "70") and second is chapter header
        if re.match(r"^\d+$", first_line) and len(non_empty_indices) > 1:
            second_idx = non_empty_indices[1]
            second_line = lines[second_idx].strip()
            if CHAPTER_HEADER_RE.search(second_line):
                return f"{first_line}\n{second_line}"

        return None

    @staticmethod
    def _has_chapter_header(text: str) -> bool:
        """Checks if text already contains a chapter header in its opening lines."""
        if not text:
            return False
        lines = [l.strip() for l in text.splitlines()[:8] if l.strip()]
        for line in lines[:3]:
            if CHAPTER_HEADER_RE.search(line):
                return True
        return False

    @classmethod
    def _ensure_chapter_title_preserved(cls, draft_text: str, polished_text: str) -> str:
        """Ensures that chapter title and headings present in the draft are not omitted in polished prose."""
        if not draft_text or not polished_text:
            return polished_text

        # If polished_text is corrupt or contains patch markers, reject it immediately
        if is_patch_format(polished_text) or "<<<<<<<" in polished_text or ">>>>>>>" in polished_text:
            logger.error("Diff patch markers detected in _ensure_chapter_title_preserved! Reverting to draft text.")
            return draft_text

        header_block = cls._extract_draft_chapter_header(draft_text)
        if not header_block:
            return polished_text

        if cls._has_chapter_header(polished_text):
            return polished_text

        logger.info(f"Restoring omitted chapter header in polished text: {header_block!r}")
        return f"{header_block}\n\n{polished_text.lstrip()}"

    def _invoke_llm_polish(
        self,
        draft_text: str,
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible,
        genre: Optional[str] = None,
        source_text: Optional[str] = None,
        preceding_context: str = "",
        chunk_idx: int = 1,
        total_chunks: int = 1,
        depth: int = 0,
        iteration: int = 1,
        procedural_graph: Optional[ProceduralGraph] = None,
        prompt_tracker: Optional[Any] = None,
        **kwargs: Any
    ) -> str:
        eval_glossary = filter_glossary_for_scene(
            glossary=active_glossary,
            source_text=source_text,
            target_text=draft_text,
            fallback_on_empty=True,
            max_fallback=15
        )
        gloss_str = "\n".join([f"- {g.source} -> {g.target}" for g in eval_glossary]) or "None"

        resolved_genre = genre or getattr(bible, "genre", "general")
        skills_text = SkillRegistry.get_instance().build_prompt_section(
            agent="polisher",
            source_lang=bible.source_language,
            genre=resolved_genre
        )
        skills_section = f"\n{skills_text}\n" if skills_text else ""

        active_pg = procedural_graph or kwargs.get("procedural_graph") or self.procedural_graph
        guidance_text = active_pg.to_compact_guidance("Inspect_Critique", max_hops=2) if active_pg else ""
        procedural_section = f"\n{guidance_text}\n" if guidance_text else ""

        use_patch = kwargs.get("use_patch", False)
        prompt_template = PATCH_POLISHING_SYSTEM_PROMPT if use_patch else POLISHING_SYSTEM_PROMPT
        sys_msg = prompt_template.format(
            target_lang=bible.target_language,
            source_lang=bible.source_language,
            critique_notes=critique_notes or "Preserve meaning and enhance natural rhythm.",
            glossary=gloss_str,
            skills_section=skills_section,
            procedural_guidance=procedural_section
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

        chunk_header = (
            f"### Draft Translation in {bible.target_language} to Polish (Chunk {chunk_idx} of {total_chunks}):\n"
            if total_chunks > 1
            else f"### Draft Translation in {bible.target_language} to Polish "
                 f"(CRITICAL: Output MUST remain 100% in {bible.target_language}, DO NOT translate back to {bible.source_language}):\n"
        )
        user_parts.append(f"{chunk_header}{draft_text}")
        user_content = "\n\n".join(user_parts)

        tracker = prompt_tracker or kwargs.get("prompt_tracker") or getattr(self, "prompt_tracker", None)
        t0 = time.time()
        try:
            response = self.llm.invoke([
                SystemMessage(content=sys_msg),
                HumanMessage(content=user_content)
            ])
            duration = time.time() - t0
            self.last_usage = extract_usage_from_message(response)
        except Exception as e:
            duration = time.time() - t0
            if tracker:
                tracker.record_error(
                    stage=PipelineStage.POLISHING,
                    agent="polisher",
                    system_prompt=sys_msg,
                    user_prompt=user_content,
                    model=getattr(self, "last_model_used", self.model_name),
                    err=e,
                    duration_seconds=duration,
                    chunk_index=chunk_idx,
                    total_chunks=total_chunks,
                    depth=depth,
                    iteration=iteration,
                    status="safety_blocked" if is_safety_block_exception(e) else "error"
                )
            raise

        text = extract_text_from_message(response.content).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
                text = "\n".join(lines[1:-1]).strip()

        if "NO_CHANGES_NEEDED" in text:
            text = draft_text
        elif is_patch_format(text):
            patched_chunk, applied, failed = apply_search_replace_patches(draft_text, text)
            if applied > 0:
                text = patched_chunk
            else:
                logger.warning(f"Failed to apply any patch edits from polisher ({failed} failed); falling back to draft text.")
                text = draft_text

        # Absolute safety guard against diff marker leaks
        if is_patch_format(text) or "<<<<<<<" in text or ">>>>>>>" in text:
            logger.error("Unparsed diff patch markers detected in polished output! Forcing fallback to draft text.")
            text = draft_text

        if tracker:
            tracker.record(
                stage=PipelineStage.POLISHING,
                agent="polisher",
                system_prompt=sys_msg,
                user_prompt=user_content,
                raw_output=text,
                parsed_output=None,
                model=getattr(self, "last_model_used", self.model_name),
                token_usage=self.last_usage,
                duration_seconds=duration,
                chunk_index=chunk_idx,
                total_chunks=total_chunks,
                depth=depth,
                iteration=iteration
            )

        # Programmatic Language Regression Guard:
        if bible.target_language.lower() != bible.source_language.lower():
            detected_polished = detect_language(text)
            if detected_polished and detected_polished.lower() == bible.source_language.lower():
                return draft_text

        return text

    def _polish_with_recursive_subdivision(
        self,
        draft_text: str,
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible,
        genre: Optional[str] = None,
        source_text: Optional[str] = None,
        preceding_context: str = "",
        chunk_idx: int = 1,
        total_chunks: int = 1,
        depth: int = 0,
        iteration: int = 1,
        procedural_graph: Optional[ProceduralGraph] = None,
        prompt_tracker: Optional[Any] = None,
        **kwargs: Any
    ) -> str:
        sub_kwargs = dict(kwargs)
        sub_kwargs.pop("iteration", None)
        sub_kwargs.pop("procedural_graph", None)
        sub_kwargs.pop("prompt_tracker", None)

        try:
            res = self._invoke_llm_polish(
                draft_text=draft_text,
                critique_notes=critique_notes,
                active_glossary=active_glossary,
                bible=bible,
                genre=genre,
                source_text=source_text,
                preceding_context=preceding_context,
                chunk_idx=chunk_idx,
                total_chunks=total_chunks,
                depth=depth,
                iteration=iteration,
                procedural_graph=procedural_graph,
                prompt_tracker=prompt_tracker,
                **sub_kwargs
            )
            self.last_subdivided_blocks.append(
                SubdividedBlock(
                    block_index=len(self.last_subdivided_blocks),
                    source_text=source_text or "",
                    draft_text=draft_text,
                    polished_text=res,
                    is_sensitive=False,
                    fallback_used=False
                )
            )
            return res
        except Exception as e:
            if not is_safety_block_exception(e):
                raise

            # Step 1: Retry once without raw source text reference
            if source_text and source_text.strip():
                logger.warning(f"⚠️ Polisher safety block (depth {depth}) - retrying without raw source text reference.")
                try:
                    res = self._invoke_llm_polish(
                        draft_text=draft_text,
                        critique_notes=critique_notes,
                        active_glossary=active_glossary,
                        bible=bible,
                        genre=genre,
                        source_text=None,
                        preceding_context=preceding_context,
                        chunk_idx=chunk_idx,
                        total_chunks=total_chunks,
                        depth=depth,
                        iteration=iteration,
                        procedural_graph=procedural_graph,
                        prompt_tracker=prompt_tracker,
                        **sub_kwargs
                    )
                    self.last_subdivided_blocks.append(
                        SubdividedBlock(
                            block_index=len(self.last_subdivided_blocks),
                            source_text=source_text or "",
                            draft_text=draft_text,
                            polished_text=res,
                            is_sensitive=False,
                            fallback_used=False
                        )
                    )
                    return res
                except Exception as retry_err:
                    if not is_safety_block_exception(retry_err):
                        raise

            # Step 2: Recursive subdivision
            can_sub = (
                self.enable_recursive_subdivision
                and depth < self.subdivision_max_depth
                and can_subdivide_text(draft_text, min_lines=self.subdivision_min_lines)
            )
            if can_sub:
                self.subdivisions_count += 1
                left_d, right_d = bisect_text(draft_text)
                left_s, right_s = bisect_text(source_text) if source_text else ("", "")
                line_count = len([l for l in draft_text.splitlines() if l.strip()])
                logger.warning(
                    f"⚠️ Sensitive scene safety block in polisher ({line_count} lines) - "
                    f"subdividing (depth {depth + 1}/{self.subdivision_max_depth})..."
                )
                left_pol = self._polish_with_recursive_subdivision(
                    draft_text=left_d,
                    critique_notes=critique_notes,
                    active_glossary=active_glossary,
                    bible=bible,
                    genre=genre,
                    source_text=left_s if left_s else None,
                    preceding_context=preceding_context,
                    chunk_idx=chunk_idx,
                    total_chunks=total_chunks,
                    depth=depth + 1,
                    iteration=iteration,
                    procedural_graph=procedural_graph,
                    prompt_tracker=prompt_tracker,
                    **sub_kwargs
                )
                left_tail_lines = [l.strip() for l in left_pol.splitlines() if l.strip()]
                left_tail = "\n".join(left_tail_lines[-3:]) if left_tail_lines else preceding_context
                right_pol = self._polish_with_recursive_subdivision(
                    draft_text=right_d,
                    critique_notes=critique_notes,
                    active_glossary=active_glossary,
                    bible=bible,
                    genre=genre,
                    source_text=right_s if right_s else None,
                    preceding_context=left_tail,
                    chunk_idx=chunk_idx,
                    total_chunks=total_chunks,
                    depth=depth + 1,
                    iteration=iteration,
                    procedural_graph=procedural_graph,
                    prompt_tracker=prompt_tracker,
                    **sub_kwargs
                )
                parts = [p.strip() for p in (left_pol, right_pol) if p and p.strip()]
                return "\n\n".join(parts)

            # Step 3: Base case -> Minimal sensitive snippet reached
            self.safety_fallbacks_used += 1
            logger.warning("⚠️ Minimal sensitive snippet in polisher - retaining draft text.")
            self.last_subdivided_blocks.append(
                SubdividedBlock(
                    block_index=len(self.last_subdivided_blocks),
                    source_text=source_text or "",
                    draft_text=draft_text,
                    polished_text=draft_text,
                    is_sensitive=True,
                    fallback_used=True
                )
            )
            return draft_text

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
        procedural_graph: Optional[ProceduralGraph] = None,
        subdivided_blocks: Optional[List[SubdividedBlock]] = None,
        **kwargs: Any
    ) -> str:
        self.last_subdivided_blocks = []
        polish_kwargs = dict(kwargs)
        iteration_val = polish_kwargs.pop("iteration", 1)

        # 1. Check for Stateful Subdivision Pattern from Drafter
        if subdivided_blocks and any(b.is_sensitive for b in subdivided_blocks):
            logger.info(
                f"✨ Polishing using stateful subdivision pattern ({len(subdivided_blocks)} blocks, "
                f"{sum(1 for b in subdivided_blocks if b.is_sensitive)} sensitive)..."
            )
            polished_parts = []
            prev_tail = ""
            for b in subdivided_blocks:
                if b.is_sensitive:
                    logger.warning(f"⚠️ Preserving unpolished draft for sensitive block {b.block_index}.")
                    b.polished_text = b.draft_text
                    polished_parts.append(b.draft_text)
                    tail_lines = [l.strip() for l in b.draft_text.splitlines() if l.strip()]
                    if tail_lines:
                        prev_tail = "\n".join(tail_lines[-3:])
                    self.last_subdivided_blocks.append(b)
                else:
                    block_pol = self._polish_with_recursive_subdivision(
                        draft_text=b.draft_text,
                        critique_notes=critique_notes,
                        active_glossary=active_glossary,
                        bible=bible,
                        genre=genre,
                        source_text=b.source_text if b.source_text else None,
                        preceding_context=prev_tail,
                        depth=0,
                        iteration=iteration_val,
                        procedural_graph=procedural_graph,
                        **polish_kwargs
                    )
                    b.polished_text = block_pol
                    polished_parts.append(block_pol)
                    tail_lines = [l.strip() for l in block_pol.splitlines() if l.strip()]
                    if tail_lines:
                        prev_tail = "\n".join(tail_lines[-3:])
            raw_polished = "\n\n".join([p.strip() for p in polished_parts if p and p.strip()])
            return self._ensure_chapter_title_preserved(draft_text=draft_text, polished_text=raw_polished)

        # 2. Chunked polishing if draft_chunks present
        if draft_chunks and len(draft_chunks) > 1:
            raw_polished = self.polish_chunked(
                draft_chunks=draft_chunks,
                critique_notes=critique_notes,
                active_glossary=active_glossary,
                bible=bible,
                genre=genre,
                source_text=source_text,
                notify_callback=notify_callback,
                rate_limiter=rate_limiter,
                stop_event=stop_event,
                procedural_graph=procedural_graph,
                iteration=iteration_val,
                **polish_kwargs
            )
            return self._ensure_chapter_title_preserved(draft_text=draft_text, polished_text=raw_polished)

        # 3. Single text polishing with recursive subdivision
        raw_polished = self._polish_with_recursive_subdivision(
            draft_text=draft_text,
            critique_notes=critique_notes,
            active_glossary=active_glossary,
            bible=bible,
            genre=genre,
            source_text=source_text,
            preceding_context="",
            depth=0,
            iteration=iteration_val,
            procedural_graph=procedural_graph,
            **polish_kwargs
        )
        return self._ensure_chapter_title_preserved(draft_text=draft_text, polished_text=raw_polished)

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
        procedural_graph: Optional[ProceduralGraph] = None,
        **kwargs: Any
    ) -> str:
        """Polishes a long draft chunk-by-chunk with sliding context to avoid output limits and TPM stalls."""
        from nousetsu.utils.rate_limiter import estimate_tokens

        polished_parts = []
        prev_polished_tail = ""
        total_usage = TokenUsage()
        raw_src_lines = source_text.splitlines(keepends=True) if source_text else None

        for chunk in draft_chunks:
            if stop_event and stop_event.is_set():
                from nousetsu.models.exceptions import BatchStoppedException
                raise BatchStoppedException("Polishing cancelled by user request.")

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
            if not chunk_source and raw_src_lines:
                # Sliced source lines per chunk instead of leaking the full unchunked source text
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

            chunk_kwargs = dict(kwargs)
            if "prompt_tracker" not in chunk_kwargs and hasattr(self, "prompt_tracker"):
                chunk_kwargs["prompt_tracker"] = self.prompt_tracker
            chunk_kwargs.setdefault("iteration", 1)

            chunk_polished = self._polish_single_chunk(
                chunk_draft=chunk_content,
                preceding_context=prev_polished_tail,
                critique_notes=critique_notes,
                active_glossary=active_glossary,
                bible=bible,
                genre=genre,
                source_text=chunk_source,
                chunk_idx=chunk_idx,
                total_chunks=total_chunks,
                procedural_graph=procedural_graph,
                **chunk_kwargs
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
        total_chunks: int = 1,
        prompt_tracker: Optional[Any] = None,
        iteration: int = 1,
        procedural_graph: Optional[ProceduralGraph] = None,
        **kwargs: Any
    ) -> str:
        sub_kwargs = dict(kwargs)
        sub_kwargs.pop("iteration", None)
        sub_kwargs.pop("procedural_graph", None)
        sub_kwargs.pop("prompt_tracker", None)
        text = self._polish_with_recursive_subdivision(
            draft_text=chunk_draft,
            critique_notes=critique_notes,
            active_glossary=active_glossary,
            bible=bible,
            genre=genre,
            source_text=source_text,
            preceding_context=preceding_context,
            chunk_idx=chunk_idx,
            total_chunks=total_chunks,
            depth=0,
            iteration=iteration,
            procedural_graph=procedural_graph,
            prompt_tracker=prompt_tracker,
            **sub_kwargs
        )
        if chunk_idx == 1:
            text = self._ensure_chapter_title_preserved(draft_text=chunk_draft, polished_text=text)
        return text
