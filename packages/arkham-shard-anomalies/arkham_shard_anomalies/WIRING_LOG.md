# Anomalies Shard Wiring Log

## Overview

This document describes the changes made to wire the Anomalies shard for full database persistence and real detection functionality.

## Changes Made

### 1. shard.py - Schema Creation and Event Subscriptions

**Added imports:**
- `json` for JSON serialization
- `typing.Any, Dict` for type hints

**Added `_create_schema()` method:**
- Creates `arkham_anomalies` table with columns:
  - `id`, `doc_id`, `project_id`, `anomaly_type`, `severity`, `status`
  - `score`, `confidence`, `title`, `description`, `explanation`
  - `field_name`, `expected_range`, `actual_value`
  - `evidence`, `details`, `tags`, `metadata` (JSON fields)
  - `detected_at`, `reviewed_at`, `reviewed_by`, `notes`
  - `created_at`, `updated_at`
- Creates `arkham_anomaly_notes` table for analyst notes
- Creates `arkham_anomaly_patterns` table for pattern detection
- Creates indexes on `doc_id`, `anomaly_type`, `status`, `severity`, `project_id`

**Updated `initialize()` method:**
- Calls `_create_schema()` on startup
- Passes database service to `AnomalyStore(db=self._db_service)`
- Passes db and vectors to `init_api()`
- Fixed event subscriptions to use correct event names:
  - `embed.document.completed` (was `embeddings.created`)
  - `documents.metadata.updated` (was `documents.indexed`)
- Registers shard in app state for API access

**Updated `shutdown()` method:**
- Fixed event unsubscription to use correct event names

### 2. storage.py - Database Persistence

**Constructor changes:**
- Added `db` parameter to accept database service
- Maintains in-memory fallback when database is unavailable

**Converted all CRUD operations to use database:**

| Method | Database Implementation |
|--------|------------------------|
| `create_anomaly()` | INSERT with named parameters |
| `get_anomaly()` | SELECT by id |
| `update_anomaly()` | UPDATE with `_save_anomaly_to_db()` |
| `delete_anomaly()` | DELETE (notes first, then anomaly) |
| `list_anomalies()` | Dynamic WHERE clause with pagination |
| `get_anomalies_by_doc()` | SELECT with doc_id filter |
| `update_status()` | UPDATE specific fields |
| `add_note()` | INSERT into notes table |
| `get_notes()` | SELECT from notes table |
| `create_pattern()` | INSERT into patterns table |
| `get_pattern()` | SELECT from patterns table |
| `list_patterns()` | SELECT all patterns |
| `get_stats()` | Aggregate queries (COUNT, AVG, GROUP BY) |
| `get_facets()` | GROUP BY queries for filtering UI |

**Added helper methods:**
- `_save_anomaly_to_db()` - Handles INSERT/UPDATE with JSON serialization
- `_row_to_anomaly()` - Converts database row to Anomaly object
- `_row_to_note()` - Converts database row to AnalystNote object
- `_row_to_pattern()` - Converts database row to AnomalyPattern object

### 3. api.py - Real Detection Logic

**Updated `init_api()`:**
- Added `db` and `vectors` parameters

**Added detection implementation to `/detect` endpoint:**
- Fetches document IDs if not provided
- Calls `_detect_document_anomalies_internal()` for each document
- Stores detected anomalies in database
- Emits `anomalies.detection_completed` event

**Added detection implementation to `/document/{doc_id}` endpoint:**
- Runs detection for single document
- Stores anomalies and emits events

**Added helper functions:**
- `_detect_document_anomalies_internal()` - Main detection orchestrator:
  - Fetches document content and metadata from database
  - Runs red flag detection
  - Runs statistical detection with corpus stats
  - Runs metadata detection with corpus metadata stats
  - Runs content/embedding detection if vectors available

- `_get_corpus_stats()` - Calculates text statistics across corpus:
  - Average character count
  - Average word count

- `_get_corpus_metadata_stats()` - Calculates metadata statistics:
  - File size mean/std

- `_detect_content_anomalies()` - Vector-based outlier detection:
  - Uses vector search to find similar documents
  - Flags documents with low similarity scores

**Added `/count` endpoint:**
- Returns total anomaly count for navigation badge
- Supports optional status filter

## Database Patterns Used

All database operations use named parameters with `:param_name` syntax:

```python
await self._db.execute(
    "INSERT INTO table (id, name) VALUES (:id, :name)",
    {"id": some_id, "name": some_name}
)

row = await self._db.fetch_one(
    "SELECT * FROM table WHERE id = :id",
    {"id": some_id}
)

rows = await self._db.fetch_all(
    "SELECT * FROM table WHERE status = :status LIMIT :limit OFFSET :offset",
    {"status": status, "limit": limit, "offset": offset}
)
```

JSON fields are serialized with `json.dumps()` before insertion:
```python
params["details"] = json.dumps(anomaly.details)
params["tags"] = json.dumps(anomaly.tags)
```

## Event Names

Corrected event subscriptions:
- `embed.document.completed` - Triggered when document embeddings are created
- `documents.metadata.updated` - Triggered when document metadata changes

Published events:
- `anomalies.detection_started` - When detection begins
- `anomalies.detection_completed` - When detection finishes
- `anomalies.detected` - When anomalies are found for a document
- `anomalies.{status}` - When anomaly status is updated

## Testing Notes

All Python files pass syntax validation:
```bash
python -m py_compile packages/arkham-shard-anomalies/arkham_shard_anomalies/shard.py
python -m py_compile packages/arkham-shard-anomalies/arkham_shard_anomalies/storage.py
python -m py_compile packages/arkham-shard-anomalies/arkham_shard_anomalies/api.py
```

## Remaining Work

1. **Integration Testing** - Test with running frame to verify:
   - Schema creation works
   - Event subscriptions receive events
   - Detection produces real anomalies

2. **Worker Integration** - For large-scale detection:
   - Queue detection jobs to worker pool
   - Handle background processing

3. **Vector Service Integration** - Content anomaly detection requires:
   - Working vector service with `search()` method
   - Document embeddings in vector store

4. **Corpus Statistics** - For better statistical detection:
   - Pre-compute and cache corpus statistics
   - Update stats when documents change

## Files Modified

- `arkham_shard_anomalies/shard.py`
- `arkham_shard_anomalies/storage.py`
- `arkham_shard_anomalies/api.py`
