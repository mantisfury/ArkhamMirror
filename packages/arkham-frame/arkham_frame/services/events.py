"""
EventBus - Event publishing and subscription.
"""

from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from dataclasses import dataclass, field
import logging
import fnmatch

logger = logging.getLogger(__name__)


class EventValidationError(Exception):
    """Event validation failed."""
    pass


class EventDeliveryError(Exception):
    """Event delivery failed."""
    pass


@dataclass
class Event:
    """An event in the system."""
    event_type: str
    payload: Dict[str, Any]
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sequence: int = 0


class EventBus:
    """
    Event bus for publish/subscribe messaging.
    """

    def __init__(self, config=None):
        self.config = config
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._sequence = 0
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize event bus."""
        self._initialized = True
        logger.info("EventBus initialized")

    async def shutdown(self) -> None:
        """Shutdown event bus."""
        self._initialized = False
        self._subscribers.clear()
        logger.info("EventBus shut down")

    def subscribe(self, pattern: str, callback: Callable) -> None:
        """Subscribe to events matching pattern."""
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(callback)

    def unsubscribe(self, pattern: str, callback: Callable) -> None:
        """Unsubscribe from events."""
        if pattern in self._subscribers:
            try:
                self._subscribers[pattern].remove(callback)
            except ValueError:
                pass

    async def emit(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: str,
    ) -> None:
        """Emit an event."""
        self._sequence += 1

        event = Event(
            event_type=event_type,
            payload=payload,
            source=source,
            sequence=self._sequence,
        )

        # Add to history
        self._event_history.insert(0, event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[:self._max_history]

        # Deliver to subscribers
        for pattern, callbacks in self._subscribers.items():
            if fnmatch.fnmatch(event_type, pattern):
                for callback in callbacks:
                    try:
                        if callable(callback):
                            result = callback({
                                "event_type": event_type,
                                "payload": payload,
                                "source": source,
                            })
                            # Handle async callbacks
                            if hasattr(result, "__await__"):
                                await result
                    except Exception as e:
                        logger.error(f"Event callback error: {e}")

    def get_events(
        self,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Get recent events."""
        events = self._event_history
        if source:
            events = [e for e in events if e.source == source]
        return events[:limit]
