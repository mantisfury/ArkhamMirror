# arkham-shard-templates

> Template management for reports, letters, and exports

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

## Overview

The Templates shard provides template management for SHATTERED's document generation needs. It supports creating, editing, versioning, and rendering templates used by reports, letters, and exports. Templates use Jinja2-style syntax with placeholder validation.

### Key Capabilities

1. **Template Management** - CRUD operations on templates
2. **Template Rendering** - Render templates with data
3. **Template Versioning** - Version control for templates
4. **Placeholder Validation** - Validate placeholder usage
5. **Template Export** - Export templates to file

## Features

### Template Types
- `report` - Report templates
- `letter` - Letter templates
- `export` - Export format templates
- `email` - Email templates
- `custom` - Custom templates

### Template Status
- `active` - Available for use
- `inactive` - Disabled
- `draft` - Work in progress

### Template Syntax
Jinja2-style templating:
- Variables: `{{variable}}`
- Filters: `{{date | format}}`
- Conditionals: `{% if condition %}...{% endif %}`
- Loops: `{% for item in items %}...{% endfor %}`

### Versioning
- Automatic version creation on updates
- Version history tracking
- Restore previous versions
- Compare versions

### Placeholder System
- Auto-detect placeholders
- Validation against schema
- Required vs optional placeholders
- Default values

## Installation

```bash
pip install -e packages/arkham-shard-templates
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Count

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/templates/health` | Health check |
| GET | `/api/templates/count` | Template count (badge) |
| GET | `/api/templates/stats` | Statistics |
| GET | `/api/templates/types` | Available types |

### Template CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/templates/` | List templates |
| POST | `/api/templates/` | Create template |
| GET | `/api/templates/{id}` | Get template |
| PUT | `/api/templates/{id}` | Update template |
| DELETE | `/api/templates/{id}` | Delete template |
| POST | `/api/templates/{id}/activate` | Activate template |
| POST | `/api/templates/{id}/deactivate` | Deactivate template |

### Versioning

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/templates/{id}/versions` | List versions |
| POST | `/api/templates/{id}/versions` | Create version |
| GET | `/api/templates/{id}/versions/{vid}` | Get version |
| POST | `/api/templates/{id}/restore/{vid}` | Restore version |

### Rendering and Validation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/templates/{id}/render` | Render template |
| POST | `/api/templates/{id}/preview` | Preview render |
| POST | `/api/templates/{id}/validate` | Validate template |
| GET | `/api/templates/{id}/placeholders` | Get placeholders |

### Batch Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/templates/batch/activate` | Batch activate |
| POST | `/api/templates/batch/deactivate` | Batch deactivate |
| POST | `/api/templates/batch/delete` | Batch delete |

## API Examples

### Create Template

```json
POST /api/templates/
{
  "name": "FOIA Request Template",
  "description": "Standard FOIA request letter template",
  "template_type": "letter",
  "content": "Dear {{recipient.name}},\n\nPursuant to the Freedom of Information Act, I hereby request...\n\n{{request_details}}\n\nSincerely,\n{{sender.name}}",
  "placeholders": [
    {"name": "recipient.name", "required": true, "description": "Recipient's name"},
    {"name": "request_details", "required": true, "description": "Details of the request"},
    {"name": "sender.name", "required": true, "description": "Sender's name"}
  ]
}
```

### Render Template

```json
POST /api/templates/{template_id}/render
{
  "data": {
    "recipient": {"name": "Records Department"},
    "request_details": "All documents relating to contract #12345",
    "sender": {"name": "John Smith"}
  },
  "format": "html"
}
```

Response:
```json
{
  "rendered_content": "Dear Records Department,\n\nPursuant to the Freedom of Information Act...",
  "warnings": [],
  "missing_placeholders": []
}
```

### Preview Template

```json
POST /api/templates/{template_id}/preview
{
  "data": {},
  "use_sample_data": true
}
```

Returns rendered template with sample data for preview.

### Validate Template

```bash
POST /api/templates/{template_id}/validate
```

Response:
```json
[
  {"placeholder": "undefined_var", "warning": "Undefined placeholder used", "severity": "error"},
  {"placeholder": "optional_field", "warning": "No default value defined", "severity": "warning"}
]
```

### Get Placeholders

```bash
GET /api/templates/{template_id}/placeholders
```

Response:
```json
[
  {"name": "recipient.name", "required": true, "type": "string"},
  {"name": "request_details", "required": true, "type": "text"},
  {"name": "date", "required": false, "type": "date", "default": "today"}
]
```

### Create Version

```json
POST /api/templates/{template_id}/versions
{
  "comment": "Updated header formatting"
}
```

### Restore Version

```bash
POST /api/templates/{template_id}/restore/{version_id}
```

### Get Statistics

```bash
GET /api/templates/stats
```

Response:
```json
{
  "total_templates": 45,
  "active_templates": 38,
  "inactive_templates": 7,
  "by_type": {
    "report": 15,
    "letter": 20,
    "export": 8,
    "custom": 2
  },
  "total_versions": 156,
  "avg_versions_per_template": 3.5
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `templates.template.created` | New template created |
| `templates.template.updated` | Template modified |
| `templates.template.deleted` | Template removed |
| `templates.template.activated` | Template activated |
| `templates.template.deactivated` | Template deactivated |
| `templates.version.created` | New version created |
| `templates.version.restored` | Version restored |
| `templates.rendered` | Template rendered |

### Subscribed Events

No subscribed events - triggered by API calls.

## UI Routes

| Route | Description |
|-------|-------------|
| `/templates` | Template list |
| `/templates/all` | All templates |
| `/templates/create` | Create template |
| `/templates/versions` | Version history |

## Dependencies

### Required Services
- **database** - Template and version storage
- **events** - Event publishing

### Optional Services
- **storage** - File storage for exports

## URL State

| Parameter | Description |
|-----------|-------------|
| `templateId` | Selected template |
| `versionId` | Selected version |
| `type` | Filter by template type |
| `status` | Filter by active/inactive |

### Local Storage Keys
- `editor_preferences` - User editor settings
- `preview_mode` - Preview mode preference
- `show_placeholders` - Show placeholder hints

## Development

```bash
# Run tests
pytest packages/arkham-shard-templates/tests/

# Type checking
mypy packages/arkham-shard-templates/
```

## License

MIT
