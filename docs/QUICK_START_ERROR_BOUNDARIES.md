# Quick Start: Error Boundaries

Get started with error boundaries in 5 minutes.

## TL;DR

```python
# 1. Add mixin to your state class
from ..state.error_state import ErrorStateMixin

class MyState(ErrorStateMixin, rx.State):
    data: list = []

    async def load_data(self):
        self.set_loading(True)
        try:
            self.data = await fetch_data()
        except Exception as e:
            self.set_error(e, ErrorCategory.DATABASE, "connection")
        finally:
            self.set_loading(False)

# 2. Wrap your page content
from ..components.error_boundary import async_operation_wrapper

def my_page():
    return layout(
        async_operation_wrapper(
            content=render_my_data(),
            is_loading_var=MyState.is_loading,
            has_error_var=MyState.has_error,
            error_message_var=MyState.error_message,
            retry_action=MyState.load_data,
        )
    )
```

That's it! Your page now has:
- ✅ Loading spinner
- ✅ Error messages
- ✅ Retry button
- ✅ Error logging
- ✅ User-friendly messages

## Common Patterns

### Pattern 1: Simple Async Loading

```python
async_operation_wrapper(
    content=my_content,
    is_loading_var=MyState.is_loading,
    has_error_var=MyState.has_error,
    error_message_var=MyState.error_message,
    retry_action=MyState.retry_load,
)
```

### Pattern 2: Data Table

```python
data_table_error_boundary(
    table_content=my_table,
    is_loading_var=MyState.is_loading,
    has_error_var=MyState.has_error,
    error_message_var=MyState.error_message,
    is_empty_var=MyState.data.length() == 0,
    retry_action=MyState.load_data,
    empty_message="No data found",
)
```

### Pattern 3: Charts

```python
chart_error_boundary(
    chart_content=rx.plotly(data=MyState.chart_data),
    is_loading_var=MyState.is_loading,
    has_error_var=MyState.has_error,
    error_message_var=MyState.error_message,
    retry_action=MyState.load_chart,
    height="400px",
)
```

## Error Categories

Use the right category for better error messages:

```python
from ..utils.error_handler import ErrorCategory

# Database queries
self.set_error(e, ErrorCategory.DATABASE, "connection")
self.set_error(e, ErrorCategory.DATABASE, "timeout")
self.set_error(e, ErrorCategory.DATABASE, "not_found")

# Network requests
self.set_error(e, ErrorCategory.NETWORK, "timeout")
self.set_error(e, ErrorCategory.NETWORK, "connection")

# File operations
self.set_error(e, ErrorCategory.FILE_IO, "not_found")
self.set_error(e, ErrorCategory.FILE_IO, "permission")

# Processing
self.set_error(e, ErrorCategory.PROCESSING, "ocr_failed")
self.set_error(e, ErrorCategory.PROCESSING, "parsing_failed")
```

## Test It

1. Run the app: `reflex run`
2. Visit: `http://localhost:3000/test/error-boundaries`
3. Click "Trigger Error" buttons to see error boundaries in action

## Available Boundaries

| Boundary | Use Case | Key Features |
|----------|----------|--------------|
| `async_operation_wrapper` | Async data loading | Loading + Error + Content |
| `data_table_error_boundary` | Tables | Loading + Error + Empty + Content |
| `chart_error_boundary` | Charts/graphs | Loading + Error + Content |
| `section_error_boundary` | Page sections | Error + Retry |
| `form_error_boundary` | Forms | Validation errors |
| `critical_section_boundary` | Sidebar/nav | Minimal error display |

## Full Documentation

- **Usage Guide**: `ERROR_HANDLING_GUIDE.md`
- **Implementation**: `ERROR_BOUNDARIES_IMPLEMENTATION.md`
- **Example**: `pages/overview.py`
- **Test Page**: `pages/error_boundary_test.py`

## Need Help?

Check the test page or look at the Overview page implementation:

```bash
# View example implementation
code arkham_reflex/arkham_reflex/pages/overview.py
code arkham_reflex/arkham_reflex/state/overview_state.py
```
