"""
Welcome Modal Component

Displays a first-run welcome screen when the database has no documents.
Provides quick start guidance and system health status.
"""

import reflex as rx


class WelcomeState(rx.State):
    """State for the welcome modal."""

    is_first_run: bool = False
    show_welcome: bool = False
    document_count: int = -1  # -1 means not checked yet

    async def check_first_run(self):
        """Check if this is a first run (no documents)."""
        try:
            from sqlalchemy import create_engine, text
            from config import DATABASE_URL

            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
                self.document_count = result or 0
                self.is_first_run = self.document_count == 0
                self.show_welcome = self.is_first_run
        except Exception:
            # If we can't connect, don't show welcome
            self.is_first_run = False
            self.show_welcome = False

    def dismiss_welcome(self):
        """Close the welcome modal."""
        self.show_welcome = False

    def go_to_ingest(self):
        """Navigate to ingest page and close modal."""
        self.show_welcome = False
        return rx.redirect("/ingest")


def feature_item(icon: str, title: str, description: str) -> rx.Component:
    """A feature highlight item."""
    return rx.hstack(
        rx.icon(icon, size=20, color="blue.9"),
        rx.vstack(
            rx.text(title, weight="medium", size="2"),
            rx.text(description, color="gray.11", size="1"),
            spacing="0",
            align_items="start",
        ),
        spacing="3",
        width="100%",
        padding="2",
    )


def welcome_modal() -> rx.Component:
    """
    Welcome modal that appears on first run.

    Add this component to your main app or layout to show the welcome screen.
    """
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.icon("shield-check", size=32, color="blue.9"),
                    rx.vstack(
                        rx.heading("Welcome to ArkhamMirror", size="6"),
                        rx.text(
                            "100% Local Investigation Platform",
                            color="gray.11",
                            size="2",
                        ),
                        spacing="0",
                        align_items="start",
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.divider(),
                # Quick start
                rx.vstack(
                    rx.heading("Quick Start", size="4"),
                    feature_item(
                        "upload",
                        "1. Ingest Documents",
                        "Upload PDFs, images, or emails to begin your investigation",
                    ),
                    feature_item(
                        "search",
                        "2. Search & Explore",
                        "Use semantic search to find information by meaning, not just keywords",
                    ),
                    feature_item(
                        "users",
                        "3. Discover Entities",
                        "Automatically extract people, organizations, and locations",
                    ),
                    feature_item(
                        "message-circle",
                        "4. Chat with Data",
                        "Ask questions about your documents using local AI (requires LM Studio)",
                    ),
                    width="100%",
                    spacing="2",
                ),
                rx.divider(),
                # Privacy note
                rx.callout(
                    rx.vstack(
                        rx.text(
                            "Your data never leaves your machine.", weight="medium"
                        ),
                        rx.text(
                            "All processing happens locally. No cloud, no tracking, no subscriptions.",
                            size="1",
                        ),
                        spacing="1",
                    ),
                    icon="lock",
                    color="green",
                ),
                # Buttons
                rx.hstack(
                    rx.button(
                        "Skip for now",
                        variant="soft",
                        color_scheme="gray",
                        on_click=WelcomeState.dismiss_welcome,
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon("upload", size=14),
                        "Get Started",
                        color_scheme="blue",
                        on_click=WelcomeState.go_to_ingest,
                    ),
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            max_width="500px",
            padding="6",
        ),
        open=WelcomeState.show_welcome,
    )
