"""Unit tests for RAG temporal boundary, multi-volume scoping, and doc_type exclusions."""
from pathlib import Path
import pytest

from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import ChapterSummary, NovelBible
from nousetsu.rag.engine import HybridSearchEngine
from nousetsu.rag.models import DocumentType, LoreDocument


def test_temporal_filter_sparse_max_chapter(tmp_path: Path):
    """Verify search_sparse excludes chapters >= max_chapter_num within the current folder."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    docs = [
        LoreDocument(doc_id="d1", doc_type=DocumentType.CHUNK, chapter_num=1, folder="Vol_01", content="Hero arrives at academy"),
        LoreDocument(doc_id="d2", doc_type=DocumentType.CHUNK, chapter_num=4, folder="Vol_01", content="Hero meets teacher at academy"),
        LoreDocument(doc_id="d3", doc_type=DocumentType.CHUNK, chapter_num=5, folder="Vol_01", content="Hero faces duel at academy"),
        LoreDocument(doc_id="d4", doc_type=DocumentType.CHUNK, chapter_num=10, folder="Vol_01", content="Hero graduates from academy"),
    ]
    engine.index_documents(docs)

    # When translating chapter 5 of Vol_01, max_chapter_num is 5
    results = engine.search_sparse(
        query="academy",
        current_folder="Vol_01",
        allowed_folders=["Vol_01"],
        max_chapter_num=5
    )
    returned_ids = [doc.doc_id for doc, _, _ in results]
    assert "d1" in returned_ids
    assert "d2" in returned_ids
    assert "d3" not in returned_ids  # Chapter 5 must be excluded
    assert "d4" not in returned_ids  # Chapter 10 must be excluded


def test_temporal_filter_future_volumes_exclusion(tmp_path: Path):
    """Verify search_sparse excludes future volumes while retaining prior volumes and current volume past chapters."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    docs = [
        # Prior volume (Vol_01): all chapters are valid historical lore
        LoreDocument(doc_id="v1_ch10", doc_type=DocumentType.CHUNK, chapter_num=10, folder="Vol_01", content="Claire royal banquet celebration"),
        # Current volume (Vol_02): only chapters < 5 are valid
        LoreDocument(doc_id="v2_ch2", doc_type=DocumentType.CHUNK, chapter_num=2, folder="Vol_02", content="Claire tea party celebration"),
        LoreDocument(doc_id="v2_ch5", doc_type=DocumentType.CHUNK, chapter_num=5, folder="Vol_02", content="Claire duel celebration"),
        # Future volume (Vol_03): must be completely excluded
        LoreDocument(doc_id="v3_ch1", doc_type=DocumentType.CHUNK, chapter_num=1, folder="Vol_03", content="Claire future coronation celebration"),
    ]
    engine.index_documents(docs)

    results = engine.search_sparse(
        query="celebration",
        current_folder="Vol_02",
        allowed_folders=["Vol_01", "Vol_02"],
        max_chapter_num=5
    )
    returned_ids = [doc.doc_id for doc, _, _ in results]
    assert "v1_ch10" in returned_ids
    assert "v2_ch2" in returned_ids
    assert "v2_ch5" not in returned_ids
    assert "v3_ch1" not in returned_ids


def test_excluded_doc_types(tmp_path: Path):
    """Verify excluded_doc_types filters out static character cards and glossary items."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    docs = [
        LoreDocument(doc_id="char_amelia", doc_type=DocumentType.CHARACTER, chapter_num=0, folder="Vol_01", content="Amelia character card profile"),
        LoreDocument(doc_id="gloss_sword", doc_type=DocumentType.GLOSSARY, chapter_num=0, folder="Vol_01", content="Amelia magic sword glossary term"),
        LoreDocument(doc_id="scene_past", doc_type=DocumentType.CHUNK, chapter_num=2, folder="Vol_01", content="Amelia scene discussion in garden"),
        LoreDocument(doc_id="summary_past", doc_type=DocumentType.SUMMARY, chapter_num=3, folder="Vol_01", content="Amelia summary of chapter 3"),
    ]
    engine.index_documents(docs)

    results = engine.search_sparse(
        query="Amelia",
        current_folder="Vol_01",
        allowed_folders=["Vol_01"],
        max_chapter_num=5,
        excluded_doc_types=[DocumentType.CHARACTER, DocumentType.GLOSSARY]
    )
    returned_ids = [doc.doc_id for doc, _, _ in results]
    assert "scene_past" in returned_ids
    assert "summary_past" in returned_ids
    assert "char_amelia" not in returned_ids
    assert "gloss_sword" not in returned_ids


def test_dense_temporal_and_type_filters(tmp_path: Path):
    """Verify search_dense respects max_chapter_num, volume boundaries, and excluded_doc_types."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    v = [1.0, 0.0, 0.0]
    docs = [
        LoreDocument(doc_id="d1", doc_type=DocumentType.CHUNK, chapter_num=1, folder="Vol_01", content="Combat scene 1"),
        LoreDocument(doc_id="d5", doc_type=DocumentType.CHUNK, chapter_num=5, folder="Vol_01", content="Combat scene 5"),
        LoreDocument(doc_id="d_future", doc_type=DocumentType.CHUNK, chapter_num=2, folder="Vol_02", content="Combat scene in Vol 2"),
        LoreDocument(doc_id="d_char", doc_type=DocumentType.CHARACTER, chapter_num=0, folder="Vol_01", content="Combat instructor card"),
    ]
    engine.index_documents(docs, [v, v, v, v])

    hits = engine.search_dense(
        query_vector=[0.99, 0.01, 0.0],
        limit=10,
        current_folder="Vol_01",
        allowed_folders=["Vol_01"],
        max_chapter_num=5,
        excluded_doc_types=[DocumentType.CHARACTER]
    )
    returned_ids = [doc.doc_id for doc, _, _ in hits]
    assert returned_ids == ["d1"]


