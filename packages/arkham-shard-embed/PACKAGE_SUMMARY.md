# Embed Shard - Package Summary

**Version**: 0.1.0
**Package Name**: arkham-shard-embed
**Entry Point**: `arkham.shards.embed = arkham_shard_embed:EmbedShard`

## Overview

The Embed Shard is a core component of the ArkhamFrame modular architecture, providing document embedding and vector operations for semantic search and similarity matching. It handles text-to-vector conversion using state-of-the-art transformer models and manages vector storage in Qdrant.

## Package Structure

```
arkham-shard-embed/
├── arkham_shard_embed/          # Main package
│   ├── __init__.py              # Package exports
│   ├── shard.py                 # EmbedShard class (main entry)
│   ├── api.py                   # FastAPI endpoints (10+ routes)
│   ├── embedder.py              # EmbeddingManager (core logic)
│   ├── storage.py               # VectorStore (Qdrant wrapper)
│   └── models.py                # Data models and types
├── examples/                     # Usage examples
│   ├── __init__.py
│   └── basic_usage.py           # 8 practical examples
├── tests/                        # Test suite
│   ├── __init__.py
│   └── test_embedder.py         # Comprehensive unit tests
├── pyproject.toml               # Package configuration
├── shard.yaml                   # Shard manifest
├── README.md                    # Main documentation
├── QUICKSTART.md                # 5-minute quick start
├── INTEGRATION.md               # Integration guide
├── ARCHITECTURE.md              # Architecture details
└── .gitignore                   # Git ignore rules
```

## Key Components

### 1. EmbedShard (shard.py)
**Lines**: ~300
**Purpose**: Main shard class, lifecycle management, service coordination

**Key Methods**:
- `initialize(frame)` - Setup with Frame services
- `shutdown()` - Cleanup resources
- `embed_text(text)` - Public API for text embedding
- `embed_batch(texts)` - Public API for batch embedding
- `find_similar(query)` - Public API for similarity search
- `store_embedding(embedding, payload)` - Public API for storage

**Event Handling**:
- Subscribes: `documents.ingested`, `documents.chunks.created`
- Publishes: `embed.text.completed`, `embed.batch.completed`, `embed.document.completed`

### 2. EmbeddingManager (embedder.py)
**Lines**: ~280
**Purpose**: Model management and embedding generation

**Key Features**:
- Lazy model loading (loads on first use)
- Automatic GPU/CPU detection
- LRU cache for frequently embedded texts
- Batch processing optimization
- Multiple similarity metrics

**Methods**:
- `embed_text(text, use_cache)` - Embed single text
- `embed_batch(texts, batch_size)` - Embed multiple texts
- `calculate_similarity(emb1, emb2, method)` - Similarity calculation
- `chunk_text(text, chunk_size, overlap)` - Text chunking
- `get_model_info()` - Model metadata
- `clear_cache()` - Cache management

### 3. VectorStore (storage.py)
**Lines**: ~280
**Purpose**: Vector database operations wrapper

**Methods**:
- `create_collection(name, vector_size)` - Collection setup
- `upsert_vector(collection, vector, payload)` - Single insert
- `upsert_batch(collection, vectors, payloads)` - Batch insert
- `search(collection, query_vector, limit)` - Similarity search
- `delete_vectors(collection, ids)` - Vector deletion
- `get_collection_info(collection)` - Collection metadata

### 4. API Router (api.py)
**Lines**: ~420
**Purpose**: HTTP endpoints for external access

**Endpoints**:
1. `POST /api/embed/text` - Embed single text
2. `POST /api/embed/batch` - Embed batch of texts
3. `POST /api/embed/document/{doc_id}` - Queue document embedding
4. `GET /api/embed/document/{doc_id}` - Get document embeddings
5. `POST /api/embed/similarity` - Calculate text similarity
6. `POST /api/embed/nearest` - Find nearest neighbors
7. `GET /api/embed/models` - List available models
8. `POST /api/embed/config` - Update configuration
9. `GET /api/embed/cache/stats` - Cache statistics
10. `POST /api/embed/cache/clear` - Clear cache

### 5. Data Models (models.py)
**Lines**: ~95
**Purpose**: Type definitions and data structures

**Models**:
- `EmbedRequest`, `BatchEmbedRequest` - Request types
- `EmbedResult`, `BatchEmbedResult` - Result types
- `SimilarityRequest`, `SimilarityResult` - Similarity types
- `NearestRequest`, `NearestResult` - Search types
- `EmbedConfig`, `ModelInfo` - Configuration types
- `DocumentEmbedRequest` - Document processing type

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_MODEL` | `BAAI/bge-m3` | Embedding model name |
| `EMBED_DEVICE` | `auto` | Device (cpu/cuda/mps/auto) |
| `EMBED_BATCH_SIZE` | `32` | Batch processing size |
| `EMBED_CACHE_SIZE` | `1000` | LRU cache size |

### Supported Models

| Model | Dimensions | Size | Description |
|-------|------------|------|-------------|
| BAAI/bge-m3 | 1024 | 2.2 GB | Multilingual, high quality |
| all-MiniLM-L6-v2 | 384 | 80 MB | Fast, lightweight |
| BAAI/bge-large-en-v1.5 | 1024 | 1.3 GB | English, high quality |
| all-mpnet-base-v2 | 768 | 420 MB | Good balance |

## Dependencies

### Required
- `arkham-frame>=0.1.0` - Framework core
- `numpy>=1.24.0` - Numerical operations
- `sentence-transformers>=2.2.0` - Embedding models

### Optional
- `torch` - GPU acceleration
- `pytest` - Testing
- `pytest-asyncio` - Async tests

### Frame Service Dependencies

**Required**:
- `vectors` - Qdrant vector storage
- `events` - Event bus for pub/sub

**Optional**:
- `workers` - Job queue for async processing
- `documents` - Document management

## API Usage Examples

### Example 1: Embed Single Text
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/api/embed/text",
        json={"text": "Sample document text"}
    )
    result = response.json()
    embedding = result['embedding']  # List of floats
```

