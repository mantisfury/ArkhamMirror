"""
ACH Shard - Shard Class Tests

Tests for ACHShard with mocked Frame services.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from arkham_shard_ach.shard import ACHShard
from arkham_shard_ach.models import (
    ACHMatrix,
    Hypothesis,
    Evidence,
    Rating,
    HypothesisScore,
    ConsistencyRating,
    EvidenceType,
    MatrixStatus,
)


# === Fixtures ===


@pytest.fixture
def mock_events():
    """Create a mock events service."""
    events = AsyncMock()
    events.emit = AsyncMock()
    events.subscribe = AsyncMock()
    events.unsubscribe = AsyncMock()
    return events


@pytest.fixture
def mock_llm():
    """Create a mock LLM service."""
    llm = MagicMock()
    llm.generate = AsyncMock(return_value={"text": "Test response", "model": "test-model"})
    return llm


@pytest.fixture
def mock_frame(mock_events, mock_llm):
    """Create a mock Frame with all services."""
    frame = MagicMock()
    frame.get_service = MagicMock(side_effect=lambda name: {
        "events": mock_events,
        "llm": mock_llm,
        "database": None,
        "vectors": None,
    }.get(name))
    return frame


@pytest.fixture
async def initialized_shard(mock_frame):
    """Create an initialized ACHShard."""
    shard = ACHShard()
    await shard.initialize(mock_frame)
    return shard


# === Shard Metadata Tests ===


class TestShardMetadata:
    """Tests for shard metadata and properties."""

    def test_shard_name(self):
        """Verify shard name is correct."""
        shard = ACHShard()
        assert shard.name == "ach"

    def test_shard_version(self):
        """Verify shard version is correct."""
        shard = ACHShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Verify shard description exists and is meaningful."""
        shard = ACHShard()
        assert "Analysis of Competing Hypotheses" in shard.description


# === Initialization Tests ===


class TestInitialization:
    """Tests for shard initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_with_frame(self, mock_frame):
        """Test shard initializes correctly with frame."""
        shard = ACHShard()
        await shard.initialize(mock_frame)

        assert shard._frame == mock_frame
        assert shard.matrix_manager is not None
        assert shard.scorer is not None
        assert shard.evidence_analyzer is not None
        assert shard.exporter is not None

    @pytest.mark.asyncio
    async def test_initialize_with_llm(self, mock_frame, mock_llm):
        """Test shard initializes with LLM service when available."""
        shard = ACHShard()
        await shard.initialize(mock_frame)

        assert shard._llm_service == mock_llm

    @pytest.mark.asyncio
    async def test_initialize_without_llm(self, mock_events):
        """Test shard initializes without LLM service."""
        frame = MagicMock()
        frame.get_service = MagicMock(side_effect=lambda name: {
            "events": mock_events,
            "llm": None,
        }.get(name))

        shard = ACHShard()
        await shard.initialize(frame)

        assert shard._llm_service is None
        # Shard should still initialize
        assert shard.matrix_manager is not None

    @pytest.mark.asyncio
    async def test_shutdown(self, initialized_shard):
        """Test shard shuts down correctly."""
        shard = await initialized_shard
        await shard.shutdown()

        assert shard.matrix_manager is None
        assert shard.scorer is None
        assert shard.evidence_analyzer is None
        assert shard.exporter is None

    @pytest.mark.asyncio
    async def test_get_routes(self, initialized_shard):
        """Test get_routes returns a router."""
        shard = await initialized_shard
        router = shard.get_routes()

        assert router is not None
        assert hasattr(router, "routes")


# === Matrix Management Tests ===


class TestMatrixManagement:
    """Tests for matrix creation and management."""

    @pytest.mark.asyncio
    async def test_create_matrix(self, initialized_shard):
        """Test creating a matrix via public API."""
        shard = await initialized_shard

        matrix = shard.create_matrix(
            title="Test Matrix",
            description="A test matrix for ACH",
            created_by="analyst-1",
            project_id="project-1",
        )

        assert matrix is not None
        assert matrix.title == "Test Matrix"
        assert matrix.description == "A test matrix for ACH"
        assert matrix.created_by == "analyst-1"
        assert matrix.project_id == "project-1"
        assert matrix.status == MatrixStatus.DRAFT

    @pytest.mark.asyncio
    async def test_create_matrix_minimal(self, initialized_shard):
        """Test creating a matrix with minimal fields."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Minimal Matrix")

        assert matrix is not None
        assert matrix.title == "Minimal Matrix"
        assert matrix.description == ""
        assert matrix.created_by is None

    @pytest.mark.asyncio
    async def test_get_matrix(self, initialized_shard):
        """Test getting a matrix by ID."""
        shard = await initialized_shard

        # Create a matrix first
        created = shard.create_matrix(title="Test")
        matrix_id = created.id

        # Get it back
        retrieved = shard.get_matrix(matrix_id)

        assert retrieved is not None
        assert retrieved.id == matrix_id
        assert retrieved.title == "Test"

    @pytest.mark.asyncio
    async def test_get_matrix_not_found(self, initialized_shard):
        """Test getting a non-existent matrix."""
        shard = await initialized_shard

        matrix = shard.get_matrix("nonexistent-id")

        assert matrix is None

    @pytest.mark.asyncio
    async def test_create_matrix_not_initialized(self):
        """Test creating a matrix when shard not initialized."""
        shard = ACHShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            shard.create_matrix(title="Test")


