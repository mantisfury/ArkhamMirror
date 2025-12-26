"""
Search Shard - Engine Tests

Tests for SemanticSearchEngine, KeywordSearchEngine, and HybridSearchEngine.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from arkham_shard_search.engines.semantic import SemanticSearchEngine
from arkham_shard_search.engines.keyword import KeywordSearchEngine
from arkham_shard_search.engines.hybrid import HybridSearchEngine
from arkham_shard_search.models import (
    SearchQuery,
    SearchMode,
    SearchFilters,
    DateRangeFilter,
    SearchResultItem,
)


class TestSemanticSearchEngineInit:
    """Tests for SemanticSearchEngine initialization."""

    def test_initialization_minimal(self):
        """Test engine initializes with just vectors service."""
        mock_vectors = MagicMock()
        engine = SemanticSearchEngine(vectors_service=mock_vectors)
        assert engine.vectors == mock_vectors
        assert engine.documents is None
        assert engine.embedding_service is None
        assert engine.worker_service is None

    def test_initialization_full(self):
        """Test engine initializes with all services."""
        mock_vectors = MagicMock()
        mock_docs = MagicMock()
        mock_embed = MagicMock()
        mock_worker = MagicMock()

        engine = SemanticSearchEngine(
            vectors_service=mock_vectors,
            documents_service=mock_docs,
            embedding_service=mock_embed,
            worker_service=mock_worker,
        )

        assert engine.vectors == mock_vectors
        assert engine.documents == mock_docs
        assert engine.embedding_service == mock_embed
        assert engine.worker_service == mock_worker


class TestSemanticSearchEngineSearch:
    """Tests for SemanticSearchEngine.search method."""

    @pytest.fixture
    def mock_vectors(self):
        """Create mock vectors service."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def engine(self, mock_vectors):
        """Create engine with mocked embedding."""
        engine = SemanticSearchEngine(vectors_service=mock_vectors)
        # Mock the embed_query method directly
        engine._embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
        return engine

    @pytest.mark.asyncio
    async def test_search_basic(self, engine, mock_vectors):
        """Test basic semantic search."""
        mock_vectors.search.return_value = [
            {
                "doc_id": "doc-1",
                "chunk_id": "chunk-1",
                "title": "Test Document",
                "text": "This is test content.",
                "score": 0.95,
            }
        ]

        query = SearchQuery(query="test query", mode=SearchMode.SEMANTIC)
        results = await engine.search(query)

        assert len(results) == 1
        assert results[0].doc_id == "doc-1"
        assert results[0].chunk_id == "chunk-1"
        assert results[0].title == "Test Document"
        assert results[0].score == 0.95
        mock_vectors.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_no_embedding(self, mock_vectors):
        """Test search returns empty when embedding fails."""
        engine = SemanticSearchEngine(vectors_service=mock_vectors)
        engine._embed_query = AsyncMock(return_value=None)

        query = SearchQuery(query="test", mode=SearchMode.SEMANTIC)
        results = await engine.search(query)

        assert results == []
        mock_vectors.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_filters(self, engine, mock_vectors):
        """Test search passes filters to vector store."""
        filters = SearchFilters(
            file_types=["pdf"],
            entity_ids=["ent-1"],
        )
        query = SearchQuery(
            query="test",
            mode=SearchMode.SEMANTIC,
            filters=filters,
        )

        await engine.search(query)

        call_kwargs = mock_vectors.search.call_args[1]
        assert "filters" in call_kwargs
        assert call_kwargs["filters"] is not None

    @pytest.mark.asyncio
    async def test_search_with_pagination(self, engine, mock_vectors):
        """Test search uses limit and offset."""
        query = SearchQuery(
            query="test",
            mode=SearchMode.SEMANTIC,
            limit=50,
            offset=10,
        )

        await engine.search(query)

        call_kwargs = mock_vectors.search.call_args[1]
        assert call_kwargs["limit"] == 50
        assert call_kwargs["offset"] == 10

    @pytest.mark.asyncio
    async def test_search_handles_exception(self, engine, mock_vectors):
        """Test search handles vector store exceptions."""
        mock_vectors.search.side_effect = Exception("Connection error")

        query = SearchQuery(query="test", mode=SearchMode.SEMANTIC)
        results = await engine.search(query)

        assert results == []


