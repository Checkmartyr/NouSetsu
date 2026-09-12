"""Unit and integration tests for 3-Tier Hierarchical Summary System (Whole Story > Arc > Situation)."""
from argparse import Namespace
from pathlib import Path
import pytest

from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.llm import MockNovelLLM
from nousetsu.cli.app import cmd_narrative
from nousetsu.models.bible import ArcSummary, ChapterSummary, CharacterProfile, GlossaryItem, NovelBible
from nousetsu.storage.repository import NovelRepository


def test_arc_summary_model_and_bible_hierarchy():
    """Verify ArcSummary model fields, serialization, and NovelBible hierarchy helpers."""
    arc1 = ArcSummary(
        arc_id="arc_0001",
        arc_num=1,
        title="Royal Academy Arc",
        synopsis="Rozemyne enters the Royal Academy and passes all exams.",
        core_conflict="Overcome social ostracization and library bans",
        status="completed",
        start_chapter=1,
        end_chapter=5,
        folder="Vol_04",
        key_milestones=["Enrolled in academy", "Unlocked library access", "Defeated rival"]
    )
    assert arc1.status == "completed"
    assert arc1.end_chapter == 5
    assert len(arc1.key_milestones) == 3

    arc2 = ArcSummary(
        arc_id="arc_0002",
        arc_num=2,
        title="Inter-Duchy Tournament",
        synopsis="Ditter competition between Ehrenfest and Dunkelfelger.",
        core_conflict="Win ditter match against superior tactics",
        status="active",
        start_chapter=6,
        folder="Vol_04",
        key_milestones=["Selected as commander"]
    )

    bible = NovelBible(
        title="Ascendance of a Bookworm",
        whole_story_summary="A reincarnated bookworm aims to create books in a fantasy world.",
        active_arc=arc2,
        archived_arcs=[arc1]
    )

    # Test get_all_arcs
    all_arcs = bible.get_all_arcs()
    assert len(all_arcs) == 2
    assert all_arcs[0].arc_num == 1
    assert all_arcs[1].arc_num == 2

    # Test get_hierarchical_context
    h_context = bible.get_hierarchical_context()
    assert h_context["whole_story"] == bible.whole_story_summary
    assert h_context["active_arc"] == arc2
    assert h_context["archived_arcs"] == [arc1]


def test_chronicler_hierarchical_json_parsing():
    """Test ChroniclerAgent parsing structured 3-tier JSON response."""
    mock_llm_response = '''{
        "chapter_summary": {
            "chapter_num": 1,
            "title": "A New Beginning",
            "synopsis": "Urano wakes up in the body of Myne.",
            "key_events": ["Woke up with fever", "Discovered absence of books"],
            "character_state_changes": ["Myne realizes she is sick"]
        },
        "arc_update": {
            "title": "Discovery Arc",
            "synopsis": "Myne discovers the state of books in the lower city.",
            "core_conflict": "Find paper or books to read",
            "milestones": ["Explored city", "Discovered parchment costs too much"],
            "is_completed": false
        },
        "story_update": "Urano is reincarnated as frail girl Myne in an impoverished household."
    }'''

    mock_llm = MockNovelLLM(responses=[mock_llm_response])
    agent = ChroniclerAgent(model_name="mock-chronicler")
    agent.llm = mock_llm

    summary = agent.chronicle(
        chapter_num=1,
        chapter_title="A New Beginning",
        translated_text="Translated chapter 1 text..."
    )

    assert summary.chapter_num == 1
    assert summary.title == "A New Beginning"
    assert "Urano wakes up" in summary.synopsis
    assert summary.arc_update is not None
    assert summary.arc_update["title"] == "Discovery Arc"
    assert summary.arc_update["core_conflict"] == "Find paper or books to read"
    assert len(summary.arc_update["milestones"]) == 2
    assert summary.story_update == "Urano is reincarnated as frail girl Myne in an impoverished household."


