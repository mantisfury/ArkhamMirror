"""
Test page for error boundary functionality.

This page demonstrates all error boundary types and can be used
to test error handling without breaking production pages.
"""

import reflex as rx
from ..components.layout import layout
from ..components.error_boundary import (
    section_error_boundary,
    async_operation_wrapper,
    form_error_boundary,
    data_table_error_boundary,
    chart_error_boundary,
    critical_section_boundary,
)
from ..components.error_display import error_callout, inline_error
from ..state.error_state import ErrorStateMixin
from ..utils.error_handler import ErrorCategory, ErrorRecovery
import plotly.express as px


class ErrorBoundaryTestState(ErrorStateMixin):
    """Test state for error boundary demonstrations."""

    # Section test
    section_has_error: bool = False
    section_error_message: str = ""

    # Async operation test
    async_data: list[str] = []
    is_loading_async: bool = False

    # Table test
    table_data: list[dict] = []
    is_loading_table: bool = False
    has_table_error: bool = False
    table_error_message: str = ""

    # Chart test
    chart_data: dict = {}
    is_loading_chart: bool = False
    has_chart_error: bool = False
    chart_error_message: str = ""

    def trigger_section_error(self):
        """Trigger a section error for testing."""
        try:
            raise Exception("Simulated section error - database connection failed")
        except Exception as e:
            self.set_error(
                e,
                category=ErrorCategory.DATABASE,
                error_type="connection",
                context={"test": "section_error"},
            )
            self.section_has_error = True
            self.section_error_message = self.error_message

    def clear_section_error(self):
        """Clear section error."""
        self.section_has_error = False
        self.section_error_message = ""
        self.clear_error()

    def trigger_async_error(self):
        """Trigger async operation error."""
        self.is_loading_async = True

        def _fail():
            raise Exception("Simulated network timeout")

        try:
            _fail()
        except Exception as e:
            self.set_error(
                e,
                category=ErrorCategory.NETWORK,
                error_type="timeout",
                context={"test": "async_error"},
            )
        finally:
            self.is_loading_async = False

    def load_async_success(self):
        """Load async data successfully."""
        self.is_loading_async = True
        self.clear_error()

        import time
        time.sleep(1)  # Simulate loading

        self.async_data = ["Item 1", "Item 2", "Item 3"]
        self.is_loading_async = False

    def trigger_table_error(self):
        """Trigger table error."""
        self.is_loading_table = True

        try:
            raise Exception("Failed to fetch table data")
        except Exception as e:
            self.has_table_error = True
            self.table_error_message = "Database query failed. Please try again."
        finally:
            self.is_loading_table = False

    def load_table_success(self):
        """Load table data successfully."""
        self.is_loading_table = True
        self.has_table_error = False

        import time
        time.sleep(0.5)

        self.table_data = [
            {"name": "Item 1", "value": 100},
            {"name": "Item 2", "value": 200},
            {"name": "Item 3", "value": 300},
        ]
        self.is_loading_table = False

    def trigger_chart_error(self):
        """Trigger chart error."""
        self.is_loading_chart = True

        try:
            raise Exception("Chart rendering failed")
        except Exception as e:
            self.has_chart_error = True
            self.chart_error_message = "Failed to generate chart. Data may be invalid."
        finally:
            self.is_loading_chart = False

    def load_chart_success(self):
        """Load chart successfully."""
        self.is_loading_chart = True
        self.has_chart_error = False

        import time
        import json
        time.sleep(0.5)

        # Create a simple bar chart
        fig = px.bar(
            x=["A", "B", "C"],
            y=[10, 20, 15],
            title="Test Chart",
        )
        self.chart_data = json.loads(fig.to_json())
        self.is_loading_chart = False

    def test_retry_with_backoff(self):
        """Test retry mechanism."""
        attempt = 0

        def failing_function():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise Exception(f"Attempt {attempt} failed")
            return "Success!"

        try:
            result = ErrorRecovery.retry_with_backoff(
                failing_function,
                max_attempts=3,
                initial_delay=0.5,
                category=ErrorCategory.NETWORK,
            )
            return result
        except Exception as e:
            self.set_error(e, ErrorCategory.NETWORK)