class TestSemanticSearchEngineFindSimilar:
    """Tests for SemanticSearchEngine.find_similar method."""

    @pytest.fixture
    def mock_vectors(self):
        """Create mock vectors service."""
        mock = MagicMock()
        mock.get_vector = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def engine(self, mock_vectors):
        """Create engine with mocks."""
        return SemanticSearchEngine(vectors_service=mock_vectors)

    @pytest.mark.asyncio
    async def test_find_similar_basic(self, engine, mock_vectors):
        """Test finding similar documents."""
        mock_vectors.search.return_value = [
            {"doc_id": "doc-2", "title": "Similar Doc", "score": 0.85},
        ]

        results = await engine.find_similar("doc-1", limit=5)

        assert len(results) == 1
        assert results[0].doc_id == "doc-2"
        mock_vectors.get_vector.assert_called_with(collection="documents", id="doc-1")

    @pytest.mark.asyncio
    async def test_find_similar_excludes_source(self, engine, mock_vectors):
        """Test that source document is excluded from results."""
        mock_vectors.search.return_value = [
            {"doc_id": "doc-1", "title": "Source Doc", "score": 1.0},
            {"doc_id": "doc-2", "title": "Similar Doc", "score": 0.85},
        ]

        results = await engine.find_similar("doc-1", limit=5)

        # Source doc should be filtered out
        doc_ids = [r.doc_id for r in results]
        assert "doc-1" not in doc_ids
        assert "doc-2" in doc_ids

    @pytest.mark.asyncio
    async def test_find_similar_no_vector(self, engine, mock_vectors):
        """Test find_similar when no vector exists."""
        mock_vectors.get_vector.return_value = None

        results = await engine.find_similar("doc-nonexistent")

        assert results == []
        mock_vectors.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_similar_with_min_similarity(self, engine, mock_vectors):
        """Test find_similar uses minimum similarity."""
        await engine.find_similar("doc-1", min_similarity=0.7)

        call_kwargs = mock_vectors.search.call_args[1]
        assert call_kwargs["score_threshold"] == 0.7


class TestSemanticSearchEngineBuildFilters:
    """Tests for SemanticSearchEngine._build_filters method."""

    @pytest.fixture
    def engine(self):
        """Create engine for filter testing."""
        return SemanticSearchEngine(vectors_service=MagicMock())

    def test_build_filters_empty(self, engine):
        """Test building filters from None."""
        result = engine._build_filters(None)
        assert result == {}

    def test_build_filters_date_range(self, engine):
        """Test building filters with date range."""
        filters = SearchFilters(
            date_range=DateRangeFilter(
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31),
            )
        )
        result = engine._build_filters(filters)
        assert "created_at_gte" in result
        assert "created_at_lte" in result

    def test_build_filters_entity_ids(self, engine):
        """Test building filters with entity IDs."""
        filters = SearchFilters(entity_ids=["ent-1", "ent-2"])
        result = engine._build_filters(filters)
        assert result["entity_ids"] == {"any": ["ent-1", "ent-2"]}

    def test_build_filters_project_ids(self, engine):
        """Test building filters with project IDs."""
        filters = SearchFilters(project_ids=["proj-1"])
        result = engine._build_filters(filters)
        assert result["project_ids"] == {"any": ["proj-1"]}

    def test_build_filters_file_types(self, engine):
        """Test building filters with file types."""
        filters = SearchFilters(file_types=["pdf", "docx"])
        result = engine._build_filters(filters)
        assert result["file_type"] == {"any": ["pdf", "docx"]}

    def test_build_filters_tags(self, engine):
        """Test building filters with tags."""
        filters = SearchFilters(tags=["important"])
        result = engine._build_filters(filters)
        assert result["tags"] == {"any": ["important"]}


