"""
Claims Shard - Model Tests

Tests for all enums, dataclasses, and data models.
"""

import pytest
from datetime import datetime

from arkham_shard_claims.models import (
    # Enums
    ClaimStatus,
    ClaimType,
    EvidenceType,
    EvidenceRelationship,
    EvidenceStrength,
    ExtractionMethod,
    # Dataclasses
    Claim,
    Evidence,
    ClaimExtractionResult,
    ClaimMatch,
    ClaimMergeResult,
    ClaimStatistics,
    ClaimFilter,
)


class TestClaimStatusEnum:
    """Tests for ClaimStatus enum."""

    def test_all_values_exist(self):
        """Verify all expected status values exist."""
        assert ClaimStatus.UNVERIFIED.value == "unverified"
        assert ClaimStatus.VERIFIED.value == "verified"
        assert ClaimStatus.DISPUTED.value == "disputed"
        assert ClaimStatus.RETRACTED.value == "retracted"
        assert ClaimStatus.UNCERTAIN.value == "uncertain"

    def test_string_inheritance(self):
        """Verify enum values can be used as strings."""
        assert ClaimStatus.VERIFIED == "verified"
        assert str(ClaimStatus.VERIFIED) == "verified"

    def test_enum_count(self):
        """Verify total number of statuses."""
        assert len(ClaimStatus) == 5


class TestClaimTypeEnum:
    """Tests for ClaimType enum."""

    def test_all_values_exist(self):
        """Verify all expected type values exist."""
        assert ClaimType.FACTUAL.value == "factual"
        assert ClaimType.OPINION.value == "opinion"
        assert ClaimType.PREDICTION.value == "prediction"
        assert ClaimType.QUANTITATIVE.value == "quantitative"
        assert ClaimType.ATTRIBUTION.value == "attribution"
        assert ClaimType.OTHER.value == "other"

    def test_enum_count(self):
        """Verify total number of types."""
        assert len(ClaimType) == 6


class TestEvidenceTypeEnum:
    """Tests for EvidenceType enum."""

    def test_all_values_exist(self):
        """Verify all expected evidence type values exist."""
        assert EvidenceType.DOCUMENT.value == "document"
        assert EvidenceType.ENTITY.value == "entity"
        assert EvidenceType.EXTERNAL.value == "external"
        assert EvidenceType.CLAIM.value == "claim"

    def test_enum_count(self):
        """Verify total number of evidence types."""
        assert len(EvidenceType) == 4


class TestEvidenceRelationshipEnum:
    """Tests for EvidenceRelationship enum."""

    def test_all_values_exist(self):
        """Verify all expected relationship values exist."""
        assert EvidenceRelationship.SUPPORTS.value == "supports"
        assert EvidenceRelationship.REFUTES.value == "refutes"
        assert EvidenceRelationship.RELATED.value == "related"

    def test_enum_count(self):
        """Verify total number of relationships."""
        assert len(EvidenceRelationship) == 3


class TestEvidenceStrengthEnum:
    """Tests for EvidenceStrength enum."""

    def test_all_values_exist(self):
        """Verify all expected strength values exist."""
        assert EvidenceStrength.STRONG.value == "strong"
        assert EvidenceStrength.MODERATE.value == "moderate"
        assert EvidenceStrength.WEAK.value == "weak"

    def test_enum_count(self):
        """Verify total number of strengths."""
        assert len(EvidenceStrength) == 3


class TestExtractionMethodEnum:
    """Tests for ExtractionMethod enum."""

    def test_all_values_exist(self):
        """Verify all expected method values exist."""
        assert ExtractionMethod.MANUAL.value == "manual"
        assert ExtractionMethod.LLM.value == "llm"
        assert ExtractionMethod.RULE.value == "rule"
        assert ExtractionMethod.IMPORTED.value == "imported"

    def test_enum_count(self):
        """Verify total number of methods."""
        assert len(ExtractionMethod) == 4


