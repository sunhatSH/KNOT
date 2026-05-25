"""Knowledge management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.database import get_session
from knot.core.models import KnowledgeBase
from knot.core.repository import KnowledgeBaseRepository
from knot.knowledge_layer.retriever import HybridRetriever
from knot.knowledge_layer.vector_store import vector_store

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

_retriever: HybridRetriever | None = None
_kb_repo = KnowledgeBaseRepository()


def configure_routes(retriever: HybridRetriever) -> None:
    """Inject dependencies into knowledge routes."""
    global _retriever
    _retriever = retriever

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
