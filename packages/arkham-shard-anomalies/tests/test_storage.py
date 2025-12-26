"""
Anomalies Shard - Storage Tests

Tests for the AnomalyStore class.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta

from arkham_shard_anomalies.storage import AnomalyStore
from arkham_shard_anomalies.models import (
    Anomaly,
    AnomalyType,
    AnomalyStatus,
    SeverityLevel,
    AnomalyPattern,
    AnalystNote,
)


class TestAnomalyStoreInit:
    """Tests for AnomalyStore initialization."""

    def test_initialization(self):
        """Test store initializes with empty collections."""
        store = AnomalyStore()
        assert store.anomalies == {}
        assert store.patterns == {}
        assert store.notes == {}


class TestAnomalyCRUD:
    """Tests for anomaly CRUD operations."""

    @pytest.fixture
    def store(self):
        """Create store for testing."""
        return AnomalyStore()

    @pytest.fixture
    def sample_anomaly(self):
        """Create sample anomaly."""
        return Anomaly(
            id="anom-123",
            doc_id="doc-456",
            anomaly_type=AnomalyType.CONTENT,
            score=3.5,
            severity=SeverityLevel.MEDIUM,
        )

    @pytest.mark.asyncio
    async def test_create_anomaly(self, store, sample_anomaly):
        """Test creating an anomaly."""
        result = await store.create_anomaly(sample_anomaly)
        assert result.id == sample_anomaly.id
        assert sample_anomaly.id in store.anomalies

    @pytest.mark.asyncio
    async def test_get_anomaly(self, store, sample_anomaly):
        """Test getting an anomaly by ID."""
        await store.create_anomaly(sample_anomaly)
        result = await store.get_anomaly(sample_anomaly.id)
        assert result is not None
        assert result.id == sample_anomaly.id
        assert result.doc_id == sample_anomaly.doc_id

    @pytest.mark.asyncio
    async def test_get_anomaly_not_found(self, store):
        """Test getting nonexistent anomaly returns None."""
        result = await store.get_anomaly("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_anomaly(self, store, sample_anomaly):
        """Test updating an anomaly."""
        await store.create_anomaly(sample_anomaly)
        sample_anomaly.status = AnomalyStatus.CONFIRMED
        result = await store.update_anomaly(sample_anomaly)
        assert result.status == AnomalyStatus.CONFIRMED
        assert result.updated_at > sample_anomaly.detected_at

    @pytest.mark.asyncio
    async def test_delete_anomaly(self, store, sample_anomaly):
        """Test deleting an anomaly."""
        await store.create_anomaly(sample_anomaly)
        result = await store.delete_anomaly(sample_anomaly.id)
        assert result is True
        assert sample_anomaly.id not in store.anomalies

    @pytest.mark.asyncio
    async def test_delete_anomaly_not_found(self, store):
        """Test deleting nonexistent anomaly returns False."""
        result = await store.delete_anomaly("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_anomaly_removes_notes(self, store, sample_anomaly):
        """Test deleting anomaly also removes associated notes."""
        await store.create_anomaly(sample_anomaly)
        note = AnalystNote(
            id="note-1",
            anomaly_id=sample_anomaly.id,
            author="analyst",
            content="Test note",
        )
        await store.add_note(note)

        await store.delete_anomaly(sample_anomaly.id)
        assert sample_anomaly.id not in store.notes


class TestAnomalyListing:
    """Tests for anomaly listing with filters."""

    @pytest.fixture
    def store(self):
        """Create store with sample data."""
        store = AnomalyStore()
        return store

    @pytest_asyncio.fixture
    async def populated_store(self, store):
        """Create store populated with test data."""
        anomalies = [
            Anomaly(id="a1", doc_id="doc-1", anomaly_type=AnomalyType.CONTENT, status=AnomalyStatus.DETECTED, severity=SeverityLevel.HIGH),
            Anomaly(id="a2", doc_id="doc-1", anomaly_type=AnomalyType.RED_FLAG, status=AnomalyStatus.CONFIRMED, severity=SeverityLevel.CRITICAL),
            Anomaly(id="a3", doc_id="doc-2", anomaly_type=AnomalyType.STATISTICAL, status=AnomalyStatus.DISMISSED, severity=SeverityLevel.LOW),
            Anomaly(id="a4", doc_id="doc-3", anomaly_type=AnomalyType.CONTENT, status=AnomalyStatus.DETECTED, severity=SeverityLevel.MEDIUM),
            Anomaly(id="a5", doc_id="doc-3", anomaly_type=AnomalyType.METADATA, status=AnomalyStatus.FALSE_POSITIVE, severity=SeverityLevel.LOW),
        ]
        for a in anomalies:
            await store.create_anomaly(a)
        return store

    @pytest.mark.asyncio
    async def test_list_all_anomalies(self, populated_store):
        """Test listing all anomalies."""
        anomalies, total = await populated_store.list_anomalies()
        assert total == 5
        assert len(anomalies) == 5

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, populated_store):
        """Test listing with pagination."""
        anomalies, total = await populated_store.list_anomalies(offset=0, limit=2)
        assert total == 5
        assert len(anomalies) == 2

        anomalies2, total2 = await populated_store.list_anomalies(offset=2, limit=2)
        assert total2 == 5
        assert len(anomalies2) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_type(self, populated_store):
        """Test filtering by anomaly type."""
        anomalies, total = await populated_store.list_anomalies(anomaly_type=AnomalyType.CONTENT)
        assert total == 2
        assert all(a.anomaly_type == AnomalyType.CONTENT for a in anomalies)

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, populated_store):
        """Test filtering by status."""
        anomalies, total = await populated_store.list_anomalies(status=AnomalyStatus.DETECTED)
        assert total == 2
        assert all(a.status == AnomalyStatus.DETECTED for a in anomalies)

    @pytest.mark.asyncio
    async def test_list_filter_by_severity(self, populated_store):
        """Test filtering by severity."""
        anomalies, total = await populated_store.list_anomalies(severity=SeverityLevel.LOW)
        assert total == 2
        assert all(a.severity == SeverityLevel.LOW for a in anomalies)

    @pytest.mark.asyncio
    async def test_list_filter_by_doc_id(self, populated_store):
        """Test filtering by document ID."""
        anomalies, total = await populated_store.list_anomalies(doc_id="doc-1")
        assert total == 2
        assert all(a.doc_id == "doc-1" for a in anomalies)

    @pytest.mark.asyncio
    async def test_list_combined_filters(self, populated_store):
        """Test combining multiple filters."""
        anomalies, total = await populated_store.list_anomalies(
            anomaly_type=AnomalyType.CONTENT,
            status=AnomalyStatus.DETECTED,
        )
        assert total == 2
        assert all(a.anomaly_type == AnomalyType.CONTENT and a.status == AnomalyStatus.DETECTED for a in anomalies)

    @pytest.mark.asyncio
    async def test_get_anomalies_by_doc(self, populated_store):
        """Test getting all anomalies for a document."""
        anomalies = await populated_store.get_anomalies_by_doc("doc-3")
        assert len(anomalies) == 2
        assert all(a.doc_id == "doc-3" for a in anomalies)


class TestStatusUpdate:
    """Tests for status update operations."""

    @pytest.fixture
    def store(self):
        """Create store for testing."""
        return AnomalyStore()

    @pytest_asyncio.fixture
    async def store_with_anomaly(self, store):
        """Create store with one anomaly."""
        anomaly = Anomaly(
            id="anom-1",
            doc_id="doc-1",
            anomaly_type=AnomalyType.CONTENT,
        )
        await store.create_anomaly(anomaly)
        return store

    @pytest.mark.asyncio
    async def test_update_status(self, store_with_anomaly):
        """Test updating anomaly status."""
        result = await store_with_anomaly.update_status(
            anomaly_id="anom-1",
            status=AnomalyStatus.CONFIRMED,
            reviewed_by="analyst@example.com",
            notes="Confirmed as legitimate anomaly",
        )
        assert result is not None
        assert result.status == AnomalyStatus.CONFIRMED
        assert result.reviewed_by == "analyst@example.com"
        assert result.reviewed_at is not None
        assert result.notes == "Confirmed as legitimate anomaly"

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, store):
        """Test updating status for nonexistent anomaly."""
        result = await store.update_status(
            anomaly_id="nonexistent",
            status=AnomalyStatus.CONFIRMED,
        )
        assert result is None


class TestAnalystNotes:
    """Tests for analyst note operations."""

    @pytest.fixture
    def store(self):
        """Create store for testing."""
        return AnomalyStore()

    @pytest_asyncio.fixture
    async def store_with_anomaly(self, store):
        """Create store with one anomaly."""
        anomaly = Anomaly(
            id="anom-1",
            doc_id="doc-1",
            anomaly_type=AnomalyType.CONTENT,
        )
        await store.create_anomaly(anomaly)
        return store

    @pytest.mark.asyncio
    async def test_add_note(self, store_with_anomaly):
        """Test adding an analyst note."""
        note = AnalystNote(
            id="note-1",
            anomaly_id="anom-1",
            author="analyst@example.com",
            content="This needs further investigation.",
        )
        result = await store_with_anomaly.add_note(note)
        assert result.id == "note-1"
        assert "anom-1" in store_with_anomaly.notes

    @pytest.mark.asyncio
    async def test_add_multiple_notes(self, store_with_anomaly):
        """Test adding multiple notes."""
        for i in range(3):
            note = AnalystNote(
                id=f"note-{i}",
                anomaly_id="anom-1",
                author="analyst@example.com",
                content=f"Note {i}",
            )
            await store_with_anomaly.add_note(note)

        notes = await store_with_anomaly.get_notes("anom-1")
        assert len(notes) == 3

    @pytest.mark.asyncio
    async def test_get_notes(self, store_with_anomaly):
        """Test getting notes for an anomaly."""
        note = AnalystNote(
            id="note-1",
            anomaly_id="anom-1",
            author="analyst@example.com",
            content="Test note",
        )
        await store_with_anomaly.add_note(note)

        notes = await store_with_anomaly.get_notes("anom-1")
        assert len(notes) == 1
        assert notes[0].content == "Test note"

    @pytest.mark.asyncio
    async def test_get_notes_empty(self, store_with_anomaly):
        """Test getting notes for anomaly with no notes."""
        notes = await store_with_anomaly.get_notes("anom-1")
        assert notes == []


class TestPatternCRUD:
    """Tests for pattern CRUD operations."""

    @pytest.fixture
    def store(self):
        """Create store for testing."""
        return AnomalyStore()

    @pytest.fixture
    def sample_pattern(self):
        """Create sample pattern."""
        return AnomalyPattern(
            id="pat-123",
            pattern_type="money_cluster",
            description="Multiple documents with excessive money references",
            anomaly_ids=["a1", "a2", "a3"],
            doc_ids=["doc-1", "doc-2", "doc-3"],
            frequency=3,
        )

    @pytest.mark.asyncio
    async def test_create_pattern(self, store, sample_pattern):
        """Test creating a pattern."""
        result = await store.create_pattern(sample_pattern)
        assert result.id == sample_pattern.id
        assert sample_pattern.id in store.patterns

    @pytest.mark.asyncio
    async def test_get_pattern(self, store, sample_pattern):
        """Test getting a pattern."""
        await store.create_pattern(sample_pattern)
        result = await store.get_pattern(sample_pattern.id)
        assert result is not None
        assert result.pattern_type == "money_cluster"

    @pytest.mark.asyncio
    async def test_get_pattern_not_found(self, store):
        """Test getting nonexistent pattern."""
        result = await store.get_pattern("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_patterns(self, store):
        """Test listing patterns."""
        for i in range(3):
            pattern = AnomalyPattern(
                id=f"pat-{i}",
                pattern_type=f"type-{i}",
                description=f"Pattern {i}",
            )
            await store.create_pattern(pattern)

        patterns = await store.list_patterns()
        assert len(patterns) == 3


class TestStatistics:
    """Tests for statistics calculation."""

    @pytest_asyncio.fixture
    async def populated_store(self):
        """Create store populated with test data."""
        store = AnomalyStore()
        now = datetime.utcnow()

        anomalies = [
            Anomaly(id="a1", doc_id="doc-1", anomaly_type=AnomalyType.CONTENT, status=AnomalyStatus.DETECTED, severity=SeverityLevel.HIGH, confidence=0.9, detected_at=now),
            Anomaly(id="a2", doc_id="doc-2", anomaly_type=AnomalyType.RED_FLAG, status=AnomalyStatus.CONFIRMED, severity=SeverityLevel.CRITICAL, confidence=0.95, detected_at=now, reviewed_at=now),
            Anomaly(id="a3", doc_id="doc-3", anomaly_type=AnomalyType.STATISTICAL, status=AnomalyStatus.DISMISSED, severity=SeverityLevel.LOW, confidence=0.7, detected_at=now, reviewed_at=now),
            Anomaly(id="a4", doc_id="doc-4", anomaly_type=AnomalyType.CONTENT, status=AnomalyStatus.FALSE_POSITIVE, severity=SeverityLevel.MEDIUM, confidence=0.8, detected_at=now, reviewed_at=now),
            Anomaly(id="a5", doc_id="doc-5", anomaly_type=AnomalyType.METADATA, status=AnomalyStatus.DETECTED, severity=SeverityLevel.LOW, confidence=0.6, detected_at=now - timedelta(days=2)),
        ]
        for a in anomalies:
            await store.create_anomaly(a)
        return store

    @pytest.mark.asyncio
    async def test_get_stats_total(self, populated_store):
        """Test total count in statistics."""
        stats = await populated_store.get_stats()
        assert stats.total_anomalies == 5

    @pytest.mark.asyncio
    async def test_get_stats_by_type(self, populated_store):
        """Test counts by type."""
        stats = await populated_store.get_stats()
        assert stats.by_type['content'] == 2
        assert stats.by_type['red_flag'] == 1

    @pytest.mark.asyncio
    async def test_get_stats_by_status(self, populated_store):
        """Test counts by status."""
        stats = await populated_store.get_stats()
        assert stats.by_status['detected'] == 2
        assert stats.by_status['confirmed'] == 1
        assert stats.by_status['dismissed'] == 1
        assert stats.by_status['false_positive'] == 1

    @pytest.mark.asyncio
    async def test_get_stats_by_severity(self, populated_store):
        """Test counts by severity."""
        stats = await populated_store.get_stats()
        assert stats.by_severity['high'] == 1
        assert stats.by_severity['critical'] == 1
        assert stats.by_severity['low'] == 2
        assert stats.by_severity['medium'] == 1

    @pytest.mark.asyncio
    async def test_get_stats_recent_activity(self, populated_store):
        """Test recent activity counts."""
        stats = await populated_store.get_stats()
        assert stats.detected_last_24h == 4  # 5th one is 2 days old
        assert stats.confirmed_last_24h == 1
        assert stats.dismissed_last_24h == 1

    @pytest.mark.asyncio
    async def test_get_stats_false_positive_rate(self, populated_store):
        """Test false positive rate calculation."""
        stats = await populated_store.get_stats()
        # 1 false positive out of 3 reviewed (confirmed, dismissed, false_positive)
        assert stats.false_positive_rate == pytest.approx(1/3, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_stats_avg_confidence(self, populated_store):
        """Test average confidence calculation."""
        stats = await populated_store.get_stats()
        expected_avg = (0.9 + 0.95 + 0.7 + 0.8 + 0.6) / 5
        assert stats.avg_confidence == pytest.approx(expected_avg, rel=0.01)


class TestFacets:
    """Tests for facet calculation."""

    @pytest_asyncio.fixture
    async def populated_store(self):
        """Create store populated with test data."""
        store = AnomalyStore()
        anomalies = [
            Anomaly(id="a1", doc_id="doc-1", anomaly_type=AnomalyType.CONTENT, status=AnomalyStatus.DETECTED, severity=SeverityLevel.HIGH),
            Anomaly(id="a2", doc_id="doc-2", anomaly_type=AnomalyType.CONTENT, status=AnomalyStatus.CONFIRMED, severity=SeverityLevel.HIGH),
            Anomaly(id="a3", doc_id="doc-3", anomaly_type=AnomalyType.RED_FLAG, status=AnomalyStatus.DETECTED, severity=SeverityLevel.CRITICAL),
        ]
        for a in anomalies:
            await store.create_anomaly(a)
        return store

    @pytest.mark.asyncio
    async def test_get_facets(self, populated_store):
        """Test facet calculation."""
        facets = await populated_store.get_facets()

        assert 'types' in facets
        assert 'statuses' in facets
        assert 'severities' in facets

        assert facets['types']['content'] == 2
        assert facets['types']['red_flag'] == 1
        assert facets['statuses']['detected'] == 2
        assert facets['statuses']['confirmed'] == 1
        assert facets['severities']['high'] == 2
        assert facets['severities']['critical'] == 1
