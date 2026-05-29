"""Tests for the knowledge layer — chunker, keyword search, fusion, enhancer, conversation memory."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from knot.core.models import KnowledgeChunk
from knot.knowledge_layer.chunker import TextChunker
from knot.knowledge_layer.keyword_search import KeywordSearch
from knot.knowledge_layer.fusion import ResultFusion
from knot.knowledge_layer.enhancer import ContextEnhancer
from knot.knowledge_layer.conversation_memory import ConversationMemory


# ─── TextChunker Tests ─────────────────────────────────────────────────────────


class TestTextChunker:
    """TextChunker splits documents into overlapping chunks."""

    def test_chunk_short_text(self):
        """Text shorter than chunk_size yields a single chunk."""
        chunker = TextChunker(chunk_size=1000, chunk_overlap=64)
        chunks = chunker.chunk("Hello world. This is a short text.")
        assert len(chunks) == 1
        assert chunks[0].content == "Hello world. This is a short text."

    def test_chunk_two_paragraphs_fit(self):
        """Two paragraphs that fit in a single chunk."""
        chunker = TextChunker(chunk_size=1000, chunk_overlap=64)
        chunks = chunker.chunk("Paragraph one.\n\nParagraph two.")
        assert len(chunks) == 1
        assert "Paragraph one." in chunks[0].content
        assert "Paragraph two." in chunks[0].content

    def test_chunk_paragraph_boundary(self):
        """Multiple paragraphs that exceed chunk_size create multiple chunks."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        para_a = "A" * 60
        para_b = "B" * 60
        para_c = "C" * 60
        chunks = chunker.chunk(f"{para_a}\n\n{para_b}\n\n{para_c}")
        assert len(chunks) >= 2

    def test_chunk_single_large_paragraph(self):
        """A single paragraph longer than chunk_size is split with overlap."""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        long_text = "X" * 120
        chunks = chunker.chunk(long_text)
        assert len(chunks) >= 2
        # Verify overlap exists between consecutive chunks
        for i in range(len(chunks) - 1):
            a = chunks[i].content
            b = chunks[i + 1].content
            overlap = set(a[-10:]) & set(b[:10])
            assert len(overlap) > 0, f"No overlap between chunks {i} and {i+1}"

    def test_chunk_empty_text(self):
        """Empty text produces no chunks."""
        chunker = TextChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_chunk_whitespace_only(self):
        """Whitespace-only text produces no chunks."""
        chunker = TextChunker()
        chunks = chunker.chunk("   \n\n  \n  ")
        assert chunks == []

    def test_chunk_metadata_preserved(self):
        """Metadata is attached to each chunk."""
        chunker = TextChunker(chunk_size=1000, chunk_overlap=64)
        chunks = chunker.chunk("Some content.", metadata={"document_id": "doc_123", "source": "test"})
        assert len(chunks) == 1
        assert chunks[0].document_id == "doc_123"
        assert chunks[0].metadata["source"] == "test"
        assert chunks[0].metadata["chunk_index"] == 0

    def test_chunk_ids_unique(self):
        """Each chunk gets a unique ID."""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "A\n\n" * 10
        chunks = chunker.chunk(text)
        ids = [c.id for c in chunks]
        assert len(set(ids)) == len(ids)

    def test_chunk_invalid_overlap(self):
        """chunk_overlap must be less than chunk_size."""
        with pytest.raises(ValueError, match="chunk_overlap.*must be less than chunk_size"):
            TextChunker(chunk_size=100, chunk_overlap=100)

    def test_chunk_zero_overlap(self):
        """Zero overlap is allowed."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=0)
        chunks = chunker.chunk("Hello world.")
        assert len(chunks) == 1


# ─── KeywordSearch Tests ───────────────────────────────────────────────────────


class TestKeywordSearch:
    """KeywordSearch provides in-memory TF-IDF-style search."""

    def test_search_after_indexing(self):
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(id="c1", content="The quick brown fox"),
            KnowledgeChunk(id="c2", content="Jumps over the lazy dog"),
            KnowledgeChunk(id="c3", content="The fox is quick"),
        ]
        ks.index_chunks(chunks)
        results = ks.search("quick fox", top_k=5)
        assert len(results) >= 2
        # "quick" and "fox" appear in c1 and c3 — these should score higher
        scores = {r.id: r.score for r in results}
        assert scores.get("c1", 0) > 0
        assert scores.get("c3", 0) > 0

    def test_search_no_index(self):
        """Search on empty index returns empty list."""
        ks = KeywordSearch()
        assert ks.search("anything") == []

    def test_search_no_match(self):
        """Search with non-matching query returns empty list."""
        ks = KeywordSearch()
        ks.index_chunks([
            KnowledgeChunk(id="c1", content="alpha beta gamma"),
        ])
        results = ks.search("zzzzz")
        assert results == []

    def test_search_chinese_text(self):
        """Search works with Chinese characters (character-level fallback)."""
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(id="c1", content="深度学习是人工智能的重要分支"),
            KnowledgeChunk(id="c2", content="机器学习是人工智能的一个子领域"),
        ]
        ks.index_chunks(chunks)
        results = ks.search("人工智能")
        assert len(results) >= 1

    def test_clear_index(self):
        ks = KeywordSearch()
        ks.index_chunks([KnowledgeChunk(id="c1", content="hello")])
        ks.clear()
        assert ks.search("hello") == []

    def test_search_top_k(self):
        ks = KeywordSearch()
        chunks = [KnowledgeChunk(id=f"c{i}", content=f"word {i}") for i in range(20)]
        ks.index_chunks(chunks)
        results = ks.search("word", top_k=5)
        assert len(results) == 5

    def test_index_overwrite_clears_previous(self):
        ks = KeywordSearch()
        ks.index_chunks([KnowledgeChunk(id="c1", content="old content")])
        ks.index_chunks([KnowledgeChunk(id="c2", content="new content")])
        results = ks.search("old")
        assert results == []

    def test_empty_content_chunks_skipped(self):
        ks = KeywordSearch()
        ks.index_chunks([
            KnowledgeChunk(id="c1", content=""),
            KnowledgeChunk(id="c2", content="real content"),
        ])
        results = ks.search("real")
        assert len(results) == 1


# ─── ResultFusion Tests ────────────────────────────────────────────────────────


class TestResultFusion:
    """ResultFusion merges ranked lists using Reciprocal Rank Fusion."""

    def make_chunk(self, cid: str, doc_id: str, content: str, score: float = 0.0) -> KnowledgeChunk:
        return KnowledgeChunk(
            id=cid, document_id=doc_id, content=content, score=score,
        )

    def test_rrf_fusion_two_lists(self):
        c1 = self.make_chunk("a", "doc1", "content a")
        c2 = self.make_chunk("b", "doc2", "content b")
        c3 = self.make_chunk("c", "doc3", "content c")
        c4 = self.make_chunk("d", "doc4", "content d")

        list1 = [c1, c2, c3]
        list2 = [c3, c4, c1]  # c3 and c1 appear in both

        fused = ResultFusion.rrf_fusion([list1, list2], top_n=10)
        assert len(fused) == 4  # 4 unique (doc_id, content) pairs
        # c1 and c3 both appear in both lists (mirrored ranks) and tie
        # on RRF score; both should score higher than c2 and c4.
        top_ids = {c.id for c in fused[:2]}
        assert "a" in top_ids
        assert "c" in top_ids
        # c2 and c4 should be at the bottom (only appear in one list each)
        assert fused[-1].id in ("b", "d")

    def test_rrf_fusion_empty_input(self):
        assert ResultFusion.rrf_fusion([]) == []

    def test_rrf_fusion_single_list(self):
        chunks = [
            self.make_chunk("a", "doc1", "a"),
            self.make_chunk("b", "doc2", "b"),
        ]
        fused = ResultFusion.rrf_fusion([chunks], top_n=5)
        assert len(fused) == 2
        assert fused[0].id == "a"

    def test_rrf_fusion_top_n(self):
        chunks = [
            self.make_chunk(f"c{i}", f"doc{i}", f"content {i}")
            for i in range(20)
        ]
        fused = ResultFusion.rrf_fusion([chunks], top_n=5)
        assert len(fused) == 5

    def test_rrf_fusion_deduplicates_by_doc_id_and_content(self):
        c1 = self.make_chunk("a", "doc1", "same content")
        c2 = self.make_chunk("b", "doc1", "same content")  # same key but different id
        fused = ResultFusion.rrf_fusion([[c1, c2]], top_n=5)
        assert len(fused) == 1  # deduplicated

    def test_deduplicate(self):
        chunks = [
            self.make_chunk("a", "doc1", "content", score=0.5),
            self.make_chunk("b", "doc1", "content", score=0.8),
        ]
        deduped = ResultFusion.deduplicate(chunks)
        assert len(deduped) == 1
        assert deduped[0].id == "b"  # higher score wins

    def test_deduplicate_no_duplicates(self):
        chunks = [
            self.make_chunk("a", "doc1", "a", score=0.5),
            self.make_chunk("b", "doc2", "b", score=0.8),
        ]
        deduped = ResultFusion.deduplicate(chunks)
        assert len(deduped) == 2

    def test_deduplicate_empty(self):
        assert ResultFusion.deduplicate([]) == []

    def test_chunk_key_fallback_to_id(self):
        """When document_id is empty, the chunk's own id is used as key."""
        chunk = self.make_chunk("fallback_id", "", "orphan content")
        key = ResultFusion._chunk_key(chunk)
        assert key == ("fallback_id", "orphan content")


