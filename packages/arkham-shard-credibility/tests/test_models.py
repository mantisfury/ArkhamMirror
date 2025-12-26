"""
Tests for credibility shard models.
"""

import pytest
from datetime import datetime

from arkham_shard_credibility.models import (
    AssessmentMethod,
    CredibilityAssessment,
    CredibilityFactor,
    CredibilityLevel,
    FactorType,
    SourceType,
    STANDARD_FACTORS,
)


def test_source_type_enum():
    """Test SourceType enum values."""
    assert SourceType.DOCUMENT.value == "document"
    assert SourceType.ENTITY.value == "entity"
    assert SourceType.WEBSITE.value == "website"
    assert SourceType.PUBLICATION.value == "publication"
    assert SourceType.PERSON.value == "person"
    assert SourceType.ORGANIZATION.value == "organization"


def test_assessment_method_enum():
    """Test AssessmentMethod enum values."""
    assert AssessmentMethod.MANUAL.value == "manual"
    assert AssessmentMethod.AUTOMATED.value == "automated"
    assert AssessmentMethod.HYBRID.value == "hybrid"


def test_credibility_level_enum():
    """Test CredibilityLevel enum values."""
    assert CredibilityLevel.UNRELIABLE.value == "unreliable"
    assert CredibilityLevel.LOW.value == "low"
    assert CredibilityLevel.MEDIUM.value == "medium"
    assert CredibilityLevel.HIGH.value == "high"
    assert CredibilityLevel.VERIFIED.value == "verified"


def test_credibility_factor():
    """Test CredibilityFactor dataclass."""
    factor = CredibilityFactor(
        factor_type=FactorType.SOURCE_RELIABILITY.value,
        weight=0.25,
        score=80,
        notes="Strong track record"
    )

    assert factor.factor_type == "source_reliability"
    assert factor.weight == 0.25
    assert factor.score == 80
    assert factor.notes == "Strong track record"


def test_credibility_assessment_level():
    """Test CredibilityAssessment level property."""
    # Unreliable: 0-20
    assessment = CredibilityAssessment(
        id="test-1",
        source_type=SourceType.DOCUMENT,
        source_id="doc-1",
        score=15,
        confidence=0.8,
    )
    assert assessment.level == CredibilityLevel.UNRELIABLE

    # Low: 21-40
    assessment.score = 30
    assert assessment.level == CredibilityLevel.LOW

    # Medium: 41-60
    assessment.score = 50
    assert assessment.level == CredibilityLevel.MEDIUM

    # High: 61-80
    assessment.score = 70
    assert assessment.level == CredibilityLevel.HIGH

    # Verified: 81-100
    assessment.score = 90
    assert assessment.level == CredibilityLevel.VERIFIED


def test_credibility_assessment_defaults():
    """Test CredibilityAssessment default values."""
    assessment = CredibilityAssessment(
        id="test-1",
        source_type=SourceType.DOCUMENT,
        source_id="doc-1",
        score=75,
        confidence=0.9,
    )

    assert assessment.factors == []
    assert assessment.assessed_by == AssessmentMethod.MANUAL
    assert assessment.assessor_id is None
    assert assessment.notes is None
    assert isinstance(assessment.created_at, datetime)
    assert isinstance(assessment.updated_at, datetime)
    assert assessment.metadata == {}


def test_credibility_assessment_with_factors():
    """Test CredibilityAssessment with factors."""
    factors = [
        CredibilityFactor(
            factor_type=FactorType.SOURCE_RELIABILITY.value,
            weight=0.25,
            score=80,
        ),
        CredibilityFactor(
            factor_type=FactorType.EVIDENCE_QUALITY.value,
            weight=0.20,
            score=70,
        ),
    ]

    assessment = CredibilityAssessment(
        id="test-1",
        source_type=SourceType.DOCUMENT,
        source_id="doc-1",
        score=75,
        confidence=0.9,
        factors=factors,
    )

    assert len(assessment.factors) == 2
    assert assessment.factors[0].factor_type == "source_reliability"
    assert assessment.factors[1].factor_type == "evidence_quality"


def test_standard_factors():
    """Test standard factor definitions."""
    assert len(STANDARD_FACTORS) == 7

    # Check weights sum to 1.0
    total_weight = sum(f.default_weight for f in STANDARD_FACTORS)
    assert abs(total_weight - 1.0) < 0.001  # Allow floating point error

    # Check all required factors present
    factor_types = {f.factor_type for f in STANDARD_FACTORS}
    assert FactorType.SOURCE_RELIABILITY.value in factor_types
    assert FactorType.EVIDENCE_QUALITY.value in factor_types
    assert FactorType.BIAS_ASSESSMENT.value in factor_types
    assert FactorType.EXPERTISE.value in factor_types
    assert FactorType.TIMELINESS.value in factor_types
    assert FactorType.INDEPENDENCE.value in factor_types
    assert FactorType.TRANSPARENCY.value in factor_types


def test_standard_factor_structure():
    """Test standard factor has required fields."""
    factor = STANDARD_FACTORS[0]

    assert hasattr(factor, "factor_type")
    assert hasattr(factor, "default_weight")
    assert hasattr(factor, "description")
    assert hasattr(factor, "scoring_guidance")

    assert isinstance(factor.factor_type, str)
    assert isinstance(factor.default_weight, float)
    assert isinstance(factor.description, str)
    assert isinstance(factor.scoring_guidance, str)

    assert 0.0 <= factor.default_weight <= 1.0
