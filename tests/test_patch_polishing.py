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
