import pytest
from nousetsu.models.bible import (
    CharacterNameDetail,
    CharacterNames,
    CharacterProfile,
    NovelBible,
)
from nousetsu.prompts.character_formatter import format_character_roster
from nousetsu.utils.character_filter import filter_characters_for_scene


def test_character_name_detail_full_name():
    # Katakana / CJK name (auto separator '・')
    detail_cjk = CharacterNameDetail(name="メアリィ", s_name="レガリヤ")
    assert detail_cjk.full_name() == "メアリィ・レガリヤ"

    # 3-part Katakana name
    detail_3part = CharacterNameDetail(name="レイフォース", m_name="ルクア", s_name="ダルフォード")
    assert detail_3part.full_name() == "レイフォース・ルクア・ダルフォード"

    # Latin / English name (space separator)
    detail_en = CharacterNameDetail(name="Mary", s_name="Legalia")
    assert detail_en.full_name() == "Mary Legalia"

    # Surname first order (e.g. Chinese traditional: Xiao Yan)
    detail_cn = CharacterNameDetail(name="炎", s_name="萧")
    assert detail_cn.full_name(separator="", order="surname_first") == "萧炎"


def test_character_profile_legacy_backfill():
    # Legacy data with only name and original_name
    char = CharacterProfile(
        name="Mary Legalia",
        original_name="メアリィ・レガリヤ",
        gender="female",
        role="protagonist",
    )
    assert char.names is not None
    assert char.names.source.name == "メアリィ"
    assert char.names.source.s_name == "レガリヤ"
    assert char.names.target.name == "Mary"
    assert char.names.target.s_name == "Legalia"


def test_character_profile_three_part_legacy_backfill():
    char = CharacterProfile(
        name="Rayforce Lukia Dalford",
        original_name="レイフォース・ルクア・ダルフォード",
    )
    assert char.names is not None
    assert char.names.source.name == "レイフォース"
    assert char.names.source.m_name == "ルクア"
    assert char.names.source.s_name == "ダルフォード"
    assert char.names.target.name == "Rayforce"
    assert char.names.target.m_name == "Lukia"
    assert char.names.target.s_name == "Dalford"


def test_character_profile_names_auto_populate_full_strings():
    # Providing names without top-level name and original_name
    char = CharacterProfile(
        names=CharacterNames(
            source=CharacterNameDetail(name="メアリィ", s_name="レガリヤ"),
            target=CharacterNameDetail(name="แมรี่", s_name="เลกาเลีย"),
        )
    )
    assert char.name == "แมรี่ เลกาเลีย"
    assert char.original_name == "メアリィ・レガリヤ"


def test_novel_bible_find_character_by_structured_names():
    bible = NovelBible(
        title="Test Novel",
        characters=[
            CharacterProfile(
                name="Mary Legalia",
                original_name="メアリィ・レガリヤ",
                names=CharacterNames(
                    source=CharacterNameDetail(name="メアリィ", s_name="レガリヤ"),
                    target=CharacterNameDetail(name="Mary", s_name="Legalia"),
                ),
            ),
            CharacterProfile(
                name="Rayforce Lukia Dalford",
                original_name="レイフォース・ルクア・ダルフォード",
                names=CharacterNames(
                    source=CharacterNameDetail(name="レイフォース", m_name="ルクア", s_name="ダルフォード"),
                    target=CharacterNameDetail(name="Rayforce", m_name="Lukia", s_name="Dalford"),
                ),
            ),
        ],
    )

    # 1. Full matches
    assert bible.find_character("Mary Legalia") is not None
    assert bible.find_character("メアリィ・レガリヤ") is not None

    # 2. Given name matches
    assert bible.find_character("Mary") is not None
    assert bible.find_character("メアリィ") is not None

    # 3. Surname matches
    assert bible.find_character("Legalia") is not None
    assert bible.find_character("レガリヤ") is not None

    # 4. Middle name matches
    assert bible.find_character("Lukia") is not None
    assert bible.find_character("ルクア") is not None


def test_character_filter_scene_structured_names():
    char1 = CharacterProfile(
        name="Mary Legalia",
        original_name="メアリィ・レガリヤ",
        role="supporting",
        names=CharacterNames(
            source=CharacterNameDetail(name="メアリィ", s_name="レガリヤ"),
            target=CharacterNameDetail(name="Mary", s_name="Legalia"),
        ),
    )
    char2 = CharacterProfile(
        name="John Doe",
        original_name="ジョン・ドウ",
        role="supporting",
    )

    # Search corpus contains only the surname "レガリヤ"
    scene_text = "レガリヤ家の執事が門を開いた。"
    filtered = filter_characters_for_scene([char1, char2], scene_text, max_characters=10)
    assert len(filtered) == 1
    assert filtered[0].name == "Mary Legalia"


def test_character_roster_formatter_name_breakdown():
    char = CharacterProfile(
        name="Mary Legalia",
        original_name="メアリィ・レガリヤ",
        gender="female",
        role="protagonist",
        names=CharacterNames(
            source=CharacterNameDetail(name="メアリィ", s_name="レガリヤ"),
            target=CharacterNameDetail(name="Mary", s_name="Legalia"),
        ),
    )
    formatted = format_character_roster([char])
    assert "Name Breakdown:" in formatted
    assert "Given: メアリィ -> Mary" in formatted
    assert "Surname: レガリヤ -> Legalia" in formatted
