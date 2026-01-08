# SHATTERED System Requirements

This document outlines the hardware requirements for running SHATTERED in various configurations.

---

## Quick Reference

| | Minimum | Recommended | Production |
|--|---------|-------------|------------|
| **CPU** | 2 cores | 4 cores | 8+ cores |
| **RAM** | 4 GB | 8 GB | 16 GB |
| **Disk** | 10 GB | 20 GB | 50+ GB |
| **GPU** | None | Optional | Recommended |

---

## CPU

| Tier | Cores | Use Case |
|------|-------|----------|
| **Minimum** | 2 cores | Basic browsing, light analysis |
| **Standard** | 4 cores | Document processing, embedding generation |
| **Optimal** | 6-8 cores | Batch processing, concurrent operations |

**Notes:**
- Document parsing (PDF/OCR) is CPU-bound
- Embedding generation on CPU is slow but works
- More cores = faster batch ingestion

---

## GPU (Optional)

| Configuration | Benefit |
|---------------|---------|
| **None** | Works fine, embeddings use CPU (~10x slower) |
| **CUDA GPU (4GB+ VRAM)** | Fast embeddings, local LLM inference possible |
| **8GB+ VRAM** | Can run 7B parameter LLMs locally |

**Notes:**
- GPU is not required - the app works fully on CPU
- If using LM Studio/Ollama on host, that's where GPU matters most
- sentence-transformers auto-detects CUDA when available

---

## Memory (RAM)

| Tier | RAM | Scenario |
|------|-----|----------|
| **Minimum** | 2 GB | No embeddings, tiny corpus |
| **Light** | 4 GB | MiniLM embeddings, <1K documents |
| **Standard** | 6 GB | BGE-M3 embeddings, 1-10K documents |
| **Heavy** | 8 GB | Large corpus, batch processing |
| **Production** | 12-16 GB | Multi-user, 100K+ documents |

### Memory Breakdown (Typical Usage)

| Component | Idle | Heavy Load |
|-----------|------|------------|
| App + 25 shards | 600 MB | 600 MB |
| PostgreSQL | 40 MB | 300-500 MB |
| Qdrant | 25 MB | 1-2 GB (with vectors) |
| Redis | 7 MB | 50-100 MB |
| Embedding model (none) | 0 MB | 0 MB |
| Embedding model (MiniLM) | 80-150 MB | 150 MB |
| Embedding model (BGE-M3) | 2.0-2.5 GB | 2.5 GB |
| Processing spikes | - | 300-500 MB |

### WSL2 Memory Allocation

If running via Docker on WSL2, configure memory in `~/.wslconfig`:

```ini
[wsl2]
memory=8GB
processors=4
```

---

## Disk Space

### Docker Images (One-Time)

| Image | Size |
|-------|------|
| shattered:local | 4.0 GB |
| postgres:15-alpine | 390 MB |
| qdrant/qdrant:latest | 255 MB |
| redis:7-alpine | 61 MB |
| **Total** | **~4.7 GB** |

### Data Volumes (Scales with Usage)

| Volume | Empty | Light Use | Heavy Use |
|--------|-------|-----------|-----------|
| PostgreSQL | 50 MB | 200 MB | 1-5 GB |
| Qdrant vectors | 1 MB | 500 MB | 5-20 GB |
| Document storage | 0 | Variable | Variable |
| Redis | 1 MB | 10 MB | 100 MB |

### Embedding Models (Downloaded on First Use)

| Model | Size | Dimensions | Quality |
|-------|------|------------|---------|
| all-MiniLM-L6-v2 | ~80 MB | 384 | Good |
| BGE-M3 | ~2.2 GB | 1024 | Excellent |
| BGE-Large-EN | ~1.3 GB | 1024 | Excellent |

### Total Disk Recommendations

| Usage | Disk Space |
|-------|------------|
| Minimum (testing) | 10 GB |
| Standard | 20 GB |
| Large corpus | 50+ GB |

---

## Network

| Requirement | Details |
|-------------|---------|
| **Ports** | 8100 (app), 5432 (postgres), 6333 (qdrant), 6379 (redis) |
| **Internet** | Optional - only needed for external LLM APIs |
| **Air-gap capable** | Yes - fully functional offline with local models |

---

## Operating System

| OS | Support |
|----|---------|
| **Linux** | Native Docker, best performance |
| **Windows 11** | Via WSL2 + Docker Desktop |
| **Windows 10** | Via WSL2 + Docker Desktop |
| **macOS** | Via Docker Desktop (ARM or Intel) |

---

## Scaling Factors

### Document Count Impact

| Documents | PostgreSQL | Qdrant (1024d) | Processing Time |
|-----------|------------|----------------|-----------------|
| 100 | 10 MB | 50 MB | Minutes |
| 1,000 | 50 MB | 200 MB | ~1 hour |
| 10,000 | 200 MB | 2 GB | Several hours |
| 100,000 | 1 GB | 15-20 GB | Days |

### Concurrent Users

| Users | Recommended RAM | Recommended CPU |
|-------|-----------------|-----------------|
| 1 (local) | 8 GB | 4 cores |
| 2-5 | 12 GB | 6 cores |
| 5-10 | 16 GB | 8 cores |
| 10+ | 32 GB | 16 cores |

---

## Performance Tips

1. **Use SSD storage** - significantly improves database and vector search performance
2. **Allocate fixed memory to WSL2** - prevents memory pressure from host
3. **Use GPU for embeddings** - 10x faster than CPU for large batches
4. **Choose appropriate embedding model** - MiniLM for speed, BGE-M3 for quality
5. **Run LLM on host** - better GPU utilization than inside container
