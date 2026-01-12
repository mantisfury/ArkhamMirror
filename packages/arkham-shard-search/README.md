# arkham-shard-search

> Semantic and keyword search for documents

**Version:** 0.1.0
**Category:** Search
**Frame Requirement:** >=0.1.0

## Overview

The Search shard provides comprehensive search capabilities for SHATTERED documents and content. It supports semantic search (vector similarity), keyword search (full-text), and hybrid search combining both approaches with configurable weights. Features include autocomplete suggestions, similar document discovery, and AI-assisted search chat.

### Key Capabilities

1. **Semantic Search** - Vector similarity search using embeddings
2. **Keyword Search** - PostgreSQL full-text search with BM25
3. **Hybrid Search** - Combined semantic + keyword with weights
4. **Similarity Search** - Find similar documents
5. **Autocomplete Suggestions** - Query suggestions

## Features

### Search Modes
- `hybrid` - Combines semantic and keyword (default)
- `semantic` - Vector similarity only
- `keyword` - Full-text search only

### Search Features
- Configurable semantic/keyword weights
- Filter by project, document type, date range
- Sort by relevance, date, name
- Pagination support
- Result facets
- Query suggestions

### Similarity Search
- Find documents similar to a given document
- Uses vector embeddings
- Configurable result count

### AI Chat Search
- Conversational search interface
- Context-aware follow-up queries
- Source attribution
- Streaming responses

## Installation

```bash
pip install -e packages/arkham-shard-search
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/search/` | Main search endpoint |
| POST | `/api/search/semantic` | Semantic search only |
| POST | `/api/search/keyword` | Keyword search only |

### Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/search/suggest` | Query suggestions |
| POST | `/api/search/similar/{doc_id}` | Find similar docs |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/search/config` | Get search config |
| GET | `/api/search/filters` | Available filters |

### AI Features

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/search/ai/junior-analyst` | AI analysis |
| POST | `/api/search/chat` | Conversational search |
| POST | `/api/search/ai/feedback` | Submit feedback |

## API Examples

### Hybrid Search

```json
POST /api/search/
{
  "query": "financial fraud investigation",
  "mode": "hybrid",
  "filters": {
    "project_id": "proj_123",
    "document_type": ["pdf", "docx"],
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-12-31"
    }
  },
  "limit": 20,
  "offset": 0,
  "sort_by": "relevance",
  "sort_order": "desc",
  "semantic_weight": 0.7,
  "keyword_weight": 0.3
}
```

Response:
```json
{
  "query": "financial fraud investigation",
  "mode": "hybrid",
  "total": 45,
  "items": [
    {
      "id": "doc_abc123",
      "title": "Q3 Financial Review",
      "filename": "q3_review.pdf",
      "snippet": "...investigation revealed significant discrepancies in the financial...",
      "score": 0.92,
      "semantic_score": 0.95,
      "keyword_score": 0.85,
      "document_type": "pdf",
      "created_at": "2024-10-15T14:30:00Z",
      "highlights": ["investigation", "financial"]
    }
  ],
  "duration_ms": 125.5,
  "facets": {
    "document_type": {"pdf": 30, "docx": 15},
    "project": {"proj_123": 45}
  },
  "offset": 0,
  "limit": 20,
  "has_more": true
}
```

### Semantic Search

```json
POST /api/search/semantic
{
  "query": "documents about corporate fraud",
  "limit": 10,
  "semantic_weight": 1.0,
  "keyword_weight": 0.0
}
```

### Keyword Search

```json
POST /api/search/keyword
{
  "query": "\"quarterly report\" AND fraud",
  "limit": 10
}
```

### Query Suggestions

```bash
GET /api/search/suggest?q=fin&limit=5
```

Response:
```json
{
  "suggestions": [
    {"text": "financial fraud", "count": 25},
    {"text": "financial report", "count": 18},
    {"text": "financial analysis", "count": 12}
  ]
}
```

### Find Similar Documents

```json
POST /api/search/similar/doc_abc123
{
  "limit": 10,
  "min_score": 0.7
}
```

Response:
```json
{
  "doc_id": "doc_abc123",
  "similar": [
    {
      "id": "doc_xyz789",
      "title": "Q4 Financial Review",
      "similarity": 0.89
    }
  ],
  "total": 8
}
```

### Get Search Configuration

```bash
GET /api/search/config
```

Response:
```json
{
  "embedding_dimensions": 1536,
  "semantic_weight": 0.7,
  "keyword_weight": 0.3,
  "bm25_enabled": true,
  "engines": {
    "semantic": true,
    "keyword": true,
    "hybrid": true
  }
}
```

### Get Available Filters

```bash
GET /api/search/filters
```

Response:
```json
{
  "available": {
    "project_id": ["proj_1", "proj_2", "proj_3"],
    "document_type": ["pdf", "docx", "txt", "html"],
    "entity_types": ["PERSON", "ORGANIZATION", "GPE"],
    "status": ["processed", "pending", "failed"]
  }
}
```

### Chat Search

```json
POST /api/search/chat
{
  "message": "What documents mention financial irregularities?",
  "session_id": "chat_abc123",
  "conversation_history": [
    {"role": "user", "content": "Search for fraud cases"},
    {"role": "assistant", "content": "I found 15 documents..."}
  ]
}
```

Returns streaming response with search results and AI-generated summary.

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `search.query.executed` | Search query executed |
| `search.results.returned` | Results returned |
| `search.suggestions.generated` | Suggestions generated |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.indexed` | Invalidate caches |
| `document.deleted` | Clean up caches |
| `embed.completed` | New embeddings available |

## UI Routes

| Route | Description |
|-------|-------------|
| `/search` | Main search interface |
| `/search/semantic` | Semantic search |
| `/search/keyword` | Keyword search |

## Dependencies

### Required Services
- **database** - Keyword search (PostgreSQL full-text)
- **vectors** - Semantic search (pgvector PostgreSQL extension)
- **events** - Event publishing

### Optional Services
- **llm** - Query expansion, NLP
- **documents** - Document metadata lookup
- **entities** - Entity-based filtering

## URL State

| Parameter | Description |
|-----------|-------------|
| `q` | Search query |
| `mode` | Search mode (hybrid, semantic, keyword) |
| `project` | Project filter |

### Local Storage Keys
- `search_mode_default` - Preferred search mode
- `results_per_page` - Results limit preference

## Search Weights

The hybrid search combines semantic and keyword scores:
- `semantic_weight` - Weight for vector similarity (default: 0.7)
- `keyword_weight` - Weight for BM25 (default: 0.3)

Final score = (semantic_score * semantic_weight) + (keyword_score * keyword_weight)

Weights are automatically adjusted based on embedding model dimensions for optimal performance.

## Sort Options

| Sort By | Description |
|---------|-------------|
| `relevance` | Combined search score |
| `date` | Document date |
| `name` | Document name |
| `created_at` | Creation timestamp |

## Development

```bash
# Run tests
pytest packages/arkham-shard-search/tests/

# Type checking
mypy packages/arkham-shard-search/
```

## License

MIT
