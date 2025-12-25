# Shard Manifest Schema v4.1

> Canonical schema for `shard.yaml` files

---

## Quick Reference

```yaml
# === REQUIRED ===
name: string              # lowercase, alphanumeric + hyphens
version: string           # semver (MAJOR.MINOR.PATCH)
description: string       # 1-2 sentences
entry_point: string       # module.path:ClassName
api_prefix: string        # /api/{name}
requires_frame: string    # semver constraint (>=, ^, ~)

navigation:
  category: string        # System|Data|Search|Analysis|Visualize|Export
  order: integer          # 0-99 (lower = higher in list)
  icon: string            # Lucide icon (PascalCase)
  label: string           # Display name
  route: string           # /path (must be unique)
  badge_endpoint: string  # optional: returns {count: N}
  badge_type: string      # optional: count|dot
  sub_routes: []          # optional: {id, label, route, icon, badge_endpoint?, badge_type?}

# === OPTIONAL ===
dependencies:
  services: []            # database|vectors|events|llm|workers
  optional: []            # same, but not required
  shards: []              # other shard names

capabilities: []          # lowercase_underscored feature names

events:
  publishes: []           # shard.action.status format
  subscribes: []

state:
  strategy: string        # url|local|session|none
  url_params: []          # NON-FILTER params only (matrixId, tab, view)
  local_keys: []          # localStorage keys (auto-prefixed with shard name)

ui:                       # see UI Configuration section
  has_custom_ui: boolean
  # ... see below
```

---

## Categories & Order Ranges

| Category | Range | Description |
|----------|-------|-------------|
| System | 0-9 | Infrastructure, monitoring |
| Data | 10-19 | Document management, ingestion |
| Search | 20-29 | Search and discovery |
| Analysis | 30-39 | Analytical tools |
| Visualize | 40-49 | Visualization tools |
| Export | 50-59 | Data export |

---

## State Strategy

| Strategy | Shareable | Persists | Use Case |
|----------|-----------|----------|----------|
| `url` | YES | Via bookmark | Shareable views, filters, IDs |
| `local` | NO | Across sessions | UI preferences |
| `session` | NO | Until tab closes | Unsaved form data |
| `none` | N/A | N/A | Stateless |

**v4 Change**: Filter params from `list_filters` are auto-inferred as URL params. Only declare non-filter params in `state.url_params`.

---

## UI Configuration

### When `has_custom_ui: false`

Shell renders generic UI from manifest. Full config:

```yaml
ui:
  has_custom_ui: false
  id_field: id              # default: "id"
  selectable: true          # default: true if bulk_actions defined
  list_endpoint: /api/shard/items
  detail_endpoint: /api/shard/item/{id}

  list_filters: []          # see Filter Types
  list_columns: []          # see Column Types
  bulk_actions: []          # see Action Config
  row_actions: []           # see Action Config
  primary_action: {}        # see Form Config
  actions: []               # additional page actions
```

### When `has_custom_ui: true`

Shell provides layout only. Shard provides all React components.

```yaml
ui:
  has_custom_ui: true
  # No other UI config needed
```

---

## Filter Types

All filter params are **auto-managed as URL params** by Shell.

| Type | Params | Renders |
|------|--------|---------|
| `search` | `param` | Search input with icon |
| `select` | `param`, `options[]` | Dropdown |
| `multi_select` | `param` (comma-sep) | Multi-select dropdown |
| `boolean` | `param` | Checkbox |
| `date` | `param` | Date picker |
| `date_range` | `param_start`, `param_end` | Two date pickers |
| `number_range` | `param_min`, `param_max` | Two number inputs |

```yaml
list_filters:
  - name: search
    type: search
    label: Search...
    param: q

  - name: status
    type: select
    label: Status
    param: status
    options:
      - { value: "", label: All }
      - { value: pending, label: Pending }
      - { value: done, label: Done }

  - name: archived
    type: boolean
    label: Show archived
    param: archived

  - name: dates
    type: date_range
    label: Date range
    param_start: from
    param_end: to
```

---

## Column Types

| Type | Properties | Renders |
|------|------------|---------|
| `text` | `sortable` | Plain text |
| `link` | `link_route`, `sortable` | Clickable link (`{id}` substitution) |
| `number` | `format`, `sortable` | Formatted number |
| `date` | `format`, `sortable` | Formatted date |
| `badge` | `sortable` | Colored badge (auto-maps value) |
| `boolean` | `sortable` | Check/X icon |

**Format options**: `integer`, `decimal`, `percent` (number); `absolute`, `relative` (date)

