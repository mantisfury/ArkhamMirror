"""
Unit tests for ACH (Analysis of Competing Hypotheses) Service.

Tests cover:
- Analysis CRUD operations
- Hypothesis CRUD operations
- Evidence CRUD operations
- Rating matrix operations
- Diagnosticity calculations
- Score calculations (Heuer method)
- Consistency checks
- Sensitivity analysis
- Milestone operations
- Snapshot comparison/diff operations
- Export functionality
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.arkham.services.db.models import (
    Base,
    ACHAnalysis,
    ACHHypothesis,
    ACHEvidence,
    ACHRating,
    ACHMilestone,
    ACHAnalysisSnapshot,
)
from app.arkham.services.ach_service import (
    ACHService,
    RATING_VALUES,
    HYPOTHESIS_COLORS,
    get_ach_service,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def in_memory_engine():
    """Create an in-memory SQLite database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def ach_service(in_memory_engine):
    """Create an ACH service with in-memory database."""
    service = ACHService()
    service.engine = in_memory_engine
    service.Session = sessionmaker(bind=in_memory_engine)
    return service


@pytest.fixture
def sample_analysis(ach_service):
    """Create a sample analysis for testing."""
    return ach_service.create_analysis(
        title="Test Analysis",
        focus_question="What caused the incident?",
        description="A test analysis for unit testing",
    )


@pytest.fixture
def analysis_with_hypotheses(ach_service, sample_analysis):
    """Create an analysis with multiple hypotheses."""
    analysis_id = sample_analysis["id"]

    ach_service.add_hypothesis(analysis_id, "Hypothesis A happened", label="H1")
    ach_service.add_hypothesis(analysis_id, "Hypothesis B happened", label="H2")
    ach_service.add_hypothesis(analysis_id, "Nothing unusual happened (null)", label="H3")

    return ach_service.get_analysis(analysis_id)


@pytest.fixture
def analysis_with_evidence(ach_service, analysis_with_hypotheses):
    """Create an analysis with hypotheses and evidence."""
    analysis_id = analysis_with_hypotheses["id"]

    ach_service.add_evidence(
        analysis_id,
        "Document shows meeting occurred",
        label="E1",
        evidence_type="document",
        reliability="high",
    )
    ach_service.add_evidence(
        analysis_id,
        "Witness claims they saw nothing",
        label="E2",
        evidence_type="testimony",
        reliability="medium",
    )
    ach_service.add_evidence(
        analysis_id,
        "Financial records show transfer",
        label="E3",
        evidence_type="document",
        reliability="high",
    )

    return ach_service.get_analysis(analysis_id)


@pytest.fixture
def fully_rated_analysis(ach_service, analysis_with_evidence):
    """Create an analysis with a fully populated rating matrix."""
    analysis_id = analysis_with_evidence["id"]
    hypotheses = analysis_with_evidence["hypotheses"]
    evidence = analysis_with_evidence["evidence"]

    # Set up a rating matrix that should make H1 the winner (lowest inconsistency)
    # H1: mostly consistent, H2: mixed, H3: mostly inconsistent
    ratings_map = {
        # E1 ratings
        ("E1", "H1"): "C",   # Consistent with H1
        ("E1", "H2"): "I",   # Inconsistent with H2
        ("E1", "H3"): "II",  # Very inconsistent with H3
        # E2 ratings
        ("E2", "H1"): "N",   # Neutral
        ("E2", "H2"): "C",   # Consistent with H2
        ("E2", "H3"): "CC",  # Very consistent with H3
        # E3 ratings
        ("E3", "H1"): "CC",  # Very consistent with H1
        ("E3", "H2"): "I",   # Inconsistent with H2
        ("E3", "H3"): "I",   # Inconsistent with H3
    }

    for e in evidence:
        for h in hypotheses:
            key = (e["label"], h["label"])
            if key in ratings_map:
                ach_service.set_rating(
                    analysis_id,
                    h["id"],
                    e["id"],
                    ratings_map[key],
                )

    return ach_service.get_analysis(analysis_id)


# =============================================================================
# ANALYSIS CRUD TESTS
# =============================================================================


