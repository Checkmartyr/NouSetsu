"""Unit tests for robust critique prompt directives, anti-omission guards, and language regression validation."""
import pytest
from unittest.mock import MagicMock

from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.metadata import QualityAudit
from nousetsu.models.bible import NovelBible
from nousetsu.models.state import TranslationState
from nousetsu.prompts.templates import (
    CRITIQUE_SYSTEM_PROMPT,
    POLISHING_SYSTEM_PROMPT,
    PATCH_POLISHING_SYSTEM_PROMPT,
)
from nousetsu.skills.builtin.critic import CRITIC_SKILLS
from nousetsu.skills.builtin.polisher import POLISHER_SKILLS
from nousetsu.utils.language import is_genuine_language_regression


def test_is_genuine_language_regression():
    """Verify programmatic verification distinguishes genuine regression from false alarms."""
    # Genuine regression: Japanese source text in Thai target
    jp_text = "マギルカも同じ学園なの？あ、俺も俺も！俺もアルトリアへ入学するんだ"
    assert is_genuine_language_regression(jp_text, "Japanese", "Thai") is True
    assert is_genuine_language_regression(jp_text, "Japanese", "English") is True

    # False alarm: 100% Thai text with zero Japanese characters
    thai_text = "พวกเรากำลังเดินทางไปยังสถาบันเวทมนตร์แห่งอัลเดีย แมรี่มองออกไปนอกหน้าต่างด้วยรอยยิ้ม"
    assert is_genuine_language_regression(thai_text, "Japanese", "Thai") is False

    # English target text
    en_text = "They walked toward the grand academy. Mary looked out the window with a calm smile."
    assert is_genuine_language_regression(en_text, "Japanese", "English") is False


def test_critique_system_prompt_directives():
    """Verify CRITIQUE_SYSTEM_PROMPT contains multi-pass calibration and meta-text exemption."""
    # 1. Anti-hallucination verification
    assert "CRITICAL VERIFICATION: You must NEVER claim a sentence or dialogue line is untranslated" in CRITIQUE_SYSTEM_PROMPT
    # 2. Webnovel author note exemption
    assert "Webnovel Meta & Author Notes Exemption" in CRITIQUE_SYSTEM_PROMPT
    assert "ブックマークありがとうございます" in CRITIQUE_SYSTEM_PROMPT
    # 3. Multi-pass calibration (no moving goalposts)
    assert "MULTI-PASS CALIBRATION (PASS 2+ RE-AUDITS)" in CRITIQUE_SYSTEM_PROMPT
    assert "DO NOT move the goalposts" in CRITIQUE_SYSTEM_PROMPT
    # 4. Calibrated 9.0-9.4 publication grade
    assert "9.0 – 9.4 (Publication Grade)" in CRITIQUE_SYSTEM_PROMPT


def test_polishing_prompts_content_retention():
    """Verify polishing prompts mandate full-content and sentence retention."""
    assert "FULL-CONTENT RETENTION" in POLISHING_SYSTEM_PROMPT
    assert "NEVER delete, skip, or consolidate dialogue lines" in POLISHING_SYSTEM_PROMPT
    assert "FULL-CONTENT RETENTION" in PATCH_POLISHING_SYSTEM_PROMPT


def test_builtin_skills_contain_retention_and_omission_updates():
    """Verify built-in skills contain content retention guard and author note exemption."""
    # Polisher content_retention_guard
    polisher_skill_names = [s.name for s in POLISHER_SKILLS]
    assert "content_retention_guard" in polisher_skill_names
    retention_skill = next(s for s in POLISHER_SKILLS if s.name == "content_retention_guard")
    assert "never drop the opening sentence or the final closing sentence" in retention_skill.content

    # Critic omission_detector
    omission_skill = next(s for s in CRITIC_SKILLS if s.name == "omission_detector")
    assert "Non-Narrative Exemption" in omission_skill.content
    assert "ブックマークありがとうございます" in omission_skill.content


def test_workflow_guards_against_hallucinated_language_regression():
    """Verify workflow discards false language regression warnings on target-language text."""
    wf = NovelTranslationWorkflow(model_name="mock-model", quality_threshold=9.0)
    bible = NovelBible(source_language="Japanese", target_language="Thai")

    # Target text is 100% Thai
    thai_text = "มาทิลด้าเดินเข้ามาในห้องพยาบาลอย่างเงียบเชียบ เธอร่ายเวทมนตร์รักษาอย่างรวดเร็ว"

    state = TranslationState(
        chapter_num=22,
        chapter_id="0022",
        source_text="source text",
        draft_text=thai_text,
        polished_text=thai_text,
        novel_bible=bible,
        review_iteration=2,
        max_review_loops=3,
        quality_threshold=9.0,
        quality_audit=QualityAudit(
            fidelity_score=9.2,
            style_score=9.0,
            glossary_compliance_pct=100.0,
            passed=True,
            warnings=["CRITICAL LANGUAGE REGRESSION: Hallucinated Japanese quote"]
        )
    )

    # Route after critique should NOT be blocked by hallucinated regression warning
    route = wf._route_after_critique(state)
    assert route == "chronicle"  # Scores >= 9.0 and hallucinated regression was ignored
