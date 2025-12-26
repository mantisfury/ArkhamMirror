"""
Tests for Patterns Shard Implementation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from arkham_shard_patterns import PatternsShard
from arkham_shard_patterns.models import (
    Pattern,
    PatternMatch,
    PatternMatchCreate,
    PatternFilter,
    PatternCriteria,
    PatternAnalysisRequest,
    CorrelationRequest,
    PatternType,
    PatternStatus,
    DetectionMethod,
    SourceType,
)


class TestPatternsShard:
    """Tests for PatternsShard class."""

    def test_shard_attributes(self):
        """Test shard has correct attributes."""
        shard = PatternsShard()

        assert shard.name == "patterns"
        assert shard.version == "0.1.0"
        assert "pattern detection" in shard.description.lower()

    def test_shard_initial_state(self):
        """Test shard initial state."""
        shard = PatternsShard()

        assert shard.frame is None
        assert shard._db is None
        assert shard._events is None
        assert shard._llm is None
        assert shard._vectors is None
        assert shard._workers is None
        assert shard._initialized is False


class TestShardInitialization:
    """Tests for shard initialization."""

    @pytest.mark.asyncio
    async def test_initialize_with_all_services(self):
        """Test initialization with all services available."""
        shard = PatternsShard()

        # Mock frame with all services
        mock_frame = MagicMock()
        mock_frame.database = AsyncMock()
        mock_frame.database.execute = AsyncMock()
        mock_frame.database.fetch_one = AsyncMock(return_value=None)
        mock_frame.database.fetch_all = AsyncMock(return_value=[])
        mock_frame.events = AsyncMock()
        mock_frame.events.subscribe = AsyncMock()
        mock_frame.llm = MagicMock()
        mock_frame.llm.is_available = MagicMock(return_value=True)
        mock_frame.vectors = MagicMock()
        mock_frame.workers = MagicMock()

        await shard.initialize(mock_frame)

        assert shard.frame == mock_frame
        assert shard._db == mock_frame.database
        assert shard._events == mock_frame.events
        assert shard._llm == mock_frame.llm
        assert shard._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_without_optional_services(self):
        """Test initialization without optional services."""
        shard = PatternsShard()

        # Mock frame with only required services
        mock_frame = MagicMock()
        mock_frame.database = AsyncMock()
        mock_frame.database.execute = AsyncMock()
        mock_frame.events = AsyncMock()
        mock_frame.events.subscribe = AsyncMock()

        # Remove optional services
        del mock_frame.llm
        del mock_frame.vectors
        del mock_frame.workers

        await shard.initialize(mock_frame)

        assert shard._db == mock_frame.database
        assert shard._llm is None
        assert shard._vectors is None
        assert shard._initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test shard shutdown."""
        shard = PatternsShard()

        # Setup mock events
        mock_events = AsyncMock()
        mock_events.unsubscribe = AsyncMock()
        shard._events = mock_events
        shard._initialized = True

        await shard.shutdown()

        assert shard._initialized is False
        # Verify unsubscribe was called for each event
        assert mock_events.unsubscribe.call_count >= 1