class TestClaimDataclass:
    """Tests for Claim dataclass."""

    def test_minimal_creation(self):
        """Test creating a claim with minimal required fields."""
        claim = Claim(
            id="test-id",
            text="The sky is blue.",
        )
        assert claim.id == "test-id"
        assert claim.text == "The sky is blue."
        assert claim.claim_type == ClaimType.FACTUAL
        assert claim.status == ClaimStatus.UNVERIFIED
        assert claim.confidence == 1.0

    def test_full_creation(self):
        """Test creating a claim with all fields."""
        now = datetime.utcnow()
        claim = Claim(
            id="full-id",
            text="The meeting occurred at 3pm.",
            claim_type=ClaimType.QUANTITATIVE,
            status=ClaimStatus.VERIFIED,
            confidence=0.95,
            source_document_id="doc-123",
            source_start_char=100,
            source_end_char=130,
            source_context="According to records, the meeting occurred at 3pm.",
            extracted_by=ExtractionMethod.LLM,
            extraction_model="gpt-4",
            entity_ids=["entity-1", "entity-2"],
            evidence_count=3,
            supporting_count=2,
            refuting_count=1,
            created_at=now,
            updated_at=now,
            verified_at=now,
            metadata={"source": "internal"},
        )
        assert claim.id == "full-id"
        assert claim.claim_type == ClaimType.QUANTITATIVE
        assert claim.status == ClaimStatus.VERIFIED
        assert claim.confidence == 0.95
        assert claim.source_document_id == "doc-123"
        assert claim.extraction_model == "gpt-4"
        assert len(claim.entity_ids) == 2
        assert claim.evidence_count == 3

    def test_default_values(self):
        """Test that default values are set correctly."""
        claim = Claim(id="test", text="test claim")
        assert claim.entity_ids == []
        assert claim.evidence_count == 0
        assert claim.supporting_count == 0
        assert claim.refuting_count == 0
        assert claim.metadata == {}
        assert claim.verified_at is None


class TestEvidenceDataclass:
    """Tests for Evidence dataclass."""

    def test_minimal_creation(self):
        """Test creating evidence with minimal required fields."""
        evidence = Evidence(
            id="ev-1",
            claim_id="claim-1",
            evidence_type=EvidenceType.DOCUMENT,
            reference_id="doc-123",
        )
        assert evidence.id == "ev-1"
        assert evidence.claim_id == "claim-1"
        assert evidence.evidence_type == EvidenceType.DOCUMENT
        assert evidence.relationship == EvidenceRelationship.SUPPORTS
        assert evidence.strength == EvidenceStrength.MODERATE

    def test_full_creation(self):
        """Test creating evidence with all fields."""
        now = datetime.utcnow()
        evidence = Evidence(
            id="ev-full",
            claim_id="claim-1",
            evidence_type=EvidenceType.EXTERNAL,
            reference_id="https://example.com/source",
            reference_title="External Source Article",
            relationship=EvidenceRelationship.REFUTES,
            strength=EvidenceStrength.STRONG,
            excerpt="The article states the opposite...",
            notes="Found during fact-check",
            added_by="analyst-1",
            added_at=now,
            metadata={"verified": True},
        )
        assert evidence.reference_title == "External Source Article"
        assert evidence.relationship == EvidenceRelationship.REFUTES
        assert evidence.strength == EvidenceStrength.STRONG
        assert evidence.added_by == "analyst-1"


