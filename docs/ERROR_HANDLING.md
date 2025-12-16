# Error Handling Guide for ArkhamMirror Reflex

This guide explains how to use the centralized error handling system in ArkhamMirror.

## Overview

The error handling system provides:
- **Centralized logging** with error IDs for tracking
- **User-friendly error messages** categorized by error type
- **Consistent error display** components
- **Context tracking** for debugging

## Quick Start

### Basic Error Handling in State Methods

```python
async def my_async_method(self):
    """Example async method with error handling."""
    self.is_loading = True
    yield

    try:
        # Your code here
        result = await some_operation()

    except Exception as e:
        from ..utils.error_handler import handle_database_error, format_error_for_ui
        from ..state.toast_state import ToastState

        # Log error and get user message
        error_info = handle_database_error(
            e,
            error_type="timeout" if "timeout" in str(e).lower() else "default",
            context={
                "action": "my_operation",
                "user_input": self.some_value,
            },
        )

        # Show error to user
        toast_state = await self.get_state(ToastState)
        toast_state.show_error(format_error_for_ui(error_info))

    finally:
        self.is_loading = False
```

## Error Categories

The system recognizes these error categories:

| Category | Use For | Handler Function |
|----------|---------|------------------|
| `DATABASE` | PostgreSQL, Qdrant queries | `handle_database_error()` |
| `NETWORK` | HTTP requests, API calls | `handle_network_error()` |
| `FILE_IO` | File read/write, permissions | `handle_file_error()` |
| `PROCESSING` | OCR, parsing, embeddings | `handle_processing_error()` |
| `VALIDATION` | Input validation | `ErrorHandler.handle_error()` |
| `UNKNOWN` | Catch-all | `ErrorHandler.handle_error()` |

## Error Types

Each category has specific error types:

### Database Errors
- `"connection"` - Cannot connect to database
- `"timeout"` - Query timed out
- `"not_found"` - Record not found
- `"default"` - General database error

### Network Errors
- `"connection"` - Cannot connect to service
- `"timeout"` - Request timed out
- `"default"` - General network error

### File I/O Errors
- `"not_found"` - File not found
- `"permission"` - Permission denied
- `"disk_full"` - Disk full
- `"default"` - General file error

### Processing Errors
- `"ocr_failed"` - OCR processing failed
- `"embedding_failed"` - Embedding generation failed
- `"parsing_failed"` - Document parsing failed
- `"default"` - General processing error

## UI Components

### Error Callout (Recommended)

```python
from ..components.error_display import error_callout

# In your page component
rx.cond(
    State.has_error,
    error_callout(
        message=State.error_message,
        error_id=State.error_id,
        severity="error",
        show_retry=True,
        retry_action=State.retry_operation,
    ),
    # Your normal content
)
```

### Inline Error (For Forms)

```python
from ..components.error_display import inline_error

rx.vstack(
    rx.input(value=State.email, on_change=State.set_email),
    rx.cond(
        State.email_error != "",
        inline_error(State.email_error),
        rx.fragment(),
    ),
)
```

### Loading with Error Fallback

```python
from ..components.error_display import loading_with_error_fallback

loading_with_error_fallback(
    is_loading=State.is_loading,
    has_error=State.has_error,
    error_message=State.error_message,
    content=rx.vstack(
        # Your content here
    ),
)
```

### Full Error Page

```python
from ..components.error_display import error_page

# For critical failures
error_page(
    title="Critical Error",
    message="Failed to load essential data.",
    error_id=State.error_id,
    show_home_button=True,
)
```

## Logging

All errors are automatically logged to `logs/arkham_mirror.log` with:
- **Error ID** - Unique identifier for tracking
- **Timestamp** - When the error occurred
- **Category** - Error category
- **Context** - Additional debugging information
- **Full traceback** - For developers

### Log Format

```
2025-11-28 14:30:45 - ArkhamMirror - ERROR - [ERR-20251128-143045] DATABASE: Query timeout
Context: {'action': 'search', 'query': 'corruption', 'page': 1}
Traceback:
...
```

## Context

Always provide context when handling errors:

```python
error_info = handle_database_error(
    e,
    error_type="timeout",
    context={
        "action": "search",           # What the user was trying to do
        "query": self.query,          # Relevant state
        "page": self.current_page,    # Additional context
        "filters": self.active_filters, # Helpful for debugging
    },
)
```

## Best Practices

### DO 

1. **Use specific error categories**
   ```python
   handle_database_error(e)  # Good
   ```

2. **Provide detailed context**
   ```python
   context={"action": "export_csv", "row_count": 1000}
   ```

3. **Use appropriate error types**
   ```python
   error_type="permission" if "permission" in str(e).lower() else "default"
   ```

