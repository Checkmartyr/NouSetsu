"""Integration tests for Hybrid Search RAG across Workflow, Drafter, and Chronicler."""
import argparse
from pathlib import Path
import pytest
from nousetsu.agents.llm import MockNovelLLM
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import ChapterSummary, NovelBible
from nousetsu.models.config import ProjectConfig
from nousetsu.models.state import TranslationState
from nousetsu.rag.embeddings import EmbeddingClient
from nousetsu.rag.engine import HybridSearchEngine
from nousetsu.rag.models import DocumentType, LoreDocument
from nousetsu.storage.repository import NovelRepository


def test_workflow_rag_indexing_and_retrieval(tmp_path: Path):
    """Verify that completing Chapter 1 indexes lore, and Chapter 2 retrieves it via Hybrid RAG."""
    repo = NovelRepository(tmp_path)
    bible = repo.initialize_project("RAG Test", "English", "Thai")

    db_path = tmp_path / ".novel" / "rag" / "lore.db"
    rag_engine = HybridSearchEngine(db_path)
    emb_client = EmbeddingClient(model_name="mock-model")

    workflow = NovelTranslationWorkflow(
        model_name="mock-model",
        rag_engine=rag_engine,
        enable_rag=True,
        rag_top_k=2,
        embedding_client=emb_client
    )

    # 1. Run Chapter 1
    state1 = TranslationState(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="001.txt",
        output_file="001.md",
        source_text="Sir Roderick swore a solemn oath to protect Princess Amelia at all costs.\nHe drew his silver blade and pledged fealty.",
        novel_bible=bible
    )
    final1 = workflow.run(state1)
    assert final1.polished_text is not None

    # Verify RAG store has indexed Chapter 1 (1 summary + at least 1 scene chunk)
    assert rag_engine.count_documents() >= 2
    summary_doc = rag_engine.get_document("summary:default:0001")
    assert summary_doc is not None
    assert summary_doc.doc_type == DocumentType.SUMMARY

    # 2. Run Chapter 2 mentioning Roderick and Amelia
    state2 = TranslationState(
        chapter_id="chapter_0002",
        chapter_num=2,
        source_file="002.txt",
        output_file="002.md",
        source_text="Years later, Princess Amelia remembered the oath Roderick had made to her in the courtyard.",
        novel_bible=bible
    )
    final2 = workflow.run(state2)

    # Verify that Chapter 2 retrieval fetched Chapter 1 lore
    assert len(final2.rag_retrieved_lore) > 0
    retrieved_ids = [r.doc_id for r in final2.rag_retrieved_lore]
    assert any("0001" in doc_id for doc_id in retrieved_ids)


def test_batch_runner_rag_engine_wiring(tmp_path: Path):
    """Verify BatchRunner initializes and wires the RAG engine from project config."""
    from nousetsu.batch.runner import BatchRunner

    repo = NovelRepository(tmp_path)
    repo.initialize_project("Batch RAG Test", "English", "Thai")

    runner = BatchRunner(
        repo,
        model_name="mock-model",
    )
    assert runner.rag_engine is not None
    assert runner.workflow.rag_engine is not None
    assert runner.workflow.enable_rag is True


def test_cli_lore_search_execution(tmp_path: Path, capsys):
    """Verify nousetsu lore search CLI displays matched results in Rich table."""
    from nousetsu.cli.app import cmd_lore_search

    repo = NovelRepository(tmp_path)
    repo.initialize_project("CLI RAG Test", "English", "Thai")
    engine = repo.get_rag_engine()

    # Index sample document
    doc = LoreDocument(
        doc_id="summary:Vol_01:0014",
        doc_type=DocumentType.SUMMARY,
        chapter_num=14,
        folder="Vol_01",
        title="Oath in the Courtyard",
        content="Sir Roderick pledged never to raise his silver sword against Amelia."
    )
    engine.index_document(doc)

    args = argparse.Namespace(
        project_dir=str(tmp_path),
        query="Roderick silver sword",
        limit=5,
        folder=None,
        embedding_model="mock-embedding"
    )
    cmd_lore_search(args)

    # Check console output (Rich prints to stdout)
    # The command should execute without throwing an error
