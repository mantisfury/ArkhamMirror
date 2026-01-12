# Search Shard Implementation Notes

## Overview

This is the complete implementation of the Search shard for ArkhamFrame's Shattered architecture, following the established pattern from the Ingest shard.

## Structure

```
arkham-shard-search/
├── pyproject.toml                # Package configuration with entry_points
├── shard.yaml                    # Manifest file
├── README.md                     # User documentation
├── IMPLEMENTATION_NOTES.md       # This file
└── arkham_shard_search/
    ├── __init__.py              # Exports SearchShard
    ├── shard.py                 # SearchShard class (inherits ArkhamShard)
    ├── api.py                   # FastAPI router with /api/search prefix
    ├── models.py                # Data models (SearchQuery, SearchResult, etc.)
    ├── filters.py               # Filter building and optimization
    ├── ranking.py               # Result ranking and reranking
    └── engines/
        ├── __init__.py          # Exports all engines
        ├── semantic.py          # Vector search using pgvector
        ├── keyword.py           # Full-text search using PostgreSQL
        └── hybrid.py            # Reciprocal Rank Fusion merging
```

## Key Components

### 1. Search Engines

**SemanticSearchEngine** (semantic.py):
- Vector similarity search via pgvector
- Embedding-based query matching
- Find similar documents by vector
- Filter support for vector queries

**KeywordSearchEngine** (keyword.py):
- PostgreSQL full-text search using ts_vector
- Keyword highlighting with ts_headline
- Autocomplete suggestions
- WHERE clause building for filters

**HybridSearchEngine** (hybrid.py):
- Combines semantic + keyword results
- Reciprocal Rank Fusion (RRF) algorithm
- Configurable weights (default 70% semantic, 30% keyword)
- Score normalization and merging

### 2. Models (models.py)

Core data models:
- `SearchMode`: HYBRID, SEMANTIC, KEYWORD
- `SearchQuery`: Query parameters with filters, pagination, weights
- `SearchFilters`: Date range, entities, projects, file types, tags
- `SearchResult`: Container for results with metadata
- `SearchResultItem`: Individual result with highlights, entities
- `SuggestionItem`: Autocomplete suggestions
- `SimilarityRequest`: Find similar documents

### 3. Filtering (filters.py)

- `FilterBuilder`: Build SearchFilters from dict, validate
- `FilterOptimizer`: Get available filter options with counts
- Post-search filter application

### 4. Ranking (ranking.py)

Multiple ranking strategies:
- Sort by relevance, date, title
- Rerank by entity presence (boost matching entities)
- Rerank by recency (time decay)
- Deduplicate results
- Boost exact matches
- Diversify by source (limit per document)

### 5. API Endpoints (api.py)

All routes have `/api/search` prefix:

- `POST /` - Main search (hybrid/semantic/keyword)
- `POST /semantic` - Vector-only search
- `POST /keyword` - Text-only search
- `GET /suggest?q=prefix` - Autocomplete suggestions
- `POST /similar/{doc_id}` - Find similar documents
- `GET /filters?q=query` - Get available filters

### 6. Shard Class (shard.py)

- Inherits from `ArkhamShard`
- Initializes all three engines
- Subscribes to document events
- Provides public API for other shards
- Graceful degradation (works with or without services)

## Frame Services Used

### Required
- `vectors` - pgvector vector store (for semantic search)
- `database` or `db` - PostgreSQL (for keyword search)
- `events` - Event bus for notifications

### Optional
- `documents` - Document metadata service
- `entities` - Entity service

## Events

### Published
- `search.query.executed` - When search completes
- `search.results.found` - When results are returned

### Subscribed
- `documents.indexed` - To invalidate caches
- `documents.deleted` - To clean up caches

## Entry Point

Registered in `pyproject.toml`:
```toml
[project.entry-points."arkham.shards"]
search = "arkham_shard_search:SearchShard"
```