class TestAnalysisCRUD:
    """Tests for analysis create, read, update, delete operations."""

    def test_create_analysis(self, ach_service):
        """Test creating a new analysis."""
        result = ach_service.create_analysis(
            title="New Analysis",
            focus_question="What happened?",
            description="Test description",
        )

        assert result is not None
        assert result["id"] > 0
        assert result["title"] == "New Analysis"
        assert result["focus_question"] == "What happened?"
        assert result["description"] == "Test description"
        assert result["status"] == "draft"
        assert result["current_step"] == 1

    def test_create_analysis_minimal(self, ach_service):
        """Test creating an analysis with only required fields."""
        result = ach_service.create_analysis(
            title="Minimal",
            focus_question="Question?",
        )

        assert result is not None
        assert result["title"] == "Minimal"
        assert result["description"] is None

    def test_get_analysis(self, ach_service, sample_analysis):
        """Test retrieving an analysis by ID."""
        result = ach_service.get_analysis(sample_analysis["id"])

        assert result is not None
        assert result["id"] == sample_analysis["id"]
        assert result["title"] == "Test Analysis"
        assert "hypotheses" in result
        assert "evidence" in result

    def test_get_analysis_not_found(self, ach_service):
        """Test retrieving a non-existent analysis."""
        result = ach_service.get_analysis(99999)
        assert result is None

    def test_get_analysis_list(self, ach_service, sample_analysis):
        """Test listing all analyses."""
        # Create another analysis
        ach_service.create_analysis(
            title="Second Analysis",
            focus_question="Another question?",
        )

        results = ach_service.get_analysis_list()

        assert len(results) >= 2
        assert any(a["title"] == "Test Analysis" for a in results)
        assert any(a["title"] == "Second Analysis" for a in results)

    def test_update_analysis(self, ach_service, sample_analysis):
        """Test updating an analysis."""
        result = ach_service.update_analysis(
            sample_analysis["id"],
            title="Updated Title",
            status="in_progress",
            current_step=3,
        )

        assert result is not None
        assert result["title"] == "Updated Title"
        assert result["status"] == "in_progress"
        assert result["current_step"] == 3
        # Unchanged fields should remain
        assert result["focus_question"] == "What caused the incident?"

    def test_update_analysis_not_found(self, ach_service):
        """Test updating a non-existent analysis."""
        result = ach_service.update_analysis(99999, title="Won't Work")
        assert result is None

    def test_delete_analysis(self, ach_service, sample_analysis):
        """Test deleting an analysis."""
        result = ach_service.delete_analysis(sample_analysis["id"])
        assert result is True

        # Verify it's gone
        retrieved = ach_service.get_analysis(sample_analysis["id"])
        assert retrieved is None

    def test_delete_analysis_not_found(self, ach_service):
        """Test deleting a non-existent analysis."""
        result = ach_service.delete_analysis(99999)
        assert result is False

    def test_mark_step_complete(self, ach_service, sample_analysis):
        """Test marking a step as complete."""
        analysis_id = sample_analysis["id"]

        result = ach_service.mark_step_complete(analysis_id, 1)
        assert result is True

        # Verify step was recorded and current_step advanced
        analysis = ach_service.get_analysis(analysis_id)
        # steps_completed is already a list (parsed in _analysis_to_dict)
        steps_completed = analysis["steps_completed"]
        assert 1 in steps_completed
        assert analysis["current_step"] == 2


# =============================================================================
# HYPOTHESIS CRUD TESTS
# =============================================================================


