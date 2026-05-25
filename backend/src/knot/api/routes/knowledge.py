"""Knowledge management API routes."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.database import get_session
from knot.core.models import KnowledgeBase
from knot.core.repository import KnowledgeBaseRepository
from knot.knowledge_layer.document_parser import DocumentParser
from knot.knowledge_layer.embedding_pipeline import EmbeddingPipeline
from knot.knowledge_layer.retriever import HybridRetriever
from knot.knowledge_layer.vector_store import vector_store
from knot.llm.registry import registry as llm_registry

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

_retriever: HybridRetriever | None = None
_pipeline: EmbeddingPipeline | None = None
_kb_repo = KnowledgeBaseRepository()


def configure_routes(retriever: HybridRetriever) -> None:
    """Inject dependencies into knowledge routes."""
    global _retriever, _pipeline
    _retriever = retriever

    # Create embedding pipeline using the global LLM provider
    try:
        provider = llm_registry.get()
        _pipeline = EmbeddingPipeline(
            llm_provider=provider,
            vector_store=vector_store,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to initialize EmbeddingPipeline: %s", exc
        )

    @router.post("/collections")
    async def create_collection(
        name: str,
        dimension: int = 1024,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """Create a new knowledge collection."""
        collection = await vector_store.create_collection(name, dimension=dimension)

        # Persist the KB definition to the database
        kb = KnowledgeBase(name=name, collection_name=name)
        await _kb_repo.save(session, kb)

        return {"collection": name, "status": "created"}

    @router.post("/search")
    async def search_knowledge(
        collection_name: str,
        query: str,
        top_k: int = 10,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """Search for relevant knowledge."""
        if not _retriever:
            raise HTTPException(status_code=503, detail="Retriever not initialized")
        chunks = await _retriever.retrieve(collection_name, query, top_k=top_k)
        return {
            "query": query,
            "results": [
                {
                    "content": c.content,
                    "score": c.score,
                    "document_id": c.document_id,
                    "metadata": c.metadata,
                }
                for c in chunks
            ],
        }

    @router.post("/documents/upload")
    async def upload_document(
        collection_name: str,
        file: UploadFile = File(...),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """Upload a document, parse it, chunk it, embed it, and store it.

        Accepts a file upload (multipart/form-data) and a collection name
        query parameter. Supports .txt, .md, .pdf, and .docx formats.
        """
        if not _pipeline:
            raise HTTPException(
                status_code=503,
                detail="Embedding pipeline not initialized. Check server logs.",
            )

        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        ext = Path(file.filename).suffix.lower()
        if ext not in DocumentParser.SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file format '{ext}'. "
                    f"Supported formats: {', '.join(sorted(DocumentParser.SUPPORTED_EXTENSIONS))}"
                ),
            )

        # Ensure the target collection exists
        try:
            await vector_store.create_collection(collection_name)
        except Exception:
            # Collection may already exist — that's ok
            pass

        # Save uploaded file to a temporary location
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        try:
            content = await file.read()
            tmp.write(content)
            tmp.close()

            chunks_created = await _pipeline.process_document(
                file_path=tmp.name,
                collection_name=collection_name,
                document_id=document_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Document processing failed: {exc}",
            )
        finally:
            # Clean up the temporary file
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        return {
            "document_id": document_id,
            "chunks_created": chunks_created,
            "collection": collection_name,
            "filename": file.filename,
        }
