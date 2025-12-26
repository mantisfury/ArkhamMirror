"""
Timeline Shard - API Tests

Tests for the Timeline Shard API endpoints.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_timeline.api import router, init_api
from arkham_shard_timeline.models import (
    TimelineEvent,
    DatePrecision,
    EventType,
    MergeStrategy,
    MergeResult,
    DateRange,
    TemporalConflict,
    ConflictType,
    ConflictSeverity,
    NormalizedDate,
)


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_extractor():
    """Create mock date extractor."""
    mock = MagicMock()
    mock.extract_events = MagicMock(return_value=[
        TimelineEvent(
            id="event-1",
            document_id="doc-1",
            text="January 15, 2024",
            date_start=datetime(2024, 1, 15),
            precision=DatePrecision.DAY,
            confidence=0.95,
        )
    ])
    mock.normalize_date = MagicMock(return_value=NormalizedDate(
        original="Jan 15, 2024",
        normalized=datetime(2024, 1, 15),
        precision=DatePrecision.DAY,
        confidence=0.95,
    ))
    return mock


@pytest.fixture
def mock_merger():
    """Create mock timeline merger."""
    mock = MagicMock()
    mock.merge = MagicMock(return_value=MergeResult(
        events=[],
        count=0,
        sources={},
        date_range=DateRange(),
        duplicates_removed=0,
    ))
    return mock


@pytest.fixture
def mock_conflict_detector():
    """Create mock conflict detector."""
    mock = MagicMock()
    mock.tolerance_days = 0
    mock.detect_conflicts = MagicMock(return_value=[])
    return mock


@pytest.fixture
def mock_database_service():
    """Create mock database service."""
    return MagicMock()


@pytest.fixture
def mock_documents_service():
    """Create mock documents service."""
    mock = MagicMock()
    mock.get_document = AsyncMock(return_value={"text": "Sample document text"})
    return mock


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    mock = MagicMock()
    mock.emit = AsyncMock()
    return mock


@pytest.fixture
def initialized_api(
    mock_extractor,
    mock_merger,
    mock_conflict_detector,
    mock_database_service,
    mock_documents_service,
    mock_event_bus,
):
    """Initialize API with mocks."""
    init_api(
        extractor=mock_extractor,
        merger=mock_merger,
        conflict_detector=mock_conflict_detector,
        database_service=mock_database_service,
        documents_service=mock_documents_service,
        entities_service=None,
        event_bus=mock_event_bus,
    )


class TestExtractEndpoint:
    """Tests for POST /api/timeline/extract endpoint."""

    def test_extract_not_initialized(self, client):
        """Test extract fails when not initialized."""
        # Reset API state
        init_api(None, None, None, None, None, None, None)

        response = client.post("/api/timeline/extract", json={"text": "Jan 15, 2024"})

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]

    def test_extract_from_text(self, client, initialized_api, mock_extractor):
        """Test extracting from text."""
        response = client.post(
            "/api/timeline/extract",
            json={"text": "Meeting on January 15, 2024."}
        )

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "count" in data
        assert "duration_ms" in data

    def test_extract_requires_text_or_document(self, client, initialized_api):
        """Test extract requires either text or document_id."""
        response = client.post("/api/timeline/extract", json={})

        assert response.status_code == 400
        assert "required" in response.json()["detail"]


class TestDocumentTimelineEndpoint:
    """Tests for GET /api/timeline/{document_id} endpoint."""

    def test_get_document_timeline_not_initialized(self, client):
        """Test get timeline fails when not initialized."""
        init_api(None, None, None, None, None, None, None)

        response = client.get("/api/timeline/doc-123")

        assert response.status_code == 503

    def test_get_document_timeline(self, client, initialized_api):
        """Test getting document timeline."""
        response = client.get("/api/timeline/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert "events" in data
        assert "count" in data

    def test_get_document_timeline_with_filters(self, client, initialized_api):
        """Test getting document timeline with filters."""
        response = client.get(
            "/api/timeline/doc-123",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "event_type": "occurrence",
                "min_confidence": 0.8,
            }
        )

        assert response.status_code == 200


class TestMergeEndpoint:
    """Tests for POST /api/timeline/merge endpoint."""

    def test_merge_not_initialized(self, client):
        """Test merge fails when not initialized."""
        init_api(None, None, None, None, None, None, None)

        response = client.post(
            "/api/timeline/merge",
            json={"document_ids": ["doc-1", "doc-2"]}
        )

        assert response.status_code == 503

    def test_merge_basic(self, client, initialized_api, mock_merger):
        """Test basic merge request."""
        mock_merger.merge.return_value = MergeResult(
            events=[],
            count=0,
            sources={"doc-1": 0, "doc-2": 0},
            date_range=DateRange(
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31),
            ),
            duplicates_removed=0,
        )

        response = client.post(
            "/api/timeline/merge",
            json={
                "document_ids": ["doc-1", "doc-2"],
                "merge_strategy": "chronological",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "sources" in data
        assert "duplicates_removed" in data

    def test_merge_invalid_strategy(self, client, initialized_api):
        """Test merge with invalid strategy."""
        response = client.post(
            "/api/timeline/merge",
            json={
                "document_ids": ["doc-1"],
                "merge_strategy": "invalid_strategy",
            }
        )

        assert response.status_code == 400
        assert "strategy" in response.json()["detail"].lower()

    def test_merge_with_priority_docs(self, client, initialized_api, mock_merger):
        """Test merge with priority documents."""
        mock_merger.merge.return_value = MergeResult(
            events=[],
            count=0,
            sources={},
            date_range=DateRange(),
            duplicates_removed=0,
        )

        response = client.post(
            "/api/timeline/merge",
            json={
                "document_ids": ["doc-1", "doc-2"],
                "merge_strategy": "source_priority",
                "priority_docs": ["doc-1"],
            }
        )

        assert response.status_code == 200


class TestRangeEndpoint:
    """Tests for GET /api/timeline/range endpoint."""

    def test_range_not_initialized(self, client):
        """Test range fails when not initialized."""
        init_api(None, None, None, None, None, None, None)

        response = client.get(
            "/api/timeline/range",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            }
        )

        assert response.status_code == 503

    def test_range_query(self, client, initialized_api):
        """Test range query."""
        response = client.get(
            "/api/timeline/range",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "count" in data
        assert "total" in data
        assert "has_more" in data

    def test_range_with_filters(self, client, initialized_api):
        """Test range query with filters."""
        response = client.get(
            "/api/timeline/range",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "document_ids": "doc-1,doc-2",
                "event_types": "occurrence,deadline",
                "limit": 50,
                "offset": 10,
            }
        )

        assert response.status_code == 200


class TestConflictsEndpoint:
    """Tests for POST /api/timeline/conflicts endpoint."""

    def test_conflicts_not_initialized(self, client):
        """Test conflicts fails when not initialized."""
        init_api(None, None, None, None, None, None, None)

        response = client.post(
            "/api/timeline/conflicts",
            json={"document_ids": ["doc-1", "doc-2"]}
        )

        assert response.status_code == 503

    def test_conflicts_basic(self, client, initialized_api, mock_conflict_detector):
        """Test basic conflict detection."""
        response = client.post(
            "/api/timeline/conflicts",
            json={"document_ids": ["doc-1", "doc-2"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert "conflicts" in data
        assert "count" in data
        assert "by_type" in data

    def test_conflicts_with_types(self, client, initialized_api, mock_conflict_detector):
        """Test conflict detection with specific types."""
        response = client.post(
            "/api/timeline/conflicts",
            json={
                "document_ids": ["doc-1", "doc-2"],
                "conflict_types": ["contradiction", "gap"],
            }
        )

        assert response.status_code == 200

    def test_conflicts_invalid_type(self, client, initialized_api):
        """Test conflict detection with invalid type."""
        response = client.post(
            "/api/timeline/conflicts",
            json={
                "document_ids": ["doc-1"],
                "conflict_types": ["invalid_type"],
            }
        )

        assert response.status_code == 400

    def test_conflicts_with_tolerance(self, client, initialized_api):
        """Test conflict detection with custom tolerance."""
        response = client.post(
            "/api/timeline/conflicts",
            json={
                "document_ids": ["doc-1", "doc-2"],
                "tolerance_days": 5,
            }
        )

        assert response.status_code == 200


class TestEntityTimelineEndpoint:
    """Tests for GET /api/timeline/entity/{entity_id} endpoint."""

    def test_entity_timeline_not_initialized(self, client):
        """Test entity timeline fails when not initialized."""
        init_api(None, None, None, None, None, None, None)

        response = client.get("/api/timeline/entity/entity-123")

        assert response.status_code == 503

    def test_entity_timeline_basic(self, client, initialized_api):
        """Test getting entity timeline."""
        response = client.get("/api/timeline/entity/entity-123")

        assert response.status_code == 200
        data = response.json()
        assert data["entity_id"] == "entity-123"
        assert "events" in data
        assert "count" in data

    def test_entity_timeline_with_filters(self, client, initialized_api):
        """Test entity timeline with filters."""
        response = client.get(
            "/api/timeline/entity/entity-123",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "include_related": True,
            }
        )

        assert response.status_code == 200


class TestNormalizeEndpoint:
    """Tests for POST /api/timeline/normalize endpoint."""

    def test_normalize_not_initialized(self, client):
        """Test normalize fails when not initialized."""
        init_api(None, None, None, None, None, None, None)

        response = client.post(
            "/api/timeline/normalize",
            json={"dates": ["Jan 15, 2024"]}
        )

        assert response.status_code == 503

    def test_normalize_dates(self, client, initialized_api, mock_extractor):
        """Test normalizing dates."""
        response = client.post(
            "/api/timeline/normalize",
            json={"dates": ["Jan 15, 2024", "2024-06-15"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert "normalized" in data
        assert len(data["normalized"]) == 2

    def test_normalize_with_reference_date(self, client, initialized_api, mock_extractor):
        """Test normalizing with reference date."""
        response = client.post(
            "/api/timeline/normalize",
            json={
                "dates": ["yesterday", "tomorrow"],
                "reference_date": "2024-06-15T00:00:00",
            }
        )

        assert response.status_code == 200

    def test_normalize_invalid_reference_date(self, client, initialized_api):
        """Test normalizing with invalid reference date."""
        response = client.post(
            "/api/timeline/normalize",
            json={
                "dates": ["Jan 15, 2024"],
                "reference_date": "not-a-date",
            }
        )

        assert response.status_code == 400
        assert "reference_date" in response.json()["detail"]


class TestStatsEndpoint:
    """Tests for GET /api/timeline/stats endpoint."""

    def test_stats_not_initialized(self, client):
        """Test stats fails when not initialized."""
        init_api(None, None, None, None, None, None, None)

        response = client.get("/api/timeline/stats")

        assert response.status_code == 503

    def test_stats_basic(self, client, initialized_api):
        """Test getting stats."""
        response = client.get("/api/timeline/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_events" in data
        assert "total_documents" in data
        assert "by_precision" in data
        assert "by_type" in data
        assert "avg_confidence" in data

    def test_stats_with_filters(self, client, initialized_api):
        """Test stats with filters."""
        response = client.get(
            "/api/timeline/stats",
            params={
                "document_ids": "doc-1,doc-2,doc-3",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            }
        )

        assert response.status_code == 200


class TestHelperFunctions:
    """Tests for API helper functions."""

    def test_event_to_dict(self, initialized_api):
        """Test _event_to_dict conversion."""
        from arkham_shard_timeline.api import _event_to_dict

        event = TimelineEvent(
            id="event-123",
            document_id="doc-456",
            text="Test event",
            date_start=datetime(2024, 1, 15),
            date_end=datetime(2024, 1, 20),
            precision=DatePrecision.DAY,
            confidence=0.95,
            entities=["entity-1"],
            event_type=EventType.OCCURRENCE,
            span=(10, 50),
            metadata={"key": "value"},
        )

        result = _event_to_dict(event)

        assert result["id"] == "event-123"
        assert result["document_id"] == "doc-456"
        assert result["text"] == "Test event"
        assert result["date_start"] == "2024-01-15T00:00:00"
        assert result["date_end"] == "2024-01-20T00:00:00"
        assert result["precision"] == "day"
        assert result["confidence"] == 0.95
        assert result["entities"] == ["entity-1"]
        assert result["event_type"] == "occurrence"
        assert result["span"] == (10, 50)
        assert result["metadata"] == {"key": "value"}

    def test_conflict_to_dict(self, initialized_api):
        """Test _conflict_to_dict conversion."""
        from arkham_shard_timeline.api import _conflict_to_dict

        conflict = TemporalConflict(
            id="conflict-123",
            type=ConflictType.CONTRADICTION,
            severity=ConflictSeverity.HIGH,
            events=["event-1", "event-2"],
            description="Conflicting dates",
            documents=["doc-1", "doc-2"],
            suggested_resolution="Review sources",
            metadata={"diff_days": 30},
        )

        result = _conflict_to_dict(conflict)

        assert result["id"] == "conflict-123"
        assert result["type"] == "contradiction"
        assert result["severity"] == "high"
        assert result["events"] == ["event-1", "event-2"]
        assert result["description"] == "Conflicting dates"
        assert result["documents"] == ["doc-1", "doc-2"]
        assert result["suggested_resolution"] == "Review sources"
        assert result["metadata"] == {"diff_days": 30}