# === Hypothesis Tests ===


class TestHypothesisManagement:
    """Tests for hypothesis management."""

    @pytest.mark.asyncio
    async def test_add_hypothesis(self, initialized_shard):
        """Test adding a hypothesis to a matrix."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        hypothesis = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Test Hypothesis",
            description="A test hypothesis",
        )

        assert hypothesis is not None
        assert hypothesis.title == "Test Hypothesis"
        assert hypothesis.matrix_id == matrix.id
        assert hypothesis.column_index == 0

    @pytest.mark.asyncio
    async def test_add_multiple_hypotheses(self, initialized_shard):
        """Test adding multiple hypotheses."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")

        h1 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Hypothesis 1",
        )
        h2 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Hypothesis 2",
        )
        h3 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Hypothesis 3",
        )

        assert h1.column_index == 0
        assert h2.column_index == 1
        assert h3.column_index == 2
        assert len(matrix.hypotheses) == 3

    @pytest.mark.asyncio
    async def test_remove_hypothesis(self, initialized_shard):
        """Test removing a hypothesis."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        h1 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Hypothesis 1",
        )
        h2 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Hypothesis 2",
        )

        result = shard.matrix_manager.remove_hypothesis(matrix.id, h1.id)

        assert result is True
        assert len(matrix.hypotheses) == 1
        assert matrix.hypotheses[0].title == "Hypothesis 2"
        # Column should be reindexed
        assert matrix.hypotheses[0].column_index == 0


# === Evidence Tests ===


class TestEvidenceManagement:
    """Tests for evidence management."""

    @pytest.mark.asyncio
    async def test_add_evidence(self, initialized_shard):
        """Test adding evidence to a matrix."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        evidence = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Test evidence",
            source="Document XYZ",
            evidence_type="document",
            credibility=0.9,
            relevance=0.85,
        )

        assert evidence is not None
        assert evidence.description == "Test evidence"
        assert evidence.source == "Document XYZ"
        assert evidence.evidence_type == EvidenceType.DOCUMENT
        assert evidence.credibility == 0.9
        assert evidence.relevance == 0.85
        assert evidence.row_index == 0

    @pytest.mark.asyncio
    async def test_add_evidence_clamps_values(self, initialized_shard):
        """Test that credibility and relevance are clamped to 0-1."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")

        # Test values over 1
        evidence = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Test",
            credibility=1.5,
            relevance=2.0,
        )
        assert evidence.credibility == 1.0
        assert evidence.relevance == 1.0

        # Test values under 0
        evidence2 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Test 2",
            credibility=-0.5,
            relevance=-1.0,
        )
        assert evidence2.credibility == 0.0
        assert evidence2.relevance == 0.0

    @pytest.mark.asyncio
    async def test_add_multiple_evidence(self, initialized_shard):
        """Test adding multiple evidence items."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")

        e1 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Evidence 1",
        )
        e2 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Evidence 2",
        )
        e3 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Evidence 3",
        )

        assert e1.row_index == 0
        assert e2.row_index == 1
        assert e3.row_index == 2
        assert len(matrix.evidence) == 3

    @pytest.mark.asyncio
    async def test_remove_evidence(self, initialized_shard):
        """Test removing evidence."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        e1 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Evidence 1",
        )
        e2 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Evidence 2",
        )

        result = shard.matrix_manager.remove_evidence(matrix.id, e1.id)

        assert result is True
        assert len(matrix.evidence) == 1
        assert matrix.evidence[0].description == "Evidence 2"
        # Row should be reindexed
        assert matrix.evidence[0].row_index == 0


# === Rating Tests ===


class TestRatingManagement:
    """Tests for rating management."""

    @pytest.mark.asyncio
    async def test_set_rating(self, initialized_shard):
        """Test setting a rating."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        hypothesis = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Test Hypothesis",
        )
        evidence = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Test Evidence",
        )

        rating = shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=evidence.id,
            hypothesis_id=hypothesis.id,
            rating=ConsistencyRating.CONSISTENT,
            reasoning="This evidence supports the hypothesis",
            confidence=0.9,
        )

        assert rating is not None
        assert rating.rating == ConsistencyRating.CONSISTENT
        assert rating.reasoning == "This evidence supports the hypothesis"
        assert rating.confidence == 0.9

    @pytest.mark.asyncio
    async def test_update_rating(self, initialized_shard):
        """Test updating an existing rating."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        hypothesis = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Test Hypothesis",
        )
        evidence = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Test Evidence",
        )

        # Set initial rating
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=evidence.id,
            hypothesis_id=hypothesis.id,
            rating=ConsistencyRating.CONSISTENT,
        )

        # Update rating
        updated = shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=evidence.id,
            hypothesis_id=hypothesis.id,
            rating=ConsistencyRating.INCONSISTENT,
            reasoning="Re-evaluated",
        )

        assert updated.rating == ConsistencyRating.INCONSISTENT
        assert updated.reasoning == "Re-evaluated"
        # Should still have only one rating
        assert len(matrix.ratings) == 1

    @pytest.mark.asyncio
    async def test_set_rating_clamps_confidence(self, initialized_shard):
        """Test that confidence is clamped to 0-1."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        hypothesis = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Test",
        )
        evidence = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Test",
        )

        rating = shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=evidence.id,
            hypothesis_id=hypothesis.id,
            rating=ConsistencyRating.NEUTRAL,
            confidence=1.5,
        )

        assert rating.confidence == 1.0


