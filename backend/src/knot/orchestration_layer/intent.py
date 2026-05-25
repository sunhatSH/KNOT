"""Intent understanding module — parses natural language into structured goals."""

from __future__ import annotations

import json
import logging
from typing import Any

from knot.llm import LLMProvider
from knot.llm.base import LLMMessage

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """\
You are an intent understanding engine for a task orchestration system.
Given a user's natural language request, extract:
1. The core goal / objective
2. Implicit constraints or requirements
3. Expected output format
4. Any domain or context hints

Respond in JSON format:
{
  "goal": "string - one-line summary of what the user wants",
  "constraints": ["list of constraints"],
  "expected_output": "string - what the user expects as output",
  "domain_hints": ["relevant domain tags"],
  "complexity": "simple|moderate|complex"
}
"""


class IntentUnderstanding:
    """Parses natural language instructions into structured intents."""

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    async def parse(self, user_input: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Parse user input into a structured intent."""
        messages = [
            LLMMessage(role="system", content=INTENT_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=f"User request: {user_input}\n"
                f"Context: {json.dumps(context or {}, ensure_ascii=False)}",
            ),
        ]
        response = await self._llm.chat(messages, temperature=0.1)
        try:
            intent = json.loads(response.content)
            logger.info("Parsed intent: %s", intent.get("goal", ""))
            return intent
        except json.JSONDecodeError:
            logger.warning("Failed to parse intent JSON, falling back to raw text")
            return {"goal": response.content, "constraints": [], "complexity": "moderate"}
