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
        # TODO: Query database for filter statistics
        # Return counts for each filter option

        return {
            "file_types": [],  # [{"type": "pdf", "count": 42}, ...]
            "entities": [],    # [{"id": "ent123", "name": "John Doe", "count": 5}, ...]
            "projects": [],    # [{"id": "proj1", "name": "Investigation A", "count": 10}, ...]
            "date_ranges": {   # Pre-computed ranges
                "last_week": {"start": None, "end": None, "count": 0},
                "last_month": {"start": None, "end": None, "count": 0},
                "last_year": {"start": None, "end": None, "count": 0},
            },
        }

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
