"""
Search Shard - Filter Tests

Tests for FilterBuilder and FilterOptimizer classes.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from arkham_shard_search.filters import FilterBuilder, FilterOptimizer
from arkham_shard_search.models import SearchFilters, DateRangeFilter, SearchResultItem


class TestFilterBuilderFromDict:
    """Tests for FilterBuilder.from_dict method."""

    def test_empty_dict(self):
        """Test building filters from empty dict."""
        filters = FilterBuilder.from_dict({})
        assert filters.date_range is None
        assert filters.entity_ids == []
        assert filters.project_ids == []
        assert filters.file_types == []
        assert filters.tags == []
        assert filters.min_score == 0.0

    def test_with_date_range_start_only(self):
        """Test building filters with date range start only."""
        data = {
            "date_range": {
                "start": "2024-01-01T00:00:00",
            }
        }
        filters = FilterBuilder.from_dict(data)
        assert filters.date_range is not None
        assert filters.date_range.start == datetime(2024, 1, 1, 0, 0, 0)
        assert filters.date_range.end is None

    def test_with_date_range_end_only(self):
        """Test building filters with date range end only."""
        data = {
            "date_range": {
                "end": "2024-12-31T23:59:59",
            }
        }
        filters = FilterBuilder.from_dict(data)
        assert filters.date_range is not None
        assert filters.date_range.start is None
        assert filters.date_range.end == datetime(2024, 12, 31, 23, 59, 59)

    def test_with_full_date_range(self):
        """Test building filters with full date range."""
        data = {
            "date_range": {
                "start": "2024-01-01T00:00:00",
                "end": "2024-12-31T23:59:59",
            }
        }
        filters = FilterBuilder.from_dict(data)
        assert filters.date_range.start == datetime(2024, 1, 1, 0, 0, 0)
        assert filters.date_range.end == datetime(2024, 12, 31, 23, 59, 59)

    def test_with_entity_ids(self):
        """Test building filters with entity IDs."""
        data = {"entity_ids": ["ent-1", "ent-2", "ent-3"]}
        filters = FilterBuilder.from_dict(data)
        assert filters.entity_ids == ["ent-1", "ent-2", "ent-3"]

    def test_with_empty_entity_ids(self):
        """Test building filters with empty entity IDs."""
        data = {"entity_ids": []}
        filters = FilterBuilder.from_dict(data)
        assert filters.entity_ids == []

    def test_with_project_ids(self):
        """Test building filters with project IDs."""
        data = {"project_ids": ["proj-alpha", "proj-beta"]}
        filters = FilterBuilder.from_dict(data)
        assert filters.project_ids == ["proj-alpha", "proj-beta"]

    def test_with_file_types(self):
        """Test building filters with file types."""
        data = {"file_types": ["pdf", "docx", "txt"]}
        filters = FilterBuilder.from_dict(data)
        assert filters.file_types == ["pdf", "docx", "txt"]

    def test_with_tags(self):
        """Test building filters with tags."""
        data = {"tags": ["important", "reviewed", "confidential"]}
        filters = FilterBuilder.from_dict(data)
        assert filters.tags == ["important", "reviewed", "confidential"]

    def test_with_min_score(self):
        """Test building filters with minimum score."""
        data = {"min_score": 0.75}
        filters = FilterBuilder.from_dict(data)
        assert filters.min_score == 0.75

    def test_with_min_score_as_string(self):
        """Test building filters with minimum score as string."""
        data = {"min_score": "0.5"}
        filters = FilterBuilder.from_dict(data)
        assert filters.min_score == 0.5

    def test_with_all_fields(self):
        """Test building filters with all fields."""
        data = {
            "date_range": {
                "start": "2024-01-01T00:00:00",
                "end": "2024-06-30T23:59:59",
            },
            "entity_ids": ["ent-1"],
            "project_ids": ["proj-1"],
            "file_types": ["pdf"],
            "tags": ["important"],
            "min_score": 0.6,
        }
        filters = FilterBuilder.from_dict(data)
        assert filters.date_range is not None
        assert len(filters.entity_ids) == 1
        assert len(filters.project_ids) == 1
        assert len(filters.file_types) == 1
        assert len(filters.tags) == 1
        assert filters.min_score == 0.6

    def test_ignores_null_date_range(self):
        """Test that null date_range is ignored."""
        data = {"date_range": None}
        filters = FilterBuilder.from_dict(data)
        assert filters.date_range is None


class TestFilterBuilderValidate:
    """Tests for FilterBuilder.validate method."""

    def test_valid_empty_filters(self):
        """Test validation of empty filters."""
        filters = SearchFilters()
        is_valid, error = FilterBuilder.validate(filters)
        assert is_valid is True
        assert error == ""

    def test_valid_date_range(self):
        """Test validation of valid date range."""
        filters = SearchFilters(
            date_range=DateRangeFilter(
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31),
            )
        )
        is_valid, error = FilterBuilder.validate(filters)
        assert is_valid is True
        assert error == ""

    def test_invalid_date_range_start_after_end(self):
        """Test validation fails when start is after end."""
        filters = SearchFilters(
            date_range=DateRangeFilter(
                start=datetime(2024, 12, 31),
                end=datetime(2024, 1, 1),
            )
        )
        is_valid, error = FilterBuilder.validate(filters)
        assert is_valid is False
        assert "Start date must be before end date" in error

    def test_valid_date_range_same_day(self):
        """Test validation of same-day date range."""
        same_day = datetime(2024, 6, 15)
        filters = SearchFilters(
            date_range=DateRangeFilter(start=same_day, end=same_day)
        )
        is_valid, error = FilterBuilder.validate(filters)
        assert is_valid is True

    def test_valid_min_score(self):
        """Test validation of valid minimum score."""
        filters = SearchFilters(min_score=0.5)
        is_valid, error = FilterBuilder.validate(filters)
        assert is_valid is True

    def test_invalid_min_score_negative(self):
        """Test validation fails for negative min_score."""
        filters = SearchFilters(min_score=-0.1)
        is_valid, error = FilterBuilder.validate(filters)
        assert is_valid is False
        assert "Minimum score must be between 0.0 and 1.0" in error

    def test_invalid_min_score_over_one(self):
        """Test validation fails for min_score over 1.0."""
        filters = SearchFilters(min_score=1.5)
        is_valid, error = FilterBuilder.validate(filters)
        assert is_valid is False
        assert "Minimum score must be between 0.0 and 1.0" in error

    def test_valid_boundary_min_scores(self):
        """Test validation of boundary min_score values."""
        filters_zero = SearchFilters(min_score=0.0)
        is_valid, _ = FilterBuilder.validate(filters_zero)
        assert is_valid is True

        filters_one = SearchFilters(min_score=1.0)
        is_valid, _ = FilterBuilder.validate(filters_one)
        assert is_valid is True


class TestFilterOptimizer:
    """Tests for FilterOptimizer class."""

    @pytest.fixture
    def mock_db_service(self):
        """Create mock database service."""
        return MagicMock()

    @pytest.fixture
    def optimizer(self, mock_db_service):
        """Create FilterOptimizer with mock DB."""
        return FilterOptimizer(mock_db_service)

    def test_initialization(self, mock_db_service):
        """Test FilterOptimizer initialization."""
        optimizer = FilterOptimizer(mock_db_service)
        assert optimizer.db == mock_db_service

    @pytest.mark.asyncio
    async def test_get_available_filters_no_query(self, optimizer):
        """Test getting available filters without query."""
        available = await optimizer.get_available_filters()
        assert "file_types" in available
        assert "entities" in available
        assert "projects" in available
        assert "date_ranges" in available

    @pytest.mark.asyncio
    async def test_get_available_filters_with_query(self, optimizer):
        """Test getting available filters with query."""
        available = await optimizer.get_available_filters(query="test query")
        assert isinstance(available, dict)
        assert "file_types" in available

    @pytest.mark.asyncio
    async def test_get_available_filters_date_ranges_structure(self, optimizer):
        """Test date ranges structure in available filters."""
        available = await optimizer.get_available_filters()
        date_ranges = available["date_ranges"]
        assert "last_week" in date_ranges
        assert "last_month" in date_ranges
        assert "last_year" in date_ranges


class TestFilterOptimizerApplyFilters:
    """Tests for FilterOptimizer.apply_filters method."""

    @pytest.fixture
    def optimizer(self):
        """Create FilterOptimizer with mock DB."""
        return FilterOptimizer(MagicMock())

    @pytest.fixture
    def sample_results(self):
        """Create sample search results."""
        return [
            SearchResultItem(
                doc_id="doc-1",
                chunk_id=None,
                title="Doc 1",
                excerpt="...",
                score=0.9,
            ),
            SearchResultItem(
                doc_id="doc-2",
                chunk_id=None,
                title="Doc 2",
                excerpt="...",
                score=0.7,
            ),
            SearchResultItem(
                doc_id="doc-3",
                chunk_id=None,
                title="Doc 3",
                excerpt="...",
                score=0.5,
            ),
            SearchResultItem(
                doc_id="doc-4",
                chunk_id=None,
                title="Doc 4",
                excerpt="...",
                score=0.3,
            ),
        ]

    def test_apply_no_filters(self, optimizer, sample_results):
        """Test applying no filters returns all results."""
        result = optimizer.apply_filters(sample_results, None)
        assert len(result) == 4

    def test_apply_empty_filters(self, optimizer, sample_results):
        """Test applying empty filters returns all results."""
        filters = SearchFilters()
        result = optimizer.apply_filters(sample_results, filters)
        assert len(result) == 4

    def test_apply_min_score_filter(self, optimizer, sample_results):
        """Test applying minimum score filter."""
        filters = SearchFilters(min_score=0.6)
        result = optimizer.apply_filters(sample_results, filters)
        assert len(result) == 2
        assert all(r.score >= 0.6 for r in result)

    def test_apply_min_score_exact_match(self, optimizer, sample_results):
        """Test min_score filter includes exact matches."""
        filters = SearchFilters(min_score=0.5)
        result = optimizer.apply_filters(sample_results, filters)
        assert len(result) == 3  # 0.9, 0.7, 0.5

    def test_apply_min_score_filters_all(self, optimizer, sample_results):
        """Test min_score filter can filter all results."""
        filters = SearchFilters(min_score=0.95)
        result = optimizer.apply_filters(sample_results, filters)
        assert len(result) == 0

    def test_apply_min_score_zero(self, optimizer, sample_results):
        """Test min_score=0 returns all results."""
        filters = SearchFilters(min_score=0.0)
        result = optimizer.apply_filters(sample_results, filters)
        assert len(result) == 4
