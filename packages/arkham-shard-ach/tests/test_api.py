"""
ACH Shard - API Tests

Tests for FastAPI endpoints using TestClient.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_ach.api import router, init_api
from arkham_shard_ach.models import (
    ACHMatrix,
    Hypothesis,
    Evidence,
    Rating,
    HypothesisScore,
    ConsistencyRating,
    EvidenceType,
    MatrixStatus,
    MatrixExport,
)


# === Test Setup ===


@pytest.fixture
def mock_matrix_manager():
    """Create a mock MatrixManager."""
    manager = MagicMock()
    manager.create_matrix = MagicMock()
    manager.get_matrix = MagicMock(return_value=None)
    manager.get_matrix_data = MagicMock(return_value=None)
    manager.update_matrix = MagicMock(return_value=None)
    manager.delete_matrix = MagicMock(return_value=False)
    manager.list_matrices = MagicMock(return_value=[])
    manager.add_hypothesis = MagicMock(return_value=None)
    manager.remove_hypothesis = MagicMock(return_value=False)
    manager.add_evidence = MagicMock(return_value=None)
    manager.remove_evidence = MagicMock(return_value=False)
    manager.set_rating = MagicMock(return_value=None)
    return manager


@pytest.fixture
def mock_scorer():
    """Create a mock ACHScorer."""
    scorer = MagicMock()
    scorer.calculate_scores = MagicMock(return_value=[])
    scorer.get_diagnosticity_report = MagicMock(return_value={})
    scorer.get_sensitivity_analysis = MagicMock(return_value={})
    return scorer


@pytest.fixture
def mock_evidence_analyzer():
    """Create a mock EvidenceAnalyzer."""
    analyzer = MagicMock()
    analyzer.identify_gaps = MagicMock(return_value={})
    return analyzer


@pytest.fixture
def mock_exporter():
    """Create a mock MatrixExporter."""
    exporter = MagicMock()
    exporter.export = MagicMock()
    return exporter


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus."""
    bus = AsyncMock()
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    llm = MagicMock()
    llm.generate = AsyncMock(return_value={"text": "Generated text", "model": "test-model"})
    return llm


@pytest.fixture
def app(mock_matrix_manager, mock_scorer, mock_evidence_analyzer, mock_exporter, mock_event_bus, mock_llm_service):
    """Create test FastAPI app with mocked dependencies."""
    test_app = FastAPI()
    test_app.include_router(router)

    # Initialize API with mocks
    init_api(
        matrix_manager=mock_matrix_manager,
        scorer=mock_scorer,
        evidence_analyzer=mock_evidence_analyzer,
        exporter=mock_exporter,
        event_bus=mock_event_bus,
        llm_service=mock_llm_service,
    )

    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_matrix():
    """Create a sample ACH matrix for testing."""
    return ACHMatrix(
        id="matrix-1",
        title="Test Matrix",
        description="A test matrix",
        status=MatrixStatus.ACTIVE,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        created_by="analyst-1",
        project_id="project-1",
    )


