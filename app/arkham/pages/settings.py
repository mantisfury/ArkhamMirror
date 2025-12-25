"""
Settings Page

Application settings, health dashboard, and data management.
"""

import reflex as rx
from ..components.layout import layout
from ..state.settings_state import SettingsState
from ..components.design_tokens import SPACING, CARD_PADDING


def status_icon(status: str) -> rx.Component:
    """Get the icon component for a status."""
    return rx.match(
        status,
        ("ok", rx.icon("circle-check", size=18, color="green.9")),
        ("warning", rx.icon("triangle-alert", size=18, color="yellow.9")),
        ("error", rx.icon("circle-x", size=18, color="red.9")),
        rx.icon("circle-help", size=18, color="gray.9"),
    )


def health_status_row(service: str, status_var, message_var) -> rx.Component:
    """Render a health status row for a service."""
    return rx.hstack(
        status_icon(status_var),
        rx.text(service, weight="medium", size="2"),
        rx.spacer(),
        rx.text(message_var, color="gray.11", size="1"),
        width="100%",
        padding_y="2",
    )


def health_check_card() -> rx.Component:
    """Health check dashboard card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("System Health", size="4"),
                rx.spacer(),
                rx.button(
                    rx.cond(
                        SettingsState.health_loading,
                        rx.spinner(size="1"),
                        rx.icon("refresh-cw", size=14),
                    ),
                    "Check",
                    size="1",
                    variant="soft",
                    on_click=SettingsState.check_health_status,
                    loading=SettingsState.health_loading,
                ),
                width="100%",
            ),
            rx.divider(),
            rx.cond(
                SettingsState.health_status,
                rx.vstack(
                    health_status_row(
                        "PostgreSQL", SettingsState.pg_status, SettingsState.pg_message
                    ),
                    health_status_row(
                        "Qdrant",
                        SettingsState.qdrant_status,
                        SettingsState.qdrant_message,
                    ),
                    health_status_row(
                        "Redis", SettingsState.redis_status, SettingsState.redis_message
                    ),
                    health_status_row(
                        "LM Studio", SettingsState.lm_status, SettingsState.lm_message
                    ),
                    health_status_row(
                        "spaCy NER",
                        SettingsState.spacy_status,
                        SettingsState.spacy_message,
                    ),
                    width="100%",
                    spacing="1",
                ),
                rx.text(
                    "Click 'Check' to test all services",
                    color="gray.11",
                    size="2",
                    style={"fontStyle": "italic"},
                ),
            ),
            width="100%",
            spacing=SPACING["md"],
        ),
        width="100%",
        padding=CARD_PADDING,
    )


def wipe_option_checkbox(label: str, checked: bool, on_change) -> rx.Component:
    """A checkbox option for the wipe dialog."""
    return rx.hstack(
        rx.checkbox(
            checked=checked,
            on_change=on_change,
        ),
        rx.text(label, size="2"),
        spacing="2",
    )


def nuclear_wipe_dialog() -> rx.Component:
    """The nuclear wipe confirmation dialog."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon("trash-2", size=16),
                "Delete All Data",
                color_scheme="red",
                variant="soft",
                on_click=SettingsState.open_wipe_dialog,
            ),
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title(
                rx.hstack(
                    rx.icon("triangle-alert", color="red.9", size=24),
                    "Nuclear Wipe",
                    spacing="2",
                ),
            ),
            rx.alert_dialog.description(
                rx.vstack(
                    rx.callout(
                        "This action is IRREVERSIBLE. All your investigation data will be permanently destroyed.",
                        icon="triangle-alert",
                        color="red",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text(
                                "This is a CONVENIENCE DELETE, not forensically secure.",
                                weight="bold",
                            ),
                            rx.text(
                                "For forensic-resistant deletion (secure overwrite, volume destruction), "
                                "stop the app and run: python scripts/forensic_wipe.py --confirm",
                                size="1",
                            ),
                            spacing="1",
                        ),
                        icon="shield-alert",
                        color="orange",
                    ),
                    # Data stats
                    rx.card(
                        rx.vstack(
                            rx.text("Data to be deleted:", weight="medium", size="2"),
                            rx.hstack(
                                rx.text(SettingsState.total_files_display, size="2"),
                                rx.text(
                                    SettingsState.total_size_display,
                                    color="gray.11",
                                    size="2",
                                ),
                                spacing="2",
                            ),
                            width="100%",
                            spacing="1",
                        ),
                        width="100%",
                    ),
                    # Wipe options
                    rx.card(
                        rx.vstack(
                            rx.text("What to delete:", weight="medium", size="2"),
                            wipe_option_checkbox(
                                "Files (documents, pages, logs)",
                                SettingsState.wipe_files,
                                SettingsState.toggle_wipe_files,
                            ),
                            wipe_option_checkbox(
                                "Database records",
                                SettingsState.wipe_database,
                                SettingsState.toggle_wipe_database,
                            ),
                            wipe_option_checkbox(
                                "Vector embeddings",
                                SettingsState.wipe_vectors,
                                SettingsState.toggle_wipe_vectors,
                            ),
                            wipe_option_checkbox(
                                "Job queue",
                                SettingsState.wipe_queue,
                                SettingsState.toggle_wipe_queue,
                            ),
                            width="100%",
                            spacing="2",
                        ),
                        width="100%",
                    ),
                    # Confirmation input
                    rx.vstack(
                        rx.text(
                            "Type 'DELETE ALL DATA' to confirm:",
                            size="2",
                            weight="medium",
                        ),
                        rx.input(
                            placeholder="DELETE ALL DATA",
                            value=SettingsState.wipe_confirmation_text,
                            on_change=SettingsState.set_confirmation_text,
                            width="100%",
                        ),
                        width="100%",
                        spacing="2",
                    ),
                    # Error message
                    rx.cond(
                        SettingsState.wipe_error != "",
                        rx.callout(
                            SettingsState.wipe_error,
                            icon="triangle-alert",
                            color="orange",
                        ),
                        rx.fragment(),
                    ),
                    # Success message
                    rx.cond(
                        SettingsState.wipe_success,
                        rx.callout(
                            rx.vstack(
                                rx.text(
                                    "All data has been destroyed.", weight="medium"
                                ),
                                rx.text(
                                    SettingsState.wipe_files_deleted.to_string()
                                    + " files deleted",
                                    size="1",
                                ),
                                spacing="1",
                            ),
                            icon="circle-check",
                            color="green",
                        ),
                        rx.fragment(),
                    ),
                    spacing=SPACING["md"],
                    width="100%",
                ),
            ),
            rx.flex(
                rx.alert_dialog.cancel(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=SettingsState.close_wipe_dialog,
                    ),
                ),
                rx.alert_dialog.action(
                    rx.button(
                        rx.cond(
                            SettingsState.wipe_in_progress,
                            rx.spinner(size="1"),
                            rx.icon("trash-2", size=14),
                        ),
                        "Destroy All Data",
                        color_scheme="red",
                        disabled=~SettingsState.can_wipe,
                        loading=SettingsState.wipe_in_progress,
                        on_click=SettingsState.execute_nuclear_wipe,
                    ),
                ),
                spacing="3",
                justify="end",
                margin_top="4",
            ),
            max_width="500px",
        ),
        open=SettingsState.wipe_dialog_open,
    )


