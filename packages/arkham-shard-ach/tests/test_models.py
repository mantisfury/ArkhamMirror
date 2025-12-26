"""
ACH Shard - Model Tests

Tests for all enums, dataclasses, and data models.
"""

import pytest
from datetime import datetime

from arkham_shard_ach.models import (
    # Enums
    ConsistencyRating,
    EvidenceType,
    MatrixStatus,
    # Dataclasses
    Hypothesis,
    Evidence,
    Rating,
    HypothesisScore,
    ACHMatrix,
    DevilsAdvocateChallenge,
    MatrixExport,
)


class TestConsistencyRatingEnum:
    """Tests for ConsistencyRating enum."""

    def test_all_values_exist(self):
        """Verify all expected rating values exist."""
        assert ConsistencyRating.HIGHLY_CONSISTENT.value == "++"
        assert ConsistencyRating.CONSISTENT.value == "+"
        assert ConsistencyRating.NEUTRAL.value == "N"
        assert ConsistencyRating.INCONSISTENT.value == "-"
        assert ConsistencyRating.HIGHLY_INCONSISTENT.value == "--"
        assert ConsistencyRating.NOT_APPLICABLE.value == "N/A"

    def test_enum_count(self):
        """Verify total number of ratings."""
        assert len(ConsistencyRating) == 6

    def test_score_property(self):
        """Test that each rating has correct numeric score."""
        assert ConsistencyRating.HIGHLY_CONSISTENT.score == 2.0
        assert ConsistencyRating.CONSISTENT.score == 1.0
        assert ConsistencyRating.NEUTRAL.score == 0.0
        assert ConsistencyRating.INCONSISTENT.score == -1.0
        assert ConsistencyRating.HIGHLY_INCONSISTENT.score == -2.0
        assert ConsistencyRating.NOT_APPLICABLE.score == 0.0

    def test_weight_property(self):
        """Test that each rating has correct weight."""
        # All have weight 1.0 except N/A
        assert ConsistencyRating.HIGHLY_CONSISTENT.weight == 1.0
        assert ConsistencyRating.CONSISTENT.weight == 1.0
        assert ConsistencyRating.NEUTRAL.weight == 1.0
        assert ConsistencyRating.INCONSISTENT.weight == 1.0
        assert ConsistencyRating.HIGHLY_INCONSISTENT.weight == 1.0
        assert ConsistencyRating.NOT_APPLICABLE.weight == 0.0


class TestEvidenceTypeEnum:
    """Tests for EvidenceType enum."""

    def test_all_values_exist(self):
        """Verify all expected evidence type values exist."""
        assert EvidenceType.FACT.value == "fact"
        assert EvidenceType.TESTIMONY.value == "testimony"
        assert EvidenceType.DOCUMENT.value == "document"
        assert EvidenceType.PHYSICAL.value == "physical"
        assert EvidenceType.CIRCUMSTANTIAL.value == "circumstantial"
        assert EvidenceType.INFERENCE.value == "inference"

    def test_enum_count(self):
        """Verify total number of evidence types."""
        assert len(EvidenceType) == 6


class TestMatrixStatusEnum:
    """Tests for MatrixStatus enum."""

    def test_all_values_exist(self):
        """Verify all expected status values exist."""
        assert MatrixStatus.DRAFT.value == "draft"
        assert MatrixStatus.ACTIVE.value == "active"
        assert MatrixStatus.COMPLETED.value == "completed"
        assert MatrixStatus.ARCHIVED.value == "archived"

    def test_enum_count(self):
        """Verify total number of statuses."""
        assert len(MatrixStatus) == 4


class TestHypothesisDataclass:
    """Tests for Hypothesis dataclass."""

    def test_minimal_creation(self):
        """Test creating a hypothesis with minimal required fields."""
        hypothesis = Hypothesis(
            id="h-1",
            matrix_id="m-1",
            title="Test Hypothesis",
        )
        assert hypothesis.id == "h-1"
        assert hypothesis.matrix_id == "m-1"
        assert hypothesis.title == "Test Hypothesis"
        assert hypothesis.description == ""
        assert hypothesis.column_index == 0
        assert hypothesis.is_lead is False

    def test_full_creation(self):
        """Test creating a hypothesis with all fields."""
        now = datetime.utcnow()
        hypothesis = Hypothesis(
            id="h-full",
            matrix_id="m-1",
            title="Full Hypothesis",
            description="A detailed description",
            column_index=2,
            created_at=now,
            updated_at=now,
            author="analyst-1",
            is_lead=True,
            notes="Some notes",
        )
        assert hypothesis.id == "h-full"
        assert hypothesis.description == "A detailed description"
        assert hypothesis.column_index == 2
        assert hypothesis.is_lead is True
        assert hypothesis.author == "analyst-1"
        assert hypothesis.notes == "Some notes"

    def test_default_values(self):
        """Test that default values are set correctly."""
        hypothesis = Hypothesis(id="h-1", matrix_id="m-1", title="Test")
        assert hypothesis.description == ""
        assert hypothesis.column_index == 0
        assert hypothesis.author is None
        assert hypothesis.is_lead is False
        assert hypothesis.notes == ""


