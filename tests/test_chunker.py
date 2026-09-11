"""Unit tests for LineSemanticChunker utility."""

import pytest
from nousetsu.utils.chunker import LineSemanticChunker, LineChunk, extract_tail_lines


def test_should_chunk_threshold():
    chunker = LineSemanticChunker(threshold_lines=5, target_chunk_lines=3)
    short_text = "Line 1\nLine 2\nLine 3\n"
    assert not chunker.should_chunk(short_text)

    long_text = "\n".join([f"Line {i}" for i in range(1, 10)])
    assert chunker.should_chunk(long_text)


def test_split_lines_single_chunk_when_below_threshold():
    chunker = LineSemanticChunker(threshold_lines=10, target_chunk_lines=5)
    text = "Line 1\nLine 2\nLine 3\n"
    chunks = chunker.split_lines(text)
    assert len(chunks) == 1
    assert chunks[0].content == text
    assert chunks[0].chunk_index == 1
    assert chunks[0].total_chunks == 1


def test_split_lines_splits_and_preserves_content():
    # 20 lines with target 8 lines per chunk
    lines = [f"This is sentence line {i}." for i in range(1, 21)]
    text = "\n".join(lines) + "\n"
    
    chunker = LineSemanticChunker(threshold_lines=10, target_chunk_lines=8, boundary_window=3)
    chunks = chunker.split_lines(text)
    
    assert len(chunks) >= 2
    # The concatenated content must match original text character-for-character
    reassembled = "".join(c.content for c in chunks)
    assert reassembled == text


def test_split_prefers_scene_breaks():
    lines = [f"Narrative line {i}." for i in range(1, 10)]
    lines.append("***")  # Scene break at line 10
    lines.extend([f"Second scene line {i}." for i in range(11, 22)])
    text = "\n".join(lines) + "\n"

    chunker = LineSemanticChunker(threshold_lines=10, target_chunk_lines=9, boundary_window=4)
    chunks = chunker.split_lines(text)
    assert len(chunks) >= 2

    # Chunk 1 should end right at or after the scene break line
    assert "***" in chunks[0].content or "***" in chunks[1].content


def test_extract_tail_lines():
    text = "First paragraph\nSecond paragraph\nThird paragraph\nFourth paragraph\n"
    tail = extract_tail_lines(text, line_count=2)
    assert tail == "Third paragraph\nFourth paragraph"

    short = "Only one line"
    assert extract_tail_lines(short, line_count=3) == "Only one line"


def test_quote_safety_does_not_split_inside_open_quotes():
    lines = [f"Narrative line {i}." for i in range(1, 8)]
    lines.append("「This is an open dialogue quote that")
    lines.append("spans across multiple lines and")
    lines.append("should not be severed in the middle.」")
    lines.extend([f"After quote line {i}." for i in range(1, 10)])
    text = "\n".join(lines) + "\n"

    chunker = LineSemanticChunker(threshold_lines=10, target_chunk_lines=8, boundary_window=3)
    chunks = chunker.split_lines(text)
    assert len(chunks) >= 2

    # Check that neither chunk has an unclosed 「 without a matching 」
    for c in chunks:
        open_count = c.content.count("「")
        close_count = c.content.count("」")
        assert open_count == close_count
