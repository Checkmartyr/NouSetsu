"""Unit and integration tests for Agent Skills System."""
from pathlib import Path
import pytest
from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.agents.llm import MockNovelLLM
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.graph.procedural import get_default_drafter_graph
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import ChapterSummary, CharacterProfile, GlossaryItem, NovelBible, StyleGuide
from nousetsu.models.state import TranslationState
from nousetsu.skills.loader import load_skills_from_directory, parse_markdown_skill
from nousetsu.skills.models import AgentSkill
from nousetsu.skills.registry import SkillRegistry
from nousetsu.utils.genre import detect_genre


def test_agent_skill_model():
    """Verify AgentSkill data model initialization and defaults."""
    skill = AgentSkill(
        name="test_skill",
        agent="drafter",
        title="Test Skill",
        description="A test skill",
        content="Directives for testing."
    )
    assert skill.name == "test_skill"
    assert skill.agent == "drafter"
    assert skill.priority == 100
    assert skill.enabled is True
    assert skill.languages == ["all"]
    assert skill.genres == ["all"]
    assert skill.source == "builtin"


def test_builtin_skills_present():
    """Verify all 5 agents have built-in domain skills."""
    reg = SkillRegistry.get_instance()
    all_skills = reg.list_skills()
    assert len(all_skills) >= 15

    extractor_skills = [s.name for s in reg.get_active_skills("extractor")]
    assert "entity_disambiguation" in extractor_skills
    assert "relationship_mapper" in extractor_skills

    drafter_skills = [s.name for s in reg.get_active_skills("drafter")]
    assert "zero_anaphora_resolution" in drafter_skills
    assert "name_address_fidelity" in drafter_skills
    assert "character_voice_differentiation" in drafter_skills
    assert "idiom_localization" in drafter_skills

    critic_skills = [s.name for s in reg.get_active_skills("critic")]
    assert "omission_detector" in critic_skills
    assert "glossary_enforcer" in critic_skills
    assert "hallucination_guard" in critic_skills
    assert "nickname_disparity_auditor" in critic_skills

    polisher_skills = [s.name for s in reg.get_active_skills("polisher")]
    assert "translationese_filter" in polisher_skills
    assert "prose_cadence_enhancer" in polisher_skills
    assert "address_form_preservation" in polisher_skills
    assert "show_dont_tell" in polisher_skills

    chronicler_skills = [s.name for s in reg.get_active_skills("chronicler")]
    assert "lore_world_state_tracker" in chronicler_skills
    assert "character_status_tracker" in chronicler_skills


def test_catalog_files_loading():
    """Verify loading custom markdown skill files from catalog."""
    import nousetsu.skills
    catalog_dir = Path(nousetsu.skills.__file__).parent / "catalog"
    assert catalog_dir.exists()
    skills = load_skills_from_directory(catalog_dir)
    skill_names = [s.name for s in skills]
    assert "wuxia_martial_arts" in skill_names
    assert "isekai_fantasy_tropes" in skill_names
    assert "otome_court_etiquette" in skill_names


def test_smart_activation_by_language():
    """Verify language-specific skills activate and deactivate appropriately."""
    reg = SkillRegistry.get_instance()

    # Zero-anaphora is restricted to East Asian languages (JA/ZH/KO)
    ja_skills = [s.name for s in reg.get_active_skills("drafter", source_lang="Japanese")]
    assert "zero_anaphora_resolution" in ja_skills

    zh_skills = [s.name for s in reg.get_active_skills("drafter", source_lang="Chinese")]
    assert "zero_anaphora_resolution" in zh_skills

    de_skills = [s.name for s in reg.get_active_skills("drafter", source_lang="German")]
    assert "zero_anaphora_resolution" not in de_skills


def test_smart_activation_by_genre():
    """Verify genre-specific skills filter according to project genre."""
    reg = SkillRegistry.get_instance()

    # Xianxia genre should activate wuxia_martial_arts and cultivation_realm_extractor
    xianxia_drafter = [s.name for s in reg.get_active_skills("drafter", genre="xianxia")]
    assert "wuxia_martial_arts" in xianxia_drafter

    xianxia_extractor = [s.name for s in reg.get_active_skills("extractor", source_lang="Chinese", genre="xianxia")]
    assert "cultivation_realm_extractor" in xianxia_extractor

    # Romance genre should activate otome_court_etiquette and exclude wuxia combat
    romance_polisher = [s.name for s in reg.get_active_skills("polisher", genre="romance")]
    assert "otome_court_etiquette" in romance_polisher

    romance_drafter = [s.name for s in reg.get_active_skills("drafter", genre="romance")]
    assert "wuxia_martial_arts" not in romance_drafter

    # Isekai genre activates isekai_fantasy_tropes
    isekai_drafter = [s.name for s in reg.get_active_skills("drafter", source_lang="Japanese", genre="isekai")]
    assert "isekai_fantasy_tropes" in isekai_drafter


def test_build_prompt_section():
    """Verify prompt text generation from active skills."""
    reg = SkillRegistry.get_instance()
    prompt = reg.build_prompt_section("drafter", source_lang="Japanese", genre="isekai")
    assert "## ACTIVE SPECIALIZED AGENT SKILLS:" in prompt
    assert "Zero-Anaphora Subject & Pronoun Resolution" in prompt
    assert "Isekai & Adventurer Guild Conventions" in prompt


