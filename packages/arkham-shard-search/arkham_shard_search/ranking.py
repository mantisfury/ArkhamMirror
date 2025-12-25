"""Result ranking and reranking utilities."""

import logging
from typing import Any, Callable

from .models import SearchResultItem, SortBy, SortOrder

logger = logging.getLogger(__name__)


class ResultRanker:
    """Rank and rerank search results."""

    @staticmethod
    def sort(
        results: list[SearchResultItem],
        sort_by: SortBy = SortBy.RELEVANCE,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> list[SearchResultItem]:
        """
        Sort search results.

        Args:
            results: List of search results
            sort_by: Sort field
            sort_order: Sort order (ASC/DESC)

        Returns:
            Sorted results
        """
        reverse = (sort_order == SortOrder.DESC)

        if sort_by == SortBy.RELEVANCE:
            key_func = lambda x: x.score
        elif sort_by == SortBy.DATE:
            key_func = lambda x: x.created_at or ""
        elif sort_by == SortBy.TITLE:
            key_func = lambda x: x.title.lower()
        else:
            key_func = lambda x: x.score

        return sorted(results, key=key_func, reverse=reverse)

    @staticmethod
    def rerank_by_entities(
        results: list[SearchResultItem],
        priority_entities: list[str],
        boost: float = 0.2,
    ) -> list[SearchResultItem]:
        """
        Rerank results by entity presence.

        Boosts results that contain priority entities.

        Args:
            results: List of search results
            priority_entities: Entity IDs to prioritize
            boost: Score boost multiplier (e.g., 0.2 = 20% boost)

        Returns:
            Reranked results
        """
        if not priority_entities:
            return results

        priority_set = set(priority_entities)

        for result in results:
            result_entities = set(result.entities)
            matches = len(priority_set & result_entities)

            if matches > 0:
                # Boost score based on number of matching entities
                result.score *= (1.0 + boost * matches)

        return sorted(results, key=lambda x: x.score, reverse=True)

    @staticmethod
    def rerank_by_recency(
        results: list[SearchResultItem],
        decay_factor: float = 0.5,
    ) -> list[SearchResultItem]:
        """
        Rerank results by recency.

        More recent documents get higher scores.

        Args:
            results: List of search results
            decay_factor: How much to weight recency (0.0-1.0)

        Returns:
            Reranked results
        """
        if decay_factor <= 0.0:
            return results

        # Find newest document
        newest = max(
            (r.created_at for r in results if r.created_at),
            default=None,
        )

        if not newest:
            return results

        for result in results:
            if not result.created_at:
                continue

            # Calculate age in days
            age_days = (newest - result.created_at).days

            # Apply exponential decay
            recency_score = 1.0 / (1.0 + age_days * 0.1)

            # Blend with original score
            result.score = (
                result.score * (1.0 - decay_factor) +
                recency_score * decay_factor
            )

        return sorted(results, key=lambda x: x.score, reverse=True)

    @staticmethod
    def deduplicate(
        results: list[SearchResultItem],
        by_field: str = "doc_id",
    ) -> list[SearchResultItem]:
        """
        Remove duplicate results.

        Keeps the highest-scoring result for each duplicate group.

        Args:
            results: List of search results
            by_field: Field to deduplicate by (doc_id, title, etc.)

        Returns:
            Deduplicated results
        """
        seen = {}

        for result in results:
            key = getattr(result, by_field, None)
            if key is None:
                continue

            if key not in seen or result.score > seen[key].score:
                seen[key] = result

        return sorted(seen.values(), key=lambda x: x.score, reverse=True)

    @staticmethod
    def boost_exact_matches(
        results: list[SearchResultItem],
        query: str,
        boost: float = 0.3,
    ) -> list[SearchResultItem]:
        """
        Boost results with exact query matches.

        Args:
            results: List of search results
            query: Original search query
            boost: Score boost for exact matches

        Returns:
            Boosted results
        """
        query_lower = query.lower()

        for result in results:
            # Check title for exact match
            if query_lower in result.title.lower():
                result.score *= (1.0 + boost)

            # Check excerpt for exact match
            elif query_lower in result.excerpt.lower():
                result.score *= (1.0 + boost * 0.5)  # Smaller boost for excerpt

        return sorted(results, key=lambda x: x.score, reverse=True)


class DiversityRanker:
    """Promote diversity in search results."""

    @staticmethod
    def diversify_by_source(
        results: list[SearchResultItem],
        max_per_source: int = 3,
    ) -> list[SearchResultItem]:
        """
        Limit results per document source.

        Prevents one document from dominating results.

        Args:
            results: List of search results
            max_per_source: Maximum results per document

        Returns:
            Diversified results
        """
        source_counts = {}
        diversified = []

        for result in results:
            doc_id = result.doc_id
            count = source_counts.get(doc_id, 0)

            if count < max_per_source:
                diversified.append(result)
                source_counts[doc_id] = count + 1

        return diversified
