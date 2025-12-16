import reflex as rx
from app.arkham.state.contradiction_state import ContradictionState
from app.arkham.components.sidebar import sidebar
from app.arkham.components.worker_management import worker_management_component


def contradiction_card(contradiction):
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.badge(
                    contradiction.severity,
                    color_scheme=rx.match(
                        contradiction.severity,
                        ("High", "red"),
                        ("Medium", "orange"),
                        "gray",
                    ),
                ),
                rx.badge(contradiction.status, variant="outline"),
                rx.spacer(),
                rx.text(f"Str: {contradiction.confidence}", size="1", color="gray"),
                width="100%",
            ),
            rx.heading(contradiction.entity_name, size="4"),
            rx.text(contradiction.description, size="2"),
            align_items="start",
            width="100%",
        ),
        on_click=lambda: ContradictionState.select_contradiction(contradiction),
        cursor="pointer",
        _hover={"transform": "scale(1.02)", "transition": "transform 0.2s"},
        width="100%",
    )


def evidence_view(evidence):
    return rx.box(
        rx.text(evidence.text, style={"font-style": "italic"}),
        rx.text(
            f"Doc ID: {evidence.document_id}", size="1", color="gray", margin_top="1"
        ),
        padding="3",
        border="1px solid #eee",
        border_radius="6px",
        bg="gray.50",
        width="100%",
    )


def entity_filter_item(entity) -> rx.Component:
    """Render an entity checkbox for filtering."""
    return rx.box(
        rx.checkbox(
            rx.hstack(
                rx.text(entity.name, size="2"),
                rx.badge(entity.label, size="1", variant="soft"),
                rx.text(f"({entity.mentions})", size="1", color="gray"),
                spacing="1",
            ),
            checked=ContradictionState.selected_entity_ids.contains(entity.id),
            on_change=lambda: ContradictionState.toggle_entity(entity.id),
            size="1",
        ),
        padding="1",
    )


def document_filter_item(doc) -> rx.Component:
    """Render a document checkbox for filtering."""
    return rx.box(
        rx.checkbox(
            rx.hstack(
                rx.text(doc.filename, size="2"),
                rx.badge(doc.doc_type, size="1", variant="soft"),
                spacing="1",
            ),
            checked=ContradictionState.selected_doc_ids.contains(doc.id),
            on_change=lambda: ContradictionState.toggle_document(doc.id),
            size="1",
        ),
        padding="1",
    )


def filter_panel() -> rx.Component:
    """Collapsible filter panel for entity and document selection."""
    return rx.cond(
        ContradictionState.show_filters,
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.icon("filter", size=16, color="var(--accent-9)"),
                    rx.heading("Focus Analysis", size="4"),
                    rx.spacer(),
                    rx.button(
                        rx.icon("x", size=14),
                        "Close",
                        variant="ghost",
                        size="1",
                        on_click=ContradictionState.toggle_filters,
                    ),
                    width="100%",
                ),
                rx.text(
                    "Select specific entities and documents to analyze. "
                    "Leave empty to analyze top entities across entire corpus.",
                    size="2",
                    color="gray",
                ),
                rx.hstack(
                    # Entity Selection
                    rx.vstack(
                        rx.hstack(
                            rx.icon("user", size=14, color="var(--purple-9)"),
                            rx.text("Entities", weight="bold", size="3"),
                            rx.badge(
                                ContradictionState.selected_entity_ids.length().to(str)
                                + " selected",
                                color_scheme="purple",
                            ),
                            spacing="2",
                        ),
                        rx.input(
                            placeholder="Search entities...",
                            value=ContradictionState.entity_search,
                            on_change=ContradictionState.set_entity_search,
                            size="1",
                            width="100%",
                        ),
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(
                                    ContradictionState.filtered_entities,
                                    entity_filter_item,
                                ),
                                spacing="1",
                                align_items="start",
                                width="100%",
                            ),
                            height="180px",
                            width="100%",
                        ),
                        border="1px solid var(--purple-a6)",
                        border_radius="8px",
                        padding="3",
                        width="100%",
                        spacing="2",
                    ),
                    # Document Selection
                    rx.vstack(
                        rx.hstack(
                            rx.icon("file-text", size=14, color="var(--blue-9)"),
                            rx.text("Documents", weight="bold", size="3"),
                            rx.badge(
                                ContradictionState.selected_doc_ids.length().to(str)
                                + " selected",
                                color_scheme="blue",
                            ),
                            spacing="2",
                        ),
                        rx.input(
                            placeholder="Search documents...",
                            value=ContradictionState.doc_search,
                            on_change=ContradictionState.set_doc_search,
                            size="1",
                            width="100%",
                        ),
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(
                                    ContradictionState.filtered_documents,
                                    document_filter_item,
                                ),
                                spacing="1",
                                align_items="start",
                                width="100%",
                            ),
                            height="180px",
                            width="100%",
                        ),
                        border="1px solid var(--blue-a6)",
                        border_radius="8px",
                        padding="3",
                        width="100%",
                        spacing="2",
                    ),
                    spacing="4",
                    width="100%",
                ),
                rx.hstack(
                    rx.button(
                        rx.icon("x", size=14),
                        "Clear Filters",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ContradictionState.clear_filters,
                    ),
                    spacing="2",
                ),
                spacing="4",
                width="100%",
            ),
            padding="4",
            margin_bottom="4",
        ),
        rx.fragment(),
    )


