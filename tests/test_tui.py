"""Unit tests for Textual TUI using pilot."""
from pathlib import Path
import pytest
from nousetsu.models.metadata import PipelineStage
from nousetsu.storage.repository import NovelRepository
from nousetsu.tui.app import NovelAgentApp
from nousetsu.tui.widgets.checkpoint_inspector import CheckpointInspectorWidget
from nousetsu.tui.widgets.new_project_modal import NewProjectModal
from nousetsu.tui.widgets.progress_panel import ProgressPanel
from nousetsu.tui.widgets.project_selector_modal import ProjectSelectorModal
from nousetsu.tui.widgets.reader import DualReaderWidget
from nousetsu.tui.widgets.settings_modal import SettingsModal


@pytest.mark.asyncio
async def test_tui_app_mount_and_widgets():
    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        # Verify core widgets mounted
        assert app.query_one("#reader", DualReaderWidget) is not None
        assert app.query_one("#inspector", CheckpointInspectorWidget) is not None
        assert app.query_one("#progress_panel", ProgressPanel) is not None

        # Verify chapter list loaded tasks
        assert len(app.current_tasks) >= 2

        # Verify selected task is chapter 1
        assert app.selected_task is not None
        assert app.selected_task.chapter_num == 1


@pytest.mark.asyncio
async def test_tui_settings_modal(tmp_path: Path):
    from textual.widgets import Button, Input
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Init Title", "Japanese", "English")

    app = NovelAgentApp(
        input_dir=str(tmp_path / "raw_chapters"),
        output_dir=str(tmp_path / "translated_chapters"),
        model_name="mock-model",
        project_dir=tmp_path
    )
    async with app.run_test() as pilot:
        # Open settings via action
        app.action_open_settings()
        await pilot.pause()

        settings_screen = app.screen
        assert isinstance(settings_screen, SettingsModal)

        # Verify only one close button exists (no duplicate top button)
        assert len(settings_screen.query("#btn_close_top")) == 0
        assert len(settings_screen.query("#btn_close_settings")) == 1

        # Verify first input (#set_title) is focused on mount
        inp_title = settings_screen.query_one("#set_title", Input)
        assert app.focused == inp_title

        # Click on title input directly
        await pilot.click(inp_title)
        await pilot.pause()
        assert app.focused == inp_title

        # Edit title and model name
        inp_title.value = "Ascendance of a Bookworm"
        inp_model = settings_screen.query_one("#set_model", Input)
        inp_model.value = "gemini-custom-test"
        inp_chunk_thresh = settings_screen.query_one("#set_chunk_threshold_lines", Input)
        inp_chunk_thresh.value = "85"

        # Click save button via pilot
        btn_save = settings_screen.query_one("#btn_save_settings", Button)
        await pilot.click(btn_save)
        await pilot.pause()

        # Modal should dismiss on save
        assert not isinstance(app.screen, SettingsModal)

        # Verify app and runner state updated
        assert app.model_name == "gemini-custom-test"
        assert app.runner.model_name == "gemini-custom-test"
        assert app.runner.workflow.chunker.threshold_lines == 85

        # Verify config was persisted to disk with all fields
        persisted_cfg = app.repo.load_config()
        assert persisted_cfg.title == "Ascendance of a Bookworm"
        assert persisted_cfg.model_name == "gemini-custom-test"
        assert persisted_cfg.chunk_threshold_lines == 85

        # Verify bible.yaml was also synchronized with title
        persisted_bible = app.repo.load_bible()
        assert persisted_bible.title == "Ascendance of a Bookworm"

        # Re-open settings and test bottom close button
        app.action_open_settings()
        await pilot.pause()
        assert isinstance(app.screen, SettingsModal)
        assert app.screen.query_one("#set_title", Input).value == "Ascendance of a Bookworm"
        assert app.screen.query_one("#set_model", Input).value == "gemini-custom-test"
        assert app.screen.query_one("#set_chunk_threshold_lines", Input).value == "85"

        btn_close = app.screen.query_one("#btn_close_settings", Button)
        await pilot.click(btn_close)
        await pilot.pause()
        assert not isinstance(app.screen, SettingsModal)


