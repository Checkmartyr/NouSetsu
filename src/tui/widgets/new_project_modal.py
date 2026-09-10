"""Modal for creating and initializing a new novel translation project."""
from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from src.storage.repository import NovelRepository, ProjectRegistry


class NewProjectModal(ModalScreen):
    """Modal dialog to initialize a new novel translation project from TUI."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    NewProjectModal {
        align: center middle;
    }
    #new-project-dialog {
        width: 80%;
        height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    .form-label {
        margin-top: 1;
        color: $text-muted;
    }
    .btn-row {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.registry = ProjectRegistry()

    def compose(self) -> ComposeResult:
        with Container(id="new-project-dialog"):
            yield Label("✨ Initialize New Novel Translation Project", classes="pane-title")

            with VerticalScroll():
                yield Label("Novel Title:", classes="form-label")
                yield Input(placeholder="e.g. The Rising of the Shield Hero", id="inp_title")

                yield Label("Project Folder Path (Absolute or relative path, e.g. D:\\Novels\\Book or project\\book):", classes="form-label")
                yield Input(placeholder="e.g. D:\\Novels\\MyNovel or project\\my_novel", value="project/new_novel", id="inp_path")

                yield Label("Source Language (or 'Auto' to detect from raw chapters):", classes="form-label")
                yield Input(value="Auto", id="inp_src_lang")

                yield Label("Target Language:", classes="form-label")
                yield Input(value="English", id="inp_tgt_lang")

                yield Label("Raw Chapters Input Folder Name / Path:", classes="form-label")
                yield Input(value="raw_chapters", id="inp_raw_dir")

                yield Label("Translated Output Folder Name / Path:", classes="form-label")
                yield Input(value="translated_chapters", id="inp_out_dir")

                yield Label("Default LLM Model Name:", classes="form-label")
                yield Input(value="gemini-2.5-pro", id="inp_model")

                yield Label("Novel Genre (e.g. general, xianxia, isekai, litrpg, romance, auto):", classes="form-label")
                yield Input(value="general", id="inp_genre")

                yield Static("", id="new_proj_status")

            with Horizontal(classes="btn-row"):
                yield Button("Initialize & Open Project", variant="primary", id="btn_create")
                yield Button("Cancel", variant="default", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss()
        elif event.button.id == "btn_create":
            title = self.query_one("#inp_title", Input).value.strip() or "Untitled Novel"
            proj_path_str = self.query_one("#inp_path", Input).value.strip() or "project/new_novel"
            src_lang = self.query_one("#inp_src_lang", Input).value.strip() or "Auto"
            tgt_lang = self.query_one("#inp_tgt_lang", Input).value.strip() or "English"
            raw_dir = self.query_one("#inp_raw_dir", Input).value.strip() or "raw_chapters"
            out_dir = self.query_one("#inp_out_dir", Input).value.strip() or "translated_chapters"
            model = self.query_one("#inp_model", Input).value.strip() or "gemini-2.5-pro"
            genre = self.query_one("#inp_genre", Input).value.strip() or "general"
            status = self.query_one("#new_proj_status", Static)

            target_path = Path(proj_path_str).expanduser().resolve()
            target_path.mkdir(parents=True, exist_ok=True)

            repo = NovelRepository(target_path)
            repo.initialize_project(
                title=title,
                source_lang=src_lang,
                target_lang=tgt_lang,
                raw_dir=raw_dir,
                output_dir=out_dir,
                model_name=model,
                genre=genre
            )

            self.registry.register_project(target_path)
            self.registry.set_last_active_project(target_path)

            status.update(f"[bold green]✓ Initialized project at {target_path}![/]")
            # Switch active project in TUI
            self.app_instance.switch_project(target_path)
            self.dismiss()
