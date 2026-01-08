# arkham-shard-patterns

> Cross-document pattern detection and recurring theme analysis

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

## Overview

The Patterns shard detects recurring themes, behaviors, and relationships across the document corpus. It identifies cross-document patterns using configurable criteria, tracks pattern matches with evidence, and provides correlation analysis between entities.

### Key Capabilities

1. **Pattern Detection** - Detect patterns across documents
2. **Recurring Theme Analysis** - Find recurring themes and behaviors
3. **Temporal Patterns** - Detect time-based patterns
4. **Correlation Detection** - Find correlations between entities
5. **AI Analysis** - AI Junior Analyst for pattern interpretation

## Features

### Pattern Types
- `recurring` - Recurring themes and behaviors
- `behavioral` - Behavioral patterns
- `temporal` - Time-based patterns
- `correlation` - Entity correlations
- `anomalous` - Unusual patterns

### Pattern Status
- `detected` - Newly detected pattern
- `confirmed` - Manually confirmed as valid
- `dismissed` - Dismissed as noise/false positive
- `investigating` - Under review

### Detection Methods
- `automated` - Algorithm-based detection
- `llm` - LLM-assisted detection
- `manual` - User-created pattern
- `hybrid` - Combined methods

### Pattern Matching
- Evidence-based matching
- Confidence scoring
- Match tracking across documents
- Batch operations for triage

### Correlation Analysis
- Find correlations between entities
- Cross-document relationship detection
- Confidence-scored correlations

## Installation

```bash
pip install -e packages/arkham-shard-patterns
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patterns/health` | Health check |
| GET | `/api/patterns/count` | Pattern count (badge) |
| GET | `/api/patterns/stats` | Statistics |
| GET | `/api/patterns/capabilities` | Available capabilities |

### Pattern CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patterns/` | List patterns with filtering |
| POST | `/api/patterns/` | Create pattern |
| GET | `/api/patterns/{id}` | Get pattern details |
| PUT | `/api/patterns/{id}` | Update pattern |
| DELETE | `/api/patterns/{id}` | Delete pattern |
| POST | `/api/patterns/{id}/confirm` | Confirm pattern |
| POST | `/api/patterns/{id}/dismiss` | Dismiss pattern |

### Pattern Matches

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patterns/{id}/matches` | Get pattern matches |
| POST | `/api/patterns/{id}/matches` | Add match to pattern |
| DELETE | `/api/patterns/{id}/matches/{match_id}` | Remove match |

### Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/patterns/analyze` | Analyze documents for patterns |
| POST | `/api/patterns/detect` | Detect patterns in text |
| POST | `/api/patterns/correlate` | Find entity correlations |

### Batch Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/patterns/batch/confirm` | Batch confirm patterns |
| POST | `/api/patterns/batch/dismiss` | Batch dismiss patterns |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/patterns/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### List Patterns with Filtering

```bash
GET /api/patterns/?page=1&page_size=20&pattern_type=recurring&status=detected&min_confidence=0.7
```

Response:
```json
{
  "items": [
    {
      "id": "pat_123",
      "name": "Financial Report Timing Pattern",
      "description": "Documents related to quarterly reports appear 2 weeks before earnings",
      "pattern_type": "temporal",
      "status": "detected",
      "confidence": 0.85,
      "match_count": 12,
      "criteria": {"time_window": "14d", "keywords": ["quarterly", "earnings"]},
      "detection_method": "automated",
      "created_at": "2024-12-15T10:30:00Z"
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 20
}
```

### Create Pattern

```json
POST /api/patterns/
{
  "name": "Vendor Communication Pattern",
  "description": "Multiple vendors referenced together across documents",
  "pattern_type": "correlation",
  "criteria": {
    "entity_types": ["ORGANIZATION"],
    "min_co_occurrence": 3
  },
  "confidence": 0.75,
  "metadata": {"category": "procurement"}
}
```

### Analyze Documents for Patterns

```json
POST /api/patterns/analyze
{
  "document_ids": ["doc_123", "doc_456", "doc_789"],
  "pattern_types": ["recurring", "behavioral", "temporal"],
  "min_confidence": 0.6,
  "use_llm": true
}
```

