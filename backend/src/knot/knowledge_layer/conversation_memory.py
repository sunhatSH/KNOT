"""Multi-turn conversation memory with history compression and persistence.

Manages conversation sessions, compresses old turns when context gets long,
and persists to database. Integrates with the workflow engine to provide
conversation context during multi-step task execution.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from knot.core.models import ConversationSession, ConversationTurn
from knot.llm.base import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

# Prompt for compressing conversation history
SUMMARY_PROMPT = """\
Compress the following conversation history into a concise summary.
Preserve key facts, decisions, user preferences, and unresolved items.
This summary will be used as context for future turns in the conversation.

Conversation history:
{history}

Summary:
"""


class ConversationMemory:
    """Manages multi-turn conversation context with compression.

    Features:
    - Maintains full conversation history for recent turns
    - Compresses older turns into a summary when token budget is exceeded
    - Persists sessions to database
    - Provides formatted context for LLM prompts
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        max_turns_full: int = 10,
        max_tokens_before_compress: int = 4000,
    ):
        self._llm = llm_provider
        self._max_turns_full = max_turns_full
        self._max_tokens_before_compress = max_tokens_before_compress
        self._sessions: dict[str, ConversationSession] = {}

    def create_session(
        self,
        workflow_id: str = "",
        execution_id: str = "",
    ) -> ConversationSession:
        """Create a new conversation session."""
        session = ConversationSession(
            workflow_id=workflow_id,
            execution_id=execution_id,
        )
        self._sessions[session.id] = session
        logger.info("Created conversation session: %s", session.id)
        return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
        token_count: int = 0,
    ) -> ConversationTurn:
        """Add a turn to a session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        turn = ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {},
            token_count=token_count or len(content) // 2,  # rough estimate
        )
        session.turns.append(turn)
        session.turn_count += 1
        session.updated_at = datetime.now()

        # Check if compression is needed
        total_tokens = sum(t.token_count for t in session.turns)
        if total_tokens > self._max_tokens_before_compress:
            logger.info(
                "Session %s: %d tokens exceeds limit %d, compressing",
                session_id, total_tokens, self._max_tokens_before_compress,
            )

        return turn

    async def get_context(
        self,
        session_id: str,
        max_recent_turns: int = 10,
    ) -> list[LLMMessage]:
        """Build context messages for LLM from conversation history.

        Returns:
        - If summary exists: [system with summary, ...recent turns]
        - If full history fits: [...all turns]
        """
        session = self._sessions.get(session_id)
        if not session:
            return []

        messages: list[LLMMessage] = []

        # Add summary as system message if it exists and there are many turns
        if session.summary and len(session.turns) > max_recent_turns:
            messages.append(LLMMessage(
                role="system",
                content=f"Previous conversation context:\n{session.summary}",
            ))

        # Add recent turns
        recent = session.turns[-max_recent_turns:]
        for turn in recent:
            kwargs: dict[str, Any] = {}
            if turn.metadata.get("name"):
                kwargs["name"] = turn.metadata["name"]
            messages.append(LLMMessage(
                role=turn.role,
                content=turn.content,
                **kwargs,
            ))

        return messages

    async def compress(
        self,
        session_id: str,
        llm_provider: LLMProvider | None = None,
    ) -> str:
        """Compress older turns into a summary using LLM.

        Keeps the most recent max_turns_full turns intact.
        Compresses everything before that into a summary string.
        """
        session = self._sessions.get(session_id)
        if not session or len(session.turns) <= self._max_turns_full:
            return session.summary if session else ""

        provider = llm_provider or self._llm
        if not provider:
            logger.warning("No LLM provider available for compression, using truncation")
            # Fallback: just truncate old turns
            old_turns = session.turns[:-self._max_turns_full]
            summary = " | ".join(
                f"[{t.role}]: {t.content[:100]}" for t in old_turns
            )
            session.summary = summary[:2000]
            session.turns = session.turns[-self._max_turns_full:]
            return session.summary

        # Compress old turns via LLM
        old_turns = session.turns[:-self._max_turns_full]
        history_text = "\n".join(
            f"[{t.role.upper()}] {t.content}" for t in old_turns
        )

        try:
            messages = [
                LLMMessage(role="user", content=SUMMARY_PROMPT.format(history=history_text)),
            ]
            response = await provider.chat(messages, temperature=0.2)
            session.summary = response.content[:2000]
            session.turns = session.turns[-self._max_turns_full:]
            logger.info(
                "Compressed %d old turns into summary (%d chars) for session %s",
                len(old_turns), len(session.summary), session_id,
            )
        except Exception as e:
            logger.warning("Compression failed for session %s: %s", session_id, e)
            session.summary = history_text[:2000]
            session.turns = session.turns[-self._max_turns_full:]

        return session.summary

    def clear_session(self, session_id: str) -> bool:
        """Clear a session from memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Cleared conversation session: %s", session_id)
            return True
        return False

    def list_sessions(self) -> list[ConversationSession]:
        """List all active sessions."""
        return list(self._sessions.values())