# ─── ContextEnhancer Tests ─────────────────────────────────────────────────────


class TestContextEnhancer:
    """ContextEnhancer injects retrieved knowledge into LLM prompts."""

    def test_enhance_with_chunks(self):
        enhancer = ContextEnhancer()
        chunks = [
            KnowledgeChunk(id="c1", document_id="doc1", content="Paris is the capital of France.", score=0.9),
            KnowledgeChunk(id="c2", document_id="doc2", content="The Eiffel Tower is in Paris.", score=0.8),
        ]
        result = enhancer.enhance("What is the capital of France?", chunks)
        assert "Paris" in result
        assert "capital of France" in result
        assert "[Source: doc1" in result
        assert "[Source: doc2" in result

    def test_enhance_with_system_prompt(self):
        enhancer = ContextEnhancer()
        chunks = [
            KnowledgeChunk(id="c1", document_id="doc1", content="Some knowledge.", score=0.5),
        ]
        result = enhancer.enhance("A query", chunks, system_prompt="You are a helpful assistant.")
        assert "You are a helpful assistant." in result
        assert "Some knowledge." in result

    def test_enhance_empty_chunks(self):
        enhancer = ContextEnhancer()
        result = enhancer.enhance("A query", [])
        # Should still produce the template with empty knowledge context
        assert "A query" in result
        assert "Relevant knowledge:" in result

    def test_enhance_custom_template(self):
        custom_template = "Knowledge: {knowledge_context}\nQuery: {query}\nAnswer:"
        enhancer = ContextEnhancer(template=custom_template)
        chunks = [KnowledgeChunk(id="c1", content="data")]
        result = enhancer.enhance("my query", chunks)
        assert "Knowledge: " in result
        assert "Query: my query" in result
        assert "Answer:" in result


