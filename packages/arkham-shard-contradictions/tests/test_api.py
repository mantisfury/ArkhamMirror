"""
Contradictions Shard - API Tests

Tests for all FastAPI endpoints.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_contradictions.api import router, init_api
from arkham_shard_contradictions.models import (
    Contradiction,
    ContradictionChain,
    ContradictionStatus,
    Severity,
    ContradictionType,
    Claim,
)


@pytest.fixture
def mock_detector():
    """Create mock contradiction detector."""
    mock = MagicMock()
    mock.extract_claims_simple = MagicMock(return_value=[
        Claim(id="claim-1", document_id="doc-1", text="Test claim"),
    ])
    mock.extract_claims_llm = AsyncMock(return_value=[
        Claim(id="claim-1", document_id="doc-1", text="Test claim"),
    ])
    mock.find_similar_claims = AsyncMock(return_value=[])
    mock.verify_contradiction = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_storage():
    """Create mock contradiction storage."""
    mock = MagicMock()
    mock.create = MagicMock(side_effect=lambda c: c)
    mock.get = MagicMock(return_value=None)
    mock.update = MagicMock(side_effect=lambda c: c)
    mock.delete = MagicMock(return_value=True)
    mock.list_all = MagicMock(return_value=([], 0))
    mock.get_by_document = MagicMock(return_value=[])
    mock.get_statistics = MagicMock(return_value={
        "total_contradictions": 0,
        "by_status": {},
        "by_severity": {},
        "by_type": {},
        "chains_detected": 0,
        "recent_count": 0,
    })
    mock.search = MagicMock(return_value=[])
    mock.list_chains = MagicMock(return_value=[])
    mock.get_chain = MagicMock(return_value=None)
    mock.get_chain_contradictions = MagicMock(return_value=[])
    mock.update_status = MagicMock(return_value=None)
    mock.add_note = MagicMock(return_value=None)
    return mock


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    mock = MagicMock()
    mock.emit = AsyncMock()
    return mock


@pytest.fixture
def mock_chain_detector():
    """Create mock chain detector."""
    mock = MagicMock()
    mock.detect_chains = MagicMock(return_value=[])
    return mock


@pytest.fixture
def client(mock_detector, mock_storage, mock_event_bus, mock_chain_detector):
    """Create test client with mocked dependencies."""
    init_api(
        detector=mock_detector,
        storage=mock_storage,
        event_bus=mock_event_bus,
        chain_detector=mock_chain_detector,
    )

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestAnalyzeEndpoint:
    """Tests for POST /api/contradictions/analyze endpoint."""

    def test_analyze_basic(self, client, mock_detector, mock_event_bus):
        """Test basic document analysis."""
        response = client.post(
            "/api/contradictions/analyze",
            json={"doc_a_id": "doc-1", "doc_b_id": "doc-2"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["doc_a_id"] == "doc-1"
        assert data["doc_b_id"] == "doc-2"
        assert "contradictions" in data
        assert "count" in data

    def test_analyze_with_threshold(self, client, mock_detector):
        """Test analysis with custom threshold."""
        response = client.post(
            "/api/contradictions/analyze",
            json={
                "doc_a_id": "doc-1",
                "doc_b_id": "doc-2",
                "threshold": 0.5,
            },
        )

        assert response.status_code == 200

    def test_analyze_without_llm(self, client, mock_detector):
        """Test analysis without LLM."""
        response = client.post(
            "/api/contradictions/analyze",
            json={
                "doc_a_id": "doc-1",
                "doc_b_id": "doc-2",
                "use_llm": False,
            },
        )

        assert response.status_code == 200
        # Should use simple extraction
        mock_detector.extract_claims_simple.assert_called()


class TestAnalyzeNotInitialized:
    """Tests for analyze when service not initialized."""

    def test_analyze_not_initialized(self):
        """Test analyze when service not initialized."""
        init_api(
            detector=None,
            storage=None,
            event_bus=None,
            chain_detector=None,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/contradictions/analyze",
            json={"doc_a_id": "doc-1", "doc_b_id": "doc-2"},
        )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestBatchEndpoint:
    """Tests for POST /api/contradictions/batch endpoint."""

    def test_batch_analyze(self, client, mock_detector):
        """Test batch document analysis."""
        response = client.post(
            "/api/contradictions/batch",
            json={
                "document_pairs": [["doc-1", "doc-2"], ["doc-3", "doc-4"]],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pairs_analyzed"] == 2
        assert "contradictions" in data


class TestDocumentEndpoint:
    """Tests for GET /api/contradictions/document/{doc_id} endpoint."""

    def test_get_document_contradictions(self, client, mock_storage):
        """Test getting contradictions for a document."""
        mock_storage.get_by_document.return_value = []

        response = client.get("/api/contradictions/document/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert "contradictions" in data

    def test_get_document_with_chains(self, client, mock_storage):
        """Test getting contradictions with chain inclusion."""
        response = client.get(
            "/api/contradictions/document/doc-123?include_chains=true"
        )

        assert response.status_code == 200
        mock_storage.get_by_document.assert_called_with("doc-123", include_related=True)


class TestListEndpoint:
    """Tests for GET /api/contradictions/list endpoint."""

    def test_list_basic(self, client, mock_storage):
        """Test basic listing."""
        contradiction = Contradiction(
            id="c-1",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Claim A",
            claim_b="Claim B",
            contradiction_type=ContradictionType.DIRECT,
            severity=Severity.HIGH,
            status=ContradictionStatus.DETECTED,
            confidence_score=0.9,
        )
        mock_storage.list_all.return_value = ([contradiction], 1)

        response = client.get("/api/contradictions/list")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["contradictions"]) == 1

    def test_list_with_pagination(self, client, mock_storage):
        """Test listing with pagination."""
        mock_storage.list_all.return_value = ([], 100)

        response = client.get("/api/contradictions/list?page=2&page_size=20")

        assert response.status_code == 200
        mock_storage.list_all.assert_called_once()
        call_kwargs = mock_storage.list_all.call_args[1]
        assert call_kwargs["page"] == 2
        assert call_kwargs["page_size"] == 20

    def test_list_filter_by_status(self, client, mock_storage):
        """Test filtering by status."""
        mock_storage.list_all.return_value = ([], 0)

        response = client.get("/api/contradictions/list?status=confirmed")

        assert response.status_code == 200
        call_kwargs = mock_storage.list_all.call_args[1]
        assert call_kwargs["status"] == ContradictionStatus.CONFIRMED

    def test_list_filter_by_severity(self, client, mock_storage):
        """Test filtering by severity."""
        mock_storage.list_all.return_value = ([], 0)

        response = client.get("/api/contradictions/list?severity=high")

        assert response.status_code == 200
        call_kwargs = mock_storage.list_all.call_args[1]
        assert call_kwargs["severity"] == Severity.HIGH

    def test_list_invalid_status(self, client):
        """Test listing with invalid status."""
        response = client.get("/api/contradictions/list?status=invalid")
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_list_invalid_severity(self, client):
        """Test listing with invalid severity."""
        response = client.get("/api/contradictions/list?severity=invalid")
        assert response.status_code == 400
        assert "Invalid severity" in response.json()["detail"]


class TestGetContradictionEndpoint:
    """Tests for GET /api/contradictions/{contradiction_id} endpoint."""

    def test_get_contradiction(self, client, mock_storage):
        """Test getting specific contradiction."""
        contradiction = Contradiction(
            id="c-123",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Claim A",
            claim_b="Claim B",
            contradiction_type=ContradictionType.DIRECT,
            severity=Severity.HIGH,
            status=ContradictionStatus.DETECTED,
            confidence_score=0.9,
        )
        mock_storage.get.return_value = contradiction

        response = client.get("/api/contradictions/c-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "c-123"
        assert data["contradiction_type"] == "direct"

    def test_get_contradiction_not_found(self, client, mock_storage):
        """Test getting nonexistent contradiction."""
        mock_storage.get.return_value = None

        response = client.get("/api/contradictions/nonexistent")

        assert response.status_code == 404


class TestUpdateStatusEndpoint:
    """Tests for PUT /api/contradictions/{contradiction_id}/status endpoint."""

    def test_update_status(self, client, mock_storage, mock_event_bus):
        """Test updating contradiction status."""
        contradiction = Contradiction(
            id="c-123",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Claim A",
            claim_b="Claim B",
            status=ContradictionStatus.CONFIRMED,
        )
        mock_storage.update_status.return_value = contradiction

        response = client.put(
            "/api/contradictions/c-123/status",
            json={
                "status": "confirmed",
                "notes": "Verified as real contradiction",
                "analyst_id": "analyst@example.com",
            },
        )

        assert response.status_code == 200
        mock_event_bus.emit.assert_called()

    def test_update_status_not_found(self, client, mock_storage):
        """Test updating nonexistent contradiction."""
        mock_storage.update_status.return_value = None

        response = client.put(
            "/api/contradictions/nonexistent/status",
            json={"status": "confirmed"},
        )

        assert response.status_code == 404

    def test_update_status_invalid(self, client):
        """Test updating with invalid status."""
        response = client.put(
            "/api/contradictions/c-123/status",
            json={"status": "invalid_status"},
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]


class TestAddNotesEndpoint:
    """Tests for POST /api/contradictions/{contradiction_id}/notes endpoint."""

    def test_add_notes(self, client, mock_storage):
        """Test adding analyst notes."""
        contradiction = Contradiction(
            id="c-123",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Claim A",
            claim_b="Claim B",
        )
        mock_storage.add_note.return_value = contradiction

        response = client.post(
            "/api/contradictions/c-123/notes",
            json={
                "notes": "This needs further investigation.",
                "analyst_id": "analyst@example.com",
            },
        )

        assert response.status_code == 200

    def test_add_notes_not_found(self, client, mock_storage):
        """Test adding notes to nonexistent contradiction."""
        mock_storage.add_note.return_value = None

        response = client.post(
            "/api/contradictions/nonexistent/notes",
            json={"notes": "Test note"},
        )

        assert response.status_code == 404


class TestClaimsEndpoint:
    """Tests for POST /api/contradictions/claims endpoint."""

    def test_extract_claims(self, client, mock_detector):
        """Test extracting claims from text."""
        response = client.post(
            "/api/contradictions/claims",
            json={
                "text": "This is some text to extract claims from.",
                "document_id": "doc-123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "claims" in data
        assert "count" in data


class TestStatsEndpoint:
    """Tests for GET /api/contradictions/stats endpoint."""

    def test_get_stats(self, client, mock_storage):
        """Test getting statistics."""
        mock_storage.get_statistics.return_value = {
            "total_contradictions": 100,
            "by_status": {"detected": 60, "confirmed": 40},
            "by_severity": {"high": 20, "medium": 80},
            "by_type": {"direct": 50, "temporal": 50},
            "chains_detected": 5,
            "recent_count": 15,
        }

        response = client.get("/api/contradictions/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_contradictions"] == 100


class TestDetectChainsEndpoint:
    """Tests for POST /api/contradictions/detect-chains endpoint."""

    def test_detect_chains(self, client, mock_storage, mock_chain_detector):
        """Test detecting contradiction chains."""
        mock_storage.search.return_value = []
        mock_chain_detector.detect_chains.return_value = []

        response = client.post("/api/contradictions/detect-chains")

        assert response.status_code == 200
        data = response.json()
        assert "chains_detected" in data
        assert "chains" in data


class TestChainsEndpoint:
    """Tests for GET /api/contradictions/chains endpoint."""

    def test_list_chains(self, client, mock_storage):
        """Test listing chains."""
        chain = ContradictionChain(
            id="chain-1",
            contradiction_ids=["c-1", "c-2"],
            description="Test chain",
            severity=Severity.HIGH,
        )
        mock_storage.list_chains.return_value = [chain]

        response = client.get("/api/contradictions/chains")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["chains"]) == 1


class TestGetChainEndpoint:
    """Tests for GET /api/contradictions/chains/{chain_id} endpoint."""

    def test_get_chain(self, client, mock_storage):
        """Test getting specific chain."""
        chain = ContradictionChain(
            id="chain-123",
            contradiction_ids=["c-1", "c-2"],
            description="Test chain",
            severity=Severity.HIGH,
        )
        mock_storage.get_chain.return_value = chain
        mock_storage.get_chain_contradictions.return_value = []

        response = client.get("/api/contradictions/chains/chain-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "chain-123"

    def test_get_chain_not_found(self, client, mock_storage):
        """Test getting nonexistent chain."""
        mock_storage.get_chain.return_value = None

        response = client.get("/api/contradictions/chains/nonexistent")

        assert response.status_code == 404


class TestDeleteEndpoint:
    """Tests for DELETE /api/contradictions/{contradiction_id} endpoint."""

    def test_delete_contradiction(self, client, mock_storage):
        """Test deleting contradiction."""
        mock_storage.delete.return_value = True

        response = client.delete("/api/contradictions/c-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["contradiction_id"] == "c-123"

    def test_delete_not_found(self, client, mock_storage):
        """Test deleting nonexistent contradiction."""
        mock_storage.delete.return_value = False

        response = client.delete("/api/contradictions/nonexistent")

        assert response.status_code == 404
