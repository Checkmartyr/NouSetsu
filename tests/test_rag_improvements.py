"""Unit tests for enhanced RAG query formulation, bilingual indexing, and reasoning retention."""
import pytest
from unittest.mock import MagicMock

from nousetsu.agents.chronicler import ChroniclerAgent
from nousetsu.agents.critic import CritiqueAgent
from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.models.state import TranslationState
from nousetsu.graph.workflow import NovelTranslationWorkflow
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible, ChapterSummary
from nousetsu.rag.engine import HybridSearchEngine
from nousetsu.rag.models import DocumentType, SearchResult
from nousetsu.rag.reranker import MockCrossEncoderReranker, LLMCrossEncoderReranker


def test_bilingual_query_generation_drafter():
    """Verify Drafter query builder combines English character names, aliases, and bilingual terms."""
    wf = NovelTranslationWorkflow(model_name="mock-model")
    bible = NovelBible(source_language="Japanese", target_language="English")
    state = TranslationState(
        chapter_num=5,
        chapter_id="0005",
        source_text="林枫站在紫霄宗的天台上。\n夜风呼啸。",
        novel_bible=bible,
        active_characters=[
            CharacterProfile(name="Lin Feng", original_name="林枫", aliases=["林枫", "Feng'er"])
        ],
        extracted_terms=[
            GlossaryItem(source="紫霄剑", target="Purple Cloud Sword", category="Weapon")
        ]
    )

    query = wf._build_drafter_rag_query(state)
    assert "Lin Feng" in query
    assert "林枫" in query
    assert "Purple Cloud Sword" in query
    assert "紫霄剑" in query


def test_critique_query_generation_clean():
    """Verify Critique query builder pairs bilingual terms and excludes noise keywords."""
    wf = NovelTranslationWorkflow(model_name="mock-model")
    bible = NovelBible(source_language="Japanese", target_language="English")
    state = TranslationState(
        chapter_num=7,
        chapter_id="0007",
        source_text="Text",
        novel_bible=bible,
        active_characters=[CharacterProfile(name="Elder Song", original_name="宋长老")],
        extracted_terms=[
            GlossaryItem(source="苍雷斩", target="Azure Thunder Slash", category="Technique")
        ]
    )

    query = wf._build_critique_rag_query(state)
    assert "Elder Song" in query
    assert "Azure Thunder Slash" in query
    assert "苍雷斩" in query
    # Ensure noise words are absent
    assert "dialogue style canonical translation" not in query


def test_chronicler_query_generation_ending_climax():
    """Verify Chronicler query builder targets final climax/resolution lines."""
    wf = NovelTranslationWorkflow(model_name="mock-model")
    bible = NovelBible(source_language="Japanese", target_language="English")
    state = TranslationState(
        chapter_num=10,
        chapter_id="0010",
        source_text="Raw source",
        novel_bible=bible,
        active_characters=[CharacterProfile(name="Lin Feng", original_name="林枫")]
    )
    final_text = "The morning started quietly.\nMidday battle raged.\nIn the end, Lin Feng successfully broke through to the Golden Core Realm!"

    query = wf._build_chronicler_rag_query(state, final_text)
    assert "Lin Feng" in query
    assert "broke through to the Golden Core Realm" in query


def test_mock_reranker_retains_reason():
    """Verify MockCrossEncoderReranker sets relevance_reason and metadata."""
    reranker = MockCrossEncoderReranker()
    doc = SearchResult(
        doc_id="test:1",
        doc_type=DocumentType.CHUNK,
        content="Lin Feng retrieved the Azure Thunder Blade from the vault.",
        title="Vault Scene",
        rrf_score=0.03
    )
    results = reranker.rerank(query="Lin Feng Azure Thunder Blade", documents=[doc], top_k=1)
    assert len(results) == 1
    assert results[0].relevance_reason is not None
    assert "Lexical overlap" in results[0].relevance_reason
    assert results[0].metadata.get("reason") == results[0].relevance_reason


def test_llm_reranker_retains_reason():
    """Verify LLMCrossEncoderReranker captures reasoning from LLM output."""
    reranker = LLMCrossEncoderReranker(model_name="mock-model")
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '[{"doc_id": "test:2", "score": 0.95, "reason": "Explicit continuity of the demonic seal oath"}]'
    mock_llm.invoke.return_value = mock_response
    reranker.llm = mock_llm

    doc = SearchResult(
        doc_id="test:2",
        doc_type=DocumentType.SUMMARY,
        content="The seal was set.",
        title="Oath Chapter",
        rrf_score=0.02
    )
    results = reranker.rerank(query="demonic seal oath", documents=[doc], top_k=1)
    assert len(results) == 1
    assert results[0].relevance_reason == "Explicit continuity of the demonic seal oath"
    assert results[0].metadata.get("reason") == "Explicit continuity of the demonic seal oath"


def test_bilingual_indexing_in_workflow():
    """Verify _index_chapter_into_rag indexes bilingual tags into summary and metadata."""
    engine = HybridSearchEngine(":memory:")
    wf = NovelTranslationWorkflow(model_name="mock-model")
    wf.rag_engine = engine

    summary = ChapterSummary(
        chapter_num=3,
        synopsis="A duel occurs at the peak.",
        key_events=["Lin Feng defeats Zhang San."],
        character_state_changes=["Lin Feng reaches Core Realm."]
    )

    bible = NovelBible(source_language="Chinese", target_language="English")
    state = TranslationState(
        chapter_num=3,
        chapter_id="0003",
        source_text="...",
        novel_bible=bible,
        active_characters=[CharacterProfile(name="Lin Feng", original_name="林枫", aliases=["林枫"])],
        extracted_terms=[GlossaryItem(source="紫霄剑", target="Purple Cloud Sword", category="Weapon")]
    )

    wf._index_chapter_into_rag(
        chapter_num=3,
        folder="Vol_01",
        title="Chapter 3",
        summary=summary,
        final_text="Line 1\nLine 2",
        state=state
    )

    # Verify document stored in SQLite
    doc = engine.get_document("summary:Vol_01:0003")
    assert doc is not None
    assert "Entities:" in doc.content
    assert "Lin Feng (林枫)" in doc.content
    assert "紫霄剑:Purple Cloud Sword" in doc.content
    assert doc.metadata.get("characters") == ["Lin Feng"]
    assert doc.metadata.get("terms") == {"紫霄剑": "Purple Cloud Sword"}


def test_drafter_prompt_formatting_with_reason():
    """Verify Drafter format_summaries includes Context reason."""
    drafter = ContextAwareDrafterAgent(model_name="mock-model")
    hit = SearchResult(
        doc_id="chunk:001",
        doc_type=DocumentType.CHUNK,
        chapter_num=1,
        title="Encounter",
        content="He unsheathed the blade with a cold smile.",
        relevance_reason="First naming of the demon blade"
    )
    formatted = drafter.format_summaries(
        rolling_summaries=[],
        limit=2,
        rag_results=[hit]
    )
    assert "### 4. Relevant Historical Lore & Past Canon" in formatted
    assert "[Context: First naming of the demon blade]" in formatted
