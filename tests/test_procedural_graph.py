"""Tests for Procedural Graph integration in Extractor and Drafter agents (arXiv:2609.09153v1)."""
import pytest
from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.agents.polisher import PolishingAgent
from nousetsu.graph.pg_refiner import DiagnosticTrace, GraphEditOperation, ProceduralGraphRefiner
from nousetsu.graph.procedural import (
    ProceduralEdge,
    ProceduralGraph,
    ProceduralNode,
    ProceduralNodeType,
    ProceduralRelation,
    get_default_chronicler_graph,
    get_default_critic_graph,
    get_default_drafter_graph,
    get_default_extractor_graph,
    get_default_polisher_graph,
)
from nousetsu.models.bible import NovelBible, StyleGuide
from nousetsu.models.metadata import QualityAudit
from nousetsu.utils.chunker import LineChunk


def test_procedural_graph_localization():
    """Verify that localized subgraphs only extract relevant outgoing transitions."""
    g = get_default_extractor_graph()
    assert len(g.nodes) == 4
    assert len(g.edges) == 3

    # Localize at Scan_Candidates with 1 hop
    local_edges = g.localize("Scan_Candidates", max_hops=1)
    assert len(local_edges) == 1
    assert local_edges[0].source == "Scan_Candidates"
    assert local_edges[0].target == "Filter_Known"

    # Localize at Scan_Candidates with 2 hops
    local_edges_2hop = g.localize("Scan_Candidates", max_hops=2)
    assert len(local_edges_2hop) == 2
    assert [e.target for e in local_edges_2hop] == ["Filter_Known", "Deduce_Profiles"]


def test_procedural_guidance_token_frugality():
    """Verify serialized procedural directives are ultra-compact (< 150 words / ~120 tokens)."""
    g = get_default_drafter_graph()
    guidance_init = g.to_compact_guidance("Scene_Init", max_hops=2)
    assert "Scene Initialization" in guidance_init or "Zero-Anaphora" in guidance_init
    assert "Pitfalls to Avoid:" in guidance_init

    # Token/word count verification
    words = guidance_init.split()
    assert len(words) < 120, f"Guidance too verbose ({len(words)} words)"

    guidance_cont = g.to_compact_guidance("Boundary_Continuity", max_hops=2)
    assert "Preceding Scene Context" in guidance_cont
    words_cont = guidance_cont.split()
    assert len(words_cont) < 120, f"Continuity guidance too verbose ({len(words_cont)} words)"


def test_extractor_with_procedural_graph():
    """Verify EntityExtractorAgent formats procedural guidance correctly."""
    bible = NovelBible(
        novel_title="Test Novel",
        source_language="Japanese",
        target_language="English",
        style_guide=StyleGuide()
    )
    extractor = EntityExtractorAgent(model_name="mock-novel-llm")
    assert extractor.procedural_graph is not None

    chars, terms, active = extractor.extract(
        source_text="佐藤は剣を抜いた。「行くぞ！」",
        bible=bible
    )
    assert isinstance(chars, list)
    assert isinstance(terms, list)
    assert isinstance(active, list)


def test_drafter_with_procedural_graph_single_and_chunked():
    """Verify ContextAwareDrafterAgent applies procedural graph guidance in single and chunked modes."""
    bible = NovelBible(
        novel_title="Test Novel",
        source_language="Japanese",
        target_language="English",
        style_guide=StyleGuide()
    )
    drafter = ContextAwareDrafterAgent(model_name="mock-novel-llm")
    assert drafter.procedural_graph is not None

    # Test single chunk
    result = drafter.draft(
        source_text="佐藤は剣を抜いた。「行くぞ！」",
        bible=bible,
        active_characters=[],
        active_glossary=[],
        rolling_summaries=[]
    )
    assert "Translated Chapter" in result

    # Test chunked mode
    chunks = [
        LineChunk(chunk_index=1, total_chunks=2, start_line=1, end_line=10, content="Line 1\nLine 2"),
        LineChunk(chunk_index=2, total_chunks=2, start_line=11, end_line=20, content="Line 3\nLine 4"),
    ]
    result_chunked = drafter.draft(
        source_text="Line 1\nLine 2\nLine 3\nLine 4",
        bible=bible,
        active_characters=[],
        active_glossary=[],
        rolling_summaries=[],
        chunks=chunks
    )
    assert "Translated Chapter" in result_chunked


