# Production Compliance - arkham-shard-parse

**Compliance Status**: COMPLIANT

**Date Updated**: 2025-12-25

---

## Changes Made

### 1. shard.yaml Updates

#### Navigation Category Correction
**Changed**:
```yaml
# Before
navigation:
  category: Analysis
  order: 40

# After
navigation:
  category: Data
  order: 12
```

**Reason**: Per task requirements, parse shard belongs in the Data category (order 10-19), not Analysis. This shard handles data extraction and processing, which is a data management function. Order 12 places it after ingest (10) but before other data processing shards.

#### Capabilities Standardization
**Changed**:
```yaml
# Before
capabilities:
  - named_entity_recognition
  - date_extraction
  - location_extraction
  - entity_linking
  - coreference_resolution
  - text_chunking

# After
capabilities:
  - entity_extraction
  - background_processing
```

**Reason**: Consolidated granular capabilities into standard registry names:
- `entity_extraction` - Covers NER, date extraction, location extraction, and entity linking
- `background_processing` - Uses worker pools for async processing

The original capabilities were too granular and not in the standard registry. The functionality is preserved in the implementation, but the manifest now uses standard capability declarations.

---

## Validation Results

### Manifest Fields (shard.yaml)

| Field | Status | Value | Compliant |
|-------|--------|-------|-----------|
| `name` | VALID | `parse` | Matches `^[a-z][a-z0-9-]*$` |
| `version` | VALID | `0.1.0` | Valid semver |
| `entry_point` | VALID | `arkham_shard_parse:ParseShard` | Correct format |
| `api_prefix` | VALID | `/api/parse` | Starts with `/api/` |
| `requires_frame` | VALID | `>=0.1.0` | Valid constraint |
| `navigation.category` | VALID | `Data` | Valid category (corrected) |
| `navigation.order` | VALID | `12` | In range 10-19 for Data |
| `navigation.icon` | VALID | `FileSearch` | Valid Lucide icon |
| `navigation.route` | VALID | `/parse` | Unique route |
| `dependencies.services` | VALID | `database, workers, events` | All valid Frame services |
| `dependencies.optional` | VALID | `documents, entities` | Valid optional services |
| `dependencies.shards` | VALID | `[]` | Empty (required) |
| `capabilities` | VALID | Updated to standards | Standardized names |
| `events.publishes` | VALID | `{shard}.{entity}.{action}` format | All compliant |
| `events.subscribes` | VALID | Valid patterns | Compliant |
| `state.strategy` | VALID | `url` | Valid strategy |
| `state.url_params` | VALID | `documentId` | Non-filter param |
| `ui.has_custom_ui` | VALID | `false` | Uses generic UI |

### Service Dependencies

All declared services are available in Frame:
- `database` - Required, for entity storage
- `workers` - Required, for background NER processing
- `events` - Required, for event pub/sub
- `documents` - Optional, for document text access
- `entities` - Optional, for entity management

### Event Declarations

All events follow naming convention `{shard}.{entity}.{action}`:
- `parse.document.started`
- `parse.document.completed`
- `parse.entities.extracted`
- `parse.chunks.created`

Subscriptions use valid patterns:
- `ingest.job.completed` - Auto-parse ingested documents
- `worker.job.completed` - Handle worker results

### Worker Pools

Shard uses these worker pools (all valid):
- `cpu-ner` - Named entity recognition using spaCy
- `cpu-heavy` - Complex text processing

---

## Issues Found and Resolved

### Issue 1: Incorrect Navigation Category
**Problem**: Shard was in "Analysis" category (order 40) but performs data extraction/processing.

**Resolution**: Moved to "Data" category with order 12. This correctly positions the shard:
- After Ingest (order 10)
- In the Data management section
- Before analysis shards (30-39)

**Impact**: Better UX, shard appears in correct navigation category.

### Issue 2: Non-standard Capability Names
**Problem**: Capabilities were too granular and not in the standard registry.

**Resolution**: Consolidated to standard names:
- All NER/extraction features → `entity_extraction`
- Worker usage → `background_processing`

**Impact**: None on functionality, improves compatibility with UI and documentation. Specific features (NER, date extraction, etc.) are still documented in README and implemented in code.

---

## Final Compliance Status

**Overall**: COMPLIANT

All requirements from `shard_manifest_schema_prod.md` are met:
- Manifest structure follows production schema
- Service dependencies use correct Frame service names
- Events follow naming conventions
- Navigation is properly configured for Data category
- Worker pools match Frame's ResourceService definitions
- No shard dependencies (as required)
- Capabilities use standard registry names

---

## API Endpoints

The shard provides these endpoints:

### Core Endpoints
- `POST /api/parse/text` - Parse raw text
- `POST /api/parse/document/{doc_id}` - Parse document
- `GET /api/parse/entities/{doc_id}` - Get entities for document
- `POST /api/parse/chunk` - Chunk text
- `POST /api/parse/link` - Link entities

### Implemented Features

**Entity Extraction** (`entity_extraction` capability):
- Named Entity Recognition (NER) - Persons, organizations, locations
- Date/time extraction and normalization
- Location extraction and geocoding
- Entity linking to canonical entities
- Coreference resolution

**Background Processing** (`background_processing` capability):
- Uses `cpu-ner` worker pool for async NER
- Auto-triggers on `ingest.job.completed` events
- Publishes completion events for downstream shards

---

## Notes

1. The shard is now fully compliant with production schema v1.0
2. Category change from Analysis to Data better reflects functionality
3. Capabilities are simplified but functionality is unchanged
4. Worker registration follows Frame patterns
5. Event subscriptions properly use EventBus
6. spaCy model loading happens in initialize() (should move to worker in production)

---

**Reviewed by**: Claude Sonnet 4.5
**Review Date**: 2025-12-25
