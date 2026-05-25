"""Milvus vector store integration."""

from __future__ import annotations

import logging
from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections

from knot.core.config import settings
from knot.core.models import KnowledgeChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """Milvus-backed vector store for knowledge retrieval."""

    def __init__(self):
        self._connected = False
        self._collections: dict[str, Collection] = {}

    async def connect(self) -> None:
        """Connect to Milvus server."""
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port,
        )
        self._connected = True
        logger.info("Connected to Milvus at %s:%s", settings.milvus_host, settings.milvus_port)

    async def create_collection(
        self,
        name: str,
        dimension: int = 1024,
        drop_if_exists: bool = False,
    ) -> Collection:
        """Create a new collection for storing embeddings."""
        if drop_if_exists:
            Collection(name).drop()

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
        ]
        schema = CollectionSchema(fields, description=f"KNOT knowledge collection: {name}")
        collection = Collection(name, schema)
        collection.create_index(
            field_name="embedding",
            index_params={
                "metric_type": "IP",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            },
        )
        collection.load()
        self._collections[name] = collection
        logger.info("Created Milvus collection: %s (dim=%d)", name, dimension)
        return collection

    async def insert_chunks(
        self,
        collection_name: str,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Insert knowledge chunks with their embeddings."""
        collection = self._get_collection(collection_name)
        entities = [
            [c.id for c in chunks],
            [c.document_id for c in chunks],
            [c.content for c in chunks],
            [c.metadata for c in chunks],
            embeddings,
        ]
        mr = collection.insert(entities)
        collection.flush()
        logger.info("Inserted %d chunks into %s (mutations: %s)", len(chunks), collection_name, mr)

    async def search(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[KnowledgeChunk]:
        """Search for similar chunks in a collection."""
        collection = self._get_collection(collection_name)
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=top_k,
            output_fields=["id", "document_id", "content", "metadata"],
        )

        chunks: list[KnowledgeChunk] = []
        for hits in results:
            for hit in hits:
                chunks.append(
                    KnowledgeChunk(
                        id=hit.entity.get("id"),
                        document_id=hit.entity.get("document_id"),
                        content=hit.entity.get("content"),
                        metadata=hit.entity.get("metadata") or {},
                        score=hit.score,
                    )
                )
        return chunks

    def _get_collection(self, name: str) -> Collection:
        if name not in self._collections:
            collection = Collection(name)
            collection.load()
            self._collections[name] = collection
        return self._collections[name]


# Global vector store instance
vector_store = VectorStore()