# ─── ConversationMemory Tests ──────────────────────────────────────────────────


class TestConversationMemory:
    """ConversationMemory manages multi-turn conversation context."""

    def test_create_session(self):
        mem = ConversationMemory()
        session = mem.create_session(workflow_id="wf_1", execution_id="exec_1")
        assert session.id is not None
        assert session.workflow_id == "wf_1"
        assert session.execution_id == "exec_1"
        assert session.turns == []
        assert session.turn_count == 0

    def test_get_session_found(self):
        mem = ConversationMemory()
        created = mem.create_session()
        retrieved = mem.get_session(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_session_not_found(self):
        mem = ConversationMemory()
        assert mem.get_session("nonexistent") is None

    def test_add_turn(self):
        mem = ConversationMemory()
        session = mem.create_session()
        turn = mem.add_turn(session.id, role="user", content="Hello!")
        assert turn.role == "user"
        assert turn.content == "Hello!"
        assert session.turn_count == 1
        assert len(session.turns) == 1

    def test_add_turn_nonexistent_session(self):
        mem = ConversationMemory()
        with pytest.raises(ValueError, match="Session not found"):
            mem.add_turn("bad_id", role="user", content="Hi")

    def test_add_multiple_turns(self):
        mem = ConversationMemory()
        session = mem.create_session()
        mem.add_turn(session.id, "user", "First")
        mem.add_turn(session.id, "assistant", "Second")
        mem.add_turn(session.id, "user", "Third")
        assert session.turn_count == 3
        assert session.turns[1].content == "Second"

    def test_add_turn_with_metadata(self):
        mem = ConversationMemory()
        session = mem.create_session()
        turn = mem.add_turn(session.id, "assistant", "Response", metadata={"name": "assistant_name"})
        assert turn.metadata.get("name") == "assistant_name"

    def test_add_turn_updates_updated_at(self):
        mem = ConversationMemory()
        session = mem.create_session()
        before = session.updated_at
        mem.add_turn(session.id, "user", "Hello!")
        assert session.updated_at >= before

    @pytest.mark.asyncio
    async def test_get_context_empty_session(self):
        mem = ConversationMemory()
        result = await mem.get_context("nonexistent")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_context_with_turns(self):
        mem = ConversationMemory()
        session = mem.create_session()
        mem.add_turn(session.id, "user", "Hello")
        mem.add_turn(session.id, "assistant", "Hi there")
        context = await mem.get_context(session.id)
        assert len(context) == 2
        assert context[0].role == "user"
        assert context[0].content == "Hello"
        assert context[1].role == "assistant"
        assert context[1].content == "Hi there"

    @pytest.mark.asyncio
    async def test_get_context_respects_max_recent_turns(self):
        mem = ConversationMemory(max_turns_full=20)
        session = mem.create_session()
        for i in range(15):
            mem.add_turn(session.id, "user", f"Turn {i}")
        context = await mem.get_context(session.id, max_recent_turns=5)
        assert len(context) == 5
        assert context[0].content == "Turn 10"

    @pytest.mark.asyncio
    async def test_get_context_includes_summary(self):
        mem = ConversationMemory(max_turns_full=2)
        session = mem.create_session()
        for i in range(5):
            mem.add_turn(session.id, "user", f"Turn {i}")
        session.summary = "Conversation summary"
        context = await mem.get_context(session.id, max_recent_turns=3)
        # Should have 1 system message (summary) + 3 recent turns
        assert context[0].role == "system"
        assert "summary" in context[0].content
        assert len(context) == 4

    @pytest.mark.asyncio
    async def test_compress_truncation_fallback(self):
        """compress() falls back to truncation when no LLM provider is set."""
        mem = ConversationMemory(llm_provider=None, max_turns_full=3)
        session = mem.create_session()
        for i in range(10):
            mem.add_turn(session.id, "user" if i % 2 == 0 else "assistant", f"Turn {i}")
        summary = await mem.compress(session.id)
        assert isinstance(summary, str)
        assert len(summary) > 0
        # Only max_turns_full turns should remain
        assert len(session.turns) == 3

    @pytest.mark.asyncio
    async def test_compress_with_llm(self):
        """compress() uses LLM when provider is available."""
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=MagicMock(content="LLM-generated summary"))

        mem = ConversationMemory(llm_provider=mock_llm, max_turns_full=3)
        session = mem.create_session()
        for i in range(10):
            mem.add_turn(session.id, "user" if i % 2 == 0 else "assistant", f"Turn {i}")
        summary = await mem.compress(session.id)
        assert summary == "LLM-generated summary"
        assert len(session.turns) == 3
        mock_llm.chat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compress_llm_error_uses_fallback(self):
        """If LLM call fails, compress() falls back to truncation."""
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=Exception("LLM failed"))

        mem = ConversationMemory(llm_provider=mock_llm, max_turns_full=3)
        session = mem.create_session()
        for i in range(10):
            mem.add_turn(session.id, "user", f"Turn {i}")
        summary = await mem.compress(session.id)
        # Fallback truncation produces a summary
        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_compress_on_session_with_few_turns(self):
        """compress() does nothing when turns <= max_turns_full."""
        mem = ConversationMemory(max_turns_full=10)
        session = mem.create_session()
        mem.add_turn(session.id, "user", "Hello")
        summary = await mem.compress(session.id)
        assert summary == ""
        assert len(session.turns) == 1

    @pytest.mark.asyncio
    async def test_compress_nonexistent_session(self):
        mem = ConversationMemory()
        result = await mem.compress("nonexistent")
        assert result == ""

    def test_clear_session(self):
        mem = ConversationMemory()
        session = mem.create_session()
        assert mem.clear_session(session.id) is True
        assert mem.get_session(session.id) is None

    def test_clear_session_not_found(self):
        mem = ConversationMemory()
        assert mem.clear_session("nonexistent") is False

    def test_list_sessions(self):
        mem = ConversationMemory()
        s1 = mem.create_session()
        s2 = mem.create_session()
        sessions = mem.list_sessions()
        assert len(sessions) == 2
        assert s1 in sessions
        assert s2 in sessions

    def test_list_sessions_empty(self):
        mem = ConversationMemory()
        assert mem.list_sessions() == []

    def test_token_count_auto_estimate(self):
        mem = ConversationMemory()
        session = mem.create_session()
        turn = mem.add_turn(session.id, "user", "Hello world")
        assert turn.token_count > 0
        assert turn.token_count == len("Hello world") // 2
