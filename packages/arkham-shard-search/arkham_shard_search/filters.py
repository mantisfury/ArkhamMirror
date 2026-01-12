"""Filter utilities for search."""

import logging
from datetime import datetime
from typing import Any

from .models import SearchFilters, DateRangeFilter

logger = logging.getLogger(__name__)


class FilterBuilder:
    """Build search filters from various sources."""

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SearchFilters:
        """
        Build SearchFilters from dictionary.

        Args:
            data: Dictionary with filter parameters

        Returns:
            SearchFilters object
        """
        filters = SearchFilters()

        # Date range
        if "date_range" in data and data["date_range"]:
            dr = data["date_range"]
            filters.date_range = DateRangeFilter(
                start=datetime.fromisoformat(dr["start"]) if dr.get("start") else None,
                end=datetime.fromisoformat(dr["end"]) if dr.get("end") else None,
            )

        # Entity IDs
        if "entity_ids" in data and data["entity_ids"]:
            filters.entity_ids = data["entity_ids"]

        # Project IDs
        if "project_ids" in data and data["project_ids"]:
            filters.project_ids = data["project_ids"]

        # File types
        if "file_types" in data and data["file_types"]:
            filters.file_types = data["file_types"]

        # Tags
        if "tags" in data and data["tags"]:
            filters.tags = data["tags"]

        # Minimum score
        if "min_score" in data:
            filters.min_score = float(data["min_score"])

        return filters

    @staticmethod
    def validate(filters: SearchFilters) -> tuple[bool, str]:
        """
        Validate search filters.

        Args:
            filters: SearchFilters to validate

        Returns:
            (is_valid, error_message) tuple
        """
        # Date range validation
        if filters.date_range:
            if filters.date_range.start and filters.date_range.end:
                if filters.date_range.start > filters.date_range.end:
                    return False, "Start date must be before end date"

        # Score validation
        if filters.min_score < 0.0 or filters.min_score > 1.0:
            return False, "Minimum score must be between 0.0 and 1.0"

        return True, ""


class FilterOptimizer:
    """Optimize filter application for performance."""

    def __init__(self, database_service):
        """
        Initialize filter optimizer.

        Args:
            database_service: Database service for statistics
        """
        self.db = database_service

    async def get_available_filters(self, query: str | None = None) -> dict[str, Any]:
        """
        Get available filter options based on current query.

        Args:
            query: Optional search query to scope filters

        Returns:
            Dictionary of available filter values with counts
        """
        from datetime import timedelta

        result = {
            "file_types": [],
            "entities": [],
            "projects": [],
            "date_ranges": {
                "last_week": {"start": None, "end": None, "count": 0},
                "last_month": {"start": None, "end": None, "count": 0},
                "last_year": {"start": None, "end": None, "count": 0},
            },
        }

        if not self.db:
            return result

        try:
            # Get file type aggregations
            file_type_rows = await self.db.fetch_all(
                """
                SELECT mime_type as type, COUNT(*) as count
                FROM arkham_frame.documents
                WHERE mime_type IS NOT NULL
                GROUP BY mime_type
                ORDER BY count DESC
                LIMIT 20
                """
            )
            result["file_types"] = [
                {"type": row["type"], "count": row["count"]}
                for row in file_type_rows
            ]

            # Get project aggregations
            try:
                project_rows = await self.db.fetch_all(
                    """
                    SELECT p.id, p.name, COUNT(DISTINCT dp.document_id) as count
                    FROM arkham_frame.projects p
                    LEFT JOIN arkham_frame.document_projects dp ON p.id = dp.project_id
                    GROUP BY p.id, p.name
                    ORDER BY count DESC
                    LIMIT 20
                    """
                )
                result["projects"] = [
                    {"id": row["id"], "name": row["name"], "count": row["count"]}
                    for row in project_rows
                ]
            except Exception as e:
                logger.debug(f"Could not fetch project aggregations: {e}")

            # Get date range counts
            now = datetime.utcnow()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            year_ago = now - timedelta(days=365)

            # Last week count
            week_result = await self.db.fetch_one(
                """
                SELECT COUNT(*) as count FROM arkham_frame.documents
                WHERE created_at >= :start_date
                """,
                {"start_date": week_ago}
            )
            result["date_ranges"]["last_week"] = {
                "start": week_ago.isoformat(),
                "end": now.isoformat(),
                "count": week_result["count"] if week_result else 0,
            }

            # Last month count
            month_result = await self.db.fetch_one(
                """
                SELECT COUNT(*) as count FROM arkham_frame.documents
                WHERE created_at >= :start_date
                """,
                {"start_date": month_ago}
            )
            result["date_ranges"]["last_month"] = {
                "start": month_ago.isoformat(),
                "end": now.isoformat(),
                "count": month_result["count"] if month_result else 0,
            }

            # Last year count
            year_result = await self.db.fetch_one(
                """
                SELECT COUNT(*) as count FROM arkham_frame.documents
                WHERE created_at >= :start_date
                """,
                {"start_date": year_ago}
            )
            result["date_ranges"]["last_year"] = {
                "start": year_ago.isoformat(),
                "end": now.isoformat(),
                "count": year_result["count"] if year_result else 0,
            }

            # Get top entities (most mentioned)
            try:
                entity_rows = await self.db.fetch_all(
                    """
                    SELECT e.id, e.name, e.entity_type, COUNT(DISTINCT em.document_id) as count
                    FROM arkham_entities e
                    LEFT JOIN arkham_entity_mentions em ON e.id = em.entity_id
                    GROUP BY e.id, e.name, e.entity_type
                    ORDER BY count DESC
                    LIMIT 20
                    """
                )
                result["entities"] = [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "type": row["entity_type"],
                        "count": row["count"],
                    }
                    for row in entity_rows
                ]
            except Exception as e:
                # Entities table may not exist
                logger.debug(f"Could not fetch entity aggregations: {e}")

        except Exception as e:
            logger.warning(f"Failed to get filter aggregations: {e}")

        return result

    def apply_filters(self, results: list, filters: SearchFilters) -> list:
        """
        Apply filters to results (post-search filtering).

        Args:
            results: List of search results
            filters: Filters to apply

        Returns:
            Filtered results
        """
        if not filters:
            return results

        filtered = results

        # Apply minimum score filter
        if filters.min_score > 0.0:
            filtered = [r for r in filtered if r.score >= filters.min_score]

        return filtered
