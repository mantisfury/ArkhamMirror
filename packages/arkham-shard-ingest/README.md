# arkham-shard-ingest

Document ingestion shard for ArkhamFrame.

## Features

- **File Intake**: Upload files via API or ingest from filesystem paths
- **Type Classification**: Automatic file type detection (documents, images, audio, archives)
- **Image Quality Assessment**: CLEAN/FIXABLE/MESSY classification for smart OCR routing
- **Worker Dispatch**: Routes files through appropriate processing pipelines
- **Batch Processing**: Handle multiple files as tracked batches
- **Priority Queue**: User uploads prioritized over batch imports

## Installation

```bash
pip install arkham-shard-ingest
```

Or for development:

```bash
cd packages/arkham-shard-ingest
pip install -e .
```

## Usage

The shard is auto-discovered by ArkhamFrame when installed.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ingest/upload` | POST | Upload single file |
| `/api/ingest/upload/batch` | POST | Upload multiple files |
| `/api/ingest/ingest-path` | POST | Ingest from filesystem |
| `/api/ingest/job/{id}` | GET | Get job status |
| `/api/ingest/batch/{id}` | GET | Get batch status |
| `/api/ingest/job/{id}/retry` | POST | Retry failed job |
| `/api/ingest/queue` | GET | Queue statistics |
| `/api/ingest/pending` | GET | List pending jobs |

### Example: Upload a File

```bash
curl -X POST http://localhost:8100/api/ingest/upload \
  -F "file=@document.pdf" \
  -F "priority=user"
```

Response:
```json
{
  "job_id": "abc123",
  "filename": "document.pdf",
  "category": "document",
  "status": "queued",
  "route": ["cpu-extract"]
}
```

### Example: Upload Image with Quality Info

```bash
curl -X POST http://localhost:8100/api/ingest/upload \
  -F "file=@scan.png"
```

Response:
```json
{
  "job_id": "def456",
  "filename": "scan.png",
  "category": "image",
  "status": "queued",
  "route": ["cpu-image", "gpu-paddle"],
  "quality": {
    "classification": "fixable",
    "issues": ["low_dpi:96", "skewed:3.2deg"],
    "dpi": 96,
    "skew": 3.2,
    "contrast": 0.72,
    "layout": "simple"
  }
}
```

## Image Quality Classification

Images are classified into three categories:

| Classification | Criteria | Processing Route |
|---------------|----------|------------------|
| **CLEAN** | High DPI, no skew, good contrast | Direct to PaddleOCR |
| **FIXABLE** | Minor issues (1-2 problems) | Preprocess, then PaddleOCR |
| **MESSY** | Multiple issues or complex layout | Heavy preprocess, Qwen-VL |

Quality checks (all under 5ms):
- DPI < 150: Needs upscaling
- Skew > 2 degrees: Needs deskewing
- Contrast < 0.4: Needs enhancement
- Layout complexity: simple/table/mixed/complex

## Events

The shard publishes these events:

| Event | When |
|-------|------|
| `ingest.file.received` | File uploaded |
| `ingest.file.classified` | Type/quality determined |
| `ingest.file.queued` | Job dispatched to workers |
| `ingest.job.completed` | Processing finished |
| `ingest.job.failed` | Processing failed (after retries) |

## Worker Pools Used

| Pool | Purpose |
|------|---------|
| `cpu-light` | Quality classification |
| `cpu-image` | Image preprocessing |
| `cpu-extract` | Document text extraction |
| `gpu-paddle` | PaddleOCR |
| `gpu-qwen` | Qwen-VL (smart OCR) |

## Configuration

In Frame config:

```yaml
ingest:
  storage_path: ./DataSilo/documents
  temp_path: ./DataSilo/temp/ingest
  max_file_size_mb: 100
  allowed_extensions: [.pdf, .docx, .png, .jpg, ...]
```
