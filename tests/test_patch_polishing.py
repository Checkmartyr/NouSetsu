"""Unit and integration tests for patch-based polishing in PolishingAgent."""
from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.models.bible import NovelBible, StyleGuide


def test_polisher_applies_patch_edits():
    polisher = PolishingAgent(model_name="mock-model")
    bible = NovelBible(source_language="English", target_language="Thai")

    base_draft = (
        "# บทที่ 1: การเริ่มต้น\n\n"
        "แอลเลนมองไปที่ท้องฟ้าสีครามและถอนหายใจยาว\n"
        "เขารู้ดีว่าการเดินทางข้างหน้าคงไม่ง่ายดายเลย"
    )

    patch_llm_output = (
        "<<<<<<< SEARCH\n"
        "แอลเลนมองไปที่ท้องฟ้าสีครามและถอนหายใจยาว\n"
        "=======\n"
        "แอลเลนแหงนมองผืนนภาสีครามพลางทอดถอนหายใจยาวเหยียด\n"
        ">>>>>>>"
    )

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=patch_llm_output)
    polisher.llm = mock_llm

    result = polisher.polish(
        draft_text=base_draft,
        critique_notes="Make first sentence more poetic.",
        active_glossary=[],
        bible=bible,
        use_patch=True
    )

    assert "แอลเลนแหงนมองผืนนภาสีครามพลางทอดถอนหายใจยาวเหยียด" in result
    assert "เขารู้ดีว่าการเดินทางข้างหน้าคงไม่ง่ายดายเลย" in result
    assert "# บทที่ 1: การเริ่มต้น" in result


def test_polisher_no_changes_needed_retains_draft():
    polisher = PolishingAgent(model_name="mock-model")
    bible = NovelBible(source_language="English", target_language="Thai")

    base_draft = "บทที่ 1: สมบูรณ์แบบทุกประโยคแล้ว"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="NO_CHANGES_NEEDED")
    polisher.llm = mock_llm

    result = polisher.polish(
        draft_text=base_draft,
        critique_notes="Looks good, just verify.",
        active_glossary=[],
        bible=bible,
        use_patch=True
    )

    assert result == base_draft


def test_polisher_full_text_fallback_when_not_patch():
    polisher = PolishingAgent(model_name="mock-model")
    bible = NovelBible(source_language="English", target_language="Thai")

    base_draft = "บทที่ 1: ร่างเดิม"
    full_rewrite = "บทที่ 1: ร่างใหม่ที่ได้รับการขัดเกลาทั้งบทเรียบร้อยแล้ว"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=full_rewrite)
    polisher.llm = mock_llm

    result = polisher.polish(
        draft_text=base_draft,
        critique_notes="Rewrite with elegance.",
        active_glossary=[],
        bible=bible,
        use_patch=False
    )

    assert result == full_rewrite


def test_polisher_chunked_propagates_use_patch():
    """Verify that chunked polishing properly propagates use_patch to chunk prompts and applies search/replace."""
    from nousetsu.utils.chunker import LineChunk

    polisher = PolishingAgent(model_name="mock-model")
    bible = NovelBible(source_language="English", target_language="Thai")

    chunks = [
        LineChunk(
            chunk_index=1,
            total_chunks=2,
            start_line=1,
            end_line=2,
            content="# บทที่ 1: การเดินทาง\nท้องฟ้าแจ่มใส",
            source_content="Chapter 1: The Journey\nThe sky was clear."
        ),
        LineChunk(
            chunk_index=2,
            total_chunks=2,
            start_line=3,
            end_line=4,
            content="แอลเลนออกเดินทางสู่ป่าใหญ่",
            source_content="Allen departed into the great forest."
        )
    ]

    captured_prompts = []

    def mock_invoke(messages):
        sys_prompt = messages[0].content
        captured_prompts.append(sys_prompt)
        user_prompt = messages[1].content
        if "ท้องฟ้าแจ่มใส" in user_prompt:
            return AIMessage(content="<<<<<<< SEARCH\nท้องฟ้าแจ่มใส\n=======\nผืนนภาปลอดโปร่งแจ่มกระจ่าง\n>>>>>>>")
        else:
            return AIMessage(content="NO_CHANGES_NEEDED")

    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(side_effect=mock_invoke)
    mock_llm.last_model_used = "mock-model"
    polisher.llm = mock_llm

    result = polisher.polish(
        draft_text="# บทที่ 1: การเดินทาง\nท้องฟ้าแจ่มใส\n\nแอลเลนออกเดินทางสู่ป่าใหญ่",
        critique_notes="Enhance atmospheric descriptions.",
        active_glossary=[],
        bible=bible,
        draft_chunks=chunks,
        use_patch=True
    )

    # Both chunks must have received PATCH_POLISHING_SYSTEM_PROMPT
    assert len(captured_prompts) == 2
    assert "SEARCH/REPLACE" in captured_prompts[0]
    assert "SEARCH/REPLACE" in captured_prompts[1]

    # First chunk patch was applied, second chunk retained
    assert "ผืนนภาปลอดโปร่งแจ่มกระจ่าง" in result
    assert "แอลเลนออกเดินทางสู่ป่าใหญ่" in result
    assert "# บทที่ 1: การเดินทาง" in result
