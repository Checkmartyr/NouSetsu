"""Settings modal screen for adjusting model, languages, style guide, and project paths."""
from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from nousetsu.models.bible import NovelBible
from nousetsu.storage.repository import NovelRepository


class SettingsModal(ModalScreen):
    """Modal screen for configuring translation model, language pairs, style guide, and folder paths."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }
    #settings-dialog {
        width: 80%;
        height: 85%;
        border: thick $primary;
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
    #settings-dialog VerticalScroll {
        height: 1fr;
    }
    .settings-section {
        height: auto;
        margin: 1 0;
        padding: 0 1;
        border: solid $accent;
    }
    .section-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    .settings-btn-row {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, repo: NovelRepository, app_instance):
        super().__init__()
        self.repo = repo
        self.app_instance = app_instance
        self.bible: NovelBible = repo.load_bible()

    def on_mount(self) -> None:
        """Focus the first input field on mount for immediate keyboard interaction."""
        self.query_one("#set_model", Input).focus()

    def compose(self) -> ComposeResult:
        with Container(id="settings-dialog"):
            yield Label("⚙️ Project & Translation Settings", classes="pane-title")

            with VerticalScroll():
                with Container(classes="settings-section"):
                    yield Label("Model & Provider Configuration", classes="section-title")
                    yield Label("LLM Model Name (e.g. gemini-2.5-pro, gemini-2.5-flash):", classes="field-label")
                    yield Input(value=self.app_instance.model_name, id="set_model")

                with Container(classes="settings-section"):
                    yield Label("Language Pair Settings", classes="section-title")
                    yield Label("Source Language (e.g. Japanese, Chinese, Korean):", classes="field-label")
                    yield Input(value=self.bible.source_language, id="set_source_lang")
                    yield Label("Target Language (e.g. English, Spanish, French):", classes="field-label")
                    yield Input(value=self.bible.target_language, id="set_target_lang")

                with Container(classes="settings-section"):
                    yield Label("Style Guide & Tone Guidelines", classes="section-title")
                    yield Label("Target Reading Level (literary_fiction, light_novel, webnovel):", classes="field-label")
                    yield Input(value=self.bible.style_guide.target_reading_level, id="set_reading_level")
                    yield Label("Narrative Tense (past / present):", classes="field-label")
                    yield Input(value=self.bible.style_guide.tense, id="set_tense")
                    yield Label("Point of View (third_person / first_person):", classes="field-label")
                    yield Input(value=self.bible.style_guide.pov, id="set_pov")
                    yield Label("Honorifics Handling (retain / adapt / drop):", classes="field-label")
                    yield Input(value=self.bible.style_guide.honorific_mode, id="set_honorifics")

                with Container(classes="settings-section"):
                    yield Label("Directory Paths", classes="section-title")
                    yield Label("Raw Chapters Input Folder:", classes="field-label")
                    yield Input(value=str(self.app_instance.input_dir), id="set_input_dir")
                    yield Label("Translated Chapters Output Folder:", classes="field-label")
                    yield Input(value=str(self.app_instance.output_dir), id="set_output_dir")

                with Container(classes="settings-section"):
                    cfg = self.repo.load_config()
                    yield Label("⚡ API Rate Limits & Throttling Guard", classes="section-title")
                    yield Label("Max Tokens Per Minute (TPM, default 16000):", classes="field-label")
                    yield Input(value=str(getattr(cfg, "max_tpm", 16000)), id="set_max_tpm")
                    yield Label("Max Requests Per Minute (RPM, default 60):", classes="field-label")
                    yield Input(value=str(getattr(cfg, "max_rpm", 60)), id="set_max_rpm")

                with Container(classes="settings-section"):
                    yield Label("🔄 Review Loop & Quality Control", classes="section-title")
                    yield Label("Max Review Loops (1–5, default 3):", classes="field-label")
                    yield Input(value=str(getattr(cfg, "max_review_loops", 3)), id="set_max_loops")
                    yield Label("Quality Threshold (5.0–10.0, default 8.5):", classes="field-label")
                    yield Input(value=str(getattr(cfg, "quality_threshold", 8.5)), id="set_quality_threshold")

                with Container(classes="settings-section"):
                    yield Label("✨ Novel Genre & Specialized Skills", classes="section-title")
                    yield Label("Genre (general, xianxia, wuxia, isekai, litrpg, romance):", classes="field-label")
                    yield Input(value=getattr(self.bible, "genre", getattr(cfg, "genre", "general")), id="set_genre")

                yield Static("", id="settings_status")

            with Horizontal(classes="settings-btn-row"):
                yield Button("Save & Apply Settings", variant="primary", id="btn_save_settings")
                yield Button("Close", variant="default", id="btn_close_settings")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_close_settings":
            self.dismiss()
        elif event.button.id == "btn_save_settings":
            self._save_settings()

    def _save_settings(self) -> None:
        model_val = self.query_one("#set_model", Input).value.strip()
        src_val = self.query_one("#set_source_lang", Input).value.strip()
        tgt_val = self.query_one("#set_target_lang", Input).value.strip()
        reading_level = self.query_one("#set_reading_level", Input).value.strip()
        tense_val = self.query_one("#set_tense", Input).value.strip()
        pov_val = self.query_one("#set_pov", Input).value.strip()
        honorifics_val = self.query_one("#set_honorifics", Input).value.strip()
        in_dir = self.query_one("#set_input_dir", Input).value.strip()
        out_dir = self.query_one("#set_output_dir", Input).value.strip()
        genre_val = self.query_one("#set_genre", Input).value.strip()

        # Update Bible in repo
        if src_val:
            self.bible.source_language = src_val
        if tgt_val:
            self.bible.target_language = tgt_val
        if reading_level:
            self.bible.style_guide.target_reading_level = reading_level
        if tense_val:
            self.bible.style_guide.tense = tense_val
        if pov_val:
            self.bible.style_guide.pov = pov_val
        if honorifics_val:
            self.bible.style_guide.honorific_mode = honorifics_val
        if genre_val:
            self.bible.genre = genre_val

        self.repo.save_bible(self.bible)

        # Update and persist complete ProjectConfig
        cfg = self.repo.load_config()
        if model_val:
            cfg.model_name = model_val
        if src_val:
            cfg.source_language = src_val
        if tgt_val:
            cfg.target_language = tgt_val
        if in_dir:
            cfg.raw_dir = in_dir
        if out_dir:
            cfg.output_dir = out_dir
        if genre_val:
            cfg.genre = genre_val

        tpm_val = self.query_one("#set_max_tpm", Input).value.strip()
        rpm_val = self.query_one("#set_max_rpm", Input).value.strip()
        if tpm_val.isdigit():
            cfg.max_tpm = int(tpm_val)
        if rpm_val.isdigit():
            cfg.max_rpm = int(rpm_val)

        loops_val = self.query_one("#set_max_loops", Input).value.strip()
        if loops_val.isdigit():
            cfg.max_review_loops = max(1, min(5, int(loops_val)))

        thresh_val = self.query_one("#set_quality_threshold", Input).value.strip()
        try:
            new_thresh = float(thresh_val)
            if 5.0 <= new_thresh <= 10.0:
                cfg.quality_threshold = new_thresh
        except ValueError:
            pass

        self.repo.save_config(cfg)

        # Update active app instance state
        self.app_instance.model_name = cfg.model_name
        self.app_instance.input_dir = cfg.get_raw_path(self.app_instance.project_dir)
        self.app_instance.output_dir = cfg.get_output_path(self.app_instance.project_dir)
        self.app_instance.title = f"Novel Translation Agent - {cfg.title}"

        # Rebuild runner with full new config and model
        from nousetsu.batch.runner import BatchRunner
        self.app_instance.runner = BatchRunner(
            self.repo,
            model_name=cfg.model_name,
            max_tpm=cfg.max_tpm,
            max_rpm=cfg.max_rpm,
            max_review_loops=cfg.max_review_loops,
            quality_threshold=cfg.quality_threshold,
            genre=cfg.genre
        )

        # Refresh scanned tasks in TUI
        self.app_instance.action_refresh_chapters()

        # Notify user and dismiss modal
        self.app_instance.notify("✓ Settings saved and applied successfully!", severity="information")
        self.dismiss()
