"""Live translation progress visualizer widget."""
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
    #engine_progress {
        height: 1;
        margin-top: 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="panel-header-row"):
                yield Static("[bold green] IDLE [/]", id="stage_badge", classes="stage-badge")
                yield Static("Engine ready. Select chapter or batch to begin.", id="engine_status_msg")
            yield ProgressBar(id="engine_progress", total=100, show_eta=False, show_percentage=True)

    def update_progress(self, filename: str, stage: PipelineStage, msg: str, percent: float) -> None:
        """Update live badge, progress bar, and status message from worker thread."""
        badge = self.query_one("#stage_badge", Static)
        pbar = self.query_one("#engine_progress", ProgressBar)
        status_lbl = self.query_one("#engine_status_msg", Static)

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
        status_lbl.update(f"[cyan]{filename}[/]: {msg}")

    def set_finished(self, filename: str) -> None:
        """Mark chapter or batch as finished."""
        badge = self.query_one("#stage_badge", Static)
        pbar = self.query_one("#engine_progress", ProgressBar)
        status_lbl = self.query_one("#engine_status_msg", Static)

        badge.update("[bold green] COMPLETED [/]")
        pbar.update(progress=100)
        status_lbl.update(f"[bold green]✓ Completed translation for {filename}![/]")

    def set_failed(self, filename: str, err: str) -> None:
        """Mark chapter as failed."""
        badge = self.query_one("#stage_badge", Static)
        status_lbl = self.query_one("#engine_status_msg", Static)

        badge.update("[bold red] FAILED [/]")
        status_lbl.update(f"[bold red]❌ Failed {filename}: {err}[/]")

    def set_stopped(self, filename: str) -> None:
        """Mark translation as stopped/paused."""
        badge = self.query_one("#stage_badge", Static)
        status_lbl = self.query_one("#engine_status_msg", Static)

        badge.update("[bold yellow] STOPPED [/]")
        status_lbl.update(f"[bold yellow]⏹ Translation stopped for {filename}. Checkpoints preserved for resume.[/]")