class TestClaimExtractionResultDataclass:
    """Tests for ClaimExtractionResult dataclass."""

    def test_empty_result(self):
        """Test creating an empty extraction result."""
        result = ClaimExtractionResult(claims=[])
        assert result.claims == []
        assert result.total_extracted == 0
        assert result.errors == []

    def test_successful_extraction(self):
        """Test creating a successful extraction result."""
        claims = [
            Claim(id="c1", text="Claim 1"),
            Claim(id="c2", text="Claim 2"),
        ]
        result = ClaimExtractionResult(
            claims=claims,
            source_document_id="doc-1",
            extraction_method=ExtractionMethod.LLM,
            extraction_model="gpt-4",
            total_extracted=2,
            processing_time_ms=1500.5,
        )
        assert len(result.claims) == 2
        assert result.total_extracted == 2
        assert result.processing_time_ms == 1500.5

    def test_extraction_with_errors(self):
        """Test extraction result with errors."""
        result = ClaimExtractionResult(
            claims=[],
            errors=["LLM unavailable", "Timeout"],
        )
        assert len(result.errors) == 2


class TestClaimMatchDataclass:
    """Tests for ClaimMatch dataclass."""

    def test_creation(self):
        """Test creating a claim match."""
        match = ClaimMatch(
            claim_id="claim-1",
            matched_claim_id="claim-2",
            similarity_score=0.92,
            match_type="semantic",
            suggested_action="merge",
        )
        assert match.claim_id == "claim-1"
        assert match.matched_claim_id == "claim-2"
        assert match.similarity_score == 0.92
        assert match.suggested_action == "merge"

    def test_default_values(self):
        """Test default values."""
        match = ClaimMatch(
            claim_id="c1",
            matched_claim_id="c2",
            similarity_score=0.85,
        )
        assert match.match_type == "semantic"
        assert match.suggested_action == "review"


class TestClaimMergeResultDataclass:
    """Tests for ClaimMergeResult dataclass."""

    def test_creation(self):
        """Test creating a merge result."""
        result = ClaimMergeResult(
            primary_claim_id="primary",
            merged_claim_ids=["dup-1", "dup-2", "dup-3"],
            evidence_transferred=5,
            entities_merged=2,
        )
        assert result.primary_claim_id == "primary"
        assert len(result.merged_claim_ids) == 3
        assert result.evidence_transferred == 5
        assert result.entities_merged == 2


class TestClaimStatisticsDataclass:
    """Tests for ClaimStatistics dataclass."""

    def test_default_values(self):
        """Test default values for statistics."""
        stats = ClaimStatistics()
        assert stats.total_claims == 0
        assert stats.by_status == {}
        assert stats.by_type == {}
        assert stats.by_extraction_method == {}
        assert stats.total_evidence == 0
        assert stats.avg_confidence == 0.0

    def test_populated_statistics(self):
        """Test statistics with data."""
        stats = ClaimStatistics(
            total_claims=100,
            by_status={"verified": 50, "unverified": 40, "disputed": 10},
            by_type={"factual": 80, "opinion": 20},
            by_extraction_method={"llm": 70, "manual": 30},
            total_evidence=250,
            evidence_supporting=200,
            evidence_refuting=50,
            claims_with_evidence=80,
            claims_without_evidence=20,
            avg_confidence=0.87,
            avg_evidence_per_claim=2.5,
        )
        assert stats.total_claims == 100
        assert stats.by_status["verified"] == 50
        assert stats.avg_evidence_per_claim == 2.5


class TestClaimFilterDataclass:
    """Tests for ClaimFilter dataclass."""

    def test_empty_filter(self):
        """Test empty filter with all None values."""
        filter = ClaimFilter()
        assert filter.status is None
        assert filter.claim_type is None
        assert filter.document_id is None
        assert filter.min_confidence is None
        assert filter.search_text is None

    def test_populated_filter(self):
        """Test filter with values."""
        now = datetime.utcnow()
        filter = ClaimFilter(
            status=ClaimStatus.VERIFIED,
            claim_type=ClaimType.FACTUAL,
            document_id="doc-1",
            min_confidence=0.8,
            max_confidence=1.0,
            extracted_by=ExtractionMethod.LLM,
            has_evidence=True,
            search_text="meeting",
            created_after=now,
        )
        assert filter.status == ClaimStatus.VERIFIED
        assert filter.min_confidence == 0.8
        assert filter.has_evidence is True
        assert filter.search_text == "meeting"
