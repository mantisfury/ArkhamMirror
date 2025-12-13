import reflex as rx
from typing import Optional


class AppState(rx.State):
    """Global application state, persisted across sessions."""

    # Persisted in browser localStorage
    current_project_id: str = rx.LocalStorage("")
    theme: str = rx.LocalStorage("dark")

    # Session state (not persisted)
    is_loading: bool = False
    error_message: Optional[str] = None

    # Computed vars
    @rx.var
    def has_project(self) -> bool:
        return self.current_project_id is not None and self.current_project_id != ""

    def set_project_id(self, project_id: str):
        self.current_project_id = project_id

    def set_theme(self, theme: str):
        """Set the application theme (light, dark, or system)."""
        self.theme = theme

    def toggle_theme(self):
        """Toggle between light and dark theme."""
        self.theme = "dark" if self.theme == "light" else "light"
