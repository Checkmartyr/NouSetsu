"""Main Textual TUI Application for Novel Translation Agent."""
from pathlib import Path
from typing import List, Optional
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Static
from nousetsu.batch.runner import BatchRunner
from nousetsu.batch.scanner import ChapterScanner, ChapterTask
from nousetsu.models.config import ProjectConfig
from nousetsu.models.metadata import PipelineStage, StageStatus
from nousetsu.storage.repository import NovelRepository, ProjectRegistry
from nousetsu.tui.widgets.bible_editor import NovelBibleModal
from nousetsu.tui.widgets.checkpoint_inspector import CheckpointInspectorWidget
from nousetsu.tui.widgets.new_project_modal import NewProjectModal
from nousetsu.tui.widgets.progress_panel import ProgressPanel
from nousetsu.tui.widgets.project_selector_modal import ProjectSelectorModal
from nousetsu.tui.widgets.reader import DualReaderWidget
from nousetsu.tui.widgets.settings_modal import SettingsModal


class ChapterListItem(ListItem):
    """Custom list item representing a chapter task."""

    def __init__(self, task: ChapterTask):
        super().__init__()
        self.chapter_task = task

    def compose(self) -> ComposeResult:
        if self.chapter_task.is_completed:
            badge = r"[bold green]✓ DONE[/]"
        elif self.chapter_task.is_failed:
            badge = r"[bold red]✕ FAILED[/]"
        elif self.chapter_task.is_paused:
            badge = rf"[bold yellow]⏸ PAUSE:{self.chapter_task.resume_stage.value[:4].upper()}[/]"
        elif self.chapter_task.needs_resume:
            badge = rf"[bold yellow]● RESUME:{self.chapter_task.resume_stage.value[:4].upper()}[/]"
        else:
            badge = r"[dim]· WAIT[/]"

        yield Static(f"{badge} Ch.{self.chapter_task.chapter_num:03d} - {self.chapter_task.source_file.name}")


