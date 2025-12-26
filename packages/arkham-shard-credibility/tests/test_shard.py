"""
Tests for credibility shard implementation.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from arkham_shard_credibility.shard import CredibilityShard
from arkham_shard_credibility.models import (
    AssessmentMethod,
    CredibilityFactor,
    CredibilityLevel,
    FactorType,
    SourceType,
)


@pytest.fixture
def mock_frame():
    """Create a mock ArkhamFrame instance."""
    frame = MagicMock()
    frame.database = MagicMock()
    frame.events = MagicMock()
    frame.llm = None
    frame.vectors = None

    # Mock database methods
    frame.database.execute = AsyncMock()
    frame.database.fetch_one = AsyncMock()
    frame.database.fetch_all = AsyncMock()

    # Mock events methods
    frame.events.subscribe = AsyncMock()
    frame.events.unsubscribe = AsyncMock()
    frame.events.emit = AsyncMock()

    return frame


@pytest.fixture
async def shard(mock_frame):
    """Create an initialized CredibilityShard instance."""
    shard = CredibilityShard()
    await shard.initialize(mock_frame)
    return shard


@pytest.mark.asyncio
async def test_shard_initialization(mock_frame):
    """Test shard initialization."""
    shard = CredibilityShard()
    assert shard.name == "credibility"
    assert shard.version == "0.1.0"

    await shard.initialize(mock_frame)

    assert shard._initialized is True
    assert shard.frame is mock_frame
    assert shard._db is mock_frame.database
    assert shard._events is mock_frame.events

    # Verify schema creation was called
    mock_frame.database.execute.assert_called()

    # Verify event subscriptions
    assert mock_frame.events.subscribe.call_count == 4


@pytest.mark.asyncio
async def test_shard_shutdown(shard, mock_frame):
    """Test shard shutdown."""
    await shard.shutdown()

    assert shard._initialized is False
    assert mock_frame.events.unsubscribe.call_count == 4


@pytest.mark.asyncio
async def test_create_assessment(shard, mock_frame):
    """Test creating a credibility assessment."""
    factors = [
        CredibilityFactor(
            factor_type=FactorType.SOURCE_RELIABILITY.value,
            weight=0.25,
            score=80,
        )
    ]

    assessment = await shard.create_assessment(
        source_type=SourceType.DOCUMENT,
        source_id="doc-123",
        score=75,
        confidence=0.9,
        factors=factors,
        assessed_by=AssessmentMethod.MANUAL,
        assessor_id="analyst-1",
        notes="Test assessment",
    )

    assert assessment.source_type == SourceType.DOCUMENT
    assert assessment.source_id == "doc-123"
    assert assessment.score == 75
    assert assessment.confidence == 0.9
    assert len(assessment.factors) == 1
    assert assessment.level == CredibilityLevel.HIGH

    # Verify database insert
    mock_frame.database.execute.assert_called()

    # Verify events emitted
    assert mock_frame.events.emit.call_count >= 2  # created + rated


@pytest.mark.asyncio
async def test_create_assessment_validation(shard):
    """Test assessment creation validation."""
    # Invalid score
    with pytest.raises(ValueError, match="Score must be 0-100"):
        await shard.create_assessment(
            source_type=SourceType.DOCUMENT,
            source_id="doc-123",
            score=150,  # Invalid
            confidence=0.9,
        )

    # Invalid confidence
    with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
        await shard.create_assessment(
            source_type=SourceType.DOCUMENT,
            source_id="doc-123",
            score=75,
            confidence=1.5,  # Invalid
        )


@pytest.mark.asyncio
async def test_get_assessment(shard, mock_frame):
    """Test retrieving an assessment by ID."""
    # Mock database response
    mock_frame.database.fetch_one.return_value = {
        "id": "test-123",
        "source_type": "document",
        "source_id": "doc-123",
        "score": 75,
        "confidence": 0.9,
        "factors": "[]",
        "assessed_by": "manual",
        "assessor_id": "analyst-1",
        "notes": "Test",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "metadata": "{}",
    }

    assessment = await shard.get_assessment("test-123")

    assert assessment is not None
    assert assessment.id == "test-123"
    assert assessment.source_type == SourceType.DOCUMENT
    assert assessment.score == 75


@pytest.mark.asyncio
async def test_get_assessment_not_found(shard, mock_frame):
    """Test retrieving non-existent assessment."""
    mock_frame.database.fetch_one.return_value = None

    assessment = await shard.get_assessment("nonexistent")

    assert assessment is None


@pytest.mark.asyncio
async def test_list_assessments(shard, mock_frame):
    """Test listing assessments."""
    # Mock database response
    mock_frame.database.fetch_all.return_value = [
        {
            "id": "test-1",
            "source_type": "document",
            "source_id": "doc-1",
            "score": 75,
            "confidence": 0.9,
            "factors": "[]",
            "assessed_by": "manual",
            "assessor_id": None,
            "notes": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": "{}",
        },
        {
            "id": "test-2",
            "source_type": "entity",
            "source_id": "ent-1",
            "score": 60,
            "confidence": 0.8,
            "factors": "[]",
            "assessed_by": "automated",
            "assessor_id": None,
            "notes": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": "{}",
        },
    ]

    assessments = await shard.list_assessments(limit=50, offset=0)

    assert len(assessments) == 2
    assert assessments[0].id == "test-1"
    assert assessments[1].id == "test-2"


@pytest.mark.asyncio
async def test_update_assessment(shard, mock_frame):
    """Test updating an assessment."""
    # Mock existing assessment
    mock_frame.database.fetch_one.return_value = {
        "id": "test-123",
        "source_type": "document",
        "source_id": "doc-123",
        "score": 75,
        "confidence": 0.9,
        "factors": "[]",
        "assessed_by": "manual",
        "assessor_id": None,
        "notes": "Original",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "metadata": "{}",
    }

    assessment = await shard.update_assessment(
        assessment_id="test-123",
        score=80,
        notes="Updated",
    )

    assert assessment is not None
    assert assessment.score == 80
    assert assessment.notes == "Updated"

    # Verify database update
    mock_frame.database.execute.assert_called()

    # Verify event emitted
    mock_frame.events.emit.assert_called()


@pytest.mark.asyncio
async def test_delete_assessment(shard, mock_frame):
    """Test deleting an assessment."""
    result = await shard.delete_assessment("test-123")

    assert result is True
    mock_frame.database.execute.assert_called()


@pytest.mark.asyncio
async def test_get_source_credibility(shard, mock_frame):
    """Test getting aggregate source credibility."""
    # Mock database response with multiple assessments
    mock_frame.database.fetch_all.return_value = [
        {
            "id": "test-1",
            "source_type": "document",
            "source_id": "doc-123",
            "score": 80,
            "confidence": 0.9,
            "factors": "[]",
            "assessed_by": "manual",
            "assessor_id": None,
            "notes": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": "{}",
        },
        {
            "id": "test-2",
            "source_type": "document",
            "source_id": "doc-123",
            "score": 70,
            "confidence": 0.8,
            "factors": "[]",
            "assessed_by": "automated",
            "assessor_id": None,
            "notes": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": "{}",
        },
    ]

    source_cred = await shard.get_source_credibility(
        SourceType.DOCUMENT,
        "doc-123"
    )

    assert source_cred is not None
    assert source_cred.source_type == SourceType.DOCUMENT
    assert source_cred.source_id == "doc-123"
    assert source_cred.avg_score == 75.0  # (80 + 70) / 2
    assert source_cred.assessment_count == 2
    assert source_cred.latest_score == 80


@pytest.mark.asyncio
async def test_get_statistics(shard, mock_frame):
    """Test getting credibility statistics."""
    # Mock database responses
    mock_frame.database.fetch_one.side_effect = [
        {"count": 100},  # total
        {"count": 10},   # unreliable
        {"count": 20},   # low
        {"count": 30},   # medium
        {"count": 25},   # high
        {"count": 15},   # verified
        {"avg": 55.5},   # avg score
        {"avg": 0.85},   # avg confidence
        {"count": 50},   # unique sources
    ]

    mock_frame.database.fetch_all.side_effect = [
        [{"source_type": "document", "count": 60}, {"source_type": "entity", "count": 40}],  # by type
        [{"assessed_by": "manual", "count": 70}, {"assessed_by": "automated", "count": 30}],  # by method
    ]

    stats = await shard.get_statistics()

    assert stats.total_assessments == 100
    assert stats.unreliable_count == 10
    assert stats.low_count == 20
    assert stats.medium_count == 30
    assert stats.high_count == 25
    assert stats.verified_count == 15
    assert stats.avg_score == 55.5
    assert stats.avg_confidence == 0.85
    assert stats.sources_assessed == 50


@pytest.mark.asyncio
async def test_get_standard_factors(shard):
    """Test getting standard credibility factors."""
    factors = shard.get_standard_factors()

    assert len(factors) == 7
    assert all("factor_type" in f for f in factors)
    assert all("default_weight" in f for f in factors)
    assert all("description" in f for f in factors)
    assert all("scoring_guidance" in f for f in factors)
