"""Tests for provider and per-agent generation setting resolution."""

from nousetsu.batch.runner import BatchRunner
from nousetsu.models.config import AgentGenerationSettings, ProjectConfig
from nousetsu.storage.repository import NovelRepository


def test_project_generation_overrides_are_independent_and_inherit_environment():
    config = ProjectConfig(
        model_name="openrouter:meta-llama/llama-3.3-70b-instruct",
        generation_settings={
            "drafter": {"temperature": 0.4, "thinking_level": "high"},
        },
    )
    env = {
        "NOVEL_TEMPERATURE": "0.8",
        "NOVEL_EXTRACTOR_TEMPERATURE": "0.2",
        "NOVEL_DRAFTER_TEMPERATURE": "0.7",
        "NOVEL_DRAFTER_THINKING_LEVEL": "low",
        "NOVEL_CRITIC_USE_INTERACTIONS": "false",
        "NOVEL_USE_INTERACTIONS": "true",
    }

    extractor = config.get_agent_generation_settings("extractor", environ=env)
    drafter = config.get_agent_generation_settings("drafter", environ=env)
    critic = config.get_agent_generation_settings("critic", environ=env)

    assert extractor["temperature"] == 0.2
    assert extractor["use_interactions_api"] is True
    assert drafter["temperature"] == 0.4
    assert drafter["thinking_level"] == "high"
    assert drafter["use_interactions_api"] is True
    assert critic["temperature"] == 0.8
    assert critic["use_interactions_api"] is False


def test_generation_defaults_match_tech_baseline():
    config = ProjectConfig()

    assert config.get_agent_generation_settings("extractor", environ={})["temperature"] == 0.1
    assert config.get_agent_generation_settings("critic", environ={})["thinking_level"] == "high"
    assert config.get_agent_generation_settings("drafter", environ={})["temperature"] == 0.1
    assert config.get_agent_generation_settings("polisher", environ={})["temperature"] == 0.1


def test_batch_runner_passes_independent_generation_settings_to_agents(tmp_path):
    repo = NovelRepository(tmp_path)
    repo.initialize_project("Generation settings", "Japanese", "English", model_name="mock-generation")
    config = repo.load_config()
    config.generation_settings = {
        "extractor": AgentGenerationSettings(temperature=0.25, use_interactions_api=False),
        "drafter": AgentGenerationSettings(temperature=0.75, use_interactions_api=True),
        "critic": AgentGenerationSettings(temperature=0.45),
    }
    repo.save_config(config)

    runner = BatchRunner(repo)

    assert runner.workflow.extractor.llm.temperature == 0.25
    assert runner.workflow.drafter.llm.temperature == 0.75
    assert runner.workflow.critic.llm.temperature == 0.45
    assert runner.workflow.generation_settings["extractor"]["use_interactions_api"] is False
    assert runner.workflow.generation_settings["drafter"]["use_interactions_api"] is True


def test_project_model_routes_resolve_per_role_and_scraper():
    config = ProjectConfig(
        model_name="openai:gpt-4.1-mini",
        critic_model="gemini-2.5-pro",
        scraper_model="openrouter:anthropic/claude-sonnet-4",
    )
    env = {
        "NOVEL_MODEL": "gemini-2.5-flash",
        "NOVEL_DRAFTER_MODEL": "openrouter:google/gemini-2.5-flash",
        "NOVEL_SCRAPER_MODEL": "openai:gpt-4o-mini",
        "NOVEL_FALLBACK_MODEL": "openrouter:openai/gpt-4.1-mini",
    }

    assert config.get_agent_model("critic", environ=env) == "gemini-2.5-pro"
    assert config.get_agent_model("drafter", environ=env) == "openai:gpt-4.1-mini"
    assert config.get_agent_model("scraper", environ=env) == "openrouter:anthropic/claude-sonnet-4"
    inherited_scraper = ProjectConfig(model_name="openai:gpt-4.1-mini")
    assert inherited_scraper.get_agent_model("scraper", environ=env) == "openai:gpt-4o-mini"
    assert config.get_fallback_model(environ=env) == "openrouter:openai/gpt-4.1-mini"


def test_builtin_and_template_defaults_agree():
    from pathlib import Path
    from dotenv import dotenv_values
    from nousetsu.models.config import GENERATION_ROLES

    config = ProjectConfig()
    template = dotenv_values(Path(__file__).parents[1] / ".env.example")
    builtin = config.get_effective_config(environ={})
    configured = config.get_effective_config(environ=template)
    for name in ("model_name", "fallback_model", "max_tpm", "max_rpm", "max_review_loops", "quality_threshold", "generation_settings"):
        assert builtin[name] == configured[name], name
    assert builtin["model_name"] == "gemini-3.5-flash-lite"
    assert builtin["fallback_model"] == "gemini-3.1-flash-lite"
    assert builtin["source_language"] == template["SOURCE_LANG"] == "Japanese"
    assert builtin["target_language"] == template["TARGET_LANG"] == "Thai"
    assert builtin["enable_rag"] is False
    assert builtin["max_tpm"] == 250000
    assert builtin["max_rpm"] == 30
    assert builtin["quality_threshold"] == 9.5
    for role in GENERATION_ROLES:
        assert builtin[role + "_model"] == configured[role + "_model"]
        generation = builtin["generation_settings"][role]
        assert generation["temperature"] == (1.0 if role == "scraper" else 0.1)
        assert generation["thinking_level"] == "high"
        assert generation["thinking_budget"] is None
        assert generation["use_interactions_api"] is True
    assert config.model_name is None
    assert config.max_tpm is None
    assert config.generation_settings == {}


def test_runtime_defaults_match_project_defaults():
    import inspect
    from nousetsu.graph.workflow import NovelTranslationWorkflow
    from nousetsu.models.state import TranslationState
    from nousetsu.utils.rate_limiter import SlidingWindowRateLimiter

    signature = inspect.signature(NovelTranslationWorkflow)
    assert signature.parameters["quality_threshold"].default == 9.5
    assert signature.parameters["enable_rag"].default is False
    assert TranslationState.model_fields["quality_threshold"].default == 9.5
    limiter = SlidingWindowRateLimiter()
    assert limiter.max_tpm == 250000
    assert limiter.max_rpm == 30
