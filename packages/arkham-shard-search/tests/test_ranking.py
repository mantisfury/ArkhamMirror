"""
Search Shard - Ranking Tests

Tests for ResultRanker and DiversityRanker classes.
"""

import pytest
from datetime import datetime, timedelta

from arkham_shard_search.ranking import ResultRanker, DiversityRanker
from arkham_shard_search.models import SearchResultItem, SortBy, SortOrder


class TestResultRankerSort:
    """Tests for ResultRanker.sort method."""

    @pytest.fixture
    def sample_results(self):
        """Create sample search results for testing."""
        return [
            SearchResultItem(
                doc_id="doc-1",
                chunk_id=None,
                title="Zebra Document",
                excerpt="...",
                score=0.5,
                created_at=datetime(2024, 1, 15),
            ),
            SearchResultItem(
                doc_id="doc-2",
                chunk_id=None,
                title="Alpha Document",
                excerpt="...",
                score=0.9,
                created_at=datetime(2024, 6, 15),
            ),
            SearchResultItem(
                doc_id="doc-3",
                chunk_id=None,
                title="Middle Document",
                excerpt="...",
                score=0.7,
                created_at=datetime(2024, 3, 15),
            ),
        ]

    def test_sort_by_relevance_desc(self, sample_results):
        """Test sorting by relevance descending."""
        sorted_results = ResultRanker.sort(
            sample_results,
            sort_by=SortBy.RELEVANCE,
            sort_order=SortOrder.DESC,
        )
        scores = [r.score for r in sorted_results]
        assert scores == [0.9, 0.7, 0.5]

    def test_sort_by_relevance_asc(self, sample_results):
        """Test sorting by relevance ascending."""
        sorted_results = ResultRanker.sort(
            sample_results,
            sort_by=SortBy.RELEVANCE,
            sort_order=SortOrder.ASC,
        )
        scores = [r.score for r in sorted_results]
        assert scores == [0.5, 0.7, 0.9]

    def test_sort_by_date_desc(self, sample_results):
        """Test sorting by date descending (newest first)."""
        sorted_results = ResultRanker.sort(
            sample_results,
            sort_by=SortBy.DATE,
            sort_order=SortOrder.DESC,
        )
        doc_ids = [r.doc_id for r in sorted_results]
        assert doc_ids == ["doc-2", "doc-3", "doc-1"]  # Jun, Mar, Jan

    def test_sort_by_date_asc(self, sample_results):
        """Test sorting by date ascending (oldest first)."""
        sorted_results = ResultRanker.sort(
            sample_results,
            sort_by=SortBy.DATE,
            sort_order=SortOrder.ASC,
        )
        doc_ids = [r.doc_id for r in sorted_results]
        assert doc_ids == ["doc-1", "doc-3", "doc-2"]  # Jan, Mar, Jun

    def test_sort_by_title_desc(self, sample_results):
        """Test sorting by title descending."""
        sorted_results = ResultRanker.sort(
            sample_results,
            sort_by=SortBy.TITLE,
            sort_order=SortOrder.DESC,
        )
        titles = [r.title for r in sorted_results]
        assert titles[0] == "Zebra Document"
        assert titles[-1] == "Alpha Document"

    def test_sort_by_title_asc(self, sample_results):
        """Test sorting by title ascending."""
        sorted_results = ResultRanker.sort(
            sample_results,
            sort_by=SortBy.TITLE,
            sort_order=SortOrder.ASC,
        )
        titles = [r.title for r in sorted_results]
        assert titles[0] == "Alpha Document"
        assert titles[-1] == "Zebra Document"

    def test_sort_empty_list(self):
        """Test sorting empty list."""
        sorted_results = ResultRanker.sort([])
        assert sorted_results == []


class TestResultRankerRerankByEntities:
    """Tests for ResultRanker.rerank_by_entities method."""

    @pytest.fixture
    def entity_results(self):
        """Create results with entity data."""
        return [
            SearchResultItem(
                doc_id="doc-1",
                chunk_id=None,
                title="Doc 1",
                excerpt="...",
                score=0.5,
                entities=["ent-1", "ent-2"],
            ),
            SearchResultItem(
                doc_id="doc-2",
                chunk_id=None,
                title="Doc 2",
                excerpt="...",
                score=0.8,
                entities=["ent-3"],
            ),
            SearchResultItem(
                doc_id="doc-3",
                chunk_id=None,
                title="Doc 3",
                excerpt="...",
                score=0.6,
                entities=["ent-1", "ent-3"],
            ),
        ]

    def test_rerank_with_priority_entities(self, entity_results):
        """Test reranking boosts results with priority entities."""
        reranked = ResultRanker.rerank_by_entities(
            entity_results,
            priority_entities=["ent-1"],
            boost=0.2,
        )
        # doc-1 has ent-1 (boost), doc-3 has ent-1 (boost), doc-2 has no match
        # After boosting: doc-1: 0.5 * 1.2 = 0.6, doc-3: 0.6 * 1.2 = 0.72
        assert reranked[0].doc_id == "doc-2"  # 0.8 (no boost but highest base)
        assert reranked[1].doc_id == "doc-3"  # 0.72 (boosted)

    def test_rerank_with_multiple_matches(self, entity_results):
        """Test reranking with multiple entity matches."""
        reranked = ResultRanker.rerank_by_entities(
            entity_results,
            priority_entities=["ent-1", "ent-2"],
            boost=0.2,
        )
        # doc-1 has 2 matches (ent-1, ent-2): 0.5 * 1.4 = 0.7
        # doc-3 has 1 match (ent-1): 0.6 * 1.2 = 0.72
        assert reranked[0].doc_id == "doc-2"  # 0.8

    def test_rerank_no_priority_entities(self, entity_results):
        """Test reranking with no priority entities returns unchanged order."""
        original_order = [r.doc_id for r in entity_results]
        reranked = ResultRanker.rerank_by_entities(entity_results, [])
        # Order unchanged when sorted by score descending
        assert reranked == entity_results

    def test_rerank_empty_results(self):
        """Test reranking empty results."""
        reranked = ResultRanker.rerank_by_entities([], ["ent-1"])
        assert reranked == []


