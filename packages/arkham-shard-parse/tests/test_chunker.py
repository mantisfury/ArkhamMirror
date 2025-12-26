"""
Parse Shard - Chunker Tests

Tests for the TextChunker class.
"""

import pytest
from arkham_shard_parse.chunker import TextChunker


class TestTextChunkerInitialization:
    """Tests for TextChunker initialization."""

    def test_default_initialization(self):
        """Test chunker initializes with defaults."""
        chunker = TextChunker()
        assert chunker.chunk_size == 500
        assert chunker.overlap == 50
        assert chunker.method == "fixed"

    def test_custom_initialization(self):
        """Test chunker initializes with custom values."""
        chunker = TextChunker(
            chunk_size=1000,
            overlap=100,
            method="sentence",
        )
        assert chunker.chunk_size == 1000
        assert chunker.overlap == 100
        assert chunker.method == "sentence"


class TestFixedChunking:
    """Tests for fixed-size chunking."""

    def test_chunk_small_text(self):
        """Test chunking text smaller than chunk size."""
        chunker = TextChunker(chunk_size=100, overlap=10, method="fixed")

        text = "Short text."
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 1
        assert chunks[0].text == "Short text."
        assert chunks[0].document_id == "doc-123"
        assert chunks[0].chunk_index == 0

    def test_chunk_exact_size(self):
        """Test chunking text exactly chunk size."""
        chunker = TextChunker(chunk_size=10, overlap=0, method="fixed")

        text = "0123456789"  # Exactly 10 chars
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 1
        assert chunks[0].text == "0123456789"

    def test_chunk_with_overlap(self):
        """Test chunking with overlap."""
        chunker = TextChunker(chunk_size=10, overlap=3, method="fixed")

        text = "0123456789ABCDEFGHIJ"  # 20 chars
        chunks = chunker.chunk_text(text, "doc-123")

        # With size=10 and overlap=3, step=7
        # Chunk 0: 0-10 (0123456789)
        # Chunk 1: 7-17 (789ABCDEFG)
        # Chunk 2: 14-20 (FGHIJ)
        assert len(chunks) == 3
        assert chunks[0].text == "0123456789"
        assert chunks[1].text == "789ABCDEFG"

    def test_chunk_indices(self):
        """Test that chunk indices are sequential."""
        chunker = TextChunker(chunk_size=10, overlap=0, method="fixed")

        text = "0" * 30
        chunks = chunker.chunk_text(text, "doc-123")

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunk_char_positions(self):
        """Test that char positions are tracked."""
        chunker = TextChunker(chunk_size=10, overlap=0, method="fixed")

        text = "0123456789ABCDEFGHIJ"
        chunks = chunker.chunk_text(text, "doc-123")

        assert chunks[0].char_start == 0
        assert chunks[0].char_end == 10
        assert chunks[1].char_start == 10
        assert chunks[1].char_end == 20

    def test_chunk_method_set(self):
        """Test that chunk method is set to 'fixed'."""
        chunker = TextChunker(chunk_size=100, method="fixed")

        chunks = chunker.chunk_text("Some text.", "doc-123")

        assert chunks[0].chunk_method == "fixed"

    def test_chunk_token_count(self):
        """Test that token count is calculated."""
        chunker = TextChunker(chunk_size=100, method="fixed")

        text = "One two three four five."
        chunks = chunker.chunk_text(text, "doc-123")

        assert chunks[0].token_count == 5

    def test_chunk_with_page_number(self):
        """Test chunking with page number."""
        chunker = TextChunker(chunk_size=100, method="fixed")

        chunks = chunker.chunk_text("Some text.", "doc-123", page_number=5)

        assert chunks[0].page_number == 5

    def test_chunk_ids_are_unique(self):
        """Test that chunk IDs are unique."""
        chunker = TextChunker(chunk_size=10, overlap=0, method="fixed")

        text = "0" * 100
        chunks = chunker.chunk_text(text, "doc-123")

        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))  # All unique

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = TextChunker(chunk_size=100, method="fixed")

        chunks = chunker.chunk_text("", "doc-123")

        assert chunks == []


class TestSentenceChunking:
    """Tests for sentence-based chunking."""

    def test_chunk_single_sentence(self):
        """Test chunking a single sentence."""
        chunker = TextChunker(chunk_size=100, method="sentence")

        text = "This is a single sentence."
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 1
        assert chunks[0].text == "This is a single sentence"

    def test_chunk_multiple_sentences(self):
        """Test chunking multiple sentences."""
        chunker = TextChunker(chunk_size=1000, method="sentence")

        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk_text(text, "doc-123")

        # All sentences fit in one chunk
        assert len(chunks) == 1
        assert "First sentence" in chunks[0].text
        assert "Third sentence" in chunks[0].text

    def test_chunk_splits_at_size(self):
        """Test that sentences are split when exceeding chunk size."""
        chunker = TextChunker(chunk_size=30, method="sentence")

        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk_text(text, "doc-123")

        # Should split into multiple chunks
        assert len(chunks) >= 2

    def test_chunk_method_set_sentence(self):
        """Test that chunk method is set to 'sentence'."""
        chunker = TextChunker(chunk_size=100, method="sentence")

        chunks = chunker.chunk_text("One sentence.", "doc-123")

        assert chunks[0].chunk_method == "sentence"

    def test_chunk_exclamation_marks(self):
        """Test chunking respects exclamation marks."""
        chunker = TextChunker(chunk_size=1000, method="sentence")

        text = "Hello! How are you! Fine thanks!"
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 1
        # All three "sentences" combined
        assert "Hello" in chunks[0].text
        assert "Fine thanks" in chunks[0].text

    def test_chunk_question_marks(self):
        """Test chunking respects question marks."""
        chunker = TextChunker(chunk_size=1000, method="sentence")

        text = "What? Why? How?"
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 1


