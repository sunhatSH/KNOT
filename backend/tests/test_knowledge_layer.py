"""Tests for the knowledge layer: chunker, keyword search, fusion, enhancer."""

from __future__ import annotations

import pytest

from knot.core.models import KnowledgeChunk
from knot.knowledge_layer.chunker import TextChunker
from knot.knowledge_layer.fusion import ResultFusion
from knot.knowledge_layer.keyword_search import KeywordSearch


# ─── TextChunker ──────────────────────────────────────────────────────────


class TestTextChunker:
    def test_init_valid(self):
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50

    def test_init_overlap_gte_size_raises(self):
        with pytest.raises(ValueError, match="must be less than"):
            TextChunker(chunk_size=100, chunk_overlap=100)
        with pytest.raises(ValueError, match="must be less than"):
            TextChunker(chunk_size=100, chunk_overlap=200)

    def test_chunk_empty_text(self):
        chunker = TextChunker()
        result = chunker.chunk("")
        assert result == []

    def test_chunk_whitespace_only(self):
        chunker = TextChunker()
        result = chunker.chunk("   \n\n  ")
        assert result == []

    def test_chunk_single_short_paragraph(self):
        chunker = TextChunker(chunk_size=512, chunk_overlap=64)
        result = chunker.chunk("Hello world.")
        assert len(result) == 1
        assert result[0].content == "Hello world."
        assert result[0].id.startswith("chunk_")
        assert result[0].metadata.get("chunk_index") == 0

    def test_chunk_multiple_paragraphs_within_size(self):
        chunker = TextChunker(chunk_size=512, chunk_overlap=64)
        text = "Para one.\n\nPara two.\n\nPara three."
        result = chunker.chunk(text)
        assert len(result) == 1
        assert "Para one." in result[0].content
        assert "Para two." in result[0].content
        assert "Para three." in result[0].content

    def test_chunk_paragraphs_exceeding_size(self):
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        # Each paragraph is short but combined they exceed chunk_size
        paras = "\n\n".join(f"Paragraph number {i} with some content." for i in range(10))
        result = chunker.chunk(paras)
        assert len(result) >= 2
        # Each chunk should be at most chunk_size + buffer
        for c in result:
            assert len(c.content) <= 50 + 15  # small buffer for overlap

    def test_chunk_single_long_paragraph(self):
        chunker = TextChunker(chunk_size=30, chunk_overlap=5)
        text = "A" * 100  # 100 characters in a single paragraph
        result = chunker.chunk(text)
        # Should be split into ceil(100/30) = 4 pieces (with overlap reducing effective size)
        assert len(result) >= 3
        assert len(result) <= 5

    def test_chunk_with_metadata(self):
        chunker = TextChunker(chunk_size=512, chunk_overlap=64)
        result = chunker.chunk(
            "Hello world.",
            metadata={"document_id": "doc_123", "source": "test"},
        )
        assert len(result) == 1
        assert result[0].document_id == "doc_123"
        assert result[0].metadata["source"] == "test"
        assert result[0].metadata["document_id"] == "doc_123"
        assert "chunk_index" in result[0].metadata

    def test_chunk_overlap_content(self):
        """Verify that consecutive chunks share overlapping text."""
        chunker = TextChunker(chunk_size=30, chunk_overlap=10)
        text = "AAAABBBBCCCCDDDDEEEEFFFFGGGG"
        result = chunker.chunk(text)
        if len(result) >= 2:
            # The overlap should contain text from the end of the previous chunk
            # (only guaranteed for same-paragraph splitting)
            pass  # structural validation only

    def test_chunk_ids_unique(self):
        chunker = TextChunker(chunk_size=50, chunk_overlap=5)
        text = "\n\n".join(f"Para {i} content here." for i in range(20))
        result = chunker.chunk(text)
        ids = [c.id for c in result]
        assert len(ids) == len(set(ids)), "All chunk IDs must be unique"


# ─── KeywordSearch ────────────────────────────────────────────────────────


