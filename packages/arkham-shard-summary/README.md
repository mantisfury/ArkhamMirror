# arkham-shard-summary

> Auto-summarization of documents, collections, and analysis results using LLM

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

## Overview

The Summary shard provides AI-powered summarization for documents, collections, and analysis results. It uses LLM services to generate concise summaries, supports batch processing, and can automatically summarize new documents as they are ingested.

### Key Capabilities

1. **Summarization** - Generate summaries of text
2. **LLM Enrichment** - AI-powered content generation
3. **Multi-Document Summary** - Summarize document collections
4. **Batch Processing** - Background batch summarization

## Features

### Summary Types
- `brief` - Short 1-2 sentence summary
- `standard` - Paragraph-length summary
- `detailed` - Multi-paragraph comprehensive summary
- `key_points` - Bullet point key takeaways
- `executive` - Executive summary format
- `technical` - Technical focus summary

### Source Types
Summarize content from various sources:
- Documents
- Entities
- Projects
- Claims
- Timeline events

### Batch Processing
- Process multiple documents at once
- Background job execution
- Progress tracking
- Error handling

### Auto-Summarization
- Automatically summarize new documents
- Configurable summary type
- Event-driven triggers

## Installation

```bash
pip install -e packages/arkham-shard-summary
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/summary/health` | Health check |
| GET | `/api/summary/count` | Summary count (badge) |
| GET | `/api/summary/capabilities` | Available capabilities |
| GET | `/api/summary/types` | Available summary types |
| GET | `/api/summary/stats` | Statistics |

### Summary CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/summary/` | List summaries |
| POST | `/api/summary/` | Create summary |
| GET | `/api/summary/{id}` | Get summary |
| DELETE | `/api/summary/{id}` | Delete summary |

### Document Summaries

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/summary/document/{doc_id}` | Get document summary |
| POST | `/api/summary/quick-summary/{doc_id}` | Quick summary |

### Batch Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/summary/batch` | Batch summarize |

### Source Listings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/summary/sources/documents` | List documents |
| GET | `/api/summary/sources/entities` | List entities |
| GET | `/api/summary/sources/projects` | List projects |
| GET | `/api/summary/sources/claims` | List claims |
| GET | `/api/summary/sources/timeline` | List timeline events |

## API Examples

### Create Summary

```json
POST /api/summary/
{
  "source_type": "document",
  "source_id": "doc_abc123",
  "summary_type": "standard",
  "max_length": 500,
  "focus_areas": ["key findings", "recommendations"]
}
```

Response:
```json
{
  "id": "sum_xyz789",
  "source_type": "document",
  "source_id": "doc_abc123",
  "summary_type": "standard",
  "content": "This document presents an analysis of...",
  "word_count": 125,
  "created_at": "2024-12-15T10:30:00Z",
  "model_used": "claude-3-sonnet"
}
```

### Quick Summary

```bash
POST /api/summary/quick-summary/{doc_id}?summary_type=brief
```

Returns a quick summary without storing it.

### Get Document Summary

```bash
GET /api/summary/document/{doc_id}
```

Returns existing summary or generates new one.

### Batch Summarize

```json
POST /api/summary/batch
{
  "source_type": "document",
  "source_ids": ["doc_1", "doc_2", "doc_3", "doc_4", "doc_5"],
  "summary_type": "key_points",
  "max_length": 300
}
```

Response:
```json
{
  "job_id": "batch_abc123",
  "total_items": 5,
  "status": "processing",
  "completed": 0,
  "failed": 0
}
```

### List Summaries with Filtering

```bash
GET /api/summary/?source_type=document&summary_type=standard&limit=20
```

### Get Capabilities

```bash
GET /api/summary/capabilities
```

Response:
```json
{
  "llm_available": true,
  "model_name": "claude-3-sonnet",
  "supported_types": ["brief", "standard", "detailed", "key_points", "executive"],
  "max_input_length": 100000,
  "batch_processing": true,
  "auto_summarize": true
}
```

### Get Summary Types

```bash
GET /api/summary/types
```

Response:
```json
{
  "types": [
    {
      "id": "brief",
      "name": "Brief",
      "description": "Short 1-2 sentence summary",
      "typical_length": "50-100 words"
    },
    {
      "id": "standard",
      "name": "Standard",
      "description": "Paragraph-length summary",
      "typical_length": "150-300 words"
    },
    {
      "id": "detailed",
      "name": "Detailed",
      "description": "Comprehensive multi-paragraph summary",
      "typical_length": "500-1000 words"
    }
  ]
}
```

### Get Statistics

```bash
GET /api/summary/stats
```

Response:
```json
{
  "total_summaries": 250,
  "by_type": {
    "brief": 80,
    "standard": 100,
    "detailed": 40,
    "key_points": 30
  },
  "by_source": {
    "document": 200,
    "entity": 30,
    "project": 20
  },
  "avg_generation_time_ms": 2345,
  "total_tokens_used": 150000
}
```

### List Document Sources

```bash
GET /api/summary/sources/documents?has_summary=false&limit=50
```

Returns documents that can be summarized, optionally filtered by whether they already have summaries.

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `summary.summary.created` | New summary generated |
| `summary.summary.updated` | Summary regenerated |
| `summary.summary.deleted` | Summary removed |
| `summary.batch.started` | Batch summarization started |
| `summary.batch.completed` | Batch summarization finished |
| `summary.batch.failed` | Batch summarization failed |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.processed` | Auto-summarize new documents |
| `documents.document.created` | Auto-summarize new documents |

## UI Routes

| Route | Description |
|-------|-------------|
| `/summary` | All summaries |
| `/summary/documents` | Document summaries |
| `/summary/collections` | Collection summaries |
| `/summary/generate` | Generate new summary |

## Dependencies

### Required Services
- **database** - Summary storage
- **events** - Event publishing

### Optional Services
- **llm** - AI summarization (highly recommended)
- **workers** - Background batch processing

## URL State

| Parameter | Description |
|-----------|-------------|
| `summaryId` | Selected summary |
| `sourceId` | Source document/entity |
| `type` | Summary type filter |

### Local Storage Keys
- `default_type` - Preferred summary type
- `max_length` - Preferred max length
- `auto_summarize` - Auto-summarize on document creation

## Summary Quality

Summary quality depends on:
- LLM model availability and quality
- Input document length and structure
- Selected summary type
- Focus areas specified

Without LLM service, fallback extractive summarization is used.

## Development

```bash
# Run tests
pytest packages/arkham-shard-summary/tests/

# Type checking
mypy packages/arkham-shard-summary/
```

## License

MIT
