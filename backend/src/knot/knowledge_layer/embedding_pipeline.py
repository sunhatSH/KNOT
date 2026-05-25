"""End-to-end pipeline: parse -> chunk -> embed -> store."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from knot.knowledge_layer.chunker import TextChunker
from knot.knowledge_layer.document_parser import DocumentParser

logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    """End-to-end pipeline: parse -> chunk -> embed -> store.

    Orchestrates the full document ingestion flow:
    1. Parse a file (or accept raw text) into plain text.
    2. Split text into overlapping chunks.
    3. Generate embeddings via an LLM provider.
    4. Insert chunks + embeddings into the vector store.
    """

    def __init__(
        self,
        llm_provider: Any,
        vector_store: Any,
        chunker: TextChunker | None = None,
    ):
        """Initialize the pipeline.

        Args:
            llm_provider: An object with an ``embed(texts: list[str])`` method
                that returns an ``EmbeddingResult`` with an ``embeddings`` field.
            vector_store: A ``VectorStore``-like object with an
                ``insert_chunks(collection_name, chunks, embeddings)`` method.
            chunker: A ``TextChunker`` instance. Defaults to a standard instance.
        """
        self._llm = llm_provider
        self._vector_store = vector_store
        self._chunker = chunker or TextChunker()
        self._parser = DocumentParser()

    async def process_document(
        self,
        file_path: str,
        collection_name: str,
        document_id: str = "",
    ) -> int:
        """Process a single document: parse, chunk, embed, insert.

        Args:
            file_path: Absolute or relative path to the document file.
            collection_name: Name of the Milvus collection to insert into.
            document_id: Optional unique identifier. Auto-generated if empty.

        Returns:
            The number of chunks created and stored.

        Raises:
            ValueError: If parsing or processing fails.
        """
        if not document_id:
            document_id = f"doc_{uuid.uuid4().hex[:12]}"

        logger.info(
            "Processing document: %s -> collection '%s' (doc_id: %s)",
            file_path,
            collection_name,
            document_id,
        )

        # Step 1: Parse
        text = await self._parser.parse(file_path)
        logger.info("Parsed %d characters from %s", len(text), file_path)

        # Step 2: Chunk
        metadata: dict[str, Any] = {
            "document_id": document_id,
            "source": file_path,
        }
        chunks = self._chunker.chunk(text, metadata=metadata)
        logger.info("Created %d chunks from document %s", len(chunks), document_id)

        if not chunks:
            logger.warning(
                "No chunks created for document %s (file may be empty)", document_id
            )
            return 0

        # Step 3: Embed
        texts = [c.content for c in chunks]
        try:
            embedding_result = await self._llm.embed(texts)
        except Exception as exc:
            raise ValueError(
                f"Embedding generation failed for document {document_id}: {exc}"
            ) from exc

        embeddings = embedding_result.embeddings
        if not embeddings:
            raise ValueError(
                f"LLM provider returned empty embeddings for document {document_id}"
            )

        logger.info(
            "Generated %d embeddings (dim=%d)",
            len(embeddings),
            len(embeddings[0]) if embeddings else 0,
        )

        # Step 4: Store
        try:
            await self._vector_store.insert_chunks(
                collection_name=collection_name,
                chunks=chunks,
                embeddings=embeddings,
            )
        except Exception as exc:
            raise ValueError(
                f"Failed to insert chunks into collection '{collection_name}': {exc}"
            ) from exc

        logger.info(
            "Successfully inserted %d chunks into collection '%s' (doc_id: %s)",
            len(chunks),
            collection_name,
            document_id,
        )
        return len(chunks)

    async def process_text(
        self,
        text: str,
        collection_name: str,
        document_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Process raw text (without a file): chunk, embed, insert.

        Useful for programmatic usage where the content is already in memory.

        Args:
            text: The plain text content to process.
            collection_name: Name of the Milvus collection to insert into.
            document_id: Optional unique identifier. Auto-generated if empty.
            metadata: Optional metadata dict. The ``document_id`` key is
                      automatically injected/overwritten.

        Returns:
            The number of chunks created and stored.
        """
        if not document_id:
            document_id = f"doc_{uuid.uuid4().hex[:12]}"

        merged_meta = dict(metadata or {})
        merged_meta["document_id"] = document_id
        if "source" not in merged_meta:
            merged_meta["source"] = "direct_input"

        logger.info(
            "Processing text (%d chars) -> collection '%s' (doc_id: %s)",
            len(text),
            collection_name,
            document_id,
        )

        # Step 1: Chunk
        chunks = self._chunker.chunk(text, metadata=merged_meta)
        logger.info("Created %d chunks from text input", len(chunks))

        if not chunks:
            logger.warning("No chunks created from input text")
            return 0

        # Step 2: Embed
        texts = [c.content for c in chunks]
        try:
            embedding_result = await self._llm.embed(texts)
        except Exception as exc:
            raise ValueError(
                f"Embedding generation failed: {exc}"
            ) from exc

        embeddings = embedding_result.embeddings
        if not embeddings:
            raise ValueError("LLM provider returned empty embeddings")

        logger.info(
            "Generated %d embeddings (dim=%d)",
            len(embeddings),
            len(embeddings[0]) if embeddings else 0,
        )

        # Step 3: Store
        try:
            await self._vector_store.insert_chunks(
                collection_name=collection_name,
                chunks=chunks,
                embeddings=embeddings,
            )
        except Exception as exc:
            raise ValueError(
                f"Failed to insert chunks into collection '{collection_name}': {exc}"
            ) from exc

        logger.info(
            "Successfully inserted %d chunks into collection '%s' (doc_id: %s)",
            len(chunks),
            collection_name,
            document_id,
        )
        return len(chunks)
