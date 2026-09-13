"""Tests for chapter title and header preservation in PolishingAgent (Feinschliff)."""
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.models.bible import NovelBible
from nousetsu.skills.builtin.polisher import POLISHER_SKILLS
from nousetsu.skills.registry import SkillRegistry


def test_polisher_skill_registered():
    """Verify chapter_header_preservation skill is defined with priority 115 and registered."""
    skill_names = [s.name for s in POLISHER_SKILLS]
    assert "chapter_header_preservation" in skill_names

    skill = next(s for s in POLISHER_SKILLS if s.name == "chapter_header_preservation")
    assert skill.priority == 115
    assert skill.agent == "polisher"
    assert "chapter heading or title" in skill.content

    active_skills = SkillRegistry.get_instance().get_active_skills(agent="polisher", source_lang="Japanese")
    assert any(s.name == "chapter_header_preservation" for s in active_skills)


def test_extract_draft_chapter_header_various_formats():
    """Verify regex extraction of chapter headers across languages and number formats."""
    # Thai with leading page number
    draft_thai_num = "70\nบทที่ 11 - อวดดอกไม้\n\nหลังจากเค้นถามข้อมูล..."
    assert PolishingAgent._extract_draft_chapter_header(draft_thai_num) == "70\nบทที่ 11 - อวดดอกไม้"

    # Thai title alone
    draft_thai = "บทที่ 11 - อวดดอกไม้\n\nหลังจากเค้นถามข้อมูล..."
    assert PolishingAgent._extract_draft_chapter_header(draft_thai) == "บทที่ 11 - อวดดอกไม้"

    # English chapter
    draft_en = "Chapter 11: Boasting a Flower\n\nCheryl and Daryl..."
    assert PolishingAgent._extract_draft_chapter_header(draft_en) == "Chapter 11: Boasting a Flower"

    # Markdown heading
    draft_md = "# Chapter 11 - Boasting a Flower\n\nProse text..."
    assert PolishingAgent._extract_draft_chapter_header(draft_md) == "# Chapter 11 - Boasting a Flower"

    # Chinese chapter
    draft_zh = "第11章 决战紫禁之巅\n\n月圆之夜..."
    assert PolishingAgent._extract_draft_chapter_header(draft_zh) == "第11章 决战紫禁之巅"

    # Korean chapter
    draft_ko = "제11장 대결의 시작\n\n검을 뽑아들었다..."
    assert PolishingAgent._extract_draft_chapter_header(draft_ko) == "제11장 대결의 시작"

    # Episode format
    draft_ep = "Episode 42: The Revelation\n\nEverything changed..."
    assert PolishingAgent._extract_draft_chapter_header(draft_ep) == "Episode 42: The Revelation"

    # Plain text without header
    draft_no_head = "หลังจากเค้นถามข้อมูลจากปากทุกคน\nเรื่องราวก็ดำเนินต่อไป..."
    assert PolishingAgent._extract_draft_chapter_header(draft_no_head) is None

    # Number alone without subsequent chapter header
    draft_num_alone = "70\nเนื้อหาบทความธรรมดาที่ไม่มีหัวข้อใดๆ"
    assert PolishingAgent._extract_draft_chapter_header(draft_num_alone) is None

    # Empty text
    assert PolishingAgent._extract_draft_chapter_header("") is None


def test_has_chapter_header_detection():
    """Verify detection of existing chapter headers in polished output."""
    assert PolishingAgent._has_chapter_header("**บทที่ 11 - อวดดอกไม้**\n\nหลังจาก...") is True
    assert PolishingAgent._has_chapter_header("บทที่ 11: อวดบุปผา\n\nหลังจาก...") is True
    assert PolishingAgent._has_chapter_header("Chapter 11 - Flaunting Blossoms\n\nProse...") is True
    assert PolishingAgent._has_chapter_header("# Chapter 11\n\nProse...") is True
    assert PolishingAgent._has_chapter_header("第11章 决战\n\n正文...") is True
    assert PolishingAgent._has_chapter_header("หลังจากเค้นถามข้อมูลจากปาก...") is False
    assert PolishingAgent._has_chapter_header("") is False


def test_ensure_chapter_title_preserved_restores_missing_title():
    """Verify that omitted chapter title is prepended to polished prose."""
    draft = "70\nบทที่ 11 - อวดดอกไม้\n\nหลังจากเค้นถามข้อมูลจากปากเหล่าผู้ร่วมรับประทานอาหาร..."
    polished_without_title = "หลังจากเค้นถามข้อมูลจากปากของเหล่าผู้ร่วมโต๊ะอาหารเสร็จสิ้น สองพี่น้องเชอริลและดาริลก็ไม่รอช้า..."

    restored = PolishingAgent._ensure_chapter_title_preserved(draft_text=draft, polished_text=polished_without_title)
    assert restored.startswith("70\nบทที่ 11 - อวดดอกไม้\n\n")
    assert "หลังจากเค้นถามข้อมูลจากปากของเหล่าผู้ร่วมโต๊ะอาหารเสร็จสิ้น" in restored


