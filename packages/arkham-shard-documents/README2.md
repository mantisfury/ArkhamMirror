# arkham-shard-documents

> Document browser with viewer, metadata editor, and AI analysis

**Version:** 0.1.0
**Category:** Data
**Frame Requirement:** >=0.1.0

## Overview

The Documents shard provides the primary interface for document interaction in SHATTERED. It offers document browsing, viewing, metadata editing, chunk browsing, and entity viewing. Includes AI Junior Analyst integration for LLM-powered document analysis.

### Key Capabilities

1. **Document Viewing** - View document content with page navigation
2. **Metadata Editing** - Update titles, tags, and custom metadata
3. **Chunk Browsing** - Browse document chunks with pagination
4. **Status Tracking** - Track document processing status
5. **AI Analysis** - AI Junior Analyst for document analysis

## Features

### Document Management
- List documents with pagination, sorting, and filtering
- Filter by status, file type, and project
- Search across document titles and content
- View full document metadata
- Update titles, tags, and custom metadata
- Delete documents (single and batch)

### Content Viewing
- View full document content
- Page-by-page navigation for multi-page documents
- View modes: metadata, content, chunks, entities
- Track recently viewed documents

### Chunk Browser
- Paginated chunk list
- View chunk content and token counts
- Link to embedding IDs

### Entity Browser
- View extracted entities (PERSON, ORG, GPE, DATE, etc.)
- Filter by entity type
- View confidence scores and occurrences
- Context snippets for each entity

### Batch Operations
- Bulk tag updates (add/remove)
- Bulk document deletion

### AI Junior Analyst
- Streaming AI analysis of documents
- Configurable analysis depth (quick, standard, detailed)
- Conversation history support
- Session continuity

## Installation

```bash
pip install -e packages/arkham-shard-documents
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents/health` | Health check |
| GET | `/api/documents/count` | Document count (badge) |
| GET | `/api/documents/stats` | Document statistics |

### Document CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents/items` | List documents (paginated) |
| GET | `/api/documents/items/{id}` | Get document by ID |
| PATCH | `/api/documents/items/{id}` | Update document metadata |
| DELETE | `/api/documents/items/{id}` | Delete document |

### Document Content

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents/{id}/content` | Get document content |
| GET | `/api/documents/{id}/pages/{num}` | Get specific page |
| GET | `/api/documents/{id}/metadata` | Get full metadata |

### Related Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents/{id}/chunks` | Get document chunks |
| GET | `/api/documents/{id}/entities` | Get extracted entities |

### History

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents/recently-viewed` | Recently viewed documents |

### Batch Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/batch/update-tags` | Bulk tag update |
| POST | `/api/documents/batch/delete` | Bulk delete |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### List Documents with Filtering

```bash
curl "http://localhost:8100/api/documents/items?page=1&page_size=20&status=processed&sort=created_at&order=desc"
```

Response:
```json
{
  "items": [
    {
      "id": "doc_abc123",
      "title": "Report Q4 2024",
      "filename": "report_q4.pdf",
      "file_type": "application/pdf",
      "file_size": 1048576,
      "status": "processed",
      "page_count": 15,
      "chunk_count": 42,
      "entity_count": 28,
      "created_at": "2024-12-15T10:30:00Z",
      "updated_at": "2024-12-15T10:35:00Z",
      "tags": ["quarterly", "finance"],
      "custom_metadata": {}
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20
}
```

### Update Document Metadata

```json
PATCH /api/documents/items/{document_id}
{
  "title": "Updated Report Title",
  "tags": ["quarterly", "finance", "reviewed"],
  "custom_metadata": {"reviewer": "John Doe"}
}
```

### Get Document Chunks

```bash
curl "http://localhost:8100/api/documents/{document_id}/chunks?page=1&page_size=50"
```

### Batch Tag Update

```json
POST /api/documents/batch/update-tags
{
  "document_ids": ["doc1", "doc2", "doc3"],
  "add_tags": ["reviewed"],
  "remove_tags": ["pending"]
}
```

### AI Junior Analyst (Streaming)

```json
POST /api/documents/ai/junior-analyst
{
  "target_id": "doc_abc123",
  "depth": "detailed",
  "message": "Summarize the key findings in this document",
  "session_id": "session_xyz"
}
```

Returns: Server-Sent Events stream with analysis chunks

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `documents.view.opened` | Document opened for viewing |
| `documents.metadata.updated` | Document metadata changed |
| `documents.status.changed` | Document status changed |
| `documents.selection.changed` | Document selection changed |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.processed` | Update document status on processing complete |
| `document.deleted` | Handle document deletion |

## Data Models

### Document Status
- `uploaded` - File uploaded, awaiting processing
- `processing` - Currently being processed
- `processed` - Processing complete
- `failed` - Processing failed

### Entity Types
- `PERSON` - People names
- `ORG` - Organizations
- `GPE` - Geopolitical entities
- `DATE` - Dates and times
- `MONEY` - Monetary values
- `LOC` - Locations
- And more (NER model dependent)

## UI Routes

| Route | Description |
|-------|-------------|
| `/documents` | All documents list |
| `/documents/recent` | Recently viewed |
| `/documents/processing` | Processing documents |

## Dependencies

### Required Services
- **database** - Document metadata persistence
- **events** - Event publishing

### Optional Services
- **storage** - File storage access
- **documents** - Frame DocumentService for CRUD

## URL State

| Parameter | Description |
|-----------|-------------|
| `documentId` | Active document ID |
| `page` | Current page number |
| `view` | View mode (metadata, content, chunks, entities) |
| `filter` | Active filter preset |

### Local Storage Keys
- `viewer_zoom` - Zoom level preference
- `show_metadata` - Metadata panel visibility
- `chunk_display_mode` - Chunk display preferences

## Document Statistics

The `/api/documents/stats` endpoint returns:
- `total_documents` - Total document count
- `processed_documents` - Successfully processed
- `processing_documents` - Currently processing
- `failed_documents` - Failed processing
- `total_size_bytes` - Total storage used
- `total_pages` - Total page count
- `total_chunks` - Total chunk count

## Development

```bash
# Run tests
pytest packages/arkham-shard-documents/tests/

# Type checking
mypy packages/arkham-shard-documents/
```

## License

MIT