def test_pg_refiner_mutations_and_validation(tmp_path):
    """Verify ProceduralGraphRefiner applies edits, validates structural checks, and records rejections."""
    base_graph = get_default_drafter_graph()
    memory_file = tmp_path / "rejection_memory.json"
    refiner = ProceduralGraphRefiner(model_name="mock-novel-llm", rejection_memory_path=memory_file)

    # Valid mutation operation
    valid_edit = GraphEditOperation(
        operation="UPDATE",
        edge_source="Zero_Anaphora_Resolution",
        edge_target="Voice_Modulation",
        new_guidance="Trace pronouns strictly before dialogue.",
        new_pitfalls="Do not invert speaker roles.",
        rationale="Fix speaker confusion."
    )
    mutated_graph = refiner._apply_edits(base_graph, [valid_edit])
    assert refiner._validate_candidate(mutated_graph) is True

    # Verify updated attribute
    for e in mutated_graph.edges:
        if e.source == "Zero_Anaphora_Resolution" and e.target == "Voice_Modulation":
            assert e.guidance == "Trace pronouns strictly before dialogue."
            assert e.pitfalls == "Do not invert speaker roles."

    # Invalid mutation (referencing non-existent node)
    invalid_edit = GraphEditOperation(
        operation="ADD",
        edge_source="Zero_Anaphora_Resolution",
        edge_target="Non_Existent_Node",
        new_guidance="Bad edge.",
        rationale="Test invalid edge."
    )
    invalid_graph = refiner._apply_edits(base_graph, [invalid_edit])
    assert refiner._validate_candidate(invalid_graph) is False

    # Verify rejection recording
    refiner._record_rejection([invalid_edit], "Target node does not exist")
    assert len(refiner.rejection_memory) == 1
    assert memory_file.exists()


def test_cmd_graph_info_renders(capsys):
    """Verify cmd_graph_info executes and renders Rich trees without errors."""
    import argparse
    from nousetsu.cli.app import cmd_graph_info

    # Test all
    cmd_graph_info(argparse.Namespace(agent="all"))
    # Test extractor
    cmd_graph_info(argparse.Namespace(agent="extractor"))
    # Test drafter
    cmd_graph_info(argparse.Namespace(agent="drafter"))
    # Test invalid agent
    cmd_graph_info(argparse.Namespace(agent="non_existent"))


def test_repository_procedural_graph_persistence(tmp_path):
    """Verify NovelRepository saves and loads procedural graphs accurately."""
    from nousetsu.storage.repository import NovelRepository
    repo = NovelRepository(tmp_path)
    base_graph = get_default_drafter_graph()
    
    # Initially None
    assert repo.load_procedural_graph("drafter") is None

    # Save and reload
    saved_path = repo.save_procedural_graph(base_graph, "drafter")
    assert saved_path.exists()
    loaded = repo.load_procedural_graph("drafter")
    assert loaded is not None
    assert loaded.graph_id == base_graph.graph_id
    assert len(loaded.edges) == len(base_graph.edges)

    # Folder-scoped fallback
    assert repo.load_procedural_graph("drafter", folder="Volume_01") is not None


