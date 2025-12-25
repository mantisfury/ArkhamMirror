# Shard Manifest Schema Specification

> Version 4.0.0 - Canonical schema for `shard.yaml` files

This document defines the required and optional fields for all shard manifest files. All shards in the ArkhamMirror Shattered ecosystem MUST conform to this schema.

---

## Changes from v3.0.0

| Change | Rationale |
|--------|-----------|
| **Auto-inferred URL params from `list_filters`** | Removed redundancy: Shell automatically treats filter params as URL params. No need to declare in `state.url_params`. |
| **Added form field `pattern`** | Regex validation for text fields (email, ID formats, etc.) |
| **Added form field `error_message`** | Custom validation error messages |
| **Clarified `state.url_params` scope** | Now only for non-UI state (matrixId, tab). Filters are auto-inferred. |
| **Added `custom_components` placeholder** | Future: Phase 6 hybrid UI mode |

---

## Quick Reference

```yaml
# REQUIRED
name: string
version: string (semver)
description: string
entry_point: string

# REQUIRED for Frame integration
api_prefix: string
requires_frame: string (semver constraint)

# REQUIRED for UI Shell
navigation:
  category: string
  order: integer
  icon: string
  label: string
  route: string
  badge_endpoint: string (optional)

# OPTIONAL
dependencies: object
capabilities: string[]
events: object
state: object
ui: object
```

---

## Full Schema Definition

### 1. Core Identity (REQUIRED)

```yaml
# Unique shard identifier (lowercase, no spaces)
name: search

# Semantic version
version: 0.1.0

# Human-readable description (1-2 sentences)
description: Semantic and keyword search for documents

# Python entry point (module:class)
entry_point: arkham_shard_search:SearchShard
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | YES | Lowercase, alphanumeric + hyphens only |
| `version` | string | YES | Semantic versioning (MAJOR.MINOR.PATCH) |
| `description` | string | YES | Brief description for UI display |
| `entry_point` | string | YES | Format: `module.path:ClassName` |

### 2. Frame Integration (REQUIRED)

```yaml
# API route prefix (must start with /api/)
api_prefix: /api/search

# Minimum Frame version required
requires_frame: ">=0.1.0"
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `api_prefix` | string | YES | Always starts with `/api/` |
| `requires_frame` | string | YES | Semver constraint (>=, ^, ~) |

**Route Collision Validation**: The Frame validates that no two shards claim the same route on startup. If a collision is detected, the Frame will fail to start with a clear error message identifying both shards and the conflicting route.

**Note**: `navigation.route` (e.g., `/search`) and `api_prefix` (e.g., `/api/search`) are different namespaces. A shard having route `/search` and api_prefix `/api/search` is valid and expected.

### 3. Navigation (REQUIRED for UI)

**Every shard MUST define navigation** to appear in the Shell sidebar.

