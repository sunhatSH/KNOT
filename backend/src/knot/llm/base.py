"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMMessage:
    """A message in a conversation with an LLM."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    role: str = "assistant"
    tool_calls: list[dict[str, Any]] | None = None
    usage: dict[str, int] | None = None
    model: str = ""
    raw: dict[str, Any] | None = None


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""

    embeddings: list[list[float]]
    model: str
    usage: dict[str, int] | None = None


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    All LLM backends (DeepSeek, OpenAI, local models, etc.) must
    implement this interface so the orchestration layer is provider-agnostic.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResult:
        """Generate embeddings for text inputs."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        ...
