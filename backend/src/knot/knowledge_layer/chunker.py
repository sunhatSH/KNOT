"""Split documents into chunks for embedding."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from knot.core.models import KnowledgeChunk

logger = logging.getLogger(__name__)


class TextChunker:
    """Split documents into overlapping chunks for embedding."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})"
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[KnowledgeChunk]:
        """Split text into overlapping chunks.

        Strategy:
        1. Split text into paragraphs by double newlines.
        2. Merge paragraphs until chunk_size (characters) is reached.
        3. Apply chunk_overlap between consecutive chunks.
        4. Each chunk gets a unique id (e.g., "chunk_<uuid4_hex8>").
        5. Each chunk carries the document_id in metadata.

        Args:
            text: The plain text to split.
            metadata: Optional metadata to attach to each chunk.
                     Should include "document_id" when available.

        Returns:
            A list of KnowledgeChunk objects.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        if not paragraphs:
            logger.warning("No paragraphs found in input text")
            return []

        chunks_text: list[str] = []
        current_chunk = ""

        for para in paragraphs:
            # Handle paragraphs that are longer than chunk_size on their own
            if len(para) > self.chunk_size:
                # Flush any accumulated chunk first
                if current_chunk:
                    chunks_text.append(current_chunk)
                    current_chunk = ""

                # Split the long paragraph into chunk_size pieces with overlap
                start = 0
                while start < len(para):
                    end = min(start + self.chunk_size, len(para))
                    chunks_text.append(para[start:end])
                    if end == len(para):
                        start = end  # exit loop
                    else:
                        start = end - self.chunk_overlap
                        # Safety: ensure progress
                        if start < 0:
                            start = 0
            else:
                # Normal paragraph that fits within chunk_size
                if not current_chunk:
                    current_chunk = para
                elif len(current_chunk) + 2 + len(para) <= self.chunk_size:
                    current_chunk += "\n\n" + para
                else:
                    # Current chunk is full — save it
                    chunks_text.append(current_chunk)

                    # Start new chunk with overlap from previous chunk
                    if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                        overlap = current_chunk[-self.chunk_overlap :]
                    elif self.chunk_overlap > 0:
                        overlap = current_chunk
                    else:
                        overlap = ""

                    current_chunk = f"{overlap}\n\n{para}" if overlap else para

        # Don't forget the last accumulated chunk
        if current_chunk:
            chunks_text.append(current_chunk)

        # Build KnowledgeChunk objects with unique IDs and metadata
        merged_meta = dict(metadata or {})
        doc_id = merged_meta.get("document_id", "")
        result: list[KnowledgeChunk] = []

        for i, ct in enumerate(chunks_text):
            result.append(
                KnowledgeChunk(
                    id=f"chunk_{uuid.uuid4().hex[:8]}",
                    document_id=doc_id,
                    content=ct,
                    metadata={**merged_meta, "chunk_index": i},
                )
            )

        logger.info(
            "Chunked text into %d chunks (size=%d, overlap=%d)",
            len(result),
            self.chunk_size,
            self.chunk_overlap,
        )
        return result
