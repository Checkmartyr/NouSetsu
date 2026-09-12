"""LangGraph translation workflow wiring the multi-agent pipeline."""
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, Optional
from langgraph.graph import END, StateGraph
from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.agents.llm import invoke_with_retry
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.models.exceptions import BatchStoppedException
from nousetsu.models.metadata import PipelineStage, StageStatus, StepTokenUsage, TokenUsage
from nousetsu.models.state import TranslationState
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.chunker import LineSemanticChunker
from nousetsu.utils.genre import detect_genre
from nousetsu.utils.language import detect_language
from nousetsu.utils.rate_limiter import SlidingWindowRateLimiter, estimate_tokens



class NovelTranslationWorkflow:
    """Orchestrates document-level novel translation with LangGraph."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        fallback_model: Optional[str] = None,
        extractor_model: Optional[str] = None,
        drafter_model: Optional[str] = None,
        critic_model: Optional[str] = None,
        polisher_model: Optional[str] = None,
        chronicler_model: Optional[str] = None,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
        max_review_loops: int = 3,
        quality_threshold: float = 8.5,
        enable_chunking: bool = True,
        chunk_threshold_lines: int = 85,
        target_chunk_lines: int = 70,
        chunk_overlap_lines: int = 3,
        extractor_pg: Optional[Any] = None,
        drafter_pg: Optional[Any] = None
    ):
        effective_model = model_name or os.environ.get("NOVEL_MODEL") or os.environ.get("DEFAULT_MODEL") or "gemini-3.1-flash-lite"
        self.model_name = effective_model
        is_mock = effective_model.startswith("mock") or effective_model.startswith("test")
        default_agent = effective_model if is_mock else None

        self.fallback_model = fallback_model or default_agent or os.environ.get("NOVEL_FALLBACK_MODEL") or "gemini-3.5-flash-lite"
        self.extractor_model = extractor_model or default_agent or os.environ.get("NOVEL_EXTRACTOR_MODEL") or "gemini-3.1-flash-lite"
        self.drafter_model = drafter_model or default_agent or os.environ.get("NOVEL_DRAFTER_MODEL") or "gemini-3.5-flash-lite"
        self.critic_model = critic_model or default_agent or os.environ.get("NOVEL_CRITIC_MODEL") or "gemma-4-26b-a4b-it"
        self.polisher_model = polisher_model or default_agent or os.environ.get("NOVEL_POLISHER_MODEL") or "gemini-3.5-flash-lite"
        self.chronicler_model = chronicler_model or default_agent or os.environ.get("NOVEL_CHRONICLER_MODEL") or "gemma-4-26b-a4b-it"

        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter()
        self.max_review_loops = max_review_loops
        self.quality_threshold = quality_threshold
        self.enable_chunking = enable_chunking
        self.chunker = (
            LineSemanticChunker(
                threshold_lines=chunk_threshold_lines,
                target_chunk_lines=target_chunk_lines,
                overlap_lines=chunk_overlap_lines
            )
            if enable_chunking
            else None
        )
        self.current_stage: PipelineStage = PipelineStage.NONE
        self.extractor = EntityExtractorAgent(
            model_name=self.extractor_model,
            fallback_model=fallback_model,
            procedural_graph=extractor_pg
        )
        self.drafter = ContextAwareDrafterAgent(
            model_name=self.drafter_model,
            fallback_model=fallback_model,
            procedural_graph=drafter_pg
        )
        self.critic = CritiqueAgent(model_name=self.critic_model, fallback_model=fallback_model)
        self.polisher = PolishingAgent(model_name=self.polisher_model, fallback_model=fallback_model)
        self.chronicler = ChroniclerAgent(model_name=self.chronicler_model, fallback_model=fallback_model)
        self.stage_callback: Optional[Callable[[PipelineStage, str, float], None]] = None
        self.stop_event: Optional[threading.Event] = None
        self.last_state: Optional[TranslationState] = None
        self.graph = self._build_graph()

    def _notify(self, stage: PipelineStage, msg: str, percent: float) -> None:
        if self.stage_callback:
            try:
                self.stage_callback(stage, msg, percent)
            except Exception:
                pass

    def _build_graph(self):
        builder = StateGraph(TranslationState)

        builder.add_node("extract", self._extract_step)
        builder.add_node("draft", self._draft_step)
        builder.add_node("critique", self._critique_step)
        builder.add_node("polish", self._polish_step)
        builder.add_node("chronicle", self._chronicle_step)

        builder.set_entry_point("extract")
        builder.add_edge("extract", "draft")
        builder.add_edge("draft", "critique")
        builder.add_conditional_edges(
            "critique",
            self._route_after_critique,
            {
                "polish": "polish",
                "chronicle": "chronicle"
            }
        )
        builder.add_conditional_edges(
            "polish",
            self._route_after_polish,
            {
                "critique": "critique",
                "chronicle": "chronicle"
            }
        )
        builder.add_edge("chronicle", END)

        return builder.compile()

    def _route_after_critique(self, state: TranslationState) -> str:
        # Pass 1: only raw draft was critiqued; must polish into literary prose
        if state.review_iteration <= 1 or not state.polished_text:
            return "polish"

        # Pass 2+: check quality threshold or loop exhaustion
        has_lang_regression = any("LANGUAGE REGRESSION" in str(w) for w in state.quality_audit.warnings)
        passed_threshold = (
            state.quality_audit.fidelity_score >= state.quality_threshold
            and state.quality_audit.style_score >= state.quality_threshold
            and state.quality_audit.passed
            and not has_lang_regression
        )
        reached_max = state.review_iteration > state.max_review_loops
        if passed_threshold or reached_max:
            return "chronicle"
        return "polish"

    def _route_after_polish(self, state: TranslationState) -> str:
        if state.max_review_loops <= 1:
            return "chronicle"
        if state.review_iteration > state.max_review_loops:
            return "chronicle"
        return "critique"

    def _check_stop(self, state: TranslationState, stage: PipelineStage) -> None:
        self.last_state = state
        self.current_stage = stage
        if self.stop_event and self.stop_event.is_set():
            raise BatchStoppedException(f"Translation stopped by user before {stage.value} stage.")

    def _extract_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.EXTRACTION)
        self.current_stage = PipelineStage.EXTRACTION
        step_start = time.time()

        ext_skills = [
            s.name for s in SkillRegistry.get_instance().get_active_skills(
                agent="extractor",
                source_lang=state.novel_bible.source_language,
                genre=state.genre
            )
        ]
        skills_suffix = f" [Skills: {', '.join(ext_skills)}]" if ext_skills else ""
        self._notify(PipelineStage.EXTRACTION, f"Extracting novel entities & terminology{skills_suffix}...", 15.0)

        # If already extracted in checkpoint, skip re-extracting
        if state.extracted_terms or state.extracted_characters:
            return {
                "current_stage": PipelineStage.EXTRACTION,
                "active_glossary": state.novel_bible.glossary + state.extracted_terms,
                "active_characters": state.novel_bible.characters + state.extracted_characters
            }

        state.novel_bible.genre = state.genre
        est_extract = estimate_tokens(state.source_text[:12000]) + 600
        new_chars, new_terms, active_terms = invoke_with_retry(
            self.extractor.extract,
            state.source_text,
            state.novel_bible,
            notify_callback=lambda msg: self._notify(PipelineStage.EXTRACTION, msg, 15.0),
            rate_limiter=self.rate_limiter,
            estimated_tokens=est_extract,
            stop_event=self.stop_event
        )
        
        all_chars = list(state.novel_bible.characters) + new_chars
        all_glossary = list(state.novel_bible.glossary) + new_terms

        extract_duration = round(time.time() - step_start, 2)
        extract_usage = getattr(self.extractor, "last_usage", TokenUsage())
        extract_record = StepTokenUsage(
            stage=PipelineStage.EXTRACTION,
            step_name="Extraction",
            iteration=1,
            model=getattr(self.extractor, "last_model_used", self.extractor_model),
            duration_seconds=extract_duration,
            usage=extract_usage
        )
        updated_token_records = list(state.step_token_records) + [extract_record]

        updated_skills = dict(state.active_skills)
        updated_skills["extraction"] = ext_skills

        return {
            "current_stage": PipelineStage.EXTRACTION,
            "extracted_characters": new_chars,
            "extracted_terms": new_terms,
            "active_characters": all_chars,
            "active_glossary": all_glossary,
            "active_skills": updated_skills,
            "step_token_records": updated_token_records
        }

    def _draft_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.DRAFTING)
        self.current_stage = PipelineStage.DRAFTING
        step_start = time.time()

        dft_skills = [
            s.name for s in SkillRegistry.get_instance().get_active_skills(
                agent="drafter",
                source_lang=state.novel_bible.source_language,
                genre=state.genre
            )
        ]
        skills_suffix = f" [Skills: {', '.join(dft_skills)}]" if dft_skills else ""
        self._notify(PipelineStage.DRAFTING, f"Drafting novelistic translation{skills_suffix}...", 35.0)

        # If draft already exists in checkpoint, retain it
        if state.draft_text:
            return {"current_stage": PipelineStage.DRAFTING}

        state.novel_bible.genre = state.genre

        source_chunks = None
        if self.chunker and self.chunker.should_chunk(state.source_text):
            source_chunks = self.chunker.split_lines(state.source_text)
            self._notify(
                PipelineStage.DRAFTING,
                f"Divided chapter into {len(source_chunks)} line chunks (target: {self.chunker.target_chunk_lines} lines/chunk)...",
                35.0
            )

        if source_chunks and len(source_chunks) > 1:
            est_draft = int(estimate_tokens(source_chunks[0].content) * 1.5) + 1500
        else:
            est_draft = int(estimate_tokens(state.source_text) * 1.5) + 2000

        current_folder = Path(state.source_file).parent.name if state.source_file else None
        cross_folder = getattr(state.novel_bible, "cross_folder_summaries", True)
        if hasattr(state.novel_bible, "get_rolling_context"):
            active_summaries = state.novel_bible.get_rolling_context(
                folder=current_folder,
                current_chapter_num=state.chapter_num,
                limit=3,
                cross_folder=cross_folder
            )
        elif hasattr(state.novel_bible, "get_summaries_for_folder"):
            active_summaries = state.novel_bible.get_summaries_for_folder(current_folder)
        else:
            active_summaries = state.novel_bible.summaries

        draft = invoke_with_retry(
            self.drafter.draft,
            source_text=state.source_text,
            bible=state.novel_bible,
            active_characters=state.active_characters,
            active_glossary=state.active_glossary,
            rolling_summaries=active_summaries,
            genre=state.genre,
            chunks=source_chunks,
            notify_callback=lambda msg: self._notify(PipelineStage.DRAFTING, msg, 35.0),
            rate_limiter=self.rate_limiter,
            estimated_tokens=est_draft,
            stop_event=self.stop_event
        )

        draft_duration = round(time.time() - step_start, 2)
        chunk_count = len(source_chunks) if source_chunks else 1
        draft_usage = getattr(self.drafter, "last_usage", TokenUsage())
        draft_record = StepTokenUsage(
            stage=PipelineStage.DRAFTING,
            step_name="Drafting",
            iteration=1,
            model=getattr(self.drafter, "last_model_used", self.drafter_model),
            chunk_count=chunk_count,
            duration_seconds=draft_duration,
            usage=draft_usage
        )
        updated_token_records = list(state.step_token_records) + [draft_record]

        updated_skills = dict(state.active_skills)
        updated_skills["drafting"] = dft_skills

        return {
            "current_stage": PipelineStage.DRAFTING,
            "draft_text": draft,
            "active_skills": updated_skills,
            "step_token_records": updated_token_records
        }

    def _critique_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.CRITIQUE)
        self.current_stage = PipelineStage.CRITIQUE
        step_start = time.time()

        crt_skills = [
            s.name for s in SkillRegistry.get_instance().get_active_skills(
                agent="critic",
                source_lang=state.novel_bible.source_language,
                genre=state.genre
            )
        ]
        skills_suffix = f" [Skills: {', '.join(crt_skills)}]" if crt_skills else ""

        is_initial_draft = (state.review_iteration == 1 and not state.polished_text)
        current_iter = state.review_iteration if is_initial_draft else state.review_iteration + 1
        display_iter = min(current_iter, state.max_review_loops)

        if is_initial_draft:
            self._notify(
                PipelineStage.CRITIQUE,
                f"Auditing fidelity, tone, and glossary adherence (Pass {display_iter}/{state.max_review_loops}){skills_suffix}...",
                60.0
            )
            # If critique notes already exist from paused checkpoint, retain
            if state.critique_notes and state.quality_audit.fidelity_score > 0:
                return {
                    "current_stage": PipelineStage.CRITIQUE,
                    "review_iteration": current_iter
                }
            text_to_audit = state.draft_text
        else:
            self._notify(
                PipelineStage.CRITIQUE,
                f"Re-auditing polished translation (Pass {display_iter}/{state.max_review_loops}){skills_suffix}...",
                60.0
            )
            text_to_audit = state.polished_text

        state.novel_bible.genre = state.genre
        est_critique = estimate_tokens(state.source_text) + estimate_tokens(text_to_audit) + 500
        audit, notes = invoke_with_retry(
            self.critic.evaluate,
            source_text=state.source_text,
            draft_text=text_to_audit,
            bible=state.novel_bible,
            active_characters=state.active_characters,
            active_glossary=state.active_glossary,
            notify_callback=lambda msg: self._notify(PipelineStage.CRITIQUE, msg, 60.0),
            rate_limiter=self.rate_limiter,
            estimated_tokens=est_critique,
            stop_event=self.stop_event
        )

        # Best-candidate regression guard
        current_score = (audit.fidelity_score + audit.style_score) / 2.0
        best_audit = state.best_audit
        best_text = state.best_polished_text

        is_source_lang = False
        if state.novel_bible.target_language.lower() != state.novel_bible.source_language.lower():
            det_audit = detect_language(text_to_audit)
            if det_audit and det_audit.lower() == state.novel_bible.source_language.lower():
                is_source_lang = True
            if any("LANGUAGE REGRESSION" in str(w) for w in audit.warnings):
                is_source_lang = True

        if not is_source_lang:
            if is_initial_draft:
                best_audit = audit
                best_text = state.best_polished_text or ""
            else:
                if best_audit is None:
                    best_audit = audit
                    best_text = text_to_audit
                else:
                    prev_best_score = (best_audit.fidelity_score + best_audit.style_score) / 2.0
                    if current_score >= prev_best_score:
                        best_audit = audit
                        best_text = text_to_audit

        critique_duration = round(time.time() - step_start, 2)
        critique_usage = getattr(self.critic, "last_usage", TokenUsage())
        critique_record = StepTokenUsage(
            stage=PipelineStage.CRITIQUE,
            step_name=f"Critique (Pass {display_iter})",
            iteration=current_iter,
            model=getattr(self.critic, "last_model_used", self.critic_model),
            duration_seconds=critique_duration,
            usage=critique_usage
        )
        updated_token_records = list(state.step_token_records) + [critique_record]

        updated_skills = dict(state.active_skills)
        updated_skills["critique"] = crt_skills

        return {
            "current_stage": PipelineStage.CRITIQUE,
            "quality_audit": audit,
            "critique_notes": notes,
            "review_iteration": current_iter,
            "best_audit": best_audit,
            "best_polished_text": best_text,
            "active_skills": updated_skills,
            "step_token_records": updated_token_records
        }

    def _polish_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.POLISHING)
        self.current_stage = PipelineStage.POLISHING
        step_start = time.time()

        pol_skills = [
            s.name for s in SkillRegistry.get_instance().get_active_skills(
                agent="polisher",
                source_lang=state.novel_bible.source_language,
                genre=state.genre
            )
        ]
        skills_suffix = f" [Skills: {', '.join(pol_skills)}]" if pol_skills else ""

        is_initial_draft = (state.review_iteration <= 1)
        display_iter = min(state.review_iteration, state.max_review_loops)
        self._notify(
            PipelineStage.POLISHING,
            f"Polishing prose cadence (Pass {display_iter}/{state.max_review_loops}){skills_suffix}...",
            80.0
        )

        # Check checkpoint resume for pass 1 if paused previously
        if is_initial_draft and state.polished_text and not state.best_polished_text:
            return {
                "current_stage": PipelineStage.POLISHING,
                "best_polished_text": state.polished_text
            }

        base_text = state.draft_text if is_initial_draft else (state.polished_text or state.best_polished_text or state.draft_text)

        # Sanity check: if base_text is in source language while draft_text is in target language, revert to draft_text
        if state.novel_bible.target_language.lower() != state.novel_bible.source_language.lower():
            if (
                detect_language(base_text) == state.novel_bible.source_language
                and detect_language(state.draft_text) != state.novel_bible.source_language
            ):
                base_text = state.draft_text

        state.novel_bible.genre = state.genre

        draft_chunks = None
        if self.chunker and self.chunker.should_chunk(base_text):
            draft_chunks = self.chunker.split_lines(base_text)
            self._notify(
                PipelineStage.POLISHING,
                f"Divided draft into {len(draft_chunks)} line chunks for paced polishing...",
                80.0
            )

        if draft_chunks and len(draft_chunks) > 1:
            est_polish = estimate_tokens(draft_chunks[0].content) * 2 + 1000
        else:
            est_polish = estimate_tokens(base_text) * 2 + 1000

        polished = invoke_with_retry(
            self.polisher.polish,
            draft_text=base_text,
            critique_notes=state.critique_notes,
            active_glossary=state.active_glossary,
            bible=state.novel_bible,
            genre=state.genre,
            source_text=state.source_text,
            draft_chunks=draft_chunks,
            notify_callback=lambda msg: self._notify(PipelineStage.POLISHING, msg, 80.0),
            rate_limiter=self.rate_limiter,
            estimated_tokens=est_polish,
            stop_event=self.stop_event
        )

        # Language regression guard on polished output:
        # If output reverted to source language while target is distinct, retain target language draft
        if state.novel_bible.target_language.lower() != state.novel_bible.source_language.lower():
            det_pol = detect_language(polished)
            if det_pol and det_pol.lower() == state.novel_bible.source_language.lower():
                self._notify(
                    PipelineStage.POLISHING,
                    f"Warning: Polisher returned {state.novel_bible.source_language}; retaining {state.novel_bible.target_language} draft.",
                    80.0
                )
                polished = state.draft_text

        best_text = polished if is_initial_draft else (state.best_polished_text or polished)

        polish_duration = round(time.time() - step_start, 2)
        chunk_count = len(draft_chunks) if draft_chunks else 1
        polish_usage = getattr(self.polisher, "last_usage", TokenUsage())
        polish_record = StepTokenUsage(
            stage=PipelineStage.POLISHING,
            step_name=f"Polishing (Pass {display_iter})",
            iteration=display_iter,
            model=getattr(self.polisher, "last_model_used", self.polisher_model),
            chunk_count=chunk_count,
            duration_seconds=polish_duration,
            usage=polish_usage
        )
        updated_token_records = list(state.step_token_records) + [polish_record]

        updated_skills = dict(state.active_skills)
        updated_skills["polishing"] = pol_skills

        return {
            "current_stage": PipelineStage.POLISHING,
            "polished_text": polished,
            "best_polished_text": best_text,
            "active_skills": updated_skills,
            "step_token_records": updated_token_records
        }

    def _chronicle_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.CHRONICLING)
        self.current_stage = PipelineStage.CHRONICLING
        step_start = time.time()

        chr_skills = [
            s.name for s in SkillRegistry.get_instance().get_active_skills(
                agent="chronicler",
                source_lang=state.novel_bible.source_language,
                genre=state.genre
            )
        ]
        skills_suffix = f" [Skills: {', '.join(chr_skills)}]" if chr_skills else ""
        self._notify(PipelineStage.CHRONICLING, f"Updating narrative lore, summaries, and checkpoint{skills_suffix}...", 95.0)

        final_text = state.best_polished_text or state.polished_text or state.draft_text
        # Ensure final_text is not in source language if draft_text is in target language
        if (
            state.novel_bible.target_language.lower() != state.novel_bible.source_language.lower()
            and detect_language(final_text) == state.novel_bible.source_language
            and detect_language(state.draft_text) != state.novel_bible.source_language
        ):
            final_text = state.draft_text

        final_audit = state.best_audit or state.quality_audit

        est_chronicle = min(estimate_tokens(final_text), 4000) + 400
        summary = invoke_with_retry(
            self.chronicler.chronicle,
            chapter_num=state.chapter_num,
            chapter_title=f"Chapter {state.chapter_num}",
            translated_text=final_text,
            genre=state.genre,
            source_lang=state.novel_bible.source_language,
            notify_callback=lambda msg: self._notify(PipelineStage.CHRONICLING, msg, 95.0),
            rate_limiter=self.rate_limiter,
            estimated_tokens=est_chronicle,
            stop_event=self.stop_event
        )

        current_folder = Path(state.source_file).parent.name if state.source_file else None
        if summary and current_folder and not getattr(summary, "folder", None):
            summary.folder = current_folder

        chronicle_duration = round(time.time() - step_start, 2)
        chronicle_usage = getattr(self.chronicler, "last_usage", TokenUsage())
        chronicle_record = StepTokenUsage(
            stage=PipelineStage.CHRONICLING,
            step_name="Chronicling",
            iteration=1,
            model=getattr(self.chronicler, "last_model_used", self.chronicler_model),
            duration_seconds=chronicle_duration,
            usage=chronicle_usage
        )
        all_token_records = list(state.step_token_records) + [chronicle_record]
        total_duration = round(sum(r.duration_seconds for r in all_token_records), 2)

        metadata = self.chronicler.assemble_metadata(
            chapter_id=state.chapter_id,
            chapter_num=state.chapter_num,
            source_file=state.source_file,
            source_sha256=state.source_sha256,
            output_file=state.output_file,
            source_text=state.source_text,
            final_text=final_text,
            model_name=self.model_name,
            duration_seconds=total_duration if total_duration > 0 else 1.0,
            quality_audit=final_audit,
            active_characters=state.active_characters,
            active_glossary=state.active_glossary,
            draft_text=state.draft_text,
            critique_notes=state.critique_notes,
            polished_text=final_text,
            status=StageStatus.COMPLETED,
            step_usage=all_token_records
        )

        updated_skills = dict(state.active_skills)
        updated_skills["chronicling"] = chr_skills

        return {
            "current_stage": PipelineStage.CHRONICLING,
            "polished_text": final_text,
            "quality_audit": final_audit,
            "new_chapter_summary": summary,
            "metadata": metadata,
            "active_skills": updated_skills,
            "step_token_records": all_token_records
        }

    def run(
        self,
        initial_state: TranslationState,
        stage_callback: Optional[Callable[[PipelineStage, str, float], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> TranslationState:
        """Run workflow graph to completion with optional stage callback and stop event."""
        if stage_callback:
            self.stage_callback = stage_callback
        self.stop_event = stop_event
        self.current_stage = PipelineStage.NONE

        # Auto-resolve genre if general or unspecified
        if not initial_state.genre or initial_state.genre == "general":
            if getattr(initial_state.novel_bible, "genre", None) and initial_state.novel_bible.genre != "general":
                initial_state.genre = initial_state.novel_bible.genre
            else:
                detected_genre = detect_genre(initial_state.source_text)
                if detected_genre != "general":
                    initial_state.genre = detected_genre

        if initial_state.max_review_loops == 3 and self.max_review_loops != 3:
            initial_state.max_review_loops = self.max_review_loops
        if initial_state.quality_threshold == 8.5 and self.quality_threshold != 8.5:
            initial_state.quality_threshold = self.quality_threshold

        self.last_state = initial_state
        start_time = time.time()
        final_state_dict = self.graph.invoke(initial_state)
        result = TranslationState.model_validate(final_state_dict)
        self.last_state = result
        if result.metadata:
            result.metadata.stats.duration_seconds = round(time.time() - start_time, 2)
        self._notify(PipelineStage.CHRONICLING, "Chapter translation completed!", 100.0)
        return result
