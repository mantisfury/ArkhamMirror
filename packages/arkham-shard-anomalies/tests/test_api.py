"""
Anomalies Shard - API Tests

Tests for all FastAPI endpoints.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_anomalies.api import router, init_api
from arkham_shard_anomalies.models import (
    Anomaly,
    AnomalyType,
    AnomalyStatus,
    SeverityLevel,
    AnomalyStats,
    AnomalyPattern,
)


@pytest.fixture
def mock_detector():
    """Create mock anomaly detector."""
    return MagicMock()


@pytest.fixture
def mock_store():
    """Create mock anomaly store."""
    mock = MagicMock()
    mock.list_anomalies = AsyncMock(return_value=([], 0))
    mock.get_anomaly = AsyncMock(return_value=None)
    mock.update_status = AsyncMock(return_value=None)
    mock.add_note = AsyncMock(return_value=None)
    mock.list_patterns = AsyncMock(return_value=[])
    mock.get_stats = AsyncMock(return_value=AnomalyStats())
    mock.get_facets = AsyncMock(return_value={"types": {}, "statuses": {}, "severities": {}})
    return mock


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    mock = MagicMock()
    mock.emit = AsyncMock()
    return mock


@pytest.fixture
def client(mock_detector, mock_store, mock_event_bus):
    """Create test client with mocked dependencies."""
    init_api(
        detector=mock_detector,
        store=mock_store,
        event_bus=mock_event_bus,
    )

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestDetectEndpoint:
    """Tests for POST /api/anomalies/detect endpoint."""

    def test_detect_basic(self, client, mock_event_bus):
        """Test basic anomaly detection request."""
        response = client.post(
            "/api/anomalies/detect",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert "anomalies_detected" in data
        assert "duration_ms" in data
        assert "job_id" in data

    def test_detect_with_project(self, client, mock_event_bus):
        """Test detection with project ID."""
        response = client.post(
            "/api/anomalies/detect",
            json={"project_id": "proj-123"},
        )

        assert response.status_code == 200
        mock_event_bus.emit.assert_called_once()

    def test_detect_with_doc_ids(self, client):
        """Test detection for specific documents."""
        response = client.post(
            "/api/anomalies/detect",
            json={"doc_ids": ["doc-1", "doc-2", "doc-3"]},
        )

        assert response.status_code == 200

    def test_detect_with_config(self, client):
        """Test detection with custom config."""
        response = client.post(
            "/api/anomalies/detect",
            json={
                "config": {
                    "z_score_threshold": 2.5,
                    "detect_content": True,
                    "detect_red_flags": True,
                }
            },
        )

        assert response.status_code == 200


class TestDetectNotInitialized:
    """Tests for detect when service not initialized."""

    def test_detect_not_initialized(self):
        """Test detect when service not initialized."""
        init_api(
            detector=None,
            store=None,
            event_bus=None,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/anomalies/detect",
            json={},
        )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestDetectDocumentEndpoint:
    """Tests for POST /api/anomalies/document/{doc_id} endpoint."""

    def test_detect_document(self, client):
        """Test checking specific document for anomalies."""
        response = client.post("/api/anomalies/document/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert "anomalies_detected" in data
        assert "duration_ms" in data


class TestListEndpoint:
    """Tests for GET /api/anomalies/list endpoint."""

    def test_list_basic(self, client, mock_store):
        """Test listing anomalies."""
        anomaly = Anomaly(
            id="a1",
            doc_id="doc-1",
            anomaly_type=AnomalyType.CONTENT,
            status=AnomalyStatus.DETECTED,
            severity=SeverityLevel.MEDIUM,
            score=3.5,
            confidence=0.85,
            explanation="Test anomaly",
        )
        mock_store.list_anomalies.return_value = ([anomaly], 1)

        response = client.get("/api/anomalies/list")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "a1"

    def test_list_with_pagination(self, client, mock_store):
        """Test listing with pagination."""
        mock_store.list_anomalies.return_value = ([], 100)

        response = client.get("/api/anomalies/list?offset=20&limit=10")

        assert response.status_code == 200
        mock_store.list_anomalies.assert_called_once()
        call_kwargs = mock_store.list_anomalies.call_args[1]
        assert call_kwargs["offset"] == 20
        assert call_kwargs["limit"] == 10

    def test_list_filter_by_type(self, client, mock_store):
        """Test filtering by anomaly type."""
        mock_store.list_anomalies.return_value = ([], 0)

        response = client.get("/api/anomalies/list?anomaly_type=content")

        assert response.status_code == 200
        call_kwargs = mock_store.list_anomalies.call_args[1]
        assert call_kwargs["anomaly_type"] == AnomalyType.CONTENT

    def test_list_filter_by_status(self, client, mock_store):
        """Test filtering by status."""
        mock_store.list_anomalies.return_value = ([], 0)

        response = client.get("/api/anomalies/list?status=confirmed")

        assert response.status_code == 200
        call_kwargs = mock_store.list_anomalies.call_args[1]
        assert call_kwargs["status"] == AnomalyStatus.CONFIRMED

    def test_list_filter_by_severity(self, client, mock_store):
        """Test filtering by severity."""
        mock_store.list_anomalies.return_value = ([], 0)

        response = client.get("/api/anomalies/list?severity=high")

        assert response.status_code == 200
        call_kwargs = mock_store.list_anomalies.call_args[1]
        assert call_kwargs["severity"] == SeverityLevel.HIGH

    def test_list_filter_by_doc_id(self, client, mock_store):
        """Test filtering by document ID."""
        mock_store.list_anomalies.return_value = ([], 0)

        response = client.get("/api/anomalies/list?doc_id=doc-123")

        assert response.status_code == 200
        call_kwargs = mock_store.list_anomalies.call_args[1]
        assert call_kwargs["doc_id"] == "doc-123"

    def test_list_invalid_type(self, client):
        """Test listing with invalid type returns 400."""
        response = client.get("/api/anomalies/list?anomaly_type=invalid")
        assert response.status_code == 400
        assert "Invalid anomaly type" in response.json()["detail"]

    def test_list_invalid_status(self, client):
        """Test listing with invalid status returns 400."""
        response = client.get("/api/anomalies/list?status=invalid")
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_list_invalid_severity(self, client):
        """Test listing with invalid severity returns 400."""
        response = client.get("/api/anomalies/list?severity=invalid")
        assert response.status_code == 400
        assert "Invalid severity" in response.json()["detail"]


class TestGetAnomalyEndpoint:
    """Tests for GET /api/anomalies/{anomaly_id} endpoint."""

    def test_get_anomaly(self, client, mock_store):
        """Test getting specific anomaly."""
        anomaly = Anomaly(
            id="anom-123",
            doc_id="doc-456",
            anomaly_type=AnomalyType.RED_FLAG,
            status=AnomalyStatus.DETECTED,
            severity=SeverityLevel.HIGH,
            score=4.5,
        )
        mock_store.get_anomaly.return_value = anomaly

        response = client.get("/api/anomalies/anom-123")

        assert response.status_code == 200
        data = response.json()
        assert data["anomaly"]["id"] == "anom-123"
        assert data["anomaly"]["anomaly_type"] == "red_flag"

    def test_get_anomaly_not_found(self, client, mock_store):
        """Test getting nonexistent anomaly."""
        mock_store.get_anomaly.return_value = None

        response = client.get("/api/anomalies/nonexistent")

        assert response.status_code == 404


class TestUpdateStatusEndpoint:
    """Tests for PUT /api/anomalies/{anomaly_id}/status endpoint."""

    def test_update_status(self, client, mock_store, mock_event_bus):
        """Test updating anomaly status."""
        anomaly = Anomaly(
            id="anom-123",
            doc_id="doc-456",
            anomaly_type=AnomalyType.CONTENT,
            status=AnomalyStatus.CONFIRMED,
        )
        mock_store.update_status.return_value = anomaly

        response = client.put(
            "/api/anomalies/anom-123/status",
            json={
                "status": "confirmed",
                "notes": "Verified as real anomaly",
                "reviewed_by": "analyst@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["anomaly"]["status"] == "confirmed"
        mock_event_bus.emit.assert_called_once()

    def test_update_status_not_found(self, client, mock_store):
        """Test updating nonexistent anomaly."""
        mock_store.update_status.return_value = None

        response = client.put(
            "/api/anomalies/nonexistent/status",
            json={"status": "confirmed"},
        )

        assert response.status_code == 404

    def test_update_status_invalid(self, client):
        """Test updating with invalid status."""
        response = client.put(
            "/api/anomalies/anom-123/status",
            json={"status": "invalid_status"},
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]


class TestAddNoteEndpoint:
    """Tests for POST /api/anomalies/{anomaly_id}/notes endpoint."""

    def test_add_note(self, client, mock_store):
        """Test adding an analyst note."""
        anomaly = Anomaly(
            id="anom-123",
            doc_id="doc-456",
            anomaly_type=AnomalyType.CONTENT,
        )
        mock_store.get_anomaly.return_value = anomaly

        response = client.post(
            "/api/anomalies/anom-123/notes",
            json={
                "content": "This needs further investigation.",
                "author": "analyst@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "note_id" in data

    def test_add_note_anomaly_not_found(self, client, mock_store):
        """Test adding note to nonexistent anomaly."""
        mock_store.get_anomaly.return_value = None

        response = client.post(
            "/api/anomalies/nonexistent/notes",
            json={
                "content": "Test note",
                "author": "analyst@example.com",
            },
        )

        assert response.status_code == 404


class TestOutliersEndpoint:
    """Tests for GET /api/anomalies/outliers endpoint."""

    def test_get_outliers(self, client, mock_store):
        """Test getting statistical outliers."""
        anomaly = Anomaly(
            id="a1",
            doc_id="doc-1",
            anomaly_type=AnomalyType.CONTENT,
            score=4.5,  # Above threshold
        )
        mock_store.list_anomalies.return_value = ([anomaly], 1)

        response = client.get("/api/anomalies/outliers?limit=10&min_z_score=3.0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    def test_get_outliers_filters_low_scores(self, client, mock_store):
        """Test outliers filters out low z-scores."""
        anomalies = [
            Anomaly(id="a1", doc_id="doc-1", anomaly_type=AnomalyType.CONTENT, score=4.5),
            Anomaly(id="a2", doc_id="doc-2", anomaly_type=AnomalyType.CONTENT, score=2.0),  # Below threshold
        ]
        mock_store.list_anomalies.return_value = (anomalies, 2)

        response = client.get("/api/anomalies/outliers?min_z_score=3.0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "a1"


class TestPatternsEndpoint:
    """Tests for POST /api/anomalies/patterns endpoint."""

    def test_detect_patterns(self, client, mock_store):
        """Test detecting patterns."""
        pattern = AnomalyPattern(
            id="pat-1",
            pattern_type="money_cluster",
            description="Multiple documents with money references",
            frequency=3,
        )
        mock_store.list_patterns.return_value = [pattern]

        response = client.post(
            "/api/anomalies/patterns",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["patterns_found"] == 1
        assert len(data["patterns"]) == 1

    def test_detect_patterns_with_options(self, client, mock_store):
        """Test detecting patterns with options."""
        mock_store.list_patterns.return_value = []

        response = client.post(
            "/api/anomalies/patterns",
            json={
                "anomaly_ids": ["a1", "a2"],
                "min_frequency": 3,
                "pattern_types": ["money", "dates"],
            },
        )

        assert response.status_code == 200


class TestStatsEndpoint:
    """Tests for GET /api/anomalies/stats endpoint."""

    def test_get_stats(self, client, mock_store):
        """Test getting anomaly statistics."""
        stats = AnomalyStats(
            total_anomalies=100,
            by_type={"content": 40, "red_flag": 60},
            by_status={"detected": 70, "confirmed": 30},
            by_severity={"high": 20, "medium": 50, "low": 30},
            detected_last_24h=15,
            confirmed_last_24h=5,
            dismissed_last_24h=3,
            false_positive_rate=0.1,
            avg_confidence=0.85,
        )
        mock_store.get_stats.return_value = stats

        response = client.get("/api/anomalies/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["total_anomalies"] == 100
        assert data["stats"]["by_type"]["content"] == 40
        assert data["stats"]["false_positive_rate"] == 0.1


class TestStatsNotInitialized:
    """Tests for stats when service not initialized."""

    def test_stats_not_initialized(self):
        """Test stats when service not initialized."""
        init_api(
            detector=MagicMock(),
            store=None,
            event_bus=MagicMock(),
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/anomalies/stats")

        assert response.status_code == 503
