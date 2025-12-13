import reflex as rx
from pydantic import BaseModel
from typing import List


class EntityOption(BaseModel):
    id: int
    name: str
    type: str = ""
    mentions: int = 0


class PathNode(BaseModel):
    id: int
    name: str
    type: str = ""
    mentions: int = 0


class PathEdge(BaseModel):
    source: int
    target: int
    weight: float = 1.0
    type: str = "associated"


class NeighborEntity(BaseModel):
    id: int
    name: str
    type: str = ""
    mentions: int = 0
    distance: int = 0


class PathFinderState(rx.State):
    """State for Shortest Path Finder."""

    # Entity selection
    entities: List[EntityOption] = []
    source_id: int = 0
    target_id: int = 0
    source_name: str = ""
    target_name: str = ""

    # Path results
    path_found: bool = False
    path_length: int = 0
    path_nodes: List[PathNode] = []
    path_edges: List[PathEdge] = []

    # All paths results
    all_paths_count: int = 0

    # Neighbors
    neighbors: List[NeighborEntity] = []
    neighbor_degree: int = 1

    # Settings
    min_weight: float = 0.1
    max_path_length: int = 5

    # UI state
    is_loading: bool = False
    error_message: str = ""
    active_tab: str = "shortest"

    def load_entities(self):
        """Load entities for selection."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.pathfinder_service import get_pathfinder_service

            service = get_pathfinder_service()
            entities = service.get_searchable_entities()

            self.entities = [
                EntityOption(
                    id=e["id"],
                    name=e["name"],
                    type=e["type"] or "",
                    mentions=e["mentions"],
                )
                for e in entities
            ]

        except Exception as e:
            self.error_message = str(e)
        finally:
            self.is_loading = False

    def set_source(self, entity_id: str):
        """Set source entity."""
        try:
            self.source_id = int(entity_id)
            for e in self.entities:
                if e.id == self.source_id:
                    self.source_name = e.name
                    break
        except ValueError:
            pass

    def set_target(self, entity_id: str):
        """Set target entity."""
        try:
            self.target_id = int(entity_id)
            for e in self.entities:
                if e.id == self.target_id:
                    self.target_name = e.name
                    break
        except ValueError:
            pass

    def find_path(self):
        """Find shortest path between selected entities."""
        if self.source_id == 0 or self.target_id == 0:
            self.error_message = "Please select both source and target entities"
            return

        self.is_loading = True
        self.error_message = ""
        self.path_found = False
        yield

        try:
            from app.arkham.services.pathfinder_service import get_pathfinder_service

            service = get_pathfinder_service()
            result = service.find_shortest_path(
                self.source_id,
                self.target_id,
                min_weight=self.min_weight,
            )

            if "error" in result:
                self.error_message = result["error"]
                return

            self.path_found = result.get("found", False)
            self.path_length = result.get("length", 0)

            if self.path_found:
                self.path_nodes = [
                    PathNode(
                        id=n["id"],
                        name=n["name"],
                        type=n["type"],
                        mentions=n["mentions"],
                    )
                    for n in result.get("path", [])
                ]

                self.path_edges = [
                    PathEdge(
                        source=e["source"],
                        target=e["target"],
                        weight=e["weight"],
                        type=e["type"],
                    )
                    for e in result.get("edges", [])
                ]

        except Exception as e:
            self.error_message = str(e)
        finally:
            self.is_loading = False

    def find_neighbors(self):
        """Find entities within N degrees."""
        if self.source_id == 0:
            self.error_message = "Please select an entity"
            return

        self.is_loading = True
        self.error_message = ""
        yield

        try:
            from app.arkham.services.pathfinder_service import get_pathfinder_service

            service = get_pathfinder_service()
            result = service.get_entity_neighbors(
                self.source_id,
                degree=self.neighbor_degree,
            )

            if "error" in result:
                self.error_message = result["error"]
                return

            self.neighbors = [
                NeighborEntity(
                    id=n["id"],
                    name=n["name"],
                    type=n["type"],
                    mentions=n["mentions"],
                    distance=n["distance"],
                )
                for n in result.get("neighbors", [])
            ]

        except Exception as e:
            self.error_message = str(e)
        finally:
            self.is_loading = False

    def swap_entities(self):
        """Swap source and target."""
        self.source_id, self.target_id = self.target_id, self.source_id
        self.source_name, self.target_name = self.target_name, self.source_name

    def clear_results(self):
        self.path_found = False
        self.path_nodes = []
        self.path_edges = []
        self.neighbors = []
        self.error_message = ""

    def set_min_weight(self, value: str):
        try:
            self.min_weight = float(value)
        except ValueError:
            pass

    def set_neighbor_degree(self, value: str):
        try:
            self.neighbor_degree = int(value)
        except ValueError:
            pass

    def set_active_tab(self, tab: str):
        self.active_tab = tab