class TestResultRankerRerankByRecency:
    """Tests for ResultRanker.rerank_by_recency method."""

    @pytest.fixture
    def dated_results(self):
        """Create results with dates for recency testing."""
        now = datetime.now()
        return [
            SearchResultItem(
                doc_id="doc-old",
                chunk_id=None,
                title="Old Doc",
                excerpt="...",
                score=0.9,
                created_at=now - timedelta(days=100),
            ),
            SearchResultItem(
                doc_id="doc-new",
                chunk_id=None,
                title="New Doc",
                excerpt="...",
                score=0.5,
                created_at=now,
            ),
            SearchResultItem(
                doc_id="doc-mid",
                chunk_id=None,
                title="Mid Doc",
                excerpt="...",
                score=0.7,
                created_at=now - timedelta(days=30),
            ),
        ]

    def test_rerank_by_recency_boosts_new(self, dated_results):
        """Test recency reranking boosts newer documents."""
        reranked = ResultRanker.rerank_by_recency(dated_results, decay_factor=0.5)
        # Newer documents should rank higher after recency boost
        # doc-new is most recent, so it should be boosted
        assert reranked[0].doc_id == "doc-new"

    def test_rerank_zero_decay_no_change(self, dated_results):
        """Test zero decay factor returns results unchanged."""
        original_order = [r.doc_id for r in dated_results]
        reranked = ResultRanker.rerank_by_recency(dated_results, decay_factor=0.0)
        # With 0 decay, the function returns early without re-sorting
        new_order = [r.doc_id for r in reranked]
        assert new_order == original_order

    def test_rerank_no_dates(self):
        """Test reranking results with no dates."""
        results = [
            SearchResultItem(
                doc_id="doc-1",
                chunk_id=None,
                title="Doc 1",
                excerpt="...",
                score=0.9,
            ),
        ]
        reranked = ResultRanker.rerank_by_recency(results, decay_factor=0.5)
        assert len(reranked) == 1

    def test_rerank_empty_results(self):
        """Test reranking empty results."""
        reranked = ResultRanker.rerank_by_recency([], decay_factor=0.5)
        assert reranked == []


class TestResultRankerDeduplicate:
    """Tests for ResultRanker.deduplicate method."""

    @pytest.fixture
    def duplicate_results(self):
        """Create results with duplicates."""
        return [
            SearchResultItem(
                doc_id="doc-1",
                chunk_id="chunk-a",
                title="Doc 1",
                excerpt="...",
                score=0.9,
            ),
            SearchResultItem(
                doc_id="doc-1",
                chunk_id="chunk-b",
                title="Doc 1",
                excerpt="...",
                score=0.7,
            ),
            SearchResultItem(
                doc_id="doc-2",
                chunk_id="chunk-c",
                title="Doc 2",
                excerpt="...",
                score=0.8,
            ),
        ]

    def test_deduplicate_by_doc_id(self, duplicate_results):
        """Test deduplication by doc_id keeps highest score."""
        deduped = ResultRanker.deduplicate(duplicate_results, by_field="doc_id")
        assert len(deduped) == 2
        # doc-1 should have score 0.9 (highest)
        doc1 = next(r for r in deduped if r.doc_id == "doc-1")
        assert doc1.score == 0.9

    def test_deduplicate_by_title(self, duplicate_results):
        """Test deduplication by title."""
        deduped = ResultRanker.deduplicate(duplicate_results, by_field="title")
        assert len(deduped) == 2

    def test_deduplicate_no_duplicates(self):
        """Test deduplication with no duplicates."""
        results = [
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
                score=0.8,
            ),
        ]
        deduped = ResultRanker.deduplicate(results)
        assert len(deduped) == 2

    def test_deduplicate_empty_list(self):
        """Test deduplication of empty list."""
        deduped = ResultRanker.deduplicate([])
        assert deduped == []


