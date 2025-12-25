"""Hybrid search combining semantic and keyword search."""

import logging
from typing import Any

from ..models import SearchQuery, SearchResultItem
from .semantic import SemanticSearchEngine
from .keyword import KeywordSearchEngine

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    Hybrid search combining semantic and keyword search.

    Merges results from both engines with configurable weights.
    """

    def __init__(self, semantic_engine: SemanticSearchEngine, keyword_engine: KeywordSearchEngine):
        """
        Initialize hybrid search engine.

        Args:
            semantic_engine: Semantic search engine
            keyword_engine: Keyword search engine
        """
        self.semantic = semantic_engine
        self.keyword = keyword_engine

    async def search(self, query: SearchQuery) -> list[SearchResultItem]:
        """
        Perform hybrid search.

        Args:
            query: SearchQuery object

        Returns:
            List of SearchResultItem, merged and reranked
        """
        logger.info(f"Hybrid search: '{query.query}' (semantic={query.semantic_weight}, keyword={query.keyword_weight})")

        # Fetch more results from each engine to allow for better merging
        extended_limit = query.limit * 2
        extended_query = SearchQuery(
            query=query.query,
            mode=query.mode,
            filters=query.filters,
            limit=extended_limit,
            offset=0,  # Always start at 0 for merging
            sort_by=query.sort_by,
            sort_order=query.sort_order,
        )

        # Execute both searches in parallel
        semantic_results = await self.semantic.search(extended_query)
        keyword_results = await self.keyword.search(extended_query)

        # Merge and rerank results
        merged = self._merge_results(
            semantic_results,
            keyword_results,
            semantic_weight=query.semantic_weight,
            keyword_weight=query.keyword_weight,
        )

        # Apply pagination
        start = query.offset
        end = start + query.limit

        return merged[start:end]

    def _merge_results(
        self,
        semantic_results: list[SearchResultItem],
        keyword_results: list[SearchResultItem],
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list[SearchResultItem]:
        """
        Merge results from semantic and keyword search.

        Uses Reciprocal Rank Fusion (RRF) algorithm with configurable weights.

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            semantic_weight: Weight for semantic scores (0.0-1.0)
            keyword_weight: Weight for keyword scores (0.0-1.0)

        Returns:
            Merged and reranked list of SearchResultItem
        """
        # Normalize weights
        total_weight = semantic_weight + keyword_weight
        if total_weight > 0:
            semantic_weight /= total_weight
            keyword_weight /= total_weight
        else:
            semantic_weight = 0.5
            keyword_weight = 0.5

        # Build result maps keyed by (doc_id, chunk_id)
        semantic_map = {}
        for rank, item in enumerate(semantic_results, 1):
            key = (item.doc_id, item.chunk_id)
            semantic_map[key] = (item, rank)

        keyword_map = {}
        for rank, item in enumerate(keyword_results, 1):
            key = (item.doc_id, item.chunk_id)
            keyword_map[key] = (item, rank)

        # Merge using RRF
        k = 60  # RRF constant
        merged_scores = {}
        all_keys = set(semantic_map.keys()) | set(keyword_map.keys())

        for key in all_keys:
            rrf_score = 0.0
            item = None

            # Add semantic contribution
            if key in semantic_map:
                sem_item, sem_rank = semantic_map[key]
                rrf_score += semantic_weight * (1.0 / (k + sem_rank))
                item = sem_item  # Prefer semantic item for metadata

            # Add keyword contribution
            if key in keyword_map:
                kw_item, kw_rank = keyword_map[key]
                rrf_score += keyword_weight * (1.0 / (k + kw_rank))

                # Merge highlights from keyword search
                if item and kw_item.highlights:
                    item.highlights.extend(kw_item.highlights)
                elif not item:
                    item = kw_item

            if item:
                # Update score with RRF score
                item.score = rrf_score
                merged_scores[key] = item

        # Sort by merged score
        sorted_items = sorted(
            merged_scores.values(),
            key=lambda x: x.score,
            reverse=True,
        )

        return sorted_items

    def _normalize_scores(self, results: list[SearchResultItem]) -> list[SearchResultItem]:
        """
        Normalize scores to 0.0-1.0 range using min-max normalization.

        Args:
            results: List of SearchResultItem

        Returns:
            Results with normalized scores
        """
        if not results:
            return results

        scores = [r.score for r in results]
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score

        if score_range == 0:
            # All scores are the same
            for r in results:
                r.score = 1.0
        else:
            for r in results:
                r.score = (r.score - min_score) / score_range

        return results
