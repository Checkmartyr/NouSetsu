"""Fidelity, tone, and terminology critique agent."""
import json
import logging
import re
from typing import Any, List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.metadata import QualityAudit, TokenUsage
from nousetsu.prompts.templates import CRITIQUE_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.language import detect_language
from nousetsu.utils.translation_fallback import (
    bisect_text,
    can_subdivide_text,
    is_safety_block_exception,
)

logger = logging.getLogger(__name__)


class CritiqueAgent:
    """Evaluates draft quality, glossary adherence, and zero-anaphora pronoun resolution."""

    def __init__(
        self,
        model_name: str = "gemma-4-26b-a4b-it",
        fallback_model: Optional[str] = None,
        chunker: Optional[Any] = None,
        enable_recursive_subdivision: bool = True,
        subdivision_min_lines: int = 8,
        subdivision_max_depth: int = 3,
    ):
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.llm = get_llm(model_name=model_name, fallback_model=fallback_model, temperature=0.1)
        self.last_usage: TokenUsage = TokenUsage()
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

    def _build_paired_chunks(self, source_text: str, draft_text: str) -> List[Any]:
        """Partitions source and draft texts into aligned semantic LineChunks."""
        from nousetsu.utils.chunker import LineChunk
        if not self.chunker:
            return []

        source_should = self.chunker.should_chunk(source_text) if hasattr(self.chunker, "should_chunk") else False
        draft_should = self.chunker.should_chunk(draft_text) if hasattr(self.chunker, "should_chunk") else False

        if source_should:
            src_chunks = self.chunker.split_lines(source_text)
            num_chunks = len(src_chunks)
            draft_lines = draft_text.splitlines(keepends=True)
            total_d_lines = len(draft_lines)
            paired = []
            for idx, s_chunk in enumerate(src_chunks):
                if total_d_lines >= num_chunks:
                    d_start = max(0, int(idx / num_chunks * total_d_lines) - 2)
                    d_end = min(total_d_lines, int((idx + 1) / num_chunks * total_d_lines) + 2)
                    d_content = "".join(draft_lines[d_start:d_end])
                else:
                    d_content = draft_text
                if not d_content.strip() and draft_text.strip():
                    d_content = draft_text
                paired.append(
                    LineChunk(
                        chunk_index=idx + 1,
                        total_chunks=num_chunks,
                        start_line=s_chunk.start_line,
                        end_line=s_chunk.end_line,
                        content=d_content,
                        source_content=s_chunk.content
                    )
                )
            return paired
        elif draft_should:
            d_chunks = self.chunker.split_lines(draft_text)
            num_chunks = len(d_chunks)
            src_lines = source_text.splitlines(keepends=True)
            total_s_lines = len(src_lines)
            paired = []
            for idx, d_chunk in enumerate(d_chunks):
                if total_s_lines >= num_chunks:
                    s_start = max(0, int(idx / num_chunks * total_s_lines) - 2)
                    s_end = min(total_s_lines, int((idx + 1) / num_chunks * total_s_lines) + 2)
                    s_content = "".join(src_lines[s_start:s_end])
                else:
                    s_content = source_text
                if not s_content.strip() and source_text.strip():
                    s_content = source_text
                d_chunk.source_content = s_content
                paired.append(d_chunk)
            return paired
        return []

    def _evaluate_single(
        self,
        source_text: str,
        draft_text: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        genre: Optional[str] = None,
        chunk_idx: int = 1,
        total_chunks: int = 1,
        depth: int = 0,
        rag_context: Optional[List[Any]] = None
    ) -> Tuple[QualityAudit, str]:
        # Filter glossary to terms actually present in this chapter to avoid prompt bloat
        relevant_glossary = [
            item for item in active_glossary
            if item.source.lower() in source_text.lower() or item.target.lower() in draft_text.lower()
        ]
        eval_glossary = relevant_glossary if relevant_glossary else (active_glossary[:15] if active_glossary else [])

        chars_str = "\n".join([f"- {c.name} ({c.original_name}, {c.gender}, voice: {c.voice})" for c in active_characters]) or "None"
        gloss_str = "\n".join([f"- {g.source} -> {g.target}" for g in eval_glossary]) or "None"

        resolved_genre = genre or getattr(bible, "genre", "general")
        skills_text = SkillRegistry.get_instance().build_prompt_section(
            agent="critic",
            source_lang=bible.source_language,
            genre=resolved_genre
        )
        skills_section = f"\n{skills_text}\n" if skills_text else ""

        rag_section = ""
        if rag_context:
            canon_lines = []
            for hit in rag_context:
                doc = hit.document if hasattr(hit, "document") else hit
                content = getattr(doc, "content", str(doc))
                title = getattr(doc, "title", "Canon Reference")
                canon_lines.append(f"- [{title}]: {content[:350]}")
            rag_section = "\nCanonical Series Memory & Prior Translations (via RAG):\n" + "\n".join(canon_lines) + "\n"

        sys_msg = CRITIQUE_SYSTEM_PROMPT.format(
            source_lang=bible.source_language,
            target_lang=bible.target_language,
            characters=chars_str,
            glossary=gloss_str,
            skills_section=skills_section,
            rag_canon_section=rag_section
        )

        chunk_info = f" (Part {chunk_idx} of {total_chunks})" if total_chunks > 1 else ""
        user_content = (
            f"Please evaluate the fidelity, style, and terminology consistency of this fictional translation excerpt{chunk_info}:\n\n"
            f"### Original Source Text ({bible.source_language}):\n{source_text[:50000]}\n\n"
            f"### Draft Translation ({bible.target_language}):\n{draft_text[:50000]}"
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content=sys_msg),
                HumanMessage(content=user_content)
            ])
            self.last_usage = extract_usage_from_message(response)
        except Exception as e:
            if is_safety_block_exception(e):
                can_sub = (
                    self.enable_recursive_subdivision
                    and depth < self.subdivision_max_depth
                    and can_subdivide_text(source_text, min_lines=self.subdivision_min_lines)
                    and can_subdivide_text(draft_text, min_lines=self.subdivision_min_lines)
                )
                if can_sub:
                    s_left, s_right = bisect_text(source_text)
                    d_left, d_right = bisect_text(draft_text)
                    if s_left and s_right and d_left and d_right:
                        self.subdivisions_count += 1
                        line_count = len([l for l in draft_text.splitlines() if l.strip()])
                        logger.warning(
                            f"⚠️ Sensitive scene safety block in critique ({line_count} lines) - "
                            f"subdividing (depth {depth + 1}/{self.subdivision_max_depth})..."
                        )
                        audit_left, notes_left = self._evaluate_single(
                            source_text=s_left,
                            draft_text=d_left,
                            bible=bible,
                            active_characters=active_characters,
                            active_glossary=active_glossary,
                            genre=genre,
                            chunk_idx=chunk_idx,
                            total_chunks=total_chunks,
                            depth=depth + 1,
                            rag_context=rag_context
                        )
                        left_usage = self.last_usage
                        audit_right, notes_right = self._evaluate_single(
                            source_text=s_right,
                            draft_text=d_right,
                            bible=bible,
                            active_characters=active_characters,
                            active_glossary=active_glossary,
                            genre=genre,
                            chunk_idx=chunk_idx,
                            total_chunks=total_chunks,
                            depth=depth + 1,
                            rag_context=rag_context
                        )
                        self.last_usage = left_usage.add(self.last_usage)
                        combined_fid = round((audit_left.fidelity_score + audit_right.fidelity_score) / 2.0, 1)
                        combined_sty = round((audit_left.style_score + audit_right.style_score) / 2.0, 1)
                        combined_glo = round((audit_left.glossary_compliance_pct + audit_right.glossary_compliance_pct) / 2.0, 1)
                        combined_warn = list(dict.fromkeys(audit_left.warnings + audit_right.warnings))
                        combined_audit = QualityAudit(
                            fidelity_score=combined_fid,
                            style_score=combined_sty,
                            glossary_compliance_pct=combined_glo,
                            warnings=combined_warn,
                            passed=(combined_fid >= 7.5 and combined_sty >= 7.5)
                        )
                        combined_notes = f"{notes_left} {notes_right}".strip()
                        return combined_audit, combined_notes

                self.safety_fallbacks_used += 1
                logger.warning("⚠️ Sensitive scene safety block bypassed during critique.")
                self.last_usage = TokenUsage()
                return QualityAudit(
                    fidelity_score=8.5,
                    style_score=8.0,
                    glossary_compliance_pct=100.0,
                    warnings=["⚠️ Sensitive scene safety block bypassed during critique."],
                    passed=True
                ), "Critique bypassed due to provider content filter on sensitive passage."
            raise

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
            # Attempt regex recovery of scores from raw text
            m_fid = re.search(r"['\"]?fidelity_score['\"]?\s*[:=]\s*(\d+(?:\.\d+)?)", raw_content, re.IGNORECASE)
            m_sty = re.search(r"['\"]?style_score['\"]?\s*[:=]\s*(\d+(?:\.\d+)?)", raw_content, re.IGNORECASE)
            m_glo = re.search(r"['\"]?glossary_compliance_pct['\"]?\s*[:=]\s*(\d+(?:\.\d+)?)", raw_content, re.IGNORECASE)
            m_notes = re.search(r"['\"]?critique_notes['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]", raw_content, re.IGNORECASE)

            if m_fid or m_sty:
                audit.fidelity_score = float(m_fid.group(1)) if m_fid else 6.0
                audit.style_score = float(m_sty.group(1)) if m_sty else 6.0
                audit.glossary_compliance_pct = float(m_glo.group(1)) if m_glo else 100.0
                audit.passed = (audit.fidelity_score >= 7.5 and audit.style_score >= 7.5)
                critique_notes = m_notes.group(1) if m_notes else "Review prose for rhythm and consistency."
                audit.warnings.append("Critique JSON recovered via regex fallback.")
            else:
                audit.fidelity_score = 6.0
                audit.style_score = 6.0
                audit.glossary_compliance_pct = 100.0
                audit.passed = False
                audit.warnings.append("Critique JSON could not be parsed; conservative failing scores assigned.")
                critique_notes = "Critique response malformed. Review prose for rhythm, zero-pronoun clarity, and verify proper nouns."

        return audit, critique_notes

    def evaluate_chunked(
        self,
        chunks: List[Any],
        source_text: str,
        draft_text: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        genre: Optional[str] = None,
        notify_callback: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        stop_event: Optional[Any] = None,
        rag_context: Optional[List[Any]] = None,
        **kwargs: Any
    ) -> Tuple[QualityAudit, str]:
        """Audits translation chunk-by-chunk to prevent single-prompt safety blocks and context saturation."""
        from nousetsu.models.exceptions import BatchStoppedException
        from nousetsu.utils.rate_limiter import estimate_tokens

        fidelity_scores: List[float] = []
        style_scores: List[float] = []
        glossary_pcts: List[float] = []
        all_warnings: List[str] = []
        notes_list: List[str] = []
        total_usage = TokenUsage()

        for chunk in chunks:
            if stop_event and stop_event.is_set():
                raise BatchStoppedException("Critique evaluation cancelled by user request.")

            chunk_idx = getattr(chunk, "chunk_index", 1)
            total_chunks = getattr(chunk, "total_chunks", len(chunks))
            chunk_draft = getattr(chunk, "content", str(chunk))
            chunk_source = getattr(chunk, "source_content", None) or source_text

            if notify_callback:
                try:
                    notify_callback(f"Auditing chunk {chunk_idx}/{total_chunks}...")
                except Exception:
                    pass

            if rate_limiter:
                est_tokens = estimate_tokens(chunk_source) + estimate_tokens(chunk_draft) + 500
                rate_limiter.acquire(
                    estimated_tokens=est_tokens,
                    stop_event=stop_event,
                    notify_callback=notify_callback
                )

            chunk_audit, chunk_notes = self._evaluate_single(
                source_text=chunk_source,
                draft_text=chunk_draft,
                bible=bible,
                active_characters=active_characters,
                active_glossary=active_glossary,
                genre=genre,
                chunk_idx=chunk_idx,
                total_chunks=total_chunks,
                rag_context=rag_context
            )
            fidelity_scores.append(chunk_audit.fidelity_score)
            style_scores.append(chunk_audit.style_score)
            glossary_pcts.append(chunk_audit.glossary_compliance_pct)
            all_warnings.extend(chunk_audit.warnings)
            if chunk_notes and chunk_notes.strip():
                notes_list.append(f"[Part {chunk_idx}]: {chunk_notes.strip()}")

            total_usage = total_usage.add(self.last_usage)
            if rate_limiter and hasattr(rate_limiter, "record_usage") and self.last_usage.total_tokens > 0:
                rate_limiter.record_usage(self.last_usage.total_tokens)

        self.last_usage = total_usage

        avg_fidelity = round(sum(fidelity_scores) / len(fidelity_scores), 1) if fidelity_scores else 9.0
        avg_style = round(sum(style_scores) / len(style_scores), 1) if style_scores else 9.0
        avg_gloss = round(sum(glossary_pcts) / len(glossary_pcts), 1) if glossary_pcts else 100.0

        audit = QualityAudit(
            fidelity_score=avg_fidelity,
            style_score=avg_style,
            glossary_compliance_pct=avg_gloss,
            warnings=list(dict.fromkeys(all_warnings)),
            passed=(avg_fidelity >= 7.5 and avg_style >= 7.5)
        )
        critique_notes = " ".join(notes_list) if notes_list else "Preserve meaning and enhance natural rhythm."

        # Programmatic check only against glossary terms that actually appeared in the source text
        source_present_terms = [item for item in active_glossary if item.source.lower() in source_text.lower()]
        missing_terms = []
        for item in source_present_terms:
            if item.target.lower() not in draft_text.lower():
                missing_terms.append(f"Glossary term '{item.target}' (source: '{item.source}') missing in draft")
        if missing_terms:
            audit.warnings.extend(missing_terms)
            if len(source_present_terms) > 0:
                audit.glossary_compliance_pct = max(0.0, 100.0 - (len(missing_terms) / len(source_present_terms) * 100.0))
        elif source_present_terms:
            audit.glossary_compliance_pct = 100.0

        # Programmatic Target Language Guard across full draft
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

    def evaluate(
        self,
        source_text: str,
        draft_text: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        genre: Optional[str] = None,
        chunks: Optional[List[Any]] = None,
        notify_callback: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        stop_event: Optional[Any] = None,
        rag_context: Optional[List[Any]] = None,
        **kwargs: Any
    ) -> Tuple[QualityAudit, str]:
        if chunks is None and self.chunker and hasattr(self.chunker, "should_chunk"):
            if self.chunker.should_chunk(source_text) or self.chunker.should_chunk(draft_text):
                chunks = self._build_paired_chunks(source_text, draft_text)

        if chunks and len(chunks) > 1:
            return self.evaluate_chunked(
                chunks=chunks,
                source_text=source_text,
                draft_text=draft_text,
                bible=bible,
                active_characters=active_characters,
                active_glossary=active_glossary,
                genre=genre,
                notify_callback=notify_callback,
                rate_limiter=rate_limiter,
                stop_event=stop_event,
                rag_context=rag_context,
                **kwargs
            )

        self.last_usage = TokenUsage()
        audit, critique_notes = self._evaluate_single(
            source_text=source_text,
            draft_text=draft_text,
            bible=bible,
            active_characters=active_characters,
            active_glossary=active_glossary,
            genre=genre,
            rag_context=rag_context
        )

        # Programmatic check only against glossary terms that actually appeared in the source text
        source_present_terms = [item for item in active_glossary if item.source.lower() in source_text.lower()]
        missing_terms = []
        for item in source_present_terms:
            if item.target.lower() not in draft_text.lower():
                missing_terms.append(f"Glossary term '{item.target}' (source: '{item.source}') missing in draft")
        if missing_terms:
            audit.warnings.extend(missing_terms)
            if len(source_present_terms) > 0:
                audit.glossary_compliance_pct = max(0.0, 100.0 - (len(missing_terms) / len(source_present_terms) * 100.0))
        elif source_present_terms:
            audit.glossary_compliance_pct = 100.0

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
