# Templates Shard

Template management system for ArkhamFrame. Create, edit, version, and render templates for reports, letters, exports, and custom documents.

## Overview

The Templates shard provides a comprehensive template management system with:

- **Template CRUD**: Create, read, update, and delete templates
- **Version Control**: Track changes with full version history
- **Placeholder System**: Define and validate placeholders for data binding
- **Template Rendering**: Render templates with Jinja2 engine
- **Type Management**: Support for multiple template types (REPORT, LETTER, EXPORT, EMAIL, CUSTOM)
- **Activation Control**: Enable/disable templates without deletion

## Features

### Template Types

- **REPORT**: Analysis reports and findings
- **LETTER**: Formal letters (FOIA requests, complaints, etc.)
- **EXPORT**: Data export templates
- **EMAIL**: Email templates
- **CUSTOM**: User-defined custom templates

### Placeholder System

Templates support placeholders for dynamic data:

```jinja2
Dear {{ recipient_name }},

This is to inform you about {{ subject }}.

Analysis Date: {{ analysis_date }}
Document Count: {{ document_count }}

{{ analysis_summary }}

Sincerely,
{{ sender_name }}
```

Placeholders are:
- Validated before rendering
- Documented with descriptions and data types
- Support default values
- Can be marked as required or optional

### Version Control

Every template change creates a new version:
- Full version history preserved
- Restore previous versions
- Track who made changes and when
- Compare versions

## Installation

```bash
cd packages/arkham-shard-templates
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on next startup.

## API Endpoints

### Health & Status

- `GET /api/templates/health` - Health check
- `GET /api/templates/count` - Total template count (badge)
- `GET /api/templates/stats` - Template statistics

### Template CRUD

- `GET /api/templates/` - List templates (with pagination and filters)
- `POST /api/templates/` - Create new template
- `GET /api/templates/{id}` - Get template by ID
- `PUT /api/templates/{id}` - Update template
- `DELETE /api/templates/{id}` - Delete template
- `POST /api/templates/{id}/activate` - Activate template
- `POST /api/templates/{id}/deactivate` - Deactivate template

### Versioning

- `GET /api/templates/{id}/versions` - List template versions
- `POST /api/templates/{id}/versions` - Create new version
- `GET /api/templates/{id}/versions/{version_id}` - Get specific version
- `POST /api/templates/{id}/restore/{version_id}` - Restore version

### Rendering

- `POST /api/templates/{id}/render` - Render template with data
- `POST /api/templates/{id}/preview` - Preview template
- `POST /api/templates/{id}/validate` - Validate placeholders

### Metadata

- `GET /api/templates/types` - List available template types
- `GET /api/templates/{id}/placeholders` - Get template placeholders

## Usage Examples

### Create a Template

```python
import httpx

template_data = {
    "name": "FOIA Request Letter",
    "template_type": "LETTER",
    "description": "Template for Freedom of Information Act requests",
    "content": """Dear {{ agency_name }},

Pursuant to the Freedom of Information Act, I hereby request access to:

{{ request_description }}

If you have any questions, please contact me at {{ contact_email }}.

Sincerely,
{{ requester_name }}
""",
    "placeholders": [
        {
            "name": "agency_name",
            "description": "Name of the agency",
            "data_type": "string",
            "required": True
        },
        {
            "name": "request_description",
            "description": "Description of records requested",
            "data_type": "string",
            "required": True
        },
        {
            "name": "contact_email",
            "description": "Contact email address",
            "data_type": "email",
            "required": True
        },
        {
            "name": "requester_name",
            "description": "Name of requester",
            "data_type": "string",
            "required": True
        }
    ],
    "is_active": True
}

response = httpx.post("http://localhost:8100/api/templates/", json=template_data)
template = response.json()
```

### Render a Template

```python
render_request = {
    "template_id": template["id"],
    "data": {
        "agency_name": "U.S. Department of Justice",
        "request_description": "All records related to case #2024-001",
        "contact_email": "requester@example.com",
        "requester_name": "John Smith"
    },
    "output_format": "text"
}

response = httpx.post(
    f"http://localhost:8100/api/templates/{template['id']}/render",
    json=render_request
)
result = response.json()
print(result["rendered_content"])
```

### List Templates with Filters

```python
# Get all active LETTER templates
response = httpx.get(
    "http://localhost:8100/api/templates/",
    params={
        "template_type": "LETTER",
        "is_active": True,
        "page": 1,
        "page_size": 20
    }
)
templates = response.json()
```

### Version Management

```python
# Create a new version
version_data = {
    "changes": "Updated formatting and added new placeholder for date"
}
response = httpx.post(
    f"http://localhost:8100/api/templates/{template_id}/versions",
    json=version_data
)

