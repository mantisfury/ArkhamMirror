"""Graph settings state with LocalStorage persistence."""

import reflex as rx
from typing import List


class GraphSettingsState(rx.State):
    """State for graph filter/display settings. All values persist via LocalStorage."""

    # ============================================================
    # FILTERING SETTINGS
    # ============================================================

    # Minimum relationship strength to show edges
    min_edge_strength: float = 0.1

    # Minimum connections for a node to be shown
    min_degree: int = 1

    # Maximum document ratio - hide super-nodes appearing in > X% of docs
    max_doc_ratio: float = 0.8

    # Entity types to exclude from the graph
    exclude_entity_types: List[str] = ["DATE"]

    # Whether to hide singleton nodes (nodes with no edges after filtering)
    hide_singletons: bool = True

    # ============================================================
    # DISPLAY SETTINGS
    # ============================================================

    # Label visibility mode: "all" | "none" | "top_percent"
    label_visibility_mode: str = "top_percent"

    # When mode is "top_percent", show labels for top N% by degree
    label_percent: int = 10

    # Edge transparency (0.0 = invisible, 1.0 = opaque)
    edge_opacity: float = 0.15

    # Spring layout repulsion factor (higher = more spread out)
    spring_k: float = 2.5

    # Node size range
    node_size_min: int = 8
    node_size_max: int = 50

    # ============================================================
    # LAYOUT SETTINGS (with LocalStorage persistence)
    # ============================================================

    # Layout algorithm: "spring" | "circular" | "kamada"
    layout_algorithm: str = rx.LocalStorage("spring", name="graph_layout")

    # Whether to show labels at all (master toggle)
    show_labels: bool = True  # Can't use LocalStorage for bool directly

    # ============================================================
    # AVAILABLE OPTIONS (loaded from DB)
    # ============================================================

    # List of all entity types in the database
    available_entity_types: List[str] = []

    # Total document count (for max_doc_ratio reference)
    total_document_count: int = 0

    # ============================================================
    # EVENT HANDLERS
    # ============================================================

    def load_available_entity_types(self):
        """Fetch unique entity types from the database."""
        try:
            from ..services.graph_service import get_available_entity_types

            self.available_entity_types = get_available_entity_types()
        except Exception as e:
            import logging

            logging.error(f"Failed to load entity types: {e}")
            # Fallback to common types
            self.available_entity_types = [
                "PERSON",
                "ORG",
                "GPE",
                "DATE",
                "MONEY",
                "EVENT",
                "PRODUCT",
                "LOCATION",
                "MISC",
            ]

    def toggle_entity_type_exclusion(self, entity_type: str):
        """Add/remove entity type from exclusion list."""
        if entity_type in self.exclude_entity_types:
            self.exclude_entity_types = [
                t for t in self.exclude_entity_types if t != entity_type
            ]
        else:
            self.exclude_entity_types = self.exclude_entity_types + [entity_type]

    def set_exclude_entity_types(self, types: List[str]):
        """Set the complete list of excluded entity types."""
        self.exclude_entity_types = types

    def set_min_edge_strength(self, value: float):
        """Set minimum edge strength threshold."""
        self.min_edge_strength = max(0.0, min(1.0, value))

    def set_min_degree(self, value: int):
        """Set minimum degree filter."""
        self.min_degree = max(0, value)

    def set_max_doc_ratio(self, value: float):
        """Set maximum document ratio threshold."""
        self.max_doc_ratio = max(0.0, min(1.0, value))

    def set_hide_singletons(self, value: bool):
        """Set whether to hide singleton nodes."""
        self.hide_singletons = value

    def set_label_visibility_mode(self, mode: str):
        """Set label visibility mode."""
        if mode in ["all", "none", "top_percent"]:
            self.label_visibility_mode = mode

    def set_label_percent(self, value: int):
        """Set top N% threshold for label visibility."""
        self.label_percent = max(1, min(100, value))

    def set_edge_opacity(self, value: float):
        """Set edge opacity."""
        self.edge_opacity = max(0.0, min(1.0, value))

    def set_spring_k(self, value: float):
        """Set spring layout repulsion factor."""
        self.spring_k = max(0.1, min(10.0, value))

    def set_node_size_min(self, value: int):
        """Set minimum node size."""
        self.node_size_min = max(2, min(value, self.node_size_max - 1))

    def set_node_size_max(self, value: int):
        """Set maximum node size."""
        self.node_size_max = max(self.node_size_min + 1, min(100, value))

    # Dropdown-specific handlers (accept str from rx.select on_change)
    def set_min_edge_strength_from_dropdown(self, value: str):
        """Set min_edge_strength from dropdown (receives string value)."""
        try:
            self.min_edge_strength = max(0.0, min(1.0, float(value)))
        except ValueError:
            pass

    def set_min_degree_from_dropdown(self, value: str):
        """Set min_degree from dropdown (receives string value)."""
        try:
            self.min_degree = max(0, int(value))
        except ValueError:
            pass

    def set_max_doc_ratio_from_dropdown(self, value: str):
        """Set max_doc_ratio from dropdown (receives string value)."""
        try:
            self.max_doc_ratio = max(0.0, min(1.0, float(value)))
        except ValueError:
            pass

    def set_label_percent_from_dropdown(self, value: str):
        """Set label_percent from dropdown (receives string value)."""
        try:
            self.label_percent = max(1, min(100, int(value)))
        except ValueError:
            pass

    def set_edge_opacity_from_dropdown(self, value: str):
        """Set edge_opacity from dropdown (receives string value)."""
        try:
            self.edge_opacity = max(0.0, min(1.0, float(value)))
        except ValueError:
            pass

    def set_spring_k_from_dropdown(self, value: str):
        """Set spring_k from dropdown (receives string value)."""
        try:
            self.spring_k = max(0.1, min(10.0, float(value)))
        except ValueError:
            pass

    def set_node_size_min_from_dropdown(self, value: str):
        """Set node_size_min from dropdown (receives string value)."""
        try:
            self.node_size_min = max(2, min(int(value), self.node_size_max - 1))
        except ValueError:
            pass

    def set_node_size_max_from_dropdown(self, value: str):
        """Set node_size_max from dropdown (receives string value)."""
        try:
            self.node_size_max = max(self.node_size_min + 1, min(100, int(value)))
        except ValueError:
            pass

    def set_layout_algorithm(self, algorithm: str):
        """Set graph layout algorithm."""
        if algorithm in ["spring", "circular", "kamada"]:
            self.layout_algorithm = algorithm

    def toggle_labels(self):
        """Toggle master label visibility."""
        self.show_labels = not self.show_labels

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.min_edge_strength = 0.1
        self.min_degree = 1
        self.max_doc_ratio = 0.8
        self.exclude_entity_types = ["DATE"]
        self.hide_singletons = True
        self.label_visibility_mode = "top_percent"
        self.label_percent = 10
        self.edge_opacity = 0.15
        self.spring_k = 2.5
        self.node_size_min = 8
        self.node_size_max = 50
        self.layout_algorithm = "spring"
        self.show_labels = True

    def get_settings_dict(self) -> dict:
        """Get all current settings as a dictionary for passing to backend."""
        return {
            "min_edge_strength": self.min_edge_strength,
            "min_degree": self.min_degree,
            "max_doc_ratio": self.max_doc_ratio,
            "exclude_entity_types": self.exclude_entity_types,
            "hide_singletons": self.hide_singletons,
            "label_visibility_mode": self.label_visibility_mode,
            "label_percent": self.label_percent,
            "edge_opacity": self.edge_opacity,
            "spring_k": self.spring_k,
            "node_size_min": self.node_size_min,
            "node_size_max": self.node_size_max,
            "layout_algorithm": self.layout_algorithm,
            "show_labels": self.show_labels,
        }
