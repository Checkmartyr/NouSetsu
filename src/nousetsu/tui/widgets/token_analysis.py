"""Token analysis widget providing series-wide and per-folder metrics, stage breakdowns, and model costs."""
from typing import List, Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label, Select, Static, TabbedContent, TabPane
from nousetsu.analysis.token_metrics import ProjectTokenSummary, compute_token_summary
from nousetsu.storage.repository import NovelRepository
from nousetsu.utils.formatting import format_duration


class TokenAnalysisWidget(Widget):
    """Rich interactive dashboard displaying token usage, pipeline stage breakdown, and per-folder stats."""

    DEFAULT_CSS = """
    TokenAnalysisWidget {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    #filter-strip {
        height: 3;
        layout: horizontal;
        align-vertical: middle;
        margin-bottom: 1;
        dock: top;
        padding: 0 1;
        background: $surface;
        border: solid $accent 30%;
    }
    #lbl_folder_filter {
        margin-right: 1;
        text-style: bold;
        color: $text;
        height: 1;
    }
    #select_folder {
        width: 36;
        height: 3;
    }
    #filter_stats_summary {
        margin-left: 2;
        color: $text-muted;
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
        self.selected_folder: str = "ALL"
        self._last_folder_options: Optional[List[str]] = None
        self._dirty: bool = True

        # Cached widget references
        self._select_folder: Optional[Select] = None
        self._filter_stats_summary: Optional[Static] = None
        self._kpi_tokens_val: Optional[Static] = None
        self._kpi_tokens_sub: Optional[Static] = None
        self._kpi_duration_val: Optional[Static] = None
        self._kpi_duration_sub: Optional[Static] = None
        self._kpi_avg_val: Optional[Static] = None
        self._kpi_avg_sub: Optional[Static] = None
        self._kpi_chapters_val: Optional[Static] = None
        self._kpi_chapters_sub: Optional[Static] = None
        self._table_stages: Optional[DataTable] = None
        self._table_models: Optional[DataTable] = None
        self._table_folders: Optional[DataTable] = None
        self._table_chapters: Optional[DataTable] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="filter-strip"):
            yield Label("📁 Volume Scope:", id="lbl_folder_filter")
            yield Select(
                options=[("🌐 All Folders (Series)", "ALL")],
                value="ALL",
                allow_blank=False,
                id="select_folder"
            )
            yield Static("", id="filter_stats_summary")

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

            with TabPane("📁 Folders & Volumes", id="subtab-folders"):
                with Vertical(classes="analysis-table-container"):
                    yield DataTable(id="table-folders")

            with TabPane("📑 Chapter Rankings", id="subtab-chapters"):
                with Vertical(classes="analysis-table-container"):
                    yield DataTable(id="table-chapters")

    def on_mount(self) -> None:
        """Initialize data table schemas and load initial metrics."""
        self._select_folder = self.query_one("#select_folder", Select)
        self._filter_stats_summary = self.query_one("#filter_stats_summary", Static)
        self._kpi_tokens_val = self.query_one("#kpi_tokens_val", Static)
        self._kpi_tokens_sub = self.query_one("#kpi_tokens_sub", Static)
        self._kpi_duration_val = self.query_one("#kpi_duration_val", Static)
        self._kpi_duration_sub = self.query_one("#kpi_duration_sub", Static)
        self._kpi_avg_val = self.query_one("#kpi_avg_val", Static)
        self._kpi_avg_sub = self.query_one("#kpi_avg_sub", Static)
        self._kpi_chapters_val = self.query_one("#kpi_chapters_val", Static)
        self._kpi_chapters_sub = self.query_one("#kpi_chapters_sub", Static)

        self._table_stages = self.query_one("#table-stages", DataTable)
        self._table_stages.cursor_type = "row"
        self._table_stages.zebra_stripes = True
        self._table_stages.add_columns(
            "Stage", "Calls", "Total Tokens", "Input (Prompt)", "Output (Compl)", "Thought", "Cached", "Duration", "Avg Sec/Call"
        )

        self._table_models = self.query_one("#table-models", DataTable)
        self._table_models.cursor_type = "row"
        self._table_models.zebra_stripes = True
        self._table_models.add_columns(
            "Model", "Calls", "Total Tokens", "Input (Prompt)", "Output (Compl)", "Thought", "Cached", "Duration", "Avg Sec/Call"
        )

        self._table_folders = self.query_one("#table-folders", DataTable)
        self._table_folders.cursor_type = "row"
        self._table_folders.zebra_stripes = True
        self._table_folders.add_columns(
            "Folder / Volume", "Chapters", "Analyzed", "Total Tokens", "Prompt", "Output", "Thought", "Cached", "Total Runtime", "Avg Tokens/Ch"
        )

        self._table_chapters = self.query_one("#table-chapters", DataTable)
        self._table_chapters.cursor_type = "row"
        self._table_chapters.zebra_stripes = True
        self._table_chapters.add_columns(
            "#", "Chapter File", "Status", "Total Tokens", "Prompt", "Output", "Thought", "Duration"
        )

        self.refresh_metrics()

    def set_repo(self, repo: NovelRepository) -> None:
        """Switch active repository and refresh token analysis."""
        self.repo = repo
        self.selected_folder = "ALL"
        self._last_folder_options = None
        self._dirty = True
        self.refresh_metrics()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle volume scope filter change."""
        if event.select.id == "select_folder":
            val = str(event.value) if event.value is not None else "ALL"
            if val != self.selected_folder:
                self.selected_folder = val
                self.refresh_metrics(force=True)

    def refresh_metrics(self, force: bool = False) -> None:
        """Compute latest token metrics from repository and populate UI."""
        if not force and self.is_mounted:
            try:
                tabs = self.app.query_one("#main-tabs")
                if getattr(tabs, "active", None) != "tab-tokens":
                    self._dirty = True
                    return
            except Exception:
                pass

        self._dirty = False
        try:
            chapters = self.repo.load_all_metadata()
        except Exception:
            chapters = {}

        summary = compute_token_summary(chapters, folder_filter=self.selected_folder)
        self.current_summary = summary

        # 1. Update Folder Selector Options
        try:
            select_ctrl = self._select_folder or self.query_one("#select_folder", Select)
            if self._last_folder_options != summary.available_folders:
                self._last_folder_options = list(summary.available_folders)
                current_options = [("🌐 All Folders (Series)", "ALL")] + [
                    (f"📁 {f}", f) for f in summary.available_folders
                ]
                select_ctrl.set_options(current_options)
                if self.selected_folder in summary.available_folders:
                    select_ctrl.value = self.selected_folder
                else:
                    select_ctrl.value = "ALL"
                    self.selected_folder = "ALL"

            scope_desc = "Entire Series" if self.selected_folder == "ALL" else f"Volume: {self.selected_folder}"
            filter_stats = self._filter_stats_summary or self.query_one("#filter_stats_summary", Static)
            filter_stats.update(
                f"[dim]Viewing:[/] [bold cyan]{scope_desc}[/] ([dim]{summary.total_chapters} chapters[/])"
            )
        except Exception:
            pass

        # 2. Update KPI Cards
        try:
            tokens_val = self._kpi_tokens_val or self.query_one("#kpi_tokens_val", Static)
            tokens_val.update(f"[bold cyan]{summary.total_tokens:,}[/]")
            tokens_sub = self._kpi_tokens_sub or self.query_one("#kpi_tokens_sub", Static)
            tokens_sub.update(
                f"In: {summary.prompt_tokens:,} | Out: {summary.completion_tokens:,} | Thought: {summary.thought_tokens:,} | Cached: {summary.cached_tokens:,}"
            )

            dur_val = self._kpi_duration_val or self.query_one("#kpi_duration_val", Static)
            dur_val.update(f"[bold green]{summary.formatted_duration}[/]")
            dur_sub = self._kpi_duration_sub or self.query_one("#kpi_duration_sub", Static)
            dur_sub.update(f"{summary.total_duration_seconds:.1f}s total compute")

            avg_val = self._kpi_avg_val or self.query_one("#kpi_avg_val", Static)
            avg_val.update(f"[bold yellow]{summary.avg_tokens_per_chapter:,.0f}[/]")
            avg_sub = self._kpi_avg_sub or self.query_one("#kpi_avg_sub", Static)
            avg_sub.update(f"Avg time: {format_duration(summary.avg_duration_per_chapter)}")

            ch_val = self._kpi_chapters_val or self.query_one("#kpi_chapters_val", Static)
            ch_val.update(f"[bold magenta]{summary.analyzed_chapters}[/] / {summary.total_chapters}")
            ch_sub = self._kpi_chapters_sub or self.query_one("#kpi_chapters_sub", Static)
            ch_sub.update(f"{summary.analyzed_chapters} with token stats")
        except Exception:
            pass

        # 3. Populate Stages Table
        try:
            t_stages = self._table_stages or self.query_one("#table-stages", DataTable)
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

        # 4. Populate Models Table
        try:
            t_models = self._table_models or self.query_one("#table-models", DataTable)
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

        # 5. Populate Folders Table
        try:
            t_folders = self._table_folders or self.query_one("#table-folders", DataTable)
            t_folders.clear()
            for fm in summary.folder_metrics:
                is_selected = (fm.folder.lower() == self.selected_folder.lower())
                folder_label = f"[bold green]▶ {fm.folder}[/]" if is_selected else f"[bold]{fm.folder}[/]"
                t_folders.add_row(
                    folder_label,
                    str(fm.chapter_count),
                    str(fm.analyzed_chapters),
                    f"[cyan]{fm.total_tokens:,}[/]",
                    f"{fm.input_tokens:,}",
                    f"{fm.output_tokens:,}",
                    f"{fm.thought_tokens:,}",
                    f"{fm.cached_tokens:,}",
                    fm.formatted_duration,
                    f"{fm.avg_tokens:,.0f}"
                )
        except Exception:
            pass

        # 6. Populate Chapters Table
        try:
            t_chapters = self._table_chapters or self.query_one("#table-chapters", DataTable)
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
