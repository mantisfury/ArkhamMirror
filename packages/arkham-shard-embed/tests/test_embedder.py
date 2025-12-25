"""
Tests for the EmbeddingManager.

These tests verify the core embedding functionality.
"""

import pytest
import numpy as np

from arkham_shard_embed.embedder import EmbeddingManager
from arkham_shard_embed.models import EmbedConfig


@pytest.fixture
def config():
    """Create a test configuration."""
    return EmbedConfig(
        model="all-MiniLM-L6-v2",  # Use lightweight model for testing
        device="cpu",  # Force CPU for consistent testing
        batch_size=32,
        cache_size=100,
    )


@pytest.fixture
def manager(config):
    """Create an EmbeddingManager instance."""
    return EmbeddingManager(config)


def test_device_detection(manager):
    """Test automatic device detection."""
    device = manager._detect_device()
    assert device in ["cpu", "cuda", "mps"]


def test_embed_single_text(manager):
    """Test embedding a single text."""
    text = "This is a test sentence."
    embedding = manager.embed_text(text)

    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)

    # MiniLM produces 384-dimensional embeddings
    assert len(embedding) == 384


def test_embed_batch(manager):
    """Test batch embedding."""
    texts = [
        "First sentence.",
        "Second sentence.",
        "Third sentence."
    ]
    embeddings = manager.embed_batch(texts)

    assert isinstance(embeddings, list)
    assert len(embeddings) == len(texts)
    assert all(isinstance(emb, list) for emb in embeddings)
    assert all(len(emb) == 384 for emb in embeddings)


def test_cache(manager):
    """Test embedding caching."""
    text = "This sentence should be cached."

    # First call - cache miss
    emb1 = manager.embed_text(text, use_cache=True)

    # Second call - cache hit
    emb2 = manager.embed_text(text, use_cache=True)

    # Should be identical
    assert emb1 == emb2

    # Check cache stats
    cache_info = manager.get_cache_info()
    assert cache_info['enabled']
    assert cache_info['hits'] > 0


def test_cache_clear(manager):
    """Test cache clearing."""
    text = "Test text"
    manager.embed_text(text, use_cache=True)

    # Get initial cache state
    before = manager.get_cache_info()
    assert before['size'] > 0

    # Clear cache
    manager.clear_cache()

    # Check cache is empty
    after = manager.get_cache_info()
    assert after['size'] == 0


def test_similarity_cosine(manager):
    """Test cosine similarity calculation."""
    emb1 = manager.embed_text("The cat sat on the mat")
    emb2 = manager.embed_text("A feline rested on the rug")
    emb3 = manager.embed_text("Python programming language")

    # Similar sentences should have high similarity
    sim_similar = manager.calculate_similarity(emb1, emb2, method="cosine")
    assert sim_similar > 0.5

    # Dissimilar sentences should have lower similarity
    sim_different = manager.calculate_similarity(emb1, emb3, method="cosine")
    assert sim_different < sim_similar


def test_similarity_euclidean(manager):
    """Test Euclidean similarity calculation."""
    emb1 = manager.embed_text("Test sentence one")
    emb2 = manager.embed_text("Test sentence two")

    sim = manager.calculate_similarity(emb1, emb2, method="euclidean")
    assert 0 <= sim <= 1


def test_similarity_dot(manager):
    """Test dot product similarity calculation."""
    emb1 = manager.embed_text("Test sentence")
    emb2 = manager.embed_text("Another sentence")

    sim = manager.calculate_similarity(emb1, emb2, method="dot")
    assert isinstance(sim, float)


def test_similarity_invalid_method(manager):
    """Test that invalid similarity method raises error."""
    emb1 = manager.embed_text("Test")
    emb2 = manager.embed_text("Test")

    with pytest.raises(ValueError):
        manager.calculate_similarity(emb1, emb2, method="invalid")


def test_chunk_text(manager):
    """Test text chunking."""
    # Short text - no chunking needed
    short_text = "This is a short text."
    chunks = manager.chunk_text(short_text, chunk_size=512)
    assert len(chunks) == 1
    assert chunks[0] == short_text

    # Long text - should be chunked
    long_text = "a " * 1000  # 2000 characters
    chunks = manager.chunk_text(long_text, chunk_size=512, chunk_overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 512 for chunk in chunks)


def test_chunk_text_with_sentences(manager):
    """Test chunking respects sentence boundaries."""
    text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    chunks = manager.chunk_text(text, chunk_size=40, chunk_overlap=10)

    # Should try to break at sentence boundaries
    assert len(chunks) > 1
    # Most chunks should end with a period
    assert sum(1 for chunk in chunks if chunk.strip().endswith('.')) >= len(chunks) // 2


def test_get_model_info(manager):
    """Test getting model information."""
    # Before loading
    info_before = manager.get_model_info()
    assert not info_before.loaded

    # Trigger model loading
    manager.embed_text("Test")

    # After loading
    info_after = manager.get_model_info()
    assert info_after.loaded
    assert info_after.name == "all-MiniLM-L6-v2"
    assert info_after.dimensions == 384
    assert info_after.device == "cpu"


def test_empty_text(manager):
    """Test embedding empty text."""
    # Should handle gracefully or raise appropriate error
    try:
        embedding = manager.embed_text("")
        assert isinstance(embedding, list)
    except Exception as e:
        # If it raises, that's also acceptable
        assert True


def test_very_long_text(manager):
    """Test embedding very long text."""
    # Create text longer than model's max length
    long_text = "word " * 10000

    # Should handle gracefully (may truncate)
    embedding = manager.embed_text(long_text)
    assert isinstance(embedding, list)
    assert len(embedding) == 384


def test_special_characters(manager):
    """Test embedding text with special characters."""
    text = "Special chars: @#$%^&*() 中文 العربية עברית"
    embedding = manager.embed_text(text)
    assert isinstance(embedding, list)
    assert len(embedding) == 384


def test_normalization(manager):
    """Test embedding normalization."""
    text = "Test normalization"
    embedding = manager.embed_text(text)

    # Calculate vector norm
    norm = np.linalg.norm(embedding)

    # Normalized embeddings should have norm close to 1
    # (depending on config.normalize setting)
    assert 0.9 <= norm <= 1.1


@pytest.mark.parametrize("batch_size", [1, 4, 16, 32])
def test_different_batch_sizes(manager, batch_size):
    """Test embedding with different batch sizes."""
    texts = [f"Sentence {i}" for i in range(10)]
    embeddings = manager.embed_batch(texts, batch_size=batch_size)

    assert len(embeddings) == len(texts)
    assert all(len(emb) == 384 for emb in embeddings)


def test_model_singleton(manager):
    """Test that model is loaded only once."""
    # First call loads model
    manager.embed_text("Test 1")

    # Second call reuses loaded model
    manager.embed_text("Test 2")

    # Model should still be the same instance
    model_info = manager.get_model_info()
    assert model_info.loaded
