"""Regression tests for settings resolution and actual prompt context consumption."""
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from nousetsu.models.config import ProjectConfig, resolve_agent_generation_settings
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import NovelBible
from nousetsu.batch.runner import BatchRunner
from nousetsu.storage.repository import NovelRepository

@pytest.mark.parametrize("name,value", [("max_tpm",0),("max_rpm",-1),("max_review_loops",6),("quality_threshold",float("nan")),("target_chunk_lines",0),("chunk_overlap_lines",-1),("safety_subdivision_min_lines",0)])
def test_invalid_project_constraints(name,value):
    with pytest.raises(ValidationError):
        ProjectConfig(**{name:value})

@pytest.mark.parametrize("name,default,override",[("max_tpm",250000,100),("max_rpm",30,7),("max_review_loops",3,2),("quality_threshold",9.5,9.0)])
def test_saved_override_and_explicit_reset(name,default,override):
    env={"NOVEL_"+name.upper():str(override)}
    assert ProjectConfig().resolve_value(name,{})==default
    assert ProjectConfig().resolve_value(name,env)==override
    assert ProjectConfig(**{name:default}).resolve_value(name,env)==default

@pytest.mark.parametrize("values",[{"NOVEL_TEMPERATURE":"nan"},{"NOVEL_TEMPERATURE":"3"},{"NOVEL_USE_INTERACTIONS":"wrong"},{"NOVEL_THINKING_BUDGET":"-1"}])
def test_invalid_effective_generation_rejected(values):
    with pytest.raises((ValueError,ValidationError)):
        resolve_agent_generation_settings("drafter",environ=values)

@pytest.mark.parametrize("overlap,expected",[(0,""),(1,"three"),(2,"two\nthree")])
def test_overlap_is_consumed_in_next_chunk(overlap,expected,monkeypatch):
    agent=ContextAwareDrafterAgent(model_name="mock",environ={},chunk_overlap_lines=overlap)
    contexts=[]
    def draft(**kwargs):
        contexts.append(kwargs["preceding_context"])
        return "one\ntwo\nthree"
    monkeypatch.setattr(agent,"_draft_single_chunk",draft)
    chunks=[SimpleNamespace(content="source",chunk_index=i,total_chunks=2) for i in (1,2)]
    agent.draft_chunked(chunks,NovelBible(title="fixture"),[],[],[])
    assert contexts==["",expected]

def test_runner_project_values_and_snapshot(tmp_path,monkeypatch):
    env=tmp_path/"machine.env";env.write_text("NOVEL_MAX_REVIEW_LOOPS=5\nNOVEL_MAX_TPM=90000\nNOVEL_USE_INTERACTIONS=false\n")
    monkeypatch.setenv("NOUSETSU_ENV_FILE",str(env))
    monkeypatch.delenv("NOVEL_MAX_REVIEW_LOOPS",raising=False)
    monkeypatch.delenv("NOVEL_MAX_TPM",raising=False)
    monkeypatch.delenv("NOVEL_USE_INTERACTIONS",raising=False)
    repo=NovelRepository(tmp_path/"project")
    repo.initialize_project("fixture","Japanese","English",model_name="mock")
    cfg=repo.load_config();cfg.max_review_loops=2;cfg.max_tpm=50000;cfg.chunk_overlap_lines=0;cfg.cross_folder_summaries=False;cfg.filter_scene_characters=False;repo.save_config(cfg)
    runner=BatchRunner(repo)
    assert runner.max_review_loops==2
    assert runner.rate_limiter.max_tpm==50000
    assert runner.workflow.drafter.chunk_overlap_lines==0
    assert runner.workflow.cross_folder_summaries is False
    assert runner.workflow.drafter.filter_scene_characters is False
    assert runner.workflow.filter_extractor_entities is True
    env.write_text("NOVEL_MAX_REVIEW_LOOPS=1\nNOVEL_USE_INTERACTIONS=true\n")
    assert runner.environ["NOVEL_USE_INTERACTIONS"]=="false"
    assert BatchRunner(repo).environ["NOVEL_USE_INTERACTIONS"]=="true"
