"""Keyword search engine using full-text search."""

import logging
from typing import Any

from ..models import SearchQuery, SearchResultItem

logger = logging.getLogger(__name__)


class KeywordSearchEngine:
    """
    Keyword search using PostgreSQL full-text search.

    Performs text-based matching with ranking.
    """

    def __init__(self, database_service, documents_service=None):
        """
        Initialize keyword search engine.

        Args:
            database_service: PostgreSQL database service
            documents_service: Optional documents service for metadata
        """
        self.db = database_service
        self.documents = documents_service

    async def search(self, query: SearchQuery) -> list[SearchResultItem]:
        """
        Perform keyword search.

        Args:
            query: SearchQuery object

        Returns:
            List of SearchResultItem
        """
        logger.info(f"Keyword search: '{query.query}' (limit={query.limit})")

        # TODO: Perform PostgreSQL full-text search
        # Use ts_vector and ts_query for text search
        # Example SQL:
        # SELECT doc_id, chunk_id, title, text, ts_rank(ts_vector, query) as score
        # FROM chunks
        # WHERE ts_vector @@ to_tsquery(%s)
        # ORDER BY score DESC
        # LIMIT %s OFFSET %s

        # Mock implementation
        results = []

        search_items = []
        for result in results:
            # Extract highlights using ts_headline
            highlights = self._extract_highlights(result.get("text", ""), query.query)

            item = SearchResultItem(
                doc_id=result.get("doc_id", ""),
                chunk_id=result.get("chunk_id"),
                title=result.get("title", ""),
                excerpt=result.get("text", "")[:300],
                score=result.get("score", 0.0),
                file_type=result.get("file_type"),
                created_at=result.get("created_at"),
                page_number=result.get("page_number"),
                highlights=highlights,
                entities=result.get("entities", []),
                project_ids=result.get("project_ids", []),
                metadata=result.get("metadata", {}),
            )
            search_items.append(item)

        return search_items

    async def suggest(self, prefix: str, limit: int = 10) -> list[tuple[str, float]]:
        """
        Generate autocomplete suggestions.

        Args:
            prefix: Search prefix
            limit: Maximum suggestions

        Returns:
            List of (suggestion, score) tuples
        """
        logger.info(f"Autocomplete: '{prefix}' (limit={limit})")

        # TODO: Query database for suggestions
        # Could use:
        # - Document titles starting with prefix
        # - Entity names starting with prefix
        # - Common search terms

        # Mock implementation
        suggestions = []

        return suggestions

    def _extract_highlights(self, text: str, query: str, max_highlights: int = 3) -> list[str]:
        """
        Extract highlighted snippets from text.

        Args:
            text: Full text
            query: Search query
            max_highlights: Maximum number of highlights

        Returns:
            List of highlighted snippets
        """
        # TODO: Use PostgreSQL ts_headline or implement simple highlighting
        # For now, simple keyword matching

        highlights = []
        query_lower = query.lower()
        text_lower = text.lower()

        # Find occurrences
        pos = 0
        while len(highlights) < max_highlights:
            idx = text_lower.find(query_lower, pos)
            if idx == -1:
                break

            # Extract context around match
            start = max(0, idx - 50)
            end = min(len(text), idx + len(query) + 50)
            snippet = text[start:end]

            # Add ellipsis if needed
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."

            highlights.append(snippet)
            pos = idx + len(query)

        return highlights

    def _build_where_clause(self, filters) -> tuple[str, list[Any]]:
        """
        Build WHERE clause from SearchFilters.

        Args:
            filters: SearchFilters object

        Returns:
            (where_clause, params) tuple
        """
        if not filters:
            return "", []

        conditions = []
        params = []

        # Date range
        if filters.date_range:
            if filters.date_range.start:
                conditions.append("created_at >= %s")
                params.append(filters.date_range.start)
            if filters.date_range.end:
                conditions.append("created_at <= %s")
                params.append(filters.date_range.end)

        # Entity filter (assuming many-to-many relationship)
        if filters.entity_ids:
            conditions.append("EXISTS (SELECT 1 FROM document_entities WHERE document_id = doc_id AND entity_id = ANY(%s))")
            params.append(filters.entity_ids)

        # Project filter
        if filters.project_ids:
            conditions.append("project_id = ANY(%s)")
            params.append(filters.project_ids)

        # File type filter
        if filters.file_types:
            conditions.append("file_type = ANY(%s)")
            params.append(filters.file_types)

        # Tags filter (assuming array column)
        if filters.tags:
            conditions.append("tags && %s")
            params.append(filters.tags)

        # Minimum score (used in post-processing)

        where_clause = " AND ".join(conditions) if conditions else ""
        return where_clause, params
