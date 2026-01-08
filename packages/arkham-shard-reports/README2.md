# arkham-shard-reports

> Analytical report generation from investigation data

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

## Overview

The Reports shard generates analytical reports from SHATTERED investigation data. It creates summary reports, entity profiles, timeline reports, contradiction analyses, and ACH reports. Supports templates for custom report formats, scheduled generation, and multiple export formats.

### Key Capabilities

1. **Summary Reports** - System overview reports
2. **Entity Reports** - Entity profile reports
3. **Timeline Reports** - Temporal analysis reports
4. **Contradiction Reports** - Contradiction analysis
5. **ACH Reports** - Analysis of Competing Hypotheses
6. **Custom Reports** - Template-based generation
7. **Scheduled Reports** - Recurring generation
8. **Report Export** - Multiple output formats

## Features

### Report Types
- `summary` - Project summary report
- `entity_profile` - Entity profile report
- `timeline` - Timeline analysis report
- `contradiction` - Contradiction analysis
- `ach` - ACH matrix report
- `custom` - Template-based custom report

### Report Status
- `pending` - Report queued
- `generating` - Report being generated
- `completed` - Report ready
- `failed` - Generation failed

### Report Formats
- `html` - Interactive HTML
- `pdf` - PDF document
- `docx` - Microsoft Word
- `markdown` - Markdown format
- `json` - Structured JSON

### Template System
- Create custom report templates
- Reusable parameter schemas
- Shared template library
- Version control

### Scheduling
- Schedule recurring reports
- Cron-like scheduling
- Automatic generation
- Notification on completion

## Installation

```bash
pip install -e packages/arkham-shard-reports
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Counts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/health` | Health check |
| GET | `/api/reports/count` | Total count |
| GET | `/api/reports/pending/count` | Pending count (badge) |

### Report CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/` | List reports |
| POST | `/api/reports/` | Create report |
| GET | `/api/reports/{id}` | Get report |
| DELETE | `/api/reports/{id}` | Delete report |
| GET | `/api/reports/{id}/content` | Get report content |
| GET | `/api/reports/{id}/download` | Download report file |

### Status Filtered

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/pending` | List pending reports |
| GET | `/api/reports/completed` | List completed reports |
| GET | `/api/reports/failed` | List failed reports |

### Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/templates` | List templates |
| POST | `/api/reports/templates` | Create template |
| GET | `/api/reports/templates/{id}` | Get template |
| GET | `/api/reports/templates/shared` | List shared templates |
| GET | `/api/reports/templates/shared/{id}` | Get shared template |
| POST | `/api/reports/from-shared-template` | Create from shared |

### Schedules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/schedules` | List schedules |
| POST | `/api/reports/schedules` | Create schedule |
| DELETE | `/api/reports/schedules/{id}` | Delete schedule |

### Preview and Stats

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/preview` | Preview report |
| GET | `/api/reports/stats` | Report statistics |

## API Examples

### Create Report

```json
POST /api/reports/
{
  "name": "Q4 Investigation Summary",
  "report_type": "summary",
  "format": "pdf",
  "project_id": "proj_123",
  "parameters": {
    "date_range": {
      "start": "2024-10-01",
      "end": "2024-12-31"
    },
    "include_entities": true,
    "include_timeline": true,
    "include_contradictions": true
  }
}
```

Response:
```json
{
  "id": "rpt_abc123",
  "name": "Q4 Investigation Summary",
  "report_type": "summary",
  "format": "pdf",
  "status": "pending",
  "project_id": "proj_123",
  "created_at": "2024-12-15T10:30:00Z",
  "generated_at": null,
  "file_path": null,
  "file_size": null,
  "download_url": null
}
```

### Get Report Content

```bash
GET /api/reports/{report_id}/content
```

Returns rendered report content (HTML for display).

### Download Report

```bash
GET /api/reports/{report_id}/download
```

Returns report file with appropriate Content-Type.

### List Reports with Filtering

```bash
GET /api/reports/?status=completed&report_type=summary&limit=20
```

### Create Report Template

```json
POST /api/reports/templates
{
  "name": "Entity Profile Template",
  "description": "Standard entity profile report",
  "report_type": "entity_profile",
  "template_content": "# {{entity.name}}\n\n## Overview\n{{entity.description}}...",
  "parameter_schema": {
    "entity_id": {"type": "string", "required": true},
    "include_relationships": {"type": "boolean", "default": true}
  },
  "default_format": "pdf"
}
```

### Create from Shared Template

```json
POST /api/reports/from-shared-template
{
  "template_id": "tpl_shared_123",
  "name": "John Smith Profile",
  "parameters": {
    "entity_id": "ent_person_123",
    "include_relationships": true
  }
}
```

### Create Schedule

```json
POST /api/reports/schedules
{
  "name": "Weekly Summary",
  "template_id": "tpl_summary",
  "cron_expression": "0 9 * * MON",
  "parameters": {
    "date_range": "last_week"
  },
  "notification_emails": ["analyst@example.com"]
}
```

### Get Statistics

```bash
GET /api/reports/stats
```

Response:
```json
{
  "total_reports": 250,
  "by_status": {
    "pending": 5,
    "generating": 2,
    "completed": 230,
    "failed": 13
  },
  "by_type": {
    "summary": 100,
    "entity_profile": 80,
    "timeline": 40,
    "ach": 30
  },
  "by_format": {
    "pdf": 150,
    "html": 60,
    "docx": 40
  },
  "total_templates": 15,
  "active_schedules": 5,
  "avg_generation_time_ms": 2345.6
}
```

### Preview Report

```json
POST /api/reports/preview
{
  "report_type": "entity_profile",
  "parameters": {"entity_id": "ent_123"},
  "max_sections": 3
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `reports.report.generated` | Report generation completed |
| `reports.report.scheduled` | Report scheduled |
| `reports.report.failed` | Report generation failed |
| `reports.template.created` | New template created |
| `reports.template.updated` | Template updated |
| `reports.schedule.created` | New schedule created |
| `reports.schedule.executed` | Scheduled report executed |

### Subscribed Events

No subscribed events - triggered by API calls.

## UI Routes

| Route | Description |
|-------|-------------|
| `/reports` | All reports list |
| `/reports/pending` | Pending reports |
| `/reports/completed` | Completed reports |
| `/reports/templates` | Template management |
| `/reports/schedules` | Schedule management |

## Dependencies

### Required Services
- **database** - Report and template storage
- **events** - Event publishing

### Optional Services
- **llm** - AI-powered report generation
- **storage** - File storage for reports
- **workers** - Background generation

## URL State

| Parameter | Description |
|-----------|-------------|
| `reportId` | Selected report |
| `templateId` | Selected template |
| `status` | Filter by status |
| `view` | Display mode |

### Local Storage Keys
- `show_parameters` - Expand parameter panels
- `sort_order` - Report list sort preference
- `default_format` - Default export format

## Template Syntax

Reports support Jinja2-style templating:

```markdown
# {{report.title}}

Generated: {{report.generated_at | date}}

## Summary
{{summary.text}}

{% for entity in entities %}
### {{entity.name}}
Type: {{entity.type}}
Mentions: {{entity.mention_count}}
{% endfor %}
```

## Development

```bash
# Run tests
pytest packages/arkham-shard-reports/tests/

# Type checking
mypy packages/arkham-shard-reports/
```

## License

MIT