```yaml
list_columns:
  - field: title
    label: Document
    type: link
    link_route: /document/{id}
    width: 40%
    sortable: true

  - field: status
    label: Status
    type: badge
    width: 15%
    sortable: true

  - field: created_at
    label: Created
    type: date
    format: relative
    width: 20%
    sortable: true
    default_sort: desc
```

---

## Actions

### Bulk Actions

Apply to selected rows. Receives `{ids: [...]}`, returns standardized response.

```yaml
bulk_actions:
  - label: Delete
    endpoint: /api/shard/batch/delete
    method: DELETE
    confirm: true
    confirm_message: Delete {count} items?
    style: danger         # default|primary|danger
    icon: Trash2
```

### Row Actions

Per-row. Type `link` navigates, `api` calls endpoint.

```yaml
row_actions:
  - label: View
    type: link
    route: /shard/{id}
    icon: Eye

  - label: Delete
    type: api
    endpoint: /api/shard/{id}
    method: DELETE
    confirm: true
    confirm_message: Delete this item?
    style: danger
    icon: Trash2
```

### Primary Action (Form)

```yaml
primary_action:
  label: Create Item
  endpoint: /api/shard/create
  method: POST
  description: Optional description
  fields:
    - name: title
      type: text
      label: Title
      required: true

    - name: email
      type: text
      label: Email
      required: false
      pattern: "^\\S+@\\S+\\.\\S+$"
      error_message: Invalid email

    - name: model
      type: select
      label: Model
      default: option1
      options:
        - { value: option1, label: Option 1 }
        - { value: option2, label: Option 2 }
```

**Field types**: `text`, `textarea`, `number`, `email`, `select`

**Validation (v4)**: `pattern` (JS regex), `error_message`, `required`, `min`, `max`

---

## API Contracts

### List Endpoint

**Must accept**: `?page=N&page_size=M&sort=field&order=asc|desc` + filter params

**Must return**:
```json
{ "items": [...], "total": 100, "page": 1, "page_size": 20 }
```

**URL format**: `/shard?q=search&status=pending&page=2` (flat params, NOT JSON)

### Bulk Action Endpoint

**Receives**: `{ "ids": ["id1", "id2"] }`

**Returns**:
```json
{
  "success": true,
  "processed": 2,
  "failed": 0,
  "errors": [],
  "message": "2 items processed"
}
```

### Badge Endpoint

**Returns**: `{ "count": 5 }`

---

## Theme CSS Variables

Shell injects these at `:root`. Shards can use or ignore.

```css
/* Colors */
--arkham-bg-primary: #1a1a2e;
--arkham-bg-secondary: #16213e;
--arkham-bg-tertiary: #0f3460;
--arkham-text-primary: #eaeaea;
--arkham-text-secondary: #a0a0a0;
--arkham-text-muted: #6b6b6b;
--arkham-accent-primary: #e94560;
--arkham-accent-secondary: #533483;
--arkham-border: #2a2a4a;
--arkham-success: #4ade80;
--arkham-warning: #fbbf24;
--arkham-error: #f87171;

/* Spacing */
--arkham-space-xs: 4px;
--arkham-space-sm: 8px;
--arkham-space-md: 16px;
--arkham-space-lg: 24px;
--arkham-space-xl: 32px;

/* Typography */
--arkham-font-mono: 'JetBrains Mono', monospace;
--arkham-font-sans: 'Inter', sans-serif;
--arkham-font-size-sm: 12px;
--arkham-font-size-md: 14px;
--arkham-font-size-lg: 16px;

/* Effects */
--arkham-shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
--arkham-shadow-md: 0 4px 6px rgba(0,0,0,0.4);
--arkham-radius-sm: 4px;
--arkham-radius-md: 8px;
```

---

## Common Validation Patterns

```yaml
# Email
pattern: "^\\S+@\\S+\\.\\S+$"

# URL
pattern: "^https?://\\S+$"

# UUID
pattern: "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# Alphanumeric ID
pattern: "^[a-zA-Z0-9_-]+$"
```

Note: Backslashes must be escaped in YAML (`\\S` not `\S`).

---

## Complete Examples

### Generic UI Shard