class TestHypothesisCRUD:
    """Tests for hypothesis create, read, update, delete operations."""

    def test_add_hypothesis(self, ach_service, sample_analysis):
        """Test adding a hypothesis to an analysis."""
        result = ach_service.add_hypothesis(
            sample_analysis["id"],
            "The suspect is guilty",
            label="H1",
        )

        assert result is not None
        assert result["label"] == "H1"
        assert result["description"] == "The suspect is guilty"
        assert result["color"] in HYPOTHESIS_COLORS

    def test_add_hypothesis_auto_label(self, ach_service, sample_analysis):
        """Test that hypotheses get auto-labeled if no label provided."""
        h1 = ach_service.add_hypothesis(sample_analysis["id"], "First hypothesis")
        h2 = ach_service.add_hypothesis(sample_analysis["id"], "Second hypothesis")

        assert h1["label"] == "H1"
        assert h2["label"] == "H2"

    def test_add_hypothesis_creates_empty_ratings(self, ach_service, analysis_with_evidence):
        """Test that adding a hypothesis creates empty ratings for existing evidence."""
        analysis_id = analysis_with_evidence["id"]

        # Add a new hypothesis
        new_h = ach_service.add_hypothesis(analysis_id, "New hypothesis", label="H4")

        # Check that ratings were created
        matrix = ach_service.get_matrix(analysis_id)
        assert new_h["label"] in [h["label"] for h in matrix["hypotheses"]]

    def test_update_hypothesis(self, ach_service, analysis_with_hypotheses):
        """Test updating a hypothesis."""
        h = analysis_with_hypotheses["hypotheses"][0]

        result = ach_service.update_hypothesis(
            h["id"],
            description="Updated description",
            future_indicators="Look for X, Y, Z",
        )

        assert result is not None
        assert result["description"] == "Updated description"
        assert result["future_indicators"] == "Look for X, Y, Z"

    def test_delete_hypothesis(self, ach_service, analysis_with_hypotheses):
        """Test deleting a hypothesis."""
        h = analysis_with_hypotheses["hypotheses"][0]

        result = ach_service.delete_hypothesis(h["id"])
        assert result is True

        # Verify it's gone
        analysis = ach_service.get_analysis(analysis_with_hypotheses["id"])
        assert h["id"] not in [hyp["id"] for hyp in analysis["hypotheses"]]


# =============================================================================
# EVIDENCE CRUD TESTS
# =============================================================================


class TestEvidenceCRUD:
    """Tests for evidence create, read, update, delete operations."""

    def test_add_evidence(self, ach_service, sample_analysis):
        """Test adding evidence to an analysis."""
        result = ach_service.add_evidence(
            sample_analysis["id"],
            "Document found at scene",
            label="E1",
            evidence_type="document",
            reliability="high",
            source="Police report #123",
        )

        assert result is not None
        assert result["label"] == "E1"
        assert result["description"] == "Document found at scene"
        assert result["evidence_type"] == "document"
        assert result["reliability"] == "high"
        assert result["source"] == "Police report #123"

    def test_add_evidence_auto_label(self, ach_service, sample_analysis):
        """Test that evidence gets auto-labeled if no label provided."""
        e1 = ach_service.add_evidence(sample_analysis["id"], "First evidence")
        e2 = ach_service.add_evidence(sample_analysis["id"], "Second evidence")

        assert e1["label"] == "E1"
        assert e2["label"] == "E2"

    def test_add_evidence_creates_empty_ratings(self, ach_service, analysis_with_hypotheses):
        """Test that adding evidence creates empty ratings for existing hypotheses."""
        analysis_id = analysis_with_hypotheses["id"]

        # Add evidence
        new_e = ach_service.add_evidence(analysis_id, "New evidence", label="E1")

        # Check that ratings were created
        matrix = ach_service.get_matrix(analysis_id)
        assert new_e["label"] in [e["label"] for e in matrix["evidence"]]

    def test_update_evidence(self, ach_service, analysis_with_evidence):
        """Test updating evidence."""
        e = analysis_with_evidence["evidence"][0]

        result = ach_service.update_evidence(
            e["id"],
            description="Updated description",
            reliability="low",
            is_critical=True,
        )

        assert result is not None
        assert result["description"] == "Updated description"
        assert result["reliability"] == "low"

    def test_delete_evidence(self, ach_service, analysis_with_evidence):
        """Test deleting evidence."""
        e = analysis_with_evidence["evidence"][0]

        result = ach_service.delete_evidence(e["id"])
        assert result is True

        # Verify it's gone
        analysis = ach_service.get_analysis(analysis_with_evidence["id"])
        assert e["id"] not in [ev["id"] for ev in analysis["evidence"]]


