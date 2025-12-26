"""
Contradictions Shard - Model Tests

Tests for all dataclasses and enums in the models module.
"""

import pytest
from datetime import datetime

from arkham_shard_contradictions.models import (
    ContradictionStatus,
    Severity,
    ContradictionType,
    Contradiction,
    Claim,
    ContradictionChain,
    AnalyzeRequest,
    BatchAnalyzeRequest,
    ClaimsRequest,
    UpdateStatusRequest,
    AddNotesRequest,
    ContradictionResult,
    ContradictionList,
    StatsResponse,
    ClaimExtractionResult,
)


class TestContradictionStatusEnum:
    """Tests for ContradictionStatus enum."""

    def test_detected_value(self):
        """Test DETECTED status value."""
        assert ContradictionStatus.DETECTED.value == "detected"

    def test_confirmed_value(self):
        """Test CONFIRMED status value."""
        assert ContradictionStatus.CONFIRMED.value == "confirmed"

    def test_dismissed_value(self):
        """Test DISMISSED status value."""
        assert ContradictionStatus.DISMISSED.value == "dismissed"

    def test_investigating_value(self):
        """Test INVESTIGATING status value."""
        assert ContradictionStatus.INVESTIGATING.value == "investigating"

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        statuses = [s.value for s in ContradictionStatus]
        assert len(statuses) == 4


class TestSeverityEnum:
    """Tests for Severity enum."""

    def test_high_value(self):
        """Test HIGH severity value."""
        assert Severity.HIGH.value == "high"

    def test_medium_value(self):
        """Test MEDIUM severity value."""
        assert Severity.MEDIUM.value == "medium"

    def test_low_value(self):
        """Test LOW severity value."""
        assert Severity.LOW.value == "low"


class TestContradictionTypeEnum:
    """Tests for ContradictionType enum."""

    def test_direct_type(self):
        """Test DIRECT type value."""
        assert ContradictionType.DIRECT.value == "direct"

    def test_temporal_type(self):
        """Test TEMPORAL type value."""
        assert ContradictionType.TEMPORAL.value == "temporal"

    def test_numeric_type(self):
        """Test NUMERIC type value."""
        assert ContradictionType.NUMERIC.value == "numeric"

    def test_entity_type(self):
        """Test ENTITY type value."""
        assert ContradictionType.ENTITY.value == "entity"

    def test_logical_type(self):
        """Test LOGICAL type value."""
        assert ContradictionType.LOGICAL.value == "logical"

    def test_contextual_type(self):
        """Test CONTEXTUAL type value."""
        assert ContradictionType.CONTEXTUAL.value == "contextual"

    def test_all_types_exist(self):
        """Test all expected types exist."""
        types = [t.value for t in ContradictionType]
        assert len(types) == 6


class TestContradictionDataclass:
    """Tests for Contradiction dataclass."""

    def test_minimal_initialization(self):
        """Test Contradiction with required fields only."""
        contradiction = Contradiction(
            id="c-123",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Claim A text",
            claim_b="Claim B text",
        )
        assert contradiction.id == "c-123"
        assert contradiction.doc_a_id == "doc-1"
        assert contradiction.doc_b_id == "doc-2"
        assert contradiction.claim_a == "Claim A text"
        assert contradiction.claim_b == "Claim B text"
        # Default values
        assert contradiction.contradiction_type == ContradictionType.DIRECT
        assert contradiction.severity == Severity.MEDIUM
        assert contradiction.status == ContradictionStatus.DETECTED
        assert contradiction.confidence_score == 0.0
        assert contradiction.detected_by == "system"
        assert contradiction.analyst_notes == []
        assert contradiction.chain_id is None
        assert contradiction.tags == []

    def test_full_initialization(self):
        """Test Contradiction with all fields."""
        created = datetime(2024, 6, 15, 10, 0, 0)
        updated = datetime(2024, 6, 15, 11, 0, 0)
        confirmed = datetime(2024, 6, 15, 12, 0, 0)

        contradiction = Contradiction(
            id="c-123",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Claim A text",
            claim_b="Claim B text",
            claim_a_location="page_1",
            claim_b_location="page_5",
            contradiction_type=ContradictionType.TEMPORAL,
            severity=Severity.HIGH,
            status=ContradictionStatus.CONFIRMED,
            explanation="Different dates for same event",
            confidence_score=0.95,
            created_at=created,
            updated_at=updated,
            detected_by="llm",
            analyst_notes=["Initial review"],
            confirmed_by="analyst@example.com",
            confirmed_at=confirmed,
            chain_id="chain-1",
            related_contradictions=["c-456"],
            tags=["temporal", "critical"],
            metadata={"source": "test"},
        )
        assert contradiction.contradiction_type == ContradictionType.TEMPORAL
        assert contradiction.severity == Severity.HIGH
        assert contradiction.status == ContradictionStatus.CONFIRMED
        assert contradiction.confidence_score == 0.95
        assert contradiction.confirmed_by == "analyst@example.com"
        assert contradiction.chain_id == "chain-1"
        assert "temporal" in contradiction.tags


