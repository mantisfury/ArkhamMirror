# Anomalies Shard - Production Compliance Report

**Date**: 2025-12-25
**Shard**: arkham-shard-anomalies
**Version**: 0.1.0

## Changes Made

### 1. Navigation Order
**Issue**: Order out of valid range for Analysis category
- **Before**: order: 50
- **After**: order: 37
- **Reason**: Analysis category uses range 30-39. Order 50 exceeds this range. Set to 37 to position after ACH (30) and Contradictions (35).

### 2. Capabilities
**Issue**: Non-standard capability names
- **Before**:
  - anomaly_detection
  - outlier_detection
  - pattern_detection
  - statistical_analysis
  - analyst_workflow
  - triage_management
- **After**:
  - anomaly_detection (standard name from registry)
- **Reason**: Simplified to standard capability name from production registry. "anomaly_detection" encompasses outlier detection, pattern detection, and statistical analysis as implementation details.

### 3. Event Naming
**Issue**: Events missing entity component in naming pattern
- **Before**:
  - anomalies.detected
  - anomalies.confirmed
  - anomalies.dismissed
  - anomalies.pattern_found
  - anomalies.stats_updated
- **After**:
  - anomalies.anomaly.detected
  - anomalies.anomaly.confirmed
  - anomalies.anomaly.dismissed
  - anomalies.pattern.found
  - anomalies.stats.updated
- **Reason**: Events must follow `{shard}.{entity}.{action}` pattern. Added "anomaly", "pattern", and "stats" as entity names.

### 4. Event Subscriptions
**Issue**: Non-standard event names in subscriptions
- **Before**:
  - embeddings.created
  - documents.indexed
- **After**:
  - embed.embedding.created
  - document.processed
- **Reason**:
  - "embeddings.created" doesn't follow standard naming (should be from embed shard)
  - "documents.indexed" uses plural "documents" instead of singular "document"
  - Updated to subscribe to actual Frame and shard events

## Validation Results

### Manifest Validation
- ✅ `name`: "anomalies" - valid (lowercase, starts with letter)
- ✅ `version`: "0.1.0" - valid semver
- ✅ `entry_point`: "arkham_shard_anomalies:AnomaliesShard" - correct format
- ✅ `api_prefix`: "/api/anomalies" - starts with /api/
- ✅ `requires_frame`: ">=0.1.0" - valid constraint
- ✅ `navigation.category`: "Analysis" - valid category
- ✅ `navigation.order`: 37 - within valid range (30-39)
- ✅ `navigation.route`: "/anomalies" - valid format
- ✅ `navigation.badge_endpoint`: "/api/anomalies/pending/count" - valid
- ✅ `navigation.badge_type`: "count" - valid type
- ✅ `dependencies.shards`: [] - empty as required

### Service Dependencies
- ✅ `database` - valid Frame service (DatabaseService)
- ✅ `vectors` - valid Frame service (VectorService)
- ✅ `events` - valid Frame service (EventBus)
- ✅ `llm` - valid optional Frame service (LLMService)

### Event Validation
- ✅ All published events follow `{shard}.{entity}.{action}` format
- ✅ No reserved prefixes used
- ✅ Subscriptions reference valid shard events (embed.embedding.created, document.processed)

### Capabilities
- ✅ All capabilities use standard registry names
- ✅ Capabilities accurately describe shard functionality

### State Management
- ✅ Strategy: "url" - valid for shareable state
- ✅ URL params: status, type, severity - appropriate for anomaly filtering

### UI Configuration
- ✅ has_custom_ui: true - shard provides custom React UI

## Compliance Status

**FULLY COMPLIANT** ✅

All production schema requirements met:
- Navigation properly categorized and ordered within Analysis (30-39)
- Service dependencies correctly declared
- Event naming follows `{shard}.{entity}.{action}` conventions
- Capabilities use standard names
- No shard dependencies
- Valid state management configuration
- Valid manifest structure

## Notes

### Integration Points
The anomalies shard properly integrates with:
- **DatabaseService**: For storing detected anomalies
- **VectorService**: For vector-based outlier detection (semantic distance from corpus)
- **EventBus**: Publishes anomaly events, subscribes to embedding and document events
- **LLMService**: Optional, for enhanced anomaly explanation

### Detection Strategies
Multi-dimensional anomaly detection:
1. **Content Anomalies**: Vector-based outlier detection using semantic distance
2. **Statistical Anomalies**: Text pattern analysis (word counts, sentence lengths, frequency distributions)
3. **Metadata Anomalies**: File property analysis (unusual sizes, dates, missing fields)
4. **Temporal Anomalies**: Time reference detection and temporal outliers
5. **Structural Anomalies**: Document structure analysis
6. **Red Flags**: Sensitive content detection (money patterns, sensitive keywords)

### Analyst Workflow
- Triage detected anomalies
- Confirm, dismiss, or mark as false positive
- Add investigation notes
- Pattern detection across anomalies
- Quality metrics tracking

### Public API
The shard exposes public methods for other shards:
- `detect_anomalies()` - Trigger anomaly detection
- `get_anomalies_for_document()` - Get anomalies for a document
- `check_document()` - Check if a document is anomalous
- `get_statistics()` - Get anomaly statistics

### Event Flow
- Subscribes to `embed.embedding.created` - Triggers content anomaly detection when new embeddings are available
- Subscribes to `document.processed` - Triggers metadata/statistical detection when documents are processed
- Publishes `anomalies.anomaly.detected` - Notifies system when anomalies are found

No issues identified with current implementation.
