"""Live translation progress visualizer widget."""
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static
from nousetsu.models.metadata import PipelineStage


class ProgressPanel(Widget):
    """Live progress panel displaying stage badges, progress bar, and status messages."""

    DEFAULT_CSS = """
    ProgressPanel {
        height: 4;
        border: solid $primary 40%;
        background: $surface;
        padding: 0 1;
        margin: 0;
    }
    .panel-header-row {
        height: 1;
        align-horizontal: left;
    }
    .stage-badge {
        text-style: bold;
        padding: 0 1;
        background: $primary;
        color: $text;
        margin-right: 1;
    }
    #engine_status_msg {
        color: $text-muted;
        height: 1;
    }
    .progress-bar-row {
        height: 1;
        align-horizontal: left;
    }
    #progress_chapter_name {
        width: auto;
        max-width: 35;
        height: 1;
        margin-right: 1;
        text-style: bold;
        color: $accent;
        overflow: hidden;
    }
    #engine_progress {
        width: 1fr;
        height: 1;
        margin-top: 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="panel-header-row"):
                yield Static("[bold green] IDLE [/]", id="stage_badge", classes="stage-badge")
                yield Static("Engine ready. Select chapter or batch to begin.", id="engine_status_msg")
            with Horizontal(classes="progress-bar-row"):
                yield Static("[dim]📖 Idle[/]", id="progress_chapter_name", classes="chapter-progress-label")
                yield ProgressBar(id="engine_progress", total=100, show_eta=False, show_percentage=True)

    def _clean_chapter_name(self, filename: str) -> str:
        if filename in ["Batch", "Active Translation"]:
            return filename
        stem = Path(filename).stem
        return stem or filename

    def set_chapter(self, filename: str) -> None:
        """Update chapter label while engine is idle or chapter selected."""
        ch_name = self._clean_chapter_name(filename)
        try:
            ch_label = self.query_one("#progress_chapter_name", Static)
            ch_label.update(f"[dim]📖 {ch_name}[/]")
        except Exception:
            pass

    def update_progress(self, filename: str, stage: PipelineStage, msg: str, percent: float) -> None:
        """Update live badge, progress bar, and status message from worker thread."""
        badge = self.query_one("#stage_badge", Static)
        pbar = self.query_one("#engine_progress", ProgressBar)
        status_lbl = self.query_one("#engine_status_msg", Static)
        ch_label = self.query_one("#progress_chapter_name", Static)

        stage_styles = {
            PipelineStage.EXTRACTION: "[bold yellow] 1/5 EXTRACTION [/]",
            PipelineStage.DRAFTING: "[bold cyan] 2/5 DRAFTING [/]",
            PipelineStage.CRITIQUE: "[bold magenta] 3/5 CRITIQUE [/]",
            PipelineStage.POLISHING: "[bold blue] 4/5 POLISHING [/]",
            PipelineStage.CHRONICLING: "[bold green] 5/5 CHRONICLING [/]",
            PipelineStage.NONE: "[dim] IDLE [/]"
        }

        badge.update(stage_styles.get(stage, f"[bold] {stage.value.upper()} [/]"))
        pbar.update(progress=percent)
        ch_name = self._clean_chapter_name(filename)
        ch_label.update(f"[bold cyan]📖 {ch_name}[/]")
        status_lbl.update(f"[cyan]{filename}[/]: {msg}")

    def set_finished(self, filename: str) -> None:
        """Mark chapter or batch as finished."""
        badge = self.query_one("#stage_badge", Static)
        pbar = self.query_one("#engine_progress", ProgressBar)
        status_lbl = self.query_one("#engine_status_msg", Static)
        ch_label = self.query_one("#progress_chapter_name", Static)

        badge.update("[bold green] COMPLETED [/]")
        pbar.update(progress=100)
        ch_name = self._clean_chapter_name(filename)
        ch_label.update(f"[bold green]✓ {ch_name}[/]")
        status_lbl.update(f"[bold green]✓ Completed translation for {filename}![/]")

    def set_failed(self, filename: str, err: str) -> None:
        """Mark chapter as failed."""
        badge = self.query_one("#stage_badge", Static)
        status_lbl = self.query_one("#engine_status_msg", Static)
        ch_label = self.query_one("#progress_chapter_name", Static)

        badge.update("[bold red] FAILED [/]")
        ch_name = self._clean_chapter_name(filename)
        ch_label.update(f"[bold red]✕ {ch_name}[/]")
        status_lbl.update(f"[bold red]❌ Failed {filename}: {err}[/]")

    def set_stopped(self, filename: str) -> None:
        """Mark translation as stopped/paused."""
        badge = self.query_one("#stage_badge", Static)
        status_lbl = self.query_one("#engine_status_msg", Static)
        ch_label = self.query_one("#progress_chapter_name", Static)

        badge.update("[bold yellow] STOPPED [/]")
        ch_name = self._clean_chapter_name(filename)
        ch_label.update(f"[bold yellow]⏸ {ch_name}[/]")
        status_lbl.update(f"[bold yellow]⏹ Translation stopped for {filename}. Checkpoints preserved for resume.[/]")
