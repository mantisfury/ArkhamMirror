# ArkhamFrame Search Shard

Semantic and keyword search for ArkhamMirror documents.

## Features

- **Semantic Search**: Vector similarity search using Qdrant
- **Keyword Search**: Full-text search using PostgreSQL
- **Hybrid Search**: Combines semantic and keyword with configurable weights
- **Similarity Search**: Find documents similar to a given document
- **Autocomplete**: Query suggestions for search-as-you-type
- **Advanced Filtering**: Filter by date, entities, projects, file types, tags
- **Result Ranking**: Multiple ranking strategies including recency and entity-based

## Installation

```bash
pip install arkham-shard-search
```

The shard is automatically discovered by ArkhamFrame via entry points.

## API Endpoints

### POST /api/search
Main search endpoint supporting all modes.

**Request:**
```json
{
  "query": "search query",
  "mode": "hybrid",
  "filters": {
    "date_range": {
      "start": "2024-01-01T00:00:00",
      "end": "2024-12-31T23:59:59"
    },
    "entity_ids": ["ent123", "ent456"],
    "project_ids": ["proj1"],
    "file_types": ["pdf", "docx"],
    "tags": ["important"],
    "min_score": 0.5
  },
  "limit": 20,
  "offset": 0,
  "sort_by": "relevance",
  "sort_order": "desc",
  "semantic_weight": 0.7,
  "keyword_weight": 0.3
}
```

**Response:**
```json
{
  "query": "search query",
  "mode": "hybrid",
  "total": 42,
  "items": [
    {
      "doc_id": "doc123",
      "chunk_id": "chunk456",
      "title": "Document Title",
      "excerpt": "Relevant excerpt...",
      "score": 0.85,
      "file_type": "pdf",
      "created_at": "2024-01-15T10:30:00",
      "page_number": 3,
      "highlights": ["...matching text..."],
      "entities": ["ent123", "ent456"],
      "project_ids": ["proj1"],
      "metadata": {}
    }
  ],
  "duration_ms": 45.2,
  "facets": {},
  "offset": 0,
  "limit": 20,
  "has_more": true
}
```

### POST /api/search/semantic
Vector-only semantic search.

### POST /api/search/keyword
Text-only keyword search.

### GET /api/search/suggest?q=prefix&limit=10
Autocomplete suggestions.

**Response:**
```json
{
  "suggestions": [
    {
      "text": "suggested term",
      "score": 0.9,
      "type": "term"
    }
  ]
}
```

### POST /api/search/similar/{doc_id}
Find similar documents.

**Request:**
```json
{
  "limit": 10,
  "min_similarity": 0.5,
  "filters": {}
}
```

**Response:**
```json
{
  "doc_id": "doc123",
  "similar": [...],
  "total": 8
}
```

### GET /api/search/filters?q=query
Get available filter options with counts.

## Usage from Other Shards

```python
# Get the search shard
search_shard = frame.get_shard("search")

# Perform search
results = await search_shard.search(
    query="investigation",
    mode="hybrid",
    limit=20,
)

# Find similar documents
similar = await search_shard.find_similar(
    doc_id="doc123",
    limit=10,
    min_similarity=0.7,
)
```

## Architecture

### Search Engines

- **SemanticSearchEngine**: Vector similarity via Qdrant
- **KeywordSearchEngine**: Full-text via PostgreSQL ts_vector
- **HybridSearchEngine**: Reciprocal Rank Fusion (RRF) merging

### Ranking Strategies

- Relevance (default)
- Date/recency
- Entity-based boosting
- Exact match boosting
- Result diversification

### Filters

- Date range
- Entity IDs
- Project IDs
- File types
- Tags
- Minimum score threshold

## Dependencies

- `arkham-frame>=0.1.0`
- Qdrant vector store (for semantic search)
- PostgreSQL (for keyword search)

## Events

**Published:**
- `search.query.executed` - When a search is performed
- `search.results.found` - When results are returned

**Subscribed:**
- `documents.indexed` - To invalidate caches
- `documents.deleted` - To clean up caches

## Configuration

Search engines are automatically configured based on available Frame services:

- `vectors` service enables semantic search
- `database` service enables keyword search
- Both services enable hybrid search

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black arkham_shard_search/
```
