"""Modal for switching between translation folders within a single novel project."""
from pathlib import Path
from typing import List, Optional, Tuple
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static


class FolderListItem(ListItem):
    """List item representing a discovered translation folder pair."""

    def __init__(self, raw_folder: str, output_folder: str, chapter_count: int, is_active: bool = False):
        super().__init__()
        self.raw_folder = raw_folder
        self.output_folder = output_folder
        self.chapter_count = chapter_count
        self.is_active = is_active

    def compose(self) -> ComposeResult:
        active_badge = " [bold green]● ACTIVE[/]" if self.is_active else ""
        with Vertical():
            yield Label(f"[bold cyan]📂 {self.raw_folder}[/]{active_badge}", classes="folder-item-title")
            yield Static(
                f"[yellow]{self.chapter_count} chapters[/] | Output: [dim]{self.output_folder}[/]",
                classes="folder-item-meta"
            )


class FolderSelectModal(ModalScreen):
    """Modal dialog allowing user to choose active translation folder or specify custom paths."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    FolderSelectModal {
        align: center middle;
    }
    #folder-selector-dialog {
        width: 80%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #folder-list {
        height: 1fr;
        border: solid $accent;
        margin: 1 0;
    }
    .folder-item-title {
        margin-top: 0;
    }
    .folder-item-meta {
        margin-bottom: 1;
        color: $text-muted;
    }
    .custom-path-row {
        height: auto;
        margin-bottom: 1;
    }
    .custom-input {
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
        self.discovered: List[Tuple[str, str, int]] = []
        self.selected_item: Optional[FolderListItem] = None

    def compose(self) -> ComposeResult:
        with Container(id="folder-selector-dialog"):
            yield Label("📂 Select Translation Folder", classes="pane-title")
            yield Static(
                "[dim]Switch active translation folder while sharing the same Novel Bible, glossary, and settings.[/]"
            )

            yield ListView(id="folder-list")

            with Horizontal(classes="custom-path-row"):
                yield Input(
                    placeholder="Custom raw folder (e.g. Villainess_05 or raw_chapters/vol2)...",
                    id="inp_custom_raw",
                    classes="custom-input"
                )
                yield Input(
                    placeholder="Custom output folder (e.g. Villainess_05_th)...",
                    id="inp_custom_out",
                    classes="custom-input"
                )

            with Horizontal(classes="btn-row"):
                yield Button("Select Folder", variant="primary", id="btn_switch_folder")
                yield Button("Apply Custom", variant="success", id="btn_apply_custom")
                yield Button("Close", variant="default", id="btn_close_folder")

    def on_mount(self) -> None:
        self.refresh_folder_list()

    def refresh_folder_list(self) -> None:
        list_view = self.query_one("#folder-list", ListView)
        list_view.clear()

        repo = self.app_instance.repo
        cfg = repo.load_config()
        active_raw = Path(cfg.raw_dir).name if cfg.raw_dir else ""

        self.discovered = repo.discover_folders()

        for raw_f, out_f, count in self.discovered:
            is_active = (raw_f.lower() == active_raw.lower())
            list_view.append(FolderListItem(raw_f, out_f, count, is_active=is_active))

        if not self.discovered:
            list_view.append(ListItem(Label("[yellow]No chapter subfolders discovered. Use custom fields below.[/]")))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, FolderListItem):
            self.selected_item = event.item
            self._apply_folder(self.selected_item.raw_folder, self.selected_item.output_folder)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, FolderListItem):
            self.selected_item = event.item
            inp_raw = self.query_one("#inp_custom_raw", Input)
            inp_out = self.query_one("#inp_custom_out", Input)
            inp_raw.value = self.selected_item.raw_folder
            inp_out.value = self.selected_item.output_folder

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_close_folder":
            self.dismiss()
        elif event.button.id == "btn_switch_folder":
            if self.selected_item:
                self._apply_folder(self.selected_item.raw_folder, self.selected_item.output_folder)
            else:
                self.app_instance.notify("Please select a folder from the list.", severity="warning")
        elif event.button.id == "btn_apply_custom":
            raw_val = self.query_one("#inp_custom_raw", Input).value.strip()
            out_val = self.query_one("#inp_custom_out", Input).value.strip()
            if not raw_val:
                self.app_instance.notify("Please enter a raw folder path.", severity="error")
                return
            if not out_val:
                out_val = f"{raw_val}_th"
            self._apply_folder(raw_val, out_val)

    def _apply_folder(self, raw_folder: str, output_folder: str) -> None:
        self.app_instance.switch_folder(raw_folder, output_folder)
        self.dismiss()