def test_detect_genre_heuristic():
    """Verify offline keyword-based genre detection."""
    xianxia_text = "The young cultivator circulated Qi through his Dantian, feeling the Golden Core solidify as the Sect Master observed."
    assert detect_genre(xianxia_text) == "xianxia"

    isekai_text = "After being reincarnated into another world, he registered at the Adventurer Guild to fight the Demon King with his cheat skill."
    assert detect_genre(isekai_text) == "isekai"

    litrpg_text = "A blue status window appeared before his eyes: [System Alert] Level Up! HP: 100/100, MP: 50/50. Quest completed."
    assert detect_genre(litrpg_text) == "litrpg"

    romance_text = "The villainess stood gracefully in the ballroom as the crown prince declared their engagement broken."
    assert detect_genre(romance_text) == "romance"

    general_text = "He walked slowly through the quiet streets of the city, looking up at the gray afternoon sky."
    assert detect_genre(general_text) == "general"


def test_agents_execute_with_skills(monkeypatch):
    """Verify all 5 agents can invoke successfully with skill prompt injections."""
    mock_llm = MockNovelLLM()

    extractor = EntityExtractorAgent(model_name="mock-novel-llm")
    extractor.llm = mock_llm
    bible = NovelBible(source_language="Japanese", genre="isekai")
    chars, terms, active = extractor.extract("Chapter text", bible=bible, genre="isekai")
    assert isinstance(chars, list)
    assert isinstance(terms, list)

    drafter = ContextAwareDrafterAgent(model_name="mock-novel-llm")
    drafter.llm = mock_llm
    draft = drafter.draft("Source text", bible=bible, active_characters=[], active_glossary=[], rolling_summaries=[], genre="isekai")
    assert draft

    critic = CritiqueAgent(model_name="mock-novel-llm")
    critic.llm = mock_llm
    audit, notes = critic.evaluate("Source", draft, bible=bible, active_characters=[], active_glossary=[], genre="isekai")
    assert audit.fidelity_score >= 0.0

    polisher = PolishingAgent(model_name="mock-novel-llm")
    polisher.llm = mock_llm
    polished = polisher.polish(draft, notes, active_glossary=[], bible=bible, genre="isekai")
    assert polished

    chronicler = ChroniclerAgent(model_name="mock-novel-llm")
    chronicler.llm = mock_llm
    summary = chronicler.chronicle(1, "Title", polished, genre="isekai", source_lang="Japanese")
    assert summary.chapter_num == 1


def test_workflow_tracks_active_skills():
    """Verify workflow executes and records active skills for all stages in state."""
    mock_llm = MockNovelLLM()
    workflow = NovelTranslationWorkflow(model_name="mock-novel-llm")
    workflow.extractor.llm = mock_llm
    workflow.drafter.llm = mock_llm
    workflow.critic.llm = mock_llm
    workflow.polisher.llm = mock_llm
    workflow.chronicler.llm = mock_llm

    bible = NovelBible(source_language="Japanese", target_language="English", genre="isekai")
    state = TranslationState(
        chapter_id="ch01",
        chapter_num=1,
        source_text="転生したらスライムだった。ステータス画面が開いた。",
        novel_bible=bible,
        genre="isekai"
    )

    final_state = workflow.run(state)
    assert final_state.current_stage == final_state.current_stage.CHRONICLING
    assert "extraction" in final_state.active_skills
    assert "drafting" in final_state.active_skills
    assert "critique" in final_state.active_skills
    assert "polishing" in final_state.active_skills
    assert "chronicling" in final_state.active_skills
    assert "zero_anaphora_resolution" in final_state.active_skills["drafting"]
    assert "name_address_fidelity" in final_state.active_skills["drafting"]
    assert "nickname_disparity_auditor" in final_state.active_skills["critique"]
    assert "address_form_preservation" in final_state.active_skills["polishing"]


def test_nickname_and_address_fidelity_skills_registered():
    """Verify detailed attributes of nickname and address fidelity skills."""
    reg = SkillRegistry.get_instance()
    all_skills = {s.name: s for s in reg.list_skills()}

    assert "name_address_fidelity" in all_skills
    drafter_skill = all_skills["name_address_fidelity"]
    assert drafter_skill.agent == "drafter"
    assert drafter_skill.priority == 105
    assert "formal/canonical" in drafter_skill.content
    assert "nickname" in drafter_skill.content

    assert "nickname_disparity_auditor" in all_skills
    critic_skill = all_skills["nickname_disparity_auditor"]
    assert critic_skill.agent == "critic"
    assert critic_skill.priority == 92
    assert "intimacy hallucinations" in critic_skill.content
    assert "intimacy flattening" in critic_skill.content

    assert "address_form_preservation" in all_skills
    polisher_skill = all_skills["address_form_preservation"]
    assert polisher_skill.agent == "polisher"
    assert polisher_skill.priority == 95
    assert "NEVER rewrite a formal name into a nickname" in polisher_skill.content


def test_nickname_skills_injected_in_prompts():
    """Verify that drafter, critic, and polisher prompt sections include nickname discipline."""
    reg = SkillRegistry.get_instance()

    drafter_section = reg.build_prompt_section("drafter")
    assert "Name & Nickname Address Form Fidelity" in drafter_section
    assert "NEVER swap it into a nickname" in drafter_section

    critic_section = reg.build_prompt_section("critic")
    assert "Nickname & Formal Address Disparity Auditor" in critic_section
    assert "intimacy hallucinations" in critic_section

    polisher_section = reg.build_prompt_section("polisher")
    assert "Address Form & Nickname Preservation" in polisher_section
    assert "NEVER rewrite a formal name into a nickname" in polisher_section


def test_drafter_procedural_graph_nickname_discipline():
    """Verify drafter procedural execution graph includes nickname rules and pitfalls."""
    graph = get_default_drafter_graph()
    guidance = graph.to_compact_guidance("Voice_Modulation")

    assert "formal names and nicknames" in guidance
    assert "Pitfalls to Avoid:" in guidance
    assert "Do NOT substitute formal character names with nicknames" in guidance