### Example 2: Batch Embedding
```python
response = await client.post(
    "http://localhost:8000/api/embed/batch",
    json={"texts": ["Text 1", "Text 2", "Text 3"]}
)
embeddings = response.json()['embeddings']
```

### Example 3: Similarity Search
```python
response = await client.post(
    "http://localhost:8000/api/embed/nearest",
    json={
        "query": "corruption investigation",
        "limit": 10,
        "min_similarity": 0.7
    }
)
results = response.json()['neighbors']
```

## Public Shard API

Other shards can use the Embed Shard directly:

```python
# Get the shard
embed_shard = frame.get_shard("embed")

# Embed text
embedding = await embed_shard.embed_text("Text to embed")

# Batch embed
embeddings = await embed_shard.embed_batch(["Text 1", "Text 2"])

# Find similar
results = await embed_shard.find_similar(
    query="search query",
    collection="documents",
    limit=10
)

# Store embedding
vector_id = await embed_shard.store_embedding(
    embedding=embedding,
    payload={"doc_id": "123"},
    collection="documents"
)
```

## Testing

### Run Tests
```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# With coverage
pytest --cov=arkham_shard_embed tests/
```

### Test Coverage

**test_embedder.py** (26 tests):
- Device detection
- Single text embedding
- Batch embedding
- Caching behavior
- Similarity calculations (cosine, euclidean, dot)
- Text chunking
- Model loading
- Edge cases (empty text, long text, special chars)

## Performance Characteristics

### Throughput
- Single embedding: 5-50 ms (depends on model, device)
- Batch (32 texts): 100-500 ms (~5-15 ms per text)
- Cache hit: <1 ms

### Memory Usage
- Model (BGE-M3): ~2.2 GB
- Model (MiniLM): ~80 MB
- Cache (1000 items): ~50-100 MB

### Scaling
- Horizontal: Multiple worker instances
- Vertical: GPU acceleration (10-100x faster)
- Batch size: 32-64 optimal for most GPUs

## Integration Patterns

### Pattern 1: Direct HTTP API
```
Client → HTTP Request → Embed Shard API → Response
```

### Pattern 2: Shard-to-Shard
```
Other Shard → frame.get_shard("embed") → Public Methods → Results
```

### Pattern 3: Event-Driven
```
Event → Embed Shard Handler → Queue Job → Worker → Storage
```

## Event System

### Published Events
- `embed.text.completed` - Single text embedded
- `embed.batch.completed` - Batch embedded
- `embed.document.completed` - Document embedded
- `embed.model.loaded` - Model loaded into memory

### Subscribed Events
- `documents.ingested` - Auto-queue embedding for new documents
- `documents.chunks.created` - Trigger chunk embedding

## Documentation Files

| File | Lines | Purpose |
|------|-------|---------|
| README.md | ~240 | Main documentation, API reference |
| QUICKSTART.md | ~220 | 5-minute quick start guide |
| INTEGRATION.md | ~370 | Detailed integration guide |
| ARCHITECTURE.md | ~480 | Architecture and design details |
| PACKAGE_SUMMARY.md | ~280 | This file - package overview |

## Installation

```bash
# From PyPI (when published)
pip install arkham-shard-embed

# From source
cd packages/arkham-shard-embed
pip install -e .

# With dev dependencies
pip install -e ".[dev]"
```

## Development Workflow

1. **Install in dev mode**: `pip install -e .`
2. **Make changes**: Edit code in `arkham_shard_embed/`
3. **Run tests**: `pytest tests/`
4. **Check types**: `mypy arkham_shard_embed/`
5. **Format code**: `black arkham_shard_embed/`
6. **Build package**: `python -m build`

## Version History

### 0.1.0 (Initial Release)
- Core embedding functionality
- Batch processing support
- Vector storage integration
- Event-driven processing
- Comprehensive API
- GPU acceleration
- LRU caching
- Multiple similarity metrics
- Auto device detection

## License

Part of the ArkhamFrame project.

## Links

- Main README: [README.md](README.md)
- Quick Start: [QUICKSTART.md](QUICKSTART.md)
- Integration Guide: [INTEGRATION.md](INTEGRATION.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Examples: [examples/basic_usage.py](examples/basic_usage.py)
- Tests: [tests/test_embedder.py](tests/test_embedder.py)

## Contact

For issues and questions, see the main ArkhamFrame documentation.
