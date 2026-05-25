"""DeepSeek LLM provider implementation."""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from knot.llm.base import EmbeddingResult, LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class DeepSeekProvider(LLMProvider):
    """LLM provider for DeepSeek API (OpenAI-compatible)."""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._default_model = "deepseek-chat"
        self._default_embed_model = "deepseek-embedding"

    @property
    def name(self) -> str:
        return "deepseek"

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        api_messages = [
            {"role": m.role, "content": m.content}
            | ({"name": m.name} if m.name else {})
            | ({"tool_calls": m.tool_calls} if m.tool_calls else {})
            | ({"tool_call_id": m.tool_call_id} if m.tool_call_id else {})
            for m in messages
        ]

        kwargs = {
            "model": model or self._default_model,
            "messages": api_messages,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        return LLMResponse(
            content=choice.message.content or "",
            role=choice.message.role,
            tool_calls=(
                [tc.model_dump() for tc in choice.message.tool_calls]
                if choice.message.tool_calls
                else None
            ),
            usage=response.usage.model_dump() if response.usage else None,
            model=response.model,
            raw=response.model_dump(),
        )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
        **kwargs: Any,
    ) -> EmbeddingResult:
        response = await self._client.embeddings.create(
            model=model or self._default_embed_model,
            input=texts,
        )
        return EmbeddingResult(
            embeddings=[d.embedding for d in response.data],
            model=response.model,
            usage=response.usage.model_dump() if response.usage else None,
        )
