import reflex as rx
import asyncio


class ToastState(rx.State):
    """Global state for toast notifications."""

    show_toast: bool = False
    toast_message: str = ""
    toast_type: str = "info"  # info, success, error, warning
    auto_hide_delay: int = 5  # seconds

    def show_success(self, message: str):
        """Show a success toast."""
        self.toast_message = message
        self.toast_type = "success"
        self.show_toast = True
        return ToastState.auto_hide_toast

    def show_error(self, message: str):
        """Show an error toast."""
        self.toast_message = message
        self.toast_type = "error"
        self.show_toast = True
        return ToastState.auto_hide_toast

    def show_info(self, message: str):
        """Show an info toast."""
        self.toast_message = message
        self.toast_type = "info"
        self.show_toast = True
        return ToastState.auto_hide_toast

    def show_warning(self, message: str):
        """Show a warning toast."""
        self.toast_message = message
        self.toast_type = "warning"
        self.show_toast = True
        return ToastState.auto_hide_toast

    @rx.event(background=True)
    async def auto_hide_toast(self):
        """Auto-hide toast after delay (default 5 seconds)."""
        delay = self.auto_hide_delay
        await asyncio.sleep(delay)
        async with self:
            self.show_toast = False

    def hide_toast(self):
        """Manually hide the toast."""
        self.show_toast = False