# List all versions
response = httpx.get(f"http://localhost:8100/api/templates/{template_id}/versions")
versions = response.json()

# Restore previous version
response = httpx.post(
    f"http://localhost:8100/api/templates/{template_id}/restore/{version_id}"
)
```

## Database Schema

Templates are stored in the `arkham_templates` schema:

### Tables

- **templates**: Main template records
  - id, name, template_type, description, content
  - placeholders (JSONB), version, is_active
  - metadata (JSONB), created_at, updated_at

- **template_versions**: Version history
  - id, template_id, version_number, content
  - placeholders (JSONB), created_at, created_by, changes

- **template_renders**: Render history (optional)
  - id, template_id, rendered_at, data_hash
  - output_format, success, error_message

## Events Published

- `templates.template.created` - New template created
- `templates.template.updated` - Template modified
- `templates.template.deleted` - Template removed
- `templates.template.activated` - Template activated
- `templates.template.deactivated` - Template deactivated
- `templates.version.created` - New version created
- `templates.version.restored` - Previous version restored
- `templates.rendered` - Template rendered with data

## Events Subscribed

None. Templates shard operates independently and is triggered via API calls.

## Configuration

No special configuration required. The shard uses standard Frame services:

- **database**: PostgreSQL for template storage
- **events**: EventBus for publishing template events
- **storage** (optional): File storage for template exports

## Integration

### With Reports Shard

Templates can be used by the Reports shard to generate formatted reports:

```python
# Reports shard uses Templates shard API
template_id = "report-template-id"
report_data = {...}

response = await frame.http_client.post(
    f"/api/templates/{template_id}/render",
    json={"data": report_data}
)
```

### With Letters Shard

Letters shard can use templates for generating formal letters:

```python
# Letters shard uses Templates shard API
template_id = "foia-letter-template"
letter_data = {...}

response = await frame.http_client.post(
    f"/api/templates/{template_id}/render",
    json={"data": letter_data}
)
```

### With Export Shard

Export shard can use templates for custom export formats:

```python
# Export shard uses Templates shard API
template_id = "export-template-id"
export_data = {...}

response = await frame.http_client.post(
    f"/api/templates/{template_id}/render",
    json={"data": export_data}
)
```

## Development

### Running Tests

```bash
pytest tests/
```

### Adding New Template Types

Template types are defined in `models.py`:

```python
class TemplateType(str, Enum):
    REPORT = "REPORT"
    LETTER = "LETTER"
    EXPORT = "EXPORT"
    EMAIL = "EMAIL"
    CUSTOM = "CUSTOM"
    # Add new types here
```

## Architecture

### Jinja2 Rendering Engine

Templates use Jinja2 for powerful template rendering:

- Variable substitution: `{{ variable }}`
- Conditionals: `{% if condition %} ... {% endif %}`
- Loops: `{% for item in items %} ... {% endfor %}`
- Filters: `{{ text|upper }}`, `{{ date|format_date }}`
- Comments: `{# This is a comment #}`

### Placeholder Validation

Before rendering, the shard validates:

1. All required placeholders are provided
2. Data types match expected types
3. Default values are applied where needed
4. Warnings for unused placeholders

### Version Control Strategy

- **Immutable versions**: Once created, versions cannot be modified
- **Automatic versioning**: Every template update creates a new version
- **Restore creates new version**: Restoring doesn't delete newer versions
- **Metadata tracking**: Who, when, and why for each version

## Security Considerations

### Template Injection Prevention

- Jinja2 auto-escaping enabled by default
- Restricted function access in templates
- No arbitrary code execution
- Validation of placeholder names (alphanumeric + underscore only)

### Access Control

Templates shard provides CRUD operations but doesn't implement authentication. Authentication should be handled by:

- ArkhamFrame middleware
- API gateway
- Shard-level authorization decorators

## Future Enhancements

Potential future features:

- [ ] Template categories and tags
- [ ] Template inheritance (base templates)
- [ ] Template testing framework
- [ ] Visual template editor
- [ ] Template marketplace/sharing
- [ ] Conditional rendering rules
- [ ] Template approval workflows
- [ ] Scheduled template rendering
- [ ] Template analytics (render counts, success rates)

## License

Part of the SHATTERED project. See project root for license information.

## Contributing

This shard follows the SHATTERED shard development standards. See `CLAUDE.md` in the project root for guidelines.

## Related Shards

- **reports**: Uses templates for report generation
- **letters**: Uses templates for letter generation
- **export**: Uses templates for custom export formats
- **settings**: Manages template-related user preferences
