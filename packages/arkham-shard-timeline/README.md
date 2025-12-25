# ArkhamFrame Timeline Shard

Temporal event extraction and timeline visualization for ArkhamMirror documents.

## Features

- **Date Extraction**: Extract dates, times, and temporal references from documents
- **Format Normalization**: Convert various date formats to ISO standard
- **Timeline Visualization**: Construct chronological timelines from extracted events
- **Timeline Merging**: Combine timelines from multiple documents
- **Conflict Detection**: Identify temporal inconsistencies and contradictions
- **Entity Timeline**: Track events associated with specific entities
- **Range Queries**: Filter events by date range
- **Precision Tracking**: Handle different date precisions (day, month, year, decade)

## Installation

```bash
pip install arkham-shard-timeline
```

The shard is automatically discovered by ArkhamFrame via entry points.

## API Endpoints

### POST /api/timeline/extract
Extract timeline events from text or document.

**Request:**
```json
{
  "text": "The meeting occurred on January 15, 2024. Three days later, the contract was signed.",
  "document_id": "doc123",
  "context": {
    "reference_date": "2024-01-01T00:00:00"
  }
}
```

**Response:**
```json
{
  "events": [
    {
      "id": "evt_abc123",
      "document_id": "doc123",
      "text": "The meeting occurred on January 15, 2024",
      "date_start": "2024-01-15T00:00:00",
      "date_end": null,
      "precision": "day",
      "confidence": 0.95,
      "entities": [],
      "event_type": "occurrence",
      "span": [0, 42]
    }
  ],
  "count": 2,
  "duration_ms": 23.4
}
```

### GET /api/timeline/{document_id}
Get timeline for a specific document.

**Query Parameters:**
- `start_date` (optional): Filter events after this date
- `end_date` (optional): Filter events before this date
- `event_type` (optional): Filter by event type
- `min_confidence` (optional): Minimum confidence threshold

**Response:**
```json
{
  "document_id": "doc123",
  "events": [...],
  "count": 15,
  "date_range": {
    "earliest": "2020-01-01T00:00:00",
    "latest": "2024-12-31T23:59:59"
  }
}
```

### POST /api/timeline/merge
Merge timelines from multiple documents.

**Request:**
```json
{
  "document_ids": ["doc123", "doc456", "doc789"],
  "merge_strategy": "chronological",
  "deduplicate": true,
  "date_range": {
    "start": "2024-01-01T00:00:00",
    "end": "2024-12-31T23:59:59"
  }
}
```

**Response:**
```json
{
  "events": [...],
  "count": 47,
  "sources": {
    "doc123": 15,
    "doc456": 18,
    "doc789": 14
  },
  "date_range": {
    "earliest": "2024-01-01T00:00:00",
    "latest": "2024-12-15T14:30:00"
  },
  "duplicates_removed": 12
}
```

### GET /api/timeline/range
Get events within a date range across all documents.

**Query Parameters:**
- `start_date`: Range start date (ISO format)
- `end_date`: Range end date (ISO format)
- `document_ids` (optional): Comma-separated document IDs
- `entity_ids` (optional): Comma-separated entity IDs
- `event_types` (optional): Comma-separated event types
- `limit` (optional): Maximum results (default: 100)
- `offset` (optional): Pagination offset

**Response:**
```json
{
  "events": [...],
  "count": 42,
  "total": 156,
  "has_more": true
}
```

### POST /api/timeline/conflicts
Find temporal conflicts across documents.

**Request:**
```json
{
  "document_ids": ["doc123", "doc456"],
  "conflict_types": ["contradiction", "inconsistency", "gap"],
  "tolerance_days": 1
}
```

**Response:**
```json
{
  "conflicts": [
    {
      "id": "conflict_xyz",
      "type": "contradiction",
      "severity": "high",
      "events": ["evt_abc", "evt_def"],
      "description": "Event A claims meeting on Jan 15, Event B claims Jan 17",
      "documents": ["doc123", "doc456"],
      "suggested_resolution": "verify_source"
    }
  ],
  "count": 3,
  "by_type": {
    "contradiction": 1,
    "inconsistency": 2,
    "gap": 0
  }
}
```

### GET /api/timeline/entity/{entity_id}
Get timeline for a specific entity.

**Query Parameters:**
- `start_date` (optional): Filter events after this date
- `end_date` (optional): Filter events before this date
- `include_related` (optional): Include related entities (default: false)

**Response:**
```json
{
  "entity_id": "ent_123",
  "events": [...],
  "count": 28,
  "date_range": {
    "earliest": "2020-03-15T00:00:00",
    "latest": "2024-11-30T16:45:00"
  }
}
```

### POST /api/timeline/normalize
Normalize date formats from various inputs.

**Request:**
```json
{
  "dates": [
    "January 15, 2024",
    "15/01/2024",
    "2024-01-15",
    "mid-2024",
    "Q3 2024"
  ],
  "reference_date": "2024-01-01T00:00:00",
  "prefer_format": "iso"
}
```

**Response:**
```json
{
  "normalized": [
    {
      "original": "January 15, 2024",
      "normalized": "2024-01-15T00:00:00",
      "precision": "day",
      "confidence": 0.99
    },
    {
      "original": "mid-2024",
      "normalized": "2024-06-30T12:00:00",
      "precision": "month",
      "confidence": 0.7
    }
  ]
}
```