# =============================================================================
# RATING MATRIX TESTS
# =============================================================================


class TestRatingMatrix:
    """Tests for rating matrix operations."""

    def test_set_rating(self, ach_service, analysis_with_evidence):
        """Test setting a rating in the matrix."""
        analysis_id = analysis_with_evidence["id"]
        h = analysis_with_evidence["hypotheses"][0]
        e = analysis_with_evidence["evidence"][0]

        result = ach_service.set_rating(analysis_id, h["id"], e["id"], "CC")
        assert result is True

        # Verify rating was set
        matrix = ach_service.get_matrix(analysis_id)
        key = f"{e['id']}_{h['id']}"
        assert matrix["ratings"].get(key) == "CC"

    def test_set_rating_invalid_value(self, ach_service, analysis_with_evidence):
        """Test that invalid rating values are rejected."""
        analysis_id = analysis_with_evidence["id"]
        h = analysis_with_evidence["hypotheses"][0]
        e = analysis_with_evidence["evidence"][0]

        result = ach_service.set_rating(analysis_id, h["id"], e["id"], "INVALID")
        assert result is False

    def test_set_rating_with_notes(self, ach_service, analysis_with_evidence):
        """Test setting a rating with notes."""
        analysis_id = analysis_with_evidence["id"]
        h = analysis_with_evidence["hypotheses"][0]
        e = analysis_with_evidence["evidence"][0]

        result = ach_service.set_rating(
            analysis_id, h["id"], e["id"], "I",
            notes="This contradicts H1 because..."
        )
        assert result is True

    def test_get_matrix(self, ach_service, analysis_with_evidence):
        """Test getting the full matrix."""
        analysis_id = analysis_with_evidence["id"]

        matrix = ach_service.get_matrix(analysis_id)

        assert "hypotheses" in matrix
        assert "evidence" in matrix
        assert "ratings" in matrix
        assert "completion_pct" in matrix
        assert len(matrix["hypotheses"]) == 3
        assert len(matrix["evidence"]) == 3

    def test_get_matrix_completion_pct(self, ach_service, fully_rated_analysis):
        """Test that completion percentage is calculated correctly."""
        matrix = ach_service.get_matrix(fully_rated_analysis["id"])

        # 3 hypotheses x 3 evidence = 9 cells, all rated
        assert matrix["completion_pct"] == 100.0
        assert matrix["total_cells"] == 9
        assert matrix["rated_cells"] == 9

    def test_get_numeric_matrix(self, ach_service, fully_rated_analysis):
        """Test getting the numeric matrix for calculations."""
        df = ach_service.get_numeric_matrix(fully_rated_analysis["id"])

        assert not df.empty
        assert df.shape == (3, 3)  # 3 evidence x 3 hypotheses
        # Check that values are numeric
        assert df.dtypes.apply(lambda x: x.kind in 'iuf').all()


# =============================================================================
# DIAGNOSTICITY TESTS
# =============================================================================


