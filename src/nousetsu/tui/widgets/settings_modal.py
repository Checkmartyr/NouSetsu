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
    .settings-section {
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
        status = self.query_one("#settings_status", Static)

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

        self.repo.save_bible(self.bible)

        # Update app instance state
        if model_val:
            self.app_instance.model_name = model_val
            self.app_instance.runner.model_name = model_val
            self.app_instance.runner.workflow.model_name = model_val

        if in_dir:
            self.app_instance.input_dir = Path(in_dir)
        if out_dir:
            self.app_instance.output_dir = Path(out_dir)

        # Update rate limits in config and active runner
        tpm_val = self.query_one("#set_max_tpm", Input).value.strip()
        rpm_val = self.query_one("#set_max_rpm", Input).value.strip()
        cfg = self.repo.load_config()
        if tpm_val.isdigit():
            new_tpm = int(tpm_val)
            cfg.max_tpm = new_tpm
            if hasattr(self.app_instance.runner, "rate_limiter"):
                self.app_instance.runner.rate_limiter.max_tpm = new_tpm
        if rpm_val.isdigit():
            new_rpm = int(rpm_val)
            cfg.max_rpm = new_rpm
            if hasattr(self.app_instance.runner, "rate_limiter"):
                self.app_instance.runner.rate_limiter.max_rpm = new_rpm

        # Update review loop configuration
        loops_val = self.query_one("#set_max_loops", Input).value.strip()
        thresh_val = self.query_one("#set_quality_threshold", Input).value.strip()
        if loops_val.isdigit():
            new_loops = max(1, min(5, int(loops_val)))
            cfg.max_review_loops = new_loops
            if hasattr(self.app_instance.runner, "max_review_loops"):
                self.app_instance.runner.max_review_loops = new_loops
            if hasattr(self.app_instance.runner, "workflow") and hasattr(self.app_instance.runner.workflow, "max_review_loops"):
                self.app_instance.runner.workflow.max_review_loops = new_loops
        try:
            new_thresh = float(thresh_val)
            if 5.0 <= new_thresh <= 10.0:
                cfg.quality_threshold = new_thresh
                if hasattr(self.app_instance.runner, "quality_threshold"):
                    self.app_instance.runner.quality_threshold = new_thresh
                if hasattr(self.app_instance.runner, "workflow") and hasattr(self.app_instance.runner.workflow, "quality_threshold"):
                    self.app_instance.runner.workflow.quality_threshold = new_thresh
        except ValueError:
            pass

        # Update genre
        genre_val = self.query_one("#set_genre", Input).value.strip()
        if genre_val:
            self.bible.genre = genre_val
            cfg.genre = genre_val
            if hasattr(self.app_instance.runner, "genre"):
                self.app_instance.runner.genre = genre_val
            self.repo.save_bible(self.bible)

        self.repo.save_config(cfg)

        # Refresh tasks in TUI
        self.app_instance.action_refresh_chapters()

        status.update("[bold green]✓ Settings saved and applied successfully![/]")
