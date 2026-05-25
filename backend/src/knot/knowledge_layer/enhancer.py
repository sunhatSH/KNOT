"""Context enhancement — injects retrieved knowledge into LLM prompts."""

from __future__ import annotations

import logging
from typing import Any

from knot.core.models import KnowledgeChunk

logger = logging.getLogger(__name__)

DEFAULT_ENHANCE_TEMPLATE = """\
You are provided with relevant background knowledge to help answer the user's query.

Relevant knowledge:
{knowledge_context}

---

User query: {query}

Please answer the query based on the provided knowledge. If the knowledge does not contain sufficient information, acknowledge this and use your general knowledge.
"""


class ContextEnhancer:
    """Enhances LLM prompts with retrieved knowledge context."""

    def __init__(self, template: str | None = None):
        self._template = template or DEFAULT_ENHANCE_TEMPLATE

    def enhance(
        self,
        query: str,
        chunks: list[KnowledgeChunk],
        system_prompt: str | None = None,
    ) -> str:
        """Inject knowledge chunks into the prompt template."""
        knowledge_context = "\n\n".join(
            f"[Source: {c.document_id} (score: {c.score:.3f})]\n{c.content}"
            for c in chunks
        )

        if system_prompt:
            return f"{system_prompt}\n\n{self._template.format(query=query, knowledge_context=knowledge_context)}"
        return self._template.format(query=query, knowledge_context=knowledge_context)