class TestKeywordSearchEngineInit:
    """Tests for KeywordSearchEngine initialization."""

    def test_initialization_minimal(self):
        """Test engine initializes with just database service."""
        mock_db = MagicMock()
        engine = KeywordSearchEngine(database_service=mock_db)
        assert engine.db == mock_db
        assert engine.documents is None

    def test_initialization_with_documents(self):
        """Test engine initializes with documents service."""
        mock_db = MagicMock()
        mock_docs = MagicMock()
        engine = KeywordSearchEngine(
            database_service=mock_db,
            documents_service=mock_docs,
        )
        assert engine.db == mock_db
        assert engine.documents == mock_docs


class TestKeywordSearchEngineSearch:
    """Tests for KeywordSearchEngine.search method."""

    @pytest.fixture
    def engine(self):
        """Create engine with mock DB."""
        return KeywordSearchEngine(database_service=MagicMock())

    @pytest.mark.asyncio
    async def test_search_returns_list(self, engine):
        """Test search returns a list."""
        query = SearchQuery(query="test", mode=SearchMode.KEYWORD)
        results = await engine.search(query)
        assert isinstance(results, list)


class TestKeywordSearchEngineSuggest:
    """Tests for KeywordSearchEngine.suggest method."""

    @pytest.fixture
    def engine(self):
        """Create engine with mock DB."""
        return KeywordSearchEngine(database_service=MagicMock())

    @pytest.mark.asyncio
    async def test_suggest_returns_list(self, engine):
        """Test suggest returns a list."""
        suggestions = await engine.suggest("test", limit=5)
        assert isinstance(suggestions, list)


class TestKeywordSearchEngineExtractHighlights:
    """Tests for KeywordSearchEngine._extract_highlights method."""

    @pytest.fixture
    def engine(self):
        """Create engine for highlight testing."""
        return KeywordSearchEngine(database_service=MagicMock())

    def test_extract_highlights_single_match(self, engine):
        """Test extracting single highlight."""
        text = "This is a test of the emergency broadcast system."
        highlights = engine._extract_highlights(text, "test")
        assert len(highlights) == 1
        assert "test" in highlights[0].lower()

    def test_extract_highlights_multiple_matches(self, engine):
        """Test extracting multiple highlights."""
        text = "Test one. Test two. Test three. Test four."
        highlights = engine._extract_highlights(text, "test", max_highlights=3)
        assert len(highlights) == 3

    def test_extract_highlights_no_match(self, engine):
        """Test extracting when no match exists."""
        text = "This is some text without the query word."
        highlights = engine._extract_highlights(text, "nonexistent")
        assert highlights == []

    def test_extract_highlights_case_insensitive(self, engine):
        """Test highlight extraction is case insensitive."""
        text = "This is a TEST of the system."
        highlights = engine._extract_highlights(text, "test")
        assert len(highlights) == 1

    def test_extract_highlights_with_ellipsis(self, engine):
        """Test highlights include ellipsis for truncation."""
        text = "A" * 100 + "test" + "B" * 100
        highlights = engine._extract_highlights(text, "test")
        assert len(highlights) == 1
        assert "..." in highlights[0]


class TestKeywordSearchEngineBuildWhereClause:
    """Tests for KeywordSearchEngine._build_where_clause method."""

    @pytest.fixture
    def engine(self):
        """Create engine for where clause testing."""
        return KeywordSearchEngine(database_service=MagicMock())

    def test_build_where_empty(self, engine):
        """Test building where clause from None."""
        clause, params = engine._build_where_clause(None)
        assert clause == ""
        assert params == []

    def test_build_where_date_range(self, engine):
        """Test building where clause with date range."""
        filters = SearchFilters(
            date_range=DateRangeFilter(
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31),
            )
        )
        clause, params = engine._build_where_clause(filters)
        assert "created_at >=" in clause
        assert "created_at <=" in clause
        assert len(params) == 2

    def test_build_where_project_ids(self, engine):
        """Test building where clause with project IDs."""
        filters = SearchFilters(project_ids=["proj-1", "proj-2"])
        clause, params = engine._build_where_clause(filters)
        assert "project_id = ANY" in clause
        assert ["proj-1", "proj-2"] in params

    def test_build_where_file_types(self, engine):
        """Test building where clause with file types."""
        filters = SearchFilters(file_types=["pdf"])
        clause, params = engine._build_where_clause(filters)
        assert "file_type = ANY" in clause


