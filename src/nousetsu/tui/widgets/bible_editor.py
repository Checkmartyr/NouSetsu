"""Modal screen for inspecting and editing Novel Bible character cards and glossary."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Markdown, Static, TabbedContent, TabPane
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible
from nousetsu.storage.repository import NovelRepository


class NovelBibleModal(ModalScreen):
    """Modal viewer and editor for the project Novel Bible."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    NovelBibleModal {
        align: center middle;
    }
    #dialog {
        width: 85%;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    .modal-header-row {
        height: auto;
        margin-bottom: 1;
        align: right middle;
    }
    .modal-header-row .pane-title {
        width: 1fr;
    }
    #dialog TabbedContent {
        height: 1fr;
    }
    .form-row {
        height: auto;
        margin: 1 0;
    }
    .input-field {
        margin-bottom: 1;
    }
    """

    def __init__(self, repo: NovelRepository):
        super().__init__()
        self.repo = repo
        self.bible: NovelBible = repo.load_bible()

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            with Horizontal(classes="modal-header-row"):
                yield Label(f"Novel Bible - {self.bible.title} ({self.bible.source_language} -> {self.bible.target_language})", classes="pane-title")
                yield Button("✖ Close (Esc)", variant="error", id="btn_close_top")

            with TabbedContent():
                with TabPane("Characters"):
                    with VerticalScroll():
                        char_md = "\n\n".join([
                            f"### {c.name} (`{c.original_name}`)\n- **Role:** {c.role} | **Gender:** {c.gender}\n- **Voice / Tone:** {c.voice}\n- **Aliases:** {', '.join(c.aliases) or 'None'}"
                            for c in self.bible.characters
                        ]) or "*No character profiles registered yet.*"
                        yield Markdown(char_md, id="chars_view")

                with TabPane("Glossary"):
                    with VerticalScroll():
                        gloss_md = "| Source | Target | Category | Notes |\n|---|---|---|---|\n" + "\n".join([
                            f"| `{g.source}` | **{g.target}** | {g.category} | {g.notes} |"
                            for g in self.bible.glossary
                        ]) if self.bible.glossary else "*No glossary items registered yet.*"
                        yield Markdown(gloss_md, id="gloss_view")

                with TabPane("Summaries"):
                    with VerticalScroll():
                        all_by_folder = self.repo.get_all_summaries_by_folder() if hasattr(self.repo, "get_all_summaries_by_folder") else {}
                        if not all_by_folder and self.bible.summaries:
                            all_by_folder = {"All": self.bible.summaries}

                        if all_by_folder:
                            blocks = []
                            for folder_name, folder_sums in all_by_folder.items():
                                blocks.append(f"## 📁 Volume / Folder: `{folder_name}` ({len(folder_sums)} chapters)")
                                for s in folder_sums:
                                    events_str = ", ".join(s.key_events) if s.key_events else "None"
                                    state_str = ", ".join(s.character_state_changes) if s.character_state_changes else "None"
                                    blocks.append(
                                        f"### Chapter {s.chapter_num}: {s.title or 'Untitled'}\n"
                                        f"- **Synopsis:** {s.synopsis}\n"
                                        f"- **Key Events:** {events_str}\n"
                                        f"- **State Changes:** {state_str}"
                                    )
                            sum_md = "\n\n".join(blocks)
                        else:
                            sum_md = "*No chapter summaries recorded yet.*"
                        yield Markdown(sum_md, id="summaries_view")

                with TabPane("Languages"):
                    with VerticalScroll():
                        yield Label(f"Current Source Language: [bold cyan]{self.bible.source_language}[/]")
                        yield Input(value=self.bible.source_language, id="inp_source_lang", classes="input-field")
                        yield Label(f"Current Target Language: [bold cyan]{self.bible.target_language}[/]")
                        yield Input(value=self.bible.target_language, id="inp_target_lang", classes="input-field")
                        with Horizontal(classes="form-row"):
                            yield Button("🔍 Auto-Detect from Raw Chapters", variant="default", id="btn_autodetect_lang")
                            yield Button("Save Language Settings", variant="primary", id="btn_save_langs")
                        yield Static("", id="lang_status")

                with TabPane("Add New Term"):
                    with VerticalScroll():
                        yield Label("Source Original Term:")
                        yield Input(placeholder="e.g. 魔導具", id="new_term_source", classes="input-field")
                        yield Label("Target Translated Term:")
                        yield Input(placeholder="e.g. magic tool", id="new_term_target", classes="input-field")
                        yield Label("Category:")
                        yield Input(placeholder="e.g. item, location, skill", id="new_term_cat", classes="input-field")
                        yield Button("Add to Novel Bible", variant="primary", id="btn_add_term")
                        yield Static("", id="add_status")

            with Horizontal(classes="form-row"):
                yield Button("Close", variant="default", id="btn_close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ["btn_close", "btn_close_top"]:
            self.dismiss()
        elif event.button.id == "btn_autodetect_lang":
            from nousetsu.utils.language import detect_language_from_dir
            config = self.repo.load_config()
            raw_dir_path = self.repo.root_dir / config.raw_dir
            detected = detect_language_from_dir(raw_dir_path)
            status = self.query_one("#lang_status", Static)
            if detected:
                self.query_one("#inp_source_lang", Input).value = detected
                status.update(f"[bold green]🔍 Detected source language from raw chapters: [bold]{detected}[/bold]![/]")
            else:
                status.update("[bold yellow]⚠ Could not detect language: No raw chapter text found.[/]")
        elif event.button.id == "btn_save_langs":
            src = self.query_one("#inp_source_lang", Input).value.strip()
            tgt = self.query_one("#inp_target_lang", Input).value.strip()
            status = self.query_one("#lang_status", Static)
            if src and tgt:
                self.bible = self.repo.set_languages(source_lang=src, target_lang=tgt)
                title_lbl = self.query_one(".pane-title", Label)
                title_lbl.update(f"Novel Bible - {self.bible.title} ({self.bible.source_language} -> {self.bible.target_language})")
                status.update(f"[bold green]Updated languages to {src} -> {tgt}![/]")
            else:
                status.update("[bold red]Please provide both source and target language names.[/]")
        elif event.button.id == "btn_add_term":
            src = self.query_one("#new_term_source", Input).value.strip()
            tgt = self.query_one("#new_term_target", Input).value.strip()
            cat = self.query_one("#new_term_cat", Input).value.strip() or "term"
            status = self.query_one("#add_status", Static)

            if src and tgt:
                new_item = GlossaryItem(source=src, target=tgt, category=cat)
                self.repo.update_bible_memory(new_characters=[], new_terms=[new_item], summary=None)
                self.bible = self.repo.load_bible()
                status.update(f"[bold green]Added '{src}' -> '{tgt}' to Novel Bible![/]")
                self.query_one("#new_term_source", Input).value = ""
                self.query_one("#new_term_target", Input).value = ""
            else:
                status.update("[bold red]Please enter both source and target terms.[/]")