def support_card() -> rx.Component:
    """Support the project card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("heart", color="red.9", size=20),
                rx.heading("Support the Project", size="4"),
                spacing="2",
            ),
            rx.divider(),
            rx.text(
                "ArkhamMirror is built to give journalists and researchers powerful forensics without cloud costs or privacy risks.",
                color="gray.11",
                size="2",
            ),
            rx.text(
                "If this tool helps you uncover the truth, consider supporting development!",
                color="gray.11",
                size="2",
            ),
            rx.link(
                rx.button(
                    rx.icon("coffee", size=16),
                    "Buy me a coffee on Ko-fi",
                    color_scheme="pink",
                    variant="soft",
                    size="2",
                ),
                href="https://ko-fi.com/arkhammirror",
                is_external=True,
            ),
            width="100%",
            spacing=SPACING["md"],
        ),
        width="100%",
        padding=CARD_PADDING,
    )


def danger_zone_card() -> rx.Component:
    """Danger zone card with nuclear wipe."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("skull", color="red.9", size=20),
                rx.heading("Danger Zone", size="4", color="red.9"),
                spacing="2",
            ),
            rx.divider(),
            rx.hstack(
                rx.vstack(
                    rx.text("Nuclear Wipe", weight="medium", size="2"),
                    rx.text(
                        "Permanently delete all documents, entities, embeddings, and job history.",
                        color="gray.11",
                        size="1",
                    ),
                    align_items="start",
                    spacing="1",
                ),
                rx.spacer(),
                nuclear_wipe_dialog(),
                width="100%",
                align="center",
            ),
            width="100%",
            spacing=SPACING["md"],
        ),
        width="100%",
        padding=CARD_PADDING,
        style={"borderColor": "var(--red-6)"},
    )


