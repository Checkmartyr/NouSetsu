"""Performance and optimization verification tests for Textual TUI widgets and batch scanner."""
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from nousetsu.batch.scanner import ChapterScanner
from nousetsu.models.metadata import (
    ChapterMetadata,
    CheckpointData,
    PipelineStage,
    StageArtifacts,
    StageStatus,
)
from nousetsu.storage.repository import NovelRepository
from nousetsu.tui.app import NovelAgentApp
from nousetsu.tui.widgets.checkpoint_inspector import CheckpointInspectorWidget
from nousetsu.tui.widgets.progress_panel import ProgressPanel
from nousetsu.tui.widgets.reader import DualReaderWidget
from nousetsu.tui.widgets.token_analysis import TokenAnalysisWidget


def test_scanner_sha256_caching(tmp_path: Path):
    """Verify ChapterScanner caches file SHA-256 hashes by (path, size, mtime)."""
    repo = NovelRepository(tmp_path)
    scanner = ChapterScanner(repo)
    test_file = tmp_path / "chapter_01.txt"
    test_file.write_text("Hello World Raw Novel Chapter", encoding="utf-8")

    scanner.clear_sha256_cache()
    assert len(scanner._sha256_cache) == 0

    hash1 = scanner.get_file_sha256(test_file)
    assert hash1 != ""
    assert len(scanner._sha256_cache) == 1

    # Second call should use cache
    hash2 = scanner.get_file_sha256(test_file)
    assert hash1 == hash2

    # Modify file
    time.sleep(0.05)
    test_file.write_text("Modified Content In Chapter", encoding="utf-8")
    hash3 = scanner.get_file_sha256(test_file)
    assert hash3 != hash1

    scanner.clear_sha256_cache()
    assert len(scanner._sha256_cache) == 0


@pytest.mark.asyncio
async def test_dual_reader_deduplication():
    """Verify DualReaderWidget skips re-parsing Markdown if content has not changed."""
    reader = DualReaderWidget()
    reader._source_widget = MagicMock()
    reader._target_widget = MagicMock()

    # Initial update
    reader.update_content("Source text 1", "Target text 1")
    assert reader._last_source == "Source text 1"
    assert reader._last_target == "Target text 1"
    assert reader._source_widget.update.call_count == 1
    assert reader._target_widget.update.call_count == 1

    # Duplicate update should be skipped
    reader.update_content("Source text 1", "Target text 1")
    assert reader._source_widget.update.call_count == 1
    assert reader._target_widget.update.call_count == 1

    # Only target changed
    reader.update_content("Source text 1", "Target text 2")
    assert reader._source_widget.update.call_count == 1
    assert reader._target_widget.update.call_count == 2
    assert reader._last_target == "Target text 2"


def test_checkpoint_inspector_deduplication():
    """Verify CheckpointInspectorWidget skips re-rendering when metadata cache_key matches."""
    inspector = CheckpointInspectorWidget()
    inspector._lbl_status = MagicMock()
    inspector._lbl_stage = MagicMock()
    inspector._lbl_hash = MagicMock()
    inspector._lbl_fidelity = MagicMock()
    inspector._lbl_style = MagicMock()
    inspector._lbl_glossary = MagicMock()
    inspector._lbl_tokens = MagicMock()
    inspector._lbl_warnings = MagicMock()
    inspector._lbl_terms = MagicMock()

    meta = ChapterMetadata(
        chapter_id="chapter_001",
        chapter_num=1,
        source_file="0001.txt",
        source_sha256="sha12345",
        output_file="0001.md",
        checkpoint=CheckpointData(
            status=StageStatus.COMPLETED,
            last_completed_stage=PipelineStage.CHRONICLING,
            stage_artifacts=StageArtifacts(
                extracted_terms=[],
                extracted_characters=[],
                draft_text="draft",
                polished_text="polished"
            )
        )
    )

    inspector.update_metadata(meta)
    first_key = inspector._last_meta_key
    assert first_key is not None
    assert inspector._lbl_status.update.call_count == 1

    # Call with identical meta should return early without re-rendering
    inspector.update_metadata(meta)
    assert inspector._lbl_status.update.call_count == 1


def test_progress_panel_micro_throttling():
    """Verify ProgressPanel throttles updates closer than 30ms with <0.5% progress change."""
    panel = ProgressPanel()
    mock_bar = MagicMock()
    panel._pbar = mock_bar
    panel._status_lbl = MagicMock()
    panel._ch_label = MagicMock()
    panel._badge = MagicMock()

    # First update
    panel.update_progress("ch1.txt", PipelineStage.DRAFTING, "Drafting...", 10.0)
    assert mock_bar.update.call_count == 1
    mock_bar.update.assert_called_with(progress=10.0)

    # Very small progress delta (0.1%) within tiny time window -> throttled
    panel._last_time = time.time()  # simulate immediate subsequent call
    panel.update_progress("ch1.txt", PipelineStage.DRAFTING, "Drafting...", 10.1)
    assert mock_bar.update.call_count == 1  # not called again!

    # Significant progress delta (>0.5%) -> bypasses throttle
    panel.update_progress("ch1.txt", PipelineStage.DRAFTING, "Drafting...", 11.0)
    assert mock_bar.update.call_count == 2
    mock_bar.update.assert_called_with(progress=11.0)


def test_token_analysis_dirty_flag(tmp_path: Path):
    """Verify TokenAnalysisWidget tracks dirty state and supports lazy loading."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Test Novel", "Japanese", "English")

    widget = TokenAnalysisWidget(repo)
    assert widget._dirty is True

    # When not mounted and force=False, refresh_metrics sets _dirty = False after computing
    widget.refresh_metrics(force=True)
    assert widget._dirty is False
    assert widget.current_summary is not None


@pytest.mark.asyncio
async def test_app_selection_preservation_and_file_cache(tmp_path: Path):
    """Verify NovelAgentApp preserves list selection during refresh and caches file reads."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Preserve Selection Test", "Japanese", "English")

    raw_dir = tmp_path / "raw_chapters"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "translated_chapters"
    out_dir.mkdir(parents=True, exist_ok=True)

    ch1 = raw_dir / "0001.txt"
    ch1.write_text("Chapter 1 Japanese source", encoding="utf-8")
    ch2 = raw_dir / "0002.txt"
    ch2.write_text("Chapter 2 Japanese source", encoding="utf-8")

    app = NovelAgentApp(
        input_dir=str(raw_dir),
        output_dir=str(out_dir),
        model_name="mock-model",
        project_dir=tmp_path
    )

    async with app.run_test() as pilot:
        assert len(app.current_tasks) == 2
        # Initial selection is chapter 1
        assert app.selected_task.chapter_num == 1

        # Select chapter 2
        app._select_task(app.current_tasks[1])
        assert app.selected_task.chapter_num == 2

        # Refresh chapters: should preserve chapter 2 selection!
        app.action_refresh_chapters()
        assert app.selected_task.chapter_num == 2

        # Test file caching
        content1 = app._read_file_cached(ch1)
        assert content1 == "Chapter 1 Japanese source"
        assert ch1 in app._file_cache

        # Cached call returns same content
        content2 = app._read_file_cached(ch1)
        assert content1 == content2
