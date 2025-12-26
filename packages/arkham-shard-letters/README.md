# Letters Shard

**Version:** 0.1.0
**Category:** Export
**Frame Requirement:** >=0.1.0

Letter generation shard for ArkhamFrame. Create formal letters from templates including FOIA requests, complaints, legal correspondence, and custom documents.

## Overview

The Letters shard is a document generation component that:

1. **Generates Letters** - Creates formal letters from templates
2. **Manages Templates** - Provides reusable letter templates with placeholders
3. **Exports Formats** - Supports multiple output formats (PDF, DOCX, HTML, Markdown, TXT)
4. **Draft Workflow** - Manages letter lifecycle from draft to finalized to sent
5. **Placeholder Substitution** - Replaces template placeholders with actual data

## Key Features

### Letter Types
- **FOIA** - Freedom of Information Act requests
- **Complaint** - Formal complaints to organizations
- **Demand** - Demand letters for legal matters
- **Notice** - Notice letters (intent, termination, etc.)
- **Cover** - Cover letters for submissions
- **Inquiry** - Information inquiry letters
- **Response** - Response letters
- **Custom** - Custom letter types

### Letter Status
- `draft` - Work in progress, can be edited
- `review` - Ready for review
- `finalized` - Finalized, ready to send
- `sent` - Marked as sent

### Export Formats
- **PDF** - PDF document (portable, print-ready)
- **DOCX** - Microsoft Word document (editable)
- **HTML** - HTML format (web-viewable)
- **Markdown** - Markdown format (portable text)
- **TXT** - Plain text (universal compatibility)

### Template Features
- Placeholder variables with `{{variable}}` syntax
- Subject line templates
- Default sender information
- Required vs optional placeholders
- Automatic placeholder extraction

## Dependencies

### Required Frame Services
- **database** - Stores letters, templates, and metadata
- **events** - Publishes letter lifecycle events

### Optional Frame Services
- **llm** - Enables AI-assisted letter generation and editing
- **storage** - Stores generated letter files

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
| `letters.template.applied` | Template applied to create letter |
| `letters.template.updated` | Template updated |

### Subscribed Events

The Letters shard does not subscribe to external events. Letters are created via API calls or template application.

## API Endpoints

### Letters CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/` | List letters with pagination |
| GET | `/api/letters/{id}` | Get letter details |
| POST | `/api/letters/` | Create new letter |
| PUT | `/api/letters/{id}` | Update letter |
| DELETE | `/api/letters/{id}` | Delete letter |

### Letter Status Views

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/drafts` | List draft letters |
| GET | `/api/letters/finalized` | List finalized letters |
| GET | `/api/letters/sent` | List sent letters |

### Letter Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/letters/{id}/export` | Export letter to format |
| GET | `/api/letters/{id}/download` | Download exported file |

### Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/templates` | List templates |
| GET | `/api/letters/templates/{id}` | Get template details |
| POST | `/api/letters/templates` | Create template |
| PUT | `/api/letters/templates/{id}` | Update template |
| DELETE | `/api/letters/templates/{id}` | Delete template |

### Template Application

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/letters/apply-template` | Create letter from template |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/letters/count` | Total letter count |
| GET | `/api/letters/stats` | Letter statistics |

## Data Models

### Letter
```python
@dataclass
class Letter:
    id: str
    title: str                      # Letter title
    letter_type: LetterType         # foia, complaint, demand, etc.
    status: LetterStatus            # draft, review, finalized, sent
    content: str                    # Letter body content
    template_id: Optional[str]      # Template used (if any)

    # Recipients and sender
    recipient_name: Optional[str]
    recipient_address: Optional[str]
    recipient_email: Optional[str]
    sender_name: Optional[str]
    sender_address: Optional[str]
    sender_email: Optional[str]

    # Subject and reference
    subject: Optional[str]
    reference_number: Optional[str]
    re_line: Optional[str]          # RE: line for legal letters

    # Timestamps
    created_at: datetime
    updated_at: datetime
    finalized_at: Optional[datetime]
    sent_at: Optional[datetime]

    # Export tracking
    last_export_format: Optional[ExportFormat]
    last_export_path: Optional[str]
    last_exported_at: Optional[datetime]

    metadata: Dict[str, Any]
```

### LetterTemplate
```python
@dataclass
class LetterTemplate:
    id: str
    name: str
    letter_type: LetterType
    description: str

    # Template content
    content_template: str           # Template with {{placeholders}}
    subject_template: Optional[str] # Subject line template

    # Placeholders
    placeholders: List[str]         # Available placeholders
    required_placeholders: List[str] # Must be filled

    # Default values
    default_sender_name: Optional[str]
    default_sender_address: Optional[str]
    default_sender_email: Optional[str]

    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
```

### PlaceholderValue
```python
@dataclass
class PlaceholderValue:
    key: str                        # Placeholder key (without {{ }})
    value: str                      # Value to substitute
    required: bool = False          # Is this placeholder required?
```

## Database Schema

The shard uses tables `arkham_letters` and `arkham_letter_templates`:

