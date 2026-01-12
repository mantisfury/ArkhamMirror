# arkham-shard-parse

> Entity extraction, NER, relationship extraction, and text chunking

**Version:** 0.1.0
**Category:** Data
**Frame Requirement:** >=0.1.0

## Overview

The Parse shard handles text analysis and extraction for SHATTERED. It performs Named Entity Recognition (NER), date extraction, location extraction, relationship extraction, coreference resolution, and text chunking. Supports both synchronous parsing for small text and async worker-based parsing for full documents.

### Key Capabilities

1. **Entity Extraction** - NER for persons, organizations, locations, dates, etc.
2. **Relationship Extraction** - Extract relationships between entities
3. **Text Chunking** - Split documents into embedding-ready segments
4. **Entity Linking** - Link mentions to canonical entities
5. **Coreference Resolution** - Resolve pronouns and references

## Features

### Named Entity Recognition (NER)
- Person names (PERSON)
- Organizations (ORG)
- Geopolitical entities (GPE)
- Locations (LOC)
- Dates and times (DATE, TIME)
- Money and quantities (MONEY, QUANTITY)
- And more entity types

### Date Extraction
- Absolute dates
- Relative dates
- Date ranges
- Temporal expressions

### Relationship Extraction
- Person-to-organization relationships
- Person-to-person relationships
- Entity co-occurrence
- Contextual relationships

### Text Chunking
- **Fixed** - Fixed character count chunks
- **Sentence** - Sentence-boundary aware chunking
- **Semantic** - Semantic similarity-based chunking
- Configurable chunk size and overlap
- Token counting

### Entity Linking
- Match mentions to canonical entities
- Create new canonical entities for unmatched mentions
- Confidence scoring

## Installation

```bash
pip install -e packages/arkham-shard-parse
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Text Parsing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/parse/text` | Parse raw text (sync) |
| POST | `/api/parse/chunk` | Chunk raw text |

### Document Parsing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/parse/document/{id}` | Parse document (async via workers) |
| POST | `/api/parse/document/{id}/sync` | Parse document (sync) |
| GET | `/api/parse/entities/{doc_id}` | Get document entities |
| GET | `/api/parse/chunks/{doc_id}` | Get document chunks |

### Chunk Browser

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/parse/chunks` | List all chunks (paginated) |

### Entity Linking

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/parse/link` | Link entity mentions |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/parse/config/chunking` | Get chunking config |
| PUT | `/api/parse/config/chunking` | Update chunking config |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/parse/stats` | Get parsing statistics |

## API Examples

### Parse Raw Text

```json
POST /api/parse/text
{
  "text": "John Smith met with Acme Corp CEO Jane Doe on January 15, 2024.",
  "extract_entities": true,
  "extract_dates": true,
  "extract_locations": true,
  "extract_relationships": true
}
```

Response:
```json
{
  "entities": [
    {"text": "John Smith", "entity_type": "PERSON", "confidence": 0.95},
    {"text": "Acme Corp", "entity_type": "ORG", "confidence": 0.92},
    {"text": "Jane Doe", "entity_type": "PERSON", "confidence": 0.94}
  ],
  "dates": [
    {"text": "January 15, 2024", "normalized": "2024-01-15"}
  ],
  "locations": [],
  "relationships": [
    {"subject": "Jane Doe", "predicate": "CEO_OF", "object": "Acme Corp"}
  ],
  "total_entities": 3,
  "total_dates": 1,
  "total_locations": 0,
  "processing_time_ms": 45.2
}
```

### Chunk Text

```json
POST /api/parse/chunk
{
  "text": "Long document text here...",
  "chunk_size": 500,
  "overlap": 50,
  "method": "sentence"
}
```

### Parse Document (Async)

```bash
POST /api/parse/document/doc_abc123
```

Returns immediately with status "processing". Listen for `parse.document.completed` event.

### Parse Document (Sync)

```bash
POST /api/parse/document/doc_abc123/sync?save_chunks=true
```

Returns full parse results when complete.

### Update Chunking Configuration

```json
PUT /api/parse/config/chunking
{
  "chunk_size": 750,
  "chunk_overlap": 100,
  "chunk_method": "semantic"
}
```

### List All Chunks

```bash
GET /api/parse/chunks?limit=50&offset=0&document_id=doc_abc123
```

Response includes chunk text, document info, token counts, and vector IDs.

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `parse.document.started` | Document parsing started |
| `parse.document.completed` | Document parsing finished |
| `parse.entities.extracted` | Entities extracted from document |
| `parse.chunks.created` | Chunks created for document |
| `parse.config.updated` | Chunking config changed |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `ingest.job.completed` | Auto-parse ingested documents |
| `worker.job.completed` | Update parse job status |

## Chunking Methods

### Fixed
Simple character-count based chunking. Fast but may split mid-sentence.

### Sentence
Respects sentence boundaries. Better for semantic coherence.

### Semantic
Uses semantic similarity to group related content. Best quality but slower.

## Configuration

### Chunking Defaults

| Setting | Default | Description |
|---------|---------|-------------|
| `chunk_size` | 500 | Target chunk size in characters |
| `chunk_overlap` | 50 | Overlap between chunks |
| `chunk_method` | sentence | Chunking method |

### Validation Rules
- `chunk_size` must be at least 50 characters
- `chunk_overlap` must be non-negative
- `chunk_overlap` must be less than `chunk_size`

## UI Routes

| Route | Description |
|-------|-------------|
| `/parse` | Parse & Extract interface |

## Dependencies

### Required Services
- **database** - PostgreSQL 14+ for chunk and entity storage
- **workers** - PostgreSQL job queue (SKIP LOCKED pattern)
- **events** - Event publishing

### Optional Services
- **documents** - Document content access
- **entities** - Entity storage

### Infrastructure Notes
This shard uses PostgreSQL for all persistence and job queuing. No Redis or external queue system is required. Parsed chunks are stored in PostgreSQL and can be vectorized using pgvector.

## URL State

| Parameter | Description |
|-----------|-------------|
| `documentId` | Document being viewed |

## Statistics

The `/api/parse/stats` endpoint returns:
- `total_entities` - Total extracted entities
- `total_chunks` - Total chunks created
- `total_documents_parsed` - Documents with chunks
- `entity_types` - Count by entity type

## Architecture Notes

### Worker Integration
Document parsing dispatches to the `cpu-ner` worker pool for heavy NER processing. The sync endpoint bypasses workers for testing and debugging.

### Event Flow
1. `ingest.job.completed` triggers auto-parse
2. Parse shard extracts entities and creates chunks
3. `parse.document.completed` triggers embed shard for vectorization

## Development

```bash
# Run tests
pytest packages/arkham-shard-parse/tests/

# Type checking
mypy packages/arkham-shard-parse/
```

## License

MIT
