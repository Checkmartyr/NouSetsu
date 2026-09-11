"""Tests for per-agent model configuration and automatic fallback model mechanism."""
from pathlib import Path
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.agents.llm import FallbackChatModel, MockNovelLLM, get_llm
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import NovelBible
from nousetsu.models.config import ProjectConfig
from nousetsu.models.metadata import PipelineStage
from nousetsu.models.state import TranslationState
from nousetsu.storage.repository import NovelRepository


class FailingMockLLM(MockNovelLLM):
    """Mock LLM that simulates an HTTP 429 quota exhaustion error."""

    model_name: str = "failing-mock-llm"

    def _generate(self, messages, stop=None, **kwargs):
        raise RuntimeError("429 ResourceExhausted: Quota exceeded for model.")


def test_fallback_chat_model_primary_success():
    primary = MockNovelLLM(model_name="primary-mock")
    fallback = MockNovelLLM(model_name="fallback-mock")
    model = FallbackChatModel(
        primary=primary,
        fallback=fallback,
        primary_model_name="primary-mock",
        fallback_model_name="fallback-mock"
    )

    assert model.model_name == "primary-mock"
    result = model.invoke([HumanMessage(content="Hello world")])
    assert isinstance(result, AIMessage)
    assert model.last_model_used == "primary-mock"
    assert model.model_name == "primary-mock"


def test_fallback_chat_model_activates_on_error():
    primary = FailingMockLLM(model_name="failing-mock")
    fallback = MockNovelLLM(model_name="fallback-mock")
    callback_records = []

    def on_fallback_cb(fallback_name, err):
        callback_records.append((fallback_name, str(err)))

    model = FallbackChatModel(
        primary=primary,
        fallback=fallback,
        primary_model_name="failing-mock",
        fallback_model_name="fallback-mock",
        on_fallback=on_fallback_cb
    )

    result = model.invoke([HumanMessage(content="Extracting entities")])
    assert isinstance(result, AIMessage)
    assert model.last_model_used == "fallback-mock"
    assert model.model_name == "fallback-mock"
    assert len(callback_records) == 1
    assert callback_records[0][0] == "fallback-mock"
    assert "429" in callback_records[0][1]


def test_get_llm_factory_fallback():
    # Without fallback
    single_llm = get_llm(model_name="mock-single")
    assert isinstance(single_llm, MockNovelLLM)
    assert single_llm.model_name == "mock-single"

    # With fallback
    fallback_llm = get_llm(model_name="mock-primary", fallback_model="mock-fallback")
    assert isinstance(fallback_llm, FallbackChatModel)
    assert fallback_llm.primary_model_name == "mock-primary"
    assert fallback_llm.fallback_model_name == "mock-fallback"


def test_project_config_agent_models_and_helpers():
    cfg = ProjectConfig(
        model_name="gemini-2.5-pro",
        fallback_model="gemini-2.5-flash",
        extractor_model="gemini-2.5-flash",
        drafter_model="gemini-2.5-pro",
        critic_model=None, # Should fallback to model_name
        polisher_model=None,
        chronicler_model=None,
    )

    assert cfg.get_agent_model("extractor") == "gemini-2.5-flash"
    assert cfg.get_agent_model("drafter") == "gemini-2.5-pro"
    assert cfg.get_agent_model("critic") == "gemini-2.5-pro" # fallback to default
    assert cfg.get_agent_model("polisher") == "gemini-2.5-pro"
    assert cfg.get_agent_model("chronicler") == "gemini-2.5-pro"
    assert cfg.get_agent_fallback_model() == "gemini-2.5-flash"


def test_agents_accept_fallback_model():
    extractor = EntityExtractorAgent(model_name="mock-extractor", fallback_model="mock-fallback")
    drafter = ContextAwareDrafterAgent(model_name="mock-drafter", fallback_model="mock-fallback")
    critic = CritiqueAgent(model_name="mock-critic", fallback_model="mock-fallback")
    polisher = PolishingAgent(model_name="mock-polisher", fallback_model="mock-fallback")
    chronicler = ChroniclerAgent(model_name="mock-chronicler", fallback_model="mock-fallback")

    assert extractor.last_model_used == "mock-extractor"
    assert drafter.last_model_used == "mock-drafter"
    assert critic.last_model_used == "mock-critic"
    assert polisher.last_model_used == "mock-polisher"
    assert chronicler.last_model_used == "mock-chronicler"


