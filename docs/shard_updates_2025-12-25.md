# Shard Production Compliance Updates - 2025-12-25

## Summary

Updated three shards to comply with the production schema (`shard_manifest_schema_prod.md`):
1. **arkham-shard-ingest**
2. **arkham-shard-parse**
3. **arkham-shard-ocr**

All shards are now **COMPLIANT** with production standards.

---

## Changes Overview

### arkham-shard-ingest

**Category**: Data (order 10) - No change needed
**Status**: COMPLIANT

#### Changes Made:
1. **Capabilities** - Standardized to production registry names
   - `file_intake` → `document_storage`
   - `type_detection` + `quality_classification` → `file_classification`
   - `image_preprocessing` → `image_analysis`
   - `worker_dispatch` → `background_processing`
   - Added `batch_processing`

#### Files Updated:
- `packages/arkham-shard-ingest/shard.yaml` - Updated capabilities
- `packages/arkham-shard-ingest/README.md` - Updated features and added capabilities section
- `packages/arkham-shard-ingest/production.md` - Created compliance documentation

#### Impact:
- No functional changes
- Better alignment with standard capability registry
- Improved documentation

---

### arkham-shard-parse

**Category**: Data (order 12) - Changed from Analysis (order 40)
**Status**: COMPLIANT

#### Changes Made:
1. **Navigation** - Corrected category and order
   - Category: `Analysis` → `Data`
   - Order: `40` → `12`
   - Reason: Parse performs data extraction, not analysis

2. **Capabilities** - Consolidated to standard names
   - All granular capabilities → `entity_extraction`
   - Added `background_processing`

#### Files Updated:
- `packages/arkham-shard-parse/shard.yaml` - Updated navigation and capabilities
- `packages/arkham-shard-parse/README.md` - Updated with overview and capabilities section
- `packages/arkham-shard-parse/production.md` - Created compliance documentation

#### Impact:
- Better navigation UX (shard in correct category)
- Correct processing pipeline order: Ingest (10) → OCR (11) → Parse (12)
- Simplified capability declarations

---

### arkham-shard-ocr

**Category**: Data (order 11) - Changed from Analysis (order 35)
**Status**: COMPLIANT

#### Changes Made:
1. **Navigation** - Corrected category and order
   - Category: `Analysis` → `Data`
   - Order: `35` → `11`
   - Reason: OCR performs data extraction, not analysis

2. **Capabilities** - Functional instead of implementation-specific
   - `paddle_ocr`, `qwen_ocr`, `page_processing`, etc. → `ocr_processing`
   - Added `gpu_acceleration`
   - Added `background_processing`

#### Files Updated:
- `packages/arkham-shard-ocr/shard.yaml` - Updated navigation and capabilities
- `packages/arkham-shard-ocr/README.md` - Updated with overview and capabilities section
- `packages/arkham-shard-ocr/production.md` - Created compliance documentation

#### Impact:
- Better navigation UX (shard in correct category)
- Correct processing pipeline order: Ingest (10) → OCR (11) → Parse (12)
- Capabilities describe "what" not "how"

---

## Data Category Processing Pipeline

The three shards now form a logical data processing pipeline in the correct order:

```
┌─────────────────────────────────────────────────────────┐
│                     Data Category                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Order 10: Ingest                                        │
│  ├─ Upload files                                         │
│  ├─ File classification                                  │
│  └─ Queue for processing                                 │
│                   │                                       │
│                   ▼                                       │
│  Order 11: OCR                                           │
│  ├─ Convert images to text                               │
│  ├─ Extract bounding boxes                               │
│  └─ GPU-accelerated processing                           │
│                   │                                       │
│                   ▼                                       │
│  Order 12: Parse                                         │
│  ├─ Extract entities (NER)                               │
│  ├─ Extract dates, locations                             │
│  ├─ Link entities                                        │
│  └─ Chunk text for embeddings                            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Validation Summary

All shards pass production schema validation:

### Manifest Requirements
- [x] `name` matches `^[a-z][a-z0-9-]*$`
- [x] `version` is valid semver
- [x] `entry_point` follows `module:Class` format
- [x] `api_prefix` starts with `/api/`
- [x] `requires_frame` is `>=0.1.0`
- [x] `navigation.category` is valid
- [x] `navigation.order` in correct range for category
- [x] `dependencies.shards` is empty `[]`

### Service Dependencies
- [x] All services are valid Frame services
- [x] Optional services properly declared
- [x] No shard-to-shard dependencies

### Events
- [x] All events follow `{shard}.{entity}.{action}` format
- [x] Subscriptions use valid patterns
- [x] No reserved prefixes used

### Worker Pools
- [x] All pool names match Frame's ResourceService
- [x] GPU pools properly declared in capabilities

### Capabilities
- [x] All capabilities use standard registry names
- [x] Capabilities describe functionality, not implementation
- [x] No version numbers or shard-specific prefixes

---

## Files Created

### Documentation
- `packages/arkham-shard-ingest/production.md`
- `packages/arkham-shard-parse/production.md`
- `packages/arkham-shard-ocr/production.md`
- `docs/shard_updates_2025-12-25.md` (this file)

### Updated Files
- `packages/arkham-shard-ingest/shard.yaml`
- `packages/arkham-shard-ingest/README.md`
- `packages/arkham-shard-parse/shard.yaml`
- `packages/arkham-shard-parse/README.md`
- `packages/arkham-shard-ocr/shard.yaml`
- `packages/arkham-shard-ocr/README.md`

---

## Testing Recommendations

1. **Frame Loading**: Verify all shards load without errors
   ```bash
   python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100
   ```

2. **API Access**: Check API docs show correct routes
   ```
   http://127.0.0.1:8100/docs
   ```

3. **Navigation**: Verify shards appear in Data category in correct order
   ```
   GET http://127.0.0.1:8100/api/shards
   ```

4. **Event Flow**: Test document processing pipeline
   - Upload file via Ingest
   - Verify OCR triggered for images
   - Verify Parse triggered after OCR
   - Check event history

5. **Worker Pools**: Verify worker registration
   ```
   GET http://127.0.0.1:8100/api/workers/stats
   ```

---

## Migration Notes

### For Developers

**No breaking changes** - All updates are backward compatible:
- Capability names changed but implementation unchanged
- Navigation changes only affect UI ordering
- All APIs remain the same
- Worker pools unchanged
- Event names unchanged

### For Users

**Improved UX** - Better navigation organization:
- Data processing shards now grouped together
- Logical processing order in sidebar
- Clear capability declarations

---

## Compliance Checklist

- [x] All three shards validated against production schema
- [x] Navigation categories and orders corrected
- [x] Capabilities standardized to registry names
- [x] Service dependencies verified
- [x] Event naming conventions followed
- [x] Worker pools match Frame definitions
- [x] No shard dependencies
- [x] Documentation created (production.md for each shard)
- [x] README files updated
- [x] All files use correct absolute paths

---

## Next Steps

1. Test the updated shards in a running Frame instance
2. Verify navigation appears correctly in the Shell UI
3. Test the processing pipeline (Ingest → OCR → Parse)
4. Update any external documentation referencing old capability names
5. Consider updating other shards using the same patterns

---

**Updated by**: Claude Sonnet 4.5
**Date**: 2025-12-25
**Schema Version**: Production v1.0