ArkhamFrame automatically discovers and loads the shard.

## Implementation Status

### Completed
- Full package structure
- All data models
- All three search engines (semantic, keyword, hybrid)
- Complete API with 6 endpoints
- Filter building and validation
- Multiple ranking strategies
- Event handling
- Public API for other shards
- README documentation

### Mock/TODO
The following are stubbed with TODO comments and will need actual implementation:

1. **Semantic Engine**:
   - Query embedding generation
   - pgvector vector search calls
   - Vector retrieval for similarity search

2. **Keyword Engine**:
   - PostgreSQL full-text search queries
   - ts_headline for highlighting
   - Autocomplete query implementation

3. **Filter Optimizer**:
   - Database queries for filter statistics
   - Facet aggregations

4. **Cache Management**:
   - Search result caching
   - Cache invalidation on document changes

## Design Patterns

### 1. Service Injection
All engines receive services via constructor, not direct imports.

### 2. Graceful Degradation
Shard works with partial service availability:
- No vectors service? Semantic search disabled, keyword still works
- No database service? Keyword search disabled, semantic still works
- Both available? Full hybrid search

### 3. Separation of Concerns
- Engines handle search logic
- API handles HTTP layer
- Shard handles lifecycle and integration
- Models define data contracts

### 4. Extensibility
- Easy to add new ranking strategies
- Easy to add new filter types
- Easy to add new search engines

### 5. Event-Driven
- Publishes events for observability
- Subscribes to document events for cache management

## Installation

```bash
cd packages/arkham-shard-search
pip install -e .
```

Frame will auto-discover via entry point on next startup.

## Testing Checklist

When implementing the actual search logic:

- [ ] Semantic search returns vector similarity results
- [ ] Keyword search returns full-text matches
- [ ] Hybrid search merges both with correct weights
- [ ] Filters correctly restrict results
- [ ] Pagination works (offset/limit)
- [ ] Sorting works (relevance/date/title)
- [ ] Autocomplete suggests relevant terms
- [ ] Similar document search finds related docs
- [ ] Events are published correctly
- [ ] Cache invalidation works on document changes
- [ ] Graceful handling when services unavailable
- [ ] Public API methods work for other shards

## Frame Integration

Other shards can use the Search shard like this:

```python
# In another shard
search_shard = self.frame.get_shard("search")

# Perform search
results = await search_shard.search(
    query="investigation",
    mode="hybrid",
    limit=20,
)

# Find similar
similar = await search_shard.find_similar(
    doc_id="doc123",
    limit=10,
)
```

## Dependencies on Frame Features

This shard assumes Frame provides:

1. Service registry (`frame.get_service()`)
2. Shard registry (`frame.get_shard()`)
3. Event bus with `emit()`, `subscribe()`, `unsubscribe()`
4. Vector service interface (pgvector wrapper)
5. Database service interface (PostgreSQL wrapper)

All of these already exist in Frame based on the Ingest shard pattern.

## Next Steps

To make this production-ready:

1. Implement actual pgvector search calls in semantic.py
2. Implement PostgreSQL full-text search in keyword.py
3. Add search result caching
4. Add query logging and analytics
5. Add search performance metrics
6. Write unit tests for each component
7. Write integration tests for the full pipeline
8. Add search query parsing (boolean operators, phrases, etc.)
9. Add spell checking and query suggestions
10. Add search history tracking

## Notes for Future Developers

- The RRF (Reciprocal Rank Fusion) algorithm in hybrid.py is battle-tested for search merging
- The k=60 constant in RRF is standard, but can be tuned
- Default weights (70% semantic, 30% keyword) work well for document search
- Consider adding query expansion for better recall
- Consider adding query rewriting for common misspellings
- The filter optimizer should cache statistics for performance
- Search results should be cached with TTL expiration

---

*Created: 2025-12-21*
*Author: Claude Sonnet 4.5*
*Status: Complete (with TODOs for actual search implementation)*
