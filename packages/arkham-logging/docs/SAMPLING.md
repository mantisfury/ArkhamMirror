# Sampling Strategies Guide

Guide to configuring sampling for cost-effective wide event logging.

## Why Sampling?

At scale, logging every operation can be expensive. Sampling allows you to:
- Reduce log volume and costs
- Keep important events (errors, slow requests)
- Maintain debugging capability with representative samples

## Tail Sampling

Tail sampling makes the sampling decision **after** the request completes, based on its outcome. This ensures you never lose important events.

### Rules

1. **Always keep errors**: 100% of errors are logged
2. **Always keep slow requests**: Requests above threshold are logged
3. **Always keep VIP users/projects**: Configured users/projects are always logged
4. **Random sample the rest**: Normal requests are sampled at configured rate

## Configuration

### YAML Configuration

```yaml
frame:
  logging:
    wide_events:
      enabled: true
      sampling_rate: 0.05  # 5% of normal requests
      tail_sampling: true
      always_sample_errors: true
      always_sample_slow: true
      slow_threshold_ms: 2000
      always_sample_users:
        - user_vip_123
        - user_admin_456
      always_sample_projects:
        - project_debug_789
```

### Environment Variables

```bash
ARKHAM_LOG_WIDE_EVENTS_SAMPLING_RATE=0.05
ARKHAM_LOG_WIDE_EVENTS_SLOW_THRESHOLD_MS=2000
```

## Sampling Rate Guidelines

- **Development**: 1.0 (100%) - See everything
- **Staging**: 0.1 (10%) - Representative sample
- **Production**: 0.01-0.05 (1-5%) - Cost-effective with error coverage

## Always-Sample Rules

### Errors

All errors are always sampled, regardless of sampling rate:

```python
event.error("ProcessingError", "Failed to process document")
# This event is always logged, even if sampling_rate = 0.01
```

### Slow Requests

Requests above the threshold are always sampled:

```yaml
slow_threshold_ms: 2000  # Requests taking >2 seconds
```

### VIP Users/Projects

Configure specific users or projects to always sample:

```yaml
always_sample_users:
  - user_vip_123
  - user_admin_456

always_sample_projects:
  - project_debug_789
```

## Cost Implications

### Example Calculation

- **Requests per second**: 1000
- **Sampling rate**: 0.05 (5%)
- **Normal requests sampled**: 1000 * 0.05 = 50/sec
- **Errors**: ~1/sec (always sampled)
- **Slow requests**: ~5/sec (always sampled)
- **Total events**: ~56/sec = ~4.8M events/day

Without sampling: 1000/sec = 86.4M events/day

**Savings**: ~94% reduction in log volume

## Best Practices

1. **Start conservative**: Begin with 1-5% sampling in production
2. **Monitor error rates**: Ensure error sampling is working
3. **Adjust based on volume**: Increase sampling if you need more data
4. **Use VIP lists**: Add important users/projects to always-sample lists
5. **Review slow requests**: Monitor slow_threshold_ms to catch performance issues

## Implementation Details

Sampling decision is made when `event.success()` or `event.error()` is called:

```python
event = create_wide_event("process_document")
event.input(document_id=doc_id)
# ... processing ...
event.success()  # Sampling decision made here
```

The sampler checks:
1. Is outcome "error"? → Always sample
2. Is duration_ms > slow_threshold_ms? → Always sample
3. Is user_id in always_sample_users? → Always sample
4. Is project_id in always_sample_projects? → Always sample
5. Otherwise → Random sample based on sampling_rate

## Disabling Sampling

To disable sampling (log everything):

```yaml
wide_events:
  sampling_rate: 1.0  # 100%
```

Or disable wide events entirely:

```yaml
wide_events:
  enabled: false
```
