"""Fidelity, tone, and terminology critique agent."""
import json
import re
from typing import Any, List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.agents.llm import extract_text_from_message, extract_usage_from_message, get_llm
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.models.metadata import QualityAudit, TokenUsage
from nousetsu.prompts.templates import CRITIQUE_SYSTEM_PROMPT
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.language import detect_language


class CritiqueAgent:
    """Evaluates draft quality, glossary adherence, and zero-anaphora pronoun resolution."""

    def __init__(
        self,
        model_name: str = "gemma-4-26b-a4b-it",
        fallback_model: Optional[str] = None,
        chunker: Optional[Any] = None
    ):
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.llm = get_llm(model_name=model_name, fallback_model=fallback_model, temperature=0.1)
        self.last_usage: TokenUsage = TokenUsage()
        self.chunker = chunker

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
                d_start = max(0, int(idx / num_chunks * total_d_lines))
                d_end = min(total_d_lines, int((idx + 1) / num_chunks * total_d_lines))
                d_content = "".join(draft_lines[d_start:d_end])
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
                s_start = max(0, int(idx / num_chunks * total_s_lines))
                s_end = min(total_s_lines, int((idx + 1) / num_chunks * total_s_lines))
                s_content = "".join(src_lines[s_start:s_end])
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
        total_chunks: int = 1
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

        sys_msg = CRITIQUE_SYSTEM_PROMPT.format(
            source_lang=bible.source_language,
            target_lang=bible.target_language,
            characters=chars_str,
            glossary=gloss_str,
            skills_section=skills_section
        )

        chunk_info = f" (Part {chunk_idx} of {total_chunks})" if total_chunks > 1 else ""
        user_content = (
            f"Please evaluate the fidelity, style, and terminology consistency of this fictional translation excerpt{chunk_info}:\n\n"
            f"### Original Source Text ({bible.source_language}):\n{source_text[:50000]}\n\n"
            f"### Draft Translation ({bible.target_language}):\n{draft_text[:50000]}"
        )

        response = self.llm.invoke([
            SystemMessage(content=sys_msg),
            HumanMessage(content=user_content)
        ])
        self.last_usage = extract_usage_from_message(response)

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
        **kwargs: Any
    ) -> Tuple[QualityAudit, str]:
        """Audits translation chunk-by-chunk to prevent single-prompt safety blocks and context saturation."""
        from nousetsu.utils.rate_limiter import estimate_tokens

        fidelity_scores: List[float] = []
        style_scores: List[float] = []
        glossary_pcts: List[float] = []
        all_warnings: List[str] = []
        notes_list: List[str] = []
        total_usage = TokenUsage()

        for chunk in chunks:
            if stop_event and stop_event.is_set():
                break

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
                total_chunks=total_chunks
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
                **kwargs
            )

        audit, critique_notes = self._evaluate_single(
            source_text=source_text,
            draft_text=draft_text,
            bible=bible,
            active_characters=active_characters,
            active_glossary=active_glossary,
            genre=genre
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
