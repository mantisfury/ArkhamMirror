# Quick Start Guide

Get up and running with the Embed Shard in 5 minutes.

## Installation

```bash
pip install arkham-shard-embed
```

## Basic Usage

### 1. Start ArkhamFrame

The shard is automatically discovered and loaded:

```bash
python -m arkham_frame
```

### 2. Embed Your First Text

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/embed/text",
            json={"text": "Hello, ArkhamFrame!"}
        )
        result = response.json()
        print(f"Embedding dimensions: {result['dimensions']}")
        print(f"Model: {result['model']}")

asyncio.run(main())
```

### 3. Find Similar Documents

```python
async def find_similar():
    async with httpx.AsyncClient() as client:
        # Embed and search in one call
        response = await client.post(
            "http://localhost:8000/api/embed/nearest",
            json={
                "query": "machine learning algorithms",
                "limit": 5,
                "min_similarity": 0.7
            }
        )
        results = response.json()
        print(f"Found {results['total']} similar documents")
        for doc in results['neighbors']:
            print(f"  - {doc['id']}: {doc['score']}")

asyncio.run(find_similar())
```

## Use Cases

### Semantic Search

```python
# Search documents by meaning, not just keywords
results = await embed.find_similar(
    query="financial corruption investigations",
    collection="documents",
    limit=20
)
```

### Document Similarity

```python
# Find documents similar to a given document
similar = await embed.find_similar(
    query=document_embedding,  # Pre-computed embedding
    collection="documents"
)
```

### Clustering

```python
# Embed all documents for clustering
texts = get_all_document_texts()
embeddings = await embed.embed_batch(texts)
# Use embeddings for k-means or other clustering
```

### Duplicate Detection

```python
# Find near-duplicates using high similarity threshold
duplicates = await embed.find_similar(
    query=doc_text,
    min_similarity=0.95,  # Very high threshold
    limit=10
)
```

## Configuration

Create a `.env` file:

```bash
EMBED_MODEL=BAAI/bge-m3
EMBED_DEVICE=auto
EMBED_BATCH_SIZE=32
EMBED_CACHE_SIZE=1000
```

## Common Patterns

### Pattern 1: Embed and Store

```python
# Embed text
embedding = await embed.embed_text("Document content")

# Store in vector database
vector_id = await embed.store_embedding(
    embedding=embedding,
    payload={"doc_id": "123", "title": "Document.pdf"},
    collection="documents"
)
```

### Pattern 2: Batch Processing

```python
# Process many documents efficiently
texts = load_documents()  # Load your documents
embeddings = await embed.embed_batch(texts, batch_size=64)

# Store all at once
await embed.store_batch(
    embeddings=embeddings,
    payloads=[{"text": t} for t in texts],
    collection="documents"
)
```

### Pattern 3: Similarity Search

```python
# Find similar documents
results = await embed.find_similar(
    query="search query",
    collection="documents",
    limit=10,
    min_similarity=0.6,
    filters={"project_id": "project-123"}  # Optional filters
)
```

## API Endpoints

Quick reference:

- `POST /api/embed/text` - Embed single text
- `POST /api/embed/batch` - Embed multiple texts
- `POST /api/embed/document/{doc_id}` - Queue document embedding
- `GET /api/embed/document/{doc_id}` - Get document embeddings
- `POST /api/embed/similarity` - Calculate text similarity
- `POST /api/embed/nearest` - Find nearest neighbors
- `GET /api/embed/models` - List available models
- `GET /api/embed/cache/stats` - Check cache performance
- `POST /api/embed/cache/clear` - Clear cache

## Performance Tips

1. **Use Batch Embedding** for multiple texts:
   ```python
   # Good - processes in one batch
   embeddings = await embed.embed_batch(texts)

   # Bad - processes one at a time
   embeddings = [await embed.embed_text(t) for t in texts]
   ```

2. **Enable GPU** for speed:
   ```bash
   export EMBED_DEVICE=cuda
   ```

3. **Use Caching** for repeated texts:
   ```python
   embedding = await embed.embed_text(text, use_cache=True)
   ```

4. **Choose Right Model** for your needs:
   - Fast & small: `all-MiniLM-L6-v2` (384 dims)
   - Quality & multilingual: `BAAI/bge-m3` (1024 dims)

## Next Steps

- Read the [full README](README.md) for detailed documentation
- Check [integration guide](INTEGRATION.md) for advanced usage
- Explore [examples](examples/basic_usage.py) for more patterns
- Review [API reference](README.md#api-endpoints)

## Troubleshooting

**Model not loading?**
```bash
# Check model directory
ls ~/.cache/huggingface/hub/

# Re-download model
rm -rf ~/.cache/huggingface/hub/models--*
```

**Out of memory?**
```bash
# Use smaller model
export EMBED_MODEL=all-MiniLM-L6-v2

# Or use CPU
export EMBED_DEVICE=cpu
```

**Slow performance?**
```bash
# Enable GPU
export EMBED_DEVICE=cuda

# Increase batch size
export EMBED_BATCH_SIZE=64
```

## Support

For issues and questions:
- Check the [README](README.md)
- Review [integration guide](INTEGRATION.md)
- See [ArkhamFrame docs](../arkham-frame/README.md)
