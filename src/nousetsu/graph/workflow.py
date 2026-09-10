"""LangGraph translation workflow wiring the multi-agent pipeline."""
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
from nousetsu.models.metadata import PipelineStage, StageStatus
from nousetsu.models.state import TranslationState
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.genre import detect_genre
from nousetsu.utils.rate_limiter import SlidingWindowRateLimiter, estimate_tokens



class NovelTranslationWorkflow:
    """Orchestrates document-level novel translation with LangGraph."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-pro",
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
        max_review_loops: int = 3,
        quality_threshold: float = 8.5
    ):
        self.model_name = model_name
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter()
        self.max_review_loops = max_review_loops
        self.quality_threshold = quality_threshold
        self.current_stage: PipelineStage = PipelineStage.NONE
        self.extractor = EntityExtractorAgent(model_name=model_name)
        self.drafter = ContextAwareDrafterAgent(model_name=model_name)
        self.critic = CritiqueAgent(model_name=model_name)
        self.polisher = PolishingAgent(model_name=model_name)
        self.chronicler = ChroniclerAgent(model_name=model_name)
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
        passed_threshold = (
            state.quality_audit.fidelity_score >= state.quality_threshold
            and state.quality_audit.style_score >= state.quality_threshold
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

        updated_skills = dict(state.active_skills)
        updated_skills["extraction"] = ext_skills

        return {
            "current_stage": PipelineStage.EXTRACTION,
            "extracted_characters": new_chars,
            "extracted_terms": new_terms,
            "active_characters": all_chars,
            "active_glossary": all_glossary,
            "active_skills": updated_skills
        }

    def _draft_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.DRAFTING)
        self.current_stage = PipelineStage.DRAFTING

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
        est_draft = int(estimate_tokens(state.source_text) * 1.5) + 2000
        draft = invoke_with_retry(
            self.drafter.draft,
            source_text=state.source_text,
            bible=state.novel_bible,
            active_characters=state.active_characters,
            active_glossary=state.active_glossary,
            rolling_summaries=state.novel_bible.summaries,
            notify_callback=lambda msg: self._notify(PipelineStage.DRAFTING, msg, 35.0),
            rate_limiter=self.rate_limiter,
            estimated_tokens=est_draft,
            stop_event=self.stop_event
        )

        updated_skills = dict(state.active_skills)
        updated_skills["drafting"] = dft_skills

        return {
            "current_stage": PipelineStage.DRAFTING,
            "draft_text": draft,
            "active_skills": updated_skills
        }

    def _critique_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.CRITIQUE)
        self.current_stage = PipelineStage.CRITIQUE

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

        updated_skills = dict(state.active_skills)
        updated_skills["critique"] = crt_skills

        return {
            "current_stage": PipelineStage.CRITIQUE,
            "quality_audit": audit,
            "critique_notes": notes,
            "review_iteration": current_iter,
            "best_audit": best_audit,
            "best_polished_text": best_text,
            "active_skills": updated_skills
        }

    def _polish_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.POLISHING)
        self.current_stage = PipelineStage.POLISHING

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

        state.novel_bible.genre = state.genre
        est_polish = estimate_tokens(base_text) * 2 + 1000
        polished = invoke_with_retry(
            self.polisher.polish,
            draft_text=base_text,
            critique_notes=state.critique_notes,
            active_glossary=state.active_glossary,
            bible=state.novel_bible,
            notify_callback=lambda msg: self._notify(PipelineStage.POLISHING, msg, 80.0),
            rate_limiter=self.rate_limiter,
            estimated_tokens=est_polish,
            stop_event=self.stop_event
        )

        best_text = polished if is_initial_draft else (state.best_polished_text or polished)

        updated_skills = dict(state.active_skills)
        updated_skills["polishing"] = pol_skills

        return {
            "current_stage": PipelineStage.POLISHING,
            "polished_text": polished,
            "best_polished_text": best_text,
            "active_skills": updated_skills
        }

    def _chronicle_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.CHRONICLING)
        self.current_stage = PipelineStage.CHRONICLING

        chr_skills = [
            s.name for s in SkillRegistry.get_instance().get_active_skills(
                agent="chronicler",
                source_lang=state.novel_bible.source_language,
                genre=state.genre
            )
        ]
        skills_suffix = f" [Skills: {', '.join(chr_skills)}]" if chr_skills else ""
        self._notify(PipelineStage.CHRONICLING, f"Updating narrative lore, summaries, and checkpoint{skills_suffix}...", 95.0)

        final_text = state.best_polished_text or state.polished_text
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

        metadata = self.chronicler.assemble_metadata(
            chapter_id=state.chapter_id,
            chapter_num=state.chapter_num,
            source_file=state.source_file,
            source_sha256=state.source_sha256,
            output_file=state.output_file,
            source_text=state.source_text,
            final_text=final_text,
            model_name=self.model_name,
            duration_seconds=1.0,
            quality_audit=final_audit,
            active_characters=state.active_characters,
            active_glossary=state.active_glossary,
            draft_text=state.draft_text,
            critique_notes=state.critique_notes,
            polished_text=final_text,
            status=StageStatus.COMPLETED
        )

        updated_skills = dict(state.active_skills)
        updated_skills["chronicling"] = chr_skills

        return {
            "current_stage": PipelineStage.CHRONICLING,
            "polished_text": final_text,
            "quality_audit": final_audit,
            "new_chapter_summary": summary,
            "metadata": metadata,
            "active_skills": updated_skills
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
