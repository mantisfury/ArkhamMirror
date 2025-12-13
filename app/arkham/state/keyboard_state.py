"""
Global keyboard shortcuts state management.
"""

import reflex as rx
from typing import Optional


class KeyboardState(rx.State):
    """
    Global keyboard shortcuts state.

    Supported shortcuts:
    - Cmd+K / Ctrl+K: Toggle global search modal
    - Escape: Close active modals
    - Cmd+/ / Ctrl+/: Show keyboard shortcuts help
    """

    # Modal states
    search_modal_open: bool = False
    shortcuts_help_open: bool = False

    def toggle_search_modal(self):
        """Toggle global search modal (Cmd+K / Ctrl+K)."""
        self.search_modal_open = not self.search_modal_open
        # Close other modals when opening search
        if self.search_modal_open:
            self.shortcuts_help_open = False

    def open_search_modal(self):
        """Open global search modal."""
        self.search_modal_open = True
        self.shortcuts_help_open = False

    def close_all_modals(self):
        """Close all open modals (Escape key)."""
        self.search_modal_open = False
        self.shortcuts_help_open = False

    def toggle_shortcuts_help(self):
        """Toggle keyboard shortcuts help modal (Cmd+/ or Ctrl+/)."""
        self.shortcuts_help_open = not self.shortcuts_help_open
        # Close other modals when opening help
        if self.shortcuts_help_open:
            self.search_modal_open = False
