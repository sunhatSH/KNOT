"""Multi-path result fusion using RRF (Reciprocal Rank Fusion)."""

from __future__ import annotations

import logging
from typing import Any

from knot.core.models import KnowledgeChunk

logger = logging.getLogger(__name__)


class ResultFusion:
    """Fuse results from multiple retrieval paths using RRF.

    Reciprocal Rank Fusion (RRF) is a simple yet effective method for
    combining ranked lists from different retrieval methods. It assigns
    a score to each item based on its rank position across all input lists,
    without requiring normalized scores or training data.
    """

    @staticmethod
    def rrf_fusion(
        results: list[list[KnowledgeChunk]],
        k: int = 60,
        top_n: int = 10,
    ) -> list[KnowledgeChunk]:
        """Reciprocal Rank Fusion: merge ranked lists from different retrieval methods.

        RRF score = sum(1 / (k + rank(position)))

        Args:
            results: List of ranked lists from different retrieval methods.
            k: RRF constant (default 60). Higher values give more weight
               to lower-ranked items.
            top_n: Number of top results to return.

        Returns:
            Deduplicated, re-ranked list of KnowledgeChunks with RRF scores.
        """
        if not results:
            return []

        # Merge by (document_id, content) to handle deduplication
        merged: dict[tuple[str, str], KnowledgeChunk] = {}

        for rank_list in results:
            for rank, chunk in enumerate(rank_list):
                # Use 1-based rank for the RRF formula (rank starts at 1)
                rrf_score = 1.0 / (k + rank + 1)

                key = ResultFusion._chunk_key(chunk)
                if key not in merged:
                    merged[key] = KnowledgeChunk(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        metadata=dict(chunk.metadata) if chunk.metadata else {},
                        score=0.0,
                    )
                merged[key].score += rrf_score

        # Sort by RRF score descending
        result = sorted(merged.values(), key=lambda c: c.score, reverse=True)
        return result[:top_n]

    @staticmethod
    def deduplicate(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        """Remove duplicate chunks by document_id+content.

        When duplicates are found, keep the one with higher score.

        Args:
            chunks: List of KnowledgeChunks, possibly with duplicates.

        Returns:
            Deduplicated list of KnowledgeChunks.
        """
        seen: dict[tuple[str, str], KnowledgeChunk] = {}
        for chunk in chunks:
            key = ResultFusion._chunk_key(chunk)
            if key not in seen or chunk.score > seen[key].score:
                seen[key] = chunk
        return list(seen.values())

    @staticmethod
    def _chunk_key(chunk: KnowledgeChunk) -> tuple[str, str]:
        """Generate a unique key for a chunk based on document_id and content.

        Uses document_id with content as the deduplication key. Falls back
        to chunk id when document_id is not available.
        """
        doc_id = chunk.document_id or chunk.id
        return (doc_id, chunk.content)
