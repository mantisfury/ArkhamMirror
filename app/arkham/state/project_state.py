import reflex as rx
import logging
from pydantic import BaseModel
from typing import List, Optional

logger = logging.getLogger(__name__)


class ProjectItem(BaseModel):
    id: int
    name: str
    description: str = ""
    status: str = "active"
    priority: str = "medium"
    tags: List[str] = []
    color: str = "blue"
    document_count: int = 0
    updated_at: str = ""


class ProjectDocItem(BaseModel):
    document_id: int
    filename: str
    file_type: str = ""
    added_at: str = ""
    notes: str = ""


class ProjectState(rx.State):
    """State for Project/Case Management.

    This state manages:
    - Project CRUD operations (create, read, update, delete)
    - Global project selection for filtering across all views
    - Sidebar project dropdown data
    """

    # Project list
    projects: List[ProjectItem] = []

    # Global selected project (persisted in browser as string, used for filtering)
    # ID 1 is always "Default Project"
    # NOTE: LocalStorage stores strings, so we use str and convert as needed
    selected_project_id: str = rx.LocalStorage("1", name="arkham_project_id")

    # Current project being viewed in detail (separate from global selection)
    current_project_id: int = 0
    current_project: Optional[ProjectItem] = None
    project_documents: List[ProjectDocItem] = []

    # Stats
    total_projects: int = 0
    active_count: int = 0
    high_priority_count: int = 0

    # New project form
    new_name: str = ""
    new_description: str = ""
    new_priority: str = "medium"
    new_color: str = "blue"
    new_tags: str = ""

    # Edit mode
    editing: bool = False
    edit_name: str = ""
    edit_description: str = ""
    edit_priority: str = ""
    edit_status: str = ""
    edit_notes: str = ""

    # Filters
    filter_status: str = "all"
    filter_priority: str = "all"

    # UI state
    is_loading: bool = False
    show_form: bool = False
    show_details: bool = False

    # Sidebar collapse state (persisted in LocalStorage)
    sidebar_collapsed: str = rx.LocalStorage("false", name="arkham_sidebar_collapsed")

    def toggle_sidebar(self):
        """Toggle sidebar collapsed state."""
        self.sidebar_collapsed = "false" if self.sidebar_collapsed == "true" else "true"

    @rx.var
    def is_sidebar_collapsed(self) -> bool:
        """Check if sidebar is collapsed (as bool for conditionals)."""
        return self.sidebar_collapsed == "true"

    # ===== COMPUTED VARS FOR SIDEBAR =====

    @rx.var
    def selected_project_id_int(self) -> int:
        """Get selected project ID as int for filtering."""
        try:
            return int(self.selected_project_id) if self.selected_project_id else 1
        except (ValueError, TypeError):
            return 1

    @rx.var
    def sidebar_project_options(self) -> List[str]:
        """Get project names for sidebar dropdown."""
        return [p.name for p in self.projects] if self.projects else ["Default Project"]

    @rx.var
    def selected_project_name(self) -> str:
        """Get the currently selected project's name for sidebar display."""
        try:
            selected_id = (
                int(self.selected_project_id) if self.selected_project_id else 1
            )
        except (ValueError, TypeError):
            selected_id = 1
        for p in self.projects:
            if p.id == selected_id:
                return p.name
        return "Default Project"

    @rx.var
    def has_projects(self) -> bool:
        """Check if any projects exist."""
        return len(self.projects) > 0

    # ===== PROJECT SELECTION (for global filtering) =====

    def set_selected_project_by_name(self, name: str):
        """Set the globally selected project by name (used by sidebar dropdown)."""
        for p in self.projects:
            if p.name == name:
                self.selected_project_id = str(p.id)
                return
        # Fallback to default
        self.selected_project_id = "1"

    def set_selected_project(self, project_id: int):
        """Set the globally selected project by ID."""
        self.selected_project_id = str(project_id)

    # ===== ENSURE DEFAULT PROJECT =====

    def ensure_default_project(self):
        """Ensure Default Project (ID=1) exists. Called on app startup."""
        try:
            from app.arkham.services.project_service import get_project_service

            service = get_project_service()
            service.ensure_default_project()
        except Exception as e:
            logger.error(f"Error ensuring default project: {e}")

    def load_projects(self):
        """Load projects list."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.project_service import get_project_service

            service = get_project_service()

            projects = service.list_projects(
                status=self.filter_status if self.filter_status else None,
                priority=self.filter_priority if self.filter_priority else None,
            )

            self.projects = [
                ProjectItem(
                    id=p["id"],
                    name=p["name"],
                    description=p["description"],
                    status=p["status"],
                    priority=p["priority"],
                    tags=p["tags"],
                    color=p["color"],
                    document_count=p["document_count"],
                    updated_at=p["updated_at"] or "",
                )
                for p in projects
            ]

            # Get stats
            stats = service.get_project_stats()
            self.total_projects = stats["total"]
            self.active_count = stats["by_status"].get("active", 0)
            self.high_priority_count = stats["by_priority"].get("high", 0)

        except Exception as e:
            logger.error(f"Error loading projects: {e}")
        finally:
            self.is_loading = False

    def create_project(self):
        """Create a new project."""
        if not self.new_name.strip():
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.project_service import get_project_service

            service = get_project_service()

            tags = [t.strip() for t in self.new_tags.split(",") if t.strip()]

            service.create_project(
                name=self.new_name,
                description=self.new_description,
                priority=self.new_priority,
                tags=tags,
                color=self.new_color,
            )

            # Reset form
            self.new_name = ""
            self.new_description = ""
            self.new_priority = "medium"
            self.new_color = "blue"
            self.new_tags = ""
            self.show_form = False

            yield from self.load_projects()

        except Exception as e:
            logger.error(f"Error creating project: {e}")
        finally:
            self.is_loading = False

    def select_project(self, project_id: int):
        """Select a project to view details."""
        self.current_project_id = project_id
        self.show_details = True
        self.editing = False
        yield from self.load_project_details()

    def load_project_details(self):
        """Load current project details."""
        if self.current_project_id == 0:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.project_service import get_project_service

            service = get_project_service()

            project = service.get_project(self.current_project_id)
            if project:
                self.current_project = ProjectItem(
                    id=project["id"],
                    name=project["name"],
                    description=project["description"] or "",
                    status=project["status"],
                    priority=project["priority"],
                    tags=project["tags"],
                    color=project["color"],
                    document_count=project["document_count"],
                    updated_at=project["updated_at"] or "",
                )

                # Load documents
                docs = service.get_project_documents(self.current_project_id)
                self.project_documents = [
                    ProjectDocItem(
                        document_id=d["document_id"],
                        filename=d["filename"],
                        file_type=d["file_type"] or "",
                        added_at=d["added_at"] or "",
                        notes=d["notes"] or "",
                    )
                    for d in docs
                ]

        except Exception as e:
            logger.error(f"Error loading project: {e}")
        finally:
            self.is_loading = False

    def start_edit(self):
        """Start editing current project."""
        if self.current_project:
            self.editing = True
            self.edit_name = self.current_project.name
            self.edit_description = self.current_project.description
            self.edit_priority = self.current_project.priority
            self.edit_status = self.current_project.status

    def save_edit(self):
        """Save project edits."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.project_service import get_project_service

            service = get_project_service()
            service.update_project(
                self.current_project_id,
                name=self.edit_name,
                description=self.edit_description,
                priority=self.edit_priority,
                status=self.edit_status,
                notes=self.edit_notes,
            )

            self.editing = False
            yield from self.load_project_details()
            yield from self.load_projects()

        except Exception as e:
            logger.error(f"Error saving: {e}")
        finally:
            self.is_loading = False

    def cancel_edit(self):
        self.editing = False

    def delete_project(self):
        """Delete the current project."""
        if self.current_project_id == 0:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.project_service import get_project_service

            service = get_project_service()
            service.delete_project(self.current_project_id)

            self.current_project_id = 0
            self.current_project = None
            self.show_details = False

            yield from self.load_projects()

        except Exception as e:
            logger.error(f"Error deleting: {e}")
        finally:
            self.is_loading = False

    def close_details(self):
        self.show_details = False
        self.current_project_id = 0

    def toggle_form(self):
        self.show_form = not self.show_form

    def set_filter_status(self, value: str):
        self.filter_status = value
        yield from self.load_projects()

    def set_filter_priority(self, value: str):
        self.filter_priority = value
        yield from self.load_projects()

    def set_new_name(self, value: str):
        self.new_name = value

    def set_new_description(self, value: str):
        self.new_description = value

    def set_new_priority(self, value: str):
        self.new_priority = value

    def set_new_color(self, value: str):
        self.new_color = value

    def set_new_tags(self, value: str):
        self.new_tags = value

    def set_edit_name(self, value: str):
        self.edit_name = value

    def set_edit_description(self, value: str):
        self.edit_description = value

    def set_edit_priority(self, value: str):
        self.edit_priority = value

    def set_edit_status(self, value: str):
        self.edit_status = value

    def set_edit_notes(self, value: str):
        self.edit_notes = value
