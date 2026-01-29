# Arkham Logging

Comprehensive logging system for SHATTERED with wide events, sampling, distributed tracing, and automatic data sanitization.

## Features

- **Structured Logging**: JSON-formatted logs with consistent fields
- **Wide Event Logging**: One comprehensive log entry per operation with full context
- **Distributed Tracing**: Automatic trace_id generation and propagation across services
- **Automatic Data Sanitization**: Protects sensitive user data without manual intervention
- **Configurable Sampling**: Tail sampling to reduce costs while keeping important events
- **Multiple Outputs**: Console (colored), file (with rotation), and separate error logs
- **Non-Blocking I/O**: AsyncFileHandler with queue prevents log loss and reduces main thread overhead
- **Production Ready**: Log rotation, retention policies, graceful shutdown

## Quick Start

### Installation

```bash
cd packages/arkham-logging
pip install -e .
```

### Basic Usage

```python
from arkham_logging import get_logger, create_wide_event, log_operation

# Standard logging
logger = get_logger(__name__)
logger.info("Processing document")

# Wide event logging
event = create_wide_event("process_document")
event.input(document_id="doc_123", filename="report.pdf")
event.user(id="user_456", subscription="premium")
result = process_document()
event.output(page_count=10, ocr_confidence=0.95)
event.success()

# Context manager for automatic exception handling
with log_operation("process_document", document_id="doc_123") as event:
    event.input(filename="report.pdf")
    result = process_document()
    event.output(page_count=10)
```

## Configuration

Logging is configured via `config/shattered.yaml` or environment variables. See [USAGE.md](docs/USAGE.md) for detailed configuration options.

## Documentation

- [USAGE.md](docs/USAGE.md) - Detailed usage guide
- [WIDE_EVENTS.md](docs/WIDE_EVENTS.md) - Wide event logging guide
- [SAMPLING.md](docs/SAMPLING.md) - Sampling strategies guide
- [INTEGRATION.md](docs/INTEGRATION.md) - Integration with arkham-frame

## Key Concepts

### Wide Events

Instead of logging multiple lines throughout an operation, emit one comprehensive "wide event" with all context:

```python
event = create_wide_event("checkout")
event.input(cart_id="cart_xyz", item_count=3)
event.user(id="user_123", subscription="premium")
event.dependency("payment_api", duration_ms=450)
event.output(order_id="order_789", total_cents=15999)
event.success()
```

### Tail Sampling

Sample events after they complete based on outcome:
- Always keep errors (100%)
- Always keep slow requests (above threshold)
- Always keep VIP users/projects
- Randomly sample the rest (configurable rate)

### Distributed Tracing

Automatic trace_id propagation enables correlating logs across services:

```python
from arkham_logging.tracing import TracingContext

tracing = TracingContext()
trace_id = tracing.get_trace_id()  # Gets from context
tracing.set_trace_id("trace_abc123")  # Sets in context
headers = tracing.propagate_to_headers()  # For HTTP requests
```

### Data Sanitization

Automatic sanitization protects sensitive data:

```python
from arkham_logging.sanitizer import DataSanitizer

sanitizer = DataSanitizer()
data = {"password": "secret123", "email": "user@example.com"}
sanitized = sanitizer.sanitize(data)
# Result: {"password": "***", "email": "***"}
```

## Integration with arkham-frame

Arkham-logging is automatically integrated into arkham-frame. See [INTEGRATION.md](docs/INTEGRATION.md) for details.

## License

MIT