4. **Show user-friendly messages**
   ```python
   toast_state.show_error(format_error_for_ui(error_info))
   ```

5. **Always use try/finally for loading states**
   ```python
   try:
       # operation
   except Exception as e:
       # handle error
   finally:
       self.is_loading = False  # Always reset
   ```

### DON'T L

1. **Don't show raw exception messages to users**
   ```python
   toast_state.show_error(str(e))  # Bad - confusing for users
   ```

2. **Don't silently catch errors**
   ```python
   try:
       do_something()
   except:
       pass  # Bad - errors are lost
   ```

3. **Don't forget context**
   ```python
   handle_database_error(e)  # Missing context parameter
   ```

4. **Don't expose sensitive data in errors**
   ```python
   context={"password": user_password}  # Bad - security issue
   ```

## Debug Mode

Set `DEBUG=true` in your `.env` file to show technical details in error messages:

```bash
DEBUG=true
```

Users will see:
```
Database connection issue. Please check your connection and try again.

Technical details: psycopg2.OperationalError: connection timeout
```

## Testing Error Handling

Force errors for testing:

```python
# In your state method
if os.getenv("TEST_ERROR") == "database":
    raise Exception("Simulated database error")
```

Then test with:
```bash
TEST_ERROR=database reflex run
```

## Migration Checklist

When updating existing code:

- [ ] Replace `print(f"Error: {e}")` with centralized error handling
- [ ] Replace `str(e)` in toast messages with `format_error_for_ui(error_info)`
- [ ] Add context to all error handlers
- [ ] Use appropriate error category (database, network, file, processing)
- [ ] Test error scenarios (timeout, permission denied, not found)
- [ ] Verify error logs are created
- [ ] Ensure loading states are always reset in `finally` blocks

## Examples

### Example 1: Database Query

```python
async def load_documents(self):
    self.is_loading = True
    yield

    try:
        from ..services.document_service import get_all_documents
        import asyncio
        from functools import partial

        loop = asyncio.get_event_loop()
        self.documents = await loop.run_in_executor(
            None,
            partial(get_all_documents, project_id=self.project_id)
        )

    except Exception as e:
        from ..utils.error_handler import handle_database_error, format_error_for_ui
        from ..state.toast_state import ToastState

        error_info = handle_database_error(
            e,
            error_type="connection" if "connect" in str(e).lower() else "default",
            context={
                "action": "load_documents",
                "project_id": self.project_id,
            },
        )

        toast_state = await self.get_state(ToastState)
        toast_state.show_error(format_error_for_ui(error_info))

    finally:
        self.is_loading = False
```

### Example 2: File Export

```python
async def export_data(self):
    try:
        import csv
        from datetime import datetime
        import os

        os.makedirs("exports", exist_ok=True)
        filename = f"exports/data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Column1", "Column2"])
            # Write data...

        from ..state.toast_state import ToastState
        toast_state = await self.get_state(ToastState)
        toast_state.show_success(f"Exported to {filename}")

    except Exception as e:
        from ..utils.error_handler import handle_file_error, format_error_for_ui
        from ..state.toast_state import ToastState

        error_info = handle_file_error(
            e,
            error_type="permission" if "permission" in str(e).lower()
                      else "disk_full" if "space" in str(e).lower()
                      else "default",
            context={
                "action": "export_csv",
                "filename": filename if 'filename' in locals() else "unknown",
            },
        )

        toast_state = await self.get_state(ToastState)
        toast_state.show_error(format_error_for_ui(error_info, show_error_id=False))
```

### Example 3: Processing Operation

```python
async def run_ocr(self):
    self.is_processing = True
    yield

    try:
        from ..services.ocr_service import process_document
        import asyncio
        from functools import partial

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(process_document, self.document_path)
        )

        self.ocr_text = result["text"]

    except Exception as e:
        from ..utils.error_handler import handle_processing_error, format_error_for_ui
        from ..state.toast_state import ToastState

        error_info = handle_processing_error(
            e,
            error_type="ocr_failed",
            context={
                "action": "run_ocr",
                "document_path": self.document_path,
                "document_type": self.document_type,
            },
        )

        toast_state = await self.get_state(ToastState)
        toast_state.show_error(format_error_for_ui(error_info))

    finally:
        self.is_processing = False
```

## Summary

1. **Always use centralized error handlers** - Don't reinvent error handling
2. **Provide context** - Makes debugging exponentially easier
3. **Use user-friendly messages** - Don't show raw exceptions
4. **Log everything** - Errors are automatically logged with IDs
5. **Reset state in finally blocks** - Prevent UI from getting stuck
6. **Test error scenarios** - Make sure errors are handled gracefully

---

For questions or issues, check the error logs at `logs/arkham_mirror.log` or search for error IDs.
