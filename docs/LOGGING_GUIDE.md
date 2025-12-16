# ArkhamMirror Logging System Guide

## Overview

ArkhamMirror now has a comprehensive logging system that provides detailed insights into application behavior, errors, and performance.

## Log Files

All logs are stored in `arkham_reflex/logs/`:

### Main Logs

| File | Purpose | Retention |
|------|---------|-----------|
| `arkham_mirror.log` | Main application log (all levels) | 100MB per file, 10 backups |
| `errors.log` | Error-level logs only | 50MB per file, 5 backups |
| `requests.log` | HTTP request/response logs | 50MB per file, 5 backups |
| `performance.log` | Performance timing metrics | 50MB per file, 5 backups |
| `startup.log` | Backend startup logs | Manual rotation |

### Log Rotation

Logs automatically rotate when they reach their size limit. Old logs are compressed and kept as backups (e.g., `arkham_mirror.log.1`, `arkham_mirror.log.2`).

## Log Levels

Configured in [config.yaml](../arkham_mirror/config.yaml) under `system.log_level`:

- **DEBUG**: Detailed information for diagnosing problems (route registration, state events)
- **INFO**: General informational messages (service calls, successful operations)
- **WARNING**: Warning messages (deprecated features, non-critical issues)
- **ERROR**: Error messages (failed operations, exceptions)
- **CRITICAL**: Critical errors (application startup failures)

## Viewing Logs

### Real-time Monitoring

```bash
# Watch all logs
cd arkham_reflex
tail -f logs/arkham_mirror.log

# Watch errors only
tail -f logs/errors.log

# Watch startup
tail -f logs/startup.log

# Filter for specific module
grep "search_service" logs/arkham_mirror.log
```

### Health Check Script

```bash
cd arkham_reflex
python health_check.py
```

This checks:
- Backend and frontend availability
- Database connectivity
- Qdrant connectivity
- Redis connectivity
- Log file sizes

## Log Format

### Standard Format

```
2025-12-02 11:48:20 - arkham_reflex.arkham_reflex - INFO - arkham_reflex:<module>:23 - Starting ArkhamMirror Reflex Application
└─────┬─────┘   └────────┬──────────┘   └─┬─┘   └───────────┬─────────┘  └────────────┬─────────────┘
  timestamp       module name          level    module:function:line           message
```

### Console Output

Console output includes color coding:
- 🟦 DEBUG: Cyan
- 🟩 INFO: Green
- 🟨 WARNING: Yellow
- 🟥 ERROR: Red
- 🟪 CRITICAL: Magenta

## Using the Logging System

### In Python Code

```python
import logging

# Get a logger
logger = logging.getLogger(__name__)

# Log messages
logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical failure")

# Log with exceptions
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
```

### Service Layer Logging

Use the `@logged_service_call` decorator for automatic logging:

```python
from arkham_reflex.utils.service_logging import logged_service_call

class SearchService:
    @logged_service_call("SearchService")
    def search_documents(self, query: str) -> List[Document]:
        # Service method implementation
        return results
```

This automatically logs:
- Method entry with sanitized arguments
- Execution time
- Return value summary
- Errors with full traceback

### Performance Timing

```python
from arkham_reflex.utils.logging_config import timed

@timed
def expensive_operation():
    # Long-running operation
    pass
```

### State Events

```python
from arkham_reflex.utils.logging_config import log_state_event

log_state_event("SearchState", "search", {"query": "test"})
```

## Common Logging Scenarios

### Application Startup Issues

Check `logs/startup.log` and `logs/arkham_mirror.log`:

```bash
# View recent startup logs
tail -100 logs/startup.log

# Search for errors during startup
grep -i error logs/startup.log
```

### Backend Crashes

Check `logs/errors.log`:

```bash
# View all errors
cat logs/errors.log

# View last error
tail -50 logs/errors.log
```

### Performance Issues

Check `logs/performance.log`:

```bash
# Find slow operations (>1 second)
grep -E "[1-9]\.[0-9]{3}s" logs/performance.log

# See all performance metrics
cat logs/performance.log
```

### Database Issues

Search main log for database-related errors:

```bash
grep -i "database\|sqlalchemy\|postgres" logs/arkham_mirror.log
```

### Qdrant/Vector Store Issues

```bash
grep -i "qdrant\|vector\|embedding" logs/arkham_mirror.log
```

## Troubleshooting

### Logs Not Appearing

1. Check log directory exists: `ls arkham_reflex/logs/`
2. Check file permissions
3. Verify logging is initialized in [arkham_reflex.py](arkham_reflex/arkham_reflex.py:20-23)
4. Check `config.yaml` log level setting

### Logs Too Verbose

Reduce log level in `config.yaml`:

```yaml
system:
  log_level: "WARNING"  # Change from INFO or DEBUG
```

### Logs Growing Too Large

Log rotation is automatic, but you can manually clean up:

```bash
cd arkham_reflex/logs
rm *.log.[0-9]*  # Remove old rotated logs
```

## Best Practices

### Do ✅

- Use appropriate log levels
- Include context in log messages
- Log exceptions with `exc_info=True`
- Use structured logging for service calls
- Monitor `errors.log` regularly

### Don't ❌

- Log sensitive data (passwords, API keys)
- Log in tight loops (use DEBUG level)
- Ignore critical errors
- Let logs grow indefinitely
- Mix logging with print statements

## Configuration

### Change Log Level

Edit [config.yaml](../arkham_mirror/config.yaml):

```yaml
system:
  log_level: "DEBUG"  # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

### Enable JSON Logging

For structured log parsing:

```python
from arkham_reflex.utils.logging_config import setup_logging

setup_logging(level="INFO", enable_json=True)
```

### Add Custom Log Handler

```python
import logging
from logging.handlers import SMTPHandler

# Email alerts for critical errors
smtp_handler = SMTPHandler(
    mailhost=('localhost', 25),
    fromaddr='arkham@localhost',
    toaddrs=['admin@localhost'],
    subject='ArkhamMirror Critical Error'
)
smtp_handler.setLevel(logging.CRITICAL)

logger = logging.getLogger('arkham')
logger.addHandler(smtp_handler)
```

## Integration with Development Workflow

### Before Debugging

1. Run health check: `python health_check.py`
2. Check recent errors: `tail -50 logs/errors.log`
3. Enable DEBUG logging if needed

### After Changes

1. Monitor startup logs: `tail -f logs/startup.log`
2. Check for new errors: `tail -f logs/errors.log`
3. Verify application behavior in main log

### Before Reporting Issues

Include relevant log excerpts:

```bash
# Get last 100 lines with context
tail -100 logs/arkham_mirror.log > issue_logs.txt

# Get all errors
cat logs/errors.log >> issue_logs.txt
```

## Summary

The logging system provides comprehensive visibility into ArkhamMirror's operation. Key files:

- **Main logging config**: [logging_config.py](arkham_reflex/utils/logging_config.py)
- **Service logging utilities**: [service_logging.py](arkham_reflex/utils/service_logging.py)
- **Health check script**: [health_check.py](health_check.py)
- **Main application**: [arkham_reflex.py](arkham_reflex/arkham_reflex.py)

For issues or questions, check the logs first! They contain detailed information about what's happening in the application.
