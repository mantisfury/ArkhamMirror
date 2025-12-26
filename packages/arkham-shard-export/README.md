# Export Shard

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

Data export shard for ArkhamFrame. Exports documents, entities, claims, timeline events, and analysis results in various formats (JSON, CSV, PDF, DOCX).

## Overview

The Export shard provides:

1. **Multi-Format Export** - JSON, CSV, PDF, DOCX (PDF/DOCX are placeholders)
2. **Export Jobs** - Asynchronous export processing with status tracking
3. **Multiple Targets** - Export documents, entities, claims, timeline, graph, matrix
4. **File Management** - Automatic file cleanup, download URLs, expiration
5. **Export History** - Track all export operations with metadata

## Key Features

### Export Formats

- **JSON** - Structured data export with full metadata
- **CSV** - Tabular data export for spreadsheet analysis
- **PDF** - Formatted document export (placeholder implementation)
- **DOCX** - Microsoft Word document export (placeholder implementation)
- **XLSX** - Excel spreadsheet export (placeholder implementation)

### Export Targets

- **documents** - Document records with text and metadata
- **entities** - Extracted entities with relationships
- **claims** - Claims with evidence and verification status
- **timeline** - Timeline events in chronological order
- **graph** - Graph nodes and edges
- **matrix** - ACH matrix with hypotheses and evidence

### Export Options

- **include_metadata** - Include system metadata in exports
- **include_relationships** - Include related entities/links
- **date_range** - Filter by date range
- **entity_types** - Filter entities by type
- **flatten** - Flatten nested structures for CSV

### Job Management

- **Async Processing** - Long-running exports processed in background
- **Status Tracking** - Pending, processing, completed, failed
- **File Storage** - Generated files stored with download URLs
- **Auto-Expiration** - Export files expire after configurable period

## Dependencies

### Required Frame Services
- **database** - Stores export jobs, metadata, and file references
- **events** - Publishes export lifecycle events

### Optional Frame Services
- **storage** - File storage for generated export files (fallback to temp files)

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `export.job.created` | New export job created |
| `export.job.started` | Export job processing started |
| `export.job.completed` | Export job finished successfully |
| `export.job.failed` | Export job failed with error |
| `export.file.created` | Export file generated |
| `export.file.downloaded` | Export file downloaded by user |
| `export.file.expired` | Export file expired/deleted |

### Subscribed Events

None - Export is triggered via API, not by events.

## API Endpoints

### Job Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/jobs` | List export jobs |
| POST | `/api/export/jobs` | Create new export job |
| GET | `/api/export/jobs/{id}` | Get job details |
| DELETE | `/api/export/jobs/{id}` | Cancel job |
| GET | `/api/export/jobs/{id}/download` | Download export file |

### Metadata

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/formats` | List supported formats |
| GET | `/api/export/targets` | List exportable targets |
| POST | `/api/export/preview` | Preview export without creating file |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/count` | Badge endpoint (pending jobs) |
| GET | `/api/export/stats` | Export statistics |

## Data Models

### ExportJob
```python
@dataclass
class ExportJob:
    id: str
    format: ExportFormat          # json, csv, pdf, docx, xlsx
    target: ExportTarget          # documents, entities, claims, etc.
    status: ExportStatus          # pending, processing, completed, failed
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    file_path: Optional[str]      # Path to generated file
    file_size: Optional[int]      # File size in bytes
    download_url: Optional[str]   # URL for download
    expires_at: Optional[datetime]
    error: Optional[str]          # Error message if failed
    filters: Dict[str, Any]       # Export filters
    options: ExportOptions        # Export options
    metadata: Dict[str, Any]
```

### ExportOptions
```python
@dataclass
class ExportOptions:
    include_metadata: bool = True
    include_relationships: bool = True
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    entity_types: Optional[List[str]] = None
    flatten: bool = False         # For CSV exports
```

### ExportResult
```python
@dataclass
class ExportResult:
    job_id: str
    success: bool
    file_path: Optional[str]
    file_size: int
    download_url: Optional[str]
    expires_at: Optional[datetime]
    record_count: int             # Number of records exported
    processing_time_ms: float
    error: Optional[str]
```

## Database Schema

The shard uses SQLite tables:

```sql
CREATE TABLE arkham_export_jobs (
    id TEXT PRIMARY KEY,
    format TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    file_path TEXT,
    file_size INTEGER,
    download_url TEXT,
    expires_at TEXT,
    error TEXT,
    filters TEXT DEFAULT '{}',
    options TEXT DEFAULT '{}',
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX idx_export_jobs_status ON arkham_export_jobs(status);
CREATE INDEX idx_export_jobs_created ON arkham_export_jobs(created_at);
CREATE INDEX idx_export_jobs_format ON arkham_export_jobs(format);
CREATE INDEX idx_export_jobs_target ON arkham_export_jobs(target);
```

## Installation

```bash
cd packages/arkham-shard-export
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on startup.

## Use Cases

### Data Analysis
- Export claims to CSV for spreadsheet analysis
- Export entities to JSON for data science workflows
- Export timeline to CSV for visualization tools

### Reporting
- Export verified claims to PDF for reports
- Export investigation results to DOCX for documentation
- Export ACH matrix to PDF for presentations

### Archival
- Export all documents to JSON for backup
- Export graph data for archival storage
- Export timeline events for historical records

### Integration
- Export entities to JSON for third-party tools
- Export claims to CSV for fact-checking platforms
- Export graph to JSON for visualization libraries

## Configuration

The shard respects these Frame configurations:

```yaml
# In frame config
export:
  default_expiration_hours: 24     # Export file expiration
  max_file_size_mb: 100            # Maximum export file size
  allowed_formats:                 # Restrict available formats
    - json
    - csv
  storage_path: ./exports          # Export file storage path
```

## Limitations

1. **PDF/DOCX** - Currently placeholder implementations returning empty files
2. **File Size** - Large exports may timeout or exceed memory limits
3. **Expiration** - Files expire after configured period (default 24 hours)
4. **Concurrency** - No built-in rate limiting on export job creation

## License

Part of the SHATTERED architecture, licensed under MIT.