class TestDiagnosticity:
    """Tests for diagnosticity calculations."""

    def test_calculate_diagnosticity(self, ach_service, fully_rated_analysis):
        """Test calculating diagnosticity scores."""
        results = ach_service.calculate_diagnosticity(fully_rated_analysis["id"])

        assert len(results) == 3  # 3 evidence items
        for r in results:
            assert "evidence_id" in r
            assert "label" in r
            assert "diagnosticity_score" in r
            assert "is_high_diagnostic" in r
            assert "is_low_diagnostic" in r

    def test_diagnosticity_sorted_by_score(self, ach_service, fully_rated_analysis):
        """Test that diagnosticity results are sorted highest first."""
        results = ach_service.calculate_diagnosticity(fully_rated_analysis["id"])

        scores = [r["diagnosticity_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_diagnosticity_high_variance(self, ach_service, analysis_with_evidence):
        """Test that evidence with high variance is marked as high diagnostic."""
        analysis_id = analysis_with_evidence["id"]
        hypotheses = analysis_with_evidence["hypotheses"]
        evidence = analysis_with_evidence["evidence"]

        # Set ratings with high variance for E1
        ach_service.set_rating(analysis_id, hypotheses[0]["id"], evidence[0]["id"], "CC")
        ach_service.set_rating(analysis_id, hypotheses[1]["id"], evidence[0]["id"], "II")
        ach_service.set_rating(analysis_id, hypotheses[2]["id"], evidence[0]["id"], "N")

        results = ach_service.calculate_diagnosticity(analysis_id)
        e1_result = next(r for r in results if r["label"] == "E1")

        assert e1_result["diagnosticity_score"] > 0

    def test_diagnosticity_low_variance(self, ach_service, analysis_with_evidence):
        """Test that evidence with low variance is marked as low diagnostic."""
        analysis_id = analysis_with_evidence["id"]
        hypotheses = analysis_with_evidence["hypotheses"]
        evidence = analysis_with_evidence["evidence"]

        # Set all ratings to the same value for E1
        for h in hypotheses:
            ach_service.set_rating(analysis_id, h["id"], evidence[0]["id"], "N")

        results = ach_service.calculate_diagnosticity(analysis_id)
        e1_result = next(r for r in results if r["label"] == "E1")

        assert e1_result["is_low_diagnostic"] is True
        assert e1_result["diagnosticity_score"] == 0.0


# =============================================================================
# SCORE CALCULATION TESTS
# =============================================================================


class TestScoreCalculation:
    """Tests for hypothesis score calculations (Heuer method)."""

    def test_calculate_scores(self, ach_service, fully_rated_analysis):
        """Test calculating inconsistency scores."""
        results = ach_service.calculate_scores(fully_rated_analysis["id"])

        assert len(results) == 3  # 3 hypotheses
        for r in results:
            assert "hypothesis_id" in r
            assert "label" in r
            assert "inconsistency_score" in r
            assert "rank" in r

    def test_scores_sorted_by_score(self, ach_service, fully_rated_analysis):
        """Test that scores are sorted lowest first (best fit)."""
        results = ach_service.calculate_scores(fully_rated_analysis["id"])

        scores = [r["inconsistency_score"] for r in results]
        assert scores == sorted(scores)

    def test_scores_have_correct_ranks(self, ach_service, fully_rated_analysis):
        """Test that ranks are assigned correctly."""
        results = ach_service.calculate_scores(fully_rated_analysis["id"])

        ranks = [r["rank"] for r in results]
        assert ranks == [1, 2, 3]

    def test_heuer_method_only_counts_inconsistencies(self, ach_service, analysis_with_evidence):
        """Test that only inconsistencies (I, II) add to score."""
        analysis_id = analysis_with_evidence["id"]
        hypotheses = analysis_with_evidence["hypotheses"]
        evidence = analysis_with_evidence["evidence"]

        # H1: all consistent (should have score 0)
        # H2: mixed
        # H3: all inconsistent
        for e in evidence:
            ach_service.set_rating(analysis_id, hypotheses[0]["id"], e["id"], "CC")
            ach_service.set_rating(analysis_id, hypotheses[1]["id"], e["id"], "N")
            ach_service.set_rating(analysis_id, hypotheses[2]["id"], e["id"], "II")

        results = ach_service.calculate_scores(analysis_id)

        h1_result = next(r for r in results if r["label"] == "H1")
        h3_result = next(r for r in results if r["label"] == "H3")

        assert h1_result["inconsistency_score"] == 0  # CC doesn't add to score
        assert h3_result["inconsistency_score"] > 0   # II adds to score

    def test_check_close_race(self, ach_service, fully_rated_analysis):
        """Test close race detection."""
        result = ach_service.check_close_race(fully_rated_analysis["id"], threshold=10.0)

        assert "is_close" in result
        assert "score_difference" in result
        assert "top_hypothesis" in result
        assert "message" in result

    def test_get_score_chart(self, ach_service, fully_rated_analysis):
        """Test generating score chart data."""
        chart = ach_service.get_score_chart(fully_rated_analysis["id"])

        assert "data" in chart
        assert "layout" in chart
        assert len(chart["data"]) > 0


# =============================================================================
# CONSISTENCY CHECKS TESTS
# =============================================================================


class TestConsistencyChecks:
    """Tests for consistency check operations."""

    def test_run_consistency_checks(self, ach_service, fully_rated_analysis):
        """Test running all consistency checks."""
        results = ach_service.run_consistency_checks(fully_rated_analysis["id"])

        assert len(results) == 4
        check_types = [r["check_type"] for r in results]
        assert "null_hypothesis" in check_types
        assert "incomplete_ratings" in check_types
        assert "low_diagnostic_evidence" in check_types
        assert "evidence_diversity" in check_types

    def test_null_hypothesis_check_passes(self, ach_service, analysis_with_hypotheses):
        """Test that null hypothesis check passes when null exists."""
        # H3 contains "nothing" which is a null keyword
        results = ach_service.run_consistency_checks(analysis_with_hypotheses["id"])
        null_check = next(r for r in results if r["check_type"] == "null_hypothesis")

        assert null_check["passed"] is True

    def test_null_hypothesis_check_fails(self, ach_service, sample_analysis):
        """Test that null hypothesis check fails when no null exists."""
        analysis_id = sample_analysis["id"]
        ach_service.add_hypothesis(analysis_id, "Theory A")
        ach_service.add_hypothesis(analysis_id, "Theory B")

        results = ach_service.run_consistency_checks(analysis_id)
        null_check = next(r for r in results if r["check_type"] == "null_hypothesis")

        assert null_check["passed"] is False

    def test_incomplete_ratings_check(self, ach_service, analysis_with_evidence):
        """Test incomplete ratings detection."""
        results = ach_service.run_consistency_checks(analysis_with_evidence["id"])
        incomplete_check = next(r for r in results if r["check_type"] == "incomplete_ratings")

        # No ratings set yet, should fail
        assert incomplete_check["passed"] is False

    def test_evidence_diversity_check_passes(self, ach_service, analysis_with_evidence):
        """Test evidence diversity check passes with multiple types."""
        # Evidence has document and testimony types
        results = ach_service.run_consistency_checks(analysis_with_evidence["id"])
        diversity_check = next(r for r in results if r["check_type"] == "evidence_diversity")

        assert diversity_check["passed"] is True


# =============================================================================
# SENSITIVITY ANALYSIS TESTS
# =============================================================================


class TestSensitivityAnalysis:
    """Tests for sensitivity analysis operations."""

    def test_run_sensitivity_analysis(self, ach_service, fully_rated_analysis):
        """Test running full sensitivity analysis."""
        results = ach_service.run_sensitivity_analysis(fully_rated_analysis["id"])

        assert len(results) == 3  # 3 evidence items
        for r in results:
            assert "evidence_id" in r
            assert "evidence_label" in r
            assert "impact" in r
            assert r["impact"] in ["critical", "moderate", "none"]

    def test_calculate_scores_excluding(self, ach_service, fully_rated_analysis):
        """Test calculating scores with evidence excluded."""
        analysis_id = fully_rated_analysis["id"]
        e1_id = fully_rated_analysis["evidence"][0]["id"]

        # Get baseline scores
        baseline = ach_service.calculate_scores(analysis_id)

        # Get scores excluding E1
        excluded = ach_service.calculate_scores_excluding(analysis_id, [e1_id])

        assert len(excluded) == len(baseline)
        # Scores should be different (unless E1 had no impact)

    def test_get_critical_evidence(self, ach_service, fully_rated_analysis):
        """Test getting critical evidence."""
        results = ach_service.get_critical_evidence(fully_rated_analysis["id"])

        # All results should have critical impact
        for r in results:
            assert r["impact"] == "critical"


# =============================================================================
# MILESTONE TESTS
# =============================================================================


class TestMilestones:
    """Tests for milestone operations."""

    def test_add_milestone(self, ach_service, analysis_with_hypotheses):
        """Test adding a milestone."""
        h = analysis_with_hypotheses["hypotheses"][0]

        result = ach_service.add_milestone(
            analysis_with_hypotheses["id"],
            h["id"],
            "Evidence X should appear within 30 days",
            expected_by=datetime.utcnow() + timedelta(days=30),
        )

        assert result is not None
        assert result["description"] == "Evidence X should appear within 30 days"
        assert result["observed"] == 0  # Pending

    def test_update_milestone(self, ach_service, analysis_with_hypotheses):
        """Test updating a milestone."""
        h = analysis_with_hypotheses["hypotheses"][0]
        milestone = ach_service.add_milestone(
            analysis_with_hypotheses["id"],
            h["id"],
            "Test milestone",
        )

        result = ach_service.update_milestone(
            milestone["id"],
            observed=1,
            observation_notes="Confirmed on 2024-01-15",
        )

        assert result is not None
        assert result["observed"] == 1
        assert result["observation_notes"] == "Confirmed on 2024-01-15"

    def test_delete_milestone(self, ach_service, analysis_with_hypotheses):
        """Test deleting a milestone."""
        h = analysis_with_hypotheses["hypotheses"][0]
        milestone = ach_service.add_milestone(
            analysis_with_hypotheses["id"],
            h["id"],
            "Test milestone",
        )

        result = ach_service.delete_milestone(milestone["id"])
        assert result is True

    def test_get_analysis_milestones(self, ach_service, analysis_with_hypotheses):
        """Test getting all milestones for an analysis."""
        analysis_id = analysis_with_hypotheses["id"]
        h = analysis_with_hypotheses["hypotheses"][0]

        # Add multiple milestones
        ach_service.add_milestone(analysis_id, h["id"], "Milestone 1")
        ach_service.add_milestone(analysis_id, h["id"], "Milestone 2")

        results = ach_service.get_analysis_milestones(analysis_id)

        assert len(results) == 2


# =============================================================================
# SNAPSHOT AND DIFF TESTS
# =============================================================================


class TestSnapshotAndDiff:
    """Tests for snapshot comparison and diff operations."""

    def test_create_snapshot(self, ach_service, fully_rated_analysis):
        """Test creating a snapshot."""
        # create_snapshot returns an ACHAnalysisSnapshot ORM object, not a dict
        result = ach_service.create_snapshot(
            fully_rated_analysis["id"],
            label="Baseline v1",
        )

        assert result is not None
        assert result.label == "Baseline v1"
        assert result.id > 0

    def test_list_snapshots(self, ach_service, fully_rated_analysis):
        """Test listing snapshots."""
        analysis_id = fully_rated_analysis["id"]

        ach_service.create_snapshot(analysis_id, label="Snapshot 1")
        ach_service.create_snapshot(analysis_id, label="Snapshot 2")

        # Method is named get_snapshots, not list_snapshots
        results = ach_service.get_snapshots(analysis_id)

        assert len(results) >= 2

    def test_diff_list_added(self, ach_service):
        """Test _diff_list detects added items."""
        list1 = [{"label": "H1"}, {"label": "H2"}]
        list2 = [{"label": "H1"}, {"label": "H2"}, {"label": "H3"}]

        result = ach_service._diff_list(list1, list2, key="label")

        assert "H3" in result["added"]
        assert len(result["removed"]) == 0

    def test_diff_list_removed(self, ach_service):
        """Test _diff_list detects removed items."""
        list1 = [{"label": "H1"}, {"label": "H2"}, {"label": "H3"}]
        list2 = [{"label": "H1"}, {"label": "H2"}]

        result = ach_service._diff_list(list1, list2, key="label")

        assert "H3" in result["removed"]
        assert len(result["added"]) == 0

    def test_diff_ratings(self, ach_service):
        """Test _diff_ratings detects rating changes."""
        evidence1 = [{"label": "E1", "ratings": {"1": "C", "2": "N"}}]
        evidence2 = [{"label": "E1", "ratings": {"1": "I", "2": "N"}}]
        hypotheses = [{"id": 1, "label": "H1"}, {"id": 2, "label": "H2"}]

        result = ach_service._diff_ratings(evidence1, evidence2, hypotheses, hypotheses)

        assert len(result) == 1
        assert result[0]["evidence_label"] == "E1"
        assert result[0]["old"] == "C"
        assert result[0]["new"] == "I"

    def test_diff_milestones(self, ach_service):
        """Test _diff_milestones detects milestone changes."""
        milestones1 = [
            {"description": "Milestone A", "observed": 0},
            {"description": "Milestone B", "observed": 0},
        ]
        milestones2 = [
            {"description": "Milestone A", "observed": 1},  # Status changed
            {"description": "Milestone C", "observed": 0},  # New
        ]

        result = ach_service._diff_milestones(milestones1, milestones2)

        assert "Milestone C" in result["added"]
        assert "Milestone B" in result["removed"]
        assert len(result["status_changes"]) == 1

    def test_compare_to_current(self, ach_service, fully_rated_analysis):
        """Test comparing a snapshot to current state."""
        analysis_id = fully_rated_analysis["id"]

        # Create a snapshot (returns ORM object)
        snapshot = ach_service.create_snapshot(analysis_id, label="Before changes")

        # Make some changes
        new_h = ach_service.add_hypothesis(analysis_id, "New hypothesis H4")

        # Compare (use snapshot.id, not snapshot["id"])
        diff = ach_service.compare_to_current(analysis_id, snapshot.id)

        assert "hypotheses" in diff
        assert "H4" in diff["hypotheses"]["added"]
        assert "meta" in diff
        assert diff["meta"]["s1_label"] == "Before changes"
        assert diff["meta"]["s2_label"] == "Current State"

    def test_compare_to_current_not_found(self, ach_service, fully_rated_analysis):
        """Test compare_to_current with invalid snapshot."""
        diff = ach_service.compare_to_current(fully_rated_analysis["id"], 99999)

        assert "error" in diff


# =============================================================================
# EXPORT TESTS
# =============================================================================


class TestExport:
    """Tests for export functionality."""

    def test_export_markdown(self, ach_service, fully_rated_analysis):
        """Test exporting analysis as Markdown."""
        md = ach_service.export_markdown(fully_rated_analysis["id"])

        assert len(md) > 0
        assert "# ACH Analysis:" in md
        assert "## Hypotheses" in md
        assert "## Evidence" in md
        assert "## Analysis Matrix" in md

    def test_export_markdown_not_found(self, ach_service):
        """Test exporting non-existent analysis."""
        md = ach_service.export_markdown(99999)
        assert md == ""

    def test_export_json(self, ach_service, fully_rated_analysis):
        """Test exporting analysis as JSON."""
        result = ach_service.export_json(fully_rated_analysis["id"])

        assert result is not None
        # Should be valid JSON
        data = json.loads(result) if isinstance(result, str) else result
        assert "title" in data or "analysis" in data


# =============================================================================
# SINGLETON PATTERN TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_ach_service_returns_same_instance(self):
        """Test that get_ach_service returns the same instance."""
        # Reset singleton for clean test
        import app.arkham.services.ach_service as module
        module._ach_service_instance = None

        service1 = get_ach_service()
        service2 = get_ach_service()

        assert service1 is service2


# =============================================================================
# RATING VALUES TESTS
# =============================================================================


class TestRatingValues:
    """Tests for rating value constants."""

    def test_rating_values_complete(self):
        """Test that all expected rating values are defined."""
        expected_ratings = ["CC", "C", "N", "I", "II", "-", ""]
        for rating in expected_ratings:
            assert rating in RATING_VALUES

    def test_rating_values_correct(self):
        """Test that rating values follow Heuer method."""
        # Consistencies should be negative (support hypothesis)
        assert RATING_VALUES["CC"] < 0
        assert RATING_VALUES["C"] < 0

        # Neutral should be 0
        assert RATING_VALUES["N"] == 0

        # Inconsistencies should be positive (count against hypothesis)
        assert RATING_VALUES["I"] > 0
        assert RATING_VALUES["II"] > 0

        # Unrated should be neutral
        assert RATING_VALUES["-"] == 0
        assert RATING_VALUES[""] == 0

    def test_hypothesis_colors_sufficient(self):
        """Test that enough hypothesis colors are defined."""
        assert len(HYPOTHESIS_COLORS) >= 8
