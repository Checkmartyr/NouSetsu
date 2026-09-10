"""LangGraph translation workflow wiring the multi-agent pipeline."""
import threading
import time
from typing import Any, Callable, Dict, Optional
from langgraph.graph import END, StateGraph
from src.agents.chronicler import ChroniclerAgent
from src.agents.critic import CritiqueAgent
from src.agents.drafter import ContextAwareDrafterAgent
from src.agents.extractor import EntityExtractorAgent
from src.agents.llm import invoke_with_retry
from src.agents.polisher import PolishingAgent
from src.models.exceptions import BatchStoppedException
from src.models.metadata import PipelineStage, StageStatus
from src.models.state import TranslationState


class NovelTranslationWorkflow:
    """Orchestrates document-level novel translation with LangGraph."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_name = model_name
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
        builder.add_edge("critique", "polish")
        builder.add_edge("polish", "chronicle")
        builder.add_edge("chronicle", END)

        return builder.compile()

    def _check_stop(self, state: TranslationState, stage: PipelineStage) -> None:
        self.last_state = state
        self.current_stage = stage
        if self.stop_event and self.stop_event.is_set():
            raise BatchStoppedException(f"Translation stopped by user before {stage.value} stage.")

    def _extract_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.EXTRACTION)
        self.current_stage = PipelineStage.EXTRACTION
        self._notify(PipelineStage.EXTRACTION, "Extracting novel entities & terminology...", 15.0)
        # If already extracted in checkpoint, skip re-extracting
        if state.extracted_terms or state.extracted_characters:
            return {
                "current_stage": PipelineStage.EXTRACTION,
                "active_glossary": state.novel_bible.glossary + state.extracted_terms,
                "active_characters": state.novel_bible.characters + state.extracted_characters
            }

        new_chars, new_terms, active_terms = invoke_with_retry(
            self.extractor.extract,
            state.source_text,
            state.novel_bible,
            notify_callback=lambda msg: self._notify(PipelineStage.EXTRACTION, msg, 15.0)
        )
        
        all_chars = list(state.novel_bible.characters) + new_chars
        all_glossary = list(state.novel_bible.glossary) + new_terms

        return {
            "current_stage": PipelineStage.EXTRACTION,
            "extracted_characters": new_chars,
            "extracted_terms": new_terms,
            "active_characters": all_chars,
            "active_glossary": all_glossary
        }

    def _draft_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.DRAFTING)
        self.current_stage = PipelineStage.DRAFTING
        self._notify(PipelineStage.DRAFTING, "Drafting novelistic translation with character context...", 35.0)
        # If draft already exists in checkpoint, retain it
        if state.draft_text:
            return {"current_stage": PipelineStage.DRAFTING}

        draft = invoke_with_retry(
            self.drafter.draft,
            source_text=state.source_text,
            bible=state.novel_bible,
            active_characters=state.active_characters,
            active_glossary=state.active_glossary,
            rolling_summaries=state.novel_bible.summaries,
            notify_callback=lambda msg: self._notify(PipelineStage.DRAFTING, msg, 35.0)
        )
        return {
            "current_stage": PipelineStage.DRAFTING,
            "draft_text": draft
        }

    def _critique_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.CRITIQUE)
        self.current_stage = PipelineStage.CRITIQUE
        self._notify(PipelineStage.CRITIQUE, "Auditing fidelity, tone, and glossary adherence...", 60.0)
        # If critique notes already exist, retain
        if state.critique_notes and state.quality_audit.fidelity_score > 0:
            return {"current_stage": PipelineStage.CRITIQUE}

        audit, notes = invoke_with_retry(
            self.critic.evaluate,
            source_text=state.source_text,
            draft_text=state.draft_text,
            bible=state.novel_bible,
            active_characters=state.active_characters,
            active_glossary=state.active_glossary,
            notify_callback=lambda msg: self._notify(PipelineStage.CRITIQUE, msg, 60.0)
        )
        return {
            "current_stage": PipelineStage.CRITIQUE,
            "quality_audit": audit,
            "critique_notes": notes
        }

    def _polish_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.POLISHING)
        self.current_stage = PipelineStage.POLISHING
        self._notify(PipelineStage.POLISHING, "Polishing prose cadence and eliminating translationese...", 80.0)
        if state.polished_text:
            return {"current_stage": PipelineStage.POLISHING}

        polished = invoke_with_retry(
            self.polisher.polish,
            draft_text=state.draft_text,
            critique_notes=state.critique_notes,
            active_glossary=state.active_glossary,
            bible=state.novel_bible,
            notify_callback=lambda msg: self._notify(PipelineStage.POLISHING, msg, 80.0)
        )
        return {
            "current_stage": PipelineStage.POLISHING,
            "polished_text": polished
        }

    def _chronicle_step(self, state: TranslationState) -> Dict[str, Any]:
        self._check_stop(state, PipelineStage.CHRONICLING)
        self.current_stage = PipelineStage.CHRONICLING
        self._notify(PipelineStage.CHRONICLING, "Updating narrative lore, summaries, and checkpoint...", 95.0)
        summary = invoke_with_retry(
            self.chronicler.chronicle,
            chapter_num=state.chapter_num,
            chapter_title=f"Chapter {state.chapter_num}",
            translated_text=state.polished_text,
            notify_callback=lambda msg: self._notify(PipelineStage.CHRONICLING, msg, 95.0)
        )

        metadata = self.chronicler.assemble_metadata(
            chapter_id=state.chapter_id,
            chapter_num=state.chapter_num,
            source_file=state.source_file,
            source_sha256=state.source_sha256,
            output_file=state.output_file,
            source_text=state.source_text,
            final_text=state.polished_text,
            model_name=self.model_name,
            duration_seconds=1.0,
            quality_audit=state.quality_audit,
            active_characters=state.active_characters,
            active_glossary=state.active_glossary,
            draft_text=state.draft_text,
            critique_notes=state.critique_notes,
            polished_text=state.polished_text,
            status=StageStatus.COMPLETED
        )

        return {
            "current_stage": PipelineStage.CHRONICLING,
            "new_chapter_summary": summary,
            "metadata": metadata
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
        self.last_state = initial_state
        start_time = time.time()
        final_state_dict = self.graph.invoke(initial_state)
        result = TranslationState.model_validate(final_state_dict)
        self.last_state = result
        if result.metadata:
            result.metadata.stats.duration_seconds = round(time.time() - start_time, 2)
        self._notify(PipelineStage.CHRONICLING, "Chapter translation completed!", 100.0)
        return result