class TestClaimDataclass:
    """Tests for Claim dataclass."""

    def test_minimal_initialization(self):
        """Test Claim with required fields only."""
        claim = Claim(
            id="claim-123",
            document_id="doc-1",
            text="This is a factual claim.",
        )
        assert claim.id == "claim-123"
        assert claim.document_id == "doc-1"
        assert claim.text == "This is a factual claim."
        assert claim.chunk_id is None
        assert claim.page_number is None
        assert claim.location == ""
        assert claim.claim_type == "fact"
        assert claim.embedding is None
        assert claim.extraction_method == "system"
        assert claim.confidence == 1.0

    def test_full_initialization(self):
        """Test Claim with all fields."""
        claim = Claim(
            id="claim-123",
            document_id="doc-1",
            text="This is a factual claim.",
            chunk_id="chunk-5",
            page_number=3,
            location="page_3_para_2",
            claim_type="attribution",
            embedding=[0.1, 0.2, 0.3],
            extraction_method="llm",
            confidence=0.85,
            metadata={"source": "test"},
        )
        assert claim.chunk_id == "chunk-5"
        assert claim.page_number == 3
        assert claim.claim_type == "attribution"
        assert claim.embedding == [0.1, 0.2, 0.3]
        assert claim.confidence == 0.85


class TestContradictionChainDataclass:
    """Tests for ContradictionChain dataclass."""

    def test_minimal_initialization(self):
        """Test ContradictionChain with required fields only."""
        chain = ContradictionChain(
            id="chain-123",
            contradiction_ids=["c-1", "c-2", "c-3"],
        )
        assert chain.id == "chain-123"
        assert len(chain.contradiction_ids) == 3
        assert chain.description == ""
        assert chain.severity == Severity.MEDIUM

    def test_full_initialization(self):
        """Test ContradictionChain with all fields."""
        chain = ContradictionChain(
            id="chain-123",
            contradiction_ids=["c-1", "c-2", "c-3"],
            description="A chain of related contradictions",
            severity=Severity.HIGH,
        )
        assert chain.description == "A chain of related contradictions"
        assert chain.severity == Severity.HIGH


class TestAnalyzeRequestModel:
    """Tests for AnalyzeRequest Pydantic model."""

    def test_required_fields(self):
        """Test AnalyzeRequest with required fields."""
        request = AnalyzeRequest(
            doc_a_id="doc-1",
            doc_b_id="doc-2",
        )
        assert request.doc_a_id == "doc-1"
        assert request.doc_b_id == "doc-2"
        assert request.threshold == 0.7
        assert request.use_llm is True

    def test_custom_values(self):
        """Test AnalyzeRequest with custom values."""
        request = AnalyzeRequest(
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            threshold=0.5,
            use_llm=False,
        )
        assert request.threshold == 0.5
        assert request.use_llm is False


class TestBatchAnalyzeRequestModel:
    """Tests for BatchAnalyzeRequest Pydantic model."""

    def test_initialization(self):
        """Test BatchAnalyzeRequest initialization."""
        request = BatchAnalyzeRequest(
            document_pairs=[("doc-1", "doc-2"), ("doc-3", "doc-4")],
        )
        assert len(request.document_pairs) == 2
        assert request.threshold == 0.7
        assert request.use_llm is True