def test_hybrid_search_with_temporal_filters(tmp_path: Path):
    """Verify hybrid_search combines filtered sparse and dense hits without leakage."""
    db_path = tmp_path / "lore.db"
    engine = HybridSearchEngine(db_path)

    v = [0.8, 0.6, 0.0]
    docs = [
        LoreDocument(doc_id="past_scene", doc_type=DocumentType.CHUNK, chapter_num=3, folder="Vol_01", content="Secret meeting in garden"),
        LoreDocument(doc_id="future_scene", doc_type=DocumentType.CHUNK, chapter_num=8, folder="Vol_01", content="Secret garden reveal"),
        LoreDocument(doc_id="char_card", doc_type=DocumentType.CHARACTER, chapter_num=0, folder="Vol_01", content="Secret garden keeper card"),
    ]
    engine.index_documents(docs, [v, v, v])

    hybrid_hits = engine.hybrid_search(
        query="Secret garden",
        query_vector=[0.8, 0.6, 0.0],
        limit=5,
        current_folder="Vol_01",
        allowed_folders=["Vol_01"],
        max_chapter_num=5,
        excluded_doc_types=[DocumentType.CHARACTER, DocumentType.GLOSSARY],
        enable_rerank=False
    )
    assert len(hybrid_hits) == 1
    assert hybrid_hits[0].doc_id == "past_scene"


def test_workflow_allowed_folders_helper():
    """Verify NovelTranslationWorkflow._get_allowed_folders derives volume chronological progression correctly."""
    wf = NovelTranslationWorkflow(model_name="mock-model")
    bible = NovelBible()
    bible.summaries = [
        ChapterSummary(chapter_num=1, synopsis="V4 Ch1", folder="Villainess_04"),
        ChapterSummary(chapter_num=1, synopsis="V5 Ch1", folder="Villainess_05"),
        ChapterSummary(chapter_num=1, synopsis="V6 Ch1", folder="Villainess_06"),
    ]

    # When translating Villainess_05, only Villainess_04 and Villainess_05 should be allowed
    allowed = wf._get_allowed_folders(bible, "Villainess_05")
    assert allowed == ["Villainess_04", "Villainess_05"]

    # When translating Villainess_04, only Villainess_04 should be allowed
    allowed_v4 = wf._get_allowed_folders(bible, "Villainess_04")
    assert allowed_v4 == ["Villainess_04"]

    # When current_folder is None
    assert wf._get_allowed_folders(bible, None) is None


def test_rag_provenance_trace_recording(tmp_path: Path):
    """Verify Drafter records RAG provenance into prompt trace metadata."""
    from nousetsu.agents.drafter import ContextAwareDrafterAgent
    from nousetsu.analysis.tracker import PromptTracker
    from nousetsu.rag.models import SearchResult

    traces_dir = tmp_path / ".novel" / "traces"
    tracker = PromptTracker(traces_dir, chapter_id="ch_01", chapter_num=1, folder="Vol_01")

    drafter = ContextAwareDrafterAgent(model_name="mock-model")
    bible = NovelBible()

    hit = SearchResult(
        doc_id="summary:Vol_01:001",
        doc_type=DocumentType.SUMMARY,
        chapter_num=1,
        folder="Vol_01",
        title="Arrival",
        content="Rei arrived at school.",
        rrf_score=0.032145
    )

    drafter.draft(
        source_text="Test source text line one.",
        bible=bible,
        active_characters=[],
        active_glossary=[],
        rolling_summaries=[],
        rag_results=[hit],
        prompt_tracker=tracker
    )

    assert len(tracker.traces) == 1
    trace = tracker.traces[0]
    assert "rag_hits" in trace.metadata
    assert len(trace.metadata["rag_hits"]) == 1
    hit_meta = trace.metadata["rag_hits"][0]
    assert hit_meta["doc_id"] == "summary:Vol_01:001"
    assert hit_meta["title"] == "Arrival"
    assert hit_meta["rrf_score"] == 0.032145
    assert hit_meta["doc_type"] == "summary"