@pytest.mark.asyncio
async def test_tui_checkpoint_inspector_duration_formatting():
    from nousetsu.models.metadata import ChapterMetadata, TranslationStats
    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        inspector = app.query_one("#inspector", CheckpointInspectorWidget)
        
        # Test duration 846.4s formatted to 14m 6s
        meta = ChapterMetadata(
            chapter_id="ch_format_test",
            chapter_num=32,
            source_file="032.txt",
            source_sha256="abc123456789",
            output_file="032_out.txt",
            stats=TranslationStats(
                total_tokens=43128,
                prompt_tokens=28450,
                completion_tokens=14678,
                duration_seconds=846.4
            )
        )
        inspector.update_metadata(meta)
        lbl_tokens = inspector.query_one("#lbl_tokens")
        rendered_text = str(lbl_tokens.render())
        assert "in 14m 6s" in rendered_text
        assert "43,128" in rendered_text


@pytest.mark.asyncio
async def test_tui_progress_panel_updates():
    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        panel = app.query_one("#progress_panel", ProgressPanel)
        panel.update_progress("chapter_001.txt", PipelineStage.DRAFTING, "Drafting translation...", 35.0)
        await pilot.pause()

        assert "2/5 DRAFTING" in str(panel.query_one("#stage_badge").render())
        assert "Drafting translation" in str(panel.query_one("#engine_status_msg").render())
        assert "chapter_001" in str(panel.query_one("#progress_chapter_name").render())

        panel.set_finished("chapter_001.txt")
        await pilot.pause()
        assert "COMPLETED" in str(panel.query_one("#stage_badge").render())
        assert "chapter_001" in str(panel.query_one("#progress_chapter_name").render())


@pytest.mark.asyncio
async def test_tui_project_modals_and_switching(tmp_path: Path):
    # Setup custom temporary project
    custom_proj = tmp_path / "custom_novel"
    repo = NovelRepository(custom_proj)
    repo.initialize_project(
        title="Slime Reincarnation",
        source_lang="Japanese",
        target_lang="Spanish",
        raw_dir="src_raw",
        output_dir="out_trans"
    )
    raw_dir = custom_proj / "src_raw"
    (raw_dir / "001.txt").write_text("第1話 スライムになった件", encoding="utf-8")

    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        # Open project selector modal
        app.action_open_project_selector()
        await pilot.pause()
        assert isinstance(app.screen, ProjectSelectorModal)
        app.screen.dismiss()
        await pilot.pause()

        # Open new project modal
        app.action_open_new_project()
        await pilot.pause()
        assert isinstance(app.screen, NewProjectModal)
        app.screen.dismiss()
        await pilot.pause()

        # Switch project dynamically
        app.switch_project(custom_proj)
        await pilot.pause()

        assert app.project_dir == custom_proj.resolve()
        assert app.input_dir == raw_dir.resolve()
        assert len(app.current_tasks) == 1
        assert app.current_tasks[0].source_file.name == "001.txt"


@pytest.mark.asyncio
async def test_tui_create_new_project_modal(tmp_path: Path):
    target_dir = tmp_path / "subfolder" / "brand_new_novel"
    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        app.action_open_new_project()
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, NewProjectModal)

        from textual.widgets import Button, Input
        modal.query_one("#inp_title", Input).value = "Ascendance of a Bookworm"
        modal.query_one("#inp_path", Input).value = str(target_dir)
        modal.query_one("#inp_src_lang", Input).value = "Japanese"
        modal.query_one("#inp_tgt_lang", Input).value = "Thai"
        modal.query_one("#inp_raw_dir", Input).value = "my_raw"
        modal.query_one("#inp_out_dir", Input).value = "my_translated"

        modal.on_button_pressed(Button.Pressed(modal.query_one("#btn_create", Button)))
        await pilot.pause()

        assert target_dir.exists()
        assert (target_dir / ".novel" / "config.yaml").exists()
        assert app.project_dir == target_dir.resolve()
        assert app.input_dir == (target_dir / "my_raw").resolve()
        assert app.output_dir == (target_dir / "my_translated").resolve()


@pytest.mark.asyncio
async def test_tui_open_external_path_in_project_selector(tmp_path: Path):
    external_proj = tmp_path / "somewhere_else" / "external_novel"
    external_proj.mkdir(parents=True, exist_ok=True)
    raw_folder = external_proj / "raw_chapters"
    raw_folder.mkdir(parents=True, exist_ok=True)
    (raw_folder / "001.txt").write_text("第1話 異世界転生", encoding="utf-8")

    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        app.action_open_project_selector()
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, ProjectSelectorModal)

        from textual.widgets import Button, Input
        modal.query_one("#inp_custom_path", Input).value = str(external_proj)
        modal.on_button_pressed(Button.Pressed(modal.query_one("#btn_open_path", Button)))
        await pilot.pause()

        # Verify app switched to external path
        assert app.project_dir == external_proj.resolve()
        assert (external_proj / ".novel").exists()
        assert len(app.current_tasks) == 1
