# Air-Gap Deployment Guide

This guide explains how to deploy SHATTERED in an air-gapped (offline) environment without internet access.

## Overview

SHATTERED is designed to be 100% air-gappable when properly configured. The application itself contains no telemetry, analytics, or phone-home mechanisms. However, some ML components require pre-caching before deployment.

## What Requires Internet Access

| Component | Purpose | Pre-Cache Required |
|-----------|---------|-------------------|
| Google Fonts | UI typography | No (bundled locally via @fontsource) |
| Embedding Models | Semantic search | Yes |
| OCR Models | Text extraction from images | Yes |
| LLM Inference | AI analysis | No (use local LLM like Ollama/LM Studio) |

## Quick Start

### 1. Enable Offline Mode

Set the environment variable to prevent any automatic model downloads:

```bash
export ARKHAM_OFFLINE_MODE=true
```

Or in Docker Compose:

```yaml
services:
  arkham-frame:
    environment:
      - ARKHAM_OFFLINE_MODE=true
```

### 2. Pre-Cache ML Models

Before going offline, download required models on a connected machine.

**Option A: Use the UI**

1. Navigate to Settings > ML Models
2. Click "Download" for each model you need
3. Models are cached in `~/.cache/huggingface/hub/` and `~/.paddleocr/`

**Option B: Use Python Scripts**

```bash
# Download embedding model
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Download PaddleOCR models
python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en')"
```

### 3. Transfer Cache to Air-Gapped System

Copy the model cache directories to your air-gapped system:

```bash
# Embedding models
~/.cache/huggingface/hub/

# OCR models
~/.paddleocr/
```

### 4. Configure Cache Path (Optional)

If you need to use a custom cache location:

```bash
export ARKHAM_MODEL_CACHE=/path/to/custom/cache
export HF_HOME=/path/to/custom/cache
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ARKHAM_OFFLINE_MODE` | Prevent automatic model downloads | `false` |
| `ARKHAM_MODEL_CACHE` | Custom model cache path | `~/.cache/huggingface/hub` |
| `HF_HOME` | HuggingFace cache path | `~/.cache/huggingface` |
| `HF_HUB_OFFLINE` | Set automatically when offline mode enabled | - |
| `TRANSFORMERS_OFFLINE` | Set automatically when offline mode enabled | - |

## Docker Deployment

### Building with Pre-Cached Models

Create a Dockerfile that includes pre-cached models:

```dockerfile
FROM python:3.11-slim

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Pre-cache embedding model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Pre-cache OCR model (optional)
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en')"

# Copy application
COPY . /app
WORKDIR /app

# Enable offline mode
ENV ARKHAM_OFFLINE_MODE=true

CMD ["python", "-m", "uvicorn", "arkham_frame.main:app", "--host", "0.0.0.0", "--port", "8100"]
```

### Using Volume Mounts

Mount pre-cached models from the host:

```yaml
services:
  arkham-frame:
    image: arkham-frame:latest
    environment:
      - ARKHAM_OFFLINE_MODE=true
      - ARKHAM_MODEL_CACHE=/models
    volumes:
      - ./models/huggingface:/models
      - ./models/paddleocr:/root/.paddleocr
```

## Available Models

### Embedding Models (sentence-transformers)

| Model | Size | Description |
|-------|------|-------------|
| `all-MiniLM-L6-v2` | ~90 MB | Default. Fast, good quality. |
| `all-mpnet-base-v2` | ~420 MB | Higher quality, slower. |
| `multi-qa-MiniLM-L6-cos-v1` | ~90 MB | Optimized for Q&A. |

### OCR Models (PaddleOCR)

| Model | Size | Description |
|-------|------|-------------|
| `paddleocr-en` | ~150 MB | English text recognition. |
| `paddleocr-ch` | ~180 MB | Chinese (also supports English). |

## Verifying Air-Gap Readiness

Use the API to check if all required models are installed:

```bash
curl http://localhost:8100/api/settings/models/offline-status
```

Response:
```json
{
  "offline_mode": true,
  "ready_for_airgap": true,
  "installed_count": 3,
  "missing_models": []
}
```

## Using Local LLM

For AI analysis features without cloud access, use a local LLM:

### Option 1: LM Studio (Recommended)

1. Install [LM Studio](https://lmstudio.ai/)
2. Download a model (e.g., Mistral, Llama)
3. Start the local server (default: `http://localhost:1234/v1`)
4. Configure SHATTERED:

```bash
export LLM_ENDPOINT=http://localhost:1234/v1
```

### Option 2: Ollama

1. Install [Ollama](https://ollama.ai/)
2. Pull a model: `ollama pull mistral`
3. Ollama runs on `http://localhost:11434`
4. Configure SHATTERED:

```bash
export LLM_ENDPOINT=http://localhost:11434/v1
```

## Troubleshooting

### "Model not found" errors in offline mode

The model is not cached locally. You need to:
1. Temporarily disable offline mode
2. Download the model via UI or script
3. Re-enable offline mode

### Models downloading on startup

`ARKHAM_OFFLINE_MODE` may not be set correctly. Verify:

```bash
echo $ARKHAM_OFFLINE_MODE  # Should print "true"
```

### Docker container can't find models

Ensure volume mounts are correct and the cache directories exist:

```bash
ls -la /models/models--sentence-transformers--all-MiniLM-L6-v2/
```

## Network Verification

To verify no external connections are made, you can:

1. **Use network monitoring**:
   ```bash
   # Linux
   sudo tcpdump -i any 'not host localhost and not host 127.0.0.1'
   ```

2. **Use Docker network isolation**:
   ```yaml
   services:
     arkham-frame:
       network_mode: none  # Complete network isolation
   ```

3. **Check firewall logs** for any blocked outbound connections

## Summary

For a fully air-gapped deployment:

1. Set `ARKHAM_OFFLINE_MODE=true`
2. Pre-cache embedding models (required for semantic search)
3. Pre-cache OCR models (optional, only if using OCR)
4. Use local LLM (LM Studio, Ollama, or vLLM)
5. Verify via Settings > ML Models in the UI

The application will not make any external network requests when properly configured.
