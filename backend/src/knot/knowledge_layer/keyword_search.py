"""Lightweight in-memory keyword search for knowledge chunks.

Uses TF-IDF-style scoring on stored chunks. Since we don't have
a full-text search engine available, this maintains an in-memory
inverted index that's rebuilt on demand.

This is a fallback/supplement for when Milvus is unavailable,
and also serves as the keyword leg of hybrid retrieval.
"""

from __future__ import annotations

import logging
import math
import re

from knot.core.models import KnowledgeChunk

logger = logging.getLogger(__name__)

# Chinese punctuation characters used as tokenization delimiters
_CHINESE_PUNCTUATION = '\u3000\u3001\u3002\uff0c\uff1b\u300a\u300b\u300c\u300d\u300e\u300f\uff08\uff09\u3010\u3011\u2014\u2026\u00b7\uff1a\uff01\uff1f\u201c\u201d\u2018\u2019'
_TOKENIZE_PATTERN = re.compile(f'[\\s{re.escape(_CHINESE_PUNCTUATION)}]+')


class KeywordSearch:
    """Lightweight in-memory keyword search for knowledge chunks.

    Maintains an in-memory index of chunk contents that can be rebuilt
    on demand from the vector store. Uses TF-IDF-style scoring with
    support for both English and Chinese text (character-level fallback
    for Chinese).
    """

    def __init__(self) -> None:
        self._chunks: dict[str, KnowledgeChunk] = {}  # chunk_id -> KnowledgeChunk
        self._index_built = False

    def index_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        """Build or update the in-memory inverted index.

        Args:
            chunks: List of KnowledgeChunk objects to index.
        """
        self._chunks.clear()
        for chunk in chunks:
            if chunk.content:
                self._chunks[chunk.id] = chunk
        self._index_built = True
        logger.info("Indexed %d chunks for keyword search", len(self._chunks))

    def search(self, query: str, top_k: int = 10) -> list[KnowledgeChunk]:
        """Search indexed chunks by keyword matching.

        Tokenizes both query and documents (split by whitespace/punctuation).
        Scores by simple term frequency matching with TF * IDF approximation.

        Args:
            query: The search query string.
            top_k: Maximum number of results to return.

        Returns:
            List of KnowledgeChunks sorted by relevance score descending.
        """
        if not self._index_built or not self._chunks:
            logger.debug("Keyword search index is empty, returning empty results")
            return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        # Expand tokens with character-level terms for Chinese text
        terms = self._expand_terms(tokens)
        # Remove duplicate terms while preserving order
        unique_terms = list(dict.fromkeys(terms))
        terms = unique_terms

        n_docs = len(self._chunks)

        # Compute document frequency for each query term
        df: dict[str, int] = {}
        for term in terms:
            count = 0
            for chunk in self._chunks.values():
                if term in chunk.content:
                    count += 1
            df[term] = count

        # Score each document using TF * smoothed IDF
        scored: list[tuple[KnowledgeChunk, float]] = []
        for chunk in self._chunks.values():
            score = 0.0
            for term in terms:
                tf = chunk.content.count(term)
                if tf > 0:
                    # Smoothed IDF to avoid division by zero
                    idf = math.log((n_docs + 1) / (df.get(term, 0) + 0.5))
                    score += tf * idf
            if score > 0:
                scored.append((chunk, score))

        # Sort by score descending and return top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        top_results = scored[:top_k]

        results = [
            KnowledgeChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                metadata=dict(chunk.metadata) if chunk.metadata else {},
                embedding=chunk.embedding,
                score=score,
            )
            for chunk, score in top_results
        ]
        logger.debug(
            "Keyword search found %d results for query: %.60s",
            len(results), query,
        )
        return results

    def clear(self) -> None:
        """Clear all indexed documents."""
        self._chunks.clear()
        self._index_built = False
        logger.info("Keyword search index cleared")

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text by splitting on whitespace and Chinese punctuation."""
        raw = _TOKENIZE_PATTERN.split(text.strip())
        return [t for t in raw if t]

    def _expand_terms(self, tokens: list[str]) -> list[str]:
        """Expand query terms with character-level tokens for Chinese text.

        When a token contains Chinese characters and is longer than 2
        characters, individual Chinese characters are added as additional
        terms to improve recall for Chinese text.
        """
        expanded = list(tokens)
        for token in tokens:
            if self._has_chinese(token) and len(token) > 2:
                for char in token:
                    if '\u4e00' <= char <= '\u9fff' or '\uf900' <= char <= '\ufaff':
                        expanded.append(char)
        return expanded

    @staticmethod
    def _has_chinese(text: str) -> bool:
        """Check if text contains any Chinese characters."""
        for c in text:
            if '\u4e00' <= c <= '\u9fff' or '\uf900' <= c <= '\ufaff':
                return True
        return False
