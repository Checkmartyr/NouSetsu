"""Tests for Procedural Graph integration in Extractor and Drafter agents (arXiv:2609.09153v1)."""
import pytest
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.extractor import EntityExtractorAgent
from nousetsu.graph.pg_refiner import DiagnosticTrace, GraphEditOperation, ProceduralGraphRefiner
from nousetsu.graph.procedural import (
    ProceduralEdge,
    ProceduralGraph,
    ProceduralNode,
    ProceduralNodeType,
    ProceduralRelation,
    get_default_drafter_graph,
    get_default_extractor_graph,
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
