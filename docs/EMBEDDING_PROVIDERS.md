# Embedding Providers Guide

ArkhamMirror v0.2.5+ supports a modular embedding architecture, allowing you to choose between different embedding providers based on your hardware resources and requirements.

## Available Providers

### 1. BGE-M3 (Standard)

**Provider ID**: `bge-m3`

The default provider. Best for multilingual support and high-accuracy semantic search.

- **Model**: `BAAI/bge-m3`
- **Size**: ~2.24 GB
- **Dimensions**: 1024 (Dense)
- **Languages**: 100+ (Multilingual)
- **Sparse Method**: Native learned lexical weights
- **Hardware**: Recommended 8GB+ RAM, GPU preferred.

### 2. MiniLM + BM25 (Minimal)

**Provider ID**: `minilm-bm25`

A lightweight alternative for resource-constrained environments or English-only use cases.

- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Size**: ~80 MB
- **Dimensions**: 384 (Dense)
- **Languages**: English (primarily)
- **Sparse Method**: Term Frequency (TF) / BM25 approximation
- **Hardware**: Runs comfortably on 4GB RAM, CPU-only.

## Configuration

To switch providers, edit `config.yaml`:

```yaml
embedding:
  provider: "minilm-bm25"  # or "bge-m3"
  device: "cpu"            # or "cuda"
```

## Hybrid Search

Both providers support hybrid search (Dense + Sparse). You can tune the importance of each component in `config.yaml`:

```yaml
search:
  hybrid_weights:
    dense: 0.7    # Semantic similarity
    sparse: 0.3   # Keyword matching
```

## Switching Providers

⚠️ **IMPORTANT**: Switching providers changes the vector dimensions (1024 vs 384). You MUST re-index your documents if you switch.

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for instructions.
