import reflex as rx
import logging
from pydantic import BaseModel
from typing import List, Optional

logger = logging.getLogger(__name__)


class EntityOption(BaseModel):
    id: int
    name: str
    type: str
    mentions: int


class NarrativeEvent(BaseModel):
    event: str
    date: str = "Unknown"
    confidence: str = "Medium"


class NarrativeRelationship(BaseModel):
    entity: str
    relationship: str
    nature: str = "neutral"


class MotiveHypothesis(BaseModel):
    hypothesis: str
    supporting_evidence: List[str] = []
    contradicting_evidence: List[str] = []
    confidence: str = "Medium"
    verification_needed: List[str] = []


class KeyPlayer(BaseModel):
    name: str
    role: str
    significance: str = ""


class BriefHypothesis(BaseModel):
    hypothesis: str
    confidence: str = "Medium"


class NarrativeState(rx.State):
    """State for Narrative Reconstruction and Motive Inference."""

    # Entity selection
    available_entities: List[EntityOption] = []
    selected_entity_id: Optional[int] = None
    selected_entity_name: str = ""

    # Narrative data
    narrative_text: str = ""
    narrative_events: List[NarrativeEvent] = []
    narrative_relationships: List[NarrativeRelationship] = []
    narrative_gaps: List[str] = []
    narrative_confidence: str = ""

    # Motive data
    hypotheses: List[MotiveHypothesis] = []
    behavioral_patterns: List[str] = []
    risk_flags: List[str] = []
    speculation_warning: str = ""

    # Brief data
    brief_summary: str = ""
    brief_key_players: List[KeyPlayer] = []
    brief_red_flags: List[str] = []
    brief_hypotheses: List[BriefHypothesis] = []
    brief_gaps: List[str] = []
    brief_next_steps: List[str] = []

    # UI state
    is_loading: bool = False
    active_tab: str = "narrative"
    show_brief: bool = False

    # Per-entity cache: {entity_id: {"narrative": {...}, "motives": {...}}}
    entity_cache: dict = {}

    def load_entities(self):
        """Load analyzable entities."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.narrative_service import get_narrative_service

            service = get_narrative_service()
            entities = service.get_analyzable_entities(limit=20)

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

    def select_entity(self, entity_id: int, entity_name: str):
        """Select an entity for analysis. Caches and restores results per entity."""
        # Save current entity's results to cache before switching
        if self.selected_entity_id is not None:
            self._save_to_cache(self.selected_entity_id)

        # Switch to new entity
        self.selected_entity_id = entity_id
        self.selected_entity_name = entity_name

        # Try to load cached results for this entity
        if not self._load_from_cache(entity_id):
            # No cache - clear results
            self._clear_entity_results()

        # Always switch to narrative tab when selecting
        self.active_tab = "narrative"

    def _save_to_cache(self, entity_id: int):
        """Save current entity results to cache."""
        self.entity_cache[str(entity_id)] = {
            "narrative_text": self.narrative_text,
            "narrative_events": [e.dict() for e in self.narrative_events],
            "narrative_relationships": [r.dict() for r in self.narrative_relationships],
            "narrative_gaps": self.narrative_gaps,
            "narrative_confidence": self.narrative_confidence,
            "hypotheses": [h.dict() for h in self.hypotheses],
            "behavioral_patterns": self.behavioral_patterns,
            "risk_flags": self.risk_flags,
            "speculation_warning": self.speculation_warning,
        }

    def _load_from_cache(self, entity_id: int) -> bool:
        """Load entity results from cache. Returns True if found."""
        key = str(entity_id)
        if key not in self.entity_cache:
            return False

        cached = self.entity_cache[key]
        self.narrative_text = cached.get("narrative_text", "")
        self.narrative_events = [
            NarrativeEvent(**e) for e in cached.get("narrative_events", [])
        ]
        self.narrative_relationships = [
            NarrativeRelationship(**r)
            for r in cached.get("narrative_relationships", [])
        ]
        self.narrative_gaps = cached.get("narrative_gaps", [])
        self.narrative_confidence = cached.get("narrative_confidence", "")
        self.hypotheses = [MotiveHypothesis(**h) for h in cached.get("hypotheses", [])]
        self.behavioral_patterns = cached.get("behavioral_patterns", [])
        self.risk_flags = cached.get("risk_flags", [])
        self.speculation_warning = cached.get("speculation_warning", "")
        return True

    def _clear_entity_results(self):
        """Clear entity-specific analysis results (not the brief)."""
        self.narrative_text = ""
        self.narrative_events = []
        self.narrative_relationships = []
        self.narrative_gaps = []
        self.narrative_confidence = ""
        self.hypotheses = []
        self.behavioral_patterns = []
        self.risk_flags = []
        self.speculation_warning = ""

    def analyze_narrative(self):
        """Run narrative reconstruction for selected entity."""
        if not self.selected_entity_id:
            return

        self.is_loading = True
        self.active_tab = "narrative"
        yield

        try:
            from app.arkham.services.narrative_service import get_narrative_service

            service = get_narrative_service()
            result = service.reconstruct_narrative(self.selected_entity_id)

            self.narrative_text = result.get("narrative", "")
            self.narrative_confidence = result.get("overall_confidence", "")
            self.narrative_gaps = result.get("gaps", [])

            # Parse events
            self.narrative_events = [
                NarrativeEvent(
                    event=e.get("event", ""),
                    date=e.get("date", "Unknown"),
                    confidence=e.get("confidence", "Medium"),
                )
                for e in result.get("events", [])
            ]

            # Parse relationships
            self.narrative_relationships = [
                NarrativeRelationship(
                    entity=r.get("entity", ""),
                    relationship=r.get("relationship", ""),
                    nature=r.get("nature", "neutral"),
                )
                for r in result.get("relationships", [])
            ]

        except Exception as e:
            logger.error(f"Error in narrative analysis: {e}")
            self.narrative_text = f"Error: {e}"
        finally:
            self.is_loading = False

    def analyze_motives(self):
        """Run motive inference for selected entity."""
        if not self.selected_entity_id:
            return

        self.is_loading = True
        self.active_tab = "motives"
        yield

        try:
            from app.arkham.services.narrative_service import get_narrative_service

            service = get_narrative_service()
            result = service.infer_motives(self.selected_entity_id)

            self.speculation_warning = result.get(
                "speculation_warning",
                "These are hypotheses based on limited evidence. Verify before acting.",
            )
            self.behavioral_patterns = result.get("behavioral_patterns", [])
            self.risk_flags = result.get("risk_flags", [])

            self.hypotheses = [
                MotiveHypothesis(
                    hypothesis=h.get("hypothesis", ""),
                    supporting_evidence=h.get("supporting_evidence", []),
                    contradicting_evidence=h.get("contradicting_evidence", []),
                    confidence=h.get("confidence", "Medium"),
                    verification_needed=h.get("verification_needed", []),
                )
                for h in result.get("hypotheses", [])
            ]

        except Exception as e:
            logger.error(f"Error in motive analysis: {e}")
        finally:
            self.is_loading = False

    def generate_brief(self):
        """Generate investigation brief."""
        self.is_loading = True
        self.active_tab = "brief"  # Switch to brief tab
        yield

        try:
            from app.arkham.services.narrative_service import get_narrative_service

            service = get_narrative_service()
            result = service.generate_investigation_brief()

            self.brief_summary = result.get("executive_summary", "")
            self.brief_red_flags = result.get("red_flags", [])
            self.brief_gaps = result.get("gaps", [])
            self.brief_next_steps = result.get("next_steps", [])

            self.brief_key_players = [
                KeyPlayer(
                    name=p.get("name", ""),
                    role=p.get("role", ""),
                    significance=p.get("significance", ""),
                )
                for p in result.get("key_players", [])
            ]

            self.brief_hypotheses = [
                BriefHypothesis(
                    hypothesis=h.get("hypothesis", ""),
                    confidence=h.get("confidence", "Medium"),
                )
                for h in result.get("hypotheses", [])
            ]

        except Exception as e:
            logger.error(f"Error generating brief: {e}")
            self.brief_summary = f"Error: {e}"
        finally:
            self.is_loading = False

    def close_brief(self):
        self.show_brief = False

    def show_brief_tab(self):
        """Switch to brief tab without regenerating."""
        self.active_tab = "brief"

    def set_active_tab(self, tab: str):
        self.active_tab = tab

    @rx.var
    def has_entity_selected(self) -> bool:
        return self.selected_entity_id is not None

    @rx.var
    def has_narrative(self) -> bool:
        return len(self.narrative_text) > 0

    @rx.var
    def has_hypotheses(self) -> bool:
        return len(self.hypotheses) > 0

    @rx.var
    def has_brief(self) -> bool:
        return len(self.brief_summary) > 0
