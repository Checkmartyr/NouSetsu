"""Line-based semantic text chunking for document-level novel translation."""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LineChunk:
    """Represents a chunk of novel text partitioned along line boundaries."""
    chunk_index: int
    total_chunks: int
    start_line: int
    end_line: int
    content: str
    preceding_context_lines: str = ""
    source_content: Optional[str] = None


class LineSemanticChunker:
    """
    Splits novel text into chunks based on line count and literary boundaries.
    
    Protects against:
    1. Splitting in the middle of a sentence or dialogue line.
    2. Splitting inside open multi-line quotes (e.g. 「...」, 『...』, "...").
    3. TPM rate-limit spikes by keeping individual chunks under token limits.
    """

    # Typical novel scene break patterns
    SCENE_BREAK_PATTERN = re.compile(
        r"^\s*(?:\*{3,}|-{3,}|#{2,}|={3,}|_{3,}|[◆◇■□▲△●○★☆]{3,}|第[0-9一二三四五六七八九十百]+[節章幕話])\s*$"
    )

    # Japanese and Western opening/closing quotes
    OPEN_QUOTES = ("「", "『", "“", "‘", "《", "〈", "【")
    CLOSE_QUOTES = ("」", "』", "”", "’", "》", "〉", "】")

    def __init__(
        self,
        threshold_lines: int = 100,
        target_chunk_lines: int = 70,
        overlap_lines: int = 3,
        boundary_window: int = 12
    ):
        self.threshold_lines = threshold_lines
        self.target_chunk_lines = target_chunk_lines
        self.overlap_lines = overlap_lines
        self.boundary_window = boundary_window

    def should_chunk(self, text: str) -> bool:
        """Determines if text has enough content lines to warrant chunking."""
        if not text or not text.strip():
            return False
        content_lines = [l for l in text.splitlines() if l.strip()]
        return len(content_lines) > self.threshold_lines

    def split_lines(self, text: str) -> List[LineChunk]:
        """
        Splits text into LineChunks along natural literary boundaries.
        If text <= threshold_lines, returns a single chunk containing the full text.
        """
        if not text or not text.strip():
            return [LineChunk(chunk_index=1, total_chunks=1, start_line=1, end_line=1, content=text)]

        raw_lines = text.splitlines(keepends=True)
        total_raw_lines = len(raw_lines)

        if not self.should_chunk(text):
            return [
                LineChunk(
                    chunk_index=1,
                    total_chunks=1,
                    start_line=1,
                    end_line=total_raw_lines,
                    content=text
                )
            ]

        # Plan split boundary line indices (0-indexed in raw_lines)
        split_points = self._compute_split_points(raw_lines)
        
        chunks: List[LineChunk] = []
        num_chunks = len(split_points) + 1
        start_idx = 0

        for i, split_idx in enumerate(split_points, start=1):
            chunk_content = "".join(raw_lines[start_idx:split_idx])
            chunks.append(
                LineChunk(
                    chunk_index=i,
                    total_chunks=num_chunks,
                    start_line=start_idx + 1,
                    end_line=split_idx,
                    content=chunk_content
                )
            )
            start_idx = split_idx

        # Final chunk
        final_content = "".join(raw_lines[start_idx:])
        chunks.append(
            LineChunk(
                chunk_index=num_chunks,
                total_chunks=num_chunks,
                start_line=start_idx + 1,
                end_line=total_raw_lines,
                content=final_content
            )
        )

        return chunks

    def _compute_split_points(self, lines: List[str]) -> List[int]:
        """Calculates optimal split line indices based on boundaries."""
        total = len(lines)
        split_points: List[int] = []
        current_start = 0

        while True:
            target_idx = current_start + self.target_chunk_lines
            remaining_lines = total - target_idx

            # If remaining lines are fewer than half a chunk, stop to avoid tiny trailing chunks
            min_trailing = max(3, min(10, self.target_chunk_lines // 2))
            if remaining_lines < min_trailing:
                break

            # Search within window [target_idx - boundary_window, target_idx + boundary_window]
            min_search = max(current_start + 3, target_idx - self.boundary_window)
            max_search = min(total - 3, target_idx + self.boundary_window)

            best_idx = self._find_best_split(lines, min_search, max_search, target_idx)
            if best_idx <= current_start:
                best_idx = target_idx
            split_points.append(best_idx)
            current_start = best_idx

        return split_points

    def _find_best_split(
        self,
        lines: List[str],
        min_idx: int,
        max_idx: int,
        preferred_idx: int
    ) -> int:
        """
        Evaluates lines in search range and picks the best literary split boundary:
        1. Scene break markers (score 100)
        2. Blank/empty lines (score 80)
        3. Lines ending with closing quote or punctuation (score 60)
        Avoids splitting inside open multi-line quotes (score -50).
        """
        best_score = -9999.0
        best_idx = preferred_idx

        quote_depth = 0
        in_dq = False
        for i in range(min_idx):
            d, in_dq = self._quote_delta(lines[i], in_dq)
            quote_depth = max(0, quote_depth + d)

        for idx in range(min_idx, max_idx + 1):
            if idx > min_idx:
                d, in_dq = self._quote_delta(lines[idx - 1], in_dq)
                quote_depth = max(0, quote_depth + d)
            
            line = lines[idx - 1] if idx - 1 < len(lines) else ""
            next_line = lines[idx] if idx < len(lines) else ""

            # Base score penalizes distance from preferred target
            dist = abs(idx - preferred_idx)
            score = -dist * 1.5

            # Penalty for being inside open quote
            if quote_depth > 0 or in_dq:
                score -= 50.0

            # Priority 1: Scene break line
            if self.SCENE_BREAK_PATTERN.match(line) or self.SCENE_BREAK_PATTERN.match(next_line):
                score += 100.0
            # Priority 2: Empty / whitespace line
            elif not line.strip() or not next_line.strip():
                score += 80.0
            # Priority 3: Line ends with closing quote or terminal punctuation
            elif line.rstrip().endswith(self.CLOSE_QUOTES) or line.rstrip().endswith(('。', '.', '！', '!', '？', '?')):
                score += 60.0

            if score > best_score:
                best_score = score
                best_idx = idx

        return best_idx

    def _quote_delta(self, line: str, in_double_quote: bool = False) -> tuple[int, bool]:
        """Returns the net change in quote nesting for a line and the updated double-quote state."""
        delta = 0
        in_dq = in_double_quote
        for char in line:
            if char in self.OPEN_QUOTES:
                delta += 1
            elif char in self.CLOSE_QUOTES:
                delta = max(0, delta - 1)
            elif char == '"':
                in_dq = not in_dq
        dq_delta = (1 if in_dq else 0) - (1 if in_double_quote else 0)
        return delta + dq_delta, in_dq


def extract_tail_lines(text: str, line_count: int = 3) -> str:
    """Extracts the last N non-empty lines from text for sliding context."""
    if not text:
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    tail = lines[-line_count:] if len(lines) >= line_count else lines
    return "\n".join(tail)
