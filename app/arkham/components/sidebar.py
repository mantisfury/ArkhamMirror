import reflex as rx
from ..state.project_state import ProjectState
from .design_tokens import SIDEBAR_WIDTH, SPACING, FONT_SIZE, Z_INDEX


def sidebar_link(text: str, icon: str, href: str) -> rx.Component:
    """Reusable sidebar link component."""
    return rx.link(
        rx.hstack(
            rx.icon(tag=icon, size=20),
            rx.text(text, font_size=FONT_SIZE["sm"]),
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


def sidebar() -> rx.Component:
    """Sidebar with navigation and project selector."""
    return rx.box(
        rx.vstack(
            # Logo area
            rx.hstack(
                rx.icon(tag="shield", color="blue.9", size=26),
                rx.text(
                    "ArkhamMirror",
                    font_weight="bold",
                    font_size=FONT_SIZE["lg"],
                    color="gray.12",
                ),
                align="center",
                width="100%",
                padding_bottom=SPACING["md"],
            ),
            rx.divider(margin_bottom=SPACING["md"]),
            # Navigation
            rx.vstack(
                sidebar_link("Overview", "layout-dashboard", "/overview"),
                sidebar_link("Search", "search", "/"),
                sidebar_link("Ingest & Chat", "file-plus", "/ingest"),
                rx.divider(margin_y="2"),
                rx.text("Analysis", size="1", color="gray", weight="bold"),
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
            rx.spacer(),
            rx.divider(margin_y=SPACING["md"]),
            # Project selector - connected to ProjectState for dynamic data
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
                on_mount=[
                    ProjectState.ensure_default_project,
                    ProjectState.load_projects,
                ],
            ),
            height="100%",
            width="100%",
            spacing="0",
            align="start",
        ),
        width=SIDEBAR_WIDTH,
        height="100vh",
        padding=SPACING["lg"],
        bg="gray.2",
        border_right="1px solid",
        border_color="gray.4",
        position="sticky",
        top="0",
        left="0",
        z_index=Z_INDEX["sticky"],
        _dark={
            "bg": "gray.1",  # Darker background in dark mode
            "border_color": "gray.4",
        },
    )