```yaml
navigation:
  # Sidebar category grouping
  category: Analysis

  # Sort order within category (lower = higher)
  order: 30

  # Lucide icon name (see https://lucide.dev/icons)
  icon: Scale

  # Display label in sidebar
  label: ACH Analysis

  # Primary route path
  route: /ach

  # Optional: Dynamic badge indicator
  badge_endpoint: /api/ach/unreviewed/count
  badge_type: count  # count | dot

  # Optional: Sub-navigation items
  sub_routes:
    - id: matrices
      label: All Matrices
      route: /ach/matrices
      icon: List

    - id: pending
      label: Pending Review
      route: /ach/pending
      icon: Clock
      badge_endpoint: /api/ach/pending/count
      badge_type: count
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `navigation.category` | string | YES | See Category Definitions below |
| `navigation.order` | integer | YES | 0-99, determines sort within category |
| `navigation.icon` | string | YES | Lucide icon name (PascalCase) |
| `navigation.label` | string | YES | Human-readable label |
| `navigation.route` | string | YES | Primary route path (must be unique) |
| `navigation.badge_endpoint` | string | NO | Endpoint returning `{count: number}` |
| `navigation.badge_type` | string | NO | `count` (show number) or `dot` (show indicator) |
| `navigation.sub_routes` | array | NO | Additional navigation items |
| `navigation.sub_routes[].badge_endpoint` | string | NO | Badge endpoint for sub-route |
| `navigation.sub_routes[].badge_type` | string | NO | Badge type for sub-route |

#### Badge Endpoint Contract

When `badge_endpoint` is specified, the endpoint MUST return:

```json
{
  "count": 5
}
```

**Note**: In v4, the Shell polls a single Frame aggregation endpoint (`/api/frame/badges`) which returns all badge counts. The Frame handles querying individual shards.

#### Category Definitions

Standard categories (use these for consistency):

| Category | Order Range | Description |
|----------|-------------|-------------|
| System | 0-9 | Infrastructure, monitoring |
| Data | 10-19 | Document management, ingestion |
| Search | 20-29 | Search and discovery |
| Analysis | 30-39 | Analytical tools |
| Visualize | 40-49 | Visualization tools |
| Export | 50-59 | Data export |

### 4. State Management (OPTIONAL) - SIMPLIFIED in v4

Defines how the shard persists state across navigation and sessions.

**IMPORTANT v4 CHANGE**: You no longer need to declare filter params in `state.url_params`. The Shell automatically infers URL params from `ui.list_filters`. Only declare params here that are NOT part of the filter UI.

```yaml
state:
  # How state is persisted
  strategy: url  # url | local | session | none

  # URL parameters for non-filter state (deep linking)
  # NOTE: Filter params (q, status, etc.) are auto-inferred from list_filters
  url_params:
    - matrixId    # /ach?matrixId=123
    - tab         # /ach?matrixId=123&tab=evidence
    - view        # /ach?view=matrix

  # Keys stored in localStorage (for UI preferences)
  local_keys:
    - ach_collapsed_sections
    - ach_sort_order
    - ach_matrix_zoom
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `state.strategy` | string | NO | Primary persistence: `url`, `local`, `session`, `none` |
| `state.url_params` | string[] | NO | URL query params for non-filter state |
| `state.local_keys` | string[] | NO | localStorage keys (prefixed with shard name) |

#### Auto-Inferred URL Params (NEW in v4)

The Shell automatically creates URL params for:

1. **All `list_filters[].param` values** - Search, select, date filters
2. **Standard list params** - `page`, `sort`, `order`

You do NOT need to declare these in `state.url_params`:

```yaml
# DON'T DO THIS - redundant!
state:
  url_params:
    - q         # Automatically inferred from list_filters
    - status    # Automatically inferred from list_filters
    - page      # Always auto-managed

# DO THIS - only non-filter state
state:
  url_params:
    - matrixId  # Not a filter, needs explicit declaration
    - tab       # Not a filter, needs explicit declaration
```

#### State Strategy Guidelines

| Strategy | Use Case | Shareable | Persists |
|----------|----------|-----------|----------|
| `url` | Shareable views (analysis ID, filters) | YES | Via bookmark |
| `local` | UI preferences (collapsed panels, sort order) | NO | Across sessions |
| `session` | Ephemeral state (unsaved form data) | NO | Until tab closes |
| `none` | No state persistence needed | N/A | N/A |

**Best Practice**: Use `url` for anything a user might want to share or bookmark. Use `local` only for cosmetic preferences.

**Security Note**: Never store sensitive data in URL params or localStorage.

### 5. Dependencies (OPTIONAL)

```yaml
dependencies:
  # Required Frame services
  services:
    - database
    - vectors
    - events

  # Optional services (shard works without them)
  optional:
    - llm
    - documents

  # Other shards this depends on
  shards:
    - embed
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `dependencies.services` | string[] | NO | Frame services: database, vectors, events, llm, workers |
| `dependencies.optional` | string[] | NO | Services that enhance but aren't required |
| `dependencies.shards` | string[] | NO | Other shard dependencies |

### 6. Capabilities (OPTIONAL)

List of features/capabilities this shard provides. Used for:
- Generic UI display
- Feature discovery
- Documentation generation

```yaml
capabilities:
  - semantic_search
  - keyword_search
  - hybrid_search
  - autocomplete
  - similarity_search
