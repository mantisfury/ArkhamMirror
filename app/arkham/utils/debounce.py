"""
Debounce Utilities for ArkhamMirror

Provides debouncing functionality for search inputs and other frequently-triggered
operations to reduce unnecessary backend calls and improve performance.
"""

from typing import Callable
import asyncio
from functools import wraps


class DebouncedState:
    """
    Mixin class that provides debouncing capabilities for Reflex state classes.

    Usage:
        class MyState(rx.State, DebouncedState):
            search_query: str = ""

            def set_search_query(self, value: str):
                self.search_query = value
                # Debounced search will be called after delay
                return self.debounced_search

            async def debounced_search(self):
                # This runs after debounce delay
                await self._execute_search()
    """

    _debounce_timers: dict = {}

    @staticmethod
    def debounce_delay_ms() -> int:
        """Override this to set custom debounce delay. Default: 300ms"""
        return 300


def debounced_handler(delay_ms: int = 300):
    """
    Decorator for creating debounced event handlers in Reflex.

    This creates a wrapper that delays execution until no new calls
    have been made for the specified delay period.

    Args:
        delay_ms: Delay in milliseconds before executing the handler

    Example:
        @debounced_handler(delay_ms=500)
        def on_search_change(self, query: str):
            self.search_query = query
            yield from self.execute_search()
    """

    def decorator(func: Callable) -> Callable:
        last_call_time = {"value": 0}

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            import time

            current_time = time.time() * 1000  # Convert to ms
            last_call_time["value"] = current_time

            # Wait for debounce period
            await asyncio.sleep(delay_ms / 1000)

            # Only execute if no newer call was made
            if last_call_time["value"] == current_time:
                result = func(self, *args, **kwargs)
                # Handle generator functions (yield from)
                if hasattr(result, "__iter__"):
                    for item in result:
                        yield item
                elif asyncio.iscoroutine(result):
                    await result

        return wrapper

    return decorator


class DebouncedInput:
    """
    Configuration class for debounced input behavior.

    Use with rx.input components to create debounced search fields:

    Example:
        rx.input(
            value=MyState.search_query,
            on_change=DebouncedInput.create_handler(
                MyState.set_search_query,
                delay_ms=300
            ),
            placeholder="Search...",
        )
    """

    @staticmethod
    def create_handler(
        immediate_handler: Callable,
        debounced_handler: Callable = None,
        delay_ms: int = 300,
    ):
        """
        Creates a handler that immediately updates state and optionally
        triggers a debounced action.

        Args:
            immediate_handler: Handler called immediately (e.g., update input value)
            debounced_handler: Optional handler called after debounce delay
            delay_ms: Debounce delay in milliseconds

        Returns:
            Handler function for on_change
        """
        # In Reflex, we handle debouncing differently - we use the immediate
        # handler and let the state method trigger the debounced action
        return immediate_handler


# Utility functions for common debounce patterns


def create_search_debouncer(delay_ms: int = 300):
    """
    Factory function to create a search debouncer.

    Returns a class that can be used as a mixin for search-related states.

    Example:
        SearchDebouncer = create_search_debouncer(300)

        class SearchState(rx.State, SearchDebouncer):
            ...
    """

    class SearchDebouncer:
        _search_pending: bool = False
        _last_search_id: int = 0

        async def _debounced_search_execute(
            self, search_id: int, search_func: Callable
        ):
            """Internal method to execute debounced search."""
            await asyncio.sleep(delay_ms / 1000)

            # Only execute if this is still the latest search
            if search_id == self._last_search_id:
                self._search_pending = True
                try:
                    result = search_func()
                    if asyncio.iscoroutine(result):
                        await result
                finally:
                    self._search_pending = False

    return SearchDebouncer


# Constants for common debounce timings
DEBOUNCE_FAST = 150  # For autocomplete, very responsive
DEBOUNCE_NORMAL = 300  # For search inputs, balanced
DEBOUNCE_SLOW = 500  # For expensive operations
DEBOUNCE_VERY_SLOW = 1000  # For very expensive operations (LLM calls)
