"""
Search Shard - Model Tests

Tests for all dataclasses and enums in the models module.
"""

import pytest
from datetime import datetime

from arkham_shard_search.models import (
    SearchMode,
    SortBy,
    SortOrder,
    DateRangeFilter,
    SearchFilters,
    SearchQuery,
    SearchResultItem,
    SearchResult,
    SuggestionItem,
    SimilarityRequest,
)


class TestSearchModeEnum:
    """Tests for SearchMode enum."""

    def test_hybrid_mode(self):
        """Test HYBRID mode value."""
        assert SearchMode.HYBRID.value == "hybrid"

    def test_semantic_mode(self):
        """Test SEMANTIC mode value."""
        assert SearchMode.SEMANTIC.value == "semantic"

    def test_keyword_mode(self):
        """Test KEYWORD mode value."""
        assert SearchMode.KEYWORD.value == "keyword"

    def test_all_modes_exist(self):
        """Test all expected modes exist."""
        modes = [m.value for m in SearchMode]
        assert "hybrid" in modes
        assert "semantic" in modes
        assert "keyword" in modes
        assert len(modes) == 3


class TestSortByEnum:
    """Tests for SortBy enum."""

    def test_relevance_sort(self):
        """Test RELEVANCE sort value."""
        assert SortBy.RELEVANCE.value == "relevance"

    def test_date_sort(self):
        """Test DATE sort value."""
        assert SortBy.DATE.value == "date"

    def test_title_sort(self):
        """Test TITLE sort value."""
        assert SortBy.TITLE.value == "title"


class TestSortOrderEnum:
    """Tests for SortOrder enum."""

    def test_desc_order(self):
        """Test DESC order value."""
        assert SortOrder.DESC.value == "desc"

    def test_asc_order(self):
        """Test ASC order value."""
        assert SortOrder.ASC.value == "asc"