```

Capabilities should be:
- Lowercase with underscores
- Descriptive of actual functionality
- Unique within the shard

### 7. Events (OPTIONAL)

Event bus integration for pub/sub communication.

```yaml
events:
  # Events this shard emits
  publishes:
    - search.query.executed
    - search.results.found
    - search.index.updated

  # Events this shard listens to
  subscribes:
    - documents.indexed
    - documents.deleted
    - embeddings.created
```

Event naming convention: `shard.action.status` (e.g., `ach.matrix.created`)

### 8. UI Configuration (OPTIONAL) - ENHANCED in v4

Controls how the Shell renders this shard.

```yaml
ui:
  # Does this shard provide custom React components?
  has_custom_ui: false

  # NOTE: When has_custom_ui: true, the Shell skips ALL generic UI generation.
  # The shard MUST provide its own React components for all routes.
  # Shell only provides the layout (sidebar, topbar, content area) and injects CSS variables.

  # ----- LIST VIEW CONFIGURATION -----

  # List view endpoint (MUST support pagination AND filtering)
  list_endpoint: /api/embed/documents

  # Which field is the unique identifier for each row
  id_field: id  # default: "id"

  # Enable row selection for bulk actions
  selectable: true  # default: true if bulk_actions defined

  # Filters appear above the table
  # NOTE: These params are AUTO-INFERRED as URL params. No need to declare in state.url_params.
  list_filters:
    - name: search
      type: search          # Special type: renders search input with icon
      label: Search documents...
      param: q              # Appended as ?q=value (auto-managed by Shell)

    - name: status
      type: select
      label: Status
      param: status         # Appended as ?status=value (auto-managed by Shell)
      options:
        - value: ""
          label: All
        - value: pending
          label: Pending
        - value: completed
          label: Completed
        - value: failed
          label: Failed

    - name: type
      type: select
      label: File Type
      param: type
      options:
        - value: ""
          label: All Types
        - value: pdf
          label: PDF
        - value: image
          label: Image
        - value: text
          label: Text

    - name: date_range
      type: date_range
      label: Date
      param_start: from_date   # ?from_date=2024-01-01
      param_end: to_date       # ?to_date=2024-12-31

  # Column definitions for list view
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

    - field: chunk_count
      label: Chunks
      type: number
      width: 10%
      sortable: true

    - field: created_at
      label: Created
      type: date
      format: relative
      width: 20%
      sortable: true
      default_sort: desc      # This column is default sort

  # Actions that apply to selected rows
  bulk_actions:
    - label: Delete Selected
      endpoint: /api/embed/batch/delete
      method: DELETE
      confirm: true
      confirm_message: Delete {count} selected items? This cannot be undone.
      style: danger           # default | primary | danger
      icon: Trash2

    - label: Export JSON
      endpoint: /api/embed/batch/export
      method: POST
      style: default
      icon: Download

    - label: Reprocess
      endpoint: /api/embed/batch/reprocess
      method: POST
      style: primary
      icon: RefreshCw

  # Actions that appear for each row (hover menu or action column)
  row_actions:
    - label: View Details
      type: link              # link = navigate, api = call endpoint
      route: /embed/{id}
      icon: Eye

    - label: Edit
      type: link
      route: /embed/{id}/edit
      icon: Pencil

    - label: Reprocess
      type: api
      endpoint: /api/embed/{id}/reprocess
      method: POST
      icon: RefreshCw
      confirm: false

    - label: Delete
      type: api
      endpoint: /api/embed/{id}
      method: DELETE
      icon: Trash2
      confirm: true
      confirm_message: Delete this document?
      style: danger

  # ----- DETAIL VIEW CONFIGURATION -----

  # Detail view endpoint pattern
  detail_endpoint: /api/embed/document/{id}

  # ----- ACTION CONFIGURATION -----

  # Primary action configuration
  primary_action:
    label: Embed Document
    endpoint: /api/embed/generate
    method: POST
    description: Generate embeddings for a document
    fields:
      - name: document_id
        type: text
        label: Document ID
        required: true

      - name: email
        type: text
        label: Notification Email
        required: false
        pattern: "^\\S+@\\S+\\.\\S+$"      # NEW in v4: Regex validation
        error_message: "Must be a valid email address"  # NEW in v4: Custom error

      - name: model
        type: select
        label: Embedding Model
        required: false
        default: bge-m3
        options:
          - value: bge-m3
            label: BGE-M3 (Multilingual)
          - value: minilm
            label: MiniLM (Fast)

  # Additional page-level actions
  actions:
    - label: Rebuild Index
      endpoint: /api/embed/reindex
      method: POST
      confirm: true
      confirm_message: This will rebuild the entire embedding index. Continue?
      description: Rebuild embedding index
      fields: []

  # ----- FUTURE: HYBRID UI MODE (Phase 6) -----

  # custom_components:
  #   - name: ProjectSelector
  #     path: ./components/ProjectSelector  # Relative to shard package
  #     slots:
  #       - primary_action.fields.project
  #       - list_columns.project
