"""Cross-Encoder Reranker for high-precision joint query-document relevance scoring."""
from abc import ABC, abstractmethod
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from nousetsu.rag.models import SearchResult

logger = logging.getLogger(__name__)


class BaseCrossEncoderReranker(ABC):
    """Abstract interface for Cross-Encoder candidate rerankers."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[SearchResult],
        top_k: int = 2
    ) -> List[SearchResult]:
        """Rerank candidate search results using joint cross-attention scoring."""
        pass


class MockCrossEncoderReranker(BaseCrossEncoderReranker):
    """Deterministic, offline mock reranker for hermetic unit and integration testing."""

    def rerank(
        self,
        query: str,
        documents: List[SearchResult],
        top_k: int = 2
    ) -> List[SearchResult]:
        if not documents:
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))
        scored_docs = []

        for doc in documents:
            doc_text = f"{doc.title} {doc.content}".lower()
            doc_tokens = set(re.findall(r"\w+", doc_text))
            overlap = len(query_tokens.intersection(doc_tokens))
            total = len(query_tokens) if query_tokens else 1
            overlap_score = min(1.0, overlap / total)

            # Combine lexical overlap with Stage 1 RRF score
            combined = round(0.7 * overlap_score + 0.3 * min(1.0, doc.rrf_score * 30), 4)

            doc_copy = doc.model_copy()
            doc_copy.rerank_score = combined
            scored_docs.append(doc_copy)

        scored_docs.sort(key=lambda d: d.rerank_score or 0.0, reverse=True)

        for rank, d in enumerate(scored_docs, start=1):
            d.rerank_rank = rank

        return scored_docs[:top_k]


class LLMCrossEncoderReranker(BaseCrossEncoderReranker):
    """Cross-Encoder reranker using Gemini or Gemma LLM with structured joint evaluation."""

    def __init__(
        self,
        model_name: str = "gemini-3.5-flash-lite",
        fallback_model: Optional[str] = None
    ):
        from nousetsu.agents.llm import get_llm
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.llm = get_llm(model_name=model_name, fallback_model=fallback_model, temperature=0.1)

    def rerank(
        self,
        query: str,
        documents: List[SearchResult],
        top_k: int = 2
    ) -> List[SearchResult]:
        if not documents:
            return []
        from nousetsu.agents.llm import extract_text_from_message

        # Prepare candidate roster for joint cross-scoring
        candidates_text = []
        for idx, doc in enumerate(documents, start=1):
            loc = f"[{doc.folder}] " if doc.folder else ""
            ch = f"Chapter {doc.chapter_num}" if doc.chapter_num else "Lore"
            t = f" - '{doc.title}'" if doc.title else ""
            snip = doc.content.strip()[:350].replace("\n", " ")
            candidates_text.append(f"[{idx}] ID: {doc.doc_id} | {loc}{ch}{t}\nContent: {snip}")

        prompt = f"""You are a literary Cross-Encoder reranker for an East Asian webnovel/light-novel translation pipeline.
Your task is to score the deep narrative relevance of candidate historical lore snippets against the current chapter query.

CRITERIA:
1. Character identity and relationship fidelity (names, aliases, titles).
2. Direct continuity of past promises, oaths, battles, artifacts, or secrets.
3. Situational alignment with the current query context.

QUERY:
{query}

CANDIDATES:
{chr(10).join(candidates_text)}

Score each candidate from 0.00 to 1.00 (1.00 = critically relevant past canon, 0.00 = irrelevant noise).
Respond STRICTLY with a valid JSON array:
[
  {{"doc_id": "<doc_id>", "score": 0.95, "reason": "<brief justification>"}},
  ...
]
"""
        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a precise Cross-Encoder relevance reranker. Respond only in valid JSON format."),
                HumanMessage(content=prompt)
            ])
            raw_content = extract_text_from_message(response.content)
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content)
            json_str = json_match.group(1) if json_match else raw_content
            parsed = json.loads(json_str)

            scores_by_id: Dict[str, float] = {}
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "doc_id" in item and "score" in item:
                        scores_by_id[str(item["doc_id"])] = float(item["score"])

            reranked_docs: List[SearchResult] = []
            for doc in documents:
                doc_copy = doc.model_copy()
                doc_copy.rerank_score = scores_by_id.get(doc.doc_id, round(doc.rrf_score, 4))
                reranked_docs.append(doc_copy)

            reranked_docs.sort(key=lambda d: d.rerank_score or 0.0, reverse=True)
            for rank, d in enumerate(reranked_docs, start=1):
                d.rerank_rank = rank

            return reranked_docs[:top_k]

        except Exception as e:
            logger.warning(f"Cross-Encoder LLM reranking failed ({e}). Falling back to Stage 1 RRF ranking.")
            fallback_docs = [d.model_copy() for d in documents]
            for rank, d in enumerate(fallback_docs, start=1):
                d.rerank_rank = rank
                d.rerank_score = round(d.rrf_score, 4)
            return fallback_docs[:top_k]


def get_reranker(
    model_name: Optional[str] = None,
    fallback_model: Optional[str] = None,
    is_mock: bool = False
) -> BaseCrossEncoderReranker:
    """Factory creating an appropriate Cross-Encoder reranker instance."""
    eff_model = model_name or os.environ.get("NOVEL_RAG_RERANKER_MODEL", "gemini-3.5-flash-lite")
    mock_mode = (
        is_mock
        or eff_model.lower().startswith(("mock", "test"))
        or bool(os.environ.get("PYTEST_CURRENT_TEST"))
        or os.environ.get("NOVEL_USE_MOCK_RERANKER", "").lower() in ("1", "true")
    )
    if mock_mode:
        return MockCrossEncoderReranker()
    return LLMCrossEncoderReranker(model_name=eff_model, fallback_model=fallback_model)