def test_workflow_records_per_agent_model(tmp_path: Path):
    workflow = NovelTranslationWorkflow(
        model_name="mock-default",
        fallback_model="mock-fallback",
        extractor_model="mock-extractor",
        drafter_model="mock-drafter",
        critic_model="mock-critic",
        polisher_model="mock-polisher",
        chronicler_model="mock-chronicler",
        max_review_loops=1
    )

    bible = NovelBible(title="Test Novel", source_language="Japanese", target_language="English")
    state = TranslationState(
        chapter_id="test_01",
        chapter_num=1,
        source_file=str(tmp_path / "ch01.txt"),
        source_text="太郎は立ち上がった。\n「行くぞ」と彼は言った。",
        output_file=str(tmp_path / "ch01_trans.md"),
        novel_bible=bible
    )

    # 1. Extraction step
    ext_res = workflow._extract_step(state)
    assert len(ext_res["step_token_records"]) == 1
    assert ext_res["step_token_records"][0].model == "mock-extractor"

    state.active_characters = ext_res["active_characters"]
    state.active_glossary = ext_res["active_glossary"]
    state.step_token_records = ext_res["step_token_records"]

    # 2. Drafting step
    draft_res = workflow._draft_step(state)
    assert len(draft_res["step_token_records"]) == 2
    assert draft_res["step_token_records"][1].model == "mock-drafter"

    state.draft_text = draft_res["draft_text"]
    state.step_token_records = draft_res["step_token_records"]

    # 3. Critique step
    critique_res = workflow._critique_step(state)
    assert len(critique_res["step_token_records"]) == 3
    assert critique_res["step_token_records"][2].model == "mock-critic"

    state.quality_audit = critique_res["quality_audit"]
    state.critique_notes = critique_res["critique_notes"]
    state.step_token_records = critique_res["step_token_records"]

    # 4. Polishing step
    polish_res = workflow._polish_step(state)
    assert len(polish_res["step_token_records"]) == 4
    assert polish_res["step_token_records"][3].model == "mock-polisher"

    state.polished_text = polish_res["polished_text"]
    state.best_polished_text = polish_res["best_polished_text"]
    state.step_token_records = polish_res["step_token_records"]

    # 5. Chronicling step
    chronicle_res = workflow._chronicle_step(state)
    meta = workflow.chronicler.assemble_metadata(
        chapter_id=state.chapter_id,
        chapter_num=state.chapter_num,
        source_file=state.source_file,
        source_sha256="abc",
        output_file=state.output_file,
        source_text=state.source_text,
        final_text=chronicle_res["polished_text"],
        model_name="mock-default",
        duration_seconds=5.0,
        quality_audit=chronicle_res["quality_audit"],
        active_characters=state.active_characters,
        active_glossary=state.active_glossary,
        draft_text=state.draft_text,
        critique_notes=state.critique_notes,
        polished_text=chronicle_res["polished_text"],
        step_usage=state.step_token_records
    )

    models_logged = [r.model for r in meta.stats.step_usage]
    assert "mock-extractor" in models_logged
    assert "mock-drafter" in models_logged
    assert "mock-critic" in models_logged
    assert "mock-polisher" in models_logged


@pytest.mark.asyncio
async def test_tui_settings_modal_agent_models(tmp_path: Path):
    from nousetsu.tui.app import NovelAgentApp
    from nousetsu.tui.widgets.settings_modal import SettingsModal
    from textual.widgets import Button, Input

    app = NovelAgentApp(
        input_dir="raw_chapters",
        output_dir="translated_chapters",
        model_name="mock-model"
    )
    async with app.run_test() as pilot:
        app.action_open_settings()
        await pilot.pause()

        settings_screen = app.screen
        assert isinstance(settings_screen, SettingsModal)

        inp_fallback = settings_screen.query_one("#set_fallback_model", Input)
        inp_extractor = settings_screen.query_one("#set_extractor_model", Input)
        inp_drafter = settings_screen.query_one("#set_drafter_model", Input)

        inp_fallback.value = "mock-fallback-val"
        inp_extractor.value = "mock-extractor-val"
        inp_drafter.value = "mock-drafter-val"

        btn_save = settings_screen.query_one("#btn_save_settings", Button)
        await pilot.click(btn_save)
        await pilot.pause()

        persisted_cfg = app.repo.load_config()
        assert persisted_cfg.fallback_model == "mock-fallback-val"
        assert persisted_cfg.extractor_model == "mock-extractor-val"
        assert persisted_cfg.drafter_model == "mock-drafter-val"
        assert app.runner.fallback_model == "mock-fallback-val"
        assert app.runner.extractor_model == "mock-extractor-val"
        assert app.runner.drafter_model == "mock-drafter-val"