```yaml
name: embed
version: 0.1.0
description: Document embedding management
entry_point: arkham_shard_embed:EmbedShard
api_prefix: /api/embed
requires_frame: ">=0.1.0"

navigation:
  category: Search
  order: 21
  icon: Binary
  label: Embeddings
  route: /embed
  badge_endpoint: /api/embed/pending/count

dependencies:
  services: [database, vectors]
  optional: [documents]

capabilities: [generate_embeddings, batch_embed, similarity_search]

events:
  publishes: [embeddings.created, embeddings.batch.completed]
  subscribes: [documents.parsed]

state:
  strategy: url
  local_keys: [embed_columns_visible]

ui:
  has_custom_ui: false
  list_endpoint: /api/embed/documents

  list_filters:
    - { name: search, type: search, label: Search..., param: q }
    - name: status
      type: select
      label: Status
      param: status
      options:
        - { value: "", label: All }
        - { value: pending, label: Pending }
        - { value: embedded, label: Embedded }

  list_columns:
    - { field: title, label: Document, type: link, link_route: /document/{id}, width: 45%, sortable: true }
    - { field: status, label: Status, type: badge, width: 15%, sortable: true }
    - { field: chunk_count, label: Chunks, type: number, width: 10%, sortable: true }
    - { field: embedded_at, label: Embedded, type: date, format: relative, width: 20%, sortable: true, default_sort: desc }

  bulk_actions:
    - { label: Delete, endpoint: /api/embed/batch/delete, method: DELETE, confirm: true, style: danger, icon: Trash2 }
    - { label: Re-embed, endpoint: /api/embed/batch/reprocess, method: POST, style: primary, icon: RefreshCw }

  row_actions:
    - { label: View, type: link, route: /embed/{id}, icon: Eye }
    - { label: Delete, type: api, endpoint: /api/embed/{id}, method: DELETE, confirm: true, style: danger, icon: Trash2 }

  primary_action:
    label: Embed Document
    endpoint: /api/embed/generate
    method: POST
    fields:
      - { name: document_id, type: text, label: Document ID, required: true, pattern: "^[a-zA-Z0-9_-]+$" }
      - { name: model, type: select, label: Model, default: bge-m3, options: [{ value: bge-m3, label: BGE-M3 }, { value: minilm, label: MiniLM }] }
```

### Custom UI Shard

```yaml
name: ach
version: 0.1.0
description: Analysis of Competing Hypotheses
entry_point: arkham_shard_ach:ACHShard
api_prefix: /api/ach
requires_frame: ">=0.1.0"

navigation:
  category: Analysis
  order: 30
  icon: Scale
  label: ACH Analysis
  route: /ach
  badge_endpoint: /api/ach/matrices/unreviewed/count
  sub_routes:
    - { id: matrices, label: All Matrices, route: /ach/matrices, icon: List }
    - { id: new, label: New Analysis, route: /ach/new, icon: Plus }

dependencies:
  services: [database, events]
  optional: [llm]

capabilities: [hypothesis_management, evidence_management, consistency_scoring, devils_advocate]

events:
  publishes: [ach.matrix.created, ach.matrix.updated, ach.hypothesis.added, ach.evidence.added]
  subscribes: [llm.analysis.completed]

state:
  strategy: url
  url_params: [matrixId, hypothesisId, tab, view]  # Non-filter params
  local_keys: [ach_matrix_zoom, ach_show_tooltips]

ui:
  has_custom_ui: true
```

---

## Validation Checklist

Required before shard loads:

- [ ] `name`: lowercase, alphanumeric + hyphens
- [ ] `version`: valid semver
- [ ] `entry_point`: valid Python path
- [ ] `api_prefix`: starts with `/api/`
- [ ] `requires_frame`: valid semver constraint
- [ ] `navigation.route`: starts with `/`, unique across shards
- [ ] `navigation.category`: valid category name
- [ ] `navigation.order`: 0-99
- [ ] `navigation.icon`: valid Lucide icon

Frame validates route/api_prefix uniqueness on startup.

---

## Migration from v3

```diff
 state:
   url_params:
-    - q           # Remove - auto-inferred from list_filters
-    - status      # Remove - auto-inferred
-    - page        # Remove - always auto-managed
     - matrixId    # Keep - not a filter
     - tab         # Keep - not a filter

 fields:
   - name: email
     type: text
+    pattern: "^\\S+@\\S+\\.\\S+$"
+    error_message: Invalid email
```

---

## Changes from v3

| Change | Rationale |
|--------|-----------|
| Auto-inferred filter URL params | No redundancy - Shell manages filter params |
| Added `pattern` field validation | Regex validation for text fields |
| Added `error_message` | Custom validation messages |
| Clarified `state.url_params` scope | Only for non-filter state |

---

*v4.1 - Condensed 2025-12-22*