def test_repository_arc_lifecycle_and_archiving(tmp_path: Path):
    """Verify repository handles active arc creation, milestone progression, arc completion, and disk persistence."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project(title="Test Novel", raw_dir="raw", output_dir="out")

    # Chapter 1: Initialize active arc
    ch1_summary = ChapterSummary(
        chapter_num=1,
        title="Prologue",
        synopsis="Story begins.",
        key_events=["Awakened"],
        character_state_changes=[],
        arc_update={
            "title": "Origins Arc",
            "synopsis": "The protagonist adjusts to the new world.",
            "core_conflict": "Survive the initial illness",
            "milestones": ["Survived fever"],
            "is_completed": False
        },
        story_update="Initial world setup."
    )

    bible = repo.update_bible_memory(
        new_characters=[CharacterProfile(name="Myne", original_name="マイン")],
        new_terms=[GlossaryItem(source="本", target="Book")],
        summary=ch1_summary,
        folder="Vol_01"
    )

    assert bible.active_arc is not None
    assert bible.active_arc.title == "Origins Arc"
    assert bible.active_arc.arc_num == 1
    assert bible.active_arc.status == "active"
    assert bible.active_arc.start_chapter == 1
    assert bible.active_arc.key_milestones == ["Survived fever"]
    assert bible.whole_story_summary == "Initial world setup."

    # Chapter 2: Complete the arc
    ch2_summary = ChapterSummary(
        chapter_num=2,
        title="Recovery and Resolution",
        synopsis="Defeated the sickness and made paper.",
        key_events=["Made mokkan"],
        character_state_changes=[],
        arc_update={
            "title": "Origins Arc",
            "synopsis": "The protagonist adjusted and survived the fever.",
            "core_conflict": "Survive the initial illness",
            "milestones": ["Crafted first slate"],
            "is_completed": True
        },
        story_update="Myne survived her initial weakness and established her quest for books."
    )

    bible = repo.update_bible_memory(
        new_characters=[],
        new_terms=[],
        summary=ch2_summary,
        folder="Vol_01"
    )

    # Previous arc should be archived
    assert len(bible.archived_arcs) == 1
    archived = bible.archived_arcs[0]
    assert archived.arc_num == 1
    assert archived.status == "completed"
    assert archived.end_chapter == 2
    assert "Crafted first slate" in archived.key_milestones

    # New active arc should be prepared
    assert bible.active_arc is not None
    assert bible.active_arc.arc_num == 2
    assert bible.active_arc.status == "active"
    assert bible.active_arc.start_chapter == 3
    assert bible.whole_story_summary == "Myne survived her initial weakness and established her quest for books."

    # Verify disk files
    arcs_dir = tmp_path / ".novel" / "summaries" / "arcs"
    assert (arcs_dir / "arc_0001.json").exists()
    assert (arcs_dir / "arc_0002.json").exists()

    # Verify reloading in fresh repo instance
    fresh_repo = NovelRepository(tmp_path)
    loaded_bible = fresh_repo.load_bible()
    assert len(loaded_bible.archived_arcs) == 1
    assert loaded_bible.archived_arcs[0].title == "Origins Arc"
    assert loaded_bible.active_arc is not None
    assert loaded_bible.active_arc.arc_num == 2
    assert loaded_bible.whole_story_summary == "Myne survived her initial weakness and established her quest for books."


def test_drafter_3tier_hierarchical_formatting():
    """Verify DrafterAgent renders 3-tier hierarchical narrative context when Bible has arc data."""
    drafter = ContextAwareDrafterAgent(model_name="mock-drafter")

    summaries = [
        ChapterSummary(
            chapter_num=10,
            title="Before the Gate",
            synopsis="The squad approaches the castle gate.",
            folder="Vol_02"
        ),
        ChapterSummary(
            chapter_num=11,
            title="Breach",
            synopsis="The gate falls and the vanguard pushes through.",
            folder="Vol_02"
        )
    ]

    arc = ArcSummary(
        arc_id="arc_0002",
        arc_num=2,
        title="Siege of Karas",
        synopsis="The coalition forces lay siege to the fortress city.",
        core_conflict="Breach the fortress walls before winter arrives",
        status="active",
        start_chapter=8,
        folder="Vol_02",
        key_milestones=["Catapults positioned", "Moat drained"]
    )

    bible = NovelBible(
        title="Kingdom Chronicle",
        whole_story_summary="The continental war enters its decisive second phase.",
        active_arc=arc,
        summaries=summaries
    )

    formatted = drafter.format_summaries(summaries, bible=bible)
    assert "## HIERARCHICAL NARRATIVE CONTEXT:" in formatted
    assert "### 1. Global Story Progression (Macro):" in formatted
    assert "The continental war enters its decisive second phase." in formatted
    assert "### 2. Active Story Arc (Meso - Arc 2: 'Siege of Karas'):" in formatted
    assert "Central Conflict: Breach the fortress walls before winter arrives" in formatted
    assert "Milestones: Catapults positioned, Moat drained" in formatted
    assert "### 3. Immediate Preceding Situation (Micro):" in formatted
    assert "[Vol_02] Chapter 10 (Before the Gate)" in formatted
    assert "[Vol_02] Chapter 11 (Breach)" in formatted

    # Test backward compatibility without bible
    legacy_formatted = drafter.format_summaries(summaries, bible=None)
    assert "[Vol_02] Chapter 10 (Before the Gate)" in legacy_formatted
    assert "### 1. Global Story Progression" not in legacy_formatted


def test_cli_narrative_command(tmp_path: Path, capsys):
    """Verify nousetsu narrative CLI command renders the Rich tree without exceptions."""
    repo = NovelRepository(tmp_path)
    repo.initialize_project(title="Test Story", raw_dir="raw", output_dir="out")

    arc = ArcSummary(
        arc_id="arc_0001",
        arc_num=1,
        title="Introductory Arc",
        synopsis="Hero wakes up.",
        core_conflict="Find safety",
        status="active",
        start_chapter=1,
        key_milestones=["Found village"]
    )

    summary = ChapterSummary(
        chapter_num=1,
        title="First Step",
        synopsis="Hero reached the town.",
        folder="Vol_01"
    )

    repo.update_bible_memory(
        new_characters=[],
        new_terms=[],
        summary=summary,
        folder="Vol_01"
    )
    bible = repo.load_bible()
    bible.active_arc = arc
    bible.whole_story_summary = "An epic tale across unknown lands."
    repo.save_bible(bible)

    # Run cmd_narrative
    args = Namespace(project_dir=str(tmp_path), folder=None)
    cmd_narrative(args)

    captured = capsys.readouterr()
    assert "Test Story" in captured.out
    assert "Global Story Progression" in captured.out
    assert "Introductory Arc" in captured.out
    assert "First Step" in captured.out
