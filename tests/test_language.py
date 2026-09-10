"""Unit tests for language detection engine and auto-detection integrations."""
from pathlib import Path
from rich.console import Console
import pytest

from nousetsu.utils.language import (
    detect_language,
    detect_language_from_file,
    detect_language_from_dir,
    is_cjk_language,
)
from nousetsu.storage.repository import NovelRepository
from nousetsu.batch.runner import BatchRunner
from nousetsu.models.metadata import StageStatus


def test_detect_language_japanese():
    text_mixed = "私は魔法使いです。エルフの森へ行くことになった。"
    assert detect_language(text_mixed) == "Japanese"

    text_katakana = "ドラゴンクエストの冒険が始まる。"
    assert detect_language(text_katakana) == "Japanese"


def test_detect_language_chinese():
    text_simplified = "在这个遥远的世界里，魔王已经苏醒了，年轻的勇者踏上了征途。"
    assert detect_language(text_simplified) == "Chinese"

    text_traditional = "在這個遙遠的世界裡，魔王已經復甦了，年輕的勇者踏上了征途。"
    assert detect_language(text_traditional) == "Chinese"


def test_detect_language_korean():
    text = "어느 날 갑자기 이세계로 소환되었다. 상태창이 눈앞에 나타났다."
    assert detect_language(text) == "Korean"


def test_detect_language_other_scripts():
    thai_text = "ในโลกแฟนตาซีแห่งนี้ ตัวเอกได้ตื่นขึ้นมาในป่าลึกลับและพบกับนางฟ้า"
    assert detect_language(thai_text) == "Thai"

    russian_text = "В этот день маг пробудился от долгого сна и открыл древнюю книгу заклинаний."
    assert detect_language(russian_text) == "Russian"


def test_detect_language_latin():
    english_text = "The knight took his sword and prepared to fight the dragon inside the dark dungeon."
    assert detect_language(english_text) == "English"

    spanish_text = "El caballero tomó su espada y se preparó para luchar contra el dragón en la mazmorra."
    assert detect_language(spanish_text) == "Spanish"

    french_text = "Le chevalier prit son épée et se prépara à combattre le dragon dans le donjon sombre."
    assert detect_language(french_text) == "French"

    german_text = "Der Ritter nahm sein Schwert und bereitete sich darauf vor, gegen den Drachen im Verlies zu kämpfen."
    assert detect_language(german_text) == "German"


def test_detect_language_empty_and_fallback():
    assert detect_language("") is None
    assert detect_language("   \n\t  ") is None
    assert detect_language("1234567890 !?...") is None
    assert detect_language("12345", default="Japanese") == "Japanese"


def test_is_cjk_language():
    assert is_cjk_language("Japanese") is True
    assert is_cjk_language("chinese") is True
    assert is_cjk_language("KOREAN") is True
    assert is_cjk_language("English") is False
    assert is_cjk_language("Russian") is False
    assert is_cjk_language(None) is False


def test_detect_from_file_and_dir(tmp_path: Path):
    raw_dir = tmp_path / "raws"
    raw_dir.mkdir()

    # Empty dir returns None
    assert detect_language_from_dir(raw_dir) is None

    # Non-existent file returns None
    assert detect_language_from_file(raw_dir / "nonexistent.txt") is None

    # File with Korean text
    ch1 = raw_dir / "001.txt"
    ch1.write_text("어느 날 갑자기 눈을 떠보니 던전 한복판이었다.", encoding="utf-8")

    assert detect_language_from_file(ch1) == "Korean"
    assert detect_language_from_dir(raw_dir) == "Korean"


def test_repository_initialize_with_auto_detect(tmp_path: Path):
    proj_dir = tmp_path / "korean_novel"
    raw_dir = proj_dir / "raw_chapters"
    raw_dir.mkdir(parents=True)

    # Put a Korean chapter
    (raw_dir / "001.txt").write_text("주인공은 칼을 들고 마왕군과 맞서 싸웠다.", encoding="utf-8")

    repo = NovelRepository(proj_dir)
    # Initialize with source_lang="Auto"
    repo.initialize_project(
        title="Dungeon Monarch",
        source_lang="Auto",
        target_lang="English",
        raw_dir="raw_chapters",
        output_dir="translated_chapters"
    )

    bible = repo.load_bible()
    assert bible.source_language == "Korean"
    assert bible.target_language == "English"


def test_repository_initialize_with_auto_fallback_when_no_raws(tmp_path: Path):
    proj_dir = tmp_path / "empty_novel"
    repo = NovelRepository(proj_dir)
    # When no raws exist, "auto" should fall back to "Japanese"
    repo.initialize_project(
        title="Empty Novel",
        source_lang="auto",
        target_lang="English",
    )

    bible = repo.load_bible()
    assert bible.source_language == "Japanese"


def test_batch_runner_auto_detects_when_bible_is_auto(tmp_path: Path):
    proj_dir = tmp_path / "chinese_novel"
    raw_dir = proj_dir / "raw_chapters"
    out_dir = proj_dir / "translated_chapters"
    raw_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    # Chinese raw chapter
    (raw_dir / "ch01.txt").write_text("天地玄黄，宇宙洪荒。少年逆天改命，修得无上金丹。", encoding="utf-8")

    repo = NovelRepository(proj_dir)
    repo.initialize_project(
        title="Cultivation Path",
        source_lang="auto",
        target_lang="English",
        raw_dir="raw_chapters",
        output_dir="translated_chapters",
    )
    # Manually reset to "auto" to verify runner's auto-detect on batch run
    repo.set_languages("auto", "English")
    assert repo.load_bible().source_language == "auto"

    console = Console(record=True)
    runner = BatchRunner(repo, model_name="mock-model", console=console)
    results = runner.run_batch(input_dir=raw_dir, output_dir=out_dir)

    assert len(results) == 1
    assert results[0].checkpoint.status == StageStatus.COMPLETED

    # Check that the runner updated the bible source language to Chinese
    updated_bible = repo.load_bible()
    assert updated_bible.source_language == "Chinese"
