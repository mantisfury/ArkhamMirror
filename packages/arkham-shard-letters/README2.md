# arkham-shard-letters

> Formal letter generation from templates (FOIA requests, complaints, legal correspondence)

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

## Overview

The Letters shard generates formal letters from templates, including FOIA requests, complaints, legal correspondence, and custom documents. It supports template-based letter creation, placeholder substitution, draft management, and export to multiple formats.

### Key Capabilities

1. **Letter Generation** - Create formal letters
2. **Template Rendering** - Apply templates to data
3. **Document Export** - Export to PDF, DOCX, HTML
4. **Draft Management** - Manage letter drafts
5. **Placeholder Substitution** - Replace placeholders with data

## Features

### Letter Types
- `foia` - Freedom of Information Act requests
- `complaint` - Formal complaints
- `legal` - Legal correspondence
- `notification` - Official notifications
- `request` - General requests
- `custom` - Custom letter types

### Letter Status
- `draft` - Work in progress
- `finalized` - Ready to send
- `sent` - Sent to recipient

### Export Formats
- `pdf` - PDF document
- `docx` - Microsoft Word
- `html` - HTML format
- `txt` - Plain text

### Template System
- Pre-built letter templates
- Custom template creation
- Placeholder variables
- Shared template library
- Template versioning

### Placeholder Variables
Standard placeholders for letter templates:
- `{{sender.name}}`, `{{sender.address}}`
- `{{recipient.name}}`, `{{recipient.organization}}`
- `{{date}}`, `{{reference_number}}`
- `{{subject}}`, `{{body}}`

## Installation

```bash
pip install -e packages/arkham-shard-letters
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Count

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/health` | Health check |
| GET | `/api/letters/count` | Letter count (badge) |

### Letter CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/` | List letters |
| POST | `/api/letters/` | Create letter |
| GET | `/api/letters/{id}` | Get letter |
| PUT | `/api/letters/{id}` | Update letter |
| DELETE | `/api/letters/{id}` | Delete letter |
| POST | `/api/letters/{id}/export` | Export letter |
| GET | `/api/letters/{id}/download` | Download letter |

### Status Filtered

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/drafts` | List draft letters |
| GET | `/api/letters/finalized` | List finalized letters |
| GET | `/api/letters/sent` | List sent letters |

### Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/templates` | List templates |
| POST | `/api/letters/templates` | Create template |
| GET | `/api/letters/templates/{id}` | Get template |
| PUT | `/api/letters/templates/{id}` | Update template |
| DELETE | `/api/letters/templates/{id}` | Delete template |
| GET | `/api/letters/templates/shared` | List shared templates |
| GET | `/api/letters/templates/shared/{id}` | Get shared template |
| POST | `/api/letters/from-shared-template` | Create from shared |
| POST | `/api/letters/apply-template` | Apply template |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/stats` | Letter statistics |

## API Examples

### Create Letter

```json
POST /api/letters/
{
  "letter_type": "foia",
  "subject": "FOIA Request - Public Records",
  "recipient": {
    "name": "Records Department",
    "organization": "City Hall",
    "address": "123 Main St, City, ST 12345"
  },
  "sender": {
    "name": "John Smith",
    "organization": "Research Inc",
    "address": "456 Oak Ave, Town, ST 67890"
  },
  "body": "Dear Records Department,\n\nPursuant to the Freedom of Information Act..."
}
```

### Create from Template

```json
POST /api/letters/from-shared-template
{
  "template_id": "tpl_foia_standard",
  "data": {
    "recipient_name": "Records Department",
    "recipient_organization": "City Hall",
    "request_details": "All documents related to...",
    "date_range": "January 2024 - December 2024"
  }
}
```

### Apply Template to Existing Letter

```json
POST /api/letters/apply-template
{
  "letter_id": "ltr_abc123",
  "template_id": "tpl_foia_standard",
  "merge_mode": "replace"
}
```

### Export Letter

```json
POST /api/letters/{letter_id}/export
{
  "format": "pdf",
  "include_letterhead": true,
  "include_signature": true
}
```

### Get Statistics

```bash
GET /api/letters/stats
```

Response:
```json
{
  "total_letters": 150,
  "by_status": {
    "draft": 20,
    "finalized": 100,
    "sent": 30
  },
  "by_type": {
    "foia": 80,
    "complaint": 30,
    "legal": 25,
    "custom": 15
  },
  "templates_count": 12,
  "avg_letters_per_day": 3.5
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `letters.letter.created` | New letter created |
| `letters.letter.updated` | Letter content updated |
| `letters.letter.finalized` | Letter marked as finalized |
| `letters.letter.sent` | Letter marked as sent |
| `letters.letter.exported` | Letter exported to file |
| `letters.template.created` | New template created |
| `letters.template.applied` | Template applied to letter |
| `letters.template.updated` | Template updated |

### Subscribed Events

No subscribed events - triggered by API calls.

## UI Routes

| Route | Description |
|-------|-------------|
| `/letters` | All letters |
| `/letters/drafts` | Draft letters |
| `/letters/finalized` | Finalized letters |
| `/letters/templates` | Template management |

## Dependencies

### Required Services
- **database** - Letter and template storage
- **events** - Event publishing

### Optional Services
- **storage** - File storage for exports
- **llm** - AI-assisted letter generation

## URL State

| Parameter | Description |
|-----------|-------------|
| `letterId` | Selected letter |
| `templateId` | Selected template |
| `status` | Filter by status |
| `letterType` | Filter by letter type |

### Local Storage Keys
- `editor_mode` - Visual vs raw editor mode
- `show_placeholders` - Show placeholder hints
- `auto_save` - Auto-save draft changes

## Development

```bash
# Run tests
pytest packages/arkham-shard-letters/tests/

# Type checking
mypy packages/arkham-shard-letters/
```

## License

MIT