class TestHybridSearchEngineInit:
    """Tests for HybridSearchEngine initialization."""

    def test_initialization(self):
        """Test engine initializes with both engines."""
        mock_semantic = MagicMock()
        mock_keyword = MagicMock()
        engine = HybridSearchEngine(
            semantic_engine=mock_semantic,
            keyword_engine=mock_keyword,
        )
        assert engine.semantic == mock_semantic
        assert engine.keyword == mock_keyword


class TestHybridSearchEngineSearch:
    """Tests for HybridSearchEngine.search method."""

    @pytest.fixture
    def mock_semantic(self):
        """Create mock semantic engine."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_keyword(self):
        """Create mock keyword engine."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def engine(self, mock_semantic, mock_keyword):
        """Create hybrid engine with mocks."""
        return HybridSearchEngine(
            semantic_engine=mock_semantic,
            keyword_engine=mock_keyword,
        )

    @pytest.mark.asyncio
    async def test_search_calls_both_engines(self, engine, mock_semantic, mock_keyword):
        """Test search calls both semantic and keyword engines."""
        query = SearchQuery(query="test", mode=SearchMode.HYBRID)
        await engine.search(query)

        mock_semantic.search.assert_called_once()
        mock_keyword.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_merges_results(self, engine, mock_semantic, mock_keyword):
        """Test search merges results from both engines."""
        mock_semantic.search.return_value = [
            SearchResultItem(doc_id="doc-1", chunk_id=None, title="Semantic", excerpt="...", score=0.9),
        ]
        mock_keyword.search.return_value = [
            SearchResultItem(doc_id="doc-2", chunk_id=None, title="Keyword", excerpt="...", score=0.8),
        ]

        query = SearchQuery(query="test", mode=SearchMode.HYBRID, limit=10)
        results = await engine.search(query)

        assert len(results) == 2
        doc_ids = [r.doc_id for r in results]
        assert "doc-1" in doc_ids
        assert "doc-2" in doc_ids

    @pytest.mark.asyncio
    async def test_search_deduplicates_results(self, engine, mock_semantic, mock_keyword):
        """Test search deduplicates overlapping results."""
        mock_semantic.search.return_value = [
            SearchResultItem(doc_id="doc-1", chunk_id="chunk-1", title="Same", excerpt="...", score=0.9),
        ]
        mock_keyword.search.return_value = [
            SearchResultItem(doc_id="doc-1", chunk_id="chunk-1", title="Same", excerpt="...", score=0.8),
        ]

        query = SearchQuery(query="test", mode=SearchMode.HYBRID)
        results = await engine.search(query)

        # Should be deduplicated to 1 result
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_applies_pagination(self, engine, mock_semantic, mock_keyword):
        """Test search applies offset and limit."""
        # Create many results
        mock_semantic.search.return_value = [
            SearchResultItem(doc_id=f"sem-{i}", chunk_id=None, title=f"Sem {i}", excerpt="...", score=0.9-i*0.1)
            for i in range(5)
        ]
        mock_keyword.search.return_value = [
            SearchResultItem(doc_id=f"kw-{i}", chunk_id=None, title=f"KW {i}", excerpt="...", score=0.8-i*0.1)
            for i in range(5)
        ]

        query = SearchQuery(query="test", mode=SearchMode.HYBRID, limit=3, offset=2)
        results = await engine.search(query)

        assert len(results) <= 3


