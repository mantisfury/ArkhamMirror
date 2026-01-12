# arkham-shard-ingest

> Document ingestion and file processing with intelligent routing

**Version:** 0.1.0
**Category:** Data
**Frame Requirement:** >=0.1.0

## Overview

The Ingest shard handles file uploads and processing for SHATTERED. It classifies incoming files, assesses image quality, and routes them through the appropriate worker pipeline (OCR, parsing, embedding). Supports single file uploads, batch uploads, and filesystem path ingestion.

### Key Capabilities

1. **File Classification** - Automatic categorization of documents, images, audio, archives
2. **Image Quality Assessment** - DPI, skew, contrast, noise analysis for OCR routing
3. **Intelligent Routing** - Routes files to appropriate workers based on type and quality
4. **Batch Processing** - Upload multiple files as tracked batches with staggered dispatch
5. **Database Persistence** - Jobs, batches, and checksums persisted across restarts

## Features

### File Processing
- Single file upload via HTTP multipart
- Batch upload with tracking
- Filesystem path ingestion (file or directory)
- Recursive directory scanning
- Checksum-based deduplication

### Image Quality Analysis
- DPI detection and classification
- Skew angle measurement
- Contrast ratio analysis
- Noise detection
- Layout complexity assessment (simple, table, mixed, complex)
- Blank page detection and skipping
- Automatic downscaling for memory optimization

### OCR Routing Modes
- **auto** - Intelligent routing based on quality assessment
- **paddle_only** - Force PaddleOCR for all images
- **qwen_only** - Force Qwen VL for all images

### Job Management
- Priority levels: user (highest), batch, reprocess
- Job status tracking: pending, queued, processing, completed, failed, dead
- Retry failed jobs (up to 3 retries)
- Queue statistics and monitoring

### Configurable Settings
- Max/min file size limits
- Deduplication toggle
- Image downscaling toggle
- Blank page skipping
- OCR confidence threshold
- OCR cache with configurable TTL

## Installation

```bash
pip install -e packages/arkham-shard-ingest
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Upload Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/upload` | Upload single file |
| POST | `/api/ingest/upload/batch` | Upload multiple files as batch |
| POST | `/api/ingest/ingest-path` | Ingest from filesystem path |

### Job Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ingest/job/{job_id}` | Get job status |
| POST | `/api/ingest/job/{job_id}/retry` | Retry failed job |
| GET | `/api/ingest/batch/{batch_id}` | Get batch status |
| GET | `/api/ingest/pending` | List pending jobs |

### Queue Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ingest/queue` | Get queue statistics |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ingest/settings` | Get current settings |
| PATCH | `/api/ingest/settings` | Update settings |

## API Examples

### Upload Single File

```bash
curl -X POST http://localhost:8100/api/ingest/upload \
  -F "file=@document.pdf" \
  -F "priority=user" \
  -F "ocr_mode=auto"
```

Response:
```json
{
  "job_id": "job_abc123",
  "filename": "document.pdf",
  "category": "document",
  "status": "queued",
  "route": ["cpu-parse", "gpu-embed"],
  "quality": null
}
```

### Upload Batch

```bash
curl -X POST http://localhost:8100/api/ingest/upload/batch \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@image.png" \
  -F "priority=batch" \
  -F "ocr_mode=auto"
```

### Ingest from Path

```json
POST /api/ingest/ingest-path
{
  "path": "/data/documents",
  "recursive": true,
  "priority": "batch",
  "ocr_mode": "auto"
}
```

### Get Queue Statistics

```json
GET /api/ingest/queue

{
  "pending": 15,
  "processing": 3,
  "completed": 142,
  "failed": 2,
  "by_priority": {
    "user": 5,
    "batch": 12,
    "reprocess": 1
  }
}
```

### Update Settings

```json
PATCH /api/ingest/settings
{
  "ingest_enable_deduplication": true,
  "ingest_max_file_size_mb": 200,
  "ocr_confidence_threshold": 0.85
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `ingest.file.received` | File received and classified |
| `ingest.file.classified` | File quality assessed |
| `ingest.file.queued` | File dispatched to workers |
| `ingest.job.started` | Job processing started |
| `ingest.job.completed` | Job completed successfully |
| `ingest.job.failed` | Job failed |
| `ingest.batch.queued` | Batch dispatched |
| `ingest.settings.updated` | Settings changed |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `worker.job.completed` | Update job status |
| `worker.job.failed` | Handle job failure |

## Data Models

### File Categories
- `document` - PDF, DOC, DOCX, TXT, etc.
- `image` - PNG, JPG, TIFF, etc.
- `audio` - MP3, WAV, etc.
- `archive` - ZIP, TAR, etc.
- `unknown` - Unrecognized types

### Image Quality Classifications
- `clean` - Direct to OCR, no preprocessing needed
- `fixable` - Light preprocessing required
- `messy` - Heavy preprocessing or smart OCR needed

### Job Priority
- `user` (1) - User-initiated uploads (highest priority)
- `batch` (2) - Batch imports
- `reprocess` (3) - Re-processing requests

### Job Status
- `pending` - Awaiting dispatch
- `queued` - In worker queue
- `processing` - Being processed
- `completed` - Successfully finished
- `failed` - Failed (can retry)
- `dead` - Failed after all retries

## Configuration Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `ingest_ocr_mode` | auto | OCR routing mode |
| `ingest_max_file_size_mb` | 100 | Maximum file size |
| `ingest_min_file_size_bytes` | 100 | Minimum file size |
| `ingest_enable_validation` | true | Validate files on upload |
| `ingest_enable_deduplication` | true | Skip duplicate files |
| `ingest_enable_downscale` | true | Downscale high-DPI images |
| `ingest_skip_blank_pages` | true | Skip blank pages |
| `ocr_parallel_pages` | 4 | Pages processed in parallel |
| `ocr_confidence_threshold` | 0.8 | Minimum OCR confidence |
| `ocr_enable_escalation` | true | Escalate low-confidence to VLM |
| `ocr_enable_cache` | true | Cache OCR results |
| `ocr_cache_ttl_days` | 7 | Cache expiration |

## UI Routes

| Route | Description |
|-------|-------------|
| `/ingest` | Ingest page with upload interface |

## Dependencies

### Required Services
- **database** - PostgreSQL 14+ for job and batch persistence
- **storage** - File storage
- **workers** - PostgreSQL job queue (SKIP LOCKED pattern)
- **events** - Event publishing

### Optional Services
- **vectors** - pgvector for embedding results

### Infrastructure Notes
This shard uses PostgreSQL for all persistence and job queuing. No Redis or external queue system is required. Job queues use PostgreSQL's SKIP LOCKED pattern for efficient concurrent processing.

## URL State

| Parameter | Description |
|-----------|-------------|
| `jobId` | Selected job |
| `batchId` | Selected batch |

## Architecture Notes

### Batch Staggering
For large batches (>10 files), jobs are dispatched with 0.5s delays every 10 jobs to prevent GPU memory overload.

### Worker Routing
Files are routed to worker pools based on type:
- Documents: `cpu-parse` -> `gpu-embed`
- Images (clean): `gpu-ocr-paddle` -> `cpu-parse` -> `gpu-embed`
- Images (messy): `gpu-ocr-qwen` -> `cpu-parse` -> `gpu-embed`

## Development

```bash
# Run tests
pytest packages/arkham-shard-ingest/tests/

# Type checking
mypy packages/arkham-shard-ingest/
```

## License

MIT
