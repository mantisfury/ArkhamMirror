# Error Handling Guide for ArkhamMirror Reflex

This guide explains how to use the error boundary system for graceful error handling across the application.

## Overview

ArkhamMirror uses a comprehensive error handling system that includes:

1. **Error Boundaries** - Wrap components to catch and display errors gracefully
2. **Error State Mixin** - Standardized error tracking in state classes
3. **Error Recovery** - Retry mechanisms and fallback strategies
4. **Error Logging** - Centralized logging with error IDs for debugging

## Components Available

### Error Boundary Components

Located in `components/error_boundary.py`:

- `section_error_boundary` - For page sections
- `async_operation_wrapper` - For async data loading
- `form_error_boundary` - For form validation
- `data_table_error_boundary` - For tables with loading/error/empty states
- `chart_error_boundary` - For charts and visualizations
- `critical_section_boundary` - For critical UI (sidebar, nav)

### Error Display Components

Located in `components/error_display.py`:

- `error_callout` - Callout box with error message
- `error_banner` - Prominent banner for important errors
- `error_page` - Full-page error display
- `inline_error` - Small inline error for forms
- `loading_with_error_fallback` - Combined loading/error/content states

## Usage Patterns

### Pattern 1: State Class with Error Handling

```python
from ..state.error_state import ErrorStateMixin
from ..utils.error_handler import ErrorCategory

class MyState(ErrorStateMixin, rx.State):
    data: list = []

    def load_data(self):
        """Load data with error handling."""
        self.set_loading(True)

        def _load():
            # Your data loading logic
            result = some_service.get_data()
            self.data = result

        # Safely execute with automatic error handling
        success = self.safe_execute(
            _load,
            category=ErrorCategory.DATABASE,
            error_type="connection",
            context={"operation": "load_data"}
        )

        self.set_loading(False)
        return success
```

### Pattern 2: Page Section with Error Boundary

```python
from ..components.error_boundary import section_error_boundary

def my_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("My Page"),

            # Wrap risky section with error boundary
            section_error_boundary(
                content=rx.vstack(
                    # Your content here
                    rx.text("Data loaded successfully"),
                ),
                error_var=MyState.has_error,
                error_message_var=MyState.error_message,
                retry_action=MyState.load_data,
                section_name="Data Section",
            ),
        )
    )
```

### Pattern 3: Async Data Loading

```python
from ..components.error_boundary import async_operation_wrapper

def data_view() -> rx.Component:
    return async_operation_wrapper(
        content=rx.foreach(
            MyState.data,
            lambda item: rx.card(rx.text(item.name))
        ),
        is_loading_var=MyState.is_loading,
        has_error_var=MyState.has_error,
        error_message_var=MyState.error_message,
        retry_action=MyState.load_data,
        loading_text="Loading data...",
    )
```

### Pattern 4: Data Table with Full States

```python
from ..components.error_boundary import data_table_error_boundary

def my_table() -> rx.Component:
    return data_table_error_boundary(
        table_content=rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Value"),
                )
            ),
            rx.table.body(
                rx.foreach(MyState.data, render_row)
            ),
        ),
        is_loading_var=MyState.is_loading,
        has_error_var=MyState.has_error,
        error_message_var=MyState.error_message,
        is_empty_var=MyState.data.length() == 0,
        retry_action=MyState.load_data,
        empty_message="No data found",
    )
```

### Pattern 5: Chart with Error Handling

```python
from ..components.error_boundary import chart_error_boundary

def my_chart() -> rx.Component:
    return chart_error_boundary(
        chart_content=rx.plotly(data=MyState.chart_data),
        is_loading_var=MyState.is_loading_chart,
        has_error_var=MyState.has_chart_error,
        error_message_var=MyState.chart_error_message,
        retry_action=MyState.load_chart,
        height="400px",
    )
```

### Pattern 6: Form with Validation