### GET /api/timeline/stats
Timeline statistics across all documents.

**Query Parameters:**
- `document_ids` (optional): Filter by documents
- `start_date` (optional): Filter range start
- `end_date` (optional): Filter range end

**Response:**
```json
{
  "total_events": 1247,
  "total_documents": 89,
  "date_range": {
    "earliest": "1995-03-12T00:00:00",
    "latest": "2024-12-20T09:15:00"
  },
  "by_precision": {
    "day": 856,
    "month": 234,
    "year": 123,
    "decade": 34
  },
  "by_type": {
    "occurrence": 678,
    "reference": 345,
    "deadline": 156,
    "period": 68
  },
  "avg_confidence": 0.87,
  "conflicts_detected": 12
}
```

## Event Structure

```python
@dataclass
class TimelineEvent:
    id: str                       # Unique event identifier
    document_id: str              # Source document
    text: str                     # Original text mentioning the date
    date_start: datetime          # Normalized start date
    date_end: Optional[datetime]  # For periods/ranges
    precision: str                # "day", "month", "year", "decade", "century"
    confidence: float             # Extraction confidence (0-1)
    entities: List[str]           # Entity IDs mentioned
    event_type: str               # "occurrence", "reference", "deadline", "period"
    span: Optional[Tuple[int, int]]  # Character span in source text
    metadata: Dict[str, Any]      # Additional context
```

## Date Parsing

The shard handles various date formats:

**Absolute Dates:**
- ISO 8601: `2024-01-15`, `2024-01-15T14:30:00`
- US Format: `01/15/2024`, `January 15, 2024`
- EU Format: `15/01/2024`, `15 January 2024`
- Natural: `Jan 15, 2024`, `15th of January 2024`

**Relative Dates:**
- Simple: `yesterday`, `today`, `tomorrow`
- Week-based: `last Tuesday`, `next Friday`
- Numeric: `3 days ago`, `2 weeks from now`
- Month-based: `last month`, `next quarter`

**Periods:**
- Quarters: `Q1 2024`, `Q3 2023`
- Seasons: `summer 2024`, `winter 2023`
- Decades: `the 1990s`, `mid-90s`
- Centuries: `the 20th century`, `early 1800s`

**Approximate:**
- `around 2020`, `circa 1995`
- `mid-2024`, `late 2023`
- `early January`, `late December`

## Usage from Other Shards

```python
# Get the timeline shard
timeline_shard = frame.get_shard("timeline")

# Extract timeline from document
events = await timeline_shard.extract_timeline(
    document_id="doc123",
)

# Merge timelines
merged = await timeline_shard.merge_timelines(
    document_ids=["doc123", "doc456", "doc789"],
    deduplicate=True,
)

# Find conflicts
conflicts = await timeline_shard.detect_conflicts(
    document_ids=["doc123", "doc456"],
    tolerance_days=1,
)

# Get entity timeline
entity_timeline = await timeline_shard.get_entity_timeline(
    entity_id="ent_123",
    start_date=datetime(2024, 1, 1),
)
```

## Architecture

### Event Extraction Pipeline

1. **Text Analysis**: Scan document text for temporal patterns
2. **Pattern Matching**: Apply regex and NLP patterns
3. **Date Parsing**: Convert to normalized datetime objects
4. **Precision Detection**: Determine date precision level
5. **Confidence Scoring**: Assess extraction confidence
6. **Entity Linking**: Associate with mentioned entities
7. **Event Classification**: Categorize event type

### Conflict Detection

Identifies temporal conflicts:
- **Contradictions**: Same event with different dates
- **Inconsistencies**: Illogical date sequences
- **Gaps**: Missing expected timeline segments
- **Overlaps**: Incompatible simultaneous events

### Merging Strategies

- **Chronological**: Sort by date, preserve all events
- **Deduplicated**: Remove duplicate events
- **Consolidated**: Merge similar events
- **Source-prioritized**: Prefer certain documents

## Dependencies

- `arkham-frame>=0.1.0`
- `python-dateutil>=2.8.0` - Flexible date parsing
- PostgreSQL - Event storage and indexing

## Events

**Published:**
- `timeline.events.extracted` - When events are extracted
- `timeline.conflicts.detected` - When conflicts are found
- `timeline.merged` - When timelines are merged

**Subscribed:**
- `documents.indexed` - To extract timeline on new documents
- `documents.deleted` - To clean up timeline events
- `entities.created` - To link events with entities

## Configuration

Timeline extraction is automatically configured based on available Frame services:
- `database` service for event storage
- `entities` service for entity linking
- `documents` service for document access

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black arkham_shard_timeline/
```

## Performance

- Event extraction: ~100-500 events/second
- Timeline merging: ~10,000 events/second
- Conflict detection: ~5,000 comparisons/second
- Date normalization: ~1,000 dates/second

## Limitations

- Requires clear temporal markers in text
- Ambiguous dates may need context
- Relative dates require reference date
- Complex temporal expressions may be simplified
- Historical dates before 1900 may have lower confidence
