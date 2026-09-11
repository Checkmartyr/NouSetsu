import os
from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from nousetsu.models.bible import NovelBible
from nousetsu.models.config import ProjectConfig
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
        self.cfg: ProjectConfig = repo.load_config()
        self.bible: NovelBible = repo.load_bible()

    def on_mount(self) -> None:
        """Focus the first input field on mount for immediate keyboard interaction."""
        self.query_one("#set_title", Input).focus()

    def compose(self) -> ComposeResult:
        with Container(id="settings-dialog"):
            yield Label("⚙️ Project & Translation Settings", classes="pane-title")

            with VerticalScroll():
                with Container(classes="settings-section"):
                    yield Label("Project & Model Configuration", classes="section-title")
                    yield Label("Novel Title:", classes="field-label")
                    yield Input(value=self.cfg.title or self.bible.title, id="set_title")
                    yield Label("Default LLM Model Name (e.g. gemini-2.5-pro, gemini-2.5-flash):", classes="field-label")
                    yield Input(value=self.cfg.model_name or self.app_instance.model_name, id="set_model")
                    yield Label("Global Fallback Model (optional, e.g. gemini-2.5-flash, mock-novel-llm):", classes="field-label")
                    yield Input(value=self.cfg.fallback_model or "", id="set_fallback_model", placeholder="Leave blank if no fallback")
                    yield Label("Novel Genre (general, xianxia, wuxia, isekai, litrpg, romance):", classes="field-label")
                    yield Input(value=self.cfg.genre or self.bible.genre, id="set_genre")

                with Container(classes="settings-section"):
                    yield Label("🤖 Multi-Agent Model Routing (Leave blank to use default model)", classes="section-title")
                    yield Label("Entity Extractor Model:", classes="field-label")
                    yield Input(value=self.cfg.extractor_model or "", id="set_extractor_model", placeholder="e.g. gemini-2.5-flash")
                    yield Label("Translation Drafter Model:", classes="field-label")
                    yield Input(value=self.cfg.drafter_model or "", id="set_drafter_model", placeholder="e.g. gemini-2.5-pro")
                    yield Label("Critique & Quality Auditor Model:", classes="field-label")
                    yield Input(value=self.cfg.critic_model or "", id="set_critic_model", placeholder="e.g. gemini-2.5-pro")
                    yield Label("Prose Polisher Model:", classes="field-label")
                    yield Input(value=self.cfg.polisher_model or "", id="set_polisher_model", placeholder="e.g. gemini-2.5-pro")
                    yield Label("Chronicler Lore Memory Model:", classes="field-label")
                    yield Input(value=self.cfg.chronicler_model or "", id="set_chronicler_model", placeholder="e.g. gemini-2.5-flash")

                with Container(classes="settings-section"):
                    yield Label("Language Pair Settings", classes="section-title")
                    yield Label("Source Language (e.g. Japanese, Chinese, Korean, English):", classes="field-label")
                    yield Input(value=self.cfg.source_language or self.bible.source_language, id="set_source_lang")
                    yield Label("Target Language (e.g. English, Spanish, Thai, French):", classes="field-label")
                    yield Input(value=self.cfg.target_language or self.bible.target_language, id="set_target_lang")

                with Container(classes="settings-section"):
                    yield Label("Directory Paths", classes="section-title")
                    yield Label("Raw Chapters Input Folder:", classes="field-label")
                    yield Input(value=self.cfg.raw_dir or str(self.app_instance.input_dir), id="set_input_dir")
                    yield Label("Translated Chapters Output Folder:", classes="field-label")
                    yield Input(value=self.cfg.output_dir or str(self.app_instance.output_dir), id="set_output_dir")

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
                    yield Label("⚡ API Rate Limits & Provider Guard", classes="section-title")
                    yield Label("Max Tokens Per Minute (TPM, default 16000):", classes="field-label")
                    yield Input(value=str(self.cfg.max_tpm), id="set_max_tpm")
                    yield Label("Max Requests Per Minute (RPM, default 60):", classes="field-label")
                    yield Input(value=str(self.cfg.max_rpm), id="set_max_rpm")
                    yield Label("Use Gemini Interactions API (true / false):", classes="field-label")
                    yield Input(value="true" if self.cfg.use_interactions_api else "false", id="set_use_interactions")

                with Container(classes="settings-section"):
                    yield Label("🔄 Review Loop & Automation", classes="section-title")
                    yield Label("Max Review Loops (1–5, default 3):", classes="field-label")
                    yield Input(value=str(self.cfg.max_review_loops), id="set_max_loops")
                    yield Label("Quality Threshold (5.0–10.0, default 8.5):", classes="field-label")
                    yield Input(value=str(self.cfg.quality_threshold), id="set_quality_threshold")
                    yield Label("Auto-Update Novel Bible (true / false):", classes="field-label")
                    yield Input(value="true" if self.cfg.auto_update_bible else "false", id="set_auto_bible")

                with Container(classes="settings-section"):
                    yield Label("📏 Line-Based Semantic Chunking", classes="section-title")
                    yield Label("Enable Line Chunking (true / false):", classes="field-label")
                    yield Input(value="true" if self.cfg.enable_chunking else "false", id="set_enable_chunking")
                    yield Label("Chunk Trigger Line Threshold (default 100 non-empty lines):", classes="field-label")
                    yield Input(value=str(self.cfg.chunk_threshold_lines), id="set_chunk_threshold_lines")
                    yield Label("Target Chunk Lines (default 70 lines per chunk):", classes="field-label")
                    yield Input(value=str(self.cfg.target_chunk_lines), id="set_target_chunk_lines")
                    yield Label("Context Overlap Lines (default 3 preceding lines):", classes="field-label")
                    yield Input(value=str(self.cfg.chunk_overlap_lines), id="set_chunk_overlap_lines")

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
        title_val = self.query_one("#set_title", Input).value.strip()
        model_val = self.query_one("#set_model", Input).value.strip()
        fallback_val = self.query_one("#set_fallback_model", Input).value.strip()
        extractor_val = self.query_one("#set_extractor_model", Input).value.strip()
        drafter_val = self.query_one("#set_drafter_model", Input).value.strip()
        critic_val = self.query_one("#set_critic_model", Input).value.strip()
        polisher_val = self.query_one("#set_polisher_model", Input).value.strip()
        chronicler_val = self.query_one("#set_chronicler_model", Input).value.strip()
        genre_val = self.query_one("#set_genre", Input).value.strip()
        src_val = self.query_one("#set_source_lang", Input).value.strip()
        tgt_val = self.query_one("#set_target_lang", Input).value.strip()
        in_dir = self.query_one("#set_input_dir", Input).value.strip()
        out_dir = self.query_one("#set_output_dir", Input).value.strip()

        reading_level = self.query_one("#set_reading_level", Input).value.strip()
        tense_val = self.query_one("#set_tense", Input).value.strip()
        pov_val = self.query_one("#set_pov", Input).value.strip()
        honorifics_val = self.query_one("#set_honorifics", Input).value.strip()

        tpm_val = self.query_one("#set_max_tpm", Input).value.strip()
        rpm_val = self.query_one("#set_max_rpm", Input).value.strip()
        interactions_val = self.query_one("#set_use_interactions", Input).value.strip().lower() in ("true", "1", "yes")

        loops_val = self.query_one("#set_max_loops", Input).value.strip()
        thresh_val = self.query_one("#set_quality_threshold", Input).value.strip()
        auto_bible_val = self.query_one("#set_auto_bible", Input).value.strip().lower() in ("true", "1", "yes")

        chunking_val = self.query_one("#set_enable_chunking", Input).value.strip().lower() in ("true", "1", "yes")
        chunk_thresh_val = self.query_one("#set_chunk_threshold_lines", Input).value.strip()
        target_chunk_val = self.query_one("#set_target_chunk_lines", Input).value.strip()
        chunk_overlap_val = self.query_one("#set_chunk_overlap_lines", Input).value.strip()

        # Update Bible in repo
        if title_val:
            self.bible.title = title_val
        if src_val:
            self.bible.source_language = src_val
        if tgt_val:
            self.bible.target_language = tgt_val
        if genre_val:
            self.bible.genre = genre_val
        if reading_level:
            self.bible.style_guide.target_reading_level = reading_level
        if tense_val:
            self.bible.style_guide.tense = tense_val
        if pov_val:
            self.bible.style_guide.pov = pov_val
        if honorifics_val:
            self.bible.style_guide.honorific_mode = honorifics_val

        self.repo.save_bible(self.bible)

        # Update and persist complete ProjectConfig
        cfg = self.repo.load_config()
        if title_val:
            cfg.title = title_val
        if model_val:
            cfg.model_name = model_val
        cfg.fallback_model = fallback_val or None
        cfg.extractor_model = extractor_val or None
        cfg.drafter_model = drafter_val or None
        cfg.critic_model = critic_val or None
        cfg.polisher_model = polisher_val or None
        cfg.chronicler_model = chronicler_val or None
        if genre_val:
            cfg.genre = genre_val
        if src_val:
            cfg.source_language = src_val
        if tgt_val:
            cfg.target_language = tgt_val
        if in_dir:
            cfg.raw_dir = in_dir
        if out_dir:
            cfg.output_dir = out_dir

        if tpm_val.isdigit():
            cfg.max_tpm = int(tpm_val)
        if rpm_val.isdigit():
            cfg.max_rpm = int(rpm_val)
        cfg.use_interactions_api = interactions_val

        if loops_val.isdigit():
            cfg.max_review_loops = max(1, min(5, int(loops_val)))

        try:
            new_thresh = float(thresh_val)
            if 5.0 <= new_thresh <= 10.0:
                cfg.quality_threshold = new_thresh
        except ValueError:
            pass

        cfg.auto_update_bible = auto_bible_val
        cfg.enable_chunking = chunking_val

        if chunk_thresh_val.isdigit():
            cfg.chunk_threshold_lines = int(chunk_thresh_val)
        if target_chunk_val.isdigit():
            cfg.target_chunk_lines = int(target_chunk_val)
        if chunk_overlap_val.isdigit():
            cfg.chunk_overlap_lines = int(chunk_overlap_val)

        self.repo.save_config(cfg)

        # Apply environment flag for interactions API
        os.environ["NOVEL_USE_INTERACTIONS"] = "1" if cfg.use_interactions_api else "0"

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
            fallback_model=cfg.fallback_model,
            extractor_model=cfg.extractor_model,
            drafter_model=cfg.drafter_model,
            critic_model=cfg.critic_model,
            polisher_model=cfg.polisher_model,
            chronicler_model=cfg.chronicler_model,
            auto_update_bible=cfg.auto_update_bible,
            max_tpm=cfg.max_tpm,
            max_rpm=cfg.max_rpm,
            max_review_loops=cfg.max_review_loops,
            quality_threshold=cfg.quality_threshold,
            genre=cfg.genre,
            enable_chunking=cfg.enable_chunking,
            chunk_threshold_lines=cfg.chunk_threshold_lines,
            target_chunk_lines=cfg.target_chunk_lines,
            chunk_overlap_lines=cfg.chunk_overlap_lines
        )

        # Refresh scanned tasks in TUI
        self.app_instance.action_refresh_chapters()

        # Notify user and dismiss modal
        self.app_instance.notify("✓ Settings saved and applied successfully!", severity="information")
        self.dismiss()