def test_collect_traces_from_repository(tmp_path):
    """Verify collect_traces_from_repository extracts DiagnosticTraces from project metadata."""
    from nousetsu.storage.repository import NovelRepository
    from nousetsu.models.metadata import ChapterMetadata, QualityAudit, StageArtifacts, CheckpointData
    from nousetsu.graph.pg_refiner import collect_traces_from_repository

    repo = NovelRepository(tmp_path)
    ch = ChapterMetadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="0001.txt",
        source_sha256="abc",
        output_file="0001.md",
        checkpoint=CheckpointData(
            stage_artifacts=StageArtifacts(
                draft_text="Sample drafted text.",
                critique_notes="Speaker attribution reversed in scene 2."
            )
        ),
        quality_audit=QualityAudit(
            fidelity_score=7.0,
            style_score=8.0,
            warnings=["Speaker attribution warning"]
        )
    )
    repo.save_all_metadata({"chapter_0001": ch})

    traces = collect_traces_from_repository(repo, stage="all")
    assert len(traces) == 2
    stages = {t.stage for t in traces}
    assert stages == {"drafter", "critic"}

    drafter_traces = collect_traces_from_repository(repo, stage="drafter")
    assert len(drafter_traces) == 1
    assert drafter_traces[0].stage == "drafter"
    assert drafter_traces[0].is_success is False
    assert drafter_traces[0].fidelity_score == 7.0
    assert "Speaker attribution reversed" in drafter_traces[0].critique_notes


