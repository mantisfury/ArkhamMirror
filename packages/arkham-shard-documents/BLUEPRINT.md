# Documents Shard Blueprint

Created: 2025-12-25
Status: Blueprint/Stub Implementation
Version: 0.1.0

## Overview

This is a **blueprint implementation** of the Documents shard for SHATTERED/ArkhamFrame. All files have been created with proper structure, interfaces, and stubs, but business logic is NOT implemented.

## Purpose

The Documents shard provides:
- Document browser with filtering and search
- Document viewer with page navigation
- Metadata editor
- Chunk browsing
- Entity viewing
- Processing status tracking

## Files Created (7)

### 1. `pyproject.toml` (26 lines)
- Package definition with correct entry point
- Dependencies: arkham-frame>=0.1.0, pydantic>=2.0.0
- Entry point: `documents = "arkham_shard_documents:DocumentsShard"`

### 2. `shard.yaml` (78 lines)
- Production-compliant manifest v1.0
- Category: Data, Order: 13
- Icon: FileText
- 3 sub-routes: all, recent, processing
- Events: 4 published, 2 subscribed
- Capabilities: document_viewing, metadata_editing, chunk_browsing, status_tracking

### 3. `README.md` (166 lines)
- Comprehensive documentation
- Feature list
- API endpoint documentation
- Usage examples
- Installation instructions
- Production compliance statement

### 4. `arkham_shard_documents/__init__.py` (6 lines)
- Package exports: DocumentsShard
- Version: 0.1.0

### 5. `arkham_shard_documents/shard.py` (212 lines)
- DocumentsShard class extending ArkhamShard
- initialize() and shutdown() methods with proper service checks
- Event handler stubs: _on_document_processed, _on_document_deleted
- Public API methods for other shards (stubs)
- Database schema creation stub

### 6. `arkham_shard_documents/api.py` (392 lines)
- FastAPI router with prefix /api/documents
- 15+ endpoint stubs including:
  - List documents with pagination
  - Get/update/delete document
  - Get document content and pages
  - Get chunks and entities
  - Statistics and counts
  - Batch operations
- All endpoints have proper models and signatures
- All endpoints return stub responses or raise 404

### 7. `arkham_shard_documents/models.py` (292 lines)
- 15 dataclass models including:
  - DocumentRecord, ViewingRecord, UserPreferences
  - DocumentPage, DocumentChunkRecord
  - DocumentEntity, EntityOccurrence
  - DocumentFilter, DocumentStatistics
  - BatchOperationResult
- All enums: DocumentStatus, ViewMode, ChunkDisplayMode
- Type-annotated with proper defaults

## Compliance

### Production Standards ✓
- [x] Manifest v1.0 compliant
- [x] Event naming: `{shard}.{entity}.{action}` format
- [x] No shard dependencies (empty `dependencies.shards`)
- [x] Correct navigation category and order
- [x] Standard capability names
- [x] Proper entry point format

### Package Structure ✓
- [x] pyproject.toml with entry point
- [x] shard.yaml manifest
- [x] README.md documentation
- [x] __init__.py exports
- [x] shard.py implementation
- [x] api.py routes
- [x] models.py data models

### Code Quality ✓
- [x] Type annotations throughout
- [x] Docstrings on all classes and methods
- [x] Logging statements
- [x] Error handling patterns
- [x] Service availability checks
- [x] TODO comments for implementation

## Next Steps (Implementation)

To complete this shard:

1. **Database Schema** (shard.py)
   - Implement `_create_schema()` for arkham_documents schema
   - Create tables: viewing_history, custom_metadata, user_preferences

2. **Event Handlers** (shard.py)
   - Implement `_on_document_processed()`
   - Implement `_on_document_deleted()`

3. **API Endpoints** (api.py)
   - Implement document listing with filters
   - Implement content retrieval from storage
   - Implement metadata updates with event publishing
   - Implement chunk and entity queries
   - Implement statistics aggregation
   - Implement batch operations

4. **Public Methods** (shard.py)
   - Implement `get_document_view_count()`
   - Implement `get_recently_viewed()`
   - Implement `mark_document_viewed()`

5. **Testing**
   - Unit tests for models
   - API endpoint tests
   - Integration tests with Frame
   - Event publishing/subscribing tests

6. **UI Integration**
   - Create React components in arkham-shard-shell
   - Document viewer component
   - Metadata editor component
   - Chunk browser component

## Events

### Published
- `documents.view.opened` - User opened a document
- `documents.metadata.updated` - Document metadata changed
- `documents.status.changed` - Document status changed
- `documents.selection.changed` - User selected different document

### Subscribed
- `document.processed` - Frame event when document processing completes
- `document.deleted` - Frame event when document is deleted

## Dependencies

### Required
- `database` - Document metadata persistence
- `events` - Event publishing and subscription

### Optional
- `storage` - File storage access (graceful degradation if unavailable)
- `documents` - Frame DocumentService (fallback to direct DB if unavailable)

## Installation

```bash
cd packages/arkham-shard-documents
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on next startup.

## Total Lines: 1,172

- pyproject.toml: 26
- shard.yaml: 78
- README.md: 166
- __init__.py: 6
- shard.py: 212
- api.py: 392
- models.py: 292

---

**Status**: Blueprint complete - ready for implementation
**Compliance**: Production v1.0 compliant
**Next**: Implement business logic and tests
