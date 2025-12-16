import reflex as rx
import logging
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)


class TimelineEvent(BaseModel):
    date: str = ""
    date_precision: str = "approximate"
    event: str = ""
    entities_involved: List[str] = []
    source: str = ""
    confidence: str = "Medium"
    original_date_text: str = ""


class TimelineConflict(BaseModel):
    date: str = ""
    type: str = ""
    description: str = ""


class TimelineGap(BaseModel):
    from_date: str = ""
    to_date: str = ""
    gap_days: int = 0
    description: str = ""


class EntityOption(BaseModel):
    id: int
    name: str
    type: str
    mentions: int


class TimelineMergeState(rx.State):
    """State for Multi-Document Timeline Merging."""

    # Timeline data
    events: List[TimelineEvent] = []
    conflicts: List[TimelineConflict] = []
    gaps: List[TimelineGap] = []

    # Analysis metadata
    total_events: int = 0
    sources_count: int = 0
    entity_focus: str = ""
    narrative: str = ""

    # Entity selection
    available_entities: List[EntityOption] = []
    selected_entity_id: int = 0
    selected_entity_name: str = ""

    # UI state
    is_loading: bool = False
    is_analyzing: bool = False
    has_results: bool = False
    active_view: str = "timeline"

    def load_entities(self):
        """Load available entities for timeline analysis."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.timeline_merge_service import (
                get_timeline_merge_service,
            )

            service = get_timeline_merge_service()
            entities = service.get_timeline_entities(30)

            self.available_entities = [
                EntityOption(
                    id=e["id"], name=e["name"], type=e["type"], mentions=e["mentions"]
                )
                for e in entities
            ]
        except Exception as e:
            logger.error(f"Error loading entities: {e}")
        finally:
            self.is_loading = False

    @rx.event(background=True)
    async def analyze_corpus_timeline(self):
        """Analyze timeline across entire corpus."""
        async with self:
            self.is_analyzing = True
            self.selected_entity_id = 0
            self.selected_entity_name = ""

        try:
            from app.arkham.services.timeline_merge_service import (
                get_timeline_merge_service,
            )

            service = get_timeline_merge_service()
            result = service.analyze_timeline()

            async with self:
                self._process_timeline_result(result)

        except Exception as e:
            logger.error(f"Error analyzing corpus timeline: {e}")
        finally:
            async with self:
                self.is_analyzing = False

    @rx.event(background=True)
    async def analyze_entity_timeline(self, entity_id: int):
        """Analyze timeline focused on a specific entity."""
        # Find entity name first (read-only, doesn't need lock)
        entity_name = ""
        for e in self.available_entities:
            if e.id == entity_id:
                entity_name = e.name
                break

        async with self:
            self.is_analyzing = True
            self.selected_entity_id = entity_id
            self.selected_entity_name = entity_name

        try:
            from app.arkham.services.timeline_merge_service import (
                get_timeline_merge_service,
            )

            service = get_timeline_merge_service()
            result = service.analyze_timeline(entity_id=entity_id)

            async with self:
                self._process_timeline_result(result)

        except Exception as e:
            logger.error(f"Error analyzing entity timeline: {e}")
        finally:
            async with self:
                self.is_analyzing = False

    def _process_timeline_result(self, result: dict):
        """Process timeline analysis result."""
        self.events = [
            TimelineEvent(
                date=e.get("date", ""),
                date_precision=e.get("date_precision", "approximate"),
                event=e.get("event", ""),
                entities_involved=e.get("entities_involved", []),
                source=e.get("source", ""),
                confidence=e.get("confidence", "Medium"),
                original_date_text=e.get("original_date_text", ""),
            )
            for e in result.get("timeline", [])
        ]

        self.conflicts = [
            TimelineConflict(
                date=c.get("date", ""),
                type=c.get("type", ""),
                description=c.get("description", ""),
            )
            for c in result.get("conflicts", [])
        ]

        self.gaps = [
            TimelineGap(
                from_date=g.get("from_date", ""),
                to_date=g.get("to_date", ""),
                gap_days=g.get("gap_days", 0),
                description=g.get("description", ""),
            )
            for g in result.get("gaps", [])
        ]

        self.total_events = result.get("total_events", 0)
        self.sources_count = result.get("sources_count", 0)
        self.entity_focus = result.get("entity_focus") or ""
        self.has_results = True

    @rx.event(background=True)
    async def generate_narrative(self):
        """Generate narrative summary of timeline."""
        # Read events first (to check if empty - but we can't access self without lock in background)
        async with self:
            if not self.events:
                return
            self.is_analyzing = True
            self.narrative = ""  # Clear previous narrative to show activity

            # Capture state data before releasing lock
            events_data = [
                {"date": e.date, "event": e.event, "source": e.source}
                for e in self.events
            ]
            conflicts_data = [{"description": c.description} for c in self.conflicts]
            gaps_data = [{"description": g.description} for g in self.gaps]
            entity_name_arg = (
                self.selected_entity_name if self.selected_entity_id else None
            )

        try:
            from app.arkham.services.timeline_merge_service import (
                get_timeline_merge_service,
            )

            service = get_timeline_merge_service()

            timeline_data = {
                "timeline": events_data,
                "conflicts": conflicts_data,
                "gaps": gaps_data,
            }

            narrative = service.generate_timeline_narrative(
                timeline_data, entity_name=entity_name_arg
            )

            # Escape dollar signs to prevent markdown math rendering issues
            narrative = narrative.replace("$", "\\$")

            async with self:
                self.narrative = narrative

        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            async with self:
                self.narrative = f"Error: {e}"
        finally:
            async with self:
                self.is_analyzing = False

    def set_active_view(self, view: str):
        self.active_view = view

    def clear_results(self):
        self.events = []
        self.conflicts = []
        self.gaps = []
        self.narrative = ""
        self.has_results = False
        self.selected_entity_id = 0
        self.selected_entity_name = ""
