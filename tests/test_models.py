"""Unit tests for data models."""
from src.models.bible import CharacterProfile, ChapterSummary, GlossaryItem, NovelBible, StyleGuide
from src.models.metadata import (
    ChapterMetadata,
    CheckpointData,
    PipelineStage,
    QualityAudit,
    StageArtifacts,
    StageStatus,
)


def test_novel_bible_models():
    char = CharacterProfile(
        name="Seraphina",
        original_name="セラフィーナ",
        aliases=["Sera"],
        gender="female",
        role="heroine",
        voice="formal, refined"
    )
    term = GlossaryItem(
        source="魔導具",
        target="magic tool",
        category="item"
    )
    summary = ChapterSummary(
        chapter_num=1,
        title="Prologue",
        synopsis="Seraphina meets the traveler.",
        key_events=["Encounter at ruins"]
    )

    bible = NovelBible(
        title="Fantasy Chronicle",
        source_language="Japanese",
        target_language="English",
        characters=[char],
        glossary=[term],
        style_guide=StyleGuide(honorific_mode="retain"),
        summaries=[summary]
    )

    assert bible.find_character("Sera") == char
    assert bible.find_character("セラフィーナ") == char
    assert bible.find_term("魔導具") == term
    assert bible.find_term("unknown") is None


def test_checkpoint_resumption_logic():
    checkpoint = CheckpointData(
        status=StageStatus.IN_PROGRESS,
        last_completed_stage=PipelineStage.DRAFTING,
        stage_artifacts=StageArtifacts(draft_text="Sample draft text")
    )
    assert checkpoint.is_resumable() is True
    assert checkpoint.is_completed() is False

    completed_checkpoint = CheckpointData(status=StageStatus.COMPLETED)
    assert completed_checkpoint.is_completed() is True
    assert completed_checkpoint.is_resumable() is False


def test_chapter_metadata_serialization():
    meta = ChapterMetadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="raw/001.txt",
        source_sha256="abc123hash",
        output_file="out/001.md",
        quality_audit=QualityAudit(fidelity_score=9.5, style_score=9.0)
    )
    json_data = meta.model_dump_json()
    reloaded = ChapterMetadata.model_validate_json(json_data)
    assert reloaded.chapter_id == "chapter_0001"
    assert reloaded.quality_audit.fidelity_score == 9.5