class TestEvidenceDataclass:
    """Tests for Evidence dataclass."""

    def test_minimal_creation(self):
        """Test creating evidence with minimal required fields."""
        evidence = Evidence(
            id="e-1",
            matrix_id="m-1",
            description="Test evidence",
        )
        assert evidence.id == "e-1"
        assert evidence.matrix_id == "m-1"
        assert evidence.description == "Test evidence"
        assert evidence.evidence_type == EvidenceType.FACT
        assert evidence.credibility == 1.0
        assert evidence.relevance == 1.0

    def test_full_creation(self):
        """Test creating evidence with all fields."""
        now = datetime.utcnow()
        evidence = Evidence(
            id="e-full",
            matrix_id="m-1",
            description="Full evidence item",
            source="Document XYZ",
            evidence_type=EvidenceType.DOCUMENT,
            credibility=0.8,
            relevance=0.9,
            row_index=3,
            created_at=now,
            updated_at=now,
            author="analyst-1",
            document_ids=["doc-1", "doc-2"],
            notes="Additional notes",
        )
        assert evidence.source == "Document XYZ"
        assert evidence.evidence_type == EvidenceType.DOCUMENT
        assert evidence.credibility == 0.8
        assert evidence.relevance == 0.9
        assert evidence.row_index == 3
        assert len(evidence.document_ids) == 2

    def test_default_values(self):
        """Test that default values are set correctly."""
        evidence = Evidence(id="e-1", matrix_id="m-1", description="Test")
        assert evidence.source == ""
        assert evidence.evidence_type == EvidenceType.FACT
        assert evidence.credibility == 1.0
        assert evidence.relevance == 1.0
        assert evidence.row_index == 0
        assert evidence.document_ids == []
        assert evidence.notes == ""


class TestRatingDataclass:
    """Tests for Rating dataclass."""

    def test_minimal_creation(self):
        """Test creating a rating with minimal required fields."""
        rating = Rating(
            matrix_id="m-1",
            evidence_id="e-1",
            hypothesis_id="h-1",
            rating=ConsistencyRating.CONSISTENT,
        )
        assert rating.matrix_id == "m-1"
        assert rating.evidence_id == "e-1"
        assert rating.hypothesis_id == "h-1"
        assert rating.rating == ConsistencyRating.CONSISTENT
        assert rating.confidence == 1.0

    def test_full_creation(self):
        """Test creating a rating with all fields."""
        now = datetime.utcnow()
        rating = Rating(
            matrix_id="m-1",
            evidence_id="e-1",
            hypothesis_id="h-1",
            rating=ConsistencyRating.HIGHLY_INCONSISTENT,
            reasoning="The evidence contradicts this hypothesis",
            confidence=0.85,
            created_at=now,
            updated_at=now,
            author="analyst-1",
        )
        assert rating.rating == ConsistencyRating.HIGHLY_INCONSISTENT
        assert rating.reasoning == "The evidence contradicts this hypothesis"
        assert rating.confidence == 0.85
        assert rating.author == "analyst-1"

    def test_weighted_score_property(self):
        """Test weighted score calculation."""
        # Highly consistent with full confidence
        rating = Rating(
            matrix_id="m-1",
            evidence_id="e-1",
            hypothesis_id="h-1",
            rating=ConsistencyRating.HIGHLY_CONSISTENT,
            confidence=1.0,
        )
        assert rating.weighted_score == 2.0  # 2.0 * 1.0 * 1.0

        # Consistent with partial confidence
        rating = Rating(
            matrix_id="m-1",
            evidence_id="e-1",
            hypothesis_id="h-1",
            rating=ConsistencyRating.CONSISTENT,
            confidence=0.5,
        )
        assert rating.weighted_score == 0.5  # 1.0 * 0.5 * 1.0

        # N/A has zero weight
        rating = Rating(
            matrix_id="m-1",
            evidence_id="e-1",
            hypothesis_id="h-1",
            rating=ConsistencyRating.NOT_APPLICABLE,
            confidence=1.0,
        )
        assert rating.weighted_score == 0.0  # 0.0 * 1.0 * 0.0

    def test_default_values(self):
        """Test that default values are set correctly."""
        rating = Rating(
            matrix_id="m-1",
            evidence_id="e-1",
            hypothesis_id="h-1",
            rating=ConsistencyRating.NEUTRAL,
        )
        assert rating.reasoning == ""
        assert rating.confidence == 1.0
        assert rating.author is None