def test_ensure_chapter_title_preserved_skips_when_already_present():
    """Verify that when polished prose already contains a title, no duplicate is added."""
    draft = "บทที่ 11 - อวดดอกไม้\n\nหลังจากเค้นถาม..."
    polished_with_title = "บทที่ 11 - อวดบุปผางาม\n\nหลังจากเค้นถามข้อมูล..."

    result = PolishingAgent._ensure_chapter_title_preserved(draft_text=draft, polished_text=polished_with_title)
    assert result == polished_with_title
    assert result.count("บทที่ 11") == 1


def test_ensure_chapter_title_preserved_no_header_in_draft():
    """Verify that chapters without headers pass through untouched."""
    draft = "สายลมพัดผ่านทุ่งหญ้าอย่างเงียบเชียบ..."
    polished = "สายลมเย็นเยียบพัดผ่านทุ่งหญ้าอันกว้างใหญ่..."

    result = PolishingAgent._ensure_chapter_title_preserved(draft_text=draft, polished_text=polished)
    assert result == polished


def test_polisher_integration_restores_title_with_mock_llm():
    """Verify end-to-end polisher call restores chapter title when LLM drops it."""
    polisher = PolishingAgent(model_name="mock-model")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="หลังจากเค้นถามข้อมูลจากผู้ร่วมโต๊ะอาหาร สองพี่น้องตัวน้อยก็ร่ายเวทมนตร์ปรับแก้ความทรงจำทันที"
    )
    polisher.llm = mock_llm

    draft = "70\nบทที่ 11 - อวดดอกไม้\n\nหลังจากเค้นถามข้อมูล..."
    bible = NovelBible(source_language="English", target_language="Thai")

    polished_output = polisher.polish(
        draft_text=draft,
        critique_notes="Enhance cadence and tone.",
        active_glossary=[],
        bible=bible
    )

    assert polished_output.startswith("70\nบทที่ 11 - อวดดอกไม้\n\n")
    assert "หลังจากเค้นถามข้อมูลจากผู้ร่วมโต๊ะอาหาร" in polished_output


def test_polisher_chunked_restores_title_with_mock_llm():
    """Verify chunked polishing retains chapter title from chunk 1."""
    polisher = PolishingAgent(model_name="mock-model")

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        AIMessage(content="ส่วนที่หนึ่งของเนื้อเรื่องได้รับการขัดเกลาอย่างสละสลวย"),
        AIMessage(content="ส่วนที่สองของเนื้อเรื่องดำเนินต่อไปอย่างน่าติดตาม"),
    ]
    polisher.llm = mock_llm

    chunk1_mock = MagicMock()
    chunk1_mock.chunk_index = 1
    chunk1_mock.total_chunks = 2
    chunk1_mock.start_line = 1
    chunk1_mock.end_line = 50
    chunk1_mock.content = "70\nบทที่ 11 - อวดดอกไม้\n\nเนื้อหาร่างส่วนที่หนึ่ง..."
    chunk1_mock.source_content = "70\nChapter 11 - Boasting a Flower\n\nSource content 1..."

    chunk2_mock = MagicMock()
    chunk2_mock.chunk_index = 2
    chunk2_mock.total_chunks = 2
    chunk2_mock.start_line = 51
    chunk2_mock.end_line = 100
    chunk2_mock.content = "เนื้อหาร่างส่วนที่สอง..."
    chunk2_mock.source_content = "Source content 2..."

    full_draft = "70\nบทที่ 11 - อวดดอกไม้\n\nเนื้อหาร่างส่วนที่หนึ่ง...\n\nเนื้อหาร่างส่วนที่สอง..."
    bible = NovelBible(source_language="English", target_language="Thai")

    polished_output = polisher.polish(
        draft_text=full_draft,
        critique_notes="Polish smoothly.",
        active_glossary=[],
        bible=bible,
        draft_chunks=[chunk1_mock, chunk2_mock]
    )

    assert polished_output.startswith("70\nบทที่ 11 - อวดดอกไม้\n\n")
    assert "ส่วนที่หนึ่งของเนื้อเรื่อง" in polished_output
    assert "ส่วนที่สองของเนื้อเรื่อง" in polished_output
