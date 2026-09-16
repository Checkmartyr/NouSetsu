"""Unit tests for data models."""
from nousetsu.models.bible import CharacterProfile, CharacterPronouns, ChapterSummary, GlossaryItem, NovelBible, StyleGuide
from nousetsu.models.metadata import (
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


def test_character_pronouns():
    # 1. Direct model creation
    cp = CharacterPronouns(source="she/her, I", target="เธอ, ฉัน")
    assert cp.source == "she/her, I"
    assert cp.target == "เธอ, ฉัน"

    # 2. Coercion from list
    cp_list = CharacterPronouns(source=["she", "her"], target=["เธอ", "ฉัน"])
    assert cp_list.source == "she, her"
    assert cp_list.target == "เธอ, ฉัน"

    # 3. Embedded in CharacterProfile
    char = CharacterProfile(
        name="Ifia",
        original_name="อิเฟีย",
        gender="female",
        pronouns=cp
    )
    assert char.pronouns.source == "she/her, I"
    assert char.pronouns.target == "เธอ, ฉัน"

    # 4. Coercion from string
    char_str = CharacterProfile(
        name="Amelia",
        original_name="アメリア",
        pronouns="she/her"
    )
    assert char_str.pronouns.source == "she/her"
    assert char_str.pronouns.target == ""

    # 5. Flat field migration (source_pronoun, target_pronoun)
    char_flat = CharacterProfile(
        name="Desalo",
        original_name="デサロ",
        source_pronoun="he/him",
        target_pronoun="เขา"
    )
    assert char_flat.pronouns.source == "he/him"
    assert char_flat.pronouns.target == "เขา"

    # 6. Backward compatibility (None pronouns)
    char_default = CharacterProfile(name="Kael", original_name="カエル")
    assert char_default.pronouns is None

    # 7. YAML roundtrip
    import yaml
    dumped = yaml.safe_dump(char.model_dump(), allow_unicode=True)
    loaded = CharacterProfile.model_validate(yaml.safe_load(dumped))
    assert loaded.pronouns.source == "she/her, I"
    assert loaded.pronouns.target == "เธอ, ฉัน"

