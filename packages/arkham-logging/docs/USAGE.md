# Usage Guide

Detailed guide for using arkham-logging.

## Getting Started

### Installation

```bash
cd packages/arkham-logging
pip install -e .
```

### Basic Logging

```python
from arkham_logging import get_logger

logger = get_logger(__name__)
logger.info("Application started")
logger.debug("Debug information")
logger.warning("Warning message")
logger.error("Error occurred")
```

## Configuration

### YAML Configuration

Configure logging in `config/shattered.yaml`:

```yaml
frame:
  logging:
    console:
      enabled: true
      level: INFO
      format: colored  # colored, standard, json
    
    file:
      enabled: true
      path: logs/arkham.log
      level: DEBUG
      max_bytes: 104857600  # 100MB
      backup_count: 10
      retention_days: 30
    
    error_file:
      enabled: true
      path: logs/errors.log
      level: ERROR
      max_bytes: 52428800  # 50MB
      backup_count: 5
    
    wide_events:
      enabled: true
      sampling_rate: 0.05  # 5% of normal requests
      tail_sampling: true
      always_sample_errors: true
      always_sample_slow: true
      slow_threshold_ms: 2000
      always_sample_users: []
      always_sample_projects: []
```

### Environment Variables

Override YAML config with environment variables:

```bash
ARKHAM_LOG_LEVEL=INFO
ARKHAM_LOG_CONSOLE_ENABLED=true
ARKHAM_LOG_CONSOLE_LEVEL=INFO
ARKHAM_LOG_CONSOLE_FORMAT=colored
ARKHAM_LOG_FILE_ENABLED=true
ARKHAM_LOG_FILE_PATH=logs/arkham.log
ARKHAM_LOG_WIDE_EVENTS_ENABLED=true
ARKHAM_LOG_WIDE_EVENTS_SAMPLING_RATE=0.05
```

## Log Levels

- **DEBUG**: Detailed information for debugging
- **INFO**: General informational messages
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical errors requiring immediate attention

## Error tracing

Every log line can include a **trace_id** when the current request has one (e.g. set by middleware from `X-Trace-ID` or generated per request). This lets you correlate all logs for a single request and filter by trace in your log aggregator.

- **Structured (JSON) formatter**: Adds a `trace_id` field to each log record when `get_trace_id()` returns a value.
- **Standard formatter**: Appends `[trace_id=...]` to the message when a trace is set.

For caught exceptions, use **log_error_with_context** so the error message and `extra` include trace_id and business context (e.g. `job_id`, `document_id`):

```python
from arkham_logging import log_error_with_context

try:
    await save_job(job)
except Exception as e:
    log_error_with_context(
        logger,
        "Failed to persist job to database",
        exc=e,
        job_id=job.id,
        filename=filename,
    )
    raise
```

Use **format_error_message** when building a message for re-raise or for a custom log:

```python
from arkham_logging import format_error_message

msg = format_error_message("Failed to persist job", exc=e, job_id=job.id)
raise RuntimeError(msg)
```

## Formatters

### Colored (Console)

Human-readable output with ANSI colors:

```
2025-01-15 10:23:45 - INFO - my_module:process_document:42 - Processing document doc_123
```

### Standard (Console)

Human-readable output without colors:

```
2025-01-15 10:23:45 - INFO - my_module:process_document:42 - Processing document doc_123
```

### JSON (File)

Structured JSON output:

```json
{
  "timestamp": "2025-01-15T10:23:45.612Z",
  "level": "INFO",
  "logger": "my_module",
  "message": "Processing document doc_123",
  "module": "my_module",
  "function": "process_document",
  "line": 42
}
```

## Handlers

### Console Handler

Outputs to stdout with optional colors. Configured via `console` section.

### File Handler

Writes to rotating log files. Uses AsyncFileHandler for non-blocking I/O.

**Configuration:**
- `path`: Log file path
- `level`: Minimum log level
- `max_bytes`: Maximum file size before rotation
- `backup_count`: Number of backup files to keep
- `retention_days`: Days to retain logs (None = forever)

### Error File Handler

Separate log file for errors only. Configured via `error_file` section.

## Best Practices

1. **Use appropriate log levels**: Don't log everything at INFO
2. **Include context**: Add relevant IDs, user info, etc.
3. **Use wide events**: For operations, use wide events instead of multiple log lines
4. **Sanitize sensitive data**: Automatic sanitization handles most cases, but be aware
5. **Configure sampling**: Adjust sampling rates based on volume and costs

## Examples

### Standard Logging

```python
from arkham_logging import get_logger

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

### Wide Event Logging

```python
from arkham_logging import create_wide_event

def process_document(doc_id: str, user_id: str):
    event = create_wide_event("process_document")
    event.input(document_id=doc_id)
    event.user(id=user_id)
    
    try:
        result = do_work(doc_id)
        event.output(page_count=result.pages, success=True)
        event.success()
        return result
    except Exception as e:
        event.error("ProcessingError", str(e), exception=e)
        raise
```

### Context Manager

```python
from arkham_logging import log_operation

def process_document(doc_id: str):
    with log_operation("process_document", document_id=doc_id) as event:
        event.input(filename=get_filename(doc_id))
        result = do_work(doc_id)
        event.output(page_count=result.pages)
        return result
```

### Service Decorator

```python
from arkham_logging.exception_handler import logged_service_call

class DocumentService:
    @logged_service_call("DocumentService")
    def process(self, doc_id: str):
        return do_work(doc_id)
```