def test_cmd_learn_graph_cli(tmp_path, monkeypatch):
    """Verify cmd_learn_graph executes smoothly with dry-run and mock models."""
    import argparse
    from nousetsu.storage.repository import NovelRepository
    from nousetsu.models.metadata import ChapterMetadata, QualityAudit, StageArtifacts, CheckpointData
    from nousetsu.cli.app import cmd_learn_graph

    repo = NovelRepository(tmp_path)
    
    # 1. Test when no traces exist
    cmd_learn_graph(argparse.Namespace(
        project_dir=str(tmp_path),
        folder=None,
        agent="all",
        max_traces=10,
        dry_run=True,
        model="mock-novel-llm"
    ))

    # 2. Add passing chapter
    ch_pass = ChapterMetadata(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="0001.txt",
        source_sha256="abc",
        output_file="0001.md",
        checkpoint=CheckpointData(stage_artifacts=StageArtifacts(draft_text="Clean draft")),
        quality_audit=QualityAudit(fidelity_score=9.5, style_score=9.5, warnings=[])
    )
    repo.save_all_metadata({"chapter_0001": ch_pass})

    cmd_learn_graph(argparse.Namespace(
        project_dir=str(tmp_path),
        folder=None,
        agent="drafter",
        max_traces=10,
        dry_run=True,
        model="mock-novel-llm"
    ))

    # 3. Add failing chapter and mock refiner proposal
    ch_fail = ChapterMetadata(
        chapter_id="chapter_0002",
        chapter_num=2,
        source_file="0002.txt",
        source_sha256="def",
        output_file="0002.md",
        checkpoint=CheckpointData(stage_artifacts=StageArtifacts(
            draft_text="Confused dialogue",
            critique_notes="Speaker attribution reversed between Alice and Bob."
        )),
        quality_audit=QualityAudit(fidelity_score=7.0, style_score=7.5, warnings=["Speaker attribution swap"])
    )
    repo.save_all_metadata({"chapter_0001": ch_pass, "chapter_0002": ch_fail})

    from unittest.mock import patch, MagicMock
    mock_edits_json = (
        '[\n'
        '  {\n'
        '    "operation": "UPDATE",\n'
        '    "edge_source": "Zero_Anaphora_Resolution",\n'
        '    "edge_target": "Voice_Modulation",\n'
        '    "new_guidance": "Verify turn-taking in rapid dialogue.",\n'
        '    "new_pitfalls": "Do not swap character speaker registers.",\n'
        '    "rationale": "Fix speaker attribution swap."\n'
        '  }\n'
        ']'
    )
    with patch("nousetsu.graph.pg_refiner.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=mock_edits_json)
        mock_get_llm.return_value = mock_llm

        # Run learn-graph for drafter (dry-run)
        cmd_learn_graph(argparse.Namespace(
            project_dir=str(tmp_path),
            folder=None,
            agent="drafter",
            max_traces=10,
            dry_run=True,
            model="mock-novel-llm"
        ))
        assert repo.load_procedural_graph("drafter") is None

        # Run learn-graph for drafter (live save)
        cmd_learn_graph(argparse.Namespace(
            project_dir=str(tmp_path),
            folder=None,
            agent="drafter",
            max_traces=10,
            dry_run=False,
            model="mock-novel-llm"
        ))
        evolved = repo.load_procedural_graph("drafter")
        assert evolved is not None
        matching_edge = next(e for e in evolved.edges if e.source == "Zero_Anaphora_Resolution" and e.target == "Voice_Modulation")
        assert matching_edge.guidance == "Verify turn-taking in rapid dialogue."
        assert matching_edge.pitfalls == "Do not swap character speaker registers."


def test_default_graphs_for_all_agents():
    """Verify default procedural graph creation, node count, and edge count for all 5 agents."""
    c_g = get_default_critic_graph()
    assert c_g.graph_id == "critic_default_v1"
    assert len(c_g.nodes) == 5
    assert len(c_g.edges) == 4
    c_guidance = c_g.to_compact_guidance("Audit_Init", max_hops=2)
    assert "Omission Verification" in c_guidance or "line-by-line alignment" in c_guidance
    assert len(c_guidance.split()) < 120

    p_g = get_default_polisher_graph()
    assert p_g.graph_id == "polisher_default_v1"
    assert len(p_g.nodes) == 5
    assert len(p_g.edges) == 4
    p_guidance = p_g.to_compact_guidance("Inspect_Critique", max_hops=2)
    assert "Title & Heading Lock" in p_guidance or "critique notes" in p_guidance
    assert len(p_guidance.split()) < 120

    chr_g = get_default_chronicler_graph()
    assert chr_g.graph_id == "chronicler_default_v1"
    assert len(chr_g.nodes) == 5
    assert len(chr_g.edges) == 4
    chr_guidance = chr_g.to_compact_guidance("Chapter_Deconstruction", max_hops=2)
    assert "State Shift Tracking" in chr_guidance or "plot developments" in chr_guidance
    assert len(chr_guidance.split()) < 120


def test_critic_polisher_chronicler_agent_procedural_graph_integration():
    """Verify CritiqueAgent, PolishingAgent, and ChroniclerAgent format and use procedural graphs."""
    bible = NovelBible(
        novel_title="Test Novel",
        source_language="Japanese",
        target_language="English",
        style_guide=StyleGuide()
    )

    critic = CritiqueAgent(model_name="mock-novel-llm")
    assert critic.procedural_graph is not None
    assert critic.procedural_graph.graph_id == "critic_default_v1"
    audit, notes = critic.evaluate(
        source_text="佐藤は剣を抜いた。「行くぞ！」",
        draft_text="Sato drew his sword. 'Let's go!'",
        bible=bible,
        active_characters=[],
        active_glossary=[]
    )
    assert audit.fidelity_score > 0

    polisher = PolishingAgent(model_name="mock-novel-llm")
    assert polisher.procedural_graph is not None
    assert polisher.procedural_graph.graph_id == "polisher_default_v1"
    polished = polisher.polish(
        draft_text="Sato drew his sword. 'Let's go!'",
        critique_notes="Smooth prose cadence.",
        active_glossary=[],
        bible=bible
    )
    assert len(polished) > 0

    chronicler = ChroniclerAgent(model_name="mock-novel-llm")
    assert chronicler.procedural_graph is not None
    assert chronicler.procedural_graph.graph_id == "chronicler_default_v1"
    summary = chronicler.chronicle(
        chapter_num=1,
        chapter_title="Chapter 1",
        translated_text="Sato drew his sword. 'Let's go!'",
        bible=bible
    )
    assert summary.chapter_num == 1


def test_workflow_wiring_all_procedural_graphs():
    """Verify NovelTranslationWorkflow forwards all procedural graphs to respective agents."""
    from nousetsu.graph.workflow import NovelTranslationWorkflow

    c_g = get_default_critic_graph()
    p_g = get_default_polisher_graph()
    chr_g = get_default_chronicler_graph()

    wf = NovelTranslationWorkflow(
        model_name="mock-novel-llm",
        critic_pg=c_g,
        polisher_pg=p_g,
        chronicler_pg=chr_g
    )
    assert wf.critic.procedural_graph == c_g
    assert wf.polisher.procedural_graph == p_g
    assert wf.chronicler.procedural_graph == chr_g



