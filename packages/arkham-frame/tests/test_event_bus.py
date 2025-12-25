"""
Integration tests for EventBus - event publishing and subscription system.

Tests subscription management, event publishing, async handler execution,
and event history.

Run with:
    cd packages/arkham-frame
    pytest tests/test_event_bus.py -v -s
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime
from typing import Dict, Any, List

from arkham_frame.services.events import (
    EventBus,
    Event,
    EventValidationError,
    EventDeliveryError,
)


# =============================================================================
# Test 1: Subscription Management
# =============================================================================

class TestSubscriptionManagement:
    """Test event subscription and unsubscription."""

    @pytest.mark.asyncio
    async def test_subscribe_to_event(self):
        """Should subscribe callback to event pattern."""
        bus = EventBus()
        await bus.initialize()

        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe("test.event", handler)

        await bus.emit("test.event", {"data": "value"}, source="test")

        await asyncio.sleep(0.1)  # Allow async processing
        assert len(received_events) == 1
        assert received_events[0]["event_type"] == "test.event"
        assert received_events[0]["payload"]["data"] == "value"

    @pytest.mark.asyncio
    async def test_unsubscribe_from_event(self):
        """Should unsubscribe callback from event."""
        bus = EventBus()
        await bus.initialize()

        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)

        await bus.emit("test.event", {"data": "value"}, source="test")

        await asyncio.sleep(0.1)
        assert len(received_events) == 0

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_event(self):
        """Multiple subscribers should all receive the same event."""
        bus = EventBus()
        await bus.initialize()

        handler1_events = []
        handler2_events = []
        handler3_events = []

        def handler1(event):
            handler1_events.append(event)

        def handler2(event):
            handler2_events.append(event)

        def handler3(event):
            handler3_events.append(event)

        bus.subscribe("multi.test", handler1)
        bus.subscribe("multi.test", handler2)
        bus.subscribe("multi.test", handler3)

        await bus.emit("multi.test", {"msg": "broadcast"}, source="test")

        await asyncio.sleep(0.1)
        assert len(handler1_events) == 1
        assert len(handler2_events) == 1
        assert len(handler3_events) == 1
        assert handler1_events[0]["payload"]["msg"] == "broadcast"
        assert handler2_events[0]["payload"]["msg"] == "broadcast"
        assert handler3_events[0]["payload"]["msg"] == "broadcast"

    @pytest.mark.asyncio
    async def test_wildcard_subscriptions(self):
        """Should support wildcard pattern matching."""
        bus = EventBus()
        await bus.initialize()

        received_events = []

        def handler(event):
            received_events.append(event)

        # Subscribe with wildcard
        bus.subscribe("user.*", handler)

        await bus.emit("user.created", {"id": 1}, source="test")
        await bus.emit("user.updated", {"id": 2}, source="test")
        await bus.emit("user.deleted", {"id": 3}, source="test")
        await bus.emit("admin.created", {"id": 4}, source="test")  # Should not match

        await asyncio.sleep(0.1)
        assert len(received_events) == 3
        assert received_events[0]["event_type"] == "user.created"
        assert received_events[1]["event_type"] == "user.updated"
        assert received_events[2]["event_type"] == "user.deleted"

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_callback(self):
        """Should handle unsubscribing nonexistent callback gracefully."""
        bus = EventBus()
        await bus.initialize()

        def handler(event):
            pass

        # Should not raise error
        bus.unsubscribe("test.event", handler)

    @pytest.mark.asyncio
    async def test_subscribe_multiple_patterns(self):
        """Should allow subscribing same handler to multiple patterns."""
        bus = EventBus()
        await bus.initialize()

        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe("pattern1.*", handler)
        bus.subscribe("pattern2.*", handler)

        await bus.emit("pattern1.event", {"id": 1}, source="test")
        await bus.emit("pattern2.event", {"id": 2}, source="test")

        await asyncio.sleep(0.1)
        assert len(received_events) == 2


# =============================================================================
# Test 2: Event Publishing
# =============================================================================

class TestEventPublishing:
    """Test event publishing and delivery."""

    @pytest.mark.asyncio
    async def test_publish_event_with_payload(self):
        """Should publish event with payload."""
        bus = EventBus()
        await bus.initialize()

        received_event = None

        def handler(event):
            nonlocal received_event
            received_event = event

        bus.subscribe("data.event", handler)

        test_payload = {
            "id": 123,
            "name": "Test Item",
            "metadata": {"key": "value"},
        }

        await bus.emit("data.event", test_payload, source="test-service")

        await asyncio.sleep(0.1)
        assert received_event is not None
        assert received_event["event_type"] == "data.event"
        assert received_event["payload"] == test_payload
        assert received_event["source"] == "test-service"

    @pytest.mark.asyncio
    async def test_publish_to_multiple_subscribers(self):
        """Should deliver event to all matching subscribers."""
        bus = EventBus()
        await bus.initialize()

        handler1_count = [0]
        handler2_count = [0]
        handler3_count = [0]

        def handler1(event):
            handler1_count[0] += 1

        def handler2(event):
            handler2_count[0] += 1

        def handler3(event):
            handler3_count[0] += 1

        bus.subscribe("broadcast.*", handler1)
        bus.subscribe("broadcast.test", handler2)
        bus.subscribe("*", handler3)

        await bus.emit("broadcast.test", {"msg": "hello"}, source="test")

        await asyncio.sleep(0.1)
        assert handler1_count[0] == 1  # Matches broadcast.*
        assert handler2_count[0] == 1  # Matches broadcast.test
        assert handler3_count[0] == 1  # Matches *

    @pytest.mark.asyncio
    async def test_publish_event_no_subscribers(self):
        """Should handle publishing event with no subscribers (no error)."""
        bus = EventBus()
        await bus.initialize()

        # Should not raise error
        await bus.emit("orphan.event", {"data": "value"}, source="test")

        await asyncio.sleep(0.1)
        # Just verify no crash

    @pytest.mark.asyncio
    async def test_event_sequence_numbers(self):
        """Events should have incrementing sequence numbers."""
        bus = EventBus()
        await bus.initialize()

        sequences = []

        def handler(event):
            sequences.append(event)

        bus.subscribe("seq.*", handler)

        await bus.emit("seq.1", {}, source="test")
        await bus.emit("seq.2", {}, source="test")
        await bus.emit("seq.3", {}, source="test")

        await asyncio.sleep(0.1)

        # Get events from history (they have sequence numbers)
        events = bus.get_events(limit=10)
        assert len(events) >= 3

        # Sequences should be increasing
        seqs = [e.sequence for e in events[:3]]
        assert seqs[0] < seqs[1] < seqs[2]


# =============================================================================
# Test 3: Async Handler Execution
# =============================================================================

class TestAsyncHandlerExecution:
    """Test async and sync handler execution."""

    @pytest.mark.asyncio
    async def test_async_handlers_are_awaited(self):
        """Async handlers should be properly awaited."""
        bus = EventBus()
        await bus.initialize()

        executed = []

        async def async_handler(event):
            await asyncio.sleep(0.05)
            executed.append("async")

        bus.subscribe("async.test", async_handler)

        await bus.emit("async.test", {"data": "value"}, source="test")

        await asyncio.sleep(0.2)  # Give time for async handler
        assert "async" in executed

    @pytest.mark.asyncio
    async def test_handler_exceptions_dont_break_other_handlers(self):
        """Exception in one handler should not prevent others from running."""
        bus = EventBus()
        await bus.initialize()

        executed = []

        def good_handler1(event):
            executed.append("good1")

        def bad_handler(event):
            executed.append("bad")
            raise ValueError("Handler failed!")

        def good_handler2(event):
            executed.append("good2")

        bus.subscribe("error.test", good_handler1)
        bus.subscribe("error.test", bad_handler)
        bus.subscribe("error.test", good_handler2)

        await bus.emit("error.test", {"data": "value"}, source="test")

        await asyncio.sleep(0.1)

        # All handlers should have been called despite the exception
        assert "good1" in executed
        assert "bad" in executed
        assert "good2" in executed

    @pytest.mark.asyncio
    async def test_handler_receives_correct_payload(self):
        """Handler should receive event with correct payload structure."""
        bus = EventBus()
        await bus.initialize()

        received = None

        def handler(event):
            nonlocal received
            received = event

        bus.subscribe("payload.test", handler)

        test_payload = {
            "user_id": 42,
            "action": "login",
            "timestamp": "2024-01-01T00:00:00Z",
        }

        await bus.emit("payload.test", test_payload, source="auth-service")

        await asyncio.sleep(0.1)

        assert received is not None
        assert received["event_type"] == "payload.test"
        assert received["payload"]["user_id"] == 42
        assert received["payload"]["action"] == "login"
        assert received["source"] == "auth-service"

    @pytest.mark.asyncio
    async def test_mixed_sync_and_async_handlers(self):
        """Should handle mix of sync and async handlers."""
        bus = EventBus()
        await bus.initialize()

        sync_executed = []
        async_executed = []

        def sync_handler(event):
            sync_executed.append(event["payload"]["id"])

        async def async_handler(event):
            await asyncio.sleep(0.05)
            async_executed.append(event["payload"]["id"])

        bus.subscribe("mixed.*", sync_handler)
        bus.subscribe("mixed.*", async_handler)

        await bus.emit("mixed.test", {"id": 1}, source="test")
        await bus.emit("mixed.test", {"id": 2}, source="test")

        await asyncio.sleep(0.2)

        assert sync_executed == [1, 2]
        assert async_executed == [1, 2]


# =============================================================================
# Test 4: Event History
# =============================================================================

class TestEventHistory:
    """Test event history logging and retrieval."""

    @pytest.mark.asyncio
    async def test_events_are_logged(self):
        """Published events should be stored in history."""
        bus = EventBus()
        await bus.initialize()

        await bus.emit("history.test1", {"id": 1}, source="test")
        await bus.emit("history.test2", {"id": 2}, source="test")
        await bus.emit("history.test3", {"id": 3}, source="test")

        events = bus.get_events(limit=10)

        assert len(events) >= 3
        # Events are inserted at the front, so most recent is first
        assert events[0].event_type == "history.test3"
        assert events[1].event_type == "history.test2"
        assert events[2].event_type == "history.test1"

    @pytest.mark.asyncio
    async def test_event_retrieval_with_limit(self):
        """Should respect limit when retrieving events."""
        bus = EventBus()
        await bus.initialize()

        # Publish 10 events
        for i in range(10):
            await bus.emit(f"limit.test{i}", {"id": i}, source="test")

        events = bus.get_events(limit=5)

        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_event_retrieval_by_source(self):
        """Should filter events by source."""
        bus = EventBus()
        await bus.initialize()

        await bus.emit("event1", {"id": 1}, source="service-a")
        await bus.emit("event2", {"id": 2}, source="service-b")
        await bus.emit("event3", {"id": 3}, source="service-a")
        await bus.emit("event4", {"id": 4}, source="service-c")

        events = bus.get_events(source="service-a", limit=10)

        assert len(events) == 2
        assert all(e.source == "service-a" for e in events)

    @pytest.mark.asyncio
    async def test_event_history_max_size(self):
        """Event history should be limited to max size."""
        bus = EventBus()
        bus._max_history = 100
        await bus.initialize()

        # Publish more than max_history events
        for i in range(150):
            await bus.emit(f"overflow.{i}", {"id": i}, source="test")

        events = bus.get_events(limit=200)

        # Should only keep last 100
        assert len(events) == 100

    @pytest.mark.asyncio
    async def test_event_has_timestamp(self):
        """Events should have timestamps."""
        bus = EventBus()
        await bus.initialize()

        before = datetime.utcnow()
        await bus.emit("timestamp.test", {"data": "value"}, source="test")
        after = datetime.utcnow()

        events = bus.get_events(limit=1)
        assert len(events) == 1

        event_time = events[0].timestamp
        assert before <= event_time <= after

    @pytest.mark.asyncio
    async def test_shutdown_clears_subscribers(self):
        """Shutdown should clear all subscribers."""
        bus = EventBus()
        await bus.initialize()

        received = []

        def handler(event):
            received.append(event)

        bus.subscribe("shutdown.test", handler)

        await bus.shutdown()

        # Subscribers should be cleared
        assert len(bus._subscribers) == 0


# =============================================================================
# Test 5: Integration Scenarios
# =============================================================================

class TestIntegrationScenarios:
    """Test real-world usage scenarios."""

    @pytest.mark.asyncio
    async def test_document_processing_pipeline(self):
        """Simulate document processing with multiple event handlers."""
        bus = EventBus()
        await bus.initialize()

        pipeline_state = {
            "ingested": [],
            "parsed": [],
            "embedded": [],
            "indexed": [],
        }

        def on_document_ingested(event):
            doc_id = event["payload"]["document_id"]
            pipeline_state["ingested"].append(doc_id)
            # Trigger next stage
            asyncio.create_task(
                bus.emit("document.parsed", {"document_id": doc_id}, source="parser")
            )

        def on_document_parsed(event):
            doc_id = event["payload"]["document_id"]
            pipeline_state["parsed"].append(doc_id)
            # Trigger next stage
            asyncio.create_task(
                bus.emit("document.embedded", {"document_id": doc_id}, source="embedder")
            )

        def on_document_embedded(event):
            doc_id = event["payload"]["document_id"]
            pipeline_state["embedded"].append(doc_id)
            # Trigger final stage
            asyncio.create_task(
                bus.emit("document.indexed", {"document_id": doc_id}, source="indexer")
            )

        def on_document_indexed(event):
            doc_id = event["payload"]["document_id"]
            pipeline_state["indexed"].append(doc_id)

        bus.subscribe("document.ingested", on_document_ingested)
        bus.subscribe("document.parsed", on_document_parsed)
        bus.subscribe("document.embedded", on_document_embedded)
        bus.subscribe("document.indexed", on_document_indexed)

        # Start pipeline
        await bus.emit("document.ingested", {"document_id": "doc-123"}, source="ingest")

        # Give pipeline time to complete
        await asyncio.sleep(0.3)

        assert "doc-123" in pipeline_state["ingested"]
        assert "doc-123" in pipeline_state["parsed"]
        assert "doc-123" in pipeline_state["embedded"]
        assert "doc-123" in pipeline_state["indexed"]

    @pytest.mark.asyncio
    async def test_shard_communication(self):
        """Simulate inter-shard communication via events."""
        bus = EventBus()
        await bus.initialize()

        ach_state = {"matrices": []}
        search_state = {"queries": []}

        async def ach_handler(event):
            # ACH shard receives document.processed event
            doc_id = event["payload"]["document_id"]
            matrix_id = f"matrix-{doc_id}"
            ach_state["matrices"].append(matrix_id)
            # ACH publishes its own event
            await bus.emit(
                "ach.matrix.created",
                {"matrix_id": matrix_id, "document_id": doc_id},
                source="arkham-shard-ach",
            )

        async def search_handler(event):
            # Search shard receives ach.matrix.created event
            matrix_id = event["payload"]["matrix_id"]
            search_state["queries"].append(f"query-{matrix_id}")

        bus.subscribe("document.processed", ach_handler)
        bus.subscribe("ach.matrix.created", search_handler)

        # Simulate document processing
        await bus.emit(
            "document.processed",
            {"document_id": "doc-456"},
            source="arkham-shard-ingest",
        )

        await asyncio.sleep(0.2)

        assert "matrix-doc-456" in ach_state["matrices"]
        assert "query-matrix-doc-456" in search_state["queries"]

    @pytest.mark.asyncio
    async def test_high_throughput_events(self):
        """Should handle high volume of events."""
        bus = EventBus()
        await bus.initialize()

        received_count = [0]

        def handler(event):
            received_count[0] += 1

        bus.subscribe("throughput.*", handler)

        # Emit 100 events rapidly
        for i in range(100):
            await bus.emit(f"throughput.event{i}", {"id": i}, source="test")

        await asyncio.sleep(0.5)

        assert received_count[0] == 100


# =============================================================================
# Smoke Test (can run directly)
# =============================================================================

async def smoke_test():
    """Quick smoke test for EventBus."""
    print("=" * 60)
    print("EventBus Smoke Test")
    print("=" * 60)

    print("\n1. Testing initialization...")
    bus = EventBus()
    await bus.initialize()
    print("   OK - EventBus initialized")

    print("\n2. Testing subscription...")
    received = []

    def handler(event):
        received.append(event)

    bus.subscribe("test.*", handler)
    print("   OK - Subscribed to test.*")

    print("\n3. Testing event publishing...")
    await bus.emit("test.event", {"message": "Hello, EventBus!"}, source="smoke-test")
    await asyncio.sleep(0.1)

    assert len(received) == 1
    assert received[0]["event_type"] == "test.event"
    assert received[0]["payload"]["message"] == "Hello, EventBus!"
    print("   OK - Event published and received")

    print("\n4. Testing event history...")
    events = bus.get_events(limit=10)
    assert len(events) >= 1
    assert events[0].event_type == "test.event"
    print(f"   OK - {len(events)} events in history")

    print("\n5. Testing async handlers...")
    async_received = []

    async def async_handler(event):
        await asyncio.sleep(0.05)
        async_received.append(event)

    bus.subscribe("async.test", async_handler)
    await bus.emit("async.test", {"async": True}, source="smoke-test")
    await asyncio.sleep(0.2)

    assert len(async_received) == 1
    print("   OK - Async handler executed")

    print("\n6. Testing shutdown...")
    await bus.shutdown()
    print("   OK - EventBus shut down")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(smoke_test())
    exit(0 if result else 1)
