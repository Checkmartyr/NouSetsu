"""Tests for CritiqueAgent canonical RAG translation memory integration."""
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from nousetsu.agents.critic import CritiqueAgent
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import CharacterProfile, NovelBible
from nousetsu.models.state import TranslationState
from nousetsu.rag.embeddings import EmbeddingClient
from nousetsu.rag.engine import HybridSearchEngine
from nousetsu.rag.models import DocumentType, LoreDocument, SearchResult


def test_critic_agent_with_rag_context():
    """Verify CritiqueAgent formats canonical RAG context into its evaluation prompt."""
    agent = CritiqueAgent(model_name="mock-model")

    mock_hits = [
        SearchResult(
            doc_id="chunk:default:0001:001",
            doc_type=DocumentType.CHUNK,
            title="Chapter 1 Scene",
            content="Princess Amelia addressed Duke Vance coldly: 'Your treachery ends today.'",
            rrf_score=0.92
        ),
        SearchResult(
            doc_id="char:amelia",
            doc_type=DocumentType.CHARACTER,
            title="Princess Amelia",
            content="Speaks with sharp aristocratic dignity and formal register.",
            rrf_score=0.85
        )
    ]

    captured_messages = []
    def fake_invoke(messages):
        captured_messages.extend(messages)
        return MagicMock(content='{"fidelity_score": 9.2, "style_score": 9.0, "glossary_compliance_pct": 100.0, "warnings": [], "critique_notes": "Good terminology consistency."}')

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke
    agent.llm = mock_llm

    bible = NovelBible(source_language="English", target_language="Thai")
    audit, notes = agent.evaluate(
        source_text="Princess Amelia confronted Duke Vance in the hall.",
        draft_text="เจ้าหญิงอเมเลียเผชิญหน้ากับดยุกแวนซ์ในห้องโถง",
        bible=bible,
        active_characters=[CharacterProfile(name="Amelia", original_name="Amelia")],
        active_glossary=[],
        rag_context=mock_hits
    )

    assert audit.fidelity_score == 9.2
    assert len(captured_messages) == 2
    sys_prompt = captured_messages[0].content
    assert "Canonical Series Memory & Prior Translations (via RAG):" in sys_prompt
    assert "[Chapter 1 Scene]: Princess Amelia addressed Duke Vance coldly" in sys_prompt
    assert "[Princess Amelia]: Speaks with sharp aristocratic dignity" in sys_prompt


def test_critic_agent_without_rag_context():
    """Verify CritiqueAgent behaves normally without rag_context (backward compatibility)."""
    agent = CritiqueAgent(model_name="mock-model")

    captured_messages = []
    def fake_invoke(messages):
        captured_messages.extend(messages)
        return MagicMock(content='{"fidelity_score": 9.5, "style_score": 9.2, "glossary_compliance_pct": 100.0, "warnings": [], "critique_notes": "Clean prose."}')

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke
    agent.llm = mock_llm

    bible = NovelBible(source_language="English", target_language="Thai")
    audit, notes = agent.evaluate(
        source_text="The sunlight filtered through the grand stained glass windows.",
        draft_text="แสงแดดส่องผ่านหน้าต่างกระจกสีอันวิจิตรงดงาม",
        bible=bible,
        active_characters=[],
        active_glossary=[],
        rag_context=None
    )

    assert audit.fidelity_score == 9.5
    sys_prompt = captured_messages[0].content
    assert "Canonical Series Memory & Prior Translations (via RAG):" not in sys_prompt


def test_workflow_passes_rag_to_critic(tmp_path: Path):
    """Verify that workflow passes retrieved canonical RAG context to Critic during critique step."""
    from nousetsu.storage.repository import NovelRepository

    repo = NovelRepository(tmp_path)
    bible = repo.initialize_project("Critic RAG Test", "English", "Thai")
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

    # Pre-seed RAG engine with historical character translation snippet
    docs = [
        LoreDocument(
            doc_id="char:roderick",
            doc_type=DocumentType.CHARACTER,
            title="Sir Roderick Translation",
            content="Sir Roderick dialogue style canonical translation pledged fealty with solemn oath."
        )
    ]
    embs = emb_client.embed_documents([d.content for d in docs])
    rag_engine.index_documents(docs, embs)

    passed_rag_context = []
    original_evaluate = workflow.critic.evaluate

    def spy_evaluate(*args, **kwargs):
        passed_rag_context.append(kwargs.get("rag_context"))
        return original_evaluate(*args, **kwargs)

    workflow.critic.evaluate = spy_evaluate

    state = TranslationState(
        chapter_id="chapter_0001",
        chapter_num=1,
        source_file="001.txt",
        output_file="001.md",
        source_text="Sir Roderick entered the hall and knelt before Princess Amelia.",
        novel_bible=bible
    )
    final_state = workflow.run(state)

    assert len(passed_rag_context) >= 1
    crit_rag_hits = passed_rag_context[0]
    assert crit_rag_hits is not None
    assert len(crit_rag_hits) > 0
    assert any("roderick" in (hit.doc_id + hit.title).lower() for hit in crit_rag_hits)