class TestDateRangeFilter:
    """Tests for DateRangeFilter dataclass."""

    def test_default_initialization(self):
        """Test DateRangeFilter with defaults."""
        dr = DateRangeFilter()
        assert dr.start is None
        assert dr.end is None

    def test_with_start_only(self):
        """Test DateRangeFilter with start only."""
        start = datetime(2024, 1, 1)
        dr = DateRangeFilter(start=start)
        assert dr.start == start
        assert dr.end is None

    def test_with_end_only(self):
        """Test DateRangeFilter with end only."""
        end = datetime(2024, 12, 31)
        dr = DateRangeFilter(end=end)
        assert dr.start is None
        assert dr.end == end

    def test_with_full_range(self):
        """Test DateRangeFilter with full range."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        dr = DateRangeFilter(start=start, end=end)
        assert dr.start == start
        assert dr.end == end


class TestSearchFilters:
    """Tests for SearchFilters dataclass."""

    def test_default_initialization(self):
        """Test SearchFilters with defaults."""
        filters = SearchFilters()
        assert filters.date_range is None
        assert filters.entity_ids == []
        assert filters.project_ids == []
        assert filters.file_types == []
        assert filters.tags == []
        assert filters.min_score == 0.0

    def test_with_date_range(self):
        """Test SearchFilters with date range."""
        dr = DateRangeFilter(start=datetime(2024, 1, 1))
        filters = SearchFilters(date_range=dr)
        assert filters.date_range == dr

    def test_with_entity_ids(self):
        """Test SearchFilters with entity IDs."""
        filters = SearchFilters(entity_ids=["ent-1", "ent-2"])
        assert filters.entity_ids == ["ent-1", "ent-2"]

    def test_with_project_ids(self):
        """Test SearchFilters with project IDs."""
        filters = SearchFilters(project_ids=["proj-1"])
        assert filters.project_ids == ["proj-1"]

    def test_with_file_types(self):
        """Test SearchFilters with file types."""
        filters = SearchFilters(file_types=["pdf", "docx"])
        assert filters.file_types == ["pdf", "docx"]

    def test_with_tags(self):
        """Test SearchFilters with tags."""
        filters = SearchFilters(tags=["important", "reviewed"])
        assert filters.tags == ["important", "reviewed"]

    def test_with_min_score(self):
        """Test SearchFilters with minimum score."""
        filters = SearchFilters(min_score=0.5)
        assert filters.min_score == 0.5


class TestSearchQuery:
    """Tests for SearchQuery dataclass."""

    def test_minimal_initialization(self):
        """Test SearchQuery with required fields only."""
        query = SearchQuery(query="test search")
        assert query.query == "test search"
        assert query.mode == SearchMode.HYBRID
        assert query.filters is None
        assert query.limit == 20
        assert query.offset == 0
        assert query.sort_by == SortBy.RELEVANCE
        assert query.sort_order == SortOrder.DESC
        assert query.semantic_weight == 0.7
        assert query.keyword_weight == 0.3

    def test_full_initialization(self):
        """Test SearchQuery with all fields."""
        filters = SearchFilters(min_score=0.5)
        query = SearchQuery(
            query="test",
            mode=SearchMode.SEMANTIC,
            filters=filters,
            limit=50,
            offset=10,
            sort_by=SortBy.DATE,
            sort_order=SortOrder.ASC,
            semantic_weight=0.9,
            keyword_weight=0.1,
        )
        assert query.query == "test"
        assert query.mode == SearchMode.SEMANTIC
        assert query.filters == filters
        assert query.limit == 50
        assert query.offset == 10
        assert query.sort_by == SortBy.DATE
        assert query.sort_order == SortOrder.ASC
        assert query.semantic_weight == 0.9
        assert query.keyword_weight == 0.1


class TestSearchResultItem:
    """Tests for SearchResultItem dataclass."""

    def test_minimal_initialization(self):
        """Test SearchResultItem with required fields only."""
        item = SearchResultItem(
            doc_id="doc-123",
            chunk_id="chunk-456",
            title="Test Document",
            excerpt="This is a test excerpt.",
            score=0.85,
        )
        assert item.doc_id == "doc-123"
        assert item.chunk_id == "chunk-456"
        assert item.title == "Test Document"
        assert item.excerpt == "This is a test excerpt."
        assert item.score == 0.85
        assert item.file_type is None
        assert item.created_at is None
        assert item.page_number is None
        assert item.highlights == []
        assert item.entities == []
        assert item.project_ids == []
        assert item.metadata == {}

    def test_full_initialization(self):
        """Test SearchResultItem with all fields."""
        created = datetime(2024, 6, 15)
        item = SearchResultItem(
            doc_id="doc-123",
            chunk_id="chunk-456",
            title="Test Document",
            excerpt="This is a test.",
            score=0.9,
            file_type="pdf",
            created_at=created,
            page_number=5,
            highlights=["...match..."],
            entities=["ent-1", "ent-2"],
            project_ids=["proj-1"],
            metadata={"source": "uploaded"},
        )
        assert item.file_type == "pdf"
        assert item.created_at == created
        assert item.page_number == 5
        assert item.highlights == ["...match..."]
        assert item.entities == ["ent-1", "ent-2"]
        assert item.project_ids == ["proj-1"]
        assert item.metadata == {"source": "uploaded"}


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_minimal_initialization(self):
        """Test SearchResult with required fields only."""
        result = SearchResult(
            query="test",
            mode=SearchMode.HYBRID,
            total=0,
        )
        assert result.query == "test"
        assert result.mode == SearchMode.HYBRID
        assert result.total == 0
        assert result.items == []
        assert result.duration_ms == 0.0
        assert result.facets == {}
        assert result.offset == 0
        assert result.limit == 20
        assert result.has_more is False

    def test_with_items(self):
        """Test SearchResult with items."""
        item = SearchResultItem(
            doc_id="doc-1",
            chunk_id=None,
            title="Test",
            excerpt="...",
            score=0.9,
        )
        result = SearchResult(
            query="test",
            mode=SearchMode.SEMANTIC,
            total=1,
            items=[item],
            duration_ms=45.2,
            has_more=False,
        )
        assert len(result.items) == 1
        assert result.items[0].doc_id == "doc-1"
        assert result.duration_ms == 45.2

    def test_with_pagination(self):
        """Test SearchResult with pagination."""
        result = SearchResult(
            query="test",
            mode=SearchMode.KEYWORD,
            total=100,
            offset=20,
            limit=20,
            has_more=True,
        )
        assert result.offset == 20
        assert result.limit == 20
        assert result.has_more is True


class TestSuggestionItem:
    """Tests for SuggestionItem dataclass."""

    def test_initialization(self):
        """Test SuggestionItem initialization."""
        item = SuggestionItem(
            text="machine learning",
            score=0.95,
            type="term",
        )
        assert item.text == "machine learning"
        assert item.score == 0.95
        assert item.type == "term"
        assert item.metadata == {}

    def test_with_metadata(self):
        """Test SuggestionItem with metadata."""
        item = SuggestionItem(
            text="John Smith",
            score=0.8,
            type="entity",
            metadata={"entity_id": "ent-123"},
        )
        assert item.type == "entity"
        assert item.metadata == {"entity_id": "ent-123"}

    def test_document_type(self):
        """Test SuggestionItem with document type."""
        item = SuggestionItem(
            text="Annual Report 2024",
            score=0.7,
            type="document",
            metadata={"doc_id": "doc-123"},
        )
        assert item.type == "document"


class TestSimilarityRequest:
    """Tests for SimilarityRequest dataclass."""

    def test_minimal_initialization(self):
        """Test SimilarityRequest with required fields only."""
        request = SimilarityRequest(doc_id="doc-123")
        assert request.doc_id == "doc-123"
        assert request.limit == 10
        assert request.min_similarity == 0.5
        assert request.filters is None

    def test_full_initialization(self):
        """Test SimilarityRequest with all fields."""
        filters = SearchFilters(file_types=["pdf"])
        request = SimilarityRequest(
            doc_id="doc-456",
            limit=20,
            min_similarity=0.7,
            filters=filters,
        )
        assert request.doc_id == "doc-456"
        assert request.limit == 20
        assert request.min_similarity == 0.7
        assert request.filters == filters