```

#### Form Field Validation (NEW in v4)

Form fields now support regex pattern validation:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `pattern` | string | NO | Regex pattern for validation (JavaScript regex syntax) |
| `error_message` | string | NO | Custom error message when pattern fails |

**Common Patterns:**

```yaml
# Email
pattern: "^\\S+@\\S+\\.\\S+$"
error_message: "Must be a valid email address"

# URL
pattern: "^https?://\\S+$"
error_message: "Must be a valid URL starting with http:// or https://"

# UUID
pattern: "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
error_message: "Must be a valid UUID"

# Alphanumeric ID
pattern: "^[a-zA-Z0-9_-]+$"
error_message: "Only letters, numbers, underscores, and hyphens allowed"

# Phone (US)
pattern: "^\\+?1?[-.\\s]?\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}$"
error_message: "Must be a valid US phone number"
```

**Note**: Patterns use JavaScript regex syntax. Backslashes must be escaped in YAML (`\\S` not `\S`).

#### List Endpoint Contract (Updated for v4)

When `list_endpoint` is specified, the endpoint MUST:

1. Accept pagination: `?page=N&page_size=M`
2. Accept filter params as defined in `list_filters`
3. Accept sorting: `?sort=field&order=asc|desc`
4. Return a paginated response:

```json
{
  "items": [...],
  "total": 1000,
  "page": 1,
  "page_size": 20
}
```

**Example Request:**
```
GET /api/embed/documents?page=1&page_size=20&q=report&status=completed&sort=created_at&order=desc
```

**URL Structure in v4:**
The Shell manages filter params as flat URL values, NOT JSON blobs:

```
CORRECT: /embed?q=report&status=pending&page=2
WRONG:   /embed?filters={"q":"report","status":"pending"}
```

#### Bulk Action Endpoint Contract

Bulk action endpoints receive an array of IDs:

```json
{
  "ids": ["id1", "id2", "id3"]
}
```

And MUST return a standardized response:

```json
{
  "success": true,
  "processed": 3,
  "failed": 0,
  "errors": [],
  "message": "3 items deleted successfully"
}
```

**Response Field Contract:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success` | boolean | YES | `true` if ALL items processed successfully |
| `processed` | number | YES | Count of successfully processed items |
| `failed` | number | YES | Count of items that failed |
| `errors` | array | NO | Array of `{id, error}` for failed items |
| `message` | string | YES | Human-readable summary for toast |

**Partial Failure Example:**

```json
{
  "success": false,
  "processed": 2,
  "failed": 1,
  "errors": [
    { "id": "doc-789", "error": "Document is locked" }
  ],
  "message": "2 of 3 items deleted, 1 failed"
}
```

#### Filter Types

| Type | Renders As | Params | Auto URL |
|------|------------|--------|----------|
| `search` | Search input with icon | `param` | YES |
| `select` | Dropdown | `param`, `options` | YES |
| `multi_select` | Multi-select dropdown | `param` (comma-separated) | YES |
| `date_range` | Two date pickers | `param_start`, `param_end` | YES |
| `date` | Single date picker | `param` | YES |
| `boolean` | Toggle/checkbox | `param` | YES |
| `number_range` | Two number inputs | `param_min`, `param_max` | YES |

**Auto URL**: All filter params are automatically managed as URL params by the Shell. You do NOT need to declare them in `state.url_params`.

#### List Column Types