# === Scoring Tests ===


class TestScoring:
    """Tests for score calculation."""

    @pytest.mark.asyncio
    async def test_calculate_scores(self, initialized_shard):
        """Test calculating scores."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        h1 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Hypothesis 1",
        )
        h2 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Hypothesis 2",
        )
        e1 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Evidence 1",
        )

        # Rate evidence against hypotheses
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e1.id,
            hypothesis_id=h1.id,
            rating=ConsistencyRating.CONSISTENT,
        )
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e1.id,
            hypothesis_id=h2.id,
            rating=ConsistencyRating.INCONSISTENT,
        )

        scores = shard.calculate_scores(matrix.id)

        assert scores is not None
        assert len(scores) == 2

        # h1 should rank higher (less inconsistency)
        h1_score = next(s for s in scores if s.hypothesis_id == h1.id)
        h2_score = next(s for s in scores if s.hypothesis_id == h2.id)

        assert h1_score.rank < h2_score.rank
        assert h1_score.inconsistency_count == 0
        assert h2_score.inconsistency_count == 1

    @pytest.mark.asyncio
    async def test_calculate_scores_not_found(self, initialized_shard):
        """Test calculating scores for non-existent matrix."""
        shard = await initialized_shard

        result = shard.calculate_scores("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_scores_not_initialized(self):
        """Test calculating scores when shard not initialized."""
        shard = ACHShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            shard.calculate_scores("some-id")


# === Export Tests ===


class TestExport:
    """Tests for matrix export."""

    @pytest.mark.asyncio
    async def test_export_matrix_json(self, initialized_shard):
        """Test exporting matrix as JSON."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")
        shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Test Hypothesis",
        )

        export = shard.export_matrix(matrix.id, format="json")

        assert export is not None
        assert export.format == "json"
        assert isinstance(export.content, (dict, str))

    @pytest.mark.asyncio
    async def test_export_matrix_markdown(self, initialized_shard):
        """Test exporting matrix as Markdown."""
        shard = await initialized_shard

        matrix = shard.create_matrix(title="Test Matrix")

        export = shard.export_matrix(matrix.id, format="markdown")

        assert export is not None
        assert export.format == "markdown"

    @pytest.mark.asyncio
    async def test_export_matrix_not_found(self, initialized_shard):
        """Test exporting non-existent matrix."""
        shard = await initialized_shard

        result = shard.export_matrix("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_export_matrix_not_initialized(self):
        """Test exporting when shard not initialized."""
        shard = ACHShard()

        with pytest.raises(RuntimeError, match="not initialized"):
            shard.export_matrix("some-id")


# === Matrix Data Tests ===


class TestMatrixData:
    """Tests for matrix data retrieval."""

    @pytest.mark.asyncio
    async def test_get_matrix_data(self, initialized_shard):
        """Test getting structured matrix data."""
        shard = await initialized_shard

        matrix = shard.create_matrix(
            title="Test Matrix",
            description="Test description",
        )
        h1 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Hypothesis 1",
        )
        e1 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Evidence 1",
        )
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e1.id,
            hypothesis_id=h1.id,
            rating=ConsistencyRating.CONSISTENT,
        )

        data = shard.matrix_manager.get_matrix_data(matrix.id)

        assert data is not None
        assert data["id"] == matrix.id
        assert data["title"] == "Test Matrix"
        assert len(data["hypotheses"]) == 1
        assert len(data["evidence"]) == 1
        assert len(data["ratings"]) == 1

    @pytest.mark.asyncio
    async def test_get_matrix_data_not_found(self, initialized_shard):
        """Test getting data for non-existent matrix."""
        shard = await initialized_shard

        data = shard.matrix_manager.get_matrix_data("nonexistent")

        assert data is None