@pytest.fixture
def sample_hypothesis():
    """Create a sample hypothesis for testing."""
    return Hypothesis(
        id="h-1",
        matrix_id="matrix-1",
        title="Test Hypothesis",
        description="A test hypothesis",
        column_index=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_evidence():
    """Create sample evidence for testing."""
    return Evidence(
        id="e-1",
        matrix_id="matrix-1",
        description="Test evidence description",
        source="Test source",
        evidence_type=EvidenceType.FACT,
        credibility=0.9,
        relevance=0.85,
        row_index=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_rating():
    """Create a sample rating for testing."""
    return Rating(
        matrix_id="matrix-1",
        evidence_id="e-1",
        hypothesis_id="h-1",
        rating=ConsistencyRating.CONSISTENT,
        reasoning="The evidence supports this hypothesis",
        confidence=0.9,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


# === Matrix CRUD Endpoint Tests ===


class TestCreateMatrixEndpoint:
    """Tests for POST /api/ach/matrix"""

    def test_create_matrix(self, client, mock_matrix_manager, sample_matrix):
        """Test creating a matrix."""
        mock_matrix_manager.create_matrix.return_value = sample_matrix

        response = client.post(
            "/api/ach/matrix",
            json={
                "title": "Test Matrix",
                "description": "A test matrix",
                "project_id": "project-1",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["matrix_id"] == "matrix-1"
        assert data["title"] == "Test Matrix"
        assert data["status"] == "active"

    def test_create_matrix_minimal(self, client, mock_matrix_manager, sample_matrix):
        """Test creating a matrix with minimal fields."""
        mock_matrix_manager.create_matrix.return_value = sample_matrix

        response = client.post(
            "/api/ach/matrix",
            json={"title": "Minimal Matrix"},
        )

        assert response.status_code == 200

    def test_create_matrix_missing_title(self, client):
        """Test creating a matrix without title fails."""
        response = client.post(
            "/api/ach/matrix",
            json={"description": "No title"},
        )

        assert response.status_code == 422  # Validation error


class TestGetMatrixEndpoint:
    """Tests for GET /api/ach/matrix/{matrix_id}"""

    def test_get_matrix_found(self, client, mock_matrix_manager):
        """Test getting an existing matrix."""
        mock_matrix_manager.get_matrix_data.return_value = {
            "id": "matrix-1",
            "title": "Test Matrix",
            "description": "A test",
            "status": "active",
            "hypotheses": [],
            "evidence": [],
            "ratings": [],
            "scores": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": None,
            "project_id": None,
            "tags": [],
            "notes": "",
        }

        response = client.get("/api/ach/matrix/matrix-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "matrix-1"
        assert data["title"] == "Test Matrix"

    def test_get_matrix_not_found(self, client, mock_matrix_manager):
        """Test getting a non-existent matrix."""
        mock_matrix_manager.get_matrix_data.return_value = None

        response = client.get("/api/ach/matrix/nonexistent")

        assert response.status_code == 404


class TestUpdateMatrixEndpoint:
    """Tests for PUT /api/ach/matrix/{matrix_id}"""

    def test_update_matrix(self, client, mock_matrix_manager, sample_matrix):
        """Test updating a matrix."""
        sample_matrix.title = "Updated Title"
        mock_matrix_manager.update_matrix.return_value = sample_matrix

        response = client.put(
            "/api/ach/matrix/matrix-1",
            json={"title": "Updated Title", "status": "completed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    def test_update_matrix_not_found(self, client, mock_matrix_manager):
        """Test updating a non-existent matrix."""
        mock_matrix_manager.update_matrix.return_value = None

        response = client.put(
            "/api/ach/matrix/nonexistent",
            json={"title": "Updated"},
        )

        assert response.status_code == 404

    def test_update_matrix_invalid_status(self, client, mock_matrix_manager):
        """Test updating matrix with invalid status."""
        response = client.put(
            "/api/ach/matrix/matrix-1",
            json={"status": "invalid_status"},
        )

        assert response.status_code == 400


class TestDeleteMatrixEndpoint:
    """Tests for DELETE /api/ach/matrix/{matrix_id}"""

    def test_delete_matrix(self, client, mock_matrix_manager):
        """Test deleting a matrix."""
        mock_matrix_manager.delete_matrix.return_value = True

        response = client.delete("/api/ach/matrix/matrix-1")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"

    def test_delete_matrix_not_found(self, client, mock_matrix_manager):
        """Test deleting a non-existent matrix."""
        mock_matrix_manager.delete_matrix.return_value = False

        response = client.delete("/api/ach/matrix/nonexistent")

        assert response.status_code == 404


class TestListMatricesEndpoint:
    """Tests for GET /api/ach/matrices"""

    def test_list_matrices_empty(self, client, mock_matrix_manager):
        """Test listing matrices when empty."""
        mock_matrix_manager.list_matrices.return_value = []

        response = client.get("/api/ach/matrices")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["matrices"] == []

    def test_list_matrices_with_results(self, client, mock_matrix_manager, sample_matrix):
        """Test listing matrices with results."""
        sample_matrix.hypotheses = []
        sample_matrix.evidence = []
        mock_matrix_manager.list_matrices.return_value = [sample_matrix]

        response = client.get("/api/ach/matrices")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["matrices"][0]["id"] == "matrix-1"

    def test_list_matrices_with_filters(self, client, mock_matrix_manager):
        """Test listing matrices with filters."""
        mock_matrix_manager.list_matrices.return_value = []

        response = client.get("/api/ach/matrices?project_id=proj-1&status=active")

        assert response.status_code == 200
        mock_matrix_manager.list_matrices.assert_called()


class TestMatricesCountEndpoint:
    """Tests for GET /api/ach/matrices/count"""

    def test_get_count(self, client, mock_matrix_manager, sample_matrix):
        """Test getting active matrices count."""
        mock_matrix_manager.list_matrices.return_value = [sample_matrix]

        response = client.get("/api/ach/matrices/count")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1


# === Hypothesis Endpoint Tests ===


class TestAddHypothesisEndpoint:
    """Tests for POST /api/ach/hypothesis"""

    def test_add_hypothesis(self, client, mock_matrix_manager, sample_hypothesis):
        """Test adding a hypothesis."""
        mock_matrix_manager.add_hypothesis.return_value = sample_hypothesis

        response = client.post(
            "/api/ach/hypothesis",
            json={
                "matrix_id": "matrix-1",
                "title": "Test Hypothesis",
                "description": "A test hypothesis",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["hypothesis_id"] == "h-1"
        assert data["title"] == "Test Hypothesis"

    def test_add_hypothesis_matrix_not_found(self, client, mock_matrix_manager):
        """Test adding hypothesis to non-existent matrix."""
        mock_matrix_manager.add_hypothesis.return_value = None

        response = client.post(
            "/api/ach/hypothesis",
            json={
                "matrix_id": "nonexistent",
                "title": "Test",
            },
        )

        assert response.status_code == 404


class TestRemoveHypothesisEndpoint:
    """Tests for DELETE /api/ach/hypothesis/{matrix_id}/{hypothesis_id}"""

    def test_remove_hypothesis(self, client, mock_matrix_manager):
        """Test removing a hypothesis."""
        mock_matrix_manager.remove_hypothesis.return_value = True

        response = client.delete("/api/ach/hypothesis/matrix-1/h-1")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "removed"

    def test_remove_hypothesis_not_found(self, client, mock_matrix_manager):
        """Test removing non-existent hypothesis."""
        mock_matrix_manager.remove_hypothesis.return_value = False

        response = client.delete("/api/ach/hypothesis/matrix-1/nonexistent")

        assert response.status_code == 404


# === Evidence Endpoint Tests ===


class TestAddEvidenceEndpoint:
    """Tests for POST /api/ach/evidence"""

    def test_add_evidence(self, client, mock_matrix_manager, sample_evidence):
        """Test adding evidence."""
        mock_matrix_manager.add_evidence.return_value = sample_evidence

        response = client.post(
            "/api/ach/evidence",
            json={
                "matrix_id": "matrix-1",
                "description": "Test evidence",
                "source": "Test source",
                "evidence_type": "fact",
                "credibility": 0.9,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["evidence_id"] == "e-1"
        assert data["description"] == "Test evidence description"

    def test_add_evidence_matrix_not_found(self, client, mock_matrix_manager):
        """Test adding evidence to non-existent matrix."""
        mock_matrix_manager.add_evidence.return_value = None

        response = client.post(
            "/api/ach/evidence",
            json={
                "matrix_id": "nonexistent",
                "description": "Test",
            },
        )

        assert response.status_code == 404


class TestRemoveEvidenceEndpoint:
    """Tests for DELETE /api/ach/evidence/{matrix_id}/{evidence_id}"""

    def test_remove_evidence(self, client, mock_matrix_manager):
        """Test removing evidence."""
        mock_matrix_manager.remove_evidence.return_value = True

        response = client.delete("/api/ach/evidence/matrix-1/e-1")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "removed"

    def test_remove_evidence_not_found(self, client, mock_matrix_manager):
        """Test removing non-existent evidence."""
        mock_matrix_manager.remove_evidence.return_value = False

        response = client.delete("/api/ach/evidence/matrix-1/nonexistent")

        assert response.status_code == 404


# === Rating Endpoint Tests ===


class TestUpdateRatingEndpoint:
    """Tests for PUT /api/ach/rating"""

    def test_update_rating(self, client, mock_matrix_manager, sample_rating):
        """Test updating a rating."""
        mock_matrix_manager.set_rating.return_value = sample_rating

        response = client.put(
            "/api/ach/rating",
            json={
                "matrix_id": "matrix-1",
                "evidence_id": "e-1",
                "hypothesis_id": "h-1",
                "rating": "+",
                "reasoning": "Evidence supports this",
                "confidence": 0.9,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == "+"
        assert data["confidence"] == 0.9

    def test_update_rating_invalid(self, client, mock_matrix_manager):
        """Test updating with invalid rating value."""
        response = client.put(
            "/api/ach/rating",
            json={
                "matrix_id": "matrix-1",
                "evidence_id": "e-1",
                "hypothesis_id": "h-1",
                "rating": "invalid",
            },
        )

        assert response.status_code == 400

    def test_update_rating_not_found(self, client, mock_matrix_manager):
        """Test updating rating when matrix/evidence/hypothesis not found."""
        mock_matrix_manager.set_rating.return_value = None

        response = client.put(
            "/api/ach/rating",
            json={
                "matrix_id": "nonexistent",
                "evidence_id": "e-1",
                "hypothesis_id": "h-1",
                "rating": "+",
            },
        )

        assert response.status_code == 404


# === Scoring Endpoint Tests ===


class TestCalculateScoresEndpoint:
    """Tests for POST /api/ach/score"""

    def test_calculate_scores(self, client, mock_matrix_manager, mock_scorer, sample_matrix, sample_hypothesis):
        """Test calculating scores."""
        sample_matrix.hypotheses = [sample_hypothesis]
        mock_matrix_manager.get_matrix.return_value = sample_matrix

        score = HypothesisScore(
            hypothesis_id="h-1",
            consistency_score=5.0,
            inconsistency_count=1,
            weighted_score=4.5,
            normalized_score=75.0,
            rank=1,
            evidence_count=5,
        )
        mock_scorer.calculate_scores.return_value = [score]

        response = client.post("/api/ach/score?matrix_id=matrix-1")

        assert response.status_code == 200
        data = response.json()
        assert data["matrix_id"] == "matrix-1"
        assert len(data["scores"]) == 1
        assert data["scores"][0]["rank"] == 1

    def test_calculate_scores_matrix_not_found(self, client, mock_matrix_manager):
        """Test calculating scores for non-existent matrix."""
        mock_matrix_manager.get_matrix.return_value = None

        response = client.post("/api/ach/score?matrix_id=nonexistent")

        assert response.status_code == 404


# === Export Endpoint Tests ===


class TestExportEndpoint:
    """Tests for GET /api/ach/export/{matrix_id}"""

    def test_export_json(self, client, mock_matrix_manager, mock_exporter, sample_matrix):
        """Test exporting as JSON."""
        mock_matrix_manager.get_matrix.return_value = sample_matrix
        mock_exporter.export.return_value = MatrixExport(
            matrix=sample_matrix,
            format="json",
            content={"id": "matrix-1", "title": "Test"},
            generated_at=datetime.utcnow(),
        )

        response = client.get("/api/ach/export/matrix-1?format=json")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"
        assert data["content_type"] == "application/json"

    def test_export_markdown(self, client, mock_matrix_manager, mock_exporter, sample_matrix):
        """Test exporting as Markdown."""
        mock_matrix_manager.get_matrix.return_value = sample_matrix
        mock_exporter.export.return_value = MatrixExport(
            matrix=sample_matrix,
            format="markdown",
            content="# Test Matrix",
            generated_at=datetime.utcnow(),
        )

        response = client.get("/api/ach/export/matrix-1?format=markdown")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "markdown"
        assert data["content_type"] == "text/markdown"

    def test_export_matrix_not_found(self, client, mock_matrix_manager):
        """Test exporting non-existent matrix."""
        mock_matrix_manager.get_matrix.return_value = None

        response = client.get("/api/ach/export/nonexistent")

        assert response.status_code == 404


# === Analysis Endpoint Tests ===


class TestDiagnosticityEndpoint:
    """Tests for GET /api/ach/diagnosticity/{matrix_id}"""

    def test_get_diagnosticity(self, client, mock_matrix_manager, mock_scorer, sample_matrix):
        """Test getting diagnosticity report."""
        mock_matrix_manager.get_matrix.return_value = sample_matrix
        mock_scorer.get_diagnosticity_report.return_value = {
            "diagnostic_evidence": [],
            "total_evidence": 5,
            "diagnostic_count": 2,
        }

        response = client.get("/api/ach/diagnosticity/matrix-1")

        assert response.status_code == 200
        data = response.json()
        assert "diagnostic_evidence" in data

    def test_get_diagnosticity_not_found(self, client, mock_matrix_manager):
        """Test diagnosticity for non-existent matrix."""
        mock_matrix_manager.get_matrix.return_value = None

        response = client.get("/api/ach/diagnosticity/nonexistent")

        assert response.status_code == 404


class TestSensitivityEndpoint:
    """Tests for GET /api/ach/sensitivity/{matrix_id}"""

    def test_get_sensitivity(self, client, mock_matrix_manager, mock_scorer, sample_matrix):
        """Test getting sensitivity analysis."""
        mock_matrix_manager.get_matrix.return_value = sample_matrix
        mock_scorer.get_sensitivity_analysis.return_value = {
            "sensitivity": "low",
            "uncertain_evidence_count": 0,
            "rank_changes": [],
        }

        response = client.get("/api/ach/sensitivity/matrix-1")

        assert response.status_code == 200
        data = response.json()
        assert "sensitivity" in data

    def test_get_sensitivity_not_found(self, client, mock_matrix_manager):
        """Test sensitivity for non-existent matrix."""
        mock_matrix_manager.get_matrix.return_value = None

        response = client.get("/api/ach/sensitivity/nonexistent")

        assert response.status_code == 404


class TestEvidenceGapsEndpoint:
    """Tests for GET /api/ach/evidence-gaps/{matrix_id}"""

    def test_get_evidence_gaps(self, client, mock_matrix_manager, mock_evidence_analyzer, sample_matrix):
        """Test getting evidence gaps."""
        mock_matrix_manager.get_matrix.return_value = sample_matrix
        mock_evidence_analyzer.identify_gaps.return_value = {
            "gaps": ["Gap 1", "Gap 2"],
        }

        response = client.get("/api/ach/evidence-gaps/matrix-1")

        assert response.status_code == 200
        data = response.json()
        assert "gaps" in data

    def test_get_evidence_gaps_not_found(self, client, mock_matrix_manager):
        """Test evidence gaps for non-existent matrix."""
        mock_matrix_manager.get_matrix.return_value = None

        response = client.get("/api/ach/evidence-gaps/nonexistent")

        assert response.status_code == 404


# === AI Status Endpoint Tests ===


class TestAIStatusEndpoint:
    """Tests for GET /api/ach/ai/status"""

    def test_get_ai_status_available(self, client):
        """Test AI status when available."""
        response = client.get("/api/ach/ai/status")

        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "llm_service" in data


# === Devil's Advocate Endpoint Tests ===


class TestDevilsAdvocateEndpoint:
    """Tests for POST /api/ach/devils-advocate"""

    def test_devils_advocate(self, client, mock_matrix_manager, mock_llm_service, sample_matrix, sample_hypothesis):
        """Test devil's advocate challenge."""
        sample_matrix.hypotheses = [sample_hypothesis]
        sample_matrix.evidence = []
        sample_matrix.scores = [HypothesisScore(hypothesis_id="h-1", rank=1)]
        mock_matrix_manager.get_matrix.return_value = sample_matrix

        response = client.post(
            "/api/ach/devils-advocate",
            json={
                "matrix_id": "matrix-1",
                "hypothesis_id": "h-1",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["matrix_id"] == "matrix-1"
        assert data["hypothesis_id"] == "h-1"
        assert "challenge" in data

    def test_devils_advocate_matrix_not_found(self, client, mock_matrix_manager):
        """Test devil's advocate for non-existent matrix."""
        mock_matrix_manager.get_matrix.return_value = None

        response = client.post(
            "/api/ach/devils-advocate",
            json={"matrix_id": "nonexistent"},
        )

        assert response.status_code == 404
