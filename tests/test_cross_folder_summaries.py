"""Unit and integration tests for Cross-Folder Narrative Summaries."""
from pathlib import Path
import pytest
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.llm import MockNovelLLM
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import ChapterSummary, NovelBible
from nousetsu.models.config import ProjectConfig
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository


def _make_summary(num: int, title: str, folder: str, synopsis: str = "") -> ChapterSummary:
    return ChapterSummary(
        chapter_num=num,
        title=title,
        synopsis=synopsis or f"Summary of {title} in {folder}",
        key_events=[f"Event {num}"],
        character_state_changes=[],
        folder=folder
    )


def test_single_folder_rolling_context():
    """Verify normal rolling context within a single folder."""
    bible = NovelBible()
    bible.summaries = [
        _make_summary(1, "Chapter 1", "Vol_01"),
        _make_summary(2, "Chapter 2", "Vol_01"),
        _make_summary(3, "Chapter 3", "Vol_01"),
    ]

    context = bible.get_rolling_context(folder="Vol_01", current_chapter_num=4, limit=3)
    assert len(context) == 3
    assert [s.chapter_num for s in context] == [1, 2, 3]
    assert all(s.folder == "Vol_01" for s in context)


def test_cross_folder_backfill_at_volume_start():
    """Verify that Chapter 1 of a new folder receives tail summaries from preceding folder."""
    bible = NovelBible()
    bible.summaries = [
        _make_summary(i, f"Ch {i}", "Villainess_04") for i in range(1, 11)
    ]
    # Villainess_05 has no chapters yet
    context = bible.get_rolling_context(
        folder="Villainess_05",
        current_chapter_num=1,
        limit=3,
        cross_folder=True,
        folder_order=["Villainess_04", "Villainess_05"]
    )
    assert len(context) == 3
    assert [s.chapter_num for s in context] == [8, 9, 10]
    assert all(s.folder == "Villainess_04" for s in context)


def test_cross_folder_partial_backfill():
    """Verify Chapter 2 of new volume receives 1 current summary and 2 backfilled summaries."""
    bible = NovelBible()
    bible.summaries = [
        _make_summary(i, f"Ch {i}", "Villainess_04") for i in range(1, 11)
    ] + [
        _make_summary(1, "Ch 1", "Villainess_05")
    ]

    context = bible.get_rolling_context(
        folder="Villainess_05",
        current_chapter_num=2,
        limit=3,
        cross_folder=True,
        folder_order=["Villainess_04", "Villainess_05"]
    )
    assert len(context) == 3
    assert [s.chapter_num for s in context] == [9, 10, 1]
    assert context[0].folder == "Villainess_04"
    assert context[1].folder == "Villainess_04"
    assert context[2].folder == "Villainess_05"


def test_cross_folder_no_backfill_when_sufficient():
    """Verify no backfill occurs once the current volume has sufficient chapters."""
    bible = NovelBible()
    bible.summaries = [
        _make_summary(i, f"Ch {i}", "Villainess_04") for i in range(1, 11)
    ] + [
        _make_summary(1, "Ch 1", "Villainess_05"),
        _make_summary(2, "Ch 2", "Villainess_05"),
        _make_summary(3, "Ch 3", "Villainess_05"),
    ]

    context = bible.get_rolling_context(
        folder="Villainess_05",
        current_chapter_num=4,
        limit=3,
        cross_folder=True,
        folder_order=["Villainess_04", "Villainess_05"]
    )
    assert len(context) == 3
    assert [s.chapter_num for s in context] == [1, 2, 3]
    assert all(s.folder == "Villainess_05" for s in context)


def test_cross_folder_disabled():
    """Verify that setting cross_folder=False strictly prevents backfill."""
    bible = NovelBible()
    bible.summaries = [
        _make_summary(i, f"Ch {i}", "Villainess_04") for i in range(1, 11)
    ]
    context = bible.get_rolling_context(
        folder="Villainess_05",
        current_chapter_num=1,
        limit=3,
        cross_folder=False,
        folder_order=["Villainess_04", "Villainess_05"]
    )
    assert len(context) == 0


def test_drafter_prompt_folder_badge():
    """Verify drafter context formatting renders [Folder] badge for summaries."""
    drafter = ContextAwareDrafterAgent(model_name="mock-novel-llm")
    summaries = [
        _make_summary(10, "Climax", "Villainess_04", synopsis="The dragon fell."),
        _make_summary(1, "New Beginning", "Villainess_05", synopsis="Elena woke up early.")
    ]
    block = drafter.format_summaries(summaries)
    assert "[Villainess_04] Chapter 10" in block
    assert "The dragon fell." in block
    assert "[Villainess_05] Chapter 1" in block
    assert "Elena woke up early." in block


def test_repository_get_folder_order_and_grouping(tmp_path: Path):
    """Verify repository folder order discovery and summary grouping."""
    repo = NovelRepository(tmp_path)
    (tmp_path / "Vol_01").mkdir()
    (tmp_path / "Vol_01" / "001.txt").write_text("Ch 1", encoding="utf-8")
    (tmp_path / "Vol_02").mkdir()
    (tmp_path / "Vol_02" / "001.txt").write_text("Ch 1", encoding="utf-8")

    order = repo.get_folder_order()
    assert "Vol_01" in order
    assert "Vol_02" in order
    assert order.index("Vol_01") < order.index("Vol_02")

    bible = repo.load_bible()
    bible.summaries = [
        _make_summary(1, "C1", "Vol_01"),
        _make_summary(2, "C2", "Vol_01"),
        _make_summary(1, "C1", "Vol_02"),
    ]
    repo.save_bible(bible)

    grouped = repo.get_all_summaries_by_folder()
    assert len(grouped["Vol_01"]) == 2
    assert len(grouped["Vol_02"]) == 1
    assert grouped["Vol_01"][0].chapter_num == 1
    assert grouped["Vol_01"][1].chapter_num == 2


def test_workflow_cross_folder_context_integration(tmp_path: Path):
    """Verify that the workflow supplies cross-folder rolling context to the drafter."""
    mock_llm = MockNovelLLM()
    workflow = NovelTranslationWorkflow(model_name="mock-novel-llm")
    workflow.extractor.llm = mock_llm
    workflow.drafter.llm = mock_llm
    workflow.critic.llm = mock_llm
    workflow.polisher.llm = mock_llm
    workflow.chronicler.llm = mock_llm

    bible = NovelBible(
        source_language="Japanese",
        target_language="English",
        genre="general",
        cross_folder_summaries=True
    )
    bible.summaries = [
        _make_summary(122, "Final Battle", "Villainess_04", synopsis="The dark god was defeated.")
    ]

    captured_summaries = []
    original_draft = workflow.drafter.draft

    def mock_draft(*args, **kwargs):
        captured_summaries.extend(kwargs.get("rolling_summaries", []))
        return original_draft(*args, **kwargs)

    workflow.drafter.draft = mock_draft

    source_file = tmp_path / "Villainess_05" / "001.txt"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("新しい学期が始まった。", encoding="utf-8")

    state = TranslationState(
        chapter_id="ch01",
        chapter_num=1,
        source_file=str(source_file),
        source_text="新しい学期が始まった。",
        novel_bible=bible,
        genre="general"
    )

    workflow.run(state)
    assert len(captured_summaries) == 1
    assert captured_summaries[0].chapter_num == 122
    assert captured_summaries[0].folder == "Villainess_04"
