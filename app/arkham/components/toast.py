import reflex as rx
from ..state.toast_state import ToastState


def toast() -> rx.Component:
    """Toast notification component."""

    # Color schemes for different toast types
    color_map = {
        "success": "green",
        "error": "red",
        "warning": "yellow",
        "info": "blue",
    }

    icon_map = {
        "success": "circle-check",
        "error": "circle-alert",
        "warning": "triangle-alert",
        "info": "info",
    }

    return rx.cond(
        ToastState.show_toast,
        rx.box(
            rx.hstack(
                rx.icon(
                    tag=icon_map.get(ToastState.toast_type, "info"),
                    size=20,
                    color="white",
                ),
                rx.text(
                    ToastState.toast_message,
                    color="white",
                    size="2",
                    weight="medium",
                ),
                rx.spacer(),
                rx.icon_button(
                    rx.icon(tag="x", size=16),
                    on_click=ToastState.hide_toast,
                    variant="ghost",
                    color_scheme=color_map.get(ToastState.toast_type, "blue"),
                    size="1",
                ),
                align="center",
                spacing="3",
                padding="3",
            ),
            position="fixed",
            top="20px",
            right="20px",
            z_index="9999",
            bg=f"{color_map.get(ToastState.toast_type, 'blue')}.600",
            border_radius="md",
            box_shadow="lg",
            min_width="300px",
            max_width="500px",
            animation="slideInRight 0.3s ease-out",
        ),
    )
