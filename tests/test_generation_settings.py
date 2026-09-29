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


def test_generation_defaults_keep_existing_agent_defaults():
    config = ProjectConfig()

    assert config.get_agent_generation_settings("extractor", environ={})["temperature"] == 0.1
    assert config.get_agent_generation_settings("critic", environ={})["thinking_level"] == "medium"
    assert config.get_agent_generation_settings("drafter", environ={})["temperature"] == 1.0
    assert config.get_agent_generation_settings("polisher", environ={})["temperature"] == 1.0


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