# === Integration Tests ===


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_ach_workflow(self, initialized_shard):
        """Test complete ACH analysis workflow."""
        shard = await initialized_shard

        # 1. Create matrix
        matrix = shard.create_matrix(
            title="Who stole the cookies?",
            description="Analysis of cookie theft incident",
        )

        # 2. Add hypotheses
        h1 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="The dog did it",
            description="The family dog stole the cookies",
        )
        h2 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="The child did it",
            description="The youngest child stole the cookies",
        )
        h3 = shard.matrix_manager.add_hypothesis(
            matrix_id=matrix.id,
            title="Outside intruder",
            description="Someone broke in and stole cookies",
        )

        # 3. Add evidence
        e1 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Crumbs found on the floor",
            evidence_type="physical",
            credibility=0.9,
        )
        e2 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="Dog was seen near the cookie jar",
            evidence_type="testimony",
            credibility=0.7,
        )
        e3 = shard.matrix_manager.add_evidence(
            matrix_id=matrix.id,
            description="All doors were locked",
            evidence_type="fact",
            credibility=1.0,
        )

        # 4. Rate evidence against hypotheses
        # Evidence 1: Crumbs - consistent with dog and child, inconsistent with intruder
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e1.id,
            hypothesis_id=h1.id,
            rating=ConsistencyRating.CONSISTENT,
        )
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e1.id,
            hypothesis_id=h2.id,
            rating=ConsistencyRating.CONSISTENT,
        )
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e1.id,
            hypothesis_id=h3.id,
            rating=ConsistencyRating.NEUTRAL,
        )

        # Evidence 2: Dog seen near jar - highly consistent with dog
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e2.id,
            hypothesis_id=h1.id,
            rating=ConsistencyRating.HIGHLY_CONSISTENT,
        )
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e2.id,
            hypothesis_id=h2.id,
            rating=ConsistencyRating.NEUTRAL,
        )
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e2.id,
            hypothesis_id=h3.id,
            rating=ConsistencyRating.INCONSISTENT,
        )

        # Evidence 3: Doors locked - inconsistent with intruder
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e3.id,
            hypothesis_id=h1.id,
            rating=ConsistencyRating.NOT_APPLICABLE,
        )
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e3.id,
            hypothesis_id=h2.id,
            rating=ConsistencyRating.NOT_APPLICABLE,
        )
        shard.matrix_manager.set_rating(
            matrix_id=matrix.id,
            evidence_id=e3.id,
            hypothesis_id=h3.id,
            rating=ConsistencyRating.HIGHLY_INCONSISTENT,
        )

        # 5. Calculate scores
        scores = shard.calculate_scores(matrix.id)

        assert len(scores) == 3

        # Dog hypothesis should rank first (least inconsistency)
        dog_score = next(s for s in scores if s.hypothesis_id == h1.id)
        intruder_score = next(s for s in scores if s.hypothesis_id == h3.id)

        assert dog_score.rank == 1
        assert dog_score.inconsistency_count == 0
        assert intruder_score.inconsistency_count == 2  # Two inconsistent ratings

        # 6. Verify leading hypothesis
        assert matrix.leading_hypothesis == h1
        assert h1.is_lead is True

        # 7. Export matrix
        export = shard.export_matrix(matrix.id, format="json")
        assert export is not None