class TestHybridSearchEngineMergeResults:
    """Tests for HybridSearchEngine._merge_results method."""

    @pytest.fixture
    def engine(self):
        """Create engine for merge testing."""
        return HybridSearchEngine(
            semantic_engine=MagicMock(),
            keyword_engine=MagicMock(),
        )

    def test_merge_empty_results(self, engine):
        """Test merging empty results."""
        merged = engine._merge_results([], [])
        assert merged == []

    def test_merge_semantic_only(self, engine):
        """Test merging with only semantic results."""
        semantic = [
            SearchResultItem(doc_id="doc-1", chunk_id=None, title="S1", excerpt="...", score=0.9),
        ]
        merged = engine._merge_results(semantic, [])
        assert len(merged) == 1
        assert merged[0].doc_id == "doc-1"

    def test_merge_keyword_only(self, engine):
        """Test merging with only keyword results."""
        keyword = [
            SearchResultItem(doc_id="doc-1", chunk_id=None, title="K1", excerpt="...", score=0.8),
        ]
        merged = engine._merge_results([], keyword)
        assert len(merged) == 1
        assert merged[0].doc_id == "doc-1"

    def test_merge_with_weights(self, engine):
        """Test merging respects weights."""
        semantic = [
            SearchResultItem(doc_id="doc-1", chunk_id=None, title="S", excerpt="...", score=0.9),
        ]
        keyword = [
            SearchResultItem(doc_id="doc-2", chunk_id=None, title="K", excerpt="...", score=0.9),
        ]

        # With semantic_weight=0.9, semantic results should rank higher
        merged = engine._merge_results(semantic, keyword, semantic_weight=0.9, keyword_weight=0.1)

        assert merged[0].doc_id == "doc-1"

    def test_merge_normalizes_weights(self, engine):
        """Test merge normalizes weights."""
        semantic = [
            SearchResultItem(doc_id="doc-1", chunk_id=None, title="S", excerpt="...", score=0.9),
        ]
        # Even with unnormalized weights, should work
        merged = engine._merge_results(semantic, [], semantic_weight=2.0, keyword_weight=1.0)
        assert len(merged) == 1


class TestHybridSearchEngineNormalizeScores:
    """Tests for HybridSearchEngine._normalize_scores method."""

    @pytest.fixture
    def engine(self):
        """Create engine for normalization testing."""
        return HybridSearchEngine(
            semantic_engine=MagicMock(),
            keyword_engine=MagicMock(),
        )

    def test_normalize_empty_list(self, engine):
        """Test normalizing empty list."""
        result = engine._normalize_scores([])
        assert result == []

    def test_normalize_single_result(self, engine):
        """Test normalizing single result."""
        results = [
            SearchResultItem(doc_id="doc-1", chunk_id=None, title="D1", excerpt="...", score=0.5),
        ]
        normalized = engine._normalize_scores(results)
        assert normalized[0].score == 1.0  # Single result gets 1.0

    def test_normalize_multiple_results(self, engine):
        """Test normalizing multiple results."""
        results = [
            SearchResultItem(doc_id="doc-1", chunk_id=None, title="D1", excerpt="...", score=0.2),
            SearchResultItem(doc_id="doc-2", chunk_id=None, title="D2", excerpt="...", score=0.8),
        ]
        normalized = engine._normalize_scores(results)

        # Lowest should be 0.0, highest should be 1.0
        scores = sorted([r.score for r in normalized])
        assert scores[0] == 0.0
        assert scores[1] == 1.0

    def test_normalize_same_scores(self, engine):
        """Test normalizing when all scores are the same."""
        results = [
            SearchResultItem(doc_id="doc-1", chunk_id=None, title="D1", excerpt="...", score=0.5),
            SearchResultItem(doc_id="doc-2", chunk_id=None, title="D2", excerpt="...", score=0.5),
        ]
        normalized = engine._normalize_scores(results)

        # All should be 1.0 when scores are equal
        assert all(r.score == 1.0 for r in normalized)
