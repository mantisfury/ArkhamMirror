"""
Tests for Patterns Shard API Routes
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_patterns.api import router
from arkham_shard_patterns.models import (
    Pattern,
    PatternMatch,
    PatternStatistics,
    PatternAnalysisResult,
    CorrelationResult,
    PatternType,
    PatternStatus,
    DetectionMethod,
    SourceType,
    PatternCriteria,
)


@pytest.fixture
def mock_shard():
    """Create a mock shard for testing."""
    shard = MagicMock()
    shard.name = "patterns"
    shard.version = "0.1.0"
    shard._initialized = True
    shard._llm = MagicMock()
    shard._llm.is_available = MagicMock(return_value=True)
    shard._vectors = MagicMock()
    shard._workers = MagicMock()
    return shard


@pytest.fixture
def app(mock_shard):
    """Create FastAPI app with mocked shard."""
    app = FastAPI()
    app.include_router(router)

    # Patch the get_shard function
    with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
        yield app, mock_shard


@pytest.fixture
def client(app):
    """Create test client."""
    app_instance, mock_shard = app
    with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
        return TestClient(app_instance), mock_shard


class TestHealthEndpoints:
    """Tests for health and status endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        test_client, mock_shard = client

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["shard"] == "patterns"

    def test_get_count(self, client):
        """Test count endpoint."""
        test_client, mock_shard = client
        mock_shard.get_count = AsyncMock(return_value=42)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/count")

        assert response.status_code == 200
        assert response.json()["count"] == 42

    def test_get_count_with_status(self, client):
        """Test count endpoint with status filter."""
        test_client, mock_shard = client
        mock_shard.get_count = AsyncMock(return_value=15)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/count?status=confirmed")

        assert response.status_code == 200
        assert response.json()["count"] == 15

    def test_get_statistics(self, client):
        """Test statistics endpoint."""
        test_client, mock_shard = client
        mock_shard.get_statistics = AsyncMock(return_value=PatternStatistics(
            total_patterns=50,
            by_type={"recurring_theme": 30, "behavioral": 20},
            by_status={"confirmed": 25, "detected": 25},
            total_matches=150,
        ))

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_patterns"] == 50
        assert data["total_matches"] == 150

    def test_get_capabilities(self, client):
        """Test capabilities endpoint."""
        test_client, mock_shard = client

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/capabilities")

        assert response.status_code == 200
        data = response.json()
        assert "llm_available" in data
        assert "vectors_available" in data
        assert "pattern_types" in data