class TestPatternCRUD:
    """Tests for pattern CRUD operations."""

    @pytest.fixture
    def shard_with_db(self):
        """Create shard with mocked database."""
        shard = PatternsShard()
        shard._db = AsyncMock()
        shard._db.execute = AsyncMock()
        shard._db.fetch_one = AsyncMock()
        shard._db.fetch_all = AsyncMock(return_value=[])
        shard._events = AsyncMock()
        shard._events.emit = AsyncMock()
        shard._initialized = True
        return shard

    @pytest.mark.asyncio
    async def test_create_pattern(self, shard_with_db):
        """Test creating a pattern."""
        pattern = await shard_with_db.create_pattern(
            name="Test Pattern",
            description="A test pattern",
            pattern_type=PatternType.RECURRING_THEME,
            confidence=0.8,
        )

        assert pattern.name == "Test Pattern"
        assert pattern.pattern_type == PatternType.RECURRING_THEME
        assert pattern.confidence == 0.8
        assert pattern.status == PatternStatus.DETECTED

        # Verify database insert was called
        shard_with_db._db.execute.assert_called()

        # Verify event was emitted
        shard_with_db._events.emit.assert_called_once()
        event_name = shard_with_db._events.emit.call_args[0][0]
        assert event_name == "patterns.pattern.detected"

    @pytest.mark.asyncio
    async def test_create_pattern_with_criteria(self, shard_with_db):
        """Test creating a pattern with criteria."""
        criteria = PatternCriteria(
            keywords=["fraud", "embezzlement"],
            min_occurrences=5,
        )

        pattern = await shard_with_db.create_pattern(
            name="Financial Fraud Pattern",
            description="Pattern of financial fraud indicators",
            pattern_type=PatternType.BEHAVIORAL,
            criteria=criteria,
        )

        assert pattern.criteria.keywords == ["fraud", "embezzlement"]
        assert pattern.criteria.min_occurrences == 5

    @pytest.mark.asyncio
    async def test_get_pattern_found(self, shard_with_db):
        """Test getting an existing pattern."""
        mock_row = {
            "id": "pattern-123",
            "name": "Test Pattern",
            "description": "A test pattern",
            "pattern_type": "recurring_theme",
            "status": "detected",
            "confidence": 0.7,
            "match_count": 5,
            "document_count": 3,
            "entity_count": 2,
            "first_detected": datetime.utcnow().isoformat(),
            "last_matched": None,
            "detection_method": "manual",
            "detection_model": None,
            "criteria": "{}",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": "user",
            "metadata": "{}",
        }
        shard_with_db._db.fetch_one = AsyncMock(return_value=mock_row)

        pattern = await shard_with_db.get_pattern("pattern-123")

        assert pattern is not None
        assert pattern.id == "pattern-123"
        assert pattern.name == "Test Pattern"
        assert pattern.match_count == 5

    @pytest.mark.asyncio
    async def test_get_pattern_not_found(self, shard_with_db):
        """Test getting a non-existent pattern."""
        shard_with_db._db.fetch_one = AsyncMock(return_value=None)

        pattern = await shard_with_db.get_pattern("nonexistent")

        assert pattern is None

    @pytest.mark.asyncio
    async def test_list_patterns_empty(self, shard_with_db):
        """Test listing patterns when empty."""
        patterns = await shard_with_db.list_patterns()

        assert patterns == []

    @pytest.mark.asyncio
    async def test_update_pattern(self, shard_with_db):
        """Test updating a pattern."""
        mock_row = {
            "id": "pattern-123",
            "name": "Original Name",
            "description": "Original description",
            "pattern_type": "recurring_theme",
            "status": "detected",
            "confidence": 0.5,
            "match_count": 0,
            "document_count": 0,
            "entity_count": 0,
            "first_detected": datetime.utcnow().isoformat(),
            "last_matched": None,
            "detection_method": "manual",
            "detection_model": None,
            "criteria": "{}",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": "user",
            "metadata": "{}",
        }
        shard_with_db._db.fetch_one = AsyncMock(return_value=mock_row)

        pattern = await shard_with_db.update_pattern(
            pattern_id="pattern-123",
            name="Updated Name",
            confidence=0.9,
        )

        assert pattern.name == "Updated Name"
        assert pattern.confidence == 0.9

    @pytest.mark.asyncio
    async def test_delete_pattern(self, shard_with_db):
        """Test deleting a pattern."""
        result = await shard_with_db.delete_pattern("pattern-123")

        assert result is True
        # Verify both matches and pattern were deleted
        assert shard_with_db._db.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_confirm_pattern(self, shard_with_db):
        """Test confirming a pattern."""
        mock_row = {
            "id": "pattern-123",
            "name": "Test Pattern",
            "description": "Test",
            "pattern_type": "recurring_theme",
            "status": "detected",
            "confidence": 0.7,
            "match_count": 5,
            "document_count": 3,
            "entity_count": 0,
            "first_detected": datetime.utcnow().isoformat(),
            "last_matched": None,
            "detection_method": "manual",
            "detection_model": None,
            "criteria": "{}",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": "user",
            "metadata": "{}",
        }
        shard_with_db._db.fetch_one = AsyncMock(return_value=mock_row)

        pattern = await shard_with_db.confirm_pattern("pattern-123")

        assert pattern.status == PatternStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_dismiss_pattern(self, shard_with_db):
        """Test dismissing a pattern."""
        mock_row = {
            "id": "pattern-123",
            "name": "Test Pattern",
            "description": "Test",
            "pattern_type": "recurring_theme",
            "status": "detected",
            "confidence": 0.3,
            "match_count": 1,
            "document_count": 1,
            "entity_count": 0,
            "first_detected": datetime.utcnow().isoformat(),
            "last_matched": None,
            "detection_method": "automated",
            "detection_model": None,
            "criteria": "{}",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "created_by": "system",
            "metadata": "{}",
        }
        shard_with_db._db.fetch_one = AsyncMock(return_value=mock_row)

        pattern = await shard_with_db.dismiss_pattern("pattern-123", notes="False positive")

        assert pattern.status == PatternStatus.DISMISSED