@pytest.mark.asyncio
async def test_tui_novel_bible_modal_escape():
    from nousetsu.tui.widgets.bible_editor import NovelBibleModal
    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        # Open Novel Bible modal
        app.action_edit_bible()
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, NovelBibleModal)

        # Press escape to dismiss
        await pilot.press("escape")
        await pilot.pause()

        # Should be back to main screen
        assert app.screen != modal
        assert not isinstance(app.screen, NovelBibleModal)


@pytest.mark.asyncio
async def test_tui_failed_badge_and_inspector():
    from nousetsu.batch.scanner import ChapterTask
    from nousetsu.models.metadata import ChapterMetadata, CheckpointData, PipelineStage, StageStatus
    from nousetsu.tui.app import ChapterListItem

    # Create failed task
    failed_meta = ChapterMetadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="ch1.txt",
        source_sha256="abc",
        output_file="ch1.md",
        checkpoint=CheckpointData(
            status=StageStatus.FAILED,
            failed_stage=PipelineStage.POLISHING,
            last_error="500 INTERNAL server error encountered",
            last_error_type="InternalServerError",
            retry_count=2
        )
    )
    task = ChapterTask(
        chapter_num=1,
        source_file=Path("raw_chapters/ch1.txt"),
        output_file=Path("translated_chapters/ch1.md"),
        source_sha256="abc",
        existing_meta=failed_meta,
        is_completed=False,
        is_failed=True,
        last_error="500 INTERNAL server error encountered"
    )

    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        item = ChapterListItem(task)
        rendered_badge = str(list(item.compose())[0].render())
        assert "FAILED" in rendered_badge

        inspector = app.query_one("#inspector", CheckpointInspectorWidget)
        inspector.update_metadata(failed_meta)
        await pilot.pause()

        assert "FAILED" in str(inspector.query_one("#lbl_status").render())
        assert "POLISHING" in str(inspector.query_one("#lbl_stage").render())
        assert "500 INTERNAL" in str(inspector.query_one("#lbl_warnings").render())


def test_bare_cli_launches_tui():
    """Verify executing nousetsu without subcommands automatically triggers cmd_tui."""
    from unittest.mock import patch
    import sys
    import nousetsu.cli.app as app_module

    with patch.object(app_module, "cmd_tui") as mock_tui:
        with patch.object(sys, "argv", ["nousetsu"]):
            app_module.main()
            assert mock_tui.called, "cmd_tui should be called automatically on bare nousetsu command"


@pytest.mark.asyncio
async def test_tui_token_analysis_tab(tmp_path: Path):
    """Verify Token Analysis tab renders properly and can be toggled via hotkey and button."""
    from textual.widgets import DataTable, TabbedContent
    from nousetsu.tui.widgets.token_analysis import TokenAnalysisWidget

    repo = NovelRepository(tmp_path)
    repo.initialize_project("Token Test", "Japanese", "English")

    app = NovelAgentApp(
        input_dir=str(tmp_path / "raw_chapters"),
        output_dir=str(tmp_path / "translated_chapters"),
        model_name="mock-model",
        project_dir=tmp_path
    )
    async with app.run_test() as pilot:
        tabs = app.query_one("#main-tabs", TabbedContent)
        token_widget = app.query_one("#token_analysis", TokenAnalysisWidget)
        assert tabs is not None
        assert token_widget is not None

        # Initially on reader tab
        assert tabs.active == "tab-reader"

        # Toggle tab via keybinding 'm'
        await pilot.press("m")
        await pilot.pause()
        assert tabs.active == "tab-tokens"

        # Verify DataTables exist and have columns
        table_stages = token_widget.query_one("#table-stages", DataTable)
        table_models = token_widget.query_one("#table-models", DataTable)
        table_chapters = token_widget.query_one("#table-chapters", DataTable)
        assert len(table_stages.columns) == 9
        assert len(table_models.columns) == 9
        assert len(table_chapters.columns) == 8

        # Toggle back to reader via toolbar button click
        await pilot.click("#btn_tokens")
        await pilot.pause()
        assert tabs.active == "tab-reader"

        # Toggle again via button
        await pilot.click("#btn_tokens")
        await pilot.pause()
        assert tabs.active == "tab-tokens"



