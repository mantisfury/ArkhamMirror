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

        if not self.db:
            logger.warning("Database service not available")
            return []

        try:
            # Use ILIKE for simple keyword matching (case-insensitive)
            # Join with documents table to get metadata
            search_term = f"%{query.query}%"

            sql = """
                SELECT
                    c.id as chunk_id,
                    c.document_id,
                    c.text,
                    c.page_number,
                    c.chunk_index,
                    d.filename as title,
                    d.mime_type,
                    d.created_at
                FROM arkham_frame.chunks c
                LEFT JOIN arkham_frame.documents d ON c.document_id = d.id
                WHERE c.text ILIKE :search_term
                ORDER BY c.chunk_index
                LIMIT :limit OFFSET :offset
            """

            rows = await self.db.fetch_all(
                sql,
                {
                    "search_term": search_term,
                    "limit": query.limit,
                    "offset": query.offset if hasattr(query, 'offset') else 0,
                }
            )
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

        search_items = []
        for row in rows:
            text = row.get("text", "") or ""
            highlights = self._extract_highlights(text, query.query)

            # Calculate simple score based on keyword frequency
            query_lower = query.query.lower()
            text_lower = text.lower()
            occurrences = text_lower.count(query_lower)
            score = min(1.0, occurrences * 0.2)  # Cap at 1.0

            item = SearchResultItem(
                doc_id=row.get("document_id", ""),
                chunk_id=row.get("chunk_id"),
                title=row.get("title", ""),
                excerpt=text[:300] if text else "",
                score=score,
                file_type=row.get("mime_type"),
                created_at=row.get("created_at"),
                page_number=row.get("page_number"),
                highlights=highlights,
                entities=[],
                project_ids=[],
                metadata={},
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
