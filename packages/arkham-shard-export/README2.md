# arkham-shard-export

> Data export in multiple formats (JSON, CSV, PDF, DOCX)

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

## Overview

The Export shard provides data export capabilities for SHATTERED. It supports exporting documents, entities, claims, timeline events, and analysis results to multiple formats including JSON, CSV, PDF, and DOCX. Exports are managed as jobs with status tracking and downloadable files.

### Key Capabilities

1. **JSON Export** - Export to JSON format
2. **CSV Export** - Export to CSV format
3. **PDF Export** - Export to PDF format
4. **DOCX Export** - Export to Word documents
5. **Batch Export** - Export multiple targets
6. **Scheduled Export** - Recurring exports (planned)

## Features

### Export Formats
- `json` - JSON format with full structure
- `csv` - Flat CSV for spreadsheets
- `pdf` - PDF documents
- `docx` - Microsoft Word format

### Export Targets
- `documents` - Document metadata and content
- `entities` - Extracted entities
- `claims` - Fact claims
- `timeline` - Timeline events
- `contradictions` - Detected contradictions
- `anomalies` - Anomaly detections
- `ach_matrices` - ACH analysis matrices
- `relationships` - Entity relationships

### Export Status
- `pending` - Job queued
- `processing` - Job running
- `completed` - Job finished
- `failed` - Job failed
- `expired` - Download expired

### Export Options
- Include/exclude metadata
- Include/exclude relationships
- Date range filtering
- Entity type filtering
- Flatten nested structures
- Record limits
- Custom sorting

## Installation

```bash
pip install -e packages/arkham-shard-export
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Job Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/count` | Export count (badge) |
| GET | `/api/export/jobs` | List export jobs |
| POST | `/api/export/jobs` | Create export job |
| GET | `/api/export/jobs/{id}` | Get job details |
| DELETE | `/api/export/jobs/{id}` | Delete job |
| GET | `/api/export/jobs/{id}/download` | Download export file |

### Format and Target Info

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/formats` | Available formats |
| GET | `/api/export/targets` | Available targets |

### Preview and Stats

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/export/preview` | Preview export |
| GET | `/api/export/stats` | Export statistics |

## API Examples

### Create Export Job

```json
POST /api/export/jobs
{
  "format": "json",
  "target": "documents",
  "filters": {
    "project_id": "proj_123",
    "status": "processed"
  },
  "options": {
    "include_metadata": true,
    "include_relationships": true,
    "date_range_start": "2024-01-01T00:00:00",
    "date_range_end": "2024-12-31T23:59:59",
    "max_records": 1000,
    "sort_by": "created_at",
    "sort_order": "desc"
  }
}
```

Response:
```json
{
  "id": "job_abc123",
  "format": "json",
  "target": "documents",
  "status": "pending",
  "created_at": "2024-12-15T10:30:00Z",
  "started_at": null,
  "completed_at": null,
  "file_path": null,
  "file_size": null,
  "download_url": null,
  "expires_at": null,
  "error": null,
  "filters": {"project_id": "proj_123"},
  "record_count": 0,
  "processing_time_ms": 0,
  "created_by": "system",
  "metadata": {}
}
```

### List Jobs with Filtering

```bash
GET /api/export/jobs?status=completed&format=csv&target=entities&limit=20
```

Response:
```json
{
  "jobs": [...],
  "total": 45,
  "limit": 20,
  "offset": 0
}
```

### Download Export

```bash
GET /api/export/jobs/{job_id}/download
```

Returns file with appropriate Content-Type header.

### Preview Export

```json
POST /api/export/preview
{
  "format": "csv",
  "target": "entities",
  "filters": {"entity_type": "PERSON"},
  "options": {"flatten": true},
  "max_preview_records": 10
}
```

Response:
```json
{
  "format": "csv",
  "target": "entities",
  "estimated_record_count": 1500,
  "preview_records": [...],
  "estimated_file_size_bytes": 256000
}
```

### Get Available Formats

```bash
GET /api/export/formats
```

Response:
```json
[
  {
    "format": "json",
    "name": "JSON",
    "description": "JavaScript Object Notation - full structure preserved",
    "file_extension": ".json",
    "mime_type": "application/json",
    "supports_flatten": false,
    "supports_metadata": true,
    "max_records": null,
    "placeholder": false
  },
  {
    "format": "csv",
    "name": "CSV",
    "description": "Comma-Separated Values - flat tabular format",
    "file_extension": ".csv",
    "mime_type": "text/csv",
    "supports_flatten": true,
    "supports_metadata": false,
    "max_records": 100000,
    "placeholder": false
  }
]
```

### Get Export Statistics

```bash
GET /api/export/stats
```

Response:
```json
{
  "total_jobs": 150,
  "by_status": {
    "pending": 5,
    "processing": 2,
    "completed": 130,
    "failed": 10,
    "expired": 3
  },
  "by_format": {
    "json": 80,
    "csv": 50,
    "pdf": 15,
    "docx": 5
  },
  "by_target": {
    "documents": 60,
    "entities": 40,
    "timeline": 30,
    "claims": 20
  },
  "jobs_pending": 5,
  "jobs_processing": 2,
  "jobs_completed": 130,
  "jobs_failed": 10,
  "total_records_exported": 250000,
  "total_file_size_bytes": 52428800,
  "avg_processing_time_ms": 1523.5,
  "oldest_pending_job": "2024-12-15T09:00:00Z"
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `export.job.created` | New export job created |
| `export.job.started` | Export job processing started |
| `export.job.completed` | Export job finished |
| `export.job.failed` | Export job failed |
| `export.file.created` | Export file generated |
| `export.file.downloaded` | Export file downloaded |
| `export.file.expired` | Export file expired |

### Subscribed Events

No subscribed events - triggered by API calls.

## UI Routes

| Route | Description |
|-------|-------------|
| `/export` | Export interface |
| `/export/jobs` | Export jobs list |
| `/export/history` | Export history |
| `/export/formats` | Format information |

## Dependencies

### Required Services
- **database** - Export job storage
- **events** - Event publishing

### Optional Services
- **storage** - File storage for exports

## URL State

| Parameter | Description |
|-----------|-------------|
| `jobId` | Selected export job |
| `format` | Filter by format |
| `status` | Filter by status |
| `target` | Filter by target |

### Local Storage Keys
- `download_auto` - Auto-download completed exports
- `show_options` - Show/hide options panel
- `default_format` - Preferred export format

## Export Options

| Option | Default | Description |
|--------|---------|-------------|
| `include_metadata` | true | Include metadata fields |
| `include_relationships` | true | Include related data |
| `date_range_start` | null | Start date filter |
| `date_range_end` | null | End date filter |
| `entity_types` | null | Filter entity types |
| `flatten` | false | Flatten nested structures |
| `max_records` | null | Maximum records |
| `sort_by` | null | Sort field |
| `sort_order` | "asc" | Sort direction |

## File Expiration

Export files are automatically cleaned up after expiration (default: 24 hours). Download URLs are invalidated after expiration.

## Development

```bash
# Run tests
pytest packages/arkham-shard-export/tests/

# Type checking
mypy packages/arkham-shard-export/
```

## License

MIT
