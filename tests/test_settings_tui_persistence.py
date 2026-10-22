"""Settings saves must persist edits or keep a visible, retryable draft."""
from unittest.mock import Mock

import pytest
from textual.widgets import Input, Static

from nousetsu.storage.repository import NovelRepository
from nousetsu.tui.app import NovelAgentApp
from nousetsu.tui.widgets.settings_modal import SettingsModal


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid", "write"])
async def test_tui_failed_save_keeps_draft_and_disk(tmp_path, monkeypatch, failure):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Before", "Japanese", "English")
    before = repo.config_file_path().read_bytes()
    app = NovelAgentApp(input_dir=str(tmp_path / "raw_chapters"),
        output_dir=str(tmp_path / "translated_chapters"), model_name="mock-model", project_dir=tmp_path)
    async with app.run_test() as pilot:
        app.action_open_settings()
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SettingsModal)
        modal.query_one("#set_title", Input).value = "Keep this draft"
        if failure == "invalid":
            modal.query_one("#set_quality_threshold", Input).value = "not a number"
        else:
            monkeypatch.setattr(modal.repo, "save_settings", Mock(side_effect=OSError("disk blocked")))
        notify = Mock()
        monkeypatch.setattr(app, "notify", notify)
        modal._save_settings()
        assert app.screen is modal
        assert modal.query_one("#set_title", Input).value == "Keep this draft"
        assert "Unable to save settings" in str(modal.query_one("#settings_status", Static).render())
        assert repo.config_file_path().read_bytes() == before
        notify.assert_not_called()
