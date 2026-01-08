# arkham-shard-timeline

> Temporal event extraction and timeline visualization

**Version:** 0.1.0
**Category:** Visualize
**Frame Requirement:** >=0.1.0

## Overview

The Timeline shard extracts temporal events from documents and constructs unified timelines. It identifies dates, normalizes temporal expressions, detects conflicts between sources, merges timelines across documents, and provides interactive visualization of chronological events.

### Key Capabilities

1. **Timeline Construction** - Build timelines from documents
2. **Date Extraction** - Extract and parse temporal expressions
3. **Timeline Visualization** - Interactive timeline display
4. **Conflict Detection** - Identify chronological contradictions
5. **Date Normalization** - Normalize varied date formats

## Features

### Event Extraction
- Extract dates and temporal expressions from text
- Parse relative dates (e.g., "last week", "three days ago")
- Multiple extraction patterns and formats
- Confidence scoring for extracted dates

### Event Types
- `occurrence` - Point-in-time events
- `period` - Events with duration
- `deadline` - Due dates
- `meeting` - Scheduled meetings
- `milestone` - Project milestones
- `announcement` - Announcements
- `birth` / `death` - Life events
- `start` / `end` - Period boundaries

### Date Precision
- `year` - Year only (2024)
- `month` - Year and month (2024-03)
- `day` - Full date (2024-03-15)
- `hour` - Date and hour
- `minute` - Date and time
- `second` - Precise timestamp

### Timeline Merging
- Merge timelines from multiple documents
- Multiple merge strategies
- Deduplication of similar events
- Priority-based conflict resolution

### Merge Strategies
- `chronological` - Order by date
- `source_priority` - Priority documents first
- `confidence_weighted` - Highest confidence wins

### Conflict Detection
- Detect chronological contradictions
- Identify overlapping events
- Find sequencing violations
- Severity-based classification

### Conflict Types
- `date_mismatch` - Same event, different dates
- `sequence_violation` - Impossible ordering
- `overlap` - Conflicting time periods
- `missing_event` - Referenced but not found

### Conflict Severity
- `critical` - Major contradiction
- `high` - Significant conflict
- `medium` - Notable inconsistency
- `low` - Minor discrepancy

### Gap Detection
- Identify temporal gaps in timeline
- Find missing periods
- Detect coverage holes

## Installation

```bash
pip install -e packages/arkham-shard-timeline
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Count

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/timeline/health` | Health check |
| GET | `/api/timeline/count` | Event count (badge) |

### Events CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/timeline/events` | List all events |
| PUT | `/api/timeline/events/{id}` | Update event |
| DELETE | `/api/timeline/events/{id}` | Delete event |
| DELETE | `/api/timeline/events` | Bulk delete events |
| POST | `/api/timeline/events/merge` | Merge duplicate events |

### Event Notes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/timeline/events/{id}/notes` | Add note |
| GET | `/api/timeline/events/{id}/notes` | Get notes |
| DELETE | `/api/timeline/events/{id}/notes/{note_id}` | Delete note |

### Extraction

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/timeline/extract` | Extract from text |
| POST | `/api/timeline/extract/{doc_id}` | Extract from document |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/timeline/documents` | List documents |
| GET | `/api/timeline/document/{id}` | Get document timeline |
| DELETE | `/api/timeline/document/{id}/events` | Delete document events |

### Timeline Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/timeline/range` | Events in date range |
| GET | `/api/timeline/stats` | Timeline statistics |
| POST | `/api/timeline/merge` | Merge timelines |
| POST | `/api/timeline/normalize` | Normalize dates |
| GET | `/api/timeline/gaps` | Detect gaps |

### Entities

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/timeline/entity/{id}` | Entity timeline |
| GET | `/api/timeline/entities` | Entities with events |

### Conflicts

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/timeline/conflicts` | Detect conflicts |
| GET | `/api/timeline/conflicts/analyze` | Analyze conflicts |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/timeline/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### Extract Timeline from Text

```json
POST /api/timeline/extract
{
  "text": "The meeting was held on March 15, 2024. The project started in January and will conclude by December.",
  "context": {
    "reference_date": "2024-06-01",
    "timezone": "America/New_York"
  }
}
```

Response:
```json
{
  "events": [
    {
      "id": "evt_123",
      "text": "The meeting was held on March 15, 2024",
      "date_start": "2024-03-15T00:00:00",
      "precision": "day",
      "event_type": "meeting",
      "confidence": 0.95
    },
    {
      "id": "evt_124",
      "text": "The project started in January",
      "date_start": "2024-01-01T00:00:00",
      "precision": "month",
      "event_type": "start",
      "confidence": 0.85
    }
  ],
  "count": 2,
  "duration_ms": 234.5
}
```

### Extract from Document

```bash
POST /api/timeline/extract/{document_id}
```

### Get Document Timeline

```bash
GET /api/timeline/document/{document_id}?start_date=2024-01-01&end_date=2024-12-31&event_type=meeting&min_confidence=0.7
```