class TestSemanticChunking:
    """Tests for semantic chunking (falls back to sentence)."""

    def test_semantic_falls_back_to_sentence(self):
        """Test that semantic chunking falls back to sentence chunking."""
        chunker = TextChunker(chunk_size=100, method="semantic")

        text = "First sentence. Second sentence."
        chunks = chunker.chunk_text(text, "doc-123")

        # Should work same as sentence chunking
        assert len(chunks) >= 1
        # Method might still be recorded as sentence since it falls back
        assert chunks[0].chunk_method == "sentence"


class TestChunkTextMethod:
    """Tests for the main chunk_text method."""

    def test_routes_to_fixed(self):
        """Test that method='fixed' routes to fixed chunking."""
        chunker = TextChunker(method="fixed")

        chunks = chunker.chunk_text("Test text.", "doc-123")

        assert chunks[0].chunk_method == "fixed"

    def test_routes_to_sentence(self):
        """Test that method='sentence' routes to sentence chunking."""
        chunker = TextChunker(method="sentence")

        chunks = chunker.chunk_text("Test text.", "doc-123")

        assert chunks[0].chunk_method == "sentence"

    def test_routes_to_semantic(self):
        """Test that method='semantic' routes to semantic chunking."""
        chunker = TextChunker(method="semantic")

        chunks = chunker.chunk_text("Test text.", "doc-123")

        # Falls back to sentence
        assert chunks[0].chunk_method == "sentence"

    def test_unknown_method_defaults_to_fixed(self):
        """Test that unknown method defaults to fixed."""
        chunker = TextChunker(method="unknown")

        chunks = chunker.chunk_text("Test text.", "doc-123")

        assert chunks[0].chunk_method == "fixed"


class TestChunkingEdgeCases:
    """Edge case tests for chunking."""

    def test_very_long_text(self):
        """Test chunking very long text."""
        chunker = TextChunker(chunk_size=100, overlap=10, method="fixed")

        text = "x" * 10000
        chunks = chunker.chunk_text(text, "doc-123")

        # Should create many chunks without error
        assert len(chunks) > 50

    def test_only_whitespace(self):
        """Test chunking only whitespace text."""
        chunker = TextChunker(chunk_size=100, method="fixed")

        chunks = chunker.chunk_text("   ", "doc-123")

        # Should create one chunk with whitespace
        assert len(chunks) == 1

    def test_special_characters(self):
        """Test chunking text with special characters."""
        chunker = TextChunker(chunk_size=100, method="fixed")

        text = "Hello! @#$%^&*() world. Testing... 123."
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_unicode_text(self):
        """Test chunking unicode text."""
        chunker = TextChunker(chunk_size=100, method="fixed")

        text = "Hello mundo. Bonjour monde."
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 1
        assert "mundo" in chunks[0].text

    def test_newlines_in_text(self):
        """Test chunking text with newlines."""
        chunker = TextChunker(chunk_size=100, method="fixed")

        text = "Line one.\nLine two.\nLine three."
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 1
        assert "\n" in chunks[0].text

    def test_overlap_larger_than_chunk(self):
        """Test chunking when overlap >= chunk_size uses step=1 for safety."""
        chunker = TextChunker(chunk_size=10, overlap=15, method="fixed")

        text = "0123456789ABCDEFGHIJ"
        # With infinite loop protection, step = max(1, 10 - 15) = 1
        # This creates many overlapping chunks but doesn't hang
        chunks = chunker.chunk_text(text, "doc-123")

        # Should produce chunks without infinite loop
        assert len(chunks) >= 1
        # With step=1, we get chunks starting at each position
        assert len(chunks) == len(text)

    def test_zero_overlap(self):
        """Test chunking with zero overlap."""
        chunker = TextChunker(chunk_size=5, overlap=0, method="fixed")

        text = "0123456789"
        chunks = chunker.chunk_text(text, "doc-123")

        assert len(chunks) == 2
        assert chunks[0].text == "01234"
        assert chunks[1].text == "56789"

    def test_document_id_required(self):
        """Test that document_id is set on all chunks."""
        chunker = TextChunker(chunk_size=10, method="fixed")

        text = "0" * 50
        chunks = chunker.chunk_text(text, "my-doc-id")

        for chunk in chunks:
            assert chunk.document_id == "my-doc-id"
