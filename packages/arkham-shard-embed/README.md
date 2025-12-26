# Embed Shard

Document embeddings and vector operations for ArkhamFrame.

## Features

- **Text Embedding**: Generate embeddings for single texts or batches
- **Document Embedding**: Automatically embed document chunks
- **Vector Storage**: Store and retrieve embeddings in Qdrant
- **Similarity Search**: Find similar texts and documents
- **Model Management**: Support for multiple embedding models with lazy loading
- **Caching**: LRU cache for frequently embedded texts
- **GPU Acceleration**: Automatic GPU detection with CPU fallback

## Installation

```bash
pip install arkham-shard-embed
```

## Configuration

Set these environment variables to configure the shard:

- `EMBED_MODEL` - Embedding model name (default: `BAAI/bge-m3`)
- `EMBED_DEVICE` - Device for inference (default: `auto`)
- `EMBED_BATCH_SIZE` - Batch size for processing (default: `32`)
- `EMBED_CACHE_SIZE` - LRU cache size (default: `1000`)

## Supported Models

### BAAI/bge-m3 (Default)
- Dimensions: 1024
- Multilingual support
- High-quality embeddings
- Size: ~2.2GB

### all-MiniLM-L6-v2 (Fallback)
- Dimensions: 384
- Fast and lightweight
- Good for resource-constrained environments
- Size: ~80MB

## API Endpoints

### POST /api/embed/text
Embed a single text and return the vector immediately.

```json
{
  "text": "Your text here",
  "doc_id": "optional-doc-id",
  "chunk_id": "optional-chunk-id",
  "use_cache": true
}
```

### POST /api/embed/batch
Embed multiple texts efficiently in a batch.

```json
{
  "texts": ["Text 1", "Text 2", "Text 3"],
  "batch_size": 32
}
```

### POST /api/embed/document/{doc_id}
Queue an async job to embed all chunks of a document.

```json
{
  "doc_id": "document-id",
  "force": false,
  "chunk_size": 512,
  "chunk_overlap": 50
}
```

### GET /api/embed/document/{doc_id}
Retrieve existing embeddings for a document.

### POST /api/embed/similarity
Calculate similarity between two texts.

```json
{
  "text1": "First text",
  "text2": "Second text",
  "method": "cosine"
}
```

Supported methods: `cosine`, `euclidean`, `dot`

### POST /api/embed/nearest
Find nearest neighbors in vector space.

```json
{
  "query": "Query text or embedding vector",
  "limit": 10,
  "min_similarity": 0.5,
  "collection": "documents",
  "filters": {}
}
```

### GET /api/embed/models
List available embedding models.

### POST /api/embed/config
Update embedding configuration at runtime.

```json
{
  "batch_size": 64,
  "cache_size": 2000
}
```

### GET /api/embed/cache/stats
Get cache statistics (hits, misses, size).

### POST /api/embed/cache/clear
Clear the embedding cache.

## Usage from Other Shards

Other shards can access embedding functionality through the public API:

```python
# Get the embed shard
embed_shard = frame.get_shard("embed")

# Embed a single text
embedding = await embed_shard.embed_text("Your text here")

# Embed multiple texts
embeddings = await embed_shard.embed_batch(["Text 1", "Text 2", "Text 3"])

# Find similar vectors
results = await embed_shard.find_similar(
    query="Query text",
    collection="documents",
    limit=10,
    min_similarity=0.7
)

# Store an embedding
vector_id = await embed_shard.store_embedding(
    embedding=embedding,
    payload={"doc_id": "123", "text": "Original text"},
    collection="documents"
)

# Get model information
model_info = embed_shard.get_model_info()
```

## Dependencies

### Required Frame Services
- **vectors** - VectorService for storing embeddings in Qdrant
- **workers** - WorkerService for background embedding jobs (uses `gpu-embed` pool)
- **events** - EventBus for pub/sub communication

### Optional Frame Services
- **documents** - DocumentService for auto-embedding document chunks

## Events

### Published Events

- `embed.embedding.created` - Embedding created and stored
- `embed.batch.completed` - Batch embedding operation completed
- `embed.model.loaded` - Embedding model loaded into memory

### Subscribed Events

- `document.ingested` - Auto-queue embedding for new documents
- `document.processed` - Trigger embedding after document processing

## Architecture

### Components

1. **EmbeddingManager** (`embedder.py`)
   - Model loading and management
   - Text embedding (single and batch)
   - Similarity calculations
   - Text chunking
   - Cache management

2. **VectorStore** (`storage.py`)
   - Qdrant vector storage wrapper
   - Collection management
   - Vector upsert, search, delete operations
   - Batch operations

3. **API Router** (`api.py`)
   - FastAPI endpoints
   - Request/response models
   - Error handling
   - Event emission

4. **EmbedShard** (`shard.py`)
   - Main shard class
   - Service initialization
   - Event handling
   - Public API for other shards

### Processing Pipeline

1. **Synchronous Embedding** (for immediate results)
   ```
   API Request -> EmbeddingManager -> Return Embedding
   ```

2. **Asynchronous Document Embedding** (for large documents)
   ```
   API Request -> Worker Queue -> EmbedWorker -> VectorStore
   ```

3. **Auto-Embedding on Ingestion**
   ```
   documents.ingested Event -> Queue Embed Job -> Worker Pool
   ```

## Performance

### Lazy Loading
Models are loaded on first use to minimize startup time and memory usage.

### Batch Processing
The `embed_batch` endpoint uses the model's native batch processing for better performance.

### Caching
Frequently embedded texts are cached using LRU cache to avoid recomputation.

### GPU Acceleration
Automatically detects and uses CUDA or MPS when available, with CPU fallback.

## Development

### Run Tests
```bash
pytest tests/
```

### Build Package
```bash
pip install build
python -m build
```

### Install in Development Mode
```bash
pip install -e .
```

## License

Part of the ArkhamFrame project.
