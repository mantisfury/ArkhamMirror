# arkham-shard-ocr

> Optical character recognition for document images

**Version:** 0.1.0
**Category:** Data
**Frame Requirement:** >=0.1.0

## Overview

The OCR shard provides optical character recognition capabilities for SHATTERED. It extracts text from document images using PaddleOCR and Qwen VL engines, with automatic quality-based routing and escalation for difficult documents.

### Key Capabilities

1. **OCR Processing** - Extract text from images and documents
2. **Multi-Engine Support** - PaddleOCR and Qwen VL engines
3. **GPU Acceleration** - Hardware-accelerated text recognition
4. **Quality-Based Routing** - Automatic engine selection based on image quality
5. **Confidence Scoring** - Per-line confidence scores

## Features

### OCR Engines

| Engine | Best For | Speed | Quality |
|--------|----------|-------|---------|
| `paddle` | Clean documents, tables | Fast | Good |
| `qwen` | Messy documents, handwriting | Slow | Excellent |

### VLM Backend Options

The Qwen/VLM engine supports multiple backends:

| Backend | Configuration | Notes |
|---------|--------------|-------|
| **Local (LM Studio)** | `VLM_ENDPOINT=http://localhost:1234/v1` | Free, requires GPU |
| **Local (Ollama)** | `VLM_ENDPOINT=http://localhost:11434/v1` | Free, requires GPU |
| **OpenRouter** | `VLM_ENDPOINT=https://openrouter.ai/api/v1` | GPT-4o, Claude, Gemini |
| **OpenAI** | `VLM_ENDPOINT=https://api.openai.com/v1` | GPT-4o vision |

Set `VLM_API_KEY` for cloud APIs (or uses `LLM_API_KEY` if not set).

### Processing Modes
- **Single Page** - OCR individual image files
- **Full Document** - OCR all pages in a document
- **Upload** - Direct file upload for immediate OCR

### Output Details
- Full extracted text
- Per-line text with bounding boxes
- Confidence scores per line
- Character and word counts
- Cache hit indication
- Escalation status

### Auto-Escalation
When PaddleOCR produces low-confidence results, the shard can automatically escalate to Qwen VL for better quality.

## Installation

```bash
pip install -e packages/arkham-shard-ocr
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ocr/health` | Health check with engine availability |
| POST | `/api/ocr/page` | OCR a single page image |
| POST | `/api/ocr/document` | OCR all pages of a document |
| POST | `/api/ocr/upload` | Upload and OCR an image file |

## API Examples

### Health Check

```bash
GET /api/ocr/health
```

Response:
```json
{
  "status": "ok",
  "shard": "ocr",
  "paddle_available": true,
  "qwen_available": true
}
```

### OCR Single Page

```json
POST /api/ocr/page
{
  "image_path": "/path/to/page.png",
  "engine": "paddle",
  "language": "en"
}
```

Response:
```json
{
  "success": true,
  "text": "Extracted text from the document...",
  "pages_processed": 1,
  "engine": "paddle",
  "confidence": 0.95,
  "lines": [
    {
      "text": "First line of text",
      "box": [[10, 20], [200, 20], [200, 40], [10, 40]],
      "confidence": 0.98
    }
  ],
  "from_cache": false,
  "escalated": false,
  "char_count": 1250,
  "word_count": 215
}
```

### OCR Document

```json
POST /api/ocr/document
{
  "document_id": "doc_abc123",
  "engine": null,
  "language": "en"
}
```

### Upload and OCR

```bash
curl -X POST http://localhost:8100/api/ocr/upload \
  -F "file=@document.png" \
  -F "engine=paddle" \
  -F "language=en"
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `ocr.page.started` | Page OCR started |
| `ocr.page.completed` | Page OCR finished |
| `ocr.document.started` | Document OCR started |
| `ocr.document.completed` | Document OCR finished |
| `ocr.error` | OCR processing error |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `ingest.job.completed` | Auto-OCR ingested images |

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether OCR succeeded |
| `text` | string | Full extracted text |
| `pages_processed` | int | Number of pages processed |
| `engine` | string | Engine used (paddle/qwen) |
| `confidence` | float | Overall confidence score |
| `lines` | array | Per-line text and boxes |
| `from_cache` | bool | Whether result was cached |
| `escalated` | bool | Whether escalated to Qwen |
| `char_count` | int | Total character count |
| `word_count` | int | Total word count |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VLM_ENDPOINT` | `http://localhost:1234/v1` | Vision model API endpoint |
| `VLM_MODEL` | `qwen2.5-vl-7b-instruct` | Vision model ID |
| `VLM_API_KEY` | - | API key for cloud providers |
| `VLM_TIMEOUT` | `120` | Request timeout in seconds |

### Example Configurations

**Local LM Studio:**
```bash
VLM_ENDPOINT=http://localhost:1234/v1
VLM_MODEL=qwen2.5-vl-7b-instruct
```

**OpenRouter (cloud):**
```bash
VLM_ENDPOINT=https://openrouter.ai/api/v1
VLM_MODEL=openai/gpt-4o
VLM_API_KEY=sk-or-v1-your-key
```

**OpenAI (cloud):**
```bash
VLM_ENDPOINT=https://api.openai.com/v1
VLM_MODEL=gpt-4o
VLM_API_KEY=sk-your-openai-key
```

## Worker Pools

OCR processing uses dedicated GPU worker pools:
- `gpu-paddle` - PaddleOCR processing
- `gpu-qwen` - Qwen VL processing

## UI Routes

| Route | Description |
|-------|-------------|
| `/ocr` | OCR interface |

## Dependencies

### Required Services
- **database** - Result storage
- **storage** - File access
- **workers** - GPU worker pools
- **events** - Event publishing

### Optional Services
- **documents** - Document access for multi-page OCR

## URL State

| Parameter | Description |
|-----------|-------------|
| `documentId` | Document being processed |
| `pageId` | Page being viewed |

## Architecture Notes

### Engine Selection
- Use `paddle` for standard documents with good image quality
- Use `qwen` for handwritten text, poor scans, or complex layouts
- Use `null` for automatic selection based on image quality assessment

### Caching
OCR results are cached to avoid reprocessing the same images. Cache hits return immediately with `from_cache: true`.

### Escalation
When auto-mode is used and PaddleOCR produces low-confidence results, the shard automatically escalates to Qwen VL and returns `escalated: true`.

## Development

```bash
# Run tests
pytest packages/arkham-shard-ocr/tests/

# Type checking
mypy packages/arkham-shard-ocr/
```

## License

MIT
