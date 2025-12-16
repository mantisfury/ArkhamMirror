import reflex as rx
from ..state.project_state import ProjectState
from .design_tokens import SIDEBAR_WIDTH, SPACING, FONT_SIZE, Z_INDEX


SIDEBAR_COLLAPSED_WIDTH = "60px"


def sidebar_link(text: str, icon: str, href: str) -> rx.Component:
    """Reusable sidebar link component."""
    return rx.link(
        rx.hstack(
            rx.icon(tag=icon, size=20),
            rx.cond(
                ProjectState.is_sidebar_collapsed,
                rx.fragment(),  # Hide text when collapsed
                rx.text(text, font_size=FONT_SIZE["sm"]),
            ),
            spacing="3",
            align="center",
        ),
        href=href,
        color="gray.11",
        _hover={"color": "blue.9", "text_decoration": "none"},
        _dark={"color": "gray.9", "_hover": {"color": "gray.12"}},
        width="100%",
        padding_y=SPACING["xs"],
    )


def collapsed_sidebar_link(icon: str, href: str, tooltip: str) -> rx.Component:
    """Sidebar link for collapsed mode - just icon with tooltip."""
    return rx.tooltip(
        rx.link(
            rx.center(
                rx.icon(tag=icon, size=20),
                width="100%",
                padding_y=SPACING["xs"],
            ),
            href=href,
            color="gray.11",
            _hover={"color": "blue.9", "text_decoration": "none"},
            width="100%",
        ),
        content=tooltip,
        side="right",
    )