```sql
CREATE TABLE arkham_letters (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    letter_type TEXT NOT NULL,
    status TEXT DEFAULT 'draft',

    content TEXT DEFAULT '',
    template_id TEXT,

    recipient_name TEXT,
    recipient_address TEXT,
    recipient_email TEXT,
    sender_name TEXT,
    sender_address TEXT,
    sender_email TEXT,

    subject TEXT,
    reference_number TEXT,
    re_line TEXT,

    created_at TEXT,
    updated_at TEXT,
    finalized_at TEXT,
    sent_at TEXT,

    last_export_format TEXT,
    last_export_path TEXT,
    last_exported_at TEXT,

    metadata TEXT DEFAULT '{}'
);

CREATE TABLE arkham_letter_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    letter_type TEXT NOT NULL,
    description TEXT,

    content_template TEXT NOT NULL,
    subject_template TEXT,

    placeholders TEXT DEFAULT '[]',
    required_placeholders TEXT DEFAULT '[]',

    default_sender_name TEXT,
    default_sender_address TEXT,
    default_sender_email TEXT,

    created_at TEXT,
    updated_at TEXT,
    metadata TEXT DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_letters_status ON arkham_letters(status);
CREATE INDEX idx_letters_type ON arkham_letters(letter_type);
CREATE INDEX idx_letters_created ON arkham_letters(created_at);
CREATE INDEX idx_letters_template ON arkham_letters(template_id);
CREATE INDEX idx_templates_type ON arkham_letter_templates(letter_type);
```

## Installation

```bash
cd packages/arkham-shard-letters
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on startup.

## Use Cases

### Investigative Journalism
- Generate FOIA requests to government agencies
- Create inquiry letters to sources
- Draft complaint letters about public records access
- Document correspondence for investigations

### Legal Self-Advocacy
- Generate demand letters for disputes
- Create notice letters (intent, termination)
- Draft response letters to legal notices
- Maintain correspondence records

**IMPORTANT:** This tool generates document templates only. It does NOT provide legal advice. Consult an attorney for legal matters.

### Academic Research
- Generate inquiry letters to institutions
- Create data access requests
- Draft permission letters for research
- Maintain research correspondence

### Activist Organizing
- Generate complaint letters to officials
- Create notice letters for campaigns
- Draft response letters to government
- Coordinate correspondence campaigns

## Template Examples

### FOIA Request Template

```
{{agency_name}}
FOIA Officer
{{agency_address}}

RE: Freedom of Information Act Request

Dear FOIA Officer:

Pursuant to the Freedom of Information Act, 5 U.S.C. § 552, I request access to and copies of {{document_description}}.

{{time_frame}}

{{fee_waiver_request}}

I request that this information be provided in electronic format if possible.

If you deny all or any part of this request, please cite each specific exemption you think justifies your refusal to release the information and notify me of appeal procedures.

Thank you for your consideration.

Sincerely,
{{requester_name}}
```

### Complaint Letter Template

```
{{recipient_name}}
{{recipient_title}}
{{organization_name}}
{{organization_address}}

RE: Complaint Regarding {{complaint_subject}}

Dear {{recipient_name}}:

I am writing to file a formal complaint regarding {{complaint_description}}.

On {{incident_date}}, {{incident_details}}.

This matter is concerning because {{impact_statement}}.

I request that {{requested_action}}.

Please respond to this complaint within {{response_timeframe}} days.

Sincerely,
{{complainant_name}}
```

## Workflow Example

### Creating a Letter from Template

1. **Create Template** (one-time setup):
```python
POST /api/letters/templates
{
  "name": "FOIA Request Template",
  "letter_type": "foia",
  "description": "Standard FOIA request",
  "content_template": "Dear FOIA Officer:\n\nI request {{document_description}}...",
  "subject_template": "FOIA Request - {{case_number}}"
}
```

2. **Apply Template** (create letter):
```python
POST /api/letters/apply-template
{
  "template_id": "template-123",
  "title": "FOIA Request - City Police Records",
  "placeholder_values": [
    {"key": "document_description", "value": "all incident reports from 2024"},
    {"key": "case_number", "value": "2024-001"}
  ],
  "recipient_name": "City Police Department"
}
```

3. **Review and Edit** (update content):
```python
PUT /api/letters/{letter_id}
{
  "content": "Updated letter content...",
  "status": "review"
}
```

4. **Finalize** (mark ready):
```python
PUT /api/letters/{letter_id}
{
  "status": "finalized"
}
```

5. **Export** (generate file):
```python
POST /api/letters/{letter_id}/export
{
  "export_format": "pdf"
}
```

6. **Download** (get file):
```python
GET /api/letters/{letter_id}/download
```

## Integration with Other Shards

### Documents Shard
- Letters can reference document IDs in metadata
- Export letters as documents for archival
- Link correspondence to evidence documents

### Timeline Shard
- Track letter send dates on timeline
- Visualize correspondence chronology
- Connect letters to events

### Entities Shard
- Link letters to entity profiles (recipients, senders)
- Track correspondence with specific entities
- Generate entity-based letter reports

### Reports Shard
- Include letters in analytical reports
- Generate correspondence summaries
- Track letter statistics

## Configuration

The shard respects these Frame configurations:

```yaml
# In frame config
letters:
  default_export_format: pdf          # Default export format
  enable_llm_assistance: true         # Enable AI-powered drafting
  max_template_placeholders: 50       # Limit placeholders per template
  export_directory: "./letters"       # Letter export location
  auto_finalize: false                # Auto-finalize on export
```

## Best Practices

### Template Design
- Use clear, descriptive placeholder names (`{{recipient_name}}` not `{{x}}`)
- Include all required elements (date, salutation, closing)
- Test templates with sample data before deployment
- Document placeholder requirements in template description

### Letter Management
- Use descriptive titles that identify purpose and recipient
- Update status as letters progress through workflow
- Add metadata for tracking (case numbers, reference IDs)
- Export finalized letters for record-keeping

### Legal Considerations
- **This tool does NOT provide legal advice**
- Review all letters with qualified professionals
- Verify compliance with applicable laws and regulations
- Maintain proper records of all correspondence
- Do not use for unauthorized practice of law

### Security & Privacy
- Redact sensitive information before export
- Use appropriate access controls
- Encrypt exported files when storing
- Follow data retention policies

## License

Part of the SHATTERED architecture, licensed under MIT.
