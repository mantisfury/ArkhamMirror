# Documents Shard - Wiring Plan

## Current State Summary

**Status:** ✅ **FULLY WIRED** - All backend endpoints implemented and functional.

### Backend (`packages/arkham-shard-documents/`)
- **shard.py**: ✅ Fully implemented
  - Database schema creation complete
  - Core service methods implemented (list, get, update, delete, stats)
  - View tracking methods implemented (get_document_view_count, get_recently_viewed, mark_document_viewed)
  - Content/Chunks/Entities retrieval methods implemented
  - Batch operations implemented (batch_update_tags, batch_delete_documents)
  - Event subscriptions wired (document.processed, document.deleted)
  - Event handlers implemented (_on_document_processed, _on_document_deleted)

- **api.py**: ✅ Fully implemented
  - List/Get/Update/Delete endpoints: ✅ Working
  - Stats/Count endpoints: ✅ Working
  - Content endpoints: ✅ Implemented (GET /{document_id}/content, GET /{document_id}/pages/{page_number})
  - Chunk endpoints: ✅ Implemented (GET /{document_id}/chunks)
  - Entity endpoints: ✅ Implemented (GET /{document_id}/entities)
  - Metadata endpoint: ✅ Implemented (GET /{document_id}/metadata)
  - Recently viewed: ✅ Implemented (GET /recently-viewed)
  - Batch operations: ✅ Implemented (POST /batch/update-tags, POST /batch/delete)

### Frontend (`packages/arkham-shard-shell/src/pages/documents/`)
- **DocumentsPage.tsx**: ✅ Fully implemented
  - List view with pagination working
  - Search and filtering working
  - Delete operation working
  - Stats display working
- **API integration**: ✅ Working for basic operations
  - Uses generic `usePaginatedFetch` hook
  - Direct fetch for delete operations

## Implementation Summary (Completed)

### Backend Changes

#### 1. View Tracking Methods (shard.py)
- `get_document_view_count(document_id)` - Returns count from arkham_document_views
- `get_recently_viewed(user_id, limit)` - Returns recently viewed document IDs
- `mark_document_viewed(document_id, user_id, view_mode, page_number)` - Records view and emits event

#### 2. Content Retrieval Methods (shard.py)
- `get_document_content(document_id, page_number)` - Fetches from Frame's arkham_frame.pages table
- Supports both single page and full document retrieval
- Falls back to direct DB query if Frame service unavailable

#### 3. Chunks Retrieval Methods (shard.py)
- `get_document_chunks(document_id, page, page_size)` - Fetches from Frame's arkham_frame.chunks table
- Supports pagination
- Returns chunk content, token count, embedding status

#### 4. Entities Retrieval Methods (shard.py)
- `get_document_entities(document_id, entity_type)` - Queries arkham_entities and arkham_entity_mentions
- Supports filtering by entity type
- Returns entities with occurrence counts and context snippets

#### 5. Batch Operations (shard.py)
- `batch_update_tags(document_ids, add_tags, remove_tags)` - Bulk tag modification
- `batch_delete_documents(document_ids)` - Bulk deletion with result tracking

#### 6. Event Handlers (shard.py)
- `_on_document_processed(event)` - Updates document status, emits documents.status.changed
- `_on_document_deleted(event)` - Cleans up views, emits documents.selection.changed
- Subscriptions wired in initialize(), unsubscribed in shutdown()

#### 7. API Endpoints (api.py)
All endpoints now properly call shard methods and handle errors:
- GET /{document_id}/content - Document content with view tracking
- GET /{document_id}/pages/{page_number} - Specific page content
- GET /{document_id}/chunks - Paginated chunks
- GET /{document_id}/entities - Entities with filtering
- GET /{document_id}/metadata - Full metadata
- GET /recently-viewed - Recently viewed documents list
- POST /batch/update-tags - Bulk tag operations
- POST /batch/delete - Bulk deletion

## Cross-Shard Dependencies

### Data Sources
1. **Frame DocumentService** (`arkham_frame.pages`, `arkham_frame.chunks`)
   - Primary source for document content and chunks
   - Accessed via frame.get_service("documents") or direct DB queries

2. **Entities Shard** (`arkham_entities`, `arkham_entity_mentions`)
   - Source for entity data per document
   - Joined via document_id in mentions table

### Events
**Published:**
- `documents.view.opened` - When content/chunks/entities accessed
- `documents.metadata.updated` - When metadata changed
- `documents.status.changed` - When processing status changes
- `documents.selection.changed` - When selection changes or document deleted

**Subscribed:**
- `document.processed` - From Frame when processing completes
- `document.deleted` - From Frame when document removed

## Testing Checklist

### Backend
- [x] GET /items returns paginated documents
- [x] GET /items/{id} returns single document with metadata
- [x] PATCH /items/{id} updates metadata correctly
- [x] DELETE /items/{id} removes document and cascades to views
- [x] GET /{id}/content returns document text
- [x] GET /{id}/chunks returns chunks with pagination
- [x] GET /{id}/entities returns extracted entities
- [x] POST /batch/update-tags updates multiple documents
- [x] POST /batch/delete removes multiple documents
- [x] View tracking records views correctly
- [x] Event handlers process events correctly

### Frontend
- [x] Document list loads and displays
- [x] Search and filtering work
- [x] Delete confirmation and execution work
- [x] Stats display correctly
- [ ] Document viewer shows content (needs frontend component)
- [ ] Chunk/entity tabs work (needs frontend component)

## Future Enhancements (Optional)

### Frontend Components Needed
1. **DocumentViewer.tsx** - View document content with page navigation
2. **DocumentDetail.tsx** - Full detail page with tabs for Content/Chunks/Entities/History
3. **ChunkBrowser.tsx** - Browse and search chunks
4. **EntityHighlighter.tsx** - Highlight entities in document text

These are UI enhancements that can be added incrementally. The backend is now fully functional.
