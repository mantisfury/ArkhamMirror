# arkham-shard-anomalies

> Anomaly and outlier detection for documents and content

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

## Overview

The Anomalies shard detects unusual patterns, outliers, and anomalies in documents and content. It identifies content anomalies (semantically distant documents), metadata anomalies (unusual file properties), statistical anomalies (text pattern deviations), and red flags (sensitive content indicators).

### Key Capabilities

1. **Anomaly Detection** - Multiple detection strategies for documents
2. **Outlier Identification** - Find semantically distant documents
3. **Pattern Detection** - Identify recurring anomaly patterns
4. **Status Tracking** - Analyst workflow for triage and review
5. **AI Analysis** - AI Junior Analyst for anomaly interpretation

## Features

### Anomaly Types
- `content` - Semantically distant from corpus
- `metadata` - Unusual file properties
- `temporal` - Unexpected dates/timestamps
- `structural` - Unusual document structure
- `statistical` - Text pattern deviations
- `red_flag` - Sensitive content indicators

### Anomaly Status
- `detected` - Newly detected, awaiting review
- `confirmed` - Confirmed as legitimate anomaly
- `dismissed` - Dismissed as normal
- `false_positive` - Marked as false positive

### Severity Levels
- `critical` - Requires immediate attention
- `high` - Significant anomaly
- `medium` - Notable anomaly
- `low` - Minor anomaly

### Detection Strategies
- **Content Detection** - Vector similarity to corpus centroid
- **Metadata Detection** - File size, type, date outliers
- **Statistical Detection** - Word count, character patterns
- **Red Flag Detection** - Sensitive keywords and patterns

### Analyst Workflow
- Review detected anomalies
- Add analyst notes
- Update status with reasoning
- Bulk status updates for triage
- View related anomalies

## Installation

```bash
pip install -e packages/arkham-shard-anomalies
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/anomalies/detect` | Run detection on documents |
| POST | `/api/anomalies/document/{id}` | Check single document |
| GET | `/api/anomalies/outliers` | Get statistical outliers |
| POST | `/api/anomalies/patterns` | Detect anomaly patterns |

### Listing and Filtering

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/anomalies/list` | List anomalies |
| GET | `/api/anomalies/count` | Get anomaly count |
| GET | `/api/anomalies/stats` | Get statistics |

### Anomaly Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/anomalies/{id}` | Get anomaly details |
| PUT | `/api/anomalies/{id}/status` | Update status |
| POST | `/api/anomalies/{id}/notes` | Add analyst note |
| GET | `/api/anomalies/{id}/notes` | Get notes |
| GET | `/api/anomalies/{id}/related` | Get related anomalies |
| POST | `/api/anomalies/bulk-status` | Bulk status update |

### Context

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/anomalies/document/{id}/preview` | Document preview |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/anomalies/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### Run Detection on Documents

```json
POST /api/anomalies/detect
{
  "project_id": "proj_123",
  "doc_ids": ["doc_abc", "doc_def"],
  "config": {
    "detect_content": true,
    "detect_metadata": true,
    "detect_statistical": true,
    "detect_red_flags": true
  }
}
```

Response:
```json
{
  "anomalies_detected": 5,
  "duration_ms": 1523.4,
  "job_id": "detect-1234567890"
}
```

### List Anomalies with Filtering

```bash
GET /api/anomalies/list?offset=0&limit=20&anomaly_type=content&status=detected&severity=high
```

Response:
```json
{
  "total": 45,
  "items": [
    {
      "id": "anom_123",
      "doc_id": "doc_abc",
      "anomaly_type": "content",
      "status": "detected",
      "score": 0.85,
      "severity": "high",
      "confidence": 0.92,
      "explanation": "Document is semantically distant from corpus",
      "detected_at": "2024-12-15T10:30:00Z"
    }
  ],
  "offset": 0,
  "limit": 20,
  "has_more": true,
  "facets": {
    "by_type": {"content": 20, "metadata": 15, "red_flag": 10},
    "by_status": {"detected": 30, "confirmed": 10, "dismissed": 5},
    "by_severity": {"high": 15, "medium": 20, "low": 10}
  }
}
```

### Update Anomaly Status

```json
PUT /api/anomalies/{anomaly_id}/status
{
  "status": "confirmed",
  "notes": "Verified as legitimate anomaly - document from external source",
  "reviewed_by": "analyst_john"
}
```

### Add Analyst Note

```json
POST /api/anomalies/{anomaly_id}/notes
{
  "content": "This anomaly correlates with doc_xyz which has similar patterns",
  "author": "analyst_john"
}
```

### Bulk Status Update

```json
POST /api/anomalies/bulk-status?anomaly_ids=anom_1&anomaly_ids=anom_2&status=dismissed&notes=Batch triage&reviewed_by=analyst_john
```

### Get Statistics

```bash
GET /api/anomalies/stats
```

Response:
```json
{
  "stats": {
    "total_anomalies": 150,
    "by_type": {"content": 50, "metadata": 40, "statistical": 30, "red_flag": 30},
    "by_status": {"detected": 80, "confirmed": 40, "dismissed": 25, "false_positive": 5},
    "by_severity": {"critical": 10, "high": 40, "medium": 60, "low": 40},
    "detected_last_24h": 12,
    "confirmed_last_24h": 5,
    "dismissed_last_24h": 3,
    "false_positive_rate": 0.033,
    "avg_confidence": 0.78,
    "calculated_at": "2024-12-15T12:00:00Z"
  }
}
```

### Get Outliers

```bash
GET /api/anomalies/outliers?limit=20&min_z_score=3.0
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `anomalies.anomaly.detected` | Anomaly detected |
| `anomalies.anomaly.confirmed` | Anomaly confirmed |
| `anomalies.anomaly.dismissed` | Anomaly dismissed |
| `anomalies.pattern.found` | Pattern detected |
| `anomalies.stats.updated` | Statistics updated |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `embed.embedding.created` | Check new embeddings |
| `document.processed` | Run detection on processed docs |

## UI Routes

| Route | Description |
|-------|-------------|
| `/anomalies` | Anomalies list |

## Tech Stack

- **PostgreSQL 14+** - Single database for all persistence
- **pgvector extension** - Vector similarity search for embedding-based detection
- **PostgreSQL job queue** - Background jobs using SKIP LOCKED pattern

## Dependencies

### Required Services
- **database** - Anomaly storage (PostgreSQL)
- **vectors** - Embedding-based detection (pgvector)
- **events** - Event publishing

### Optional Services
- **llm** - AI-powered analysis

## URL State

| Parameter | Description |
|-----------|-------------|
| `status` | Filter by status |
| `type` | Filter by anomaly type |
| `severity` | Filter by severity |

## Detection Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `detect_content` | true | Run content detection |
| `detect_metadata` | true | Run metadata detection |
| `detect_statistical` | true | Run statistical detection |
| `detect_red_flags` | true | Run red flag detection |

## Red Flag Keywords

The shard detects sensitive content patterns including:
- Classified/confidential markers
- Financial fraud indicators
- Legal risk terms
- Personal data patterns
- Security concerns

## Development

```bash
# Run tests
pytest packages/arkham-shard-anomalies/tests/

# Type checking
mypy packages/arkham-shard-anomalies/
```

## License

MIT
