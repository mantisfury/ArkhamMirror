# arkham-shard-documents

Document browser with viewer and metadata editor - primary interface for document interaction.

## Overview

The Documents shard provides a comprehensive interface for browsing, viewing, and managing documents within the ArkhamFrame system. It serves as the primary user-facing interface for document interaction, offering features like metadata editing, chunk browsing, entity viewing, and processing status tracking.

## Features

- **Document Browsing**: List and filter documents with pagination and search
- **Document Viewer**: View document content with page navigation for multi-page documents
- **Metadata Editor**: Edit document metadata (title, description, tags, etc.)
- **Chunk Browser**: View and navigate document chunks generated during processing
- **Entity Viewer**: Display extracted entities associated with documents
- **Status Tracking**: Monitor document processing status and workflow stages

## Navigation

- **Category**: Data
- **Order**: 13
- **Route**: `/documents`
- **Sub-routes**:
  - `/documents` - All documents
  - `/documents/recent` - Recently added documents
  - `/documents/processing` - Documents currently being processed

## Dependencies

### Required Services
- `database` - Document metadata persistence
- `events` - Event publishing for document interactions

### Optional Services
- `storage` - File storage access for retrieving document files
- `documents` - Frame DocumentService for CRUD operations

## Events

### Published Events
- `documents.view.opened` - User opened a document for viewing
- `documents.metadata.updated` - Document metadata was modified
- `documents.status.changed` - Document processing status changed
- `documents.selection.changed` - User selected different document(s)

### Subscribed Events
- `document.processed` - Frame event when a document completes processing
- `document.deleted` - Frame event when a document is deleted

## API Endpoints

### Document Management
- `GET /api/documents/items` - List documents with pagination and filtering
- `GET /api/documents/items/{document_id}` - Get single document details
- `PATCH /api/documents/items/{document_id}` - Update document metadata
- `DELETE /api/documents/items/{document_id}` - Delete a document

### Document Content
- `GET /api/documents/{document_id}/content` - Get document content
- `GET /api/documents/{document_id}/pages/{page_number}` - Get specific page

### Related Data
- `GET /api/documents/{document_id}/chunks` - Get document chunks
- `GET /api/documents/{document_id}/entities` - Get extracted entities
- `GET /api/documents/{document_id}/metadata` - Get full metadata

### Status and Counts
- `GET /api/documents/count` - Get total document count (for badge)
- `GET /api/documents/stats` - Get document statistics

## Capabilities

- `document_viewing` - View document content and navigate pages
- `metadata_editing` - Edit document metadata
- `chunk_browsing` - Browse and search document chunks
- `status_tracking` - Track document processing status

## State Management

### URL State
- `documentId` - Currently viewed document ID
- `page` - Current page number for multi-page documents
- `view` - Active view mode (metadata, content, chunks, entities)
- `filter` - Active filter preset

### Local Storage
- `viewer_zoom` - Document viewer zoom level
- `show_metadata` - Metadata panel visibility
- `chunk_display_mode` - Chunk display preferences

## Installation

```bash
cd packages/arkham-shard-documents
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on next startup.

## Development

### Running Tests
```bash
pytest
```

### Type Checking
```bash
mypy arkham_shard_documents
```

### Code Formatting
```bash
black arkham_shard_documents
```

## Architecture

### Components

- **DocumentsShard** - Main shard class implementing ArkhamShard interface
- **API Router** - FastAPI endpoints for document operations
- **Models** - Pydantic models for request/response validation
- **Business Logic** - Document viewing, metadata editing, status tracking

### Database Schema

Uses schema `arkham_documents` with tables for:
- Document metadata cache
- User viewing history
- Custom metadata fields

## Usage Example

```python
# The shard is automatically loaded by the Frame
# Access via Frame API or directly through endpoints

# List documents
GET /api/documents/items?page=1&page_size=20&status=processed

# View a document
GET /api/documents/items/{doc_id}

# Update metadata
PATCH /api/documents/items/{doc_id}
{
  "title": "New Title",
  "tags": ["important", "reviewed"]
}

# Get document chunks
GET /api/documents/{doc_id}/chunks
```

## Production Compliance

This shard is compliant with:
- Shard Manifest Schema v1.0 (`shard_manifest_schema_prod.md`)
- ArkhamFrame v0.1.0
- Event naming conventions: `{shard}.{entity}.{action}`
- No direct shard dependencies (empty `dependencies.shards`)

## License

Part of the SHATTERED project.