class NovelAgentApp(App):
    """Textual TUI for managing novel translation, viewing checkpoints, and editing the Novel Bible."""

    TITLE = "Novel Translation Agent"
    CSS = """
    Screen {
        background: $background;
    }
    #main-container {
        height: 1fr;
    }
    #sidebar {
        width: 38;
        border-right: solid $accent 50%;
        padding: 0 1;
        background: $surface;
    }
    .pane-title {
        text-style: bold;
        color: $accent;
        height: 1;
        margin-bottom: 0;
    }
    #chapter-list {
        height: 1fr;
        border: solid $primary 50%;
        margin-bottom: 0;
    }
    #sidebar-toolbar {
        height: auto;
        margin-top: 1;
        padding-bottom: 0;
    }
    .toolbar-row {
        height: auto;
        margin-bottom: 1;
        align-horizontal: center;
    }
    .tool-btn {
        height: 1;
        min-width: 6;
        border: none;
        padding: 0 1;
        margin: 0 1 0 0;
    }
    #content-pane {
        width: 1fr;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_chapters", "Refresh"),
        Binding("b", "run_batch", "Run Batch"),
        Binding("t", "translate_selected", "Translate"),
        Binding("x", "stop_translation", "Stop"),
        Binding("e", "edit_bible", "Novel Bible"),
        Binding("p", "open_project_selector", "Projects"),
        Binding("n", "open_new_project", "New Project"),
        Binding("s", "open_settings", "Settings"),
    ]

    def __init__(
        self,
        input_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        project_dir: Optional[Path | str] = None
    ):
        super().__init__()
        self.registry = ProjectRegistry()

        if project_dir is not None and str(project_dir) != ".":
            self.project_dir = Path(project_dir).expanduser().resolve()
        else:
            last_proj = self.registry.get_last_active_project()
            if last_proj:
                self.project_dir = last_proj
            else:
                self.project_dir = Path(project_dir or ".").expanduser().resolve()

        self.repo = NovelRepository(self.project_dir)
        cfg = self.repo.load_config()

        if input_dir and input_dir != "raw_chapters":
            self.input_dir = Path(input_dir).expanduser().resolve()
        else:
            self.input_dir = cfg.get_raw_path(self.project_dir)

        if output_dir and output_dir != "translated_chapters":
            self.output_dir = Path(output_dir).expanduser().resolve()
        else:
            self.output_dir = cfg.get_output_path(self.project_dir)

        self.model_name = model_name or cfg.model_name
        self.scanner = ChapterScanner(self.repo)
        self.runner = BatchRunner(self.repo, model_name=self.model_name)
        self.current_tasks: List[ChapterTask] = []
        self.selected_task: Optional[ChapterTask] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with Vertical(id="sidebar"):
                yield Label("📚 Chapters", classes="pane-title")
                yield ListView(id="chapter-list")
                with Vertical(id="sidebar-toolbar"):
                    with Horizontal(classes="toolbar-row"):
                        yield Button("▶ Trans (T)", variant="primary", id="btn_translate", classes="tool-btn")
                        yield Button("⚡ Batch (B)", variant="warning", id="btn_batch", classes="tool-btn")
                        yield Button("⏹ Stop (X)", variant="error", id="btn_stop", classes="tool-btn", disabled=True)
                    with Horizontal(classes="toolbar-row"):
                        yield Button("📖 Bible", variant="default", id="btn_bible", classes="tool-btn")
                        yield Button("📁 Proj", variant="default", id="btn_projects", classes="tool-btn")
                        yield Button("✨ New", variant="success", id="btn_new_project", classes="tool-btn")
                        yield Button("⚙ Set", variant="default", id="btn_settings", classes="tool-btn")

            with Vertical(id="content-pane"):
                yield ProgressPanel(id="progress_panel")
                yield DualReaderWidget(id="reader")
                yield CheckpointInspectorWidget(id="inspector")

        yield Footer()

    def on_mount(self) -> None:
        self.repo.load_bible()
        cfg = self.repo.load_config()
        self.title = f"Novel Translation Agent - {cfg.title}"
        self.registry.set_last_active_project(self.project_dir)
        self.action_refresh_chapters()

    def switch_project(self, new_dir: Path) -> None:
        """Switch active project directory and refresh state."""
        self.project_dir = Path(new_dir).expanduser().resolve()
        self.registry.set_last_active_project(self.project_dir)
        self.repo = NovelRepository(self.project_dir)
        cfg = self.repo.load_config()
        self.input_dir = cfg.get_raw_path(self.project_dir)
        self.output_dir = cfg.get_output_path(self.project_dir)
        self.model_name = cfg.model_name
        self.repo.load_bible()
        self.scanner = ChapterScanner(self.repo)
        self.runner = BatchRunner(self.repo, model_name=self.model_name)

        self.title = f"Novel Translation Agent - {cfg.title}"
        try:
            progress = self.query_one("#progress_panel", ProgressPanel)
            progress.query_one("#engine_status_msg", Static).update(
                f"[bold cyan]Active Project:[/] {cfg.title} ({cfg.source_language} -> {cfg.target_language})"
            )
        except Exception:
            pass

        self.notify(f"Active project: {cfg.title}", severity="information")
        self.action_refresh_chapters()

    def action_refresh_chapters(self) -> None:
        """Scan input directory and update chapter list view."""
        self.current_tasks = self.scanner.scan_directory(self.input_dir, self.output_dir)
        list_view = self.query_one("#chapter-list", ListView)
        list_view.clear()

        for task in self.current_tasks:
            list_view.append(ChapterListItem(task))

        if self.current_tasks:
            self._select_task(self.current_tasks[0])
        else:
            self.selected_task = None
            reader = self.query_one("#reader", DualReaderWidget)
            inspector = self.query_one("#inspector", CheckpointInspectorWidget)
            reader.update_content("", "")
            inspector.update_metadata(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ChapterListItem):
            self._select_task(event.item.chapter_task)

    def _select_task(self, task: ChapterTask) -> None:
        self.selected_task = task
        reader = self.query_one("#reader", DualReaderWidget)
        inspector = self.query_one("#inspector", CheckpointInspectorWidget)

        src_text = ""
        if task.source_file.exists():
            try:
                with open(task.source_file, "r", encoding="utf-8") as f:
                    src_text = f.read()
            except Exception as e:
                src_text = f"Error reading source file: {e}"

        tgt_text = ""
        if task.output_file.exists():
            try:
                with open(task.output_file, "r", encoding="utf-8") as f:
                    tgt_text = f.read()
            except Exception:
                tgt_text = ""

        # Load freshest metadata
        meta = self.repo.load_metadata(task.output_file)
        reader.update_content(src_text, tgt_text)
        inspector.update_metadata(meta)

    def action_open_project_selector(self) -> None:
        self.push_screen(ProjectSelectorModal(self))

    def action_open_new_project(self) -> None:
        self.push_screen(NewProjectModal(self))

    def action_edit_bible(self) -> None:
        self.push_screen(NovelBibleModal(self.repo))

    def action_open_settings(self) -> None:
        self.push_screen(SettingsModal(self.repo, self))

    def _set_translating_ui(self, is_translating: bool) -> None:
        try:
            btn_stop = self.query_one("#btn_stop", Button)
            btn_batch = self.query_one("#btn_batch", Button)
            btn_translate = self.query_one("#btn_translate", Button)
            btn_stop.disabled = not is_translating
            btn_batch.disabled = is_translating
            btn_translate.disabled = is_translating
        except Exception:
            pass

    def action_stop_translation(self) -> None:
        """Signal runner to halt ongoing translation."""
        self.runner.stop()
        self.notify("🛑 Stop signal sent! Halting translation cleanly...", severity="warning")
        try:
            progress_panel = self.query_one("#progress_panel", ProgressPanel)
            progress_panel.set_stopped("Active Translation")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_translate":
            self.action_translate_selected()
        elif event.button.id == "btn_batch":
            self.action_run_batch()
        elif event.button.id == "btn_stop":
            self.action_stop_translation()
        elif event.button.id == "btn_bible":
            self.action_edit_bible()
        elif event.button.id == "btn_projects":
            self.action_open_project_selector()
        elif event.button.id == "btn_new_project":
            self.action_open_new_project()
        elif event.button.id == "btn_settings":
            self.action_open_settings()

    @work(thread=True)
    def action_translate_selected(self) -> None:
        if not self.selected_task:
            self.notify("No chapter selected to translate!", severity="warning")
            return

        self.app.call_from_thread(self._set_translating_ui, True)
        task = self.selected_task
        task_filename = task.source_file.name
        self.notify(f"Translating Chapter {task.chapter_num}...", severity="information")
        progress_panel = self.query_one("#progress_panel", ProgressPanel)

        def stage_cb(fn: str, stg: PipelineStage, msg: str, pct: float):
            self.app.call_from_thread(progress_panel.update_progress, fn, stg, msg, pct)

        try:
            self.runner.run_batch(
                input_dir=self.input_dir,
                output_dir=self.output_dir,
                force_retranslate=True,
                tasks=[task],
                stage_callback=stage_cb
            )
            if self.runner.is_stopped:
                self.app.call_from_thread(progress_panel.set_stopped, task_filename)
                self.notify(f"Chapter {task.chapter_num} translation stopped.", severity="warning")
            else:
                self.app.call_from_thread(progress_panel.set_finished, task_filename)
                self.notify(f"Chapter {task.chapter_num} translation complete!", severity="information")
            self.app.call_from_thread(self.action_refresh_chapters)
        except Exception as e:
            self.app.call_from_thread(progress_panel.set_failed, task_filename, str(e))
            self.notify(f"Translation failed: {e}", severity="error")
        finally:
            self.app.call_from_thread(self._set_translating_ui, False)

    @work(thread=True)
    def action_run_batch(self) -> None:
        self.app.call_from_thread(self._set_translating_ui, True)
        self.notify("Starting batch translation...", severity="information")
        progress_panel = self.query_one("#progress_panel", ProgressPanel)

        def stage_cb(fn: str, stg: PipelineStage, msg: str, pct: float):
            self.app.call_from_thread(progress_panel.update_progress, fn, stg, msg, pct)

        try:
            self.runner.run_batch(
                input_dir=self.input_dir,
                output_dir=self.output_dir,
                stage_callback=stage_cb
            )
            if self.runner.is_stopped:
                self.app.call_from_thread(progress_panel.set_stopped, "Batch")
                self.notify("Batch translation stopped by user.", severity="warning")
            else:
                self.app.call_from_thread(progress_panel.set_finished, "Batch")
                self.notify("Batch translation finished!", severity="information")
            self.app.call_from_thread(self.action_refresh_chapters)
        except Exception as e:
            self.app.call_from_thread(progress_panel.set_failed, "Batch", str(e))
            self.notify(f"Batch translation failed: {e}", severity="error")
        finally:
            self.app.call_from_thread(self._set_translating_ui, False)