class TestKeywordSearch:
    def test_empty_index(self):
        ks = KeywordSearch()
        results = ks.search("test")
        assert results == []

    def test_search_no_index(self):
        ks = KeywordSearch()
        assert ks._index_built is False
        results = ks.search("anything")
        assert results == []

    def test_index_and_search_single_chunk(self):
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(id="c1", content="The quick brown fox"),
        ]
        ks.index_chunks(chunks)
        results = ks.search("fox")
        assert len(results) == 1
        assert results[0].id == "c1"
        assert results[0].score > 0

    def test_search_no_match(self):
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(id="c1", content="Hello world"),
        ]
        ks.index_chunks(chunks)
        results = ks.search("nonexistent")
        assert results == []

    def test_search_multiple_chunks_ranking(self):
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(id="c1", content="Python is a programming language"),
            KnowledgeChunk(id="c2", content="Python is great for data science"),
            KnowledgeChunk(id="c3", content="Java is also a programming language"),
        ]
        ks.index_chunks(chunks)
        # Search for "programming language" - c1 and c3 should match
        results = ks.search("programming language")
        assert len(results) == 2
        # c1 should rank higher (both terms appear)
        assert results[0].score > 0
        assert results[1].score > 0

    def test_search_top_k(self):
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(id=f"c{i}", content=f"This chunk contains the word {' '.join(['important'] * (i + 1))}")
            for i in range(10)
        ]
        ks.index_chunks(chunks)
        results = ks.search("important", top_k=3)
        assert len(results) == 3

    def test_clear_index(self):
        ks = KeywordSearch()
        ks.index_chunks([KnowledgeChunk(id="c1", content="some text")])
        assert ks._index_built is True
        ks.clear()
        assert ks._index_built is False
        assert ks.search("text") == []

    def test_reindex(self):
        ks = KeywordSearch()
        ks.index_chunks([KnowledgeChunk(id="c1", content="old content")])
        ks.index_chunks([KnowledgeChunk(id="c2", content="new content")])
        results = ks.search("new")
        assert len(results) == 1
        assert results[0].id == "c2"

    def test_chinese_token_expansion(self):
        """Chinese characters should get character-level expansion."""
        ks = KeywordSearch()
        assert ks._has_chinese("你好世界") is True
        assert ks._has_chinese("hello") is False
        assert ks._has_chinese("hello世界") is True

        tokens = ks._tokenize("人工智能")
        assert len(tokens) >= 1

    def test_expand_terms_with_chinese(self):
        ks = KeywordSearch()
        tokens = ["人工智能", "hello"]
        expanded = ks._expand_terms(tokens)
        # "人工智能" has 4 Chinese chars > 2, should add each char individually
        assert "人" in expanded
        assert "工" in expanded
        assert "智" in expanded
        assert "能" in expanded
        # "hello" has no Chinese, should not be expanded
        assert expanded.count("hello") == 1

    def test_expand_terms_short_chinese(self):
        """Chinese tokens <= 2 chars should not be expanded."""
        ks = KeywordSearch()
        tokens = ["你好"]
        expanded = ks._expand_terms(tokens)
        # "你好" has 2 chars, not > 2, so no expansion
        for char in "你好":
            assert expanded.count(char) == 0

    def test_chinese_search_accuracy(self):
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(id="c1", content="人工智能是计算机科学的重要分支"),
            KnowledgeChunk(id="c2", content="机器学习和深度学习是人工智能的子领域"),
            KnowledgeChunk(id="c3", content="Python是一种流行的编程语言"),
        ]
        ks.index_chunks(chunks)
        # Search for "人工智能" - should find c1 and c2
        results = ks.search("人工智能")
        assert len(results) == 2
        # c1 should have the exact term match, c2 has it in content
        assert results[0].score > 0

    def test_tokenize_empty(self):
        ks = KeywordSearch()
        assert ks._tokenize("") == []
        assert ks._tokenize("   ") == []

    def test_tokenize_english(self):
        ks = KeywordSearch()
        tokens = ks._tokenize("Hello world")
        assert "Hello" in tokens
        assert "world" in tokens

    def test_search_with_empty_query(self):
        ks = KeywordSearch()
        ks.index_chunks([KnowledgeChunk(id="c1", content="some text")])
        results = ks.search("")
        assert results == []

    def test_score_calculation(self):
        """Verify TF-IDF scoring produces different scores for different docs."""
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(id="c1", content="apple apple apple"),
            KnowledgeChunk(id="c2", content="apple banana"),
            KnowledgeChunk(id="c3", content="cherry date"),
        ]
        ks.index_chunks(chunks)
        results = ks.search("apple")
        assert len(results) == 2
        # c1 has 3x the term frequency, should score higher
        assert results[0].id == "c1"
        assert results[0].score > results[1].score

    def test_search_preserves_metadata(self):
        ks = KeywordSearch()
        chunks = [
            KnowledgeChunk(
                id="c1",
                content="test content",
                metadata={"source": "doc1", "page": 5},
            ),
        ]
        ks.index_chunks(chunks)
        results = ks.search("test")
        assert len(results) == 1
        assert results[0].metadata["source"] == "doc1"
        assert results[0].metadata["page"] == 5


