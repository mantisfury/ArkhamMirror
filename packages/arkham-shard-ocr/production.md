# Production Compliance - arkham-shard-ocr

**Compliance Status**: COMPLIANT

**Date Updated**: 2025-12-25

---

## Changes Made

### 1. shard.yaml Updates

#### Navigation Category Correction
**Changed**:
```yaml
# Before
navigation:
  category: Analysis
  order: 35

# After
navigation:
  category: Data
  order: 11
```

**Reason**: Per task requirements, OCR shard belongs in the Data category (order 10-19), not Analysis. OCR is a data extraction process that converts images to text. Order 11 places it:
- After Ingest (order 10)
- Before Parse (order 12)
- In the natural processing pipeline: Ingest → OCR → Parse

#### Capabilities Standardization
**Changed**:
```yaml
# Before
capabilities:
  - paddle_ocr
  - qwen_ocr
  - page_processing
  - text_extraction
  - bounding_boxes

# After
capabilities:
  - ocr_processing
  - gpu_acceleration
  - background_processing
```

**Reason**: Updated to use standard capability names from the production schema:
- `ocr_processing` - Optical character recognition (covers PaddleOCR, Qwen-VL, page processing, text extraction, bounding boxes)
- `gpu_acceleration` - Uses GPU worker pools (gpu-paddle, gpu-qwen)
- `background_processing` - Uses worker pools for async processing

Original capabilities were implementation-specific. The new names are functional descriptors that align with the standard registry.

---

## Validation Results

### Manifest Fields (shard.yaml)

| Field | Status | Value | Compliant |
|-------|--------|-------|-----------|
| `name` | VALID | `ocr` | Matches `^[a-z][a-z0-9-]*$` |
| `version` | VALID | `0.1.0` | Valid semver |
| `entry_point` | VALID | `arkham_shard_ocr:OCRShard` | Correct format |
| `api_prefix` | VALID | `/api/ocr` | Starts with `/api/` |
| `requires_frame` | VALID | `>=0.1.0` | Valid constraint |
| `navigation.category` | VALID | `Data` | Valid category (corrected) |
| `navigation.order` | VALID | `11` | In range 10-19 for Data |
| `navigation.icon` | VALID | `ScanText` | Valid Lucide icon |
| `navigation.route` | VALID | `/ocr` | Unique route |
| `dependencies.services` | VALID | `database, storage, workers, events` | All valid Frame services |
| `dependencies.optional` | VALID | `documents` | Valid optional service |
| `dependencies.shards` | VALID | `[]` | Empty (required) |
| `capabilities` | VALID | Updated to standards | Standardized names |
| `events.publishes` | VALID | `{shard}.{entity}.{action}` format | All compliant |
| `events.subscribes` | VALID | `ingest.job.completed` | Valid pattern |
| `state.strategy` | VALID | `url` | Valid strategy |
| `state.url_params` | VALID | `documentId, pageId` | Non-filter params |
| `ui.has_custom_ui` | VALID | `false` | Uses generic UI |

### Service Dependencies

All declared services are available in Frame:
- `database` - Required, for OCR result storage
- `storage` - Required, for image file access
- `workers` - Required, for background OCR processing
- `events` - Required, for event pub/sub
- `documents` - Optional, for document management integration

### Event Declarations

All events follow naming convention `{shard}.{entity}.{action}`:
- `ocr.page.started`
- `ocr.page.completed`
- `ocr.document.started`
- `ocr.document.completed`
- `ocr.error`

Subscriptions use valid patterns:
- `ingest.job.completed` - Auto-trigger OCR for image documents

### Worker Pools

Shard uses these worker pools (all valid):
- `gpu-paddle` - PaddleOCR (2GB VRAM, 1 worker)
- `gpu-qwen` - Qwen-VL vision model (8GB VRAM, 1 worker)

Both pools are defined in Frame's ResourceService and match the production schema.

---

## Issues Found and Resolved

### Issue 1: Incorrect Navigation Category
**Problem**: Shard was in "Analysis" category (order 35) but performs data extraction.

**Resolution**: Moved to "Data" category with order 11. This correctly positions the shard:
- After Ingest (order 10) - OCR processes ingested images
- Before Parse (order 12) - OCR output feeds into parsing
- In the Data processing pipeline

**Impact**: Better UX, shard appears in correct navigation category in logical processing order.

### Issue 2: Implementation-Specific Capability Names
**Problem**: Capabilities listed implementation details (paddle_ocr, qwen_ocr) rather than functional capabilities.

**Resolution**: Updated to standard functional capability names:
- `ocr_processing` - What it does (optical character recognition)
- `gpu_acceleration` - How it does it (uses GPU workers)
- `background_processing` - Processing model (async workers)

**Impact**: None on functionality. Capabilities now describe what the shard does, not how. Specific OCR engines (Paddle, Qwen) are still documented in README and code.

---

## Final Compliance Status

**Overall**: COMPLIANT

All requirements from `shard_manifest_schema_prod.md` are met:
- Manifest structure follows production schema
- Service dependencies use correct Frame service names
- Events follow naming conventions
- Navigation is properly configured for Data category
- Worker pools match Frame's ResourceService definitions
- No shard dependencies (as required)
- Capabilities use standard functional names

---

## API Endpoints

The shard provides these endpoints:

### Core Endpoints
- `POST /api/ocr/page` - OCR a single page image
- `POST /api/ocr/document` - OCR all pages of a document

### Request/Response Examples

**OCR a Page**:
```bash
POST /api/ocr/page
{
  "image_path": "/path/to/image.png",
  "engine": "paddle",  # or "qwen"
  "language": "en"
}
```

Returns:
```json
{
  "text": "Extracted text...",
  "bounding_boxes": [...],
  "confidence": 0.95,
  "processing_time_ms": 234.5
}
```

---

## Implemented Features

### OCR Processing (`ocr_processing` capability)
- **PaddleOCR**: Fast, accurate OCR for printed text
  - Uses `gpu-paddle` worker pool
  - Best for clean, printed documents
  - Returns text with bounding boxes

- **Qwen-VL**: Vision-language model for complex OCR
  - Uses `gpu-qwen` worker pool
  - Best for handwritten text, degraded documents, complex layouts
  - Supports table extraction

- **Page-level processing**: Single images
- **Document-level processing**: Multi-page documents

### GPU Acceleration (`gpu_acceleration` capability)
- Uses GPU worker pools for hardware acceleration
- Automatic fallback if GPU unavailable (via ResourceService)
- VRAM-aware model loading

### Background Processing (`background_processing` capability)
- Async processing via worker queues
- Auto-triggers on `ingest.job.completed` for image documents
- Publishes completion events for downstream shards

---

## Processing Pipeline

1. **Ingest** triggers `ingest.job.completed` event
2. **OCR Shard** subscribes to event, checks document type
3. If image/scanned PDF:
   - Dispatches to appropriate GPU pool (paddle or qwen)
   - Processes page(s) asynchronously
   - Stores OCR results
   - Publishes `ocr.document.completed` event
4. **Downstream shards** (Parse, Search) can consume OCR results

---

## Notes

1. The shard is now fully compliant with production schema v1.0
2. Category change from Analysis to Data better reflects functionality
3. OCR is positioned in the correct processing pipeline order
4. Capabilities are functional rather than implementation-specific
5. GPU pool usage aligns with Frame's ResourceService tier system
6. Worker registration follows Frame patterns
7. Event subscriptions properly use EventBus

---

**Reviewed by**: Claude Sonnet 4.5
**Review Date**: 2025-12-25
