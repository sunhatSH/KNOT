"""Hybrid retriever combining vector search and keyword search."""

from __future__ import annotations

import logging
from typing import Any

from knot.core.models import KnowledgeChunk
from knot.knowledge_layer.vector_store import vector_store
from knot.llm import ProviderRegistry

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Performs hybrid retrieval combining vector and keyword search."""

    def __init__(self, provider_registry: ProviderRegistry):
        self._registry = provider_registry

    async def retrieve(
        self,
        collection_name: str,
        query: str,
        top_k: int = 10,
    ) -> list[KnowledgeChunk]:
        """Retrieve relevant knowledge chunks for a query.

        Uses vector search as the primary retrieval method.
        """
        provider = self._registry.get()
        embedding_result = await provider.embed([query])
        query_embedding = embedding_result.embeddings[0]

        chunks = await vector_store.search(
            collection_name=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
        )
        logger.info(
            "Retrieved %d chunks from '%s' for query: %.60s",
            len(chunks), collection_name, query,
        )
        return chunks
