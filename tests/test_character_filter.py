"""Unit and integration tests for per-scene character filtering."""
from unittest.mock import MagicMock
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.models.bible import CharacterProfile, NovelBible, StyleGuide
from nousetsu.utils.character_filter import filter_characters_for_scene


def test_filter_by_original_name():
    chars = [
        CharacterProfile(name="Amelia", original_name="アメリア", role="supporting"),
        CharacterProfile(name="Barlen", original_name="バーレン", role="supporting"),
        CharacterProfile(name="Chloe", original_name="クロエ", role="supporting"),
    ]
    # Only Amelia and Chloe mentioned in Japanese source text
    source_text = "アメリアは言った。「クロエ、準備はいい？」"
    filtered = filter_characters_for_scene(chars, source_text=source_text)

    names = [c.name for c in filtered]
    assert "Amelia" in names
    assert "Chloe" in names
    assert "Barlen" not in names


def test_filter_by_translated_name():
    chars = [
        CharacterProfile(name="Lord Raven", original_name="レイヴン", role="supporting"),
        CharacterProfile(name="Sylvia", original_name="シルヴィア", role="supporting"),
    ]
    target_text = "Lord Raven approached the altar in silence."
    filtered = filter_characters_for_scene(chars, target_text=target_text)

    names = [c.name for c in filtered]
    assert "Lord Raven" in names
    assert "Sylvia" not in names


def test_filter_by_aliases():
    chars = [
        CharacterProfile(
            name="Lin Feng",
            original_name="林枫",
            aliases=["Asura", "Sword God"],
            role="supporting"
        ),
        CharacterProfile(name="Old Man Hu", original_name="胡老", role="supporting"),
    ]
    source_text = "修罗之名震慑四方！(The name of Asura shook the four directions!)"
    filtered = filter_characters_for_scene(chars, source_text=source_text)

    names = [c.name for c in filtered]
    assert "Lin Feng" in names
    assert "Old Man Hu" not in names


def test_protagonist_core_role_always_retained():
    chars = [
        CharacterProfile(name="Main Hero", original_name="主人公", role="protagonist"),
        CharacterProfile(name="Lead Heroine", original_name="ヒロイン", role="lead"),
        CharacterProfile(name="Villager A", original_name="村人A", role="supporting"),
        CharacterProfile(name="Villager B", original_name="村人B", role="supporting"),
    ]
    # Neither protagonist nor heroine named, but Villager B is mentioned
    source_text = "「村人Bだ！逃げろ！」"
    filtered = filter_characters_for_scene(chars, source_text=source_text)

    names = [c.name for c in filtered]
    # Core roles retained for zero-anaphora subject inference
    assert "Main Hero" in names
    assert "Lead Heroine" in names
    assert "Villager B" in names
    # Unmentioned non-core supporting character omitted
    assert "Villager A" not in names


def test_fallback_when_zero_matches():
    chars = [
        CharacterProfile(name="Char 1", original_name="名前1", role="supporting"),
        CharacterProfile(name="Char 2", original_name="名前2", role="supporting"),
        CharacterProfile(name="Char 3", original_name="名前3", role="supporting"),
    ]
    # Unrelated text
    source_text = "空は青く、風が静かに吹いていた。"
    filtered = filter_characters_for_scene(chars, source_text=source_text, max_characters=2)

    # Falls back to top max_characters to prevent empty prompt
    assert len(filtered) == 2
    assert filtered[0].name == "Char 1"
    assert filtered[1].name == "Char 2"


def test_empty_and_whitespace_edge_cases():
    assert filter_characters_for_scene([]) == []

    chars = [CharacterProfile(name="Alice", original_name="アリス", role="supporting")]
    assert filter_characters_for_scene(chars, source_text="") == chars
    assert filter_characters_for_scene(chars, source_text="   ") == chars


def test_drafter_uses_scene_filtered_characters():
    drafter = ContextAwareDrafterAgent(model_name="mock-model")
    bible = NovelBible(
        title="Test Novel",
        source_language="Japanese",
        target_language="English",
        style_guide=StyleGuide()
    )
    chars = [
        CharacterProfile(name="Protagonist", original_name="主人公", role="protagonist"),
        CharacterProfile(name="Active Character", original_name="登場キャラ", role="supporting"),
        CharacterProfile(name="Absent Character", original_name="不在キャラ", role="supporting"),
    ]

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Draft text."
    mock_response.response_metadata = {}
    mock_response.usage_metadata = {}
    mock_llm.invoke.return_value = mock_response
    drafter.llm = mock_llm

    source_chunk = "登場キャラが微笑んだ。"
    draft = drafter._invoke_llm_draft(
        chunk_text=source_chunk,
        preceding_context="",
        bible=bible,
        active_characters=chars,
        active_glossary=[],
        rolling_summaries=[]
    )
    assert draft == "Draft text."

    # Inspect the system prompt sent to LLM
    call_args = mock_llm.invoke.call_args[0][0]
    sys_prompt = call_args[0].content
    assert "Protagonist" in sys_prompt
    assert "Active Character" in sys_prompt
    assert "Absent Character" not in sys_prompt


def test_critic_uses_scene_filtered_characters():
    critic = CritiqueAgent(model_name="mock-model")
    bible = NovelBible(
        title="Test Novel",
        source_language="Japanese",
        target_language="English",
        style_guide=StyleGuide()
    )
    chars = [
        CharacterProfile(name="Protagonist", original_name="主人公", role="protagonist"),
        CharacterProfile(name="Target Person", original_name="ターゲット", role="supporting"),
        CharacterProfile(name="Ignored Person", original_name="無視キャラ", role="supporting"),
    ]

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"fidelity_score": 9.0, "style_score": 9.0, "glossary_compliance_pct": 100.0, "critique_notes": "Good."}'
    mock_response.response_metadata = {}
    mock_response.usage_metadata = {}
    mock_llm.invoke.return_value = mock_response
    critic.llm = mock_llm

    audit, notes = critic._evaluate_single(
        source_text="ターゲットが立ち上がった。",
        draft_text="Target Person stood up.",
        bible=bible,
        active_characters=chars,
        active_glossary=[]
    )
    assert audit.fidelity_score == 9.0

    call_args = mock_llm.invoke.call_args[0][0]
    sys_prompt = call_args[0].content
    assert "Protagonist" in sys_prompt
    assert "Target Person" in sys_prompt
    assert "Ignored Person" not in sys_prompt
