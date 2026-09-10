"""TUI widgets package."""
from src.tui.widgets.bible_editor import NovelBibleModal
from src.tui.widgets.checkpoint_inspector import CheckpointInspectorWidget
from src.tui.widgets.new_project_modal import NewProjectModal
from src.tui.widgets.progress_panel import ProgressPanel
from src.tui.widgets.project_selector_modal import ProjectSelectorModal
from src.tui.widgets.reader import DualReaderWidget
from src.tui.widgets.settings_modal import SettingsModal

__all__ = [
    "DualReaderWidget",
    "CheckpointInspectorWidget",
    "NovelBibleModal",
    "SettingsModal",
    "ProgressPanel",
    "NewProjectModal",
    "ProjectSelectorModal",
]

