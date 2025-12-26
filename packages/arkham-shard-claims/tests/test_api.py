"""
Claims Shard - API Tests

Tests for FastAPI endpoints using TestClient.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_claims.api import router
from arkham_shard_claims.models import (
    Claim,
    Evidence,
    ClaimStatus,
    ClaimType,
    ClaimExtractionResult,
    ClaimMatch,
    ClaimMergeResult,
    ClaimStatistics,
    EvidenceType,
    EvidenceRelationship,
    EvidenceStrength,
    ExtractionMethod,
)


# === Test Setup ===


@pytest.fixture
def mock_shard():
    """Create a mock ClaimsShard."""
    shard = MagicMock()
    shard.get_count = AsyncMock(return_value=42)
    shard.list_claims = AsyncMock(return_value=[])
    shard.create_claim = AsyncMock()
    shard.get_claim = AsyncMock(return_value=None)
    shard.update_claim_status = AsyncMock(return_value=None)
    shard.get_claim_evidence = AsyncMock(return_value=[])
    shard.add_evidence = AsyncMock()
    shard.extract_claims_from_text = AsyncMock()
    shard.find_similar_claims = AsyncMock(return_value=[])
    shard.merge_claims = AsyncMock()
    shard.get_statistics = AsyncMock()
    return shard


@pytest.fixture
def mock_frame(mock_shard):
    """Create a mock Frame that returns the mock shard."""
    frame = MagicMock()
    frame.get_shard = MagicMock(return_value=mock_shard)
    return frame


@pytest.fixture
def app(mock_frame):
    """Create test FastAPI app with mocked dependencies."""
    test_app = FastAPI()
    test_app.include_router(router)

    # Patch get_frame to return our mock
    with patch("arkham_shard_claims.api.get_frame", return_value=mock_frame):
        yield test_app


@pytest.fixture
def client(app, mock_frame):
    """Create test client with patched get_frame."""
    with patch("arkham_shard_claims.api.get_frame", return_value=mock_frame):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def sample_claim():
    """Create a sample claim for testing."""
    return Claim(
        id="claim-1",
        text="The sky is blue.",
        claim_type=ClaimType.FACTUAL,
        status=ClaimStatus.UNVERIFIED,
        confidence=0.95,
        source_document_id="doc-1",
        extracted_by=ExtractionMethod.LLM,
        entity_ids=["entity-1"],
        evidence_count=2,
        supporting_count=1,
        refuting_count=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        metadata={"source": "test"},
    )


@pytest.fixture
def sample_evidence():
    """Create sample evidence for testing."""
    return Evidence(
        id="ev-1",
        claim_id="claim-1",
        evidence_type=EvidenceType.DOCUMENT,
        reference_id="doc-123",
        reference_title="Test Document",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        excerpt="Relevant excerpt...",
        notes="Analyst notes",
        added_by="analyst-1",
        added_at=datetime.utcnow(),
        metadata={},
    )


# === Count Endpoint Tests ===


class TestCountEndpoint:
    """Tests for GET /api/claims/count"""

    def test_get_count(self, client, mock_shard):
        """Test getting claim count."""
        mock_shard.get_count.return_value = 42

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/count")

        assert response.status_code == 200
        assert response.json()["count"] == 42

    def test_get_count_with_status_filter(self, client, mock_shard):
        """Test getting count with status filter."""
        mock_shard.get_count.return_value = 15

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/count?status=verified")

        assert response.status_code == 200


# === List Endpoint Tests ===


class TestListEndpoint:
    """Tests for GET /api/claims/"""

    def test_list_claims_empty(self, client, mock_shard):
        """Test listing claims when empty."""
        mock_shard.list_claims.return_value = []
        mock_shard.get_count.return_value = 0

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/")

        assert response.status_code == 200
        data = response.json()
        assert data["claims"] == []
        assert data["total"] == 0

    def test_list_claims_with_results(self, client, mock_shard, sample_claim):
        """Test listing claims with results."""
        mock_shard.list_claims.return_value = [sample_claim]
        mock_shard.get_count.return_value = 1

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["claims"]) == 1
        assert data["claims"][0]["id"] == "claim-1"

    def test_list_claims_with_filters(self, client, mock_shard):
        """Test listing claims with query filters."""
        mock_shard.list_claims.return_value = []
        mock_shard.get_count.return_value = 0

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get(
                "/api/claims/?status=verified&claim_type=factual&min_confidence=0.8"
            )

        assert response.status_code == 200
        mock_shard.list_claims.assert_called_once()

    def test_list_claims_pagination(self, client, mock_shard):
        """Test listing claims with pagination."""
        mock_shard.list_claims.return_value = []
        mock_shard.get_count.return_value = 100

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/?limit=10&offset=20")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 20


# === Create Endpoint Tests ===


class TestCreateEndpoint:
    """Tests for POST /api/claims/"""

    def test_create_claim(self, client, mock_shard, sample_claim):
        """Test creating a claim."""
        mock_shard.create_claim.return_value = sample_claim

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/",
                json={
                    "text": "The sky is blue.",
                    "claim_type": "factual",
                    "confidence": 0.95,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["text"] == "The sky is blue."

    def test_create_claim_minimal(self, client, mock_shard, sample_claim):
        """Test creating a claim with minimal fields."""
        mock_shard.create_claim.return_value = sample_claim

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/",
                json={"text": "Simple claim."},
            )

        assert response.status_code == 201

    def test_create_claim_missing_text(self, client, mock_shard):
        """Test creating a claim without text fails."""
        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/",
                json={"claim_type": "factual"},
            )

        assert response.status_code == 422  # Validation error


# === Get Single Claim Tests ===


class TestGetClaimEndpoint:
    """Tests for GET /api/claims/{claim_id}"""

    def test_get_claim_found(self, client, mock_shard, sample_claim):
        """Test getting an existing claim."""
        mock_shard.get_claim.return_value = sample_claim

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/claim-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "claim-1"
        assert data["text"] == "The sky is blue."

    def test_get_claim_not_found(self, client, mock_shard):
        """Test getting a non-existent claim."""
        mock_shard.get_claim.return_value = None

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/nonexistent")

        assert response.status_code == 404


# === Update Status Tests ===


class TestUpdateStatusEndpoint:
    """Tests for PATCH /api/claims/{claim_id}/status"""

    def test_update_status(self, client, mock_shard, sample_claim):
        """Test updating claim status."""
        updated_claim = Claim(
            id=sample_claim.id,
            text=sample_claim.text,
            status=ClaimStatus.VERIFIED,
            claim_type=sample_claim.claim_type,
            confidence=sample_claim.confidence,
            created_at=sample_claim.created_at,
            updated_at=datetime.utcnow(),
            verified_at=datetime.utcnow(),
        )
        mock_shard.update_claim_status.return_value = updated_claim

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.patch(
                "/api/claims/claim-1/status",
                json={"status": "verified", "notes": "Confirmed"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "verified"

    def test_update_status_not_found(self, client, mock_shard):
        """Test updating status for non-existent claim."""
        mock_shard.update_claim_status.return_value = None

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.patch(
                "/api/claims/nonexistent/status",
                json={"status": "verified"},
            )

        assert response.status_code == 404


# === Delete Endpoint Tests ===


class TestDeleteEndpoint:
    """Tests for DELETE /api/claims/{claim_id}"""

    def test_delete_claim(self, client, mock_shard, sample_claim):
        """Test deleting (retracting) a claim."""
        mock_shard.update_claim_status.return_value = sample_claim

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.delete("/api/claims/claim-1")

        assert response.status_code == 204

    def test_delete_claim_not_found(self, client, mock_shard):
        """Test deleting non-existent claim."""
        mock_shard.update_claim_status.return_value = None

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.delete("/api/claims/nonexistent")

        assert response.status_code == 404


# === Evidence Endpoint Tests ===


class TestEvidenceEndpoints:
    """Tests for evidence-related endpoints."""

    def test_get_claim_evidence(self, client, mock_shard, sample_claim, sample_evidence):
        """Test getting evidence for a claim."""
        mock_shard.get_claim.return_value = sample_claim
        mock_shard.get_claim_evidence.return_value = [sample_evidence]

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/claim-1/evidence")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "ev-1"

    def test_get_evidence_claim_not_found(self, client, mock_shard):
        """Test getting evidence for non-existent claim."""
        mock_shard.get_claim.return_value = None

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/nonexistent/evidence")

        assert response.status_code == 404

    def test_add_evidence(self, client, mock_shard, sample_claim, sample_evidence):
        """Test adding evidence to a claim."""
        mock_shard.get_claim.return_value = sample_claim
        mock_shard.add_evidence.return_value = sample_evidence

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/claim-1/evidence",
                json={
                    "evidence_type": "document",
                    "reference_id": "doc-123",
                    "relationship": "supports",
                    "strength": "strong",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["evidence_type"] == "document"

    def test_add_evidence_claim_not_found(self, client, mock_shard):
        """Test adding evidence to non-existent claim."""
        mock_shard.get_claim.return_value = None

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/nonexistent/evidence",
                json={
                    "evidence_type": "document",
                    "reference_id": "doc-123",
                },
            )

        assert response.status_code == 404


# === Extraction Endpoint Tests ===


class TestExtractionEndpoint:
    """Tests for POST /api/claims/extract"""

    def test_extract_claims(self, client, mock_shard, sample_claim):
        """Test extracting claims from text."""
        mock_shard.extract_claims_from_text.return_value = ClaimExtractionResult(
            claims=[sample_claim],
            source_document_id="doc-1",
            extraction_method=ExtractionMethod.LLM,
            extraction_model="gpt-4",
            total_extracted=1,
            processing_time_ms=500.0,
            errors=[],
        )

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/extract",
                json={
                    "text": "Some text with claims.",
                    "document_id": "doc-1",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_extracted"] == 1
        assert len(data["claims"]) == 1

    def test_extract_claims_with_errors(self, client, mock_shard):
        """Test extraction that returns errors."""
        mock_shard.extract_claims_from_text.return_value = ClaimExtractionResult(
            claims=[],
            errors=["LLM unavailable"],
            total_extracted=0,
            processing_time_ms=10.0,
        )

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/extract",
                json={"text": "Some text."},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_extracted"] == 0
        assert len(data["errors"]) == 1


# === Similarity Endpoint Tests ===


class TestSimilarityEndpoint:
    """Tests for POST /api/claims/{claim_id}/similar"""

    def test_find_similar_claims(self, client, mock_shard, sample_claim):
        """Test finding similar claims."""
        mock_shard.get_claim.return_value = sample_claim
        mock_shard.find_similar_claims.return_value = [
            ClaimMatch(
                claim_id="claim-1",
                matched_claim_id="claim-2",
                similarity_score=0.92,
                match_type="semantic",
                suggested_action="review",
            )
        ]

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/claim-1/similar",
                json={"threshold": 0.8, "limit": 10},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["matched_claim_id"] == "claim-2"
        assert data[0]["similarity_score"] == 0.92

    def test_find_similar_claim_not_found(self, client, mock_shard):
        """Test finding similar claims for non-existent claim."""
        mock_shard.get_claim.return_value = None

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/nonexistent/similar",
                json={"threshold": 0.8},
            )

        assert response.status_code == 404


# === Merge Endpoint Tests ===


class TestMergeEndpoint:
    """Tests for POST /api/claims/{claim_id}/merge"""

    def test_merge_claims(self, client, mock_shard, sample_claim):
        """Test merging claims."""
        mock_shard.get_claim.return_value = sample_claim
        mock_shard.merge_claims.return_value = ClaimMergeResult(
            primary_claim_id="claim-1",
            merged_claim_ids=["claim-2", "claim-3"],
            evidence_transferred=3,
            entities_merged=2,
        )

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/claim-1/merge",
                json={"claim_ids_to_merge": ["claim-2", "claim-3"]},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["primary_claim_id"] == "claim-1"
        assert len(data["merged_claim_ids"]) == 2
        assert data["evidence_transferred"] == 3

    def test_merge_claim_not_found(self, client, mock_shard):
        """Test merging with non-existent primary claim."""
        mock_shard.get_claim.return_value = None

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.post(
                "/api/claims/nonexistent/merge",
                json={"claim_ids_to_merge": ["claim-2"]},
            )

        assert response.status_code == 404


# === Statistics Endpoint Tests ===


class TestStatisticsEndpoint:
    """Tests for GET /api/claims/stats/overview"""

    def test_get_statistics(self, client, mock_shard):
        """Test getting claim statistics."""
        mock_shard.get_statistics.return_value = ClaimStatistics(
            total_claims=100,
            by_status={"verified": 50, "unverified": 50},
            by_type={"factual": 80, "opinion": 20},
            by_extraction_method={"llm": 70, "manual": 30},
            total_evidence=200,
            evidence_supporting=150,
            evidence_refuting=50,
            claims_with_evidence=80,
            claims_without_evidence=20,
            avg_confidence=0.87,
            avg_evidence_per_claim=2.0,
        )

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/stats/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["total_claims"] == 100
        assert data["by_status"]["verified"] == 50
        assert data["avg_confidence"] == 0.87


# === Filtered List Endpoint Tests ===


class TestFilteredListEndpoints:
    """Tests for status-specific list endpoints."""

    def test_list_unverified(self, client, mock_shard, sample_claim):
        """Test listing unverified claims."""
        mock_shard.list_claims.return_value = [sample_claim]
        mock_shard.get_count.return_value = 1

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/status/unverified")

        assert response.status_code == 200

    def test_list_verified(self, client, mock_shard):
        """Test listing verified claims."""
        mock_shard.list_claims.return_value = []
        mock_shard.get_count.return_value = 0

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/status/verified")

        assert response.status_code == 200

    def test_list_disputed(self, client, mock_shard):
        """Test listing disputed claims."""
        mock_shard.list_claims.return_value = []
        mock_shard.get_count.return_value = 0

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/status/disputed")

        assert response.status_code == 200

    def test_list_by_document(self, client, mock_shard):
        """Test listing claims by document."""
        mock_shard.list_claims.return_value = []

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/by-document/doc-123")

        assert response.status_code == 200

    def test_list_by_entity(self, client, mock_shard):
        """Test listing claims by entity."""
        mock_shard.list_claims.return_value = []

        with patch("arkham_shard_claims.api._get_shard", return_value=mock_shard):
            response = client.get("/api/claims/by-entity/entity-123")

        assert response.status_code == 200