class TestHypothesisScoreDataclass:
    """Tests for HypothesisScore dataclass."""

    def test_minimal_creation(self):
        """Test creating a score with minimal fields."""
        score = HypothesisScore(hypothesis_id="h-1")
        assert score.hypothesis_id == "h-1"
        assert score.consistency_score == 0.0
        assert score.inconsistency_count == 0
        assert score.rank == 0

    def test_full_creation(self):
        """Test creating a score with all fields."""
        now = datetime.utcnow()
        score = HypothesisScore(
            hypothesis_id="h-1",
            consistency_score=5.0,
            inconsistency_count=2,
            weighted_score=4.5,
            normalized_score=75.0,
            rank=1,
            evidence_count=10,
            calculation_timestamp=now,
        )
        assert score.consistency_score == 5.0
        assert score.inconsistency_count == 2
        assert score.weighted_score == 4.5
        assert score.normalized_score == 75.0
        assert score.rank == 1
        assert score.evidence_count == 10


class TestACHMatrixDataclass:
    """Tests for ACHMatrix dataclass."""

    def test_minimal_creation(self):
        """Test creating a matrix with minimal required fields."""
        matrix = ACHMatrix(
            id="m-1",
            title="Test Matrix",
        )
        assert matrix.id == "m-1"
        assert matrix.title == "Test Matrix"
        assert matrix.status == MatrixStatus.DRAFT
        assert matrix.hypotheses == []
        assert matrix.evidence == []
        assert matrix.ratings == []
        assert matrix.scores == []

    def test_full_creation(self):
        """Test creating a matrix with all fields."""
        now = datetime.utcnow()
        matrix = ACHMatrix(
            id="m-full",
            title="Full Matrix",
            description="A detailed matrix description",
            status=MatrixStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            created_by="analyst-1",
            project_id="project-1",
            tags=["important", "review"],
            notes="Matrix notes",
        )
        assert matrix.description == "A detailed matrix description"
        assert matrix.status == MatrixStatus.ACTIVE
        assert matrix.created_by == "analyst-1"
        assert matrix.project_id == "project-1"
        assert len(matrix.tags) == 2

    def test_get_hypothesis(self):
        """Test getting a hypothesis by ID."""
        matrix = ACHMatrix(id="m-1", title="Test")
        h1 = Hypothesis(id="h-1", matrix_id="m-1", title="Hypothesis 1")
        h2 = Hypothesis(id="h-2", matrix_id="m-1", title="Hypothesis 2")
        matrix.hypotheses = [h1, h2]

        assert matrix.get_hypothesis("h-1") == h1
        assert matrix.get_hypothesis("h-2") == h2
        assert matrix.get_hypothesis("h-3") is None

    def test_get_evidence(self):
        """Test getting evidence by ID."""
        matrix = ACHMatrix(id="m-1", title="Test")
        e1 = Evidence(id="e-1", matrix_id="m-1", description="Evidence 1")
        e2 = Evidence(id="e-2", matrix_id="m-1", description="Evidence 2")
        matrix.evidence = [e1, e2]

        assert matrix.get_evidence("e-1") == e1
        assert matrix.get_evidence("e-2") == e2
        assert matrix.get_evidence("e-3") is None

    def test_get_rating(self):
        """Test getting a rating for evidence-hypothesis pair."""
        matrix = ACHMatrix(id="m-1", title="Test")
        r1 = Rating(
            matrix_id="m-1",
            evidence_id="e-1",
            hypothesis_id="h-1",
            rating=ConsistencyRating.CONSISTENT,
        )
        r2 = Rating(
            matrix_id="m-1",
            evidence_id="e-1",
            hypothesis_id="h-2",
            rating=ConsistencyRating.INCONSISTENT,
        )
        matrix.ratings = [r1, r2]

        assert matrix.get_rating("e-1", "h-1") == r1
        assert matrix.get_rating("e-1", "h-2") == r2
        assert matrix.get_rating("e-1", "h-3") is None
        assert matrix.get_rating("e-2", "h-1") is None

    def test_get_score(self):
        """Test getting score for a hypothesis."""
        matrix = ACHMatrix(id="m-1", title="Test")
        s1 = HypothesisScore(hypothesis_id="h-1", rank=1)
        s2 = HypothesisScore(hypothesis_id="h-2", rank=2)
        matrix.scores = [s1, s2]

        assert matrix.get_score("h-1") == s1
        assert matrix.get_score("h-2") == s2
        assert matrix.get_score("h-3") is None

    def test_leading_hypothesis(self):
        """Test getting the leading hypothesis."""
        matrix = ACHMatrix(id="m-1", title="Test")
        h1 = Hypothesis(id="h-1", matrix_id="m-1", title="Hypothesis 1")
        h2 = Hypothesis(id="h-2", matrix_id="m-1", title="Hypothesis 2")
        matrix.hypotheses = [h1, h2]

        # No scores yet
        assert matrix.leading_hypothesis is None

        # Add scores
        s1 = HypothesisScore(hypothesis_id="h-1", rank=2)
        s2 = HypothesisScore(hypothesis_id="h-2", rank=1)
        matrix.scores = [s1, s2]

        # h-2 has rank 1, so it's the leader
        assert matrix.leading_hypothesis == h2

    def test_default_values(self):
        """Test that default values are set correctly."""
        matrix = ACHMatrix(id="m-1", title="Test")
        assert matrix.description == ""
        assert matrix.status == MatrixStatus.DRAFT
        assert matrix.hypotheses == []
        assert matrix.evidence == []
        assert matrix.ratings == []
        assert matrix.scores == []
        assert matrix.created_by is None
        assert matrix.project_id is None
        assert matrix.tags == []
        assert matrix.notes == ""