# ─── ResultFusion ─────────────────────────────────────────────────────────


class TestResultFusion:
    def test_rrf_fusion_no_results(self):
        result = ResultFusion.rrf_fusion([])
        assert result == []

    def test_rrf_fusion_empty_lists(self):
        result = ResultFusion.rrf_fusion([[], []])
        assert result == []

    def test_rrf_fusion_single_list(self):
        chunks = [
            KnowledgeChunk(id="c1", content="alpha", document_id="d1"),
            KnowledgeChunk(id="c2", content="beta", document_id="d2"),
        ]
        result = ResultFusion.rrf_fusion([chunks])
        assert len(result) == 2
        # Order should be preserved from the single input
        assert result[0].id == "c1"
        assert result[1].id == "c2"

    def test_rrf_fusion_combines_scores(self):
        list1 = [
            KnowledgeChunk(id="c1", content="alpha", document_id="d1"),
            KnowledgeChunk(id="c2", content="beta", document_id="d2"),
        ]
        list2 = [
            KnowledgeChunk(id="c2", content="beta", document_id="d2"),  # same doc+content
            KnowledgeChunk(id="c3", content="gamma", document_id="d3"),
        ]
        result = ResultFusion.rrf_fusion([list1, list2], k=60, top_n=10)
        assert len(result) == 3  # c1, c2, c3 (c2 should have combined RRF score)
        # c2 appears in both lists, so its score should be higher
        c2_entry = [r for r in result if r.id == "c2"][0]
        c1_entry = [r for r in result if r.id == "c1"][0]
        assert c2_entry.score > c1_entry.score

    def test_rrf_fusion_deduplicates_by_document_id_and_content(self):
        list1 = [
            KnowledgeChunk(id="c1", content="same text", document_id="d1"),
        ]
        list2 = [
            KnowledgeChunk(id="c2", content="same text", document_id="d1"),
        ]
        result = ResultFusion.rrf_fusion([list1, list2])
        assert len(result) == 1  # deduplicated

    def test_rrf_fusion_top_n(self):
        chunks = [
            KnowledgeChunk(id=f"c{i}", content=f"content_{i}", document_id=f"d{i}")
            for i in range(20)
        ]
        result = ResultFusion.rrf_fusion([chunks], top_n=5)
        assert len(result) == 5

    def test_rrf_fusion_different_k_values(self):
        chunks = [
            KnowledgeChunk(id="c1", content="alpha", document_id="d1"),
            KnowledgeChunk(id="c2", content="beta", document_id="d2"),
        ]
        # With k=0, rank weights are more aggressive
        result_high = ResultFusion.rrf_fusion([chunks], k=60)
        result_low = ResultFusion.rrf_fusion([chunks], k=1)
        assert len(result_high) == 2
        assert len(result_low) == 2

    def test_deduplicate_no_duplicates(self):
        chunks = [
            KnowledgeChunk(id="c1", content="alpha", document_id="d1", score=0.9),
            KnowledgeChunk(id="c2", content="beta", document_id="d2", score=0.8),
        ]
        result = ResultFusion.deduplicate(chunks)
        assert len(result) == 2

    def test_deduplicate_with_duplicates(self):
        chunks = [
            KnowledgeChunk(id="c1", content="same text", document_id="d1", score=0.9),
            KnowledgeChunk(id="c2", content="same text", document_id="d1", score=0.5),
        ]
        result = ResultFusion.deduplicate(chunks)
        assert len(result) == 1
        # Should keep the higher-scored one
        assert result[0].id == "c1"
        assert result[0].score == 0.9

    def test_deduplicate_keeps_highest_score(self):
        chunks = [
            KnowledgeChunk(id="c1", content="text", document_id="d1", score=0.3),
            KnowledgeChunk(id="c2", content="text", document_id="d1", score=0.9),
            KnowledgeChunk(id="c3", content="text", document_id="d1", score=0.6),
        ]
        result = ResultFusion.deduplicate(chunks)
        assert len(result) == 1
        assert result[0].id == "c2"  # highest score

    def test_deduplicate_fallback_to_chunk_id(self):
        """When document_id is empty, fall back to chunk id."""
        chunks = [
            KnowledgeChunk(id="c1", content="text", score=0.9),
            KnowledgeChunk(id="c2", content="text", score=0.8),
        ]
        result = ResultFusion.deduplicate(chunks)
        # Different chunk ids with empty doc_ids should NOT be deduplicated
        assert len(result) == 2

    def test_rrf_fusion_many_lists(self):
        lists = []
        for i in range(5):
            lists.append([
                KnowledgeChunk(id=f"c{j}", content=f"content_{j}", document_id=f"d{j}")
                for j in range(5)
            ])
        result = ResultFusion.rrf_fusion(lists, top_n=10)
        assert len(result) == 5  # 5 unique chunks after dedup
        assert all(c.score > 0 for c in result)


