"""Hybrid retriever combining vector search and keyword search."""

from __future__ import annotations

import logging
from typing import Any

from knot.core.models import KnowledgeChunk
from knot.knowledge_layer.vector_store import vector_store
from knot.knowledge_layer.keyword_search import KeywordSearch
from knot.knowledge_layer.fusion import ResultFusion
from knot.llm import ProviderRegistry

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Performs hybrid retrieval combining vector and keyword search.

    Uses multi-path retrieval (vector search + keyword search) and fuses
    results using Reciprocal Rank Fusion (RRF) for improved relevance.
    """

    def __init__(self, provider_registry: ProviderRegistry):
        self._registry = provider_registry
        self._keyword_search = KeywordSearch()

    async def retrieve(
        self,
        collection_name: str,
        query: str,
        top_k: int = 10,
    ) -> list[KnowledgeChunk]:
        """Retrieve relevant knowledge chunks for a query.

        Uses multi-path retrieval with vector search and keyword search,
        then fuses results using Reciprocal Rank Fusion (RRF).

        Args:
            collection_name: Name of the Milvus collection to search.
            query: The search query string.
            top_k: Maximum number of results to return.

        Returns:
            List of KnowledgeChunks sorted by relevance score descending.
        """
        # 1. Vector search (existing path)
        provider = self._registry.get()
        embedding_result = await provider.embed([query])
        query_embedding = embedding_result.embeddings[0]

        vector_chunks = await vector_store.search(
            collection_name=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        # 2. Keyword search (new path)
        keyword_chunks = self._keyword_search.search(query, top_k=top_k)

        # 3. Fuse results using RRF when both methods return results
        if vector_chunks and keyword_chunks:
            fused = ResultFusion.rrf_fusion(
                [vector_chunks, keyword_chunks],
                top_n=top_k,
            )
            logger.info(
                "Vector: %d results, Keyword: %d results, Fused: %d results",
                len(vector_chunks),
                len(keyword_chunks),
                len(fused),
            )
            return fused
        elif vector_chunks:
            logger.info(
                "Vector: %d results (keyword search unavailable), query: %.60s",
                len(vector_chunks),
                query,
            )
            return vector_chunks
        elif keyword_chunks:
            logger.info(
                "Keyword: %d results (vector search unavailable), query: %.60s",
                len(keyword_chunks),
                query,
            )
            return keyword_chunks

        logger.info("No results found for query: %.60s", query)
        return []

    def index_all(self, collection_name: str) -> None:
        """Load all chunks from the vector store and feed them to KeywordSearch.

        Rebuilds the in-memory keyword index from the Milvus collection.
        Should be called after the Milvus connection is established.

        Args:
            collection_name: Name of the Milvus collection to load chunks from.
        """
        try:
            from pymilvus import Collection

            collection = Collection(collection_name)
            collection.load()
            results = collection.query(
                expr="",
                output_fields=["id", "document_id", "content", "metadata"],
                limit=16384,  # Milvus default max limit
            )

            if not results:
                logger.warning(
                    "No chunks found in collection '%s' for keyword indexing",
                    collection_name,
                )
                return

            chunks = [
                KnowledgeChunk(
                    id=r["id"],
                    document_id=r.get("document_id", ""),
                    content=r["content"],
                    metadata=r.get("metadata", {}),
                )
                for r in results
            ]

            self._keyword_search.index_chunks(chunks)
            logger.info(
                "Rebuilt keyword index with %d chunks from '%s'",
                len(chunks),
                collection_name,
            )
        except Exception as exc:
            logger.warning(
                "Failed to load chunks from '%s' for keyword indexing: %s",
                collection_name,
                exc,
            )
