"""Modal for switching between novel translation projects."""
from pathlib import Path
from typing import Dict, List, Optional
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static
from nousetsu.storage.repository import NovelRepository, ProjectRegistry
from nousetsu.tui.widgets.new_project_modal import NewProjectModal


class ProjectListItem(ListItem):
    """List item representing a registered novel translation project."""

    def __init__(self, project_info: dict):
        super().__init__()
        self.project_info = project_info
        self.project_path = Path(project_info["path"]).resolve()

    def compose(self) -> ComposeResult:
        title = self.project_info.get("title", "Untitled Novel")
        path_str = str(self.project_path)
        src_lang = self.project_info.get("source_language", "Japanese")
        tgt_lang = self.project_info.get("target_language", "English")
        raw_dir = self.project_info.get("raw_dir", "raw_chapters")
        out_dir = self.project_info.get("output_dir", "translated_chapters")

        with Vertical():
            yield Label(f"[bold cyan]📁 {title}[/]", classes="project-item-title")
            yield Static(f"[dim]{path_str}[/]", classes="project-item-path")
            yield Static(
                f"[yellow]{src_lang} -> {tgt_lang}[/] | Raw: [dim]{raw_dir}[/] | Out: [dim]{out_dir}[/]",
                classes="project-item-meta"
            )


class ProjectSelectorModal(ModalScreen):
    """Modal dialog allowing user to choose active project, open external path, or create new."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    ProjectSelectorModal {
        align: center middle;
    }
    #project-selector-dialog {
        width: 88%;
        height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #project-list {
        height: 1fr;
        border: solid $accent;
        margin: 1 0;
    }
    .project-item-title {
        margin-top: 0;
    }
    .project-item-path {
        color: $text-muted;
    }
    .project-item-meta {
        margin-bottom: 1;
        color: $text-muted;
    }
    .open-path-row {
        height: auto;
        margin-bottom: 1;
    }
    #inp_custom_path {
        width: 1fr;
        margin-right: 1;
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
        self.projects: List[dict] = []
        self.selected_item: Optional[ProjectListItem] = None

    def compose(self) -> ComposeResult:
        with Container(id="project-selector-dialog"):
            yield Label("📁 Select Novel Translation Project", classes="pane-title")

            with Horizontal(classes="open-path-row"):
                yield Input(
                    placeholder="Enter or paste path to any project (e.g. D:\\Novels\\MyNovel or project\\Villainess)...",
                    id="inp_custom_path"
                )
                yield Button("Open Path", variant="warning", id="btn_open_path")

            self.projects = self.registry.list_projects()
            if self.projects:
                with ListView(id="project-list"):
                    for proj in self.projects:
                        yield ProjectListItem(proj)
            else:
                yield Static(
                    "\n[bold yellow]No registered novel projects found.[/]\n"
                    "Enter a path above, or click '+ New Project' below to initialize a workspace!\n",
                    id="empty_projects_msg"
                )

            with Horizontal(classes="btn-row"):
                yield Button("Select Project", variant="primary", id="btn_select", disabled=not bool(self.projects))
                yield Button("+ New Project", variant="success", id="btn_new_proj")
                yield Button("Close", variant="default", id="btn_close")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ProjectListItem):
            self.selected_item = event.item
            self._switch_to_selected()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, ProjectListItem):
            self.selected_item = event.item

    def _switch_to_selected(self) -> None:
        if self.selected_item:
            self.registry.set_last_active_project(self.selected_item.project_path)
            self.app_instance.switch_project(self.selected_item.project_path)
            self.dismiss()

    def _open_custom_path(self) -> None:
        raw_input = self.query_one("#inp_custom_path", Input).value.strip()
        if not raw_input:
            self.app_instance.notify("Please enter a valid directory path!", severity="warning")
            return

        target_path = Path(raw_input).expanduser().resolve()
        if not target_path.exists():
            self.app_instance.notify(f"Directory not found: {target_path}", severity="error")
            return

        # If not initialized, initialize default project config
        repo = NovelRepository(target_path)
        if not (target_path / ".novel").exists():
            repo.initialize_project(title=target_path.name)

        self.registry.register_project(target_path)
        self.registry.set_last_active_project(target_path)
        self.app_instance.switch_project(target_path)
        self.dismiss()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "inp_custom_path":
            self._open_custom_path()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_close":
            self.dismiss()
        elif event.button.id == "btn_open_path":
            self._open_custom_path()
        elif event.button.id == "btn_new_proj":
            self.dismiss()
            self.app_instance.push_screen(NewProjectModal(self.app_instance))
        elif event.button.id == "btn_select":
            if not self.selected_item:
                list_view = self.query(ListView).first()
                if list_view and list_view.children:
                    first_child = list_view.children[0]
                    if isinstance(first_child, ProjectListItem):
                        self.selected_item = first_child
            if self.selected_item:
                self._switch_to_selected()
            else:
                self.app_instance.notify("Please select a project from the list.", severity="warning")