def sidebar() -> rx.Component:
    """Collapsible sidebar with navigation and project selector."""
    return rx.box(
        rx.vstack(
            # Header with toggle button
            rx.hstack(
                rx.cond(
                    ProjectState.is_sidebar_collapsed,
                    # Collapsed: just the icon
                    rx.icon(tag="shield", color="blue.9", size=26),
                    # Expanded: full logo
                    rx.hstack(
                        rx.icon(tag="shield", color="blue.9", size=26),
                        rx.text(
                            "ArkhamMirror",
                            font_weight="bold",
                            font_size=FONT_SIZE["lg"],
                            color="gray.12",
                        ),
                        align="center",
                        flex="1",
                    ),
                ),
                rx.spacer(),
                rx.tooltip(
                    rx.icon_button(
                        rx.cond(
                            ProjectState.is_sidebar_collapsed,
                            rx.icon("chevron-right", size=16),
                            rx.icon("chevron-left", size=16),
                        ),
                        on_click=ProjectState.toggle_sidebar,
                        variant="ghost",
                        size="1",
                        cursor="pointer",
                    ),
                    content=rx.cond(
                        ProjectState.is_sidebar_collapsed,
                        "Expand sidebar",
                        "Collapse sidebar",
                    ),
                    side="right",
                ),
                width="100%",
                align="center",
                padding_bottom=SPACING["md"],
            ),
            rx.divider(margin_bottom=SPACING["md"]),
            # Navigation - conditionally show full or collapsed version
            rx.cond(
                ProjectState.is_sidebar_collapsed,
                # Collapsed navigation - icons only
                rx.vstack(
                    collapsed_sidebar_link("layout-dashboard", "/overview", "Overview"),
                    collapsed_sidebar_link("search", "/", "Search"),
                    collapsed_sidebar_link("file-plus", "/ingest", "Ingest & Chat"),
                    rx.divider(margin_y="2"),
                    collapsed_sidebar_link("brain", "/ach", "ACH Analysis"),
                    collapsed_sidebar_link("triangle-alert", "/anomalies", "Anomalies"),
                    collapsed_sidebar_link("flag", "/red-flags", "Red Flags"),
                    collapsed_sidebar_link(
                        "scale", "/contradictions", "Contradictions"
                    ),
                    rx.divider(margin_y="2"),
                    collapsed_sidebar_link("network", "/graph", "Graph"),
                    collapsed_sidebar_link("calendar", "/timeline", "Timeline"),
                    collapsed_sidebar_link("map", "/map", "Map"),
                    rx.divider(margin_y="2"),
                    collapsed_sidebar_link("folder", "/projects", "Projects"),
                    collapsed_sidebar_link("settings", "/settings", "Settings"),
                    width="100%",
                    spacing="1",
                    align="center",
                ),
                # Expanded navigation - full links
                rx.vstack(
                    sidebar_link("Overview", "layout-dashboard", "/overview"),
                    sidebar_link("Search", "search", "/"),
                    sidebar_link("Ingest & Chat", "file-plus", "/ingest"),
                    rx.divider(margin_y="2"),
                    rx.text("Analysis", size="1", color="gray", weight="bold"),
                    sidebar_link("ACH Analysis", "brain", "/ach"),
                    sidebar_link("Anomalies", "triangle-alert", "/anomalies"),
                    sidebar_link("Red Flags", "flag", "/red-flags"),
                    sidebar_link("Contradictions", "scale", "/contradictions"),
                    sidebar_link(
                        "Contradiction Chain", "git-branch", "/contradiction-chain"
                    ),
                    sidebar_link("Fact Comparison", "git-compare", "/fact-comparison"),
                    sidebar_link("Narrative", "book-open", "/narrative"),
                    sidebar_link("Hidden Content", "eye-off", "/hidden-content"),
                    sidebar_link("Big Picture", "globe", "/big-picture"),
                    sidebar_link(
                        "Metadata Forensics", "file-search", "/metadata-forensics"
                    ),
                    rx.divider(margin_y="2"),
                    rx.text("Visualization", size="1", color="gray", weight="bold"),
                    sidebar_link("Graph", "network", "/graph"),
                    sidebar_link("Influence Map", "crown", "/influence"),
                    sidebar_link("Timeline", "calendar", "/timeline"),
                    sidebar_link("Timeline Merge", "git-merge", "/timeline-merge"),
                    sidebar_link("Map", "map", "/map"),
                    sidebar_link("Visualizations", "bar-chart-2", "/visualizations"),
                    rx.divider(margin_y="2"),
                    rx.text("Data", size="1", color="gray", weight="bold"),
                    sidebar_link("Tables", "table", "/tables"),
                    sidebar_link("Entity Dedup", "link", "/entity-dedup"),
                    sidebar_link("Duplicate Detector", "copy", "/duplicates"),
                    sidebar_link("Regex Search", "scan-search", "/regex-search"),
                    sidebar_link("Path Finder", "route", "/pathfinder"),
                    rx.divider(margin_y="2"),
                    rx.text("AI Tools", size="1", color="gray", weight="bold"),
                    sidebar_link("Speculation Mode", "brain", "/speculation"),
                    rx.divider(margin_y="2"),
                    rx.text("System", size="1", color="gray", weight="bold"),
                    sidebar_link("Projects", "folder", "/projects"),
                    sidebar_link("Filters", "filter", "/filters"),
                    sidebar_link("Upload History", "history", "/upload-history"),
                    sidebar_link("Annotations", "sticky-note", "/annotations"),
                    sidebar_link("Doc Comparison", "git-compare", "/comparison"),
                    sidebar_link("Export", "package", "/export"),
                    sidebar_link("Settings", "settings", "/settings"),
                    width="100%",
                    spacing="1",
                    align="start",
                ),
            ),
            rx.spacer(),
            rx.divider(margin_y=SPACING["md"]),
            # Project selector - hide text when collapsed
            rx.cond(
                ProjectState.is_sidebar_collapsed,
                # Collapsed: just show folder icon
                rx.tooltip(
                    rx.center(
                        rx.icon("folder", size=20, color="gray.9"),
                        width="100%",
                        padding_y=SPACING["xs"],
                    ),
                    content=ProjectState.selected_project_name,
                    side="right",
                ),
                # Expanded: full project selector
                rx.vstack(
                    rx.text(
                        "Project",
                        font_size=FONT_SIZE["xs"],
                        color="gray.9",
                        text_transform="uppercase",
                        font_weight="bold",
                    ),
                    rx.select(
                        ProjectState.sidebar_project_options,
                        value=ProjectState.selected_project_name,
                        on_change=ProjectState.set_selected_project_by_name,
                        variant="surface",
                        width="100%",
                    ),
                    width="100%",
                    spacing="2",
                ),
            ),
            height="100%",
            width="100%",
            spacing="0",
            align="start",
            on_mount=[
                ProjectState.ensure_default_project,
                ProjectState.load_projects,
            ],
        ),
        width=rx.cond(
            ProjectState.is_sidebar_collapsed,
            SIDEBAR_COLLAPSED_WIDTH,
            SIDEBAR_WIDTH,
        ),
        min_width=rx.cond(
            ProjectState.is_sidebar_collapsed,
            SIDEBAR_COLLAPSED_WIDTH,
            SIDEBAR_WIDTH,
        ),
        height="100vh",
        padding=rx.cond(
            ProjectState.is_sidebar_collapsed,
            SPACING["sm"],
            SPACING["lg"],
        ),
        bg="gray.2",
        border_right="1px solid",
        border_color="gray.4",
        position="sticky",
        top="0",
        left="0",
        z_index=Z_INDEX["sticky"],
        overflow_y="auto",
        overflow_x="hidden",
        transition="width 0.2s ease, min-width 0.2s ease, padding 0.2s ease",
        _dark={
            "bg": "gray.1",
            "border_color": "gray.4",
        },
    )