class TestDevilsAdvocateChallengeDataclass:
    """Tests for DevilsAdvocateChallenge dataclass."""

    def test_minimal_creation(self):
        """Test creating a challenge with minimal fields."""
        challenge = DevilsAdvocateChallenge(
            matrix_id="m-1",
            hypothesis_id="h-1",
            challenge_text="This hypothesis may be wrong because...",
            alternative_interpretation="An alternative view is...",
        )
        assert challenge.matrix_id == "m-1"
        assert challenge.hypothesis_id == "h-1"
        assert challenge.challenge_text == "This hypothesis may be wrong because..."
        assert challenge.weaknesses_identified == []
        assert challenge.evidence_gaps == []

    def test_full_creation(self):
        """Test creating a challenge with all fields."""
        now = datetime.utcnow()
        challenge = DevilsAdvocateChallenge(
            matrix_id="m-1",
            hypothesis_id="h-1",
            challenge_text="Main challenge",
            alternative_interpretation="Alternative view",
            weaknesses_identified=["weakness 1", "weakness 2"],
            evidence_gaps=["gap 1", "gap 2"],
            recommended_investigations=["investigate X", "check Y"],
            created_at=now,
            model_used="gpt-4",
        )
        assert len(challenge.weaknesses_identified) == 2
        assert len(challenge.evidence_gaps) == 2
        assert len(challenge.recommended_investigations) == 2
        assert challenge.model_used == "gpt-4"


class TestMatrixExportDataclass:
    """Tests for MatrixExport dataclass."""

    def test_json_export(self):
        """Test creating a JSON export."""
        matrix = ACHMatrix(id="m-1", title="Test")
        export = MatrixExport(
            matrix=matrix,
            format="json",
            content={"id": "m-1", "title": "Test"},
        )
        assert export.format == "json"
        assert isinstance(export.content, dict)
        assert export.content["id"] == "m-1"

    def test_markdown_export(self):
        """Test creating a Markdown export."""
        matrix = ACHMatrix(id="m-1", title="Test")
        export = MatrixExport(
            matrix=matrix,
            format="markdown",
            content="# Test Matrix\n\nMatrix content here...",
        )
        assert export.format == "markdown"
        assert isinstance(export.content, str)
        assert "# Test Matrix" in export.content

    def test_export_timestamp(self):
        """Test that export has generated_at timestamp."""
        matrix = ACHMatrix(id="m-1", title="Test")
        export = MatrixExport(
            matrix=matrix,
            format="csv",
            content="col1,col2\nval1,val2",
        )
        assert export.generated_at is not None
        assert isinstance(export.generated_at, datetime)
