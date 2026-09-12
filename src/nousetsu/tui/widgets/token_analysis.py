"""Token analysis widget providing series-wide metrics, stage breakdowns, and model costs."""
from typing import Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label, Static, TabbedContent, TabPane
from nousetsu.analysis.token_metrics import ProjectTokenSummary, compute_token_summary
from nousetsu.storage.repository import NovelRepository
from nousetsu.utils.formatting import format_duration


class TokenAnalysisWidget(Widget):
    """Rich interactive dashboard displaying token usage, pipeline stage breakdown, and model stats."""

    DEFAULT_CSS = """
    TokenAnalysisWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #kpi-strip {
        layout: horizontal;
        height: 5;
        margin-bottom: 1;
        dock: top;
    }
    .kpi-card {
        width: 1fr;
        height: 100%;
        border: solid $accent 35%;
        padding: 0 1;
        margin-right: 1;
        background: $surface;
    }
    .kpi-card-last {
        margin-right: 0;
    }
    .kpi-val {
        color: $accent;
        text-style: bold;
    }
    .kpi-lbl {
        color: $text;
        text-style: bold;
    }
    .kpi-sub {
        color: $text-muted;
    }
    #analysis-subtabs {
        height: 1fr;
    }
    .analysis-table-container {
        height: 1fr;
        border: solid $primary 30%;
    }
    DataTable {
        height: 1fr;
    }
    """

    def __init__(self, repo: NovelRepository, id: Optional[str] = None):
        super().__init__(id=id)
        self.repo = repo
        self.current_summary: Optional[ProjectTokenSummary] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="kpi-strip"):
            with Vertical(classes="kpi-card", id="card_tokens"):
                yield Static("0", id="kpi_tokens_val", classes="kpi-val")
                yield Label("Total Tokens", classes="kpi-lbl")
                yield Static("In: 0 | Out: 0 | Thought: 0", id="kpi_tokens_sub", classes="kpi-sub")

            with Vertical(classes="kpi-card", id="card_duration"):
                yield Static("0s", id="kpi_duration_val", classes="kpi-val")
                yield Label("Total Runtime", classes="kpi-lbl")
                yield Static("0s compute", id="kpi_duration_sub", classes="kpi-sub")

            with Vertical(classes="kpi-card", id="card_avg"):
                yield Static("0", id="kpi_avg_val", classes="kpi-val")
                yield Label("Avg / Chapter", classes="kpi-lbl")
                yield Static("Avg time: 0s", id="kpi_avg_sub", classes="kpi-sub")

            with Vertical(classes="kpi-card kpi-card-last", id="card_chapters"):
                yield Static("0", id="kpi_chapters_val", classes="kpi-val")
                yield Label("Analyzed Chapters", classes="kpi-lbl")
                yield Static("0 total chapters", id="kpi_chapters_sub", classes="kpi-sub")

        with TabbedContent(id="analysis-subtabs", initial="subtab-stages"):
            with TabPane("🎯 Pipeline Stages", id="subtab-stages"):
                with Vertical(classes="analysis-table-container"):
                    yield DataTable(id="table-stages")

            with TabPane("🤖 LLM Models", id="subtab-models"):
                with Vertical(classes="analysis-table-container"):
                    yield DataTable(id="table-models")

            with TabPane("📑 Chapter Rankings", id="subtab-chapters"):
                with Vertical(classes="analysis-table-container"):
                    yield DataTable(id="table-chapters")

    def on_mount(self) -> None:
        """Initialize data table schemas and load initial metrics."""
        table_stages = self.query_one("#table-stages", DataTable)
        table_stages.cursor_type = "row"
        table_stages.zebra_stripes = True
        table_stages.add_columns(
            "Stage", "Calls", "Total Tokens", "Input (Prompt)", "Output (Compl)", "Thought", "Cached", "Duration", "Avg Sec/Call"
        )

        table_models = self.query_one("#table-models", DataTable)
        table_models.cursor_type = "row"
        table_models.zebra_stripes = True
        table_models.add_columns(
            "Model", "Calls", "Total Tokens", "Input (Prompt)", "Output (Compl)", "Thought", "Cached", "Duration", "Avg Sec/Call"
        )

        table_chapters = self.query_one("#table-chapters", DataTable)
        table_chapters.cursor_type = "row"
        table_chapters.zebra_stripes = True
        table_chapters.add_columns(
            "#", "Chapter File", "Status", "Total Tokens", "Prompt", "Output", "Thought", "Duration"
        )

        self.refresh_metrics()

    def set_repo(self, repo: NovelRepository) -> None:
        """Switch active repository and refresh token analysis."""
        self.repo = repo
        self.refresh_metrics()

    def refresh_metrics(self) -> None:
        """Compute latest token metrics from repository and populate UI."""
        try:
            chapters = self.repo.load_all_metadata()
        except Exception:
            chapters = {}

        summary = compute_token_summary(chapters)
        self.current_summary = summary

        # 1. Update KPI Cards
        try:
            self.query_one("#kpi_tokens_val", Static).update(f"[bold cyan]{summary.total_tokens:,}[/]")
            self.query_one("#kpi_tokens_sub", Static).update(
                f"In: {summary.prompt_tokens:,} | Out: {summary.completion_tokens:,} | Thought: {summary.thought_tokens:,} | Cached: {summary.cached_tokens:,}"
            )

            self.query_one("#kpi_duration_val", Static).update(f"[bold green]{summary.formatted_duration}[/]")
            self.query_one("#kpi_duration_sub", Static).update(f"{summary.total_duration_seconds:.1f}s total compute")

            self.query_one("#kpi_avg_val", Static).update(f"[bold yellow]{summary.avg_tokens_per_chapter:,.0f}[/]")
            self.query_one("#kpi_avg_sub", Static).update(f"Avg time: {format_duration(summary.avg_duration_per_chapter)}")

            self.query_one("#kpi_chapters_val", Static).update(f"[bold magenta]{summary.analyzed_chapters}[/] / {summary.total_chapters}")
            self.query_one("#kpi_chapters_sub", Static).update(f"{summary.analyzed_chapters} with token stats")
        except Exception:
            pass

        # 2. Populate Stages Table
        try:
            t_stages = self.query_one("#table-stages", DataTable)
            t_stages.clear()
            for sm in summary.stage_metrics:
                t_stages.add_row(
                    f"[bold]{sm.stage.upper()}[/]",
                    str(sm.calls),
                    f"[cyan]{sm.total_tokens:,}[/]",
                    f"{sm.input_tokens:,}",
                    f"{sm.output_tokens:,}",
                    f"{sm.thought_tokens:,}",
                    f"{sm.cached_tokens:,}",
                    sm.formatted_duration,
                    f"{sm.avg_duration:.2f}s"
                )
        except Exception:
            pass

        # 3. Populate Models Table
        try:
            t_models = self.query_one("#table-models", DataTable)
            t_models.clear()
            for mm in summary.model_metrics:
                t_models.add_row(
                    f"[bold]{mm.model}[/]",
                    str(mm.calls),
                    f"[cyan]{mm.total_tokens:,}[/]",
                    f"{mm.input_tokens:,}",
                    f"{mm.output_tokens:,}",
                    f"{mm.thought_tokens:,}",
                    f"{mm.cached_tokens:,}",
                    mm.formatted_duration,
                    f"{mm.avg_duration:.2f}s"
                )
        except Exception:
            pass

        # 4. Populate Chapters Table
        try:
            t_chapters = self.query_one("#table-chapters", DataTable)
            t_chapters.clear()
            for cm in summary.chapter_rankings:
                status_color = "green" if cm.status == "completed" else ("red" if cm.status == "failed" else "yellow")
                t_chapters.add_row(
                    str(cm.chapter_num),
                    cm.source_file,
                    f"[{status_color}]{cm.status.upper()}[/]",
                    f"[cyan]{cm.total_tokens:,}[/]",
                    f"{cm.prompt_tokens:,}",
                    f"{cm.completion_tokens:,}",
                    f"{cm.thought_tokens:,}",
                    cm.formatted_duration
                )
        except Exception:
            pass
