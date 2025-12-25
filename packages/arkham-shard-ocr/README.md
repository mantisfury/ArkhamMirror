# arkham-shard-ocr

OCR processing shard for ArkhamFrame.

## Features

- **PaddleOCR**: Fast, accurate OCR for printed text
- **Qwen-VL**: Vision-language model for complex/handwritten text
- Page-level and document-level processing
- Bounding box extraction for text regions

## Installation

```bash
cd packages/arkham-shard-ocr
pip install -e .

# For GPU support (CUDA):
pip install -e ".[gpu]"

# For Qwen-VL support:
pip install -e ".[qwen]"
```

## Usage

The shard registers automatically when installed. Access via API:

```bash
# OCR a page
curl -X POST http://localhost:8100/api/ocr/page \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/image.png"}'

# OCR a document
curl -X POST http://localhost:8100/api/ocr/document \
  -H "Content-Type: application/json" \
  -d '{"document_id": "doc-123"}'
```

## Configuration

Set OCR defaults in Frame config:

```yaml
ocr:
  default_engine: paddle  # or qwen
  language: en
```

## Workers

This shard provides two OCR workers:

### PaddleWorker (pool: gpu-paddle)
- Fast CPU-based OCR using PaddleOCR
- Best for: printed documents, clear text, high-volume processing
- Returns text with bounding boxes

### QwenWorker (pool: gpu-qwen)
- VLM-based OCR using OpenAI-compatible vision endpoints
- Works with LM Studio, Ollama, vLLM, etc.
- Best for: handwritten text, complex layouts, degraded documents
- Supports table extraction

## Events

### Published Events
- `ocr.page.started` - OCR processing started for a page
- `ocr.page.completed` - Page OCR completed
- `ocr.document.started` - Document OCR started
- `ocr.document.completed` - Document OCR completed
- `ocr.error` - OCR processing error

### Subscribed Events
- `ingest.job.completed` - Auto-trigger OCR for ingested images
