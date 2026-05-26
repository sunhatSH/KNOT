"""Shared pytest fixtures for KNOT backend tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Override DATABASE_URL before any knot imports, so database.py creates test engine
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

# Ensure backend/src/ is on sys.path (backstop for when pytest.ini pythonpath is not honoured)
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from knot.core.database import Base
from knot.llm.base import EmbeddingResult, LLMMessage, LLMProvider, LLMResponse

# ── In-memory SQLite URL ─────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite://"


# ── Database Fixtures ────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    """Create a fresh in-memory SQLite engine with all tables for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a new database session for each test (transaction-scoped)."""
    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as session:
        yield session


# ── Mock LLM Provider ────────────────────────────────────────────────────


class MockLLMProvider(LLMProvider):
    """LLM provider stub for tests. Returns canned responses."""

    def __init__(
        self,
        chat_response: str = "Mock response",
        embed_dim: int = 128,
    ):
        self._chat_response = chat_response
        self._embed_dim = embed_dim

    @property
    def name(self) -> str:
        return "mock"

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(content=self._chat_response)

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResult:
        dim = self._embed_dim
        return EmbeddingResult(
            embeddings=[[float(i) for i in range(dim)] for _ in texts],
            model=model or "mock-model",
        )


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    """Return a basic MockLLMProvider instance."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_provider_summary() -> MockLLMProvider:
    """Return a MockLLMProvider that returns a summary string."""
    return MockLLMProvider(
        chat_response="Compressed summary of conversation history."
    )


# ── Mock Vector Store ─────────────────────────────────────────────────────


class MockVectorStore:
    """In-memory vector store stub for testing retrieval flows."""

    def __init__(self) -> None:
        self._collections: dict[str, list[dict[str, Any]]] = {}

    def create_collection(self, name: str, dimension: int = 128) -> None:
        self._collections.setdefault(name, [])

    def insert(
        self, collection_name: str, vectors: list[list[float]], metadata: list[dict[str, Any]]
    ) -> None:
        coll = self._collections.setdefault(collection_name, [])
        for vec, meta in zip(vectors, metadata):
            coll.append({"vector": vec, "metadata": meta})

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        coll = self._collections.get(collection_name, [])
        results = []
        for item in coll:
            score = self._cosine_similarity(query_vector, item["vector"])
            results.append({"metadata": item["metadata"], "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def delete_collection(self, name: str) -> None:
        self._collections.pop(name, None)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if not na or not nb:
            return 0.0
        return dot / (na * nb)


@pytest.fixture
def mock_vector_store() -> MockVectorStore:
    """Return a MockVectorStore instance."""
    return MockVectorStore()
