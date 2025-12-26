# Reports Shard

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

Analytical report generation shard for ArkhamFrame. Creates comprehensive reports from investigation data including summary reports, entity profiles, timeline reports, and custom analytical outputs.

## Overview

The Reports shard is a data export and analysis component that:

1. **Generates Reports** - Creates analytical reports from investigation data
2. **Manages Templates** - Provides reusable report templates
3. **Schedules Reports** - Automates periodic report generation
4. **Exports Formats** - Supports multiple output formats (HTML, PDF, Markdown, JSON)
5. **Custom Reports** - Allows custom report creation with parameters

## Key Features

### Report Types
- **Summary Reports** - System-wide summaries of documents, entities, claims
- **Entity Profile Reports** - Detailed profiles of specific entities
- **Timeline Reports** - Chronological event and document timelines
- **Contradiction Reports** - Analysis of contradictions and disputes
- **ACH Analysis Reports** - Analysis of Competing Hypotheses results
- **Custom Reports** - User-defined reports with custom parameters

### Report Formats
- **HTML** - Rich formatted HTML reports
- **PDF** - Print-ready PDF documents
- **Markdown** - Portable markdown format
- **JSON** - Machine-readable structured data

### Report Status
- `pending` - Queued for generation
- `generating` - Currently being generated
- `completed` - Successfully generated
- `failed` - Generation failed with errors

### Templates
- Pre-defined report templates
- Custom parameter schemas
- Default format configuration
- Reusable across multiple generations

### Scheduling
- Cron-based scheduling
- Automatic report generation
- Email delivery (when configured)
- Retention policies

## Dependencies

### Required Frame Services
- **database** - Stores reports, templates, and schedules
- **events** - Publishes report lifecycle events

### Optional Frame Services
- **llm** - Enables AI-powered report generation and summarization
- **storage** - Stores generated report files
- **workers** - Enables background report generation

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `reports.report.generated` | Report generation completed |
| `reports.report.scheduled` | Report scheduled for future generation |
| `reports.report.failed` | Report generation failed |
| `reports.template.created` | New report template created |
| `reports.template.updated` | Report template updated |
| `reports.schedule.created` | New report schedule created |
| `reports.schedule.executed` | Scheduled report executed |

### Subscribed Events

The Reports shard does not subscribe to external events. Reports are triggered via API calls or scheduled jobs.

## API Endpoints

### Reports CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/` | List reports with pagination |
| GET | `/api/reports/{id}` | Get report details |
| POST | `/api/reports/` | Generate new report |
| DELETE | `/api/reports/{id}` | Delete report |
| GET | `/api/reports/{id}/download` | Download report file |

### Report Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/pending` | List pending reports |
| GET | `/api/reports/completed` | List completed reports |
| GET | `/api/reports/failed` | List failed reports |

### Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/templates` | List templates |
| GET | `/api/reports/templates/{id}` | Get template details |
| POST | `/api/reports/templates` | Create template |
| PATCH | `/api/reports/templates/{id}` | Update template |
| DELETE | `/api/reports/templates/{id}` | Delete template |

### Schedules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/schedules` | List schedules |
| POST | `/api/reports/schedules` | Create schedule |
| PATCH | `/api/reports/schedules/{id}` | Update schedule |
| DELETE | `/api/reports/schedules/{id}` | Delete schedule |

### Preview & Generation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/preview` | Preview report without saving |
| POST | `/api/reports/generate/{template_id}` | Generate from template |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/count` | Total report count |
| GET | `/api/reports/pending/count` | Pending count (badge) |
| GET | `/api/reports/stats` | Report statistics |

## Data Models

### Report
```python
@dataclass
class Report:
    id: str
    report_type: ReportType         # summary, entity_profile, etc.
    title: str                      # Report title
    status: ReportStatus            # pending, generating, completed, failed
    created_at: datetime
    completed_at: Optional[datetime]
    parameters: Dict[str, Any]      # Generation parameters
    output_format: ReportFormat     # html, pdf, markdown, json
    file_path: Optional[str]        # Path to generated file
    file_size: Optional[int]        # File size in bytes
    error: Optional[str]            # Error message if failed
    metadata: Dict[str, Any]
```

### ReportTemplate
```python
@dataclass
class ReportTemplate:
    id: str
    name: str
    report_type: ReportType
    description: str
    parameters_schema: Dict[str, Any]  # JSON schema for parameters
    default_format: ReportFormat
    template_content: str              # Template markup
    created_at: datetime
    updated_at: datetime
```

### ReportSchedule
```python
@dataclass
class ReportSchedule:
    id: str
    template_id: str
    cron_expression: str               # Cron schedule
    enabled: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    parameters: Dict[str, Any]
    output_format: ReportFormat
    retention_days: int                # Keep reports for N days
```

### GeneratedSection
```python
@dataclass
class GeneratedSection:
    title: str
    content: str                       # Section content
    charts: List[Dict[str, Any]]       # Chart data
    tables: List[Dict[str, Any]]       # Table data
    subsections: List[GeneratedSection]
```

## Database Schema

The shard uses tables `arkham_reports`, `arkham_report_templates`, `arkham_report_schedules`:

```sql
CREATE TABLE arkham_reports (
    id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    completed_at TEXT,
    parameters TEXT DEFAULT '{}',
    output_format TEXT,
    file_path TEXT,
    file_size INTEGER,
    error TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE arkham_report_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    description TEXT,
    parameters_schema TEXT DEFAULT '{}',
    default_format TEXT,
    template_content TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE arkham_report_schedules (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    last_run TEXT,
    next_run TEXT,
    parameters TEXT DEFAULT '{}',
    output_format TEXT,
    retention_days INTEGER DEFAULT 30,
    FOREIGN KEY (template_id) REFERENCES arkham_report_templates(id)
);

-- Indexes
CREATE INDEX idx_reports_status ON arkham_reports(status);
CREATE INDEX idx_reports_type ON arkham_reports(report_type);
CREATE INDEX idx_reports_created ON arkham_reports(created_at);
CREATE INDEX idx_schedules_template ON arkham_report_schedules(template_id);
CREATE INDEX idx_schedules_enabled ON arkham_report_schedules(enabled);
```

## Installation

```bash
cd packages/arkham-shard-reports
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on startup.

## Use Cases

### Investigative Journalism
- Generate weekly summary reports of investigation progress
- Create entity profiles for key subjects
- Export timeline reports for article drafts
- Schedule daily updates for editors

### Legal Research
- Generate case summary reports
- Create entity relationship reports
- Export contradiction analysis for review
- Schedule periodic case updates

### Academic Research
- Generate literature review summaries
- Create author/entity profiles
- Export timeline of research developments
- Schedule monthly progress reports

## Integration with Other Shards

### All Shards
- Reports can aggregate data from any shard
- Templates can query shard endpoints
- No direct dependencies required

### Dashboard Shard
- Reports provide exportable views of dashboard data
- Scheduled reports for monitoring alerts

### Timeline Shard
- Timeline reports use timeline shard data
- Event chronology in summary reports

### ACH Shard
- ACH analysis reports
- Hypothesis evaluation summaries

## Configuration

The shard respects these Frame configurations:

```yaml
# In frame config
reports:
  max_concurrent_generations: 3     # Max parallel report generation
  default_retention_days: 30        # Keep reports for 30 days
  output_directory: "./reports"     # Report storage location
  enable_scheduling: true           # Allow scheduled reports
  formats_enabled: [html, pdf, markdown, json]  # Enabled formats
```

## License

Part of the SHATTERED architecture, licensed under MIT.
