# arkham-shard-embed

> Document embeddings, vector operations, and model management

**Version:** 0.1.0
**Category:** Search
**Frame Requirement:** >=0.1.0

## Overview

The Embed shard handles vector embedding generation and management for SHATTERED. It generates embeddings for text and documents, stores them in PostgreSQL using pgvector, and provides similarity search and nearest neighbor queries. Supports multiple embedding models with project-scoped vector collections.

### Infrastructure

- **Database**: PostgreSQL 14+ with pgvector extension
- **Vector Storage**: `arkham_vectors.embeddings` table
- **Job Queue**: PostgreSQL with SKIP LOCKED pattern (no Redis)

### Key Capabilities

1. **Embedding Generation** - Generate vector embeddings for text and documents
2. **Similarity Search** - Calculate similarity between texts
3. **Nearest Neighbor Search** - Find similar documents in vector space
4. **Model Management** - Switch between embedding models with dimension handling
5. **GPU Acceleration** - Hardware-accelerated embedding generation

## Features

### Embedding Generation
- Single text embedding (sync)
- Batch text embedding
- Document chunk embedding (async via workers)
- Multi-document batch embedding
- Embedding caching for performance

### Vector Operations
- Cosine similarity calculation
- Nearest neighbor search with filters
- Project-scoped vector collections
- Multiple collection support (documents, chunks, entities)

### Model Management
- Multiple embedding models supported
- Model switching with automatic dimension handling
- Collection recreation on dimension change
- Model info and statistics

### Supported Models

| Model | Dimensions | Max Length | Description |
|-------|------------|------------|-------------|
| `all-MiniLM-L6-v2` | 384 | 512 | Lightweight, fast (default) |
| `all-mpnet-base-v2` | 768 | 512 | High quality, balanced |
| `BAAI/bge-m3` | 1024 | 8192 | Multilingual, highest quality |
| `paraphrase-MiniLM-L6-v2` | 384 | 512 | Paraphrase detection |

### Cache Management
- LRU cache for embeddings
- Cache statistics
- Cache clearing

## Installation

```bash
pip install -e packages/arkham-shard-embed
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Text Embedding

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/embed/text` | Embed single text |
| POST | `/api/embed/batch` | Embed multiple texts |

### Document Embedding

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/embed/document/{id}` | Queue document for embedding |
| GET | `/api/embed/document/{id}` | Get document embeddings |
| GET | `/api/embed/documents/available` | List documents with embedding status |
| POST | `/api/embed/documents/batch` | Queue multiple documents |

### Similarity and Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/embed/similarity` | Calculate text similarity |
| POST | `/api/embed/nearest` | Find nearest neighbors |

### Model Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/embed/models` | List available models |
| GET | `/api/embed/model/current` | Get current model info |
| GET | `/api/embed/model/available` | List all supported models |
| GET | `/api/embed/model/collections` | Get vector collection info |
| POST | `/api/embed/model/check-switch` | Check model switch impact |
| POST | `/api/embed/model/switch` | Switch embedding model |

### Configuration and Cache

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/embed/config` | Update embedding config |
| GET | `/api/embed/cache/stats` | Get cache statistics |
| POST | `/api/embed/cache/clear` | Clear embedding cache |

## API Examples

### Embed Single Text

```json
POST /api/embed/text
{
  "text": "This is a sample document for embedding.",
  "doc_id": "doc_123",
  "chunk_id": "chunk_001",
  "use_cache": true
}
```

Response:
```json
{
  "embedding": [0.023, -0.156, 0.089, ...],
  "dimensions": 384,
  "model": "all-MiniLM-L6-v2",
  "doc_id": "doc_123",
  "chunk_id": "chunk_001",
  "text_length": 43,
  "success": true
}
```

### Batch Embed Texts

```json
POST /api/embed/batch
{
  "texts": [
    "First document text",
    "Second document text",
    "Third document text"
  ],
  "batch_size": 32
}
```

### Queue Document for Embedding

```bash
POST /api/embed/document/doc_abc123
```

Queues all chunks of the document for embedding via the `gpu-embed` worker pool.

### Find Nearest Neighbors

```json
POST /api/embed/nearest
{
  "query": "search query text",
  "limit": 10,
  "min_similarity": 0.5,
  "collection": "documents",
  "filters": {"project_id": "proj_123"}
}
```

### Calculate Similarity

```json
POST /api/embed/similarity
{
  "text1": "The quick brown fox",
  "text2": "A fast brown fox",
  "method": "cosine"
}
```

Response:
```json
{
  "similarity": 0.89,
  "method": "cosine",
  "success": true
}
```

### Check Model Switch Impact

```json
POST /api/embed/model/check-switch
{
  "model": "BAAI/bge-m3"
}
```

Response shows if wipe is required and affected collections.

### Switch Embedding Model

```json
POST /api/embed/model/switch
{
  "model": "BAAI/bge-m3",
  "confirm_wipe": true
}
```

**Warning:** If dimensions differ, all vector collections will be wiped!

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `embed.embedding.created` | New embedding generated |
| `embed.batch.completed` | Batch embedding finished |
| `embed.model.loaded` | Embedding model loaded |
| `embed.model.switched` | Model switched |
| `embed.text.completed` | Text embedding completed |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.ingested` | Auto-embed new documents |
| `document.processed` | Embed processed documents |
| `parse.document.completed` | Embed parsed document chunks |

## Project-Scoped Collections

When a project is active, embeddings are scoped by project_id in the `arkham_vectors.embeddings` table. This allows different projects to maintain separate vector spaces.

The embeddings table schema includes:
- `id` - Unique embedding identifier
- `doc_id` - Associated document ID
- `chunk_id` - Associated chunk ID
- `project_id` - Project scope (nullable)
- `embedding` - Vector data (pgvector)
- `model` - Embedding model used
- `created_at` - Timestamp

## UI Routes

| Route | Description |
|-------|-------------|
| `/embed` | Embeddings management interface |

## Dependencies

### Required Services
- **database** - PostgreSQL 14+ with pgvector extension
- **workers** - Background embedding jobs (PostgreSQL SKIP LOCKED)
- **events** - Event publishing

### Optional Services
- **documents** - Document access for batch embedding

## Configuration

### Embedding Config

| Setting | Description |
|---------|-------------|
| `batch_size` | Batch size for embedding |
| `cache_size` | LRU cache size |
| `device` | Device for model (cpu/cuda) |

### Model Info

Each model provides:
- `name` - Model identifier
- `dimensions` - Vector dimensions
- `max_length` - Maximum input length
- `size_mb` - Model size
- `device` - Current device
- `loaded` - Whether model is loaded

## Architecture Notes

### Worker Integration
Document embedding is processed by the `gpu-embed` worker pool. Jobs include all chunk texts and IDs for batch processing.

### Dimension Changes
When switching to a model with different dimensions:
1. Existing embeddings with different dimensions must be deleted
2. The embeddings table supports multiple dimensions via pgvector
3. All documents need re-embedding
4. Requires `confirm_wipe: true` in request

### Caching
Embeddings are cached using an LRU cache keyed by text hash. This significantly speeds up repeated queries for the same text.

## Development

```bash
# Run tests
pytest packages/arkham-shard-embed/tests/

# Type checking
mypy packages/arkham-shard-embed/
```

## License

MIT