class TestClaimsRequestModel:
    """Tests for ClaimsRequest Pydantic model."""

    def test_required_fields(self):
        """Test ClaimsRequest with required text."""
        request = ClaimsRequest(
            text="This is some text to extract claims from.",
        )
        assert "text to extract" in request.text
        assert request.document_id is None
        assert request.use_llm is True

    def test_with_document_id(self):
        """Test ClaimsRequest with document ID."""
        request = ClaimsRequest(
            text="Some text",
            document_id="doc-123",
            use_llm=False,
        )
        assert request.document_id == "doc-123"
        assert request.use_llm is False


class TestUpdateStatusRequestModel:
    """Tests for UpdateStatusRequest Pydantic model."""

    def test_required_fields(self):
        """Test UpdateStatusRequest with required status."""
        request = UpdateStatusRequest(status="confirmed")
        assert request.status == "confirmed"
        assert request.notes == ""
        assert request.analyst_id is None

    def test_full_request(self):
        """Test UpdateStatusRequest with all fields."""
        request = UpdateStatusRequest(
            status="dismissed",
            notes="False positive",
            analyst_id="analyst@example.com",
        )
        assert request.status == "dismissed"
        assert request.notes == "False positive"


class TestAddNotesRequestModel:
    """Tests for AddNotesRequest Pydantic model."""

    def test_initialization(self):
        """Test AddNotesRequest initialization."""
        request = AddNotesRequest(
            notes="This needs further investigation.",
            analyst_id="analyst@example.com",
        )
        assert "further investigation" in request.notes
        assert request.analyst_id == "analyst@example.com"


class TestContradictionResultModel:
    """Tests for ContradictionResult Pydantic model."""

    def test_initialization(self):
        """Test ContradictionResult initialization."""
        result = ContradictionResult(
            id="c-123",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Claim A",
            claim_b="Claim B",
            contradiction_type="direct",
            severity="high",
            status="detected",
            explanation="Direct contradiction",
            confidence_score=0.9,
            created_at="2024-06-15T10:00:00",
        )
        assert result.id == "c-123"
        assert result.contradiction_type == "direct"
        assert result.severity == "high"


class TestContradictionListModel:
    """Tests for ContradictionList Pydantic model."""

    def test_initialization(self):
        """Test ContradictionList initialization."""
        result = ContradictionResult(
            id="c-123",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Claim A",
            claim_b="Claim B",
            contradiction_type="direct",
            severity="high",
            status="detected",
            explanation="Test",
            confidence_score=0.9,
            created_at="2024-06-15T10:00:00",
        )
        lst = ContradictionList(
            contradictions=[result],
            total=100,
            page=2,
            page_size=50,
        )
        assert lst.total == 100
        assert lst.page == 2
        assert len(lst.contradictions) == 1


class TestStatsResponseModel:
    """Tests for StatsResponse Pydantic model."""

    def test_initialization(self):
        """Test StatsResponse initialization."""
        stats = StatsResponse(
            total_contradictions=100,
            by_status={"detected": 60, "confirmed": 30, "dismissed": 10},
            by_severity={"high": 20, "medium": 50, "low": 30},
            by_type={"direct": 40, "temporal": 30, "numeric": 30},
            chains_detected=5,
            recent_count=15,
        )
        assert stats.total_contradictions == 100
        assert stats.by_status["confirmed"] == 30
        assert stats.chains_detected == 5


class TestClaimExtractionResultModel:
    """Tests for ClaimExtractionResult Pydantic model."""

    def test_initialization(self):
        """Test ClaimExtractionResult initialization."""
        result = ClaimExtractionResult(
            claims=[
                {"id": "c1", "text": "Claim 1", "type": "fact"},
                {"id": "c2", "text": "Claim 2", "type": "opinion"},
            ],
            count=2,
            document_id="doc-123",
        )
        assert result.count == 2
        assert result.document_id == "doc-123"
        assert len(result.claims) == 2
