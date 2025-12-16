"""
Entity Deduplication State

State management for the entity deduplication page.
Handles both automatic suggestions and manual merge operations.
"""

import reflex as rx
import logging
from typing import List, Dict, Any, Optional
import asyncio

logger = logging.getLogger(__name__)


class EntityDedupState(rx.State):
    """State for entity deduplication page."""

    # Duplicate candidates
    candidates: List[Dict[str, Any]] = []
    filtered_candidates: List[Dict[str, Any]] = []

    # Statistics
    stats: Dict[str, Any] = {}

    # Filters
    label_filter: str = "all"
    min_similarity: float = 0.75
    show_auto_matches_only: bool = False

    # Selected pair for detailed view
    selected_pair: Optional[Dict[str, Any]] = None
    entity1_details: Optional[Dict[str, Any]] = None
    entity2_details: Optional[Dict[str, Any]] = None

    # UI state
    is_loading: bool = False
    error_message: str = ""
    success_message: str = ""

    # Pagination
    page: int = 0
    page_size: int = 20

    @rx.var
    def total_pages(self) -> int:
        """Calculate total pages."""
        if not self.filtered_candidates:
            return 0
        import math

        return math.ceil(len(self.filtered_candidates) / self.page_size)

    @rx.var
    def current_page_candidates(self) -> List[Dict[str, Any]]:
        """Get candidates for current page."""
        start = self.page * self.page_size
        end = start + self.page_size
        return self.filtered_candidates[start:end]

    @rx.var
    def available_labels(self) -> List[str]:
        """Get list of unique labels from candidates."""
        # Return all as default - label filtering handled on backend
        return ["all"]

    # Computed vars for entity 1 details
    @rx.var
    def entity1_canonical_name(self) -> str:
        """Get entity 1 canonical name."""
        return (
            self.entity1_details.get("canonical_name", "")
            if self.entity1_details
            else ""
        )

    @rx.var
    def entity1_label(self) -> str:
        """Get entity 1 label."""
        return self.entity1_details.get("label", "") if self.entity1_details else ""

    @rx.var
    def entity1_total_mentions(self) -> int:
        """Get entity 1 total mentions."""
        return (
            self.entity1_details.get("total_mentions", 0) if self.entity1_details else 0
        )

    @rx.var
    def entity1_document_count(self) -> int:
        """Get entity 1 document count."""
        return (
            self.entity1_details.get("document_count", 0) if self.entity1_details else 0
        )

    @rx.var
    def entity1_has_aliases(self) -> bool:
        """Check if entity 1 has aliases."""
        if not self.entity1_details:
            return False
        aliases = self.entity1_details.get("aliases", [])
        return len(aliases) > 0 if aliases else False

    @rx.var
    def entity1_has_mentions(self) -> bool:
        """Check if entity 1 has mention variations."""
        if not self.entity1_details:
            return False
        mentions = self.entity1_details.get("mention_texts", [])
        return len(mentions) > 0 if mentions else False

    @rx.var
    def entity1_has_location(self) -> bool:
        """Check if entity 1 has location."""
        if not self.entity1_details:
            return False
        return self.entity1_details.get("latitude") is not None

    @rx.var
    def entity1_location_text(self) -> str:
        """Get entity 1 location text."""
        if not self.entity1_details:
            return ""
        lat = self.entity1_details.get("latitude", 0)
        lon = self.entity1_details.get("longitude", 0)
        return f"{lat}, {lon}"

    @rx.var
    def entity1_resolved_address(self) -> str:
        """Get entity 1 resolved address."""
        if not self.entity1_details:
            return ""
        return self.entity1_details.get("resolved_address") or ""

    @rx.var
    def entity1_has_address(self) -> bool:
        """Check if entity 1 has resolved address."""
        if not self.entity1_details:
            return False
        addr = self.entity1_details.get("resolved_address")
        return addr is not None and addr != ""

    # Computed vars for entity 2 details
    @rx.var
    def entity2_canonical_name(self) -> str:
        """Get entity 2 canonical name."""
        return (
            self.entity2_details.get("canonical_name", "")
            if self.entity2_details
            else ""
        )

    @rx.var
    def entity2_label(self) -> str:
        """Get entity 2 label."""
        return self.entity2_details.get("label", "") if self.entity2_details else ""

    @rx.var
    def entity2_total_mentions(self) -> int:
        """Get entity 2 total mentions."""
        return (
            self.entity2_details.get("total_mentions", 0) if self.entity2_details else 0
        )

    @rx.var
    def entity2_document_count(self) -> int:
        """Get entity 2 document count."""
        return (
            self.entity2_details.get("document_count", 0) if self.entity2_details else 0
        )

    @rx.var
    def entity2_has_aliases(self) -> bool:
        """Check if entity 2 has aliases."""
        if not self.entity2_details:
            return False
        aliases = self.entity2_details.get("aliases", [])
        return len(aliases) > 0 if aliases else False

    @rx.var
    def entity2_has_mentions(self) -> bool:
        """Check if entity 2 has mention variations."""
        if not self.entity2_details:
            return False
        mentions = self.entity2_details.get("mention_texts", [])
        return len(mentions) > 0 if mentions else False

    @rx.var
    def entity2_has_location(self) -> bool:
        """Check if entity 2 has location."""
        if not self.entity2_details:
            return False
        return self.entity2_details.get("latitude") is not None

    @rx.var
    def entity2_location_text(self) -> str:
        """Get entity 2 location text."""
        if not self.entity2_details:
            return ""
        lat = self.entity2_details.get("latitude", 0)
        lon = self.entity2_details.get("longitude", 0)
        return f"{lat}, {lon}"

    @rx.var
    def entity2_resolved_address(self) -> str:
        """Get entity 2 resolved address."""
        if not self.entity2_details:
            return ""
        return self.entity2_details.get("resolved_address") or ""

    @rx.var
    def entity2_has_address(self) -> bool:
        """Check if entity 2 has resolved address."""
        if not self.entity2_details:
            return False
        addr = self.entity2_details.get("resolved_address")
        return addr is not None and addr != ""

    async def load_candidates(self):
        """Load duplicate candidates from the backend."""
        self.is_loading = True
        self.error_message = ""
        yield

        try:
            # Import here to avoid circular imports
            from ..services.entity_deduplication_service import get_duplicate_candidates

            # Get candidates
            label = None if self.label_filter == "all" else self.label_filter
            self.candidates = await asyncio.to_thread(
                get_duplicate_candidates,
                label_filter=label,
                min_similarity=self.min_similarity,
                limit=500,
            )

            # Apply filters
            self._apply_filters()

            # Reset page
            self.page = 0

        except Exception as e:
            self.error_message = f"Failed to load candidates: {str(e)}"
        finally:
            self.is_loading = False

    async def load_statistics(self):
        """Load deduplication statistics."""
        try:
            from ..services.entity_deduplication_service import get_deduplication_stats

            self.stats = await asyncio.to_thread(get_deduplication_stats)

        except Exception as e:
            self.error_message = f"Failed to load statistics: {str(e)}"

    def _apply_filters(self):
        """Apply filters to candidates."""
        filtered = self.candidates

        # Filter by auto-match
        if self.show_auto_matches_only:
            filtered = [c for c in filtered if c.get("is_auto_match", False)]

        self.filtered_candidates = filtered

    def set_label_filter(self, label: str):
        """Set label filter and reload."""
        self.label_filter = label
        return EntityDedupState.load_candidates

    def set_min_similarity(self, value: float):
        """Set minimum similarity threshold and reload."""
        self.min_similarity = value
        return EntityDedupState.load_candidates

    def toggle_auto_matches_only(self):
        """Toggle auto-matches filter."""
        self.show_auto_matches_only = not self.show_auto_matches_only
        self._apply_filters()
        self.page = 0

    def next_page(self):
        """Go to next page."""
        if self.page < self.total_pages - 1:
            self.page += 1

    def prev_page(self):
        """Go to previous page."""
        if self.page > 0:
            self.page -= 1

    async def select_pair(self, id1: int, id2: int):
        """Select a pair for detailed view."""
        self.is_loading = True
        self.error_message = ""

        # Clear previous details
        self.entity1_details = None
        self.entity2_details = None

        # Find the pair in candidates
        candidate = None
        for c in self.candidates:
            if c["id1"] == id1 and c["id2"] == id2:
                candidate = c
                break

        if not candidate:
            self.error_message = "Candidate pair not found"
            self.is_loading = False
            return

        self.selected_pair = candidate
        yield

        try:
            from ..services.entity_deduplication_service import get_entity_details

            # Load detailed information
            # Use asyncio.gather to load both in parallel
            d1, d2 = await asyncio.gather(
                asyncio.to_thread(get_entity_details, id1),
                asyncio.to_thread(get_entity_details, id2),
            )

            self.entity1_details = d1
            self.entity2_details = d2

            if not d1 or not d2:
                self.error_message = "Failed to load details for one or both entities"
                # Keep modal open so user can see empty state? No, better to close or show error.
                # If we close, user sees error on main page.
                # But let's keep it open and let the UI handle the missing data with a message
                pass

        except Exception as e:
            self.error_message = f"Failed to load entity details: {str(e)}"
            # Close modal on error so user sees the message
            self.selected_pair = None
        finally:
            self.is_loading = False

    def clear_selection(self):
        """Clear selected pair."""
        self.selected_pair = None
        self.entity1_details = None
        self.entity2_details = None

    async def merge_entities(self, keep_id: int, merge_id: int):
        """Merge two entities."""
        self.is_loading = True
        self.error_message = ""
        self.success_message = ""
        yield

        try:
            from ..services.entity_deduplication_service import merge_entities

            result = await asyncio.to_thread(merge_entities, keep_id, merge_id)

            if result.get("success"):
                self.success_message = (
                    f"Successfully merged entities. "
                    f"Final name: '{result['final_name']}'. "
                    f"Updated {result['entities_updated']} entity mentions."
                )

                # Remove from candidates
                self.candidates = [
                    c
                    for c in self.candidates
                    if not (
                        (c["id1"] == keep_id and c["id2"] == merge_id)
                        or (c["id1"] == merge_id and c["id2"] == keep_id)
                    )
                ]
                self._apply_filters()

                # Clear selection
                self.clear_selection()

                # Reload stats
                await self.load_statistics()

            else:
                self.error_message = (
                    f"Merge failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.error_message = f"Merge failed: {str(e)}"
        finally:
            self.is_loading = False

    async def unmerge_last(self):
        """Undo the last merge operation."""
        self.is_loading = True
        self.error_message = ""
        self.success_message = ""
        yield

        try:
            from ..services.entity_deduplication_service import unmerge_last_merge, get_deduplication_stats

            result = await asyncio.to_thread(unmerge_last_merge)

            if result.get("success"):
                self.success_message = (
                    f"Unmerged entities. Restored '{result['restored_name']}' "
                    f"(ID: {result['restored_id']}). Moved {result['entities_moved']} mentions back."
                )
                # Reload stats
                self.stats = await asyncio.to_thread(get_deduplication_stats)
            else:
                self.error_message = f"Unmerge failed: {result.get('error', 'Unknown error')}"

        except Exception as e:
            self.error_message = f"Unmerge failed: {str(e)}"
        finally:
            self.is_loading = False

    async def add_alias(self, canonical_id: int, alias: str):
        """Add an alias to a canonical entity."""
        if not alias or not alias.strip():
            self.error_message = "Alias cannot be empty"
            return

        self.is_loading = True
        self.error_message = ""
        yield

        try:
            from ..services.entity_deduplication_service import add_alias

            result = await asyncio.to_thread(add_alias, canonical_id, alias.strip())

            if result.get("success"):
                self.success_message = f"Added alias '{alias}' successfully"

                # Reload details if this entity is selected
                if self.entity1_details and self.entity1_details["id"] == canonical_id:
                    from ..services.entity_deduplication_service import (
                        get_entity_details,
                    )

                    self.entity1_details = await asyncio.to_thread(
                        get_entity_details, canonical_id
                    )
                if self.entity2_details and self.entity2_details["id"] == canonical_id:
                    from ..services.entity_deduplication_service import (
                        get_entity_details,
                    )

                    self.entity2_details = await asyncio.to_thread(
                        get_entity_details, canonical_id
                    )

            else:
                self.error_message = (
                    f"Failed to add alias: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.error_message = f"Failed to add alias: {str(e)}"
        finally:
            self.is_loading = False

    def dismiss_pair(self, id1: int, id2: int):
        """Dismiss a candidate pair (remove from view without merging)."""
        self.candidates = [
            c for c in self.candidates if not (c["id1"] == id1 and c["id2"] == id2)
        ]
        self._apply_filters()

        if (
            self.selected_pair
            and self.selected_pair["id1"] == id1
            and self.selected_pair["id2"] == id2
        ):
            self.clear_selection()

    def clear_messages(self):
        """Clear error and success messages."""
        self.error_message = ""
        self.success_message = ""

    # Manual merge state
    manual_search_query: str = ""
    manual_search_results: List[Dict[str, Any]] = []
    manual_entity1: Optional[Dict[str, Any]] = None
    manual_entity2: Optional[Dict[str, Any]] = None
    manual_merge_modal_open: bool = False
    all_labels: List[str] = []

    async def load_labels(self):
        """Load all available entity labels."""
        try:
            from ..services.entity_deduplication_service import get_all_labels

            self.all_labels = await asyncio.to_thread(get_all_labels)
        except Exception as e:
            logger.error(f"Error loading labels: {e}")

    async def search_entities(self, query: str):
        """Search for entities by name. Loads top entities if query is empty."""
        self.manual_search_query = query
        
        try:
            from ..services.entity_deduplication_service import search_entities

            label = None if self.label_filter == "all" else self.label_filter
            self.manual_search_results = await asyncio.to_thread(
                search_entities,
                query=query,
                label_filter=label,
                limit=30,
            )
        except Exception as e:
            self.error_message = f"Search failed: {str(e)}"

    def select_manual_entity1(self, entity: Dict[str, Any]):
        """Select first entity for manual merge."""
        self.manual_entity1 = entity
        # Clear search results after selection
        self.manual_search_results = []
        self.manual_search_query = ""

    def select_manual_entity2(self, entity: Dict[str, Any]):
        """Select second entity for manual merge."""
        self.manual_entity2 = entity
        self.manual_search_results = []
        self.manual_search_query = ""

    def clear_manual_selection(self):
        """Clear manual entity selections."""
        self.manual_entity1 = None
        self.manual_entity2 = None
        self.manual_search_results = []
        self.manual_search_query = ""

    async def manual_merge(self, keep_first: bool = True):
        """Merge the two manually selected entities."""
        if not self.manual_entity1 or not self.manual_entity2:
            self.error_message = "Please select two entities to merge"
            return

        self.is_loading = True
        self.error_message = ""
        self.success_message = ""
        yield

        try:
            from ..services.entity_deduplication_service import (
                merge_entities,
                get_deduplication_stats,
                get_duplicate_candidates,
            )

            if keep_first:
                keep_id = self.manual_entity1["id"]
                merge_id = self.manual_entity2["id"]
            else:
                keep_id = self.manual_entity2["id"]
                merge_id = self.manual_entity1["id"]

            result = await asyncio.to_thread(merge_entities, keep_id, merge_id)

            if result.get("success"):
                self.success_message = (
                    f"Successfully merged entities. "
                    f"Final name: '{result['final_name']}'."
                )
                self.clear_manual_selection()
                # Reload stats and candidates inline
                self.stats = await asyncio.to_thread(get_deduplication_stats)
                label = None if self.label_filter == "all" else self.label_filter
                self.candidates = await asyncio.to_thread(
                    get_duplicate_candidates,
                    label_filter=label,
                    min_similarity=self.min_similarity,
                    limit=500,
                )
                self._apply_filters()
            else:
                self.error_message = (
                    f"Merge failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.error_message = f"Merge failed: {str(e)}"
        finally:
            self.is_loading = False

    async def delete_entity(self, entity_id: int, entity_name: str):
        """Delete a garbage/malformed entity."""
        self.is_loading = True
        self.error_message = ""
        self.success_message = ""
        yield

        try:
            from ..services.entity_deduplication_service import (
                delete_entity,
                get_deduplication_stats,
                get_duplicate_candidates,
            )

            result = await asyncio.to_thread(delete_entity, entity_id)

            if result.get("success"):
                self.success_message = (
                    f"Deleted '{entity_name}'. "
                    f"Unlinked {result['entities_unlinked']} mentions, "
                    f"deleted {result['relationships_deleted']} relationships."
                )
                # Reload stats and candidates inline
                self.stats = await asyncio.to_thread(get_deduplication_stats)
                label = None if self.label_filter == "all" else self.label_filter
                self.candidates = await asyncio.to_thread(
                    get_duplicate_candidates,
                    label_filter=label,
                    min_similarity=self.min_similarity,
                    limit=500,
                )
                self._apply_filters()
            else:
                self.error_message = (
                    f"Delete failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            self.error_message = f"Delete failed: {str(e)}"
        finally:
            self.is_loading = False

    @rx.var
    def can_manual_merge(self) -> bool:
        """Check if manual merge is possible."""
        if not self.manual_entity1 or not self.manual_entity2:
            return False
        return self.manual_entity1["id"] != self.manual_entity2["id"]

    @rx.var
    def manual_entity1_name(self) -> str:
        """Get manual entity 1 name."""
        return self.manual_entity1["name"] if self.manual_entity1 else ""

    @rx.var
    def manual_entity2_name(self) -> str:
        """Get manual entity 2 name."""
        return self.manual_entity2["name"] if self.manual_entity2 else ""