```python
from ..state.error_state import ValidationErrorState
from ..components.error_boundary import form_error_boundary

class FormState(ValidationErrorState, rx.State):
    name: str = ""
    email: str = ""

    def validate_email(self, email: str) -> tuple[bool, str]:
        """Validate email format."""
        if "@" not in email:
            return False, "Invalid email format"
        return True, ""

    def submit_form(self):
        """Submit with validation."""
        # Validate
        if not self.validate_field("email", self.email, [self.validate_email]):
            return

        # Submit
        self.safe_execute(
            lambda: submit_data(self.name, self.email),
            category=ErrorCategory.NETWORK,
        )

def my_form() -> rx.Component:
    return form_error_boundary(
        form_content=rx.vstack(
            rx.input(
                value=FormState.name,
                on_change=FormState.set_name,
                placeholder="Name",
            ),
            rx.cond(
                FormState.get_field_error("name") != "",
                inline_error(FormState.get_field_error("name")),
                rx.fragment(),
            ),
            rx.input(
                value=FormState.email,
                on_change=FormState.set_email,
                placeholder="Email",
            ),
            rx.cond(
                FormState.get_field_error("email") != "",
                inline_error(FormState.get_field_error("email")),
                rx.fragment(),
            ),
            rx.button("Submit", on_click=FormState.submit_form),
        ),
        error_var=FormState.has_error,
        error_message_var=FormState.error_message,
    )
```

## Error Recovery Strategies

### Retry with Backoff

```python
from ..utils.error_handler import ErrorRecovery, ErrorCategory

class MyState(ErrorStateMixin, rx.State):
    def retry_operation(self):
        """Retry a failed operation."""
        def _operation():
            return risky_network_call()

        result = ErrorRecovery.retry_with_backoff(
            _operation,
            max_attempts=3,
            initial_delay=1.0,
            backoff_factor=2.0,
            category=ErrorCategory.NETWORK,
        )
        return result
```

### Fallback Chain

```python
from ..utils.error_handler import ErrorRecovery

def get_data_with_fallbacks():
    """Try primary, then fallback sources."""
    return ErrorRecovery.fallback_chain(
        lambda: get_from_primary_source(),
        lambda: get_from_cache(),
        lambda: get_from_backup_source(),
    )
```

## Error Categories

Use appropriate categories for better error messages:

- `ErrorCategory.DATABASE` - Database connection/query issues
- `ErrorCategory.NETWORK` - Network/API failures
- `ErrorCategory.FILE_IO` - File read/write errors
- `ErrorCategory.VALIDATION` - Input validation errors
- `ErrorCategory.PROCESSING` - Data processing failures
- `ErrorCategory.UNKNOWN` - Unexpected errors

## Best Practices

### 1. Always Use Error Boundaries for Async Operations

```python
# GOOD
async_operation_wrapper(
    content=my_content,
    is_loading_var=MyState.is_loading,
    has_error_var=MyState.has_error,
    # ...
)

# BAD - No error handling
my_content  # If loading fails, whole page breaks
```

### 2. Provide Context in Error Logs

```python
# GOOD
self.set_error(
    error,
    category=ErrorCategory.DATABASE,
    context={
        "operation": "load_documents",
        "project_id": self.project_id,
        "user_action": "search",
    }
)

# LESS HELPFUL
self.set_error(error)
```

### 3. Use Specific Error Types

```python
# GOOD
handle_database_error(e, error_type="timeout")

# LESS SPECIFIC
handle_database_error(e)  # Uses "default" message
```

### 4. Provide Retry Actions

```python
# GOOD - User can retry
section_error_boundary(
    content=content,
    error_var=MyState.has_error,
    error_message_var=MyState.error_message,
    retry_action=MyState.reload_data,  # ← Retry button
)

# LESS USER-FRIENDLY
section_error_boundary(
    content=content,
    error_var=MyState.has_error,
    error_message_var=MyState.error_message,
    # No retry - user is stuck
)
```

