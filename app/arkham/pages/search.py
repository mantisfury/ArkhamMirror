import reflex as rx
from ..components.layout import layout
from ..components.search_bar import search_bar
from ..components.result_card import result_card, document_viewer_modal
from ..components.skeletons import skeleton_search_results
from ..state.search_state import SearchState
from ..components.design_tokens import SPACING, CARD_PADDING


class SearchPageState(rx.State):
    """State for the search page to handle URL query parameters."""

    async def check_doc_filter(self):
        """Check for doc_id query parameter on page load."""
        router_data = self.router.page.params

        doc_id_str = router_data.get("doc_id", "")
        if doc_id_str:
            try:
                doc_id = int(doc_id_str)
                from ..services.search_service import get_document_title
                doc_title = get_document_title(doc_id) or f"Document #{doc_id}"

                search_state = await self.get_state(SearchState)
                search_state.filter_doc_id = doc_id
                search_state.filter_doc_title = doc_title
                if not search_state.query:
                    search_state.query = "*"
                await search_state.execute_search()
            except (ValueError, TypeError):
                pass


def filters_panel() -> rx.Component:
    """Advanced filters panel for search refinement."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("Filters", size="4"),
                rx.spacer(),
                rx.button(
                    "Clear All",
                    on_click=SearchState.clear_filters,
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                ),
                width="100%",
                align="center",
            ),
            # Date range filters
            rx.vstack(
                rx.text("Date Range", size="2", weight="bold", color="gray.11"),
                rx.hstack(
                    rx.vstack(
                        rx.text("From:", size="1", color="gray.11"),
                        rx.input(
                            type="date",
                            value=SearchState.date_from,
                            on_change=SearchState.set_date_from,
                            size="2",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    rx.vstack(
                        rx.text("To:", size="1", color="gray.11"),
                        rx.input(
                            type="date",
                            value=SearchState.date_to,
                            on_change=SearchState.set_date_to,
                            size="2",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    spacing=SPACING["md"],
                    width="100%",
                ),
                spacing=SPACING["sm"],
                width="100%",
            ),
            # Entity type filter
            rx.vstack(
                rx.text("Entity Types", size="2", weight="bold", color="gray.11"),
                rx.select.root(
                    rx.select.trigger(),
                    rx.select.content(
                        rx.select.item("All Types", value="all"),
                        rx.select.item("People", value="PERSON"),
                        rx.select.item("Organizations", value="ORG"),
                        rx.select.item("Locations", value="GPE"),
                        rx.select.item("Dates", value="DATE"),
                        rx.select.item("Money", value="MONEY"),
                        rx.select.item("Emails", value="EMAIL"),
                        rx.select.item("Phone Numbers", value="PHONE"),
                    ),
                    value=SearchState.entity_type_filter,
                    on_change=SearchState.set_entity_type_filter,
                    size="2",
                ),
                spacing=SPACING["sm"],
                width="100%",
            ),
            # Document type filter
            rx.vstack(
                rx.text("Document Type", size="2", weight="bold", color="gray.11"),
                rx.select.root(
                    rx.select.trigger(),
                    rx.select.content(
                        rx.select.item("All Documents", value="all"),
                        rx.select.item("PDF", value="pdf"),
                        rx.select.item("Word Documents", value="docx"),
                        rx.select.item("Text Files", value="txt"),
                        rx.select.item("Emails", value="eml"),
                        rx.select.item("Outlook Messages", value="msg"),
                    ),
                    value=SearchState.doc_type_filter,
                    on_change=SearchState.set_doc_type_filter,
                    size="2",
                ),
                spacing=SPACING["sm"],
                width="100%",
            ),
            # Apply filters button
            rx.button(
                "Apply Filters",
                on_click=SearchState.execute_search,
                width="100%",
                size="2",
            ),
            spacing=SPACING["lg"],
            width="100%",
        ),
        width="100%",
        padding=CARD_PADDING,
    )


def doc_filter_banner() -> rx.Component:
    """Banner showing active document filter with clear button."""
    return rx.cond(
        SearchState.filter_doc_id,
        rx.callout.root(
            rx.callout.icon(rx.icon(tag="filter")),
            rx.callout.text(
                rx.hstack(
                    rx.text("Searching within: ", weight="bold"),
                    rx.text(SearchState.filter_doc_title),
                    rx.spacer(),
                    rx.button(
                        rx.icon(tag="x", size=14),
                        "Clear Filter",
                        on_click=SearchState.clear_doc_filter,
                        size="1",
                        variant="ghost",
                    ),
                    width="100%",
                    align="center",
                ),
            ),
            color_scheme="blue",
            margin_bottom=SPACING["md"],
        ),
        rx.fragment(),
    )


@rx.page(route="/search", on_load=SearchPageState.check_doc_filter)
def search_page() -> rx.Component:
    """Main search page."""
    return layout(
        rx.vstack(
            rx.heading("Document Search", size="8", margin_bottom=SPACING["md"]),
            doc_filter_banner(),
            search_bar(),
            rx.divider(margin_y=SPACING["lg"]),
            # Filters and results layout
            rx.hstack(
                # Left sidebar - Filters
                rx.box(
                    filters_panel(),
                    width="300px",
                    flex_shrink="0",
                ),
                # Right content - Results
                rx.vstack(
                    # Results header with export
                    rx.cond(
                        SearchState.results.length() > 0,
                        rx.hstack(
                            rx.text(
                                f"{SearchState.results.length()} results",
                                size="2",
                                color="gray.11",
                            ),
                            rx.spacer(),
                            rx.button(
                                rx.icon(tag="download", size=16),
                                "Export CSV",
                                on_click=SearchState.export_results,
                                size="2",
                                variant="soft",
                            ),
                            width="100%",
                            align="center",
                            margin_bottom=SPACING["md"],
                        ),
                    ),
                    # Results list
                    rx.cond(
                        SearchState.is_loading,
                        skeleton_search_results(count=5),
                        rx.vstack(
                            rx.foreach(
                                SearchState.results,
                                result_card,
                            ),
                            spacing=SPACING["md"],
                            width="100%",
                        ),
                    ),
                    # Empty state
                    rx.cond(
                        (SearchState.results.length() == 0)
                        & (~SearchState.is_loading)
                        & (SearchState.query != ""),
                        rx.center(
                            rx.vstack(
                                rx.icon(tag="search", size=40, color="gray.8"),
                                rx.text("No results found", color="gray.11"),
                                spacing=SPACING["sm"],
                                align="center",
                            ),
                            width="100%",
                            padding=SPACING["2xl"],
                        ),
                        rx.fragment(),
                    ),
                    # Pagination
                    rx.cond(
                        SearchState.results.length() > 0,
                        rx.hstack(
                            rx.button(
                                "Previous",
                                on_click=lambda: SearchState.set_current_page(
                                    SearchState.current_page - 1
                                ),
                                disabled=SearchState.current_page <= 1,
                                variant="outline",
                            ),
                            rx.text(
                                f"Page {SearchState.current_page}", color="gray.11"
                            ),
                            rx.button(
                                "Next",
                                on_click=lambda: SearchState.set_current_page(
                                    SearchState.current_page + 1
                                ),
                                # Disable next if fewer results than limit (rough heuristic)
                                disabled=SearchState.results.length()
                                < SearchState.results_per_page,
                                variant="outline",
                            ),
                            justify="center",
                            width="100%",
                            padding_top=SPACING["lg"],
                            spacing=SPACING["md"],
                        ),
                        rx.fragment(),
                    ),
                    spacing=SPACING["md"],
                    width="100%",
                    flex="1",
                ),
                spacing=SPACING["xl"],
                width="100%",
                align="start",
            ),
            spacing=SPACING["md"],
            width="100%",
            align="start",
        ),
        # Document viewer modal
        document_viewer_modal(),
    )