class TestPatternCRUD:
    """Tests for pattern CRUD endpoints."""

    def test_list_patterns(self, client):
        """Test listing patterns."""
        test_client, mock_shard = client
        mock_shard.list_patterns = AsyncMock(return_value=[])
        mock_shard.get_count = AsyncMock(return_value=0)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1

    def test_list_patterns_with_filters(self, client):
        """Test listing patterns with filters."""
        test_client, mock_shard = client
        mock_shard.list_patterns = AsyncMock(return_value=[])
        mock_shard.get_count = AsyncMock(return_value=0)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get(
                "/api/patterns/?pattern_type=recurring_theme&status=confirmed&min_confidence=0.7"
            )

        assert response.status_code == 200

    def test_create_pattern(self, client):
        """Test creating a pattern."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="new-pattern",
            name="New Pattern",
            description="A new pattern",
            pattern_type=PatternType.RECURRING_THEME,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_shard.create_pattern = AsyncMock(return_value=mock_pattern)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.post(
                "/api/patterns/",
                json={
                    "name": "New Pattern",
                    "description": "A new pattern",
                    "pattern_type": "recurring_theme",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Pattern"

    def test_get_pattern(self, client):
        """Test getting a pattern."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="pattern-123",
            name="Test Pattern",
            description="A test pattern",
            pattern_type=PatternType.BEHAVIORAL,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_shard.get_pattern = AsyncMock(return_value=mock_pattern)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/pattern-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pattern-123"

    def test_get_pattern_not_found(self, client):
        """Test getting a non-existent pattern."""
        test_client, mock_shard = client
        mock_shard.get_pattern = AsyncMock(return_value=None)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/nonexistent")

        assert response.status_code == 404

    def test_update_pattern(self, client):
        """Test updating a pattern."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="pattern-123",
            name="Updated Pattern",
            description="Updated description",
            pattern_type=PatternType.BEHAVIORAL,
            confidence=0.9,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_shard.update_pattern = AsyncMock(return_value=mock_pattern)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.put(
                "/api/patterns/pattern-123",
                json={"name": "Updated Pattern", "confidence": 0.9},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Pattern"

    def test_delete_pattern(self, client):
        """Test deleting a pattern."""
        test_client, mock_shard = client
        mock_shard.delete_pattern = AsyncMock(return_value=True)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.delete("/api/patterns/pattern-123")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

    def test_confirm_pattern(self, client):
        """Test confirming a pattern."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="pattern-123",
            name="Test Pattern",
            description="Test",
            pattern_type=PatternType.RECURRING_THEME,
            status=PatternStatus.CONFIRMED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_shard.confirm_pattern = AsyncMock(return_value=mock_pattern)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.post("/api/patterns/pattern-123/confirm")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"

    def test_dismiss_pattern(self, client):
        """Test dismissing a pattern."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="pattern-123",
            name="Test Pattern",
            description="Test",
            pattern_type=PatternType.RECURRING_THEME,
            status=PatternStatus.DISMISSED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_shard.dismiss_pattern = AsyncMock(return_value=mock_pattern)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.post("/api/patterns/pattern-123/dismiss")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "dismissed"


class TestPatternMatches:
    """Tests for pattern match endpoints."""

    def test_get_pattern_matches(self, client):
        """Test getting matches for a pattern."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="pattern-123",
            name="Test",
            description="Test",
            pattern_type=PatternType.RECURRING_THEME,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_shard.get_pattern = AsyncMock(return_value=mock_pattern)
        mock_shard.get_pattern_matches = AsyncMock(return_value=[])
        mock_shard.get_match_count = AsyncMock(return_value=0)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.get("/api/patterns/pattern-123/matches")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_add_match(self, client):
        """Test adding a match to a pattern."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="pattern-123",
            name="Test",
            description="Test",
            pattern_type=PatternType.RECURRING_THEME,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_match = PatternMatch(
            id="match-456",
            pattern_id="pattern-123",
            source_type=SourceType.DOCUMENT,
            source_id="doc-789",
            match_score=0.85,
            matched_at=datetime.utcnow(),
        )
        mock_shard.get_pattern = AsyncMock(return_value=mock_pattern)
        mock_shard.add_match = AsyncMock(return_value=mock_match)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.post(
                "/api/patterns/pattern-123/matches",
                json={
                    "source_type": "document",
                    "source_id": "doc-789",
                    "match_score": 0.85,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source_id"] == "doc-789"

    def test_remove_match(self, client):
        """Test removing a match."""
        test_client, mock_shard = client
        mock_shard.remove_match = AsyncMock(return_value=True)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.delete("/api/patterns/pattern-123/matches/match-456")

        assert response.status_code == 200
        data = response.json()
        assert data["removed"] is True


class TestAnalysis:
    """Tests for analysis endpoints."""

    def test_analyze_for_patterns(self, client):
        """Test analyzing documents for patterns."""
        test_client, mock_shard = client
        mock_result = PatternAnalysisResult(
            patterns_detected=[],
            matches_found=[],
            documents_analyzed=3,
            processing_time_ms=150.5,
        )
        mock_shard.analyze_documents = AsyncMock(return_value=mock_result)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.post(
                "/api/patterns/analyze",
                json={
                    "document_ids": ["doc-1", "doc-2", "doc-3"],
                    "pattern_types": ["recurring_theme"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["documents_analyzed"] == 3

    def test_find_correlations(self, client):
        """Test finding correlations."""
        test_client, mock_shard = client
        mock_result = CorrelationResult(
            correlations=[],
            entities_analyzed=3,
            processing_time_ms=50.0,
        )
        mock_shard.find_correlations = AsyncMock(return_value=mock_result)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.post(
                "/api/patterns/correlate",
                json={
                    "entity_ids": ["entity-1", "entity-2", "entity-3"],
                    "time_window_days": 90,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["entities_analyzed"] == 3


class TestBatchOperations:
    """Tests for batch operations."""

    def test_batch_confirm(self, client):
        """Test batch confirming patterns."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="pattern-1",
            name="Test",
            description="Test",
            pattern_type=PatternType.RECURRING_THEME,
            status=PatternStatus.CONFIRMED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_shard.confirm_pattern = AsyncMock(return_value=mock_pattern)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.post(
                "/api/patterns/batch/confirm",
                json=["pattern-1", "pattern-2"],
            )

        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 2

    def test_batch_dismiss(self, client):
        """Test batch dismissing patterns."""
        test_client, mock_shard = client
        mock_pattern = Pattern(
            id="pattern-1",
            name="Test",
            description="Test",
            pattern_type=PatternType.RECURRING_THEME,
            status=PatternStatus.DISMISSED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            first_detected=datetime.utcnow(),
        )
        mock_shard.dismiss_pattern = AsyncMock(return_value=mock_pattern)

        with patch("arkham_shard_patterns.api.get_shard", return_value=mock_shard):
            response = test_client.post(
                "/api/patterns/batch/dismiss",
                json=["pattern-1", "pattern-2"],
            )

        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 2
