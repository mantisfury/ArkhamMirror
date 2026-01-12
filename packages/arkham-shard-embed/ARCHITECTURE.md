# Architecture

This document describes the architecture of the Embed Shard.

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Embed Shard                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   API       │  │  Embedder    │  │  Storage     │      │
│  │  (api.py)   │  │ (embedder.py)│  │ (storage.py) │      │
│  └─────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                   │             │
│         └────────┬────────┴──────────┬────────┘             │
│                  │                   │                      │
│           ┌──────▼──────┐     ┌──────▼──────┐              │
│           │   Shard     │     │   Models    │              │
│           │ (shard.py)  │     │ (models.py) │              │
│           └─────────────┘     └─────────────┘              │
│                  │                                          │
└──────────────────┼──────────────────────────────────────────┘
                   │
                   │ Uses Frame Services
                   │
         ┌─────────▼─────────┐
         │   ArkhamFrame     │
         ├───────────────────┤
         │ - Vectors Service │
         │ - Events Service  │
         │ - Worker Service  │
         │ - Document Svc    │
         └───────────────────┘
```

## Layer Breakdown

### 1. API Layer (api.py)

**Responsibility**: HTTP endpoints and request handling

**Components**:
- FastAPI router with 10+ endpoints
- Request/response Pydantic models
- Error handling and validation
- Event emission

**Endpoints**:
- `/api/embed/text` - Single text embedding
- `/api/embed/batch` - Batch embedding
- `/api/embed/document/{doc_id}` - Document embedding
- `/api/embed/similarity` - Text similarity
- `/api/embed/nearest` - Nearest neighbor search
- `/api/embed/models` - Model information
- `/api/embed/config` - Configuration management
- `/api/embed/cache/*` - Cache operations

### 2. Core Logic Layer (embedder.py)

**Responsibility**: Embedding generation and model management

**Components**:
- `EmbeddingManager` class
  - Model loading (lazy initialization)
  - Device detection (CPU/GPU/MPS)
  - Text embedding (single and batch)
  - Similarity calculations
  - Text chunking
  - LRU cache management

**Key Features**:
- Lazy model loading
- GPU acceleration with CPU fallback
- Configurable batch processing
- LRU cache for frequently embedded texts
- Multiple similarity metrics (cosine, euclidean, dot)

### 3. Storage Layer (storage.py)

**Responsibility**: Vector database operations

**Components**:
- `VectorStore` class wrapping pgvector
  - Collection management
  - Vector upsert (single and batch)
  - Similarity search
  - Vector deletion
  - Index optimization

**Operations**:
- Create/delete collections
- Upsert vectors with metadata
- Search by vector similarity
- Delete by ID or filter
- Collection information

### 4. Orchestration Layer (shard.py)

**Responsibility**: Shard lifecycle and coordination

**Components**:
- `EmbedShard` class (extends `ArkhamShard`)
  - Initialization and shutdown
  - Service dependency management
  - Event subscriptions
  - Public API for other shards

**Lifecycle**:
```
Initialize → Load Config → Setup Services → Subscribe Events → Ready
                ↓                                ↓
         EmbeddingManager              VectorStore
```

**Event Handling**:
- `documents.ingested` → Queue embedding job
- `documents.chunks.created` → Trigger chunk embedding

### 5. Data Models Layer (models.py)

**Responsibility**: Type definitions and data structures

**Models**:
- Request models: `EmbedRequest`, `BatchEmbedRequest`, `SimilarityRequest`, etc.
- Result models: `EmbedResult`, `BatchEmbedResult`, `SimilarityResult`, etc.
- Config models: `EmbedConfig`, `ModelInfo`
- Enums: `EmbedStatus`

## Data Flow

### Synchronous Embedding Flow

```
Client Request
     │
     ▼
API Endpoint (/api/embed/text)
     │
     ▼
EmbeddingManager.embed_text()
     │
     ├──→ Check cache
     │    └──→ Cache hit? → Return cached
     │
     ├──→ Cache miss
     │
     ├──→ Load model (if needed)
     │
     ├──→ Generate embedding
     │
     ├──→ Store in cache
     │
     ▼
Return embedding to client
```

### Asynchronous Document Embedding Flow

```
Document Ingested Event
     │
     ▼
Embed Shard Event Handler
     │
     ▼
Queue Job in Worker Pool
     │
     ▼
EmbedWorker (gpu-embed pool)
     │
     ├──→ Load document chunks
     │
     ├──→ Generate embeddings
     │
     ├──→ Store in pgvector
     │
     ▼
Emit completion event
```

### Similarity Search Flow

```
Search Query
     │
     ▼
API Endpoint (/api/embed/nearest)
     │
     ├──→ Is query text?
     │    ├──→ Yes: Embed text
     │    └──→ No: Use as vector
     │
     ▼
VectorStore.search()
     │
     ├──→ Query pgvector
     │
     ├──→ Apply filters
     │
     ├──→ Apply score threshold
     │
     ▼
Return results with scores
```

## Integration Patterns

### Pattern 1: Direct API Calls

```
External Client
     │
     ▼
HTTP Request
     │
     ▼
Embed Shard API
     │
     ▼
Response
```

### Pattern 2: Shard-to-Shard Communication

```
Analysis Shard
     │
     ▼
frame.get_shard("embed")
     │
     ▼
Embed Shard Public Methods
     │
     ▼
Results
```

### Pattern 3: Event-Driven Processing

```
Document Shard
     │
     ▼
Emit "documents.ingested"
     │
     ▼
Event Bus
     │
     ▼
Embed Shard (subscribed)
     │
     ▼
Queue Embedding Job
```

## Service Dependencies

### Required Services

1. **Vectors Service** (pgvector client)
   - Vector storage and retrieval
   - Collection management
   - Similarity search

2. **Events Service** (Event bus)
   - Publish completion events
   - Subscribe to document events

### Optional Services

3. **Workers Service** (Job queue)
   - Async document processing
   - Background embedding jobs

4. **Documents Service**
   - Document metadata
   - Chunk retrieval

## Configuration Flow

```
Environment Variables
     │
     ├──→ EMBED_MODEL
     ├──→ EMBED_DEVICE
     ├──→ EMBED_BATCH_SIZE
     └──→ EMBED_CACHE_SIZE
     │
     ▼
EmbedConfig
     │
     ▼
EmbeddingManager
     │
     ├──→ Model selection
     ├──→ Device detection
     ├──→ Cache initialization
     └──→ Batch configuration
```

## Memory Management

### Model Loading

```
First embed_text() call
     │
     ▼
Check if model loaded
     │
     ├──→ No: Load model
     │    ├──→ Download from HuggingFace
     │    ├──→ Load into memory
     │    └──→ Move to device (CPU/GPU)
     │
     └──→ Yes: Reuse loaded model
```

### Cache Strategy

```
LRU Cache (configurable size)
     │
     ├──→ Text embedding requested
     │
     ├──→ Hash text as key
     │
     ├──→ Check cache
     │    ├──→ Hit: Return cached embedding
     │    └──→ Miss: Compute and cache
     │
     └──→ Evict least recently used when full
```

## Error Handling

```
API Request
     │
     ├──→ Validation error → 400 Bad Request
     │
     ├──→ Service unavailable → 503 Service Unavailable
     │
     ├──→ Processing error → 500 Internal Server Error
     │
     └──→ Success → 200 OK with result
```

## Performance Optimization

### Batch Processing

```
Single Requests (slow)          Batch Request (fast)
     │                               │
     ├─→ Embed text 1                ├─→ Batch texts
     ├─→ Embed text 2                │
     ├─→ Embed text 3                ├─→ Model forward pass
     └─→ Embed text N                │   (vectorized)
                                     │
     N model calls                   └─→ 1 model call
     ~N × overhead                       ~overhead
```

### GPU Acceleration

```
CPU Processing              GPU Processing
     │                          │
     ├─→ Serial               ├─→ Parallel
     │   processing           │   processing
     │                        │
     └─→ Slower               └─→ Faster
                                  (10-100x)
```

### Caching

```
Without Cache               With Cache
     │                         │
     ├─→ Compute               ├─→ Check cache
     │   every time            │   ├─→ Hit: Return
     │                         │   └─→ Miss: Compute
     │                         │
     └─→ Redundant             └─→ Efficient
         computation               (avoid recomputation)
```

## Security Considerations

1. **Input Validation**
   - Text length limits
   - Batch size limits
   - Filter validation

2. **Resource Limits**
   - Max batch size
   - Cache size limits
   - GPU memory management

3. **Access Control**
   - API authentication (via Frame)
   - Collection access control
   - Event permissions

## Testing Strategy

### Unit Tests
- `test_embedder.py` - Core embedding logic
- Model loading and inference
- Similarity calculations
- Text chunking
- Cache behavior

### Integration Tests
- API endpoint testing
- Service integration
- Event handling
- Worker pool integration

### Performance Tests
- Batch processing speed
- GPU vs CPU performance
- Cache hit rate
- Memory usage

## Deployment Considerations

### Resource Requirements

**CPU Mode**:
- RAM: 2-8 GB (depending on model)
- CPU: 2+ cores recommended
- Storage: 100-3000 MB for models

**GPU Mode**:
- GPU Memory: 2-8 GB
- CUDA: 11.x or higher
- Storage: Same as CPU

### Scaling

**Horizontal Scaling**:
- Multiple worker instances
- Load balancing across workers
- Shared pgvector instance

**Vertical Scaling**:
- Larger GPU
- More CPU cores
- Increased batch size

## Monitoring

### Metrics to Track

1. **Performance**
   - Embedding latency
   - Batch processing time
   - Cache hit rate

2. **Resources**
   - GPU utilization
   - Memory usage
   - Model load time

3. **Usage**
   - API request rate
   - Embedding count
   - Collection sizes

## Future Enhancements

1. **Model Management**
   - Hot-swap models
   - Multiple models loaded
   - Auto model selection

2. **Optimization**
   - Quantization support
   - ONNX runtime
   - Batch queue optimization

3. **Features**
   - Cross-encoder support
   - Multi-modal embeddings
   - Fine-tuning support
