"""Batch runner for sequential chapter execution with checkpoint resumption."""
import os
from pathlib import Path
import re
import threading
from typing import Callable, List, Optional
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from nousetsu.batch.scanner import ChapterScanner, ChapterTask
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.exceptions import BatchStoppedException
from nousetsu.models.metadata import ChapterMetadata, CheckpointData, PipelineStage, StageArtifacts, StageStatus, TokenUsage
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository
from nousetsu.utils.env import load_env
from nousetsu.utils.language import detect_language
from nousetsu.utils.rate_limiter import SlidingWindowRateLimiter
import logging

logger = logging.getLogger(__name__)


class BatchRunner:
    """Executes folder-to-folder automated translation, managing cross-chapter state and checkpoints."""

    def __init__(
        self,
        repository: NovelRepository,
        model_name: Optional[str] = None,
        fallback_model: Optional[str] = None,
        extractor_model: Optional[str] = None,
        drafter_model: Optional[str] = None,
        critic_model: Optional[str] = None,
        polisher_model: Optional[str] = None,
        chronicler_model: Optional[str] = None,
        auto_update_bible: Optional[bool] = None,
        max_tpm: Optional[int] = None,
        max_rpm: Optional[int] = None,
        max_review_loops: Optional[int] = None,
        quality_threshold: Optional[float] = None,
        genre: Optional[str] = None,
        enable_chunking: Optional[bool] = None,
        chunk_threshold_lines: Optional[int] = None,
        target_chunk_lines: Optional[int] = None,
        chunk_overlap_lines: Optional[int] = None,
        enable_rag: Optional[bool] = None,
        enable_rag_reranker: Optional[bool] = None,
        filter_extractor_entities: Optional[bool] = None,
        enable_post_polish_reconciliation: Optional[bool] = None,
        enable_procedural_graph_learning: Optional[bool] = None,
        procedural_learning_cadence: Optional[str] = None,
        procedural_learning_interval: Optional[int] = None,
        procedural_learning_min_failures: Optional[int] = None,
        procedural_refiner_model: Optional[str] = None,
        console: Optional[Console] = None
    ):
        if isinstance(repository, NovelRepository):
            self.repo = repository
        else:
            from nousetsu.storage.repository import resolve_project_dir
            self.repo = NovelRepository(resolve_project_dir(repository))
        load_env(self.repo.root_dir)
        cfg = self.repo.load_config()

        # Resolve primary model
        resolved_model = model_name or cfg.get_model_name()
        self.model_name = resolved_model

        # If primary model is a mock/test model, propagate to all agents unless caller explicitly specified otherwise
        is_mock = resolved_model.startswith("mock") or resolved_model.startswith("test")
        default_agent_model = resolved_model if is_mock else None

        # Resolve fallback and per-agent models
        resolved_fallback = fallback_model or default_agent_model or cfg.get_fallback_model()
        resolved_extractor = extractor_model or default_agent_model or cfg.get_agent_model("extractor")
        resolved_drafter = drafter_model or default_agent_model or cfg.get_agent_model("drafter")
        resolved_critic = critic_model or default_agent_model or cfg.get_agent_model("critic")
        resolved_polisher = polisher_model or default_agent_model or cfg.get_agent_model("polisher")
        resolved_chronicler = chronicler_model or default_agent_model or cfg.get_agent_model("chronicler")
        resolved_generation = {
            role: cfg.get_agent_generation_settings(role)
            for role in ("extractor", "drafter", "critic", "polisher", "chronicler")
        }

        self.fallback_model = resolved_fallback
        self.extractor_model = resolved_extractor
        self.drafter_model = resolved_drafter
        self.critic_model = resolved_critic
        self.polisher_model = resolved_polisher
        self.chronicler_model = resolved_chronicler

        self.console = console or Console()
        self.scanner = ChapterScanner(repository)

        self.genre = genre or getattr(cfg, "genre", "general")

        # Rate limiting configuration (default 32K TPM / 60 RPM; for mock models bypass throttle)
        if is_mock and not max_tpm and "NOVEL_MAX_TPM" not in os.environ:
            resolved_tpm = 10_000_000
            resolved_rpm = 10_000
        else:
            env_tpm = int(os.environ["NOVEL_MAX_TPM"]) if "NOVEL_MAX_TPM" in os.environ else None
            env_rpm = int(os.environ["NOVEL_MAX_RPM"]) if "NOVEL_MAX_RPM" in os.environ else None
            resolved_tpm = max_tpm or env_tpm or getattr(cfg, "max_tpm", 32000)
            resolved_rpm = max_rpm or env_rpm or getattr(cfg, "max_rpm", 60)

        # Review loop configuration
        env_loops = int(os.environ["NOVEL_MAX_REVIEW_LOOPS"]) if "NOVEL_MAX_REVIEW_LOOPS" in os.environ else None
        env_thresh = float(os.environ["NOVEL_QUALITY_THRESHOLD"]) if "NOVEL_QUALITY_THRESHOLD" in os.environ else None
        resolved_loops = max_review_loops or env_loops or getattr(cfg, "max_review_loops", 3)
        resolved_thresh = quality_threshold or env_thresh or getattr(cfg, "quality_threshold", 8.5)

        self.max_review_loops = resolved_loops
        self.quality_threshold = resolved_thresh

        # Chunking configuration
        resolved_chunking = enable_chunking if enable_chunking is not None else getattr(cfg, "enable_chunking", True)
        resolved_chunk_thresh = chunk_threshold_lines or getattr(cfg, "chunk_threshold_lines", 800)
        resolved_target_lines = target_chunk_lines or getattr(cfg, "target_chunk_lines", 400)
        resolved_overlap_lines = chunk_overlap_lines or getattr(cfg, "chunk_overlap_lines", 3)

        resolved_rag = enable_rag if enable_rag is not None else getattr(cfg, "enable_rag", True)
        resolved_reranker = enable_rag_reranker if enable_rag_reranker is not None else getattr(cfg, "enable_rag_reranker", True)
        resolved_filter_extractor = (
            filter_extractor_entities
            if filter_extractor_entities is not None
            else (
                cfg.get_filter_extractor_entities()
                if hasattr(cfg, "get_filter_extractor_entities")
                else getattr(cfg, "filter_extractor_entities", True)
            )
        )
        resolved_reconcile = (
            enable_post_polish_reconciliation
            if enable_post_polish_reconciliation is not None
            else (
                cfg.get_post_polish_reconciliation()
                if hasattr(cfg, "get_post_polish_reconciliation")
                else getattr(cfg, "enable_post_polish_reconciliation", True)
            )
        )

        self.rate_limiter = SlidingWindowRateLimiter(max_tpm=resolved_tpm, max_rpm=resolved_rpm)
        self.workflow = NovelTranslationWorkflow(
            model_name=resolved_model,
            fallback_model=resolved_fallback,
            extractor_model=resolved_extractor,
            drafter_model=resolved_drafter,
            critic_model=resolved_critic,
            polisher_model=resolved_polisher,
            chronicler_model=resolved_chronicler,
            rate_limiter=self.rate_limiter,
            max_review_loops=resolved_loops,
            quality_threshold=resolved_thresh,
            enable_chunking=resolved_chunking,
            chunk_threshold_lines=resolved_chunk_thresh,
            target_chunk_lines=resolved_target_lines,
            chunk_overlap_lines=resolved_overlap_lines,
            safety_recursive_subdivision=getattr(cfg, "safety_recursive_subdivision", True),
            safety_subdivision_min_lines=getattr(cfg, "safety_subdivision_min_lines", 8),
            safety_subdivision_max_depth=getattr(cfg, "safety_subdivision_max_depth", 4),
            rag_engine=self.repo.get_rag_engine() if resolved_rag else None,
            enable_rag=resolved_rag,
            rag_top_k=getattr(cfg, "rag_top_k", 2),
            rag_embedding_model=cfg.get_rag_embedding_model() if hasattr(cfg, "get_rag_embedding_model") else getattr(cfg, "rag_embedding_model", "text-multilingual-embedding-002"),
            enable_rag_reranker=resolved_reranker,
            rag_reranker_model=default_agent_model if is_mock else (cfg.get_rag_reranker_model() if hasattr(cfg, "get_rag_reranker_model") else getattr(cfg, "rag_reranker_model", "gemini-3.5-flash-lite")),
            traces_dir=self.repo.traces_dir,
            extractor_pg=self.repo.load_procedural_graph("extractor"),
            drafter_pg=self.repo.load_procedural_graph("drafter"),
            critic_pg=self.repo.load_procedural_graph("critic"),
            polisher_pg=self.repo.load_procedural_graph("polisher"),
            chronicler_pg=self.repo.load_procedural_graph("chronicler"),
            enable_patch_polishing=getattr(cfg, "enable_patch_polishing", True),
            filter_extractor_entities=resolved_filter_extractor,
            enable_post_polish_reconciliation=resolved_reconcile,
            generation_settings=resolved_generation,
        )
        self.rag_engine = self.workflow.rag_engine
        self.auto_update_bible = auto_update_bible if auto_update_bible is not None else cfg.auto_update_bible
        self.stop_event = threading.Event()
        self.batch_token_usage = TokenUsage()
        self.task_token_usage: dict[str, TokenUsage] = {}

        self.enable_procedural_graph_learning = (
            enable_procedural_graph_learning
            if enable_procedural_graph_learning is not None
            else (
                cfg.get_enable_procedural_graph_learning()
                if hasattr(cfg, "get_enable_procedural_graph_learning")
                else getattr(cfg, "enable_procedural_graph_learning", True)
            )
        )
        self.procedural_learning_cadence = (
            procedural_learning_cadence
            if procedural_learning_cadence is not None
            else (
                cfg.get_procedural_learning_cadence()
                if hasattr(cfg, "get_procedural_learning_cadence")
                else getattr(cfg, "procedural_learning_cadence", "both")
            )
        )
        self.procedural_learning_interval = (
            procedural_learning_interval
            if procedural_learning_interval is not None
            else (
                cfg.get_procedural_learning_interval()
                if hasattr(cfg, "get_procedural_learning_interval")
                else getattr(cfg, "procedural_learning_interval", 15)
            )
        )
        self.procedural_learning_min_failures = (
            procedural_learning_min_failures
            if procedural_learning_min_failures is not None
            else (
                cfg.get_procedural_learning_min_failures()
                if hasattr(cfg, "get_procedural_learning_min_failures")
                else getattr(cfg, "procedural_learning_min_failures", 2)
            )
        )
        self.procedural_refiner_model = (
            default_agent_model
            if is_mock
            else (
                procedural_refiner_model
                or (
                    cfg.get_procedural_refiner_model()
                    if hasattr(cfg, "get_procedural_refiner_model")
                    else getattr(cfg, "procedural_refiner_model", "gemini-3.5-flash-lite")
                )
            )
        )
        self._refiner = None

    @property
    def refiner(self):
        """Lazy-loaded ProceduralGraphRefiner instance."""
        if self._refiner is None:
            from nousetsu.graph.pg_refiner import ProceduralGraphRefiner
            rejection_path = self.repo.procedural_graphs_dir / "rejection_memory.json"
            self._refiner = ProceduralGraphRefiner(
                model_name=self.procedural_refiner_model,
                rejection_memory_path=rejection_path
            )
        return self._refiner


    def stop(self) -> None:
        """Signal batch runner to gracefully halt translation."""
        self.stop_event.set()

    def reset_stop(self) -> None:
        """Reset stop signal for a new batch run."""
        self.stop_event.clear()

    @property
    def is_stopped(self) -> bool:
        return self.stop_event.is_set()

    def run_batch(
        self,
        input_dir: Path,
        output_dir: Path,
        limit: Optional[int] = None,
        force_retranslate: bool = False,
        chapter_filter: Optional[str | int] = None,
        tasks: Optional[List[ChapterTask]] = None,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
        stage_callback: Optional[Callable[[str, PipelineStage, str, float], None]] = None
    ) -> List[ChapterMetadata]:
        """Execute batch translation across all chapters in directory."""
        if tasks is None:
            tasks = self.scanner.scan_directory(input_dir, output_dir)
        if chapter_filter is not None:
            tasks = ChapterScanner.filter_tasks(tasks, chapter_filter)
            if not tasks and self.console:
                self.console.print(f"[bold yellow]⚠️ No chapters matched filter: '{chapter_filter}'.[/]")
        if limit:
            tasks = tasks[:limit]

        if not tasks:
            return []

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        self.reset_stop()
        results: List[ChapterMetadata] = []
        total_tasks = len(tasks)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
            transient=False
        ) as progress:
            overall_task = progress.add_task("[bold cyan]Translating novel...", total=total_tasks)

            for idx, task in enumerate(tasks, start=1):
                if self.is_stopped:
                    self.console.print("\n[bold yellow]🛑 Batch translation stopped by user request.[/]")
                    break

                desc = f"Ch.{task.chapter_num} ({task.source_file.name})"

                if task.is_completed and not force_retranslate:
                    progress.update(overall_task, advance=1, description=f"[green]Skipped (Done): {desc}")
                    if progress_callback:
                        progress_callback(task.source_file.name, idx, total_tasks, "SKIPPED")
                    if task.existing_meta:
                        results.append(task.existing_meta)
                    continue

                progress.update(overall_task, description=f"[yellow]Processing: {desc}")
                if progress_callback:
                    progress_callback(task.source_file.name, idx, total_tasks, "RUNNING")

                try:
                    meta = self.run_chapter(
                        task=task,
                        force_retranslate=force_retranslate,
                        stop_event=self.stop_event,
                        stage_callback=stage_callback
                    )
                    if meta:
                        results.append(meta)
                        tok_display = f" [cyan]({meta.stats.total_tokens:,} tokens)[/]" if (meta.stats and meta.stats.total_tokens) else ""
                        progress.update(overall_task, advance=1, description=f"[bold green]Finished: {desc}{tok_display}")
                        if progress_callback:
                            progress_callback(task.source_file.name, idx, total_tasks, "COMPLETED")

                except BatchStoppedException:
                    paused_meta = self.repo.load_metadata(task.output_file) or task.existing_meta
                    if paused_meta:
                        results.append(paused_meta)
                    progress.update(overall_task, description=f"[bold yellow]Paused: {desc}")
                    if progress_callback:
                        progress_callback(task.source_file.name, idx, total_tasks, "PAUSED")
                    paused_stage = getattr(self.workflow, "current_stage", PipelineStage.NONE)
                    self.console.print(f"\n[bold yellow]🛑 Translation paused at {paused_stage.value.upper()} stage for {desc}. Checkpoints preserved.[/]")
                    break

                except Exception as err:
                    failed_meta = self.repo.load_metadata(task.output_file) or task.existing_meta
                    if failed_meta:
                        results.append(failed_meta)
                    progress.update(overall_task, advance=1, description=f"[bold red]Failed: {desc} ({err})")
                    if progress_callback:
                        progress_callback(task.source_file.name, idx, total_tasks, "FAILED")

        self._print_batch_summary(results)
        return results

    def run_chapter(
        self,
        task: ChapterTask,
        force_retranslate: bool = False,
        stop_event: Optional[threading.Event] = None,
        notify_callback: Optional[Callable[[str], None]] = None,
        stage_callback: Optional[Callable[[str, PipelineStage, str, float], None]] = None
    ) -> Optional[ChapterMetadata]:
        """Execute translation for a single chapter task with checkpoint resumption and error handling."""
        effective_stop = stop_event or self.stop_event
        if effective_stop and effective_stop.is_set():
            raise BatchStoppedException("Translation stopped by user before chapter start.")

        if task.is_completed and not force_retranslate:
            return task.existing_meta

        # Read source text
        with open(task.source_file, "r", encoding="utf-8") as sf:
            source_text = sf.read()

        # Load fresh Novel Bible state for current chapter
        bible = self.repo.load_bible()
        if (not bible.source_language) or bible.source_language.strip().lower() in ["auto", "autodetect", "detect", "unknown"]:
            detected = detect_language(source_text, default="Japanese")
            bible = self.repo.set_languages(source_lang=detected)

        # Prepare initial state with possible checkpoint resumption
        initial_state = TranslationState(
            chapter_id=f"chapter_{task.chapter_num:04d}",
            chapter_num=task.chapter_num,
            source_file=str(task.source_file),
            source_sha256=task.source_sha256,
            output_file=str(task.output_file),
            source_text=source_text,
            model_name=self.model_name,
            genre=self.genre or getattr(bible, "genre", "general"),
            novel_bible=bible,
            max_review_loops=self.max_review_loops,
            quality_threshold=self.quality_threshold
        )

        # Resume stage artifacts if present
        if task.needs_resume and task.existing_meta:
            artifacts = task.existing_meta.checkpoint.stage_artifacts
            if artifacts.draft_text:
                initial_state.draft_text = artifacts.draft_text
            if artifacts.critique_notes:
                initial_state.critique_notes = artifacts.critique_notes
            if artifacts.extracted_terms:
                initial_state.extracted_terms = artifacts.extracted_terms
            if artifacts.extracted_characters:
                initial_state.extracted_characters = artifacts.extracted_characters
            if getattr(artifacts, "reconciled_terms", None):
                initial_state.reconciled_terms = artifacts.reconciled_terms
            if getattr(artifacts, "reconciled_characters", None):
                initial_state.reconciled_characters = artifacts.reconciled_characters
            if artifacts.polished_text:
                initial_state.polished_text = artifacts.polished_text
                initial_state.best_polished_text = artifacts.polished_text
            if task.existing_meta.quality_audit and task.existing_meta.quality_audit.fidelity_score > 0:
                initial_state.quality_audit = task.existing_meta.quality_audit
                initial_state.best_audit = task.existing_meta.quality_audit
            if getattr(artifacts, "safety_fallbacks_used", 0):
                initial_state.safety_fallbacks_used = artifacts.safety_fallbacks_used
            if getattr(artifacts, "subdivisions_count", 0):
                initial_state.subdivisions_count = artifacts.subdivisions_count
            if getattr(artifacts, "subdivided_blocks", None):
                initial_state.subdivided_blocks = artifacts.subdivided_blocks

        def _on_stage(st: PipelineStage, msg: str, pct: float):
            if stage_callback:
                stage_callback(task.source_file.name, st, msg, pct)
            if notify_callback:
                notify_callback(msg)

        try:
            final_state = self.workflow.run(
                initial_state,
                stage_callback=_on_stage,
                stop_event=effective_stop
            )

            # Ensure output dir exists and write translated text
            task.output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(task.output_file, "w", encoding="utf-8") as out_f:
                out_f.write(final_state.polished_text)

            # Update persistent memory across chapters (scoped to current folder)
            task_folder = task.folder or Path(task.source_file).parent.name
            if self.auto_update_bible:
                chars_to_save = final_state.reconciled_characters or final_state.extracted_characters
                terms_to_save = final_state.reconciled_terms or final_state.extracted_terms
                self.repo.update_bible_memory(
                    new_characters=chars_to_save,
                    new_terms=terms_to_save,
                    summary=final_state.new_chapter_summary,
                    folder=task_folder
                )
            elif final_state.new_chapter_summary:
                self.repo.update_bible_memory(
                    new_characters=[],
                    new_terms=[],
                    summary=final_state.new_chapter_summary,
                    folder=task_folder
                )

            # Save chapter metadata and checkpoint
            if final_state.metadata:
                st = final_state.metadata.stats
                tok_use = TokenUsage(
                    input_tokens=st.prompt_tokens,
                    output_tokens=st.completion_tokens,
                    thought_tokens=st.thought_tokens,
                    cached_tokens=st.cached_tokens,
                    total_tokens=st.total_tokens,
                )
                self.task_token_usage[task.source_file.name] = tok_use
                self.batch_token_usage = self.batch_token_usage.add(tok_use)

                self.repo.save_metadata(final_state.metadata, task.output_file)

                # Check and handle online procedural graph learning
                try:
                    self._handle_procedural_graph_learning(
                        completed_chapter_num=task.chapter_num,
                        folder=task_folder,
                        final_state=final_state,
                        notify_callback=notify_callback,
                    )
                except Exception as e:
                    logger.warning(f"Error during procedural graph learning check: {e}")

                return final_state.metadata


            return None

        except BatchStoppedException:
            paused_stage = getattr(self.workflow, "current_stage", PipelineStage.NONE)
            last_st = getattr(self.workflow, "last_state", initial_state) or initial_state

            extracted_chars = getattr(last_st, "extracted_characters", []) or (task.existing_meta.checkpoint.stage_artifacts.extracted_characters if task.existing_meta else [])
            extracted_terms = getattr(last_st, "extracted_terms", []) or (task.existing_meta.checkpoint.stage_artifacts.extracted_terms if task.existing_meta else [])
            reconciled_chars = getattr(last_st, "reconciled_characters", []) or (getattr(task.existing_meta.checkpoint.stage_artifacts, "reconciled_characters", []) if task.existing_meta else [])
            reconciled_terms = getattr(last_st, "reconciled_terms", []) or (getattr(task.existing_meta.checkpoint.stage_artifacts, "reconciled_terms", []) if task.existing_meta else [])
            draft_text = getattr(last_st, "draft_text", None) or (task.existing_meta.checkpoint.stage_artifacts.draft_text if task.existing_meta else None)
            critique_notes = getattr(last_st, "critique_notes", None) or (task.existing_meta.checkpoint.stage_artifacts.critique_notes if task.existing_meta else None)
            polished_text = getattr(last_st, "best_polished_text", None) or getattr(last_st, "polished_text", None) or (task.existing_meta.checkpoint.stage_artifacts.polished_text if task.existing_meta else None)

            paused_meta = ChapterMetadata(
                chapter_id=f"chapter_{task.chapter_num:04d}",
                chapter_num=task.chapter_num,
                source_file=str(task.source_file),
                source_sha256=task.source_sha256,
                output_file=str(task.output_file),
                model=self.model_name,
                checkpoint=CheckpointData(
                    status=StageStatus.PAUSED,
                    last_completed_stage=paused_stage,
                    stage_artifacts=StageArtifacts(
                        extracted_terms=extracted_terms,
                        extracted_characters=extracted_chars,
                        reconciled_terms=reconciled_terms,
                        reconciled_characters=reconciled_chars,
                        draft_text=draft_text,
                        critique_notes=critique_notes,
                        polished_text=polished_text,
                        safety_fallbacks_used=getattr(last_st, "safety_fallbacks_used", 0),
                        subdivisions_count=getattr(last_st, "subdivisions_count", 0),
                        subdivided_blocks=getattr(last_st, "subdivided_blocks", [])
                    )
                )
            )
            self.repo.save_metadata(paused_meta, task.output_file)
            raise

        except Exception as err:
            import traceback
            tb_str = traceback.format_exc()
            failed_stage = getattr(self.workflow, "current_stage", PipelineStage.NONE)

            last_st = getattr(self.workflow, "last_state", initial_state) or initial_state
            existing_artifacts = (
                task.existing_meta.checkpoint.stage_artifacts
                if (task.existing_meta and task.existing_meta.checkpoint)
                else StageArtifacts()
            )

            extracted_chars = getattr(last_st, "extracted_characters", []) or existing_artifacts.extracted_characters
            extracted_terms = getattr(last_st, "extracted_terms", []) or existing_artifacts.extracted_terms
            draft_text = getattr(last_st, "draft_text", None) or existing_artifacts.draft_text
            critique_notes = getattr(last_st, "critique_notes", None) or existing_artifacts.critique_notes
            polished_text = getattr(last_st, "best_polished_text", None) or getattr(last_st, "polished_text", None) or existing_artifacts.polished_text

            # Determine last completed stage strictly preceding the failed stage
            stage_order_map = {
                PipelineStage.NONE: 0,
                PipelineStage.EXTRACTION: 1,
                PipelineStage.DRAFTING: 2,
                PipelineStage.CRITIQUE: 3,
                PipelineStage.POLISHING: 4,
                PipelineStage.CHRONICLING: 5,
            }
            failed_order = stage_order_map.get(failed_stage, 0)
            max_allowed_order = max(0, failed_order - 1)

            if max_allowed_order >= 4 and polished_text:
                completed_stage = PipelineStage.POLISHING
            elif max_allowed_order >= 3 and critique_notes:
                completed_stage = PipelineStage.CRITIQUE
            elif max_allowed_order >= 2 and draft_text:
                completed_stage = PipelineStage.DRAFTING
            elif max_allowed_order >= 1 and (extracted_terms or extracted_chars):
                completed_stage = PipelineStage.EXTRACTION
            else:
                completed_stage = PipelineStage.NONE

            completed_order = stage_order_map.get(completed_stage, 0)
            saved_chars = extracted_chars if completed_order >= 1 else []
            saved_terms = extracted_terms if completed_order >= 1 else []
            saved_draft = draft_text if completed_order >= 2 else None
            saved_notes = critique_notes if completed_order >= 3 else None
            saved_polish = polished_text if completed_order >= 4 else None

            # Save failed checkpoint with detailed error diagnostics and preserved stage artifacts
            failed_meta = ChapterMetadata(
                chapter_id=f"chapter_{task.chapter_num:04d}",
                chapter_num=task.chapter_num,
                source_file=str(task.source_file),
                source_sha256=task.source_sha256,
                output_file=str(task.output_file),
                model=self.model_name,
                checkpoint=task.existing_meta.checkpoint if (task.existing_meta and task.existing_meta.checkpoint) else CheckpointData()
            )
            failed_meta.checkpoint.stage_artifacts = StageArtifacts(
                extracted_terms=saved_terms,
                extracted_characters=saved_chars,
                draft_text=saved_draft,
                critique_notes=saved_notes,
                polished_text=saved_polish,
                safety_fallbacks_used=getattr(last_st, "safety_fallbacks_used", 0),
                subdivisions_count=getattr(last_st, "subdivisions_count", 0),
                subdivided_blocks=getattr(last_st, "subdivided_blocks", []) or existing_artifacts.subdivided_blocks
            )
            if completed_stage != PipelineStage.NONE:
                failed_meta.checkpoint.last_completed_stage = completed_stage

            failed_meta.checkpoint.record_error(
                stage=failed_stage,
                err=err,
                traceback_str=tb_str,
                model=self.model_name
            )
            self.repo.save_metadata(failed_meta, task.output_file)
            raise

        self._print_batch_summary(results)
        return results

    def _print_batch_summary(self, results: List[ChapterMetadata]) -> None:
        """Display Rich summary table of batch run and granular token breakdown."""
        if not results:
            return

        table = Table(title="Batch Translation Summary", show_header=True, header_style="bold magenta")
        table.add_column("Chapter", style="cyan", width=12)
        table.add_column("Status", style="green", width=12)
        table.add_column("Fidelity", justify="right", width=10)
        table.add_column("Words", justify="right", width=10)
        table.add_column("Tokens", justify="right", width=12, style="bold cyan")
        table.add_column("Time (s)", justify="right", width=10)
        table.add_column("Warnings", style="yellow")

        for m in results:
            warnings_str = f"{len(m.quality_audit.warnings)} issues" if m.quality_audit.warnings else "None"
            table.add_row(
                f"Ch.{m.chapter_num}",
                m.checkpoint.status.value.upper(),
                f"{m.quality_audit.fidelity_score:.1f}/10",
                str(m.stats.target_word_count),
                f"{m.stats.total_tokens:,}" if m.stats.total_tokens else "-",
                f"{m.stats.duration_seconds:.1f}",
                warnings_str
            )

        self.console.print(table)

        # Granular Token Usage by Task & Step Table
        token_table = Table(title="📊 Token & Duration Breakdown by Pipeline Step", show_header=True, header_style="bold cyan")
        token_table.add_column("Task / Chapter", style="bold yellow", width=16)
        token_table.add_column("Extraction", justify="right", width=14)
        token_table.add_column("Drafting", justify="right", width=14)
        token_table.add_column("Critique", justify="right", width=14)
        token_table.add_column("Polishing", justify="right", width=14)
        token_table.add_column("Chronicle", justify="right", width=14)
        token_table.add_column("Thought", justify="right", width=10, style="dim magenta")
        token_table.add_column("Total Tokens", justify="right", width=14, style="bold green")
        token_table.add_column("Time (s)", justify="right", width=10, style="bold blue")

        for m in results:
            step_map: dict[str, int] = {}
            dur_map: dict[str, float] = {}
            for step in m.stats.step_usage:
                key = step.stage.value.lower()
                step_map[key] = step_map.get(key, 0) + step.usage.total_tokens
                dur_map[key] = round(dur_map.get(key, 0.0) + step.duration_seconds, 2)

            def _fmt_step(k: str) -> str:
                toks = step_map.get(k, 0)
                dur = dur_map.get(k, 0.0)
                if dur > 0:
                    return f"{toks:,} [dim]({dur:.1f}s)[/]"
                return f"{toks:,}"

            token_table.add_row(
                f"Ch.{m.chapter_num} ({Path(m.source_file).name})",
                _fmt_step('extraction'),
                _fmt_step('drafting'),
                _fmt_step('critique'),
                _fmt_step('polishing'),
                _fmt_step('chronicling'),
                f"{m.stats.thought_tokens:,}",
                f"{m.stats.total_tokens:,}",
                f"{m.stats.duration_seconds:.1f}"
            )

        token_table.add_section()
        total_time = sum(m.stats.duration_seconds for m in results)
        token_table.add_row(
            "GRAND TOTAL",
            "-", "-", "-", "-", "-",
            f"{self.batch_token_usage.thought_tokens:,}",
            f"{self.batch_token_usage.total_tokens:,}",
            f"{total_time:.1f}",
            style="bold cyan"
        )
        try:
            self.console.print(token_table)
        except Exception:
            try:
                token_table.title = "Token & Duration Breakdown by Pipeline Step"
                self.console.print(token_table)
            except Exception:
                pass

    def _handle_procedural_graph_learning(
        self,
        completed_chapter_num: int,
        folder: Optional[str],
        final_state: TranslationState,
        notify_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Evaluate triggers and execute online learning/rollback for Procedural Graphs."""
        if not self.enable_procedural_graph_learning:
            return

        cadence = (self.procedural_learning_cadence or "both").lower()
        interval = self.procedural_learning_interval or 15

        # Check triggers
        is_arc_trigger = False
        if cadence in ("arc", "both"):
            arc_sum = getattr(final_state, "arc_summary", None)
            if arc_sum and (getattr(arc_sum, "arc_completed", False) is True or getattr(arc_sum, "status", "").lower() == "completed"):
                is_arc_trigger = True
            ch_sum = getattr(final_state, "new_chapter_summary", None)
            if ch_sum and getattr(ch_sum, "arc_update", None):
                arc_up = ch_sum.arc_update
                if isinstance(arc_up, dict) and (arc_up.get("arc_completed") is True or str(arc_up.get("status", "")).lower() == "completed"):
                    is_arc_trigger = True

        is_interval_trigger = False
        if cadence in ("interval", "both"):
            if completed_chapter_num > 0 and (completed_chapter_num % interval == 0):
                is_interval_trigger = True

        if not (is_arc_trigger or is_interval_trigger):
            return

        trigger_type = "arc" if is_arc_trigger else "interval"
        msg = f"🔄 Evaluating Procedural Graph online learning ({trigger_type} boundary at Ch.{completed_chapter_num})..."
        logger.info(msg)
        if notify_callback:
            notify_callback(msg)

        from nousetsu.graph.pg_refiner import collect_traces_from_repository
        from nousetsu.graph.procedural import (
            get_default_chronicler_graph,
            get_default_critic_graph,
            get_default_drafter_graph,
            get_default_extractor_graph,
            get_default_polisher_graph,
        )

        default_graph_factory = {
            "extractor": get_default_extractor_graph,
            "drafter": get_default_drafter_graph,
            "critic": get_default_critic_graph,
            "polisher": get_default_polisher_graph,
            "chronicler": get_default_chronicler_graph,
        }

        # Collect recent diagnostic traces (capped to 2*interval)
        traces = collect_traces_from_repository(
            repo=self.repo,
            folder=folder,
            stage="all",
            max_traces=max(20, interval * 2)
        )
        if not traces:
            return

        # Check for regression and rollback first across all agents
        for agent_name in ["drafter", "polisher", "extractor", "critic", "chronicler"]:
            agent_traces = [t for t in traces if t.stage == agent_name]
            if len(agent_traces) >= 3 and self.refiner.check_score_regression(agent_traces, window_size=3):
                restored = self.repo.rollback_procedural_graph(agent_name, folder=folder)
                if restored:
                    self.workflow.update_procedural_graph(agent_name, restored)
                    rollback_msg = f"⚠️ Regression detected for {agent_name}; rolled back to previous Procedural Graph version."
                    logger.warning(rollback_msg)
                    if notify_callback:
                        notify_callback(rollback_msg)

        # Iterate agents and check if failure count >= min_failures
        min_failures = self.procedural_learning_min_failures or 2
        for agent_name, factory_fn in default_graph_factory.items():
            agent_traces = [t for t in traces if t.stage == agent_name]
            failures = [t for t in agent_traces if not t.is_success]
            if len(failures) < min_failures:
                continue

            current_g = self.repo.load_procedural_graph(agent_name, folder=folder) or factory_fn()
            try:
                evolved_g, edits = self.refiner.evolve_and_persist(
                    graph=current_g,
                    traces=agent_traces,
                    repo=self.repo,
                    agent_name=agent_name,
                    folder=folder,
                    trigger_type=trigger_type,
                    chapter_num=completed_chapter_num
                )
                if evolved_g and edits:
                    self.workflow.update_procedural_graph(agent_name, evolved_g)
                    success_msg = f"✨ Online evolved Procedural Graph for {agent_name} ({len(edits)} edits applied)!"
                    logger.info(success_msg)
                    if notify_callback:
                        notify_callback(success_msg)
            except Exception as e:
                logger.warning(f"Procedural graph evolution failed for {agent_name}: {e}")
