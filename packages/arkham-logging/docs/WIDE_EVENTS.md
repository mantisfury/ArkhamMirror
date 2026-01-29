# Wide Event Logging Guide

Guide to using wide events for comprehensive operation tracking.

## What are Wide Events?

Wide events are comprehensive log entries that capture all relevant context for an operation in a single event. Instead of logging multiple lines throughout an operation, you build one event with all the information you might need for debugging.

## Why Use Wide Events?

1. **Complete Context**: All information in one place
2. **Queryable**: Structured data enables powerful queries
3. **Correlation**: trace_id enables correlating events across services
4. **Cost Effective**: Sampling reduces volume while keeping important events

## Creating Wide Events

### Basic Example

```python
from arkham_logging import create_wide_event

event = create_wide_event("process_document")
event.input(document_id="doc_123", filename="report.pdf")
event.user(id="user_456", subscription="premium")
result = process_document()
event.output(page_count=10, ocr_confidence=0.95)
event.success()
```

### With Context Manager

```python
from arkham_logging import log_operation

with log_operation("process_document", document_id="doc_123") as event:
    event.input(filename="report.pdf", size_bytes=1024000)
    event.user(id="user_456")
    result = process_document()
    event.output(page_count=10, ocr_confidence=0.95)
```

## Adding Context

### User Context

```python
event.user(
    id="user_123",
    subscription="premium",
    account_age_days=365,
    lifetime_value_cents=50000,
)
```

### Input Context

```python
event.input(
    document_id="doc_123",
    filename="report.pdf",
    size_bytes=1024000,
    mime_type="application/pdf",
)
```

### Output Context

```python
event.output(
    page_count=10,
    ocr_confidence=0.95,
    entities_found=25,
    processing_time_ms=1234,
)
```

### Dependencies

Track external service calls:

```python
start = time.time()
result = call_external_api()
duration_ms = int((time.time() - start) * 1000)

event.dependency(
    "external_api",
    duration_ms=duration_ms,
    status_code=200,
    response_size_bytes=1024,
)
```

### Custom Context

```python
event.context("feature_flag", "new_checkout_flow")
event.context("deployment_id", "deploy_789")
event.context("region", "us-east-1")
```

## Error Handling

### Manual Error Logging

```python
try:
    result = process_document()
    event.success()
except Exception as e:
    event.error(
        code="ProcessingError",
        message=str(e),
        exception=e,
    )
    raise
```

### Automatic with Context Manager

```python
with log_operation("process_document", document_id=doc_id) as event:
    event.input(filename=filename)
    result = process_document()  # Exception automatically logged
    event.output(page_count=result.pages)
```

## Distributed Tracing

Wide events automatically include trace_id for correlation:

```python
from arkham_logging.tracing import TracingContext

tracing = TracingContext()
trace_id = tracing.get_trace_id()  # Gets from context

# Create event with trace_id
event = create_wide_event("process_document", trace_id=trace_id)
```

## Integration with FastAPI

The WideEventMiddleware automatically creates wide events for HTTP requests:

```python
# Middleware automatically creates events like:
{
  "service": "api_request",
  "trace_id": "trace_abc123",
  "input": {
    "method": "POST",
    "path": "/api/documents",
    "user_id": "user_456",
    "project_id": "project_789"
  },
  "output": {
    "status_code": 200
  },
  "duration_ms": 1234,
  "outcome": "success"
}
```

## Querying Wide Events

With structured logging, you can query events:

```python
# Find all errors for a user
# Query: user.id = "user_456" AND outcome = "error"

# Find slow requests
# Query: duration_ms > 2000

# Find checkout failures with new flow
# Query: service = "checkout" AND outcome = "error" AND feature_flag = "new_checkout_flow"
```

## Best Practices

1. **One event per operation**: Don't create multiple events for the same operation
2. **Include all context**: Add everything you might need for debugging
3. **Use meaningful service names**: `process_document` not `process`
4. **Track dependencies**: Log external service calls with timing
5. **Include user/project context**: Enables filtering by user/project
6. **Use status codes**: For HTTP operations, include status_code

## Examples

### Document Processing

```python
def process_document(doc_id: str, user_id: str):
    event = create_wide_event("process_document")
    event.input(document_id=doc_id, user_id=user_id)
    event.user(id=user_id)
    
    # OCR
    ocr_start = time.time()
    ocr_result = perform_ocr(doc_id)
    event.dependency("ocr", duration_ms=int((time.time() - ocr_start) * 1000))
    
    # Parsing
    parse_start = time.time()
    parse_result = parse_document(ocr_result)
    event.dependency("parse", duration_ms=int((time.time() - parse_start) * 1000))
    
    # Embedding
    embed_start = time.time()
    embeddings = create_embeddings(parse_result)
    event.dependency("embedding", duration_ms=int((time.time() - embed_start) * 1000))
    
    event.output(
        page_count=parse_result.pages,
        entities_found=len(parse_result.entities),
        embedding_count=len(embeddings),
    )
    event.success()
    return parse_result
```

### API Request

```python
@app.post("/api/documents")
async def create_document(request: Request):
    # Middleware automatically creates wide event
    # Add additional context
    event = request.state.wide_event  # If stored by middleware
    
    document = await create_document_from_request(request)
    event.output(document_id=document.id, status_code=201)
    return document
```
