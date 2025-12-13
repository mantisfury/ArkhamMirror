"""
Components package for ArkhamMirror Reflex UI.

This package provides reusable UI components and utilities.
"""

# Layout components
from .layout import layout
from .sidebar import sidebar

# UI Component Library
from .ui_library import (
    # Cards & Containers
    stat_card,
    info_card,
    section_card,
    # Buttons & Actions
    action_button,
    icon_button,
    button_group,
    # Form Inputs
    search_input,
    labeled_input,
    select_field,
    # Data Display
    data_table_header,
    entity_badge,
    severity_badge,
    status_badge,
    progress_indicator,
    # Layout Helpers
    empty_state,
    loading_overlay,
    grid_layout,
    two_column_layout,
    # Feedback & Notifications
    alert_banner,
    confirmation_dialog,
    # Specialized Components
    document_card,
    entity_relationship_badge,
)

__all__ = [
    # Layout
    "layout",
    "sidebar",
    # Cards
    "stat_card",
    "info_card",
    "section_card",
    # Buttons
    "action_button",
    "icon_button",
    "button_group",
    # Forms
    "search_input",
    "labeled_input",
    "select_field",
    # Data Display
    "data_table_header",
    "entity_badge",
    "severity_badge",
    "status_badge",
    "progress_indicator",
    # Layout
    "empty_state",
    "loading_overlay",
    "grid_layout",
    "two_column_layout",
    # Feedback
    "alert_banner",
    "confirmation_dialog",
    # Specialized
    "document_card",
    "entity_relationship_badge",
]
