# Integration Guide

Guide to integrating arkham-logging with arkham-frame and shards.

## Arkham-Frame Integration

Arkham-logging is automatically integrated into arkham-frame. The frame initializes logging during startup:

```python
# In ArkhamFrame.initialize()
from arkham_logging import LoggingManager, initialize as init_logging
from arkham_logging.tracing import TracingContext

config_path = os.environ.get("CONFIG_PATH", "config/shattered.yaml")
self.logging_manager = init_logging(config_path=config_path)
self.tracing = TracingContext()
```

## Using Logging in Shards

### Standard Logging

```python
from arkham_frame import get_logger

logger = get_logger(__name__)

class MyShard(ArkhamShard):
    async def initialize(self, frame):
        logger.info("Initializing MyShard")
```

### Wide Event Logging

```python
from arkham_frame import create_wide_event, log_operation

class MyShard(ArkhamShard):
    async def process_document(self, doc_id: str):
        # Option 1: Manual wide event
        event = self.frame.create_wide_event("process_document")
        event.input(document_id=doc_id)
        result = await do_work(doc_id)
        event.output(page_count=result.pages)
        event.success()
        
        # Option 2: Context manager
        with self.frame.log_operation("process_document", document_id=doc_id) as event:
            event.input(filename=get_filename(doc_id))
            result = await do_work(doc_id)
            event.output(page_count=result.pages)
```

## FastAPI Middleware

The WideEventMiddleware automatically logs HTTP requests:

```python
# Middleware is automatically added in main.py
# It creates wide events for all requests with:
# - Method, path, query params
# - User/project context from request.state
# - Response status code
# - Request duration
# - Automatic trace_id extraction/generation
```

## Distributed Tracing

### Extracting trace_id

```python
from arkham_logging.tracing import TracingContext

tracing = TracingContext()
trace_id = tracing.get_trace_id()  # Gets from context
```

### Propagating trace_id

For HTTP requests:

```python
from arkham_logging.tracing import TracingContext

tracing = TracingContext()
headers = tracing.propagate_to_headers()
# Returns: {"X-Trace-ID": "trace_abc123", "traceparent": "00-..."}

# Use in HTTP request
response = httpx.get(url, headers=headers)
```

### EventBus Integration

EventBus automatically includes trace_id in events:

```python
await frame.events.emit(
    "document.processed",
    {"document_id": doc_id},
    source="documents-shard",
)
# Event automatically includes trace_id from context
```

## Migration from Standard Logging

### Before

```python
import logging

logger = logging.getLogger(__name__)

def process_document(doc_id: str):
    logger.info(f"Processing document {doc_id}")
    try:
        result = do_work(doc_id)
        logger.info(f"Document {doc_id} processed successfully")
        return result
    except Exception as e:
        logger.error(f"Failed to process document {doc_id}: {e}", exc_info=True)
        raise
```

### After (Standard Logging)

```python
from arkham_frame import get_logger

logger = get_logger(__name__)

def process_document(doc_id: str):
    logger.info(f"Processing document {doc_id}")
    try:
        result = do_work(doc_id)
        logger.info(f"Document {doc_id} processed successfully")
        return result
    except Exception as e:
        logger.error(f"Failed to process document {doc_id}: {e}", exc_info=True)
        raise
```

### After (Wide Events)

```python
from arkham_frame import log_operation

def process_document(doc_id: str):
    with log_operation("process_document", document_id=doc_id) as event:
        event.input(filename=get_filename(doc_id))
        result = do_work(doc_id)
        event.output(page_count=result.pages)
        return result
```

## Best Practices

1. **Use frame utilities**: Access logging via `frame.get_logger()`, `frame.create_wide_event()`, etc.
2. **Include context**: Add user_id, project_id, document_id to events
3. **Use wide events for operations**: Use wide events for business operations, standard logging for debug messages
4. **Propagate trace_id**: Include trace_id in external HTTP requests
5. **Leverage middleware**: Let middleware handle request logging automatically

## Configuration

Configure logging in `config/shattered.yaml` or via environment variables. See [USAGE.md](USAGE.md) for details.

## Troubleshooting

### Logging not working

1. Check that arkham-logging is installed: `pip list | grep arkham-logging`
2. Check configuration: Verify `config/shattered.yaml` has logging section
3. Check logs: Look for "LoggingManager initialized" in startup logs

### Wide events not appearing

1. Check sampling: Verify `wide_events.enabled = true` and sampling_rate > 0
2. Check log level: Ensure log level includes INFO (wide events log at INFO)
3. Check file handler: Verify file handler is enabled and path is writable

### Trace_id not propagating

1. Check middleware: Ensure WideEventMiddleware is added to app
2. Check context: Verify TracingContext is initialized in frame
3. Check headers: Verify X-Trace-ID or traceparent headers are present
