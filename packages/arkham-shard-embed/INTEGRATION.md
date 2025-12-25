# Integration Guide

This guide explains how to integrate the Embed Shard into an ArkhamFrame application.

## Installation

### 1. Install the package

```bash
pip install arkham-shard-embed
```

Or install from source:

```bash
cd packages/arkham-shard-embed
pip install -e .
```

### 2. Install dependencies

The shard requires `sentence-transformers` which will be installed automatically. For GPU support, also install PyTorch with CUDA:

```bash
# CPU only (automatic)
pip install sentence-transformers

# With CUDA support (optional, for GPU acceleration)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Configuration

### Environment Variables

Set these before starting ArkhamFrame:

```bash
export EMBED_MODEL="BAAI/bge-m3"          # Default: BAAI/bge-m3
export EMBED_DEVICE="auto"                 # auto|cpu|cuda|mps
export EMBED_BATCH_SIZE="32"               # Batch size for processing
export EMBED_CACHE_SIZE="1000"             # LRU cache size
```

### Frame Configuration

The shard is automatically discovered via entry points. Just ensure it's installed and ArkhamFrame will load it.

## Shard Discovery

The Embed Shard registers itself via the `arkham.shards` entry point in `pyproject.toml`:

```toml
[project.entry-points."arkham.shards"]
embed = "arkham_shard_embed:EmbedShard"
```

ArkhamFrame will automatically discover and load it on startup.

## Service Dependencies

The Embed Shard requires these Frame services:

**Required:**
- `vectors` - Qdrant vector storage service
- `events` - Event bus for pub/sub

**Optional:**
- `documents` - Document management service
- `workers` - Worker pool for async jobs

## Using the Shard

### From API (HTTP)

```python
import httpx

async def embed_text():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/embed/text",
            json={"text": "Your text here"}
        )
        result = response.json()
        embedding = result['embedding']
        return embedding
```

### From Another Shard

```python
from arkham_frame.shard_interface import ArkhamShard

class MyAnalysisShard(ArkhamShard):
    async def initialize(self, frame):
        self.frame = frame

    async def analyze_text(self, text: str):
        # Get the embed shard
        embed_shard = self.frame.get_shard("embed")

        # Use its public API
        embedding = await embed_shard.embed_text(text)
        similar = await embed_shard.find_similar(
            query=text,
            collection="documents",
            limit=10
        )

        return embedding, similar
```

### From Application Code

```python
from arkham_frame import ArkhamFrame

async def main():
    # Initialize frame
    frame = ArkhamFrame()
    await frame.initialize()

    # Get embed shard
    embed = frame.get_shard("embed")

    # Embed text
    embedding = await embed.embed_text("Document text")

    # Find similar
    results = await embed.find_similar(
        query="search query",
        limit=10,
        min_similarity=0.7
    )
```

## Event Subscriptions

The Embed Shard automatically responds to these events:

### documents.ingested

When a document is ingested, the shard automatically queues an embedding job:

```python
# Publish event
await event_bus.emit(
    "documents.ingested",
    {"doc_id": "123", "title": "Document.pdf"},
    source="ingest-shard"
)

# Embed shard receives and queues embedding job automatically
```

### documents.chunks.created

When document chunks are created:

```python
await event_bus.emit(
    "documents.chunks.created",
    {"doc_id": "123", "chunk_count": 45},
    source="splitter-shard"
)
```

## Events Published

The Embed Shard publishes these events:

### embed.text.completed

```python
{
    "doc_id": "123",
    "chunk_id": "456",
    "dimensions": 1024,
    "duration_ms": 42.5
}
```

### embed.batch.completed

```python
{
    "count": 100,
    "dimensions": 1024,
    "duration_ms": 1250.0
}
```

### embed.document.completed

```python
{
    "doc_id": "123",
    "chunk_count": 45,
    "success": True
}
```

## Worker Pool Integration

For async document embedding, the shard uses the `gpu-embed` worker pool:

```python
# The shard dispatches to workers
job_id = await worker_service.enqueue(
    pool="gpu-embed",
    job_type="embed_document",
    payload={
        "doc_id": doc_id,
        "force": False,
        "chunk_size": 512,
        "chunk_overlap": 50
    }
)
```

Ensure you have EmbedWorkers running:

```bash
python -m arkham_frame.workers.embed_worker
```

## Vector Storage

Embeddings are stored in Qdrant collections:

### Default Collection: documents

```python
# Store embedding
vector_id = await embed.store_embedding(
    embedding=[0.1, 0.2, ...],
    payload={
        "doc_id": "123",
        "chunk_id": "456",
        "text": "Original text"
    },
    collection="documents"
)