### 5. Clear Errors Before New Operations

```python
# GOOD
def load_data(self):
    self.clear_error()  # Clear old errors
    self.set_loading(True)
    # ... load data

# CONFUSING - Old errors stay visible
def load_data(self):
    self.set_loading(True)
    # ... load data
```

## Testing Error Boundaries

Create test endpoints that simulate failures:

```python
class TestState(ErrorStateMixin, rx.State):
    def trigger_database_error(self):
        """Test database error handling."""
        try:
            raise Exception("Simulated database connection timeout")
        except Exception as e:
            self.set_error(
                e,
                category=ErrorCategory.DATABASE,
                error_type="timeout",
            )

    def trigger_network_error(self):
        """Test network error handling."""
        try:
            raise Exception("Simulated network timeout")
        except Exception as e:
            self.set_error(
                e,
                category=ErrorCategory.NETWORK,
                error_type="timeout",
            )
```

## Migration Checklist

To add error handling to an existing page:

- [ ] Add `ErrorStateMixin` to state class
- [ ] Add error tracking variables (`has_error`, `error_message`)
- [ ] Wrap `set_loading()` calls with error clearing
- [ ] Use `safe_execute()` for risky operations
- [ ] Wrap async sections with `async_operation_wrapper`
- [ ] Add retry actions where appropriate
- [ ] Wrap tables with `data_table_error_boundary`
- [ ] Wrap charts with `chart_error_boundary`
- [ ] Add appropriate error categories
- [ ] Test with simulated failures

## Common Patterns by Page Type

### Search/List Pages

```python
class SearchState(ErrorStateMixin, rx.State):
    results: list = []
    is_loading: bool = False

    def search(self, query: str):
        self.set_loading(True)
        success = self.safe_execute(
            lambda: self._perform_search(query),
            category=ErrorCategory.DATABASE,
        )
        self.set_loading(False)
```

### Visualization Pages

```python
class VizState(ErrorStateMixin, rx.State):
    chart_data: dict = {}
    is_loading_chart: bool = False
    has_chart_error: bool = False

    def load_visualization(self):
        self.is_loading_chart = True
        # Use chart_error_boundary in component
```

### Form Pages

```python
class FormState(ValidationErrorState, rx.State):
    # Field-specific error tracking
    # Use validate_field() for validation
    # Use form_error_boundary in component
```

## Error Logging

All errors are logged to `logs/arkham_mirror.log` with:

- Timestamp
- Error ID (for tracking)
- Category and severity
- Stack trace
- Context information

Error IDs follow format: `ERR-YYYYMMDD-HHMMSS`

Example log entry:
```
2025-11-28 14:23:45 - ArkhamMirror - ERROR - [ERR-20251128-142345] DATABASE: Connection timeout
Context: {'operation': 'load_documents', 'project_id': '123', 'state': 'SearchState'}
Traceback:
  ...
```

## Troubleshooting

### Error: "Cannot access attribute on Var"

**Problem**: Trying to access Python attributes on Reflex Vars
**Solution**: Use Reflex var methods

```python
# BAD
if MyState.data:  # Can't check Var truthiness

# GOOD
rx.cond(MyState.data.length() > 0, ...)
```

### Error: "Event handler not defined"

**Problem**: Using undefined state methods in error boundaries
**Solution**: Ensure retry actions exist

```python
# Make sure this exists in your state class
def reload_data(self):
    self.load_data()
```

### Errors Not Displaying

**Problem**: Error state not updating UI
**Solution**: Check state inheritance

```python
# GOOD
class MyState(ErrorStateMixin, rx.State):
    ...

# BAD - Missing mixin
class MyState(rx.State):
    has_error: bool = False  # Won't get helper methods
```

## Resources

- Error handler: `utils/error_handler.py`
- Error boundaries: `components/error_boundary.py`
- Error display: `components/error_display.py`
- Error state: `state/error_state.py`
- Example usage: See updated pages in `pages/`