| Type | Renders As | Additional Properties |
|------|------------|----------------------|
| `text` | Plain text | `sortable` |
| `link` | Clickable link | `link_route` with `{id}` placeholder, `sortable` |
| `number` | Formatted number | `format`: `integer`, `decimal`, `percent`, `sortable` |
| `date` | Formatted date | `format`: `absolute`, `relative`, `sortable` |
| `badge` | Colored badge | Maps value to color automatically, `sortable` |
| `boolean` | Check/X icon | `sortable` |
| `actions` | Row action buttons | Used if `row_actions` defined |

#### Row Action Types

| Type | Behavior |
|------|----------|
| `link` | Navigate to `route` (with `{id}` substitution) |
| `api` | Call `endpoint` with `method`, show result toast |

#### Bulk/Row Action Styles

| Style | Appearance |
|-------|------------|
| `default` | Neutral/secondary button |
| `primary` | Highlighted/accent button |
| `danger` | Red/destructive button |

#### Theme CSS Variables

The Shell ALWAYS injects theme CSS variables at `:root`. Shards can use them or ignore them:

```css
/* Shell always provides these variables */
:root {
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
}
```

---

## Complete Examples

### Example 1: Simple Shard with Generic UI (Full Features)

```yaml
name: embed
version: 0.1.0
description: Generate and manage document embeddings
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
  badge_type: count

dependencies:
  services:
    - database
    - vectors
  optional:
    - documents

capabilities:
  - generate_embeddings
  - batch_embed
  - similarity_search
  - vector_operations

events:
  publishes:
    - embeddings.created
    - embeddings.batch.completed
  subscribes:
    - documents.parsed

state:
  strategy: url
  # NOTE: q, status, page, sort, order are auto-inferred from list_filters
  # Only need to declare non-filter URL params here (none in this case)
  local_keys:
    - embed_columns_visible

ui:
  has_custom_ui: false
  id_field: id
  selectable: true

  list_endpoint: /api/embed/documents

  # All these params are auto-managed in URL by Shell
  list_filters:
    - name: search
      type: search
      label: Search documents...
      param: q

    - name: status
      type: select
      label: Status
      param: status
      options:
        - value: ""
          label: All
        - value: pending
          label: Pending
        - value: embedded
          label: Embedded
        - value: failed
          label: Failed

  list_columns:
    - field: title
      label: Document
      type: link
      link_route: /document/{id}
      width: 45%
      sortable: true

    - field: status
      label: Status
      type: badge
      width: 15%
      sortable: true

    - field: chunk_count
      label: Chunks
      type: number
      width: 10%
      sortable: true

    - field: embedded_at
      label: Embedded
      type: date
      format: relative
      width: 20%
      sortable: true
      default_sort: desc

  bulk_actions:
    - label: Delete
      endpoint: /api/embed/batch/delete
      method: DELETE
      confirm: true
      confirm_message: Delete {count} documents and their embeddings?
      style: danger
      icon: Trash2

    - label: Re-embed
      endpoint: /api/embed/batch/reprocess
      method: POST
      style: primary
      icon: RefreshCw

  row_actions:
    - label: View
      type: link
      route: /embed/{id}
      icon: Eye

    - label: Re-embed
      type: api
      endpoint: /api/embed/{id}/reprocess
      method: POST
      icon: RefreshCw

    - label: Delete
      type: api
      endpoint: /api/embed/{id}
      method: DELETE
      confirm: true
      confirm_message: Delete this document and its embeddings?
      style: danger
      icon: Trash2

  detail_endpoint: /api/embed/document/{id}

  primary_action:
    label: Embed Document
    endpoint: /api/embed/generate
    method: POST
    description: Generate embeddings for a document
    fields:
      - name: document_id
        type: text
        label: Document ID
        required: true
        pattern: "^[a-zA-Z0-9_-]+$"
        error_message: "Document ID must be alphanumeric with underscores/hyphens only"

      - name: notification_email
        type: text
        label: Notification Email (optional)
        required: false
        pattern: "^\\S+@\\S+\\.\\S+$"
        error_message: "Must be a valid email address"

      - name: model
        type: select
        label: Model
        default: bge-m3
        options:
          - value: bge-m3
            label: BGE-M3
          - value: minilm
            label: MiniLM
```