class TestResultRankerBoostExactMatches:
    """Tests for ResultRanker.boost_exact_matches method."""

    @pytest.fixture
    def query_results(self):
        """Create results for exact match testing."""
        return [
            SearchResultItem(
                doc_id="doc-1",
                chunk_id=None,
                title="Machine Learning Guide",
                excerpt="Introduction to algorithms.",
                score=0.5,
            ),
            SearchResultItem(
                doc_id="doc-2",
                chunk_id=None,
                title="Data Science",
                excerpt="Uses machine learning techniques.",
                score=0.7,
            ),
            SearchResultItem(
                doc_id="doc-3",
                chunk_id=None,
                title="Other Topic",
                excerpt="No match here.",
                score=0.8,
            ),
        ]

    def test_boost_title_match(self, query_results):
        """Test boosting results with query in title."""
        boosted = ResultRanker.boost_exact_matches(
            query_results,
            query="machine learning",
            boost=0.3,
        )
        # doc-1 has "Machine Learning" in title, should get full boost
        doc1 = next(r for r in boosted if r.doc_id == "doc-1")
        assert doc1.score == pytest.approx(0.5 * 1.3)

    def test_boost_excerpt_match(self, query_results):
        """Test boosting results with query in excerpt."""
        boosted = ResultRanker.boost_exact_matches(
            query_results,
            query="machine learning",
            boost=0.3,
        )
        # doc-2 has "machine learning" in excerpt, should get half boost
        doc2 = next(r for r in boosted if r.doc_id == "doc-2")
        assert doc2.score == pytest.approx(0.7 * 1.15)

    def test_no_boost_no_match(self, query_results):
        """Test no boost for results without match."""
        boosted = ResultRanker.boost_exact_matches(
            query_results,
            query="machine learning",
            boost=0.3,
        )
        # doc-3 has no match, score unchanged
        doc3 = next(r for r in boosted if r.doc_id == "doc-3")
        assert doc3.score == 0.8

    def test_boost_case_insensitive(self, query_results):
        """Test boost is case insensitive."""
        boosted = ResultRanker.boost_exact_matches(
            query_results,
            query="MACHINE LEARNING",
            boost=0.3,
        )
        doc1 = next(r for r in boosted if r.doc_id == "doc-1")
        assert doc1.score > 0.5  # Got boosted


class TestDiversityRanker:
    """Tests for DiversityRanker class."""

    @pytest.fixture
    def chunk_results(self):
        """Create results with multiple chunks per document."""
        return [
            SearchResultItem(doc_id="doc-1", chunk_id="chunk-1", title="D1", excerpt="...", score=0.95),
            SearchResultItem(doc_id="doc-1", chunk_id="chunk-2", title="D1", excerpt="...", score=0.90),
            SearchResultItem(doc_id="doc-1", chunk_id="chunk-3", title="D1", excerpt="...", score=0.85),
            SearchResultItem(doc_id="doc-1", chunk_id="chunk-4", title="D1", excerpt="...", score=0.80),
            SearchResultItem(doc_id="doc-2", chunk_id="chunk-5", title="D2", excerpt="...", score=0.75),
            SearchResultItem(doc_id="doc-2", chunk_id="chunk-6", title="D2", excerpt="...", score=0.70),
        ]

    def test_diversify_limits_per_source(self, chunk_results):
        """Test diversification limits results per document."""
        diversified = DiversityRanker.diversify_by_source(
            chunk_results,
            max_per_source=2,
        )
        # Should only have 2 from doc-1 and 2 from doc-2
        doc1_count = sum(1 for r in diversified if r.doc_id == "doc-1")
        doc2_count = sum(1 for r in diversified if r.doc_id == "doc-2")
        assert doc1_count == 2
        assert doc2_count == 2
        assert len(diversified) == 4

    def test_diversify_keeps_highest_scores(self, chunk_results):
        """Test diversification keeps highest scoring chunks."""
        diversified = DiversityRanker.diversify_by_source(
            chunk_results,
            max_per_source=2,
        )
        # First 2 from doc-1 should be chunk-1 (0.95) and chunk-2 (0.90)
        doc1_chunks = [r for r in diversified if r.doc_id == "doc-1"]
        assert doc1_chunks[0].chunk_id == "chunk-1"
        assert doc1_chunks[1].chunk_id == "chunk-2"

    def test_diversify_with_higher_limit(self, chunk_results):
        """Test diversification with high limit keeps all."""
        diversified = DiversityRanker.diversify_by_source(
            chunk_results,
            max_per_source=10,
        )
        assert len(diversified) == 6

    def test_diversify_empty_list(self):
        """Test diversification of empty list."""
        diversified = DiversityRanker.diversify_by_source([], max_per_source=2)
        assert diversified == []

    def test_diversify_single_source(self):
        """Test diversification with single source."""
        results = [
            SearchResultItem(doc_id="doc-1", chunk_id=f"chunk-{i}", title="D1", excerpt="...", score=0.9-i*0.1)
            for i in range(5)
        ]
        diversified = DiversityRanker.diversify_by_source(results, max_per_source=3)
        assert len(diversified) == 3
