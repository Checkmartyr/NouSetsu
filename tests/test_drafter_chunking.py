"""Unit tests for chunked drafting and token usage aggregation."""

from nousetsu.agents.drafter import ContextAwareDrafterAgent
from nousetsu.agents.llm import MockNovelLLM
from nousetsu.models.bible import CharacterProfile, GlossaryItem, NovelBible, StyleGuide
from nousetsu.utils.chunker import LineChunk, LineSemanticChunker


def test_drafter_draft_chunked_accumulates_tokens_and_joins_output():
    drafter = ContextAwareDrafterAgent(model_name="mock-novel-llm")
    bible = NovelBible(
        title="Test Novel",
        source_language="Japanese",
        target_language="English",
        style_guide=StyleGuide()
    )

    chunks = [
        LineChunk(chunk_index=1, total_chunks=2, start_line=1, end_line=3, content="Line 1\nLine 2\nLine 3\n"),
        LineChunk(chunk_index=2, total_chunks=2, start_line=4, end_line=6, content="Line 4\nLine 5\nLine 6\n"),
    ]

    result = drafter.draft(
        source_text="Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\n",
        bible=bible,
        active_characters=[],
        active_glossary=[],
        rolling_summaries=[],
        chunks=chunks
    )

    assert result is not None
    assert len(result) > 0
    # Usage should accumulate across both chunks
    assert drafter.last_usage.total_tokens > 0
    # Each mock call produces 22 tokens (10 in + 10 out + 2 thought)
    # With 2 chunks, total should be at least 44
    assert drafter.last_usage.total_tokens >= 40