class FormTestState(rx.State):
    """Test state for form validation."""

    # Form validation tracking (inline since ValidationErrorState was removed)
    field_errors: dict = {}
    has_validation_errors: bool = False

    email: str = ""
    name: str = ""
    submit_error: str = ""

    def validate_email(self, email: str) -> tuple[bool, str]:
        """Validate email."""
        if not email:
            return False, "Email is required"
        if "@" not in email:
            return False, "Invalid email format"
        return True, ""

    def validate_name(self, name: str) -> tuple[bool, str]:
        """Validate name."""
        if not name:
            return False, "Name is required"
        if len(name) < 3:
            return False, "Name must be at least 3 characters"
        return True, ""

    def submit_form(self):
        """Submit form with validation."""
        self.clear_all_field_errors()
        self.submit_error = ""

        # Validate all fields
        email_valid = self.validate_field("email", self.email, [self.validate_email])
        name_valid = self.validate_field("name", self.name, [self.validate_name])

        if not email_valid or not name_valid:
            return

        # Simulate submission success
        self.submit_error = ""
        # Reset form
        self.email = ""
        self.name = ""


def error_boundary_test_page() -> rx.Component:
    """Test page for error boundaries."""
    return layout(
        rx.vstack(
            rx.heading("🛡️ Error Boundary Test Suite", size="8"),
            rx.text(
                "This page demonstrates error boundary functionality. "
                "Click buttons to trigger various error scenarios.",
                color="gray.500",
            ),

            # Section 1: Section Error Boundary
            rx.card(
                rx.vstack(
                    rx.heading("1. Section Error Boundary", size="6"),
                    rx.hstack(
                        rx.button(
                            "Trigger Error",
                            on_click=ErrorBoundaryTestState.trigger_section_error,
                            color_scheme="red",
                        ),
                        rx.button(
                            "Clear Error",
                            on_click=ErrorBoundaryTestState.clear_section_error,
                            color_scheme="green",
                        ),
                        spacing="2",
                    ),
                    section_error_boundary(
                        content=rx.box(
                            rx.text("✅ Section loaded successfully!"),
                            padding="4",
                            bg="green.900",
                            border_radius="md",
                        ),
                        error_var=ErrorBoundaryTestState.section_has_error,
                        error_message_var=ErrorBoundaryTestState.section_error_message,
                        retry_action=ErrorBoundaryTestState.clear_section_error,
                        section_name="Test Section",
                    ),
                    spacing="4",
                    width="100%",
                ),
                width="100%",
            ),

            # Section 2: Async Operation Wrapper
            rx.card(
                rx.vstack(
                    rx.heading("2. Async Operation Wrapper", size="6"),
                    rx.hstack(
                        rx.button(
                            "Trigger Error",
                            on_click=ErrorBoundaryTestState.trigger_async_error,
                            color_scheme="red",
                        ),
                        rx.button(
                            "Load Success",
                            on_click=ErrorBoundaryTestState.load_async_success,
                            color_scheme="green",
                        ),
                        spacing="2",
                    ),
                    async_operation_wrapper(
                        content=rx.vstack(
                            rx.foreach(
                                ErrorBoundaryTestState.async_data,
                                lambda item: rx.text(item),
                            ),
                            spacing="2",
                        ),
                        is_loading_var=ErrorBoundaryTestState.is_loading_async,
                        has_error_var=ErrorBoundaryTestState.has_error,
                        error_message_var=ErrorBoundaryTestState.error_message,
                        retry_action=ErrorBoundaryTestState.load_async_success,
                        loading_text="Loading async data...",
                    ),
                    spacing="4",
                    width="100%",
                ),
                width="100%",
            ),

            # Section 3: Data Table Error Boundary
            rx.card(
                rx.vstack(
                    rx.heading("3. Data Table Error Boundary", size="6"),
                    rx.hstack(
                        rx.button(
                            "Trigger Error",
                            on_click=ErrorBoundaryTestState.trigger_table_error,
                            color_scheme="red",
                        ),
                        rx.button(
                            "Load Success",
                            on_click=ErrorBoundaryTestState.load_table_success,
                            color_scheme="green",
                        ),
                        spacing="2",
                    ),
                    data_table_error_boundary(
                        table_content=rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Name"),
                                    rx.table.column_header_cell("Value"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    ErrorBoundaryTestState.table_data,
                                    lambda row: rx.table.row(
                                        rx.table.cell(row["name"]),
                                        rx.table.cell(row["value"]),
                                    ),
                                )
                            ),
                        ),
                        is_loading_var=ErrorBoundaryTestState.is_loading_table,
                        has_error_var=ErrorBoundaryTestState.has_table_error,
                        error_message_var=ErrorBoundaryTestState.table_error_message,
                        is_empty_var=ErrorBoundaryTestState.table_data.length() == 0,
                        retry_action=ErrorBoundaryTestState.load_table_success,
                        empty_message="No data in table",
                    ),
                    spacing="4",
                    width="100%",
                ),
                width="100%",
            ),

            # Section 4: Chart Error Boundary
            rx.card(
                rx.vstack(
                    rx.heading("4. Chart Error Boundary", size="6"),
                    rx.hstack(
                        rx.button(
                            "Trigger Error",
                            on_click=ErrorBoundaryTestState.trigger_chart_error,
                            color_scheme="red",
                        ),
                        rx.button(
                            "Load Success",
                            on_click=ErrorBoundaryTestState.load_chart_success,
                            color_scheme="green",
                        ),
                        spacing="2",
                    ),
                    chart_error_boundary(
                        chart_content=rx.plotly(data=ErrorBoundaryTestState.chart_data),
                        is_loading_var=ErrorBoundaryTestState.is_loading_chart,
                        has_error_var=ErrorBoundaryTestState.has_chart_error,
                        error_message_var=ErrorBoundaryTestState.chart_error_message,
                        retry_action=ErrorBoundaryTestState.load_chart_success,
                        height="300px",
                    ),
                    spacing="4",
                    width="100%",
                ),
                width="100%",
            ),

            # Section 5: Form Error Boundary
            rx.card(
                rx.vstack(
                    rx.heading("5. Form Validation", size="6"),
                    form_error_boundary(
                        form_content=rx.vstack(
                            rx.vstack(
                                rx.text("Name", size="2", weight="bold"),
                                rx.input(
                                    value=FormTestState.name,
                                    on_change=FormTestState.set_name,
                                    placeholder="Enter your name",
                                ),
                                rx.cond(
                                    FormTestState.get_field_error("name") != "",
                                    inline_error(FormTestState.get_field_error("name")),
                                    rx.fragment(),
                                ),
                                spacing="2",
                                width="100%",
                            ),
                            rx.vstack(
                                rx.text("Email", size="2", weight="bold"),
                                rx.input(
                                    value=FormTestState.email,
                                    on_change=FormTestState.set_email,
                                    placeholder="Enter your email",
                                ),
                                rx.cond(
                                    FormTestState.get_field_error("email") != "",
                                    inline_error(FormTestState.get_field_error("email")),
                                    rx.fragment(),
                                ),
                                spacing="2",
                                width="100%",
                            ),
                            rx.button(
                                "Submit",
                                on_click=FormTestState.submit_form,
                                width="100%",
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        error_var=FormTestState.has_error,
                        error_message_var=FormTestState.error_message,
                        show_inline=False,
                    ),
                    spacing="4",
                    width="100%",
                ),
                width="100%",
            ),

            # Section 6: Retry Mechanism
            rx.card(
                rx.vstack(
                    rx.heading("6. Retry with Backoff", size="6"),
                    rx.text("Tests automatic retry with exponential backoff", color="gray.500"),
                    rx.button(
                        "Test Retry Mechanism",
                        on_click=ErrorBoundaryTestState.test_retry_with_backoff,
                        color_scheme="blue",
                    ),
                    rx.cond(
                        ErrorBoundaryTestState.has_error,
                        error_callout(ErrorBoundaryTestState.error_message, severity="error"),
                        rx.fragment(),
                    ),
                    spacing="4",
                    width="100%",
                ),
                width="100%",
            ),

            spacing="6",
            width="100%",
        ),
        page_name="Error Boundary Test"
    )
