# Parse Shard

Entity extraction and parsing shard for ArkhamFrame.

## Features

- **Named Entity Recognition (NER)** - Extract persons, organizations, locations, dates, and more using spaCy
- **Date/Time Extraction** - Parse dates in various formats
- **Location Extraction** - Extract and geocode geographic locations
- **Relationship Extraction** - Find relationships between entities
- **Entity Linking** - Map mentions to canonical entities
- **Coreference Resolution** - Resolve pronouns to entities
- **Text Chunking** - Split text into embedding-ready chunks

## Installation

```bash
pip install arkham-shard-parse
```

## Requirements

- Python 3.10+
- spaCy with `en_core_web_sm` model
- arkham-frame >= 0.1.0

Install spaCy model:

```bash
python -m spacy download en_core_web_sm
```

## API Endpoints

### Parse Text

```
POST /api/parse/text
```

Parse raw text and extract entities.

**Request:**
```json
{
  "text": "Apple Inc. announced new products on January 15, 2024.",
  "extract_entities": true,
  "extract_dates": true
}
```

**Response:**
```json
{
  "entities": [
    {
      "text": "Apple Inc.",
      "entity_type": "ORG",
      "confidence": 0.85
    }
  ],
  "dates": [
    {
      "text": "January 15, 2024",
      "normalized_date": "2024-01-15T00:00:00"
    }
  ],
  "total_entities": 1,
  "processing_time_ms": 45.2
}
```

### Parse Document

```
POST /api/parse/document/{doc_id}
```

Parse a full document (async, dispatches to worker).

### Get Entities

```
GET /api/parse/entities/{doc_id}
```

Get extracted entities for a document.

### Chunk Text

```
POST /api/parse/chunk
```

Chunk text into embedding-ready segments.

**Request:**
```json
{
  "text": "Long text here...",
  "chunk_size": 500,
  "overlap": 50,
  "method": "sentence"
}
```

### Link Entities

```
POST /api/parse/link
```

Link entity mentions to canonical entities.

## Configuration

Add to Frame config:

```python
config = {
    "parse.spacy_model": "en_core_web_sm",
    "parse.chunk_size": 500,
    "parse.chunk_overlap": 50,
    "parse.chunk_method": "sentence",
}
```

## Events

### Published

- `parse.document.started` - Parsing started
- `parse.document.completed` - Parsing completed
- `parse.entities.extracted` - Entities extracted
- `parse.chunks.created` - Chunks created

### Subscribed

- `ingest.job.completed` - Auto-parse ingested documents
- `worker.job.completed` - Handle worker results

## Worker Pools

Uses these worker pools:

- `cpu-ner` - Named entity recognition (spaCy)
- `cpu-heavy` - Complex text processing

## License

MIT