Response:
```json
{
  "patterns_detected": 3,
  "new_patterns": 2,
  "updated_patterns": 1,
  "patterns": [
    {
      "id": "pat_new_1",
      "name": "Monthly Meeting References",
      "pattern_type": "recurring",
      "confidence": 0.82,
      "match_count": 5
    }
  ],
  "duration_ms": 2345.6
}
```

### Detect Patterns in Text

```bash
POST /api/patterns/detect?text=The quarterly report mentions...&pattern_types=temporal,recurring&min_confidence=0.5
```

### Find Entity Correlations

```json
POST /api/patterns/correlate
{
  "entity_ids": ["ent_person_123", "ent_org_456"],
  "min_correlation": 0.6,
  "include_indirect": true
}
```

Response:
```json
{
  "correlations": [
    {
      "entity_a": "ent_person_123",
      "entity_b": "ent_org_789",
      "correlation_score": 0.78,
      "co_occurrence_count": 8,
      "documents": ["doc_1", "doc_2", "doc_3"]
    }
  ],
  "total_correlations": 5
}
```

### Confirm Pattern

```bash
POST /api/patterns/{pattern_id}/confirm?notes=Verified across multiple document sets
```

### Get Statistics

```bash
GET /api/patterns/stats
```

Response:
```json
{
  "total_patterns": 150,
  "by_type": {
    "recurring": 45,
    "behavioral": 35,
    "temporal": 40,
    "correlation": 30
  },
  "by_status": {
    "detected": 80,
    "confirmed": 50,
    "dismissed": 20
  },
  "by_detection_method": {
    "automated": 100,
    "llm": 30,
    "manual": 20
  },
  "total_matches": 450,
  "avg_confidence": 0.72,
  "avg_matches_per_pattern": 3.0
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `patterns.pattern.detected` | New pattern detected |
| `patterns.pattern.updated` | Pattern updated with new evidence |
| `patterns.pattern.confirmed` | Pattern manually confirmed |
| `patterns.pattern.dismissed` | Pattern dismissed as noise |
| `patterns.match.added` | New match added to pattern |
| `patterns.analysis.started` | Pattern analysis job started |
| `patterns.analysis.completed` | Pattern analysis job completed |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.processed` | Scan new documents for patterns |
| `entity.created` | Check entities against patterns |
| `claims.claim.created` | Check claims for pattern matches |
| `timeline.event.created` | Check timeline events for patterns |

## UI Routes

| Route | Description |
|-------|-------------|
| `/patterns` | All patterns list |
| `/patterns/recurring` | Recurring patterns |
| `/patterns/behavioral` | Behavioral patterns |
| `/patterns/temporal` | Temporal patterns |

## Dependencies

### Required Services
- **database** - Pattern and match storage
- **events** - Event publishing

### Optional Services
- **llm** - AI-powered pattern analysis
- **vectors** - Semantic similarity for pattern matching
- **workers** - Background pattern detection jobs

## URL State

| Parameter | Description |
|-----------|-------------|
| `patternId` | Selected pattern |
| `type` | Pattern type filter |
| `status` | Status filter |
| `view` | Display mode |

### Local Storage Keys
- `show_evidence` - Evidence panel expansion
- `sort_order` - Pattern list sort preference
- `confidence_threshold` - Minimum confidence filter

## Detection Process

1. **Document Analysis**: Scan documents for pattern indicators
   - Extract features (entities, dates, keywords)
   - Compare against existing pattern criteria

2. **Pattern Matching**: Match documents against patterns
   - Criteria-based matching
   - Semantic similarity (with vectors service)
   - LLM-assisted matching (with llm service)

3. **Correlation Detection**: Find entity relationships
   - Co-occurrence analysis
   - Temporal proximity
   - Document clustering

4. **Confidence Scoring**: Calculate pattern confidence
   - Evidence strength
   - Match consistency
   - Cross-document validation

## Development

```bash
# Run tests
pytest packages/arkham-shard-patterns/tests/

# Type checking
mypy packages/arkham-shard-patterns/
```

## License

MIT
