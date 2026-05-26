"""Tests for conversation memory (session lifecycle, compression, context)."""

from __future__ import annotations

import pytest

from knot.core.models import ConversationSession, ConversationTurn
from knot.knowledge_layer.conversation_memory import ConversationMemory
from knot.llm.base import LLMMessage


# --- ConversationMemory ---------------------------------------------------


class TestConversationMemory:
    def test_create_session(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session(workflow_id="wf_1", execution_id="exec_1")

        assert session.id.startswith("conv_")
        assert session.workflow_id == "wf_1"
        assert session.execution_id == "exec_1"
        assert session.turns == []
        assert session.turn_count == 0
        assert session.summary == ""

        # Should be retrievable
        assert memory.get_session(session.id) is session

    def test_get_session_nonexistent(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        assert memory.get_session("no-such-session") is None

    def test_add_turn(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()

        turn = memory.add_turn(session.id, role="user", content="Hello!")
        assert turn.role == "user"
        assert turn.content == "Hello!"
        assert turn.id.startswith("turn_")
        assert turn.token_count > 0

        # Check session was updated
        assert session.turn_count == 1
        assert len(session.turns) == 1
        assert session.turns[0] is turn

    def test_add_turn_invalid_session(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        with pytest.raises(ValueError, match="Session not found"):
            memory.add_turn("invalid", "user", "test")

    def test_add_turn_with_metadata(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()

        turn = memory.add_turn(
            session.id,
            role="assistant",
            content="Hello back!",
            metadata={"name": "bot"},
            token_count=42,
        )
        assert turn.metadata == {"name": "bot"}
        assert turn.token_count == 42

    def test_add_multiple_turns(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()

        for i in range(5):
            memory.add_turn(session.id, role="user", content=f"Turn {i}")
            memory.add_turn(session.id, role="assistant", content=f"Response {i}")

        assert session.turn_count == 10
        assert len(session.turns) == 10

    def test_get_context_empty_session(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()

        import asyncio
        context = asyncio.run(memory.get_context(session.id))
        assert context == []

    def test_get_context_with_turns(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()

        memory.add_turn(session.id, role="user", content="Hello")
        memory.add_turn(session.id, role="assistant", content="Hi there!")

        import asyncio
        context = asyncio.run(memory.get_context(session.id))
        assert len(context) == 2
        assert context[0].role == "user"
        assert context[0].content == "Hello"
        assert context[1].role == "assistant"
        assert context[1].content == "Hi there!"

    def test_get_context_with_summary(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()

        # Set up a session with a summary and many turns
        session.summary = "Previous conversation summary"
        for i in range(15):
            memory.add_turn(session.id, role="user", content=f"Q{i}")
            memory.add_turn(session.id, role="assistant", content=f"A{i}")

        import asyncio
        context = asyncio.run(memory.get_context(session.id, max_recent_turns=5))
        # Should have 1 system message (summary) + 5 recent turns
        assert len(context) == 6
        assert context[0].role == "system"
        assert "Previous conversation" in context[0].content
        assert context[-1].role == "assistant"

    def test_get_context_invalid_session(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        import asyncio
        context = asyncio.run(memory.get_context("invalid"))
        assert context == []

    def test_get_context_with_name_metadata(self, mock_llm_provider):
        """If turn metadata has 'name', it should be passed to LLMMessage."""
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()

        memory.add_turn(
            session.id,
            role="tool",
            content="result data",
            metadata={"name": "calculator"},
        )

        import asyncio
        context = asyncio.run(memory.get_context(session.id))
        assert len(context) == 1
        assert context[0].name == "calculator"

    def test_clear_session(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()

        assert memory.clear_session(session.id) is True
        assert memory.get_session(session.id) is None

    def test_clear_nonexistent_session(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        assert memory.clear_session("invalid") is False

    def test_list_sessions(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        s1 = memory.create_session()
        s2 = memory.create_session()
        s3 = memory.create_session()

        sessions = memory.list_sessions()
        assert len(sessions) == 3
        ids = {s.id for s in sessions}
        assert s1.id in ids
        assert s2.id in ids
        assert s3.id in ids

    def test_create_session_defaults(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        session = memory.create_session()
        assert session.workflow_id == ""
        assert session.execution_id == ""


# --- Compression ----------------------------------------------------------


class TestCompression:
    def test_compress_no_llm_truncates(self, mock_llm_provider):
        """Without LLM provider, compress should fall back to truncation."""
        memory = ConversationMemory(llm_provider=None, max_turns_full=3)
        session = memory.create_session()

        for i in range(10):
            memory.add_turn(session.id, role="user", content=f"Turn {i}")
            memory.add_turn(session.id, role="assistant", content=f"Response {i}")

        import asyncio
        summary = asyncio.run(memory.compress(session.id))
        assert summary != ""
        # Should keep only max_turns_full recent turns
        assert len(session.turns) == 3

    def test_compress_with_llm(self, mock_llm_provider_summary):
        """With LLM provider, compress should use LLM for summarization."""
        memory = ConversationMemory(
            llm_provider=mock_llm_provider_summary,
            max_turns_full=3,
        )
        session = memory.create_session()

        for i in range(10):
            memory.add_turn(session.id, role="user", content=f"Turn {i}")
            memory.add_turn(session.id, role="assistant", content=f"Response {i}")

        import asyncio
        summary = asyncio.run(memory.compress(session.id))
        assert summary == "Compressed summary of conversation history."
        assert len(session.turns) == 3  # Kept only max_turns_full

    def test_compress_not_needed(self, mock_llm_provider):
        """When turns <= max_turns_full, compress should be a no-op."""
        memory = ConversationMemory(llm_provider=mock_llm_provider, max_turns_full=10)
        session = memory.create_session()

        memory.add_turn(session.id, role="user", content="Hello")
        memory.add_turn(session.id, role="assistant", content="Hi")

        import asyncio
        summary = asyncio.run(memory.compress(session.id))
        assert summary == ""
        assert len(session.turns) == 2  # unchanged

    def test_compress_invalid_session(self, mock_llm_provider):
        memory = ConversationMemory(llm_provider=mock_llm_provider)
        import asyncio
        result = asyncio.run(memory.compress("invalid"))
        assert result == ""

    def test_compress_fallback_on_llm_failure(self):
        """When LLM compression fails, fall back to truncation."""
        class FailingMockProvider:
            @property
            def name(self):
                return "failing"
            async def chat(self, messages, **kwargs):
                raise RuntimeError("LLM failure")
            async def embed(self, texts, **kwargs):
                raise RuntimeError("LLM failure")

        memory = ConversationMemory(
            llm_provider=FailingMockProvider(),  # type: ignore[arg-type]
            max_turns_full=2,
        )
        session = memory.create_session()

        for i in range(6):
            memory.add_turn(session.id, role="user", content=f"Q{i}")

        import asyncio
        summary = asyncio.run(memory.compress(session.id))
        # Should have a fallback summary
        assert summary != ""
        assert len(session.turns) == 2

    def test_compress_with_explicit_llm(self, mock_llm_provider_summary):
        """Compress should accept an explicit llm_provider parameter."""
        memory = ConversationMemory(llm_provider=None, max_turns_full=3)
        session = memory.create_session()

        for i in range(8):
            memory.add_turn(session.id, role="user", content=f"Q{i}")

        import asyncio
        summary = asyncio.run(
            memory.compress(session.id, llm_provider=mock_llm_provider_summary)
        )
        assert summary != ""
        assert len(session.turns) == 3


# --- Token Threshold Compression -----------------------------------------


class TestAutoCompression:
    def test_add_turn_auto_compress_triggers(self, mock_llm_provider):
        """Adding a turn that exceeds token budget should trigger compression log."""
        memory = ConversationMemory(
            llm_provider=None,
            max_tokens_before_compress=500,
        )

        # Should not raise an error
        session = memory.create_session()
        for i in range(20):
            long_content = f"Long turn content with some padding text to increase token count here: {i} " * 5
            memory.add_turn(session.id, role="user", content=long_content, token_count=100)

        # After auto-compression trigger, tokens should still be tracked
        total = sum(t.token_count for t in session.turns)
        assert total > 0