def job_progress_panel() -> rx.Component:
    """Panel showing background job progress with controls."""
    return rx.cond(
        ContradictionState.job_id != "",
        rx.card(
            rx.vstack(
                # Header with status
                rx.hstack(
                    rx.icon("activity", size=18, color="var(--accent-9)"),
                    rx.heading("Detection Progress", size="4"),
                    rx.badge(
                        ContradictionState.job_status,
                        color_scheme=rx.match(
                            ContradictionState.job_status,
                            ("running", "green"),
                            ("paused", "yellow"),
                            ("cooldown", "blue"),
                            ("complete", "green"),
                            ("failed", "red"),
                            ("stopped", "orange"),
                            "gray",
                        ),
                    ),
                    rx.spacer(),
                    # Close button for completed jobs
                    rx.cond(
                        ~ContradictionState.is_job_running
                        & ~ContradictionState.is_job_paused,
                        rx.button(
                            rx.icon("x", size=14),
                            variant="ghost",
                            size="1",
                            on_click=ContradictionState.load_results,
                        ),
                        rx.fragment(),
                    ),
                    width="100%",
                    align="center",
                ),
                # Progress bar
                rx.progress(
                    value=ContradictionState.progress_pct,
                    max=100,
                    width="100%",
                ),
                # Stats row
                rx.hstack(
                    rx.text(
                        ContradictionState.job_progress.to(str)
                        + " / "
                        + ContradictionState.job_total.to(str)
                        + " entities",
                        size="2",
                    ),
                    rx.text("⚡", size="2"),
                    rx.text(
                        ContradictionState.job_found.to(str) + " contradictions found",
                        size="2",
                        color="var(--red-11)",
                    ),
                    rx.spacer(),
                    rx.text(ContradictionState.eta_display, size="2", color="gray"),
                    width="100%",
                ),
                # Current entity
                rx.cond(
                    ContradictionState.job_current_entity != "",
                    rx.hstack(
                        rx.text("Analyzing:", size="2", color="gray"),
                        rx.text(
                            ContradictionState.job_current_entity,
                            size="2",
                            weight="bold",
                        ),
                        spacing="2",
                    ),
                    rx.fragment(),
                ),
                # Error message
                rx.cond(
                    ContradictionState.job_error != "",
                    rx.callout(
                        ContradictionState.job_error,
                        icon="triangle-alert",
                        color="red",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                # Control buttons
                rx.hstack(
                    rx.cond(
                        ContradictionState.is_job_running,
                        rx.button(
                            rx.icon("pause", size=14),
                            "Pause",
                            variant="soft",
                            color_scheme="yellow",
                            on_click=ContradictionState.pause_job,
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        ContradictionState.is_job_paused,
                        rx.button(
                            rx.icon("play", size=14),
                            "Resume",
                            variant="soft",
                            color_scheme="green",
                            on_click=ContradictionState.resume_job,
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        ContradictionState.is_job_running
                        | ContradictionState.is_job_paused,
                        rx.button(
                            rx.icon("square", size=14),
                            "Stop",
                            variant="soft",
                            color_scheme="red",
                            on_click=ContradictionState.stop_job,
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        ContradictionState.job_status == "complete",
                        rx.button(
                            rx.icon("check", size=14),
                            "Load Results",
                            color_scheme="green",
                            on_click=ContradictionState.load_results,
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                ),
                spacing="3",
                width="100%",
            ),
            padding="4",
            margin_bottom="4",
            border="1px solid var(--accent-6)",
        ),
        rx.fragment(),
    )


# Phase 4: Search and filter bar
def search_filter_bar():
    return rx.hstack(
        # Search input
        rx.input(
            placeholder="Search contradictions...",
            value=ContradictionState.search_query,
            on_change=ContradictionState.set_search_query,
            width="250px",
        ),
        rx.divider(orientation="vertical", size="1"),
        # Severity filter
        rx.select(
            ["all", "High", "Medium", "Low"],
            placeholder="Severity",
            value=rx.cond(
                ContradictionState.severity_filter == "",
                "all",
                ContradictionState.severity_filter,
            ),
            on_change=ContradictionState.set_severity_filter,
            size="2",
        ),
        # Status filter
        rx.select(
            ["all", "Open", "Resolved", "False Positive"],
            placeholder="Status",
            value=rx.cond(
                ContradictionState.status_filter == "",
                "all",
                ContradictionState.status_filter,
            ),
            on_change=ContradictionState.set_status_filter,
            size="2",
        ),
        # Sort
        rx.select(
            ["newest", "oldest", "severity", "strength"],
            value=ContradictionState.sort_by,
            on_change=ContradictionState.set_sort_by,
            size="2",
        ),
        rx.divider(orientation="vertical", size="1"),
        # View toggle
        rx.button(
            rx.cond(
                ContradictionState.view_mode == "list",
                rx.icon("layout-grid", size=14),
                rx.icon("list", size=14),
            ),
            on_click=ContradictionState.toggle_view_mode,
            variant="outline",
            size="1",
        ),
        # Page size
        rx.select(
            ["10", "25", "50", "100"],
            value=ContradictionState.page_size.to_string(),
            on_change=ContradictionState.set_page_size,
            size="1",
        ),
        # Result count
        rx.badge(
            ContradictionState.result_count,
            " results",
            variant="soft",
        ),
        # Export CSV
        rx.button(
            rx.icon("download", size=12),
            "CSV",
            on_click=ContradictionState.export_csv,
            variant="outline",
            size="1",
        ),
        # Clear filters
        rx.button(
            rx.icon("x", size=12),
            "Clear",
            on_click=ContradictionState.clear_all_filters,
            variant="ghost",
            size="1",
        ),
        spacing="2",
        width="100%",
        padding="2",
        bg="gray.2",
        border_radius="6px",
    )


# Phase 4: List view (table)
def list_view_row(contradiction):
    return rx.table.row(
        rx.table.cell(
            rx.badge(
                contradiction.severity,
                color_scheme=rx.match(
                    contradiction.severity,
                    ("High", "red"),
                    ("Medium", "orange"),
                    "gray",
                ),
                size="1",
            ),
        ),
        rx.table.cell(rx.text(contradiction.entity_name, weight="bold", size="2")),
        rx.table.cell(
            rx.badge(
                contradiction.category,
                color_scheme=rx.match(
                    contradiction.category,
                    ("timeline", "blue"),
                    ("financial", "green"),
                    ("location", "purple"),
                    ("identity", "orange"),
                    "gray",
                ),
                variant="soft",
                size="1",
            ),
        ),
        rx.table.cell(
            rx.text(
                contradiction.description[:60] + "...",
                size="2",
            ),
        ),
        rx.table.cell(rx.badge(contradiction.status, variant="outline", size="1")),
        rx.table.cell(
            rx.text(
                (contradiction.confidence * 100).to(int).to_string() + "%", size="2"
            )
        ),
        rx.table.cell(
            rx.cond(
                contradiction.created_at,
                rx.text(contradiction.created_at[:10], size="1", color="gray"),
                rx.text("-", size="1", color="gray"),
            ),
        ),
        on_click=lambda: ContradictionState.select_contradiction(contradiction),
        cursor="pointer",
        _hover={"bg": "gray.3"},
    )


def list_view():
    """Sortable list view with clickable headers."""

    def sort_header(label: str, column: str):
        """Create a clickable, sortable column header."""
        return rx.table.column_header_cell(
            rx.hstack(
                rx.text(label),
                rx.cond(
                    ContradictionState.sort_column == column,
                    rx.cond(
                        ContradictionState.sort_ascending,
                        rx.icon("arrow-up", size=12),
                        rx.icon("arrow-down", size=12),
                    ),
                    rx.icon("arrow-up-down", size=12, color="gray"),
                ),
                spacing="1",
                cursor="pointer",
            ),
            on_click=lambda: ContradictionState.toggle_sort(column),
            cursor="pointer",
        )

    return rx.table.root(
        rx.table.header(
            rx.table.row(
                sort_header("Severity", "severity"),
                sort_header("Entity", "entity"),
                rx.table.column_header_cell("Category"),  # Phase 3
                rx.table.column_header_cell("Description"),  # Not sortable
                sort_header("Status", "status"),
                sort_header("Str", "strength"),
                sort_header("Date", "date"),
            ),
        ),
        rx.table.body(
            rx.foreach(ContradictionState.displayed_contradictions, list_view_row),
        ),
        width="100%",
        variant="surface",
    )


# Batch Management Panel
def batch_status_row(batch):
    """Render a single batch status row."""
    status_color = rx.match(
        batch["status"],
        ("complete", "green"),
        ("running", "blue"),
        ("incomplete", "orange"),
        "gray",
    )
    return rx.hstack(
        rx.progress(
            value=rx.cond(
                batch["status"] == "complete",
                100,
                rx.cond(batch["status"] == "running", 50, 0),
            ),
            width="80px",
            color_scheme=status_color,
        ),
        rx.text(f"Batch {batch['batch_number']}", weight="bold", size="2"),
        rx.badge(batch["status"], color_scheme=status_color, size="1"),
        rx.text(f"{batch['entity_count']} entities", size="1", color="gray"),
        rx.text(f"{batch['contradictions_found']} found", size="1"),
        spacing="2",
        width="100%",
    )


def batch_overview_panel():
    """Panel showing batch status and controls."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("Batch Overview", size="4"),
                rx.spacer(),
                rx.text(
                    f"{ContradictionState.completed_batches}/{ContradictionState.total_batches} batches complete",
                    size="2",
                    color="gray",
                ),
                rx.text(
                    f"{ContradictionState.total_entities} total entities",
                    size="2",
                    color="gray",
                ),
                width="100%",
            ),
            rx.divider(),
            # Show batches list or "no entities" message
            rx.cond(
                ContradictionState.total_batches > 0,
                rx.foreach(ContradictionState.batches, batch_status_row),
                rx.hstack(
                    rx.icon("info", size=14, color="gray"),
                    rx.text(
                        "No entities found. Ingest documents to detect contradictions.",
                        size="2",
                        color="gray",
                    ),
                    spacing="2",
                    padding="3",
                ),
            ),
            rx.divider(),
            rx.hstack(
                rx.button(
                    rx.icon("play", size=14),
                    "Start Next Batch",
                    on_click=ContradictionState.start_next_batch,
                    disabled=ContradictionState.all_batches_complete
                    | (ContradictionState.total_batches == 0),
                    size="2",
                ),
                rx.checkbox(
                    "Auto-Continue",
                    checked=ContradictionState.auto_continue,
                    on_change=ContradictionState.toggle_auto_continue,
                    size="1",
                ),
                rx.checkbox(
                    "Force Refresh",
                    checked=ContradictionState.force_refresh,
                    on_change=ContradictionState.toggle_force_refresh,
                    size="1",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("refresh-cw", size=12),
                    "Refresh",
                    on_click=ContradictionState.load_batch_overview,
                    variant="outline",
                    size="1",
                ),
                rx.button(
                    rx.icon("rotate-ccw", size=12),
                    "Reset All",
                    on_click=ContradictionState.reset_batches,
                    variant="ghost",
                    color_scheme="red",
                    size="1",
                ),
                spacing="2",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def contradictions_page():
    return rx.hstack(
        sidebar(),
        rx.vstack(
            rx.heading("Contradiction Detection Engine", size="8"),
            rx.text(
                "Identify conflicting statements and factual inconsistencies across the corpus.",
                color="gray",
            ),
            # New docs ingested banner (Phase 2)
            rx.cond(
                ContradictionState.has_new_docs,
                rx.callout(
                    "New documents have been ingested since the last analysis. Consider re-running detection.",
                    icon="info",
                    color="blue",
                    size="1",
                ),
                rx.fragment(),
            ),
            # Worker Management Panel
            worker_management_component(),
            # Batch Overview Panel
            batch_overview_panel(),
            # Semantic Search Panel (Phase 4)
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.icon("brain", size=16),
                        rx.text("Semantic Search", weight="bold"),
                        rx.tooltip(
                            rx.icon("info", size=12, color="gray"),
                            content="Search contradictions by meaning, not just keywords",
                        ),
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.input(
                            placeholder="Search by meaning... (e.g., 'financial discrepancies')",
                            value=ContradictionState.semantic_query,
                            on_change=ContradictionState.set_semantic_query,
                            width="100%",
                        ),
                        rx.button(
                            rx.icon("search", size=14),
                            "Search",
                            on_click=ContradictionState.semantic_search,
                            loading=ContradictionState.is_searching,
                            color_scheme="blue",
                        ),
                        rx.cond(
                            ContradictionState.is_semantic_search,
                            rx.button(
                                rx.icon("x", size=14),
                                "Clear",
                                on_click=ContradictionState.clear_semantic_search,
                                variant="ghost",
                            ),
                            rx.fragment(),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.cond(
                        ContradictionState.is_semantic_search,
                        rx.badge(
                            f"Showing {ContradictionState.semantic_results.length()} semantic matches",
                            color_scheme="blue",
                            variant="soft",
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                    width="100%",
                ),
                padding="3",
            ),
            # Filter indicator
            rx.hstack(
                rx.text(ContradictionState.filter_description, size="2", color="gray"),
                rx.cond(
                    (ContradictionState.selected_entity_ids.length() > 0)
                    | (ContradictionState.selected_doc_ids.length() > 0),
                    rx.badge(
                        "Filtered",
                        color_scheme="purple",
                        variant="soft",
                    ),
                    rx.fragment(),
                ),
                spacing="2",
            ),
            # Action buttons
            rx.hstack(
                rx.button(
                    rx.icon("filter", size=14),
                    "Filter",
                    on_click=ContradictionState.toggle_filters,
                    variant="outline",
                    color_scheme=rx.cond(
                        ContradictionState.show_filters, "purple", "gray"
                    ),
                    disabled=ContradictionState.is_job_running,
                ),
                # Background detection button - switches between Start and sync Run
                rx.cond(
                    ~ContradictionState.is_job_running
                    & ~ContradictionState.is_job_paused,
                    rx.button(
                        rx.icon("play"),
                        "Start Detection",
                        on_click=ContradictionState.start_background_detection,
                        loading=ContradictionState.is_loading,
                        disabled=ContradictionState.job_id != "",
                    ),
                    rx.fragment(),
                ),
                rx.link(
                    rx.button(
                        rx.icon("git-branch", size=14),
                        "View Chain",
                        variant="soft",
                        color_scheme="red",
                    ),
                    href="/contradiction-chain",
                ),
                rx.button(
                    rx.icon("refresh-cw"),
                    "Refresh",
                    on_click=ContradictionState.load_contradictions,
                    variant="outline",
                    disabled=ContradictionState.is_job_running,
                ),
                rx.button(
                    rx.icon("trash-2"),
                    "Clear All",
                    on_click=ContradictionState.clear_all,
                    variant="outline",
                    color_scheme="red",
                    disabled=ContradictionState.is_job_running,
                ),
                # Force refresh checkbox
                rx.checkbox(
                    "Force Refresh (bypass cache)",
                    checked=ContradictionState.force_refresh,
                    on_change=ContradictionState.toggle_force_refresh,
                    size="1",
                ),
                spacing="2",
            ),
            # Filter panel
            filter_panel(),
            # Job progress panel (shows when job is active)
            job_progress_panel(),
            # Phase 4: Search and filter bar
            search_filter_bar(),
            # Results - toggle between list and card view
            rx.cond(
                ContradictionState.is_loading,
                rx.center(rx.spinner(), width="100%", padding="4"),
                rx.cond(
                    ContradictionState.view_mode == "list",
                    list_view(),
                    rx.grid(
                        rx.foreach(
                            ContradictionState.displayed_contradictions,
                            contradiction_card,
                        ),
                        columns="3",
                        spacing="4",
                        width="100%",
                    ),
                ),
            ),
            # Phase 5: Pagination controls
            rx.hstack(
                rx.button(
                    rx.icon("chevron-left", size=14),
                    "Previous",
                    on_click=ContradictionState.prev_page,
                    disabled=~ContradictionState.can_prev,
                    variant="outline",
                    size="2",
                ),
                rx.text(ContradictionState.page_info, color="gray"),
                rx.button(
                    "Next",
                    rx.icon("chevron-right", size=14),
                    on_click=ContradictionState.next_page,
                    disabled=~ContradictionState.can_next,
                    variant="outline",
                    size="2",
                ),
                justify="center",
                spacing="4",
                width="100%",
                padding="3",
            ),
            # Detail Modal
            rx.dialog.root(
                rx.dialog.content(
                    rx.vstack(
                        rx.hstack(
                            rx.heading("Contradiction Detail", size="5"),
                            rx.dialog.close(
                                rx.button(
                                    rx.icon("x"),
                                    variant="ghost",
                                    on_click=ContradictionState.clear_selection,
                                )
                            ),
                            justify="between",
                            width="100%",
                        ),
                        rx.cond(
                            ContradictionState.selected_contradiction,
                            rx.vstack(
                                rx.heading(
                                    ContradictionState.selected_contradiction.entity_name,
                                    size="6",
                                ),
                                rx.text(
                                    ContradictionState.selected_contradiction.description
                                ),
                                rx.divider(),
                                rx.heading("Evidence", size="4"),
                                rx.foreach(
                                    ContradictionState.selected_contradiction.evidence,
                                    evidence_view,
                                ),
                                spacing="4",
                                width="100%",
                            ),
                            rx.spinner(),
                        ),
                        rx.hstack(
                            rx.button(
                                "Mark Resolved",
                                on_click=ContradictionState.mark_resolved,
                                color_scheme="green",
                            ),
                            rx.button(
                                "False Positive",
                                on_click=ContradictionState.mark_false_positive,
                                color_scheme="gray",
                            ),
                            justify="end",
                            width="100%",
                            margin_top="4",
                        ),
                    ),
                    max_width="800px",
                ),
                open=ContradictionState.selected_contradiction.bool(),
                on_open_change=ContradictionState.on_open_change,
            ),
            # Polling interval for job status (polls every 5 seconds when job is active)
            rx.cond(
                ContradictionState.is_job_running | ContradictionState.is_job_paused,
                rx.moment(
                    interval=5000,  # 5 seconds
                    on_change=lambda _: ContradictionState.poll_job_status(),
                ),
                rx.fragment(),
            ),
            padding="2em",
            width="100%",
            align_items="start",
            on_mount=[
                ContradictionState.load_batch_overview,
                ContradictionState.load_contradictions,
            ],
        ),
        width="100%",
        height="100vh",
    )