def anomaly_keywords_card() -> rx.Component:
    """Card for managing anomaly detection keywords."""
    return rx.card(
        rx.vstack(
            rx.heading("Anomaly Keywords", size="4"),
            rx.text(
                "Define keywords that flag document chunks as suspicious.",
                color="gray.11",
                size="1",
            ),
            rx.divider(),
            # Add new keyword form
            rx.hstack(
                rx.input(
                    placeholder="Keyword (e.g., confidential)",
                    value=SettingsState.new_keyword,
                    on_change=SettingsState.set_new_keyword,
                    width="100%",
                ),
                rx.input(
                    placeholder="Weight (0.1 - 1.0)",
                    value=SettingsState.new_weight,
                    on_change=SettingsState.set_new_weight,
                    width="100px",
                    type="number",
                    step="0.1",
                ),
                rx.button(
                    rx.icon("plus", size=16),
                    "Add",
                    on_click=SettingsState.add_keyword,
                    loading=SettingsState.is_keywords_loading,
                ),
                width="100%",
            ),
            # Keywords list
            rx.vstack(
                rx.foreach(
                    SettingsState.keywords,
                    lambda k: rx.hstack(
                        rx.text(k.keyword, weight="medium"),
                        rx.spacer(),
                        rx.badge(f"Weight: {k.weight}", variant="soft"),
                        rx.switch(
                            checked=k.is_active,
                            on_change=lambda _: SettingsState.toggle_keyword(k.id),
                        ),
                        rx.button(
                            rx.icon("trash-2", size=14),
                            size="1",
                            variant="ghost",
                            color_scheme="red",
                            on_click=lambda: SettingsState.delete_keyword(k.id),
                        ),
                        width="100%",
                        padding="2",
                        border_bottom="1px solid var(--gray-a3)",
                    ),
                ),
                max_height="300px",
                overflow_y="auto",
                width="100%",
            ),
            spacing=SPACING["md"],
        ),
        width="100%",
        padding=CARD_PADDING,
        on_mount=SettingsState.load_keywords,
    )


def settings_page() -> rx.Component:
    """Settings page."""
    return layout(
        rx.vstack(
            rx.heading("Settings", size="8"),
            # Health Check Dashboard
            health_check_card(),
            # Anomaly Keywords
            anomaly_keywords_card(),
            # Support the Project
            support_card(),
            # Danger Zone
            danger_zone_card(),
            spacing=SPACING["md"],
            width="100%",
        ),
        # Load health status on page load
        on_mount=SettingsState.check_health_status,
    )
