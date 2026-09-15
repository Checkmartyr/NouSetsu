"""Tests for ChroniclerAgent bi-directional RAG integration."""
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import CharacterProfile, NovelBible
from nousetsu.models.state import TranslationState
from nousetsu.rag.embeddings import EmbeddingClient
from nousetsu.rag.engine import HybridSearchEngine
from nousetsu.rag.models import DocumentType, LoreDocument, SearchResult


def test_chronicler_agent_with_rag_context():
    """Verify ChroniclerAgent injects prior RAG lore into the system prompt."""
    agent = ChroniclerAgent(model_name="mock-model")

    mock_hits = [
        SearchResult(
            doc_id="summary:default:0001",
            doc_type=DocumentType.SUMMARY,
            title="Chapter 1 Summary",
            content="Amelia was poisoned by Duke Vance with Black Lotus venom. Lost sword arm.",
            rrf_score=0.95
        ),
        SearchResult(
            doc_id="char:amelia",
            doc_type=DocumentType.CHARACTER,
            title="Amelia Barlen",
            content="Former crown princess, currently exiled.",
            rrf_score=0.88
        )
    ]

    captured_messages = []
    def fake_invoke(messages):
        captured_messages.extend(messages)
        return MagicMock(content='{"chapter_num": 2, "title": "Chapter 2", "synopsis": "Amelia fought back.", "key_events": ["Battle won"], "character_state_changes": ["Amelia recovered from venom"]}')

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke
    agent.llm = mock_llm

    summary = agent.chronicle(
        chapter_num=2,
        chapter_title="Chapter 2",
        translated_text="Amelia stood tall despite her lingering pain from the Black Lotus.",
        rag_context=mock_hits
    )

    assert summary.synopsis == "Amelia fought back."
    assert len(captured_messages) == 2
    sys_prompt = captured_messages[0].content
    assert "Prior Series Lore & Character Memory (via RAG):" in sys_prompt
    assert "[Chapter 1 Summary]: Amelia was poisoned by Duke Vance with Black Lotus venom" in sys_prompt
    assert "[Amelia Barlen]: Former crown princess" in sys_prompt


def test_chronicler_agent_without_rag_context():
    """Verify ChroniclerAgent behaves normally without rag_context (backward compatibility)."""
    agent = ChroniclerAgent(model_name="mock-model")

    captured_messages = []
    def fake_invoke(messages):
        captured_messages.extend(messages)
        return MagicMock(content='{"chapter_num": 1, "title": "Chapter 1", "synopsis": "Initial peace.", "key_events": ["Ceremony completed"], "character_state_changes": []}')

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke
    agent.llm = mock_llm

    summary = agent.chronicle(
        chapter_num=1,
        chapter_title="Chapter 1",
        translated_text="The kingdom was at peace.",
        rag_context=None
    )

    assert summary.synopsis == "Initial peace."
    sys_prompt = captured_messages[0].content
    assert "Prior Series Lore & Character Memory (via RAG):" not in sys_prompt


def test_workflow_passes_rag_to_chronicler(tmp_path: Path):
    """Verify that workflow passes retrieved RAG context to Chronicler during chronicling stage."""
    from nousetsu.storage.repository import NovelRepository

    repo = NovelRepository(tmp_path)
    bible = repo.initialize_project("Chronicler RAG Test", "English", "Thai")
    bible.characters.append(CharacterProfile(name="Roderick", original_name="Roderick"))

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

    # Pre-seed RAG engine with historical character document
    docs = [
        LoreDocument(
            doc_id="char:roderick",
            doc_type=DocumentType.CHARACTER,
            title="Sir Roderick",
            content="Sir Roderick swore an oath. Currently wounded knight."
        )
    ]
    embs = emb_client.embed_documents([d.content for d in docs])
    rag_engine.index_documents(docs, embs)

    passed_rag_context = []
    original_chronicle = workflow.chronicler.chronicle

    def spy_chronicle(*args, **kwargs):
        passed_rag_context.append(kwargs.get("rag_context"))
        return original_chronicle(*args, **kwargs)

    workflow.chronicler.chronicle = spy_chronicle

    state = TranslationState(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="001.txt",
        output_file="001.md",
        source_text="Sir Roderick and Princess Amelia fought together in the courtyard.\nThey drew their swords side by side.",
        novel_bible=bible
    )
    final_state = workflow.run(state)

    assert len(passed_rag_context) == 1
    # Check that chronicler received RAG hits
    rag_hits = passed_rag_context[0]
    assert rag_hits is not None
    assert len(rag_hits) > 0
    assert any("roderick" in hit.doc_id for hit in rag_hits)