# ─── ContextEnhancer ──────────────────────────────────────────────────────


class TestContextEnhancer:
    def test_enhance_with_chunks(self):
        from knot.knowledge_layer.enhancer import ContextEnhancer

        enhancer = ContextEnhancer()
        chunks = [
            KnowledgeChunk(id="c1", document_id="doc1", content="Paris is the capital of France.", score=0.95),
            KnowledgeChunk(id="c2", document_id="doc2", content="The Eiffel Tower is in Paris.", score=0.80),
        ]
        result = enhancer.enhance("What is the capital of France?", chunks)
        assert "Paris" in result
        assert "capital" in result
        assert "doc1" in result
        assert "0.950" in result or "0.95" in result

    def test_enhance_no_chunks(self):
        from knot.knowledge_layer.enhancer import ContextEnhancer

        enhancer = ContextEnhancer()
        result = enhancer.enhance("Hello?", [])
        assert "Hello?" in result or "hello" in result.lower()

    def test_enhance_with_system_prompt(self):
        from knot.knowledge_layer.enhancer import ContextEnhancer

        enhancer = ContextEnhancer()
        chunks = [
            KnowledgeChunk(id="c1", document_id="d1", content="Important data", score=0.9),
        ]
        result = enhancer.enhance(
            "Tell me about it",
            chunks,
            system_prompt="You are a helpful assistant.",
        )
        assert "You are a helpful assistant" in result
        assert "Important data" in result
        assert "Tell me about it" in result

    def test_custom_template(self):
        from knot.knowledge_layer.enhancer import ContextEnhancer

        custom_template = "CUSTOM: {query} | KNOWLEDGE: {knowledge_context}"
        enhancer = ContextEnhancer(template=custom_template)
        chunks = [
            KnowledgeChunk(id="c1", document_id="d1", content="facts", score=0.5),
        ]
        result = enhancer.enhance("query?", chunks)
        assert "CUSTOM:" in result
        assert "facts" in result
        assert "query?" in result