### Example 2: Complex Shard with Custom UI

```yaml
name: ach
version: 0.1.0
description: Analysis of Competing Hypotheses matrix for intelligence analysis
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
  badge_type: count
  sub_routes:
    - id: matrices
      label: All Matrices
      route: /ach/matrices
      icon: List
    - id: new
      label: New Analysis
      route: /ach/new
      icon: Plus

dependencies:
  services:
    - database
    - events
  optional:
    - llm

capabilities:
  - hypothesis_management
  - evidence_management
  - consistency_scoring
  - devils_advocate
  - matrix_export
  - ai_suggestions

events:
  publishes:
    - ach.matrix.created
    - ach.matrix.updated
    - ach.matrix.deleted
    - ach.hypothesis.added
    - ach.evidence.added
    - ach.rating.updated
    - ach.score.calculated
  subscribes:
    - llm.analysis.completed

state:
  strategy: url
  # These are NOT filters, so must be declared explicitly
  url_params:
    - matrixId
    - hypothesisId
    - tab
    - view
  local_keys:
    - ach_matrix_zoom
    - ach_show_tooltips
    - ach_color_scheme

ui:
  has_custom_ui: true
  # Custom UI handles everything - no generic UI config needed
```

---

## Validation

### Required Field Checklist

Before a shard can be loaded:

- [ ] `name` is present and valid (lowercase, alphanumeric + hyphens)
- [ ] `version` is valid semver
- [ ] `description` is present
- [ ] `entry_point` is valid Python path
- [ ] `api_prefix` starts with `/api/`
- [ ] `requires_frame` is valid semver constraint
- [ ] `navigation.category` is a valid category
- [ ] `navigation.order` is 0-99
- [ ] `navigation.icon` is a valid Lucide icon name
- [ ] `navigation.label` is present
- [ ] `navigation.route` starts with `/` and is unique across all shards

### Frame Startup Validation

The Frame performs these checks on startup:

1. **Route Uniqueness**: No two shards may claim the same `navigation.route`
2. **API Prefix Uniqueness**: No two shards may claim the same `api_prefix`
3. **Dependency Resolution**: All shard dependencies must be available
4. **Schema Version Compatibility**: Manifest version must be compatible with Frame

If validation fails, the Frame logs a clear error and refuses to start.

---

## Migration Guide

### Migrating from v3.0.0 to v4.0.0

#### 1. Remove redundant URL param declarations

```diff
 state:
   strategy: url
   url_params:
-    - q           # Remove - auto-inferred from list_filters
-    - status      # Remove - auto-inferred from list_filters
-    - page        # Remove - always auto-managed
     - matrixId    # Keep - not a filter param
     - tab         # Keep - not a filter param
```

#### 2. Add pattern validation where needed

```diff
 primary_action:
   fields:
     - name: email
       type: text
       label: Email
       required: true
+      pattern: "^\\S+@\\S+\\.\\S+$"
+      error_message: "Must be a valid email address"
```

#### 3. Verify your list endpoints accept flat params

Your API endpoints should accept:
- Filter params directly: `?q=search&status=pending` (NOT `?filters={...}`)
- Sort params: `?sort=field&order=asc|desc`

---

## Schema Version History

| Version | Date | Changes |
|---------|------|---------|
| 4.0.0 | 2025-12-22 | Auto-inferred URL params, form pattern validation, error_message, hybrid UI placeholder |
| 3.0.0 | 2025-12-22 | Added list_filters, bulk_actions, row_actions, sortable columns |
| 2.0.0 | 2025-12-22 | Added state, badge_endpoint, list_columns, form fields; removed uses_shell_theme |
| 1.0.0 | 2025-12-21 | Initial schema definition |

---

## See Also

- [UI_SHELL_PLAN_v4.md](UI_SHELL_PLAN_v4.md) - Shell implementation plan
- [Lucide Icons](https://lucide.dev/icons) - Icon reference
- [nuqs](https://nuqs.dev) - URL state management patterns

---

*This schema is enforced by the Frame during shard loading. Non-conforming shards will fail to load with descriptive error messages.*
