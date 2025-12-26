"""
Search Shard - API Tests

Tests for all FastAPI endpoints.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_search.api import router, init_api
from arkham_shard_search.models import SearchResultItem


@pytest.fixture
def mock_semantic_engine():
    """Create mock semantic search engine."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value=[])
    mock.find_similar = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_keyword_engine():
    """Create mock keyword search engine."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value=[])
    mock.suggest = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_hybrid_engine():
    """Create mock hybrid search engine."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_filter_optimizer():
    """Create mock filter optimizer."""
    mock = MagicMock()
    mock.get_available_filters = AsyncMock(return_value={
        "file_types": [],
        "entities": [],
        "projects": [],
        "date_ranges": {},
    })
    return mock


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    mock = MagicMock()
    mock.emit = AsyncMock()
    return mock


@pytest.fixture
def client(
    mock_semantic_engine,
    mock_keyword_engine,
    mock_hybrid_engine,
    mock_filter_optimizer,
    mock_event_bus,
):
    """Create test client with mocked dependencies."""
    init_api(
        semantic_engine=mock_semantic_engine,
        keyword_engine=mock_keyword_engine,
        hybrid_engine=mock_hybrid_engine,
        filter_optimizer=mock_filter_optimizer,
        event_bus=mock_event_bus,
    )

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestSearchEndpoint:
    """Tests for POST /api/search endpoint."""

    def test_search_basic(self, client, mock_hybrid_engine):
        """Test basic search request."""
        mock_hybrid_engine.search.return_value = [
            SearchResultItem(
                doc_id="doc-1",
                chunk_id="chunk-1",
                title="Test Document",
                excerpt="This is a test.",
                score=0.9,
            )
        ]

        response = client.post(
            "/api/search/",
            json={"query": "test search"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test search"
        assert data["mode"] == "hybrid"
        assert len(data["items"]) == 1
        assert data["total"] == 1

    def test_search_with_mode_semantic(self, client, mock_semantic_engine):
        """Test search with semantic mode."""
        response = client.post(
            "/api/search/",
            json={"query": "test", "mode": "semantic"},
        )

        assert response.status_code == 200
        mock_semantic_engine.search.assert_called_once()

    def test_search_with_mode_keyword(self, client, mock_keyword_engine):
        """Test search with keyword mode."""
        response = client.post(
            "/api/search/",
            json={"query": "test", "mode": "keyword"},
        )

        assert response.status_code == 200
        mock_keyword_engine.search.assert_called_once()

    def test_search_with_invalid_mode(self, client):
        """Test search with invalid mode returns 400."""
        response = client.post(
            "/api/search/",
            json={"query": "test", "mode": "invalid"},
        )

        assert response.status_code == 400
        assert "Invalid search mode" in response.json()["detail"]

    def test_search_with_filters(self, client, mock_hybrid_engine):
        """Test search with filters."""
        response = client.post(
            "/api/search/",
            json={
                "query": "test",
                "filters": {
                    "file_types": ["pdf"],
                    "min_score": 0.5,
                },
            },
        )

        assert response.status_code == 200
        mock_hybrid_engine.search.assert_called_once()

    def test_search_with_invalid_filters(self, client):
        """Test search with invalid filters returns 400."""
        response = client.post(
            "/api/search/",
            json={
                "query": "test",
                "filters": {
                    "min_score": 1.5,  # Invalid: > 1.0
                },
            },
        )

        assert response.status_code == 400
        assert "Minimum score" in response.json()["detail"]

    def test_search_with_pagination(self, client, mock_hybrid_engine):
        """Test search with pagination parameters."""
        response = client.post(
            "/api/search/",
            json={
                "query": "test",
                "limit": 50,
                "offset": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["offset"] == 10

    def test_search_with_sort_options(self, client, mock_hybrid_engine):
        """Test search with sort options."""
        response = client.post(
            "/api/search/",
            json={
                "query": "test",
                "sort_by": "date",
                "sort_order": "asc",
            },
        )

        assert response.status_code == 200

    def test_search_with_weights(self, client, mock_hybrid_engine):
        """Test search with custom weights."""
        response = client.post(
            "/api/search/",
            json={
                "query": "test",
                "semantic_weight": 0.8,
                "keyword_weight": 0.2,
            },
        )

        assert response.status_code == 200

    def test_search_emits_event(self, client, mock_hybrid_engine, mock_event_bus):
        """Test search emits event."""
        response = client.post(
            "/api/search/",
            json={"query": "test"},
        )

        assert response.status_code == 200
        mock_event_bus.emit.assert_called_once()
        call_args = mock_event_bus.emit.call_args
        assert call_args[0][0] == "search.query.executed"

    def test_search_duration_tracked(self, client, mock_hybrid_engine):
        """Test search tracks duration."""
        response = client.post(
            "/api/search/",
            json={"query": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "duration_ms" in data
        assert data["duration_ms"] >= 0


class TestSearchNotInitialized:
    """Tests for search when service not initialized."""

    def test_search_not_initialized(self):
        """Test search when engines not initialized."""
        init_api(
            semantic_engine=None,
            keyword_engine=None,
            hybrid_engine=None,
            filter_optimizer=None,
            event_bus=None,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/search/",
            json={"query": "test"},
        )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestSemanticSearchEndpoint:
    """Tests for POST /api/search/semantic endpoint."""

    def test_semantic_search(self, client, mock_semantic_engine):
        """Test semantic-only search."""
        response = client.post(
            "/api/search/semantic",
            json={"query": "test"},
        )

        assert response.status_code == 200
        mock_semantic_engine.search.assert_called_once()


class TestKeywordSearchEndpoint:
    """Tests for POST /api/search/keyword endpoint."""

    def test_keyword_search(self, client, mock_keyword_engine):
        """Test keyword-only search."""
        response = client.post(
            "/api/search/keyword",
            json={"query": "test"},
        )

        assert response.status_code == 200
        mock_keyword_engine.search.assert_called_once()


class TestSuggestEndpoint:
    """Tests for GET /api/search/suggest endpoint."""

    def test_suggest_basic(self, client, mock_keyword_engine):
        """Test autocomplete suggestions."""
        mock_keyword_engine.suggest.return_value = [
            ("machine learning", 0.9),
            ("machine vision", 0.7),
        ]

        response = client.get("/api/search/suggest?q=mach")

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 2
        assert data["suggestions"][0]["text"] == "machine learning"

    def test_suggest_empty_query(self, client, mock_keyword_engine):
        """Test suggest with empty query returns 422 due to min_length validation."""
        response = client.get("/api/search/suggest?q=")

        # The API has Query(min_length=1), so empty query is validation error
        assert response.status_code == 422

    def test_suggest_with_limit(self, client, mock_keyword_engine):
        """Test suggest with custom limit."""
        mock_keyword_engine.suggest.return_value = []

        response = client.get("/api/search/suggest?q=test&limit=5")

        assert response.status_code == 200
        mock_keyword_engine.suggest.assert_called_with("test", limit=5)


class TestSuggestNotInitialized:
    """Tests for suggest when service not initialized."""

    def test_suggest_not_initialized(self):
        """Test suggest when keyword engine not initialized."""
        init_api(
            semantic_engine=MagicMock(),
            keyword_engine=None,
            hybrid_engine=MagicMock(),
            filter_optimizer=MagicMock(),
            event_bus=MagicMock(),
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/search/suggest?q=test")

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestSimilarDocumentsEndpoint:
    """Tests for POST /api/search/similar/{doc_id} endpoint."""

    def test_find_similar(self, client, mock_semantic_engine):
        """Test finding similar documents."""
        mock_semantic_engine.find_similar.return_value = [
            SearchResultItem(
                doc_id="doc-2",
                chunk_id=None,
                title="Similar Doc",
                excerpt="...",
                score=0.85,
            )
        ]

        response = client.post("/api/search/similar/doc-1")

        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "doc-1"
        assert len(data["similar"]) == 1
        assert data["total"] == 1

    def test_find_similar_with_options(self, client, mock_semantic_engine):
        """Test find similar with custom options."""
        response = client.post(
            "/api/search/similar/doc-1?limit=20&min_similarity=0.7"
        )

        assert response.status_code == 200
        mock_semantic_engine.find_similar.assert_called_with(
            doc_id="doc-1",
            limit=20,
            min_similarity=0.7,
        )


class TestSimilarNotInitialized:
    """Tests for similar when service not initialized."""

    def test_similar_not_initialized(self):
        """Test find similar when semantic engine not initialized."""
        init_api(
            semantic_engine=None,
            keyword_engine=MagicMock(),
            hybrid_engine=MagicMock(),
            filter_optimizer=MagicMock(),
            event_bus=MagicMock(),
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post("/api/search/similar/doc-1")

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestFiltersEndpoint:
    """Tests for GET /api/search/filters endpoint."""

    def test_get_filters(self, client, mock_filter_optimizer):
        """Test getting available filters."""
        response = client.get("/api/search/filters")

        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "file_types" in data["available"]
        assert "entities" in data["available"]
        assert "projects" in data["available"]
        assert "date_ranges" in data["available"]

    def test_get_filters_with_query(self, client, mock_filter_optimizer):
        """Test getting filters scoped to query."""
        response = client.get("/api/search/filters?q=test")

        assert response.status_code == 200
        mock_filter_optimizer.get_available_filters.assert_called_with("test")


class TestFiltersNotInitialized:
    """Tests for filters when service not initialized."""

    def test_filters_not_initialized(self):
        """Test get filters when optimizer not initialized."""
        init_api(
            semantic_engine=MagicMock(),
            keyword_engine=MagicMock(),
            hybrid_engine=MagicMock(),
            filter_optimizer=None,
            event_bus=MagicMock(),
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/search/filters")

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestSearchErrorHandling:
    """Tests for error handling in search endpoints."""

    def test_search_engine_exception(
        self, mock_hybrid_engine, mock_semantic_engine, mock_keyword_engine,
        mock_filter_optimizer, mock_event_bus
    ):
        """Test handling search engine exception."""
        mock_hybrid_engine.search.side_effect = Exception("Search failed")

        init_api(
            semantic_engine=mock_semantic_engine,
            keyword_engine=mock_keyword_engine,
            hybrid_engine=mock_hybrid_engine,
            filter_optimizer=mock_filter_optimizer,
            event_bus=mock_event_bus,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/search/",
            json={"query": "test"},
        )

        assert response.status_code == 500
        assert "Search failed" in response.json()["detail"]

    def test_suggest_exception(
        self, mock_hybrid_engine, mock_semantic_engine, mock_keyword_engine,
        mock_filter_optimizer, mock_event_bus
    ):
        """Test handling suggest exception."""
        mock_keyword_engine.suggest.side_effect = Exception("Autocomplete failed")

        init_api(
            semantic_engine=mock_semantic_engine,
            keyword_engine=mock_keyword_engine,
            hybrid_engine=mock_hybrid_engine,
            filter_optimizer=mock_filter_optimizer,
            event_bus=mock_event_bus,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/search/suggest?q=test")

        assert response.status_code == 500
        assert "Autocomplete failed" in response.json()["detail"]

    def test_similar_exception(
        self, mock_hybrid_engine, mock_semantic_engine, mock_keyword_engine,
        mock_filter_optimizer, mock_event_bus
    ):
        """Test handling find similar exception."""
        mock_semantic_engine.find_similar.side_effect = Exception("Similar search failed")

        init_api(
            semantic_engine=mock_semantic_engine,
            keyword_engine=mock_keyword_engine,
            hybrid_engine=mock_hybrid_engine,
            filter_optimizer=mock_filter_optimizer,
            event_bus=mock_event_bus,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post("/api/search/similar/doc-1")

        assert response.status_code == 500
        assert "Similar search failed" in response.json()["detail"]