# Search for similar
results = await embed.find_similar(
    query="search text",
    collection="documents",
    limit=10
)
```

## Performance Tuning

### GPU Acceleration

Set device to enable GPU:

```bash
export EMBED_DEVICE="cuda"  # For NVIDIA GPUs
export EMBED_DEVICE="mps"   # For Apple Silicon
```

### Batch Size

Increase batch size for better throughput:

```bash
export EMBED_BATCH_SIZE="64"  # Higher = faster for large batches
```

### Cache Size

Increase cache for frequently repeated texts:

```bash
export EMBED_CACHE_SIZE="5000"  # More cache = fewer recomputations
```

### Model Selection

Choose model based on your needs:

```bash
# High quality, multilingual (1024 dims, ~2.2GB)
export EMBED_MODEL="BAAI/bge-m3"

# Fast, lightweight (384 dims, ~80MB)
export EMBED_MODEL="all-MiniLM-L6-v2"

# Other options:
# - BAAI/bge-large-en-v1.5 (1024 dims, English only, high quality)
# - sentence-transformers/all-mpnet-base-v2 (768 dims, good quality)
```

## Monitoring

### Check Model Status

```bash
curl http://localhost:8000/api/embed/models
```

### Check Cache Performance

```bash
curl http://localhost:8000/api/embed/cache/stats
```

### Clear Cache

```bash
curl -X POST http://localhost:8000/api/embed/cache/clear
```

## Troubleshooting

### Model Download Issues

Models are downloaded from HuggingFace on first use. If download fails:

1. Check internet connection
2. Set HuggingFace cache directory:
   ```bash
   export HF_HOME=/path/to/cache
   ```

### Out of Memory

If you get OOM errors:

1. Use smaller model (MiniLM instead of BGE-M3)
2. Reduce batch size: `EMBED_BATCH_SIZE=16`
3. Use CPU instead of GPU: `EMBED_DEVICE=cpu`

### Slow Performance

If embedding is slow:

1. Enable GPU: `EMBED_DEVICE=cuda`
2. Increase batch size: `EMBED_BATCH_SIZE=64`
3. Use smaller model for speed: `all-MiniLM-L6-v2`

### Cache Not Working

Check cache stats to verify it's enabled:

```python
stats = await embed.get_cache_info()
print(stats)
```

If disabled, increase cache size: `EMBED_CACHE_SIZE=1000`

## Example Integration

Complete example of integrating Embed Shard into an application:

```python
import asyncio
from arkham_frame import ArkhamFrame

async def main():
    # Create and initialize frame
    frame = ArkhamFrame()
    await frame.initialize()

    # Get embed shard
    embed = frame.get_shard("embed")

    # Check model info
    info = embed.get_model_info()
    print(f"Model: {info['name']}")
    print(f"Dimensions: {info['dimensions']}")

    # Embed some text
    texts = [
        "First document about AI",
        "Second document about ML",
        "Third document about NLP"
    ]

    # Batch embed
    embeddings = await embed.embed_batch(texts)
    print(f"Generated {len(embeddings)} embeddings")

    # Store in vector database
    for i, (text, embedding) in enumerate(zip(texts, embeddings)):
        await embed.store_embedding(
            embedding=embedding,
            payload={"text": text, "index": i},
            collection="documents"
        )

    # Search for similar
    query = "machine learning research"
    results = await embed.find_similar(
        query=query,
        collection="documents",
        limit=3,
        min_similarity=0.5
    )

    print(f"\nFound {len(results)} similar documents for '{query}':")
    for result in results:
        print(f"  - {result['payload']['text']} (score: {result['score']})")

    # Cleanup
    await frame.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

## Next Steps

- Review the [API documentation](README.md#api-endpoints)
- Explore [usage examples](examples/basic_usage.py)
- Check out other shards for integration patterns
- Read the [ArkhamFrame documentation](../arkham-frame/README.md)