class TestPatternMatches:
    """Tests for pattern match operations."""

    @pytest.fixture
    def shard_with_db(self):
        """Create shard with mocked database."""
        shard = PatternsShard()
        shard._db = AsyncMock()
        shard._db.execute = AsyncMock()
        shard._db.fetch_one = AsyncMock(return_value={"count": 0})
        shard._db.fetch_all = AsyncMock(return_value=[])
        shard._events = AsyncMock()
        shard._events.emit = AsyncMock()
        shard._initialized = True
        return shard

    @pytest.mark.asyncio
    async def test_add_match(self, shard_with_db):
        """Test adding a match to a pattern."""
        match_create = PatternMatchCreate(
            source_type=SourceType.DOCUMENT,
            source_id="doc-123",
            source_title="Test Document",
            match_score=0.85,
            excerpt="Matching text excerpt...",
        )

        match = await shard_with_db.add_match("pattern-123", match_create)

        assert match.pattern_id == "pattern-123"
        assert match.source_type == SourceType.DOCUMENT
        assert match.source_id == "doc-123"
        assert match.match_score == 0.85

        # Verify event was emitted
        shard_with_db._events.emit.assert_called()

    @pytest.mark.asyncio
    async def test_get_pattern_matches(self, shard_with_db):
        """Test getting matches for a pattern."""
        matches = await shard_with_db.get_pattern_matches("pattern-123")

        assert matches == []

    @pytest.mark.asyncio
    async def test_remove_match(self, shard_with_db):
        """Test removing a match."""
        result = await shard_with_db.remove_match("pattern-123", "match-456")

        assert result is True


class TestPatternAnalysis:
    """Tests for pattern analysis."""

    @pytest.fixture
    def shard_with_services(self):
        """Create shard with mocked services."""
        shard = PatternsShard()
        shard._db = AsyncMock()
        shard._db.execute = AsyncMock()
        shard._db.fetch_one = AsyncMock(return_value=None)
        shard._db.fetch_all = AsyncMock(return_value=[])
        shard._events = AsyncMock()
        shard._events.emit = AsyncMock()
        shard._initialized = True
        return shard

    @pytest.mark.asyncio
    async def test_analyze_documents_no_text(self, shard_with_services):
        """Test analysis with no text."""
        request = PatternAnalysisRequest(
            document_ids=[],
            text=None,
        )

        result = await shard_with_services.analyze_documents(request)

        assert result.documents_analyzed == 0
        assert "No text to analyze" in result.errors

    @pytest.mark.asyncio
    async def test_analyze_documents_with_text(self, shard_with_services):
        """Test analysis with text."""
        request = PatternAnalysisRequest(
            text="This is a test text with some repeated words. The words appear multiple times. Words are important.",
            min_confidence=0.3,
        )

        result = await shard_with_services.analyze_documents(request)

        assert result.processing_time_ms > 0
        # Keyword detection should find some patterns
        assert isinstance(result.patterns_detected, list)

    @pytest.mark.asyncio
    async def test_find_correlations(self, shard_with_services):
        """Test finding correlations."""
        request = CorrelationRequest(
            entity_ids=["entity-1", "entity-2", "entity-3"],
            time_window_days=90,
        )

        result = await shard_with_services.find_correlations(request)

        assert result.entities_analyzed == 3
        assert result.processing_time_ms >= 0


class TestStatistics:
    """Tests for statistics."""

    @pytest.fixture
    def shard_with_db(self):
        """Create shard with mocked database."""
        shard = PatternsShard()
        shard._db = AsyncMock()
        shard._initialized = True
        return shard

    @pytest.mark.asyncio
    async def test_get_statistics(self, shard_with_db):
        """Test getting statistics."""
        shard_with_db._db.fetch_one = AsyncMock(return_value={"count": 10, "avg": 0.75})
        shard_with_db._db.fetch_all = AsyncMock(return_value=[
            {"pattern_type": "recurring_theme", "count": 5},
            {"pattern_type": "behavioral", "count": 5},
        ])

        stats = await shard_with_db.get_statistics()

        assert stats.total_patterns == 10
        assert "recurring_theme" in stats.by_type

    @pytest.mark.asyncio
    async def test_get_count(self, shard_with_db):
        """Test getting pattern count."""
        shard_with_db._db.fetch_one = AsyncMock(return_value={"count": 42})

        count = await shard_with_db.get_count()

        assert count == 42

    @pytest.mark.asyncio
    async def test_get_count_with_status(self, shard_with_db):
        """Test getting pattern count with status filter."""
        shard_with_db._db.fetch_one = AsyncMock(return_value={"count": 15})

        count = await shard_with_db.get_count(status="confirmed")

        assert count == 15

    @pytest.mark.asyncio
    async def test_get_match_count(self, shard_with_db):
        """Test getting match count for a pattern."""
        shard_with_db._db.fetch_one = AsyncMock(return_value={"count": 25})

        count = await shard_with_db.get_match_count("pattern-123")

        assert count == 25


class TestRoutes:
    """Tests for route registration."""

    def test_get_routes(self):
        """Test that get_routes returns a router."""
        shard = PatternsShard()
        router = shard.get_routes()

        assert router is not None
        # Verify router has routes registered
        assert len(router.routes) > 0
