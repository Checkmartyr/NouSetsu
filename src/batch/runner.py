"""Batch runner for sequential chapter execution with checkpoint resumption."""
from pathlib import Path
from typing import Callable, List, Optional
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from src.batch.scanner import ChapterScanner, ChapterTask
from src.graph.workflow import NovelTranslationWorkflow
from src.models.metadata import ChapterMetadata, CheckpointData, PipelineStage, StageStatus
from src.models.state import TranslationState
from src.storage.repository import NovelRepository


class BatchRunner:
    """Executes folder-to-folder automated translation, managing cross-chapter state and checkpoints."""

    def __init__(
        self,
        repository: NovelRepository,
        model_name: str = "gemini-2.5-pro",
        console: Optional[Console] = None
    ):
        self.repo = repository
        self.model_name = model_name
        self.console = console or Console()
        self.scanner = ChapterScanner(repository)
        self.workflow = NovelTranslationWorkflow(model_name=model_name)

    def run_batch(
        self,
        input_dir: Path,
        output_dir: Path,
        limit: Optional[int] = None,
        force_retranslate: bool = False,
        tasks: Optional[List[ChapterTask]] = None,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
        stage_callback: Optional[Callable[[str, PipelineStage, str, float], None]] = None
    ) -> List[ChapterMetadata]:
        """Execute batch translation across all chapters in directory."""
        if tasks is None:
            tasks = self.scanner.scan_directory(input_dir, output_dir)
        if limit:
            tasks = tasks[:limit]

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

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

                # Read source text
                with open(task.source_file, "r", encoding="utf-8") as sf:
                    source_text = sf.read()

                # Load fresh Novel Bible state for current chapter
                bible = self.repo.load_bible()

                # Prepare initial state with possible checkpoint resumption
                initial_state = TranslationState(
                    chapter_id=f"chapter_{task.chapter_num:04d}",
                    chapter_num=task.chapter_num,
                    source_file=str(task.source_file),
                    source_sha256=task.source_sha256,
                    output_file=str(task.output_file),
                    source_text=source_text,
                    model_name=self.model_name,
                    novel_bible=bible
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

                try:
                    # Run LangGraph pipeline with stage notification
                    def _on_stage(st: PipelineStage, msg: str, pct: float):
                        if stage_callback:
                            stage_callback(task.source_file.name, st, msg, pct)

                    final_state = self.workflow.run(initial_state, stage_callback=_on_stage)

                    # Write translated text
                    with open(task.output_file, "w", encoding="utf-8") as out_f:
                        out_f.write(final_state.polished_text)

                    # Update persistent memory across chapters
                    self.repo.update_bible_memory(
                        new_characters=final_state.extracted_characters,
                        new_terms=final_state.extracted_terms,
                        summary=final_state.new_chapter_summary
                    )

                    # Save chapter metadata and checkpoint
                    if final_state.metadata:
                        self.repo.save_metadata(final_state.metadata, task.output_file)
                        results.append(final_state.metadata)

                    progress.update(overall_task, advance=1, description=f"[bold green]Finished: {desc}")
                    if progress_callback:
                        progress_callback(task.source_file.name, idx, total_tasks, "COMPLETED")

                except Exception as err:
                    import traceback
                    tb_str = traceback.format_exc()
                    failed_stage = getattr(self.workflow, "current_stage", PipelineStage.NONE)

                    # Save failed checkpoint with detailed error diagnostics to enable resumption later
                    failed_meta = ChapterMetadata(
                        chapter_id=f"chapter_{task.chapter_num:04d}",
                        chapter_num=task.chapter_num,
                        source_file=str(task.source_file),
                        source_sha256=task.source_sha256,
                        output_file=str(task.output_file),
                        model=self.model_name,
                        checkpoint=task.existing_meta.checkpoint if (task.existing_meta and task.existing_meta.checkpoint) else CheckpointData()
                    )
                    failed_meta.checkpoint.record_error(
                        stage=failed_stage,
                        err=err,
                        traceback_str=tb_str,
                        model=self.model_name
                    )
                    self.repo.save_metadata(failed_meta, task.output_file)

                    progress.update(overall_task, advance=1, description=f"[bold red]Failed: {desc} ({err})")
                    if progress_callback:
                        progress_callback(task.source_file.name, idx, total_tasks, "FAILED")

        self._print_batch_summary(results)
        return results

    def _print_batch_summary(self, results: List[ChapterMetadata]) -> None:
        """Display Rich summary table of batch run."""
        table = Table(title="Batch Translation Summary", show_header=True, header_style="bold magenta")
        table.add_column("Chapter", style="cyan", width=12)
        table.add_column("Status", style="green", width=12)
        table.add_column("Fidelity", justify="right", width=10)
        table.add_column("Words", justify="right", width=10)
        table.add_column("Time (s)", justify="right", width=10)
        table.add_column("Warnings", style="yellow")

        for m in results:
            warnings_str = f"{len(m.quality_audit.warnings)} issues" if m.quality_audit.warnings else "None"
            table.add_row(
                f"Ch.{m.chapter_num}",
                m.checkpoint.status.value.upper(),
                f"{m.quality_audit.fidelity_score:.1f}/10",
                str(m.stats.target_word_count),
                f"{m.stats.duration_seconds:.1f}",
                warnings_str
            )

        self.console.print(table)
