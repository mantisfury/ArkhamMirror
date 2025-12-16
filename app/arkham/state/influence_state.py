import reflex as rx
import logging
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class InfluenceEntity(BaseModel):
    id: int
    name: str
    type: str
    mentions: int
    degree: int
    community: int
    influence_score: float
    degree_centrality: float = 0.0
    betweenness: float = 0.0
    closeness: float = 0.0
    pagerank: float = 0.0
    eigenvector: float = 0.0


class InfluenceBroker(BaseModel):
    id: int
    name: str
    betweenness: float
    community: int
    degree: int


class InfluenceBridge(BaseModel):
    entity1_id: int
    entity1_name: str
    entity2_id: int
    entity2_name: str
    community1: int
    community2: int
    strength: float


class InfluenceState(rx.State):
    """State for Entity Influence Mapping."""

    entities: List[InfluenceEntity] = []
    brokers: List[InfluenceBroker] = []
    bridges: List[InfluenceBridge] = []
    communities: List[Dict[str, Any]] = []

    summary_total_entities: int = 0
    summary_total_connections: int = 0
    summary_density: float = 0.0
    summary_avg_degree: float = 0.0
    summary_num_communities: int = 0
    summary_most_influential: str = "N/A"

    selected_entity: Optional[InfluenceEntity] = None
    selected_entity_neighbors: List[Dict[str, Any]] = []

    is_loading: bool = False
    active_tab: str = "rankings"

    # Session cache flag - prevents auto-reload when navigating back
    _has_loaded: bool = False

    @rx.var
    def has_data(self) -> bool:
        """Check if influence data has been loaded."""
        return len(self.entities) > 0

    def load_influence_data(self):
        """Load all influence metrics from the service."""
        # Skip if already loaded (session cache)
        if self._has_loaded and self.entities:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.influence_service import get_influence_service

            service = get_influence_service()
            data = service.get_influence_metrics()

            # Convert entities
            self.entities = []
            for e in data.get("entities", []):
                metrics = e.get("metrics", {})
                self.entities.append(
                    InfluenceEntity(
                        id=e["id"],
                        name=e["name"],
                        type=e["type"],
                        mentions=e["mentions"],
                        degree=e["degree"],
                        community=e["community"],
                        influence_score=e["influence_score"],
                        degree_centrality=metrics.get("degree_centrality", 0),
                        betweenness=metrics.get("betweenness", 0),
                        closeness=metrics.get("closeness", 0),
                        pagerank=metrics.get("pagerank", 0),
                        eigenvector=metrics.get("eigenvector", 0),
                    )
                )

            self.communities = data.get("communities", [])

            # Summary
            summary = data.get("summary", {})
            self.summary_total_entities = summary.get("total_entities", 0)
            self.summary_total_connections = summary.get("total_connections", 0)
            self.summary_density = summary.get("density", 0)
            self.summary_avg_degree = summary.get("avg_degree", 0)
            self.summary_num_communities = summary.get("num_communities", 0)
            self.summary_most_influential = summary.get("most_influential", "N/A")

            # Power dynamics
            dynamics = service.get_power_dynamics()

            self.brokers = [
                InfluenceBroker(
                    id=b["id"],
                    name=b["name"],
                    betweenness=b["betweenness"],
                    community=b["community"],
                    degree=b["degree"],
                )
                for b in dynamics.get("brokers", [])
            ]

            self.bridges = [
                InfluenceBridge(
                    entity1_id=b["entity1_id"],
                    entity1_name=b["entity1_name"],
                    entity2_id=b["entity2_id"],
                    entity2_name=b["entity2_name"],
                    community1=b["community1"],
                    community2=b["community2"],
                    strength=b["strength"],
                )
                for b in dynamics.get("bridges", [])
            ]

        except Exception as e:
            logger.error(f"Error loading influence data: {e}")
        finally:
            self.is_loading = False
            self._has_loaded = True  # Mark as loaded for session cache

    def refresh_influence_data(self):
        """Force reload influence data, clearing cache."""
        self._has_loaded = False
        return InfluenceState.load_influence_data

    def select_entity(self, entity: InfluenceEntity):
        """Select an entity for detailed view."""
        self.selected_entity = entity
        self._load_entity_detail(entity.id)

    def _load_entity_detail(self, entity_id: int):
        """Load detailed info for selected entity."""
        try:
            from app.arkham.services.influence_service import get_influence_service

            service = get_influence_service()
            detail = service.get_entity_influence_detail(entity_id)

            if detail:
                self.selected_entity_neighbors = detail.get("neighbors", [])
        except Exception as e:
            logger.error(f"Error loading entity detail: {e}")

    def clear_selection(self):
        self.selected_entity = None
        self.selected_entity_neighbors = []
        self.mention_sources = []
        self.show_mentions_modal = False

    def on_open_change(self, is_open: bool):
        if not is_open:
            self.clear_selection()

    def set_active_tab(self, tab: str):
        self.active_tab = tab

    # Mention sources feature
    mention_sources: List[Dict[str, Any]] = []
    mention_sources_entity_name: str = ""
    mention_sources_unique_docs: int = 0
    show_mentions_modal: bool = False

    def load_mention_sources(self, entity_id: int):
        """Load sources for entity mentions."""
        try:
            from app.arkham.services.influence_service import get_influence_service

            service = get_influence_service()
            data = service.get_entity_mention_sources(entity_id)

            self.mention_sources = data.get("sources", [])
            self.mention_sources_entity_name = data.get("entity_name", "Unknown")
            self.mention_sources_unique_docs = data.get("unique_documents", 0)
            self.show_mentions_modal = True
        except Exception as e:
            logger.error(f"Error loading mention sources: {e}")

    def close_mentions_modal(self):
        """Close the mentions modal (for on_click)."""
        self.show_mentions_modal = False

    def on_mentions_modal_change(self, is_open: bool):
        """Handle mentions modal open/close state change."""
        if not is_open:
            self.show_mentions_modal = False

    connection_sources: List[Dict[str, Any]] = []
    connection_sources_entity_name: str = ""
    connection_sources_total: int = 0
    show_connections_modal: bool = False

    def load_connection_sources(self, entity_id: int):
        """Load connection details for an entity."""
        try:
            from app.arkham.services.influence_service import get_influence_service

            service = get_influence_service()
            data = service.get_entity_connections(entity_id)

            self.connection_sources = data.get("connections", [])
            self.connection_sources_entity_name = data.get("entity_name", "Unknown")
            self.connection_sources_total = data.get("total_connections", 0)
            self.show_connections_modal = True
        except Exception as e:
            logger.error(f"Error loading connection sources: {e}")

    def close_connections_modal(self):
        """Close the connections modal (for on_click)."""
        self.show_connections_modal = False

    def on_connections_modal_change(self, is_open: bool):
        """Handle connections modal open/close state change."""
        if not is_open:
            self.show_connections_modal = False

    @rx.var
    def top_10_entities(self) -> List[InfluenceEntity]:
        return self.entities[:10]

    @rx.var
    def entity_count(self) -> int:
        return len(self.entities)