Response:
```json
{
  "document_id": "doc_abc123",
  "events": [...],
  "count": 15,
  "date_range": {
    "earliest": "2024-01-15T00:00:00",
    "latest": "2024-11-20T00:00:00"
  }
}
```

### Merge Multiple Timelines

```json
POST /api/timeline/merge
{
  "document_ids": ["doc_a", "doc_b", "doc_c"],
  "merge_strategy": "chronological",
  "deduplicate": true,
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-12-31"
  },
  "priority_docs": ["doc_a"]
}
```

Response:
```json
{
  "events": [...],
  "count": 45,
  "sources": {
    "doc_a": 20,
    "doc_b": 15,
    "doc_c": 10
  },
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-12-31"
  },
  "duplicates_removed": 5
}
```

### Detect Conflicts

```json
POST /api/timeline/conflicts
{
  "document_ids": ["doc_a", "doc_b"],
  "conflict_types": ["date_mismatch", "sequence_violation"],
  "tolerance_days": 1
}
```

Response:
```json
{
  "conflicts": [
    {
      "id": "conflict_123",
      "type": "date_mismatch",
      "severity": "high",
      "event_a": {"id": "evt_1", "text": "Meeting on March 15"},
      "event_b": {"id": "evt_2", "text": "Meeting on March 18"},
      "description": "Same event with different dates"
    }
  ],
  "count": 3,
  "by_type": {
    "date_mismatch": 2,
    "sequence_violation": 1
  }
}
```

### Normalize Dates

```json
POST /api/timeline/normalize
{
  "dates": ["March 15, 2024", "last Tuesday", "Q1 2024"],
  "reference_date": "2024-06-01",
  "prefer_format": "iso"
}
```

Response:
```json
{
  "normalized": [
    {"original": "March 15, 2024", "normalized": "2024-03-15", "precision": "day"},
    {"original": "last Tuesday", "normalized": "2024-05-28", "precision": "day"},
    {"original": "Q1 2024", "normalized": "2024-01-01", "precision": "quarter"}
  ]
}
```

### Get Entity Timeline

```bash
GET /api/timeline/entity/{entity_id}
```

Response:
```json
{
  "entity_id": "ent_person_123",
  "events": [...],
  "count": 25,
  "date_range": {
    "earliest": "2020-01-01",
    "latest": "2024-12-31"
  }
}
```

### Get Statistics

```bash
GET /api/timeline/stats?document_ids=doc_a,doc_b&start_date=2024-01-01
```

Response:
```json
{
  "total_events": 150,
  "total_documents": 5,
  "date_range": {
    "earliest": "2020-01-15",
    "latest": "2024-11-30"
  },
  "by_precision": {
    "day": 100,
    "month": 30,
    "year": 20
  },
  "by_type": {
    "occurrence": 80,
    "meeting": 40,
    "deadline": 30
  },
  "avg_confidence": 0.87,
  "conflicts_detected": 5
}
```

### Detect Gaps

```bash
GET /api/timeline/gaps?document_ids=doc_a,doc_b&min_gap_days=30
```

### Update Event

```json
PUT /api/timeline/events/{event_id}
{
  "text": "Updated event description",
  "date_start": "2024-03-16T10:00:00",
  "precision": "minute",
  "confidence": 0.95,
  "entities": ["ent_123", "ent_456"]
}
```

### Merge Duplicate Events

```json
POST /api/timeline/events/merge
{
  "event_ids": ["evt_1", "evt_2", "evt_3"],
  "primary_id": "evt_1",
  "merge_notes": true
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `timeline.timeline.extracted` | Timeline extracted from document |
| `timeline.timeline.merged` | Timelines merged |
| `timeline.conflict.detected` | Conflict detected |
| `timeline.entity_timeline.built` | Entity timeline built |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.document.indexed` | Extract timeline from new doc |
| `document.document.deleted` | Remove document events |
| `entity.entity.created` | Link events to entity |

## UI Routes

| Route | Description |
|-------|-------------|
| `/timeline` | Timeline visualization |

## Dependencies

### Required Services
- **database** - Event storage
- **events** - Event publishing

### Optional Services
- **documents** - Document access for extraction
- **entities** - Entity linking

## URL State

| Parameter | Description |
|-----------|-------------|
| `documentIds` | Filter by documents |
| `entityId` | Filter by entity |
| `startDate` | Date range start |
| `endDate` | Date range end |

## Extraction Features

### Supported Date Formats
- ISO 8601: `2024-03-15T10:30:00`
- US format: `03/15/2024`, `March 15, 2024`
- European: `15/03/2024`, `15 March 2024`
- Relative: `yesterday`, `last week`, `3 days ago`
- Quarters: `Q1 2024`, `first quarter`
- Fiscal years: `FY2024`

### Entity Linking
Timeline events can be linked to entities:
- Extract entity mentions from event text
- Link existing entities to events
- Build entity-centric timelines

## Development

```bash
# Run tests
pytest packages/arkham-shard-timeline/tests/

# Type checking
mypy packages/arkham-shard-timeline/
```

## License

MIT
