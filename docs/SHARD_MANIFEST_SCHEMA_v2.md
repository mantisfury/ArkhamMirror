# Shard Manifest Schema Specification

> Version 2.0.0 - Canonical schema for `shard.yaml` files

This document defines the required and optional fields for all shard manifest files. All shards in the ArkhamMirror Shattered ecosystem MUST conform to this schema.

---

## Changes from v1.0.0

| Change | Rationale |
|--------|-----------|
| Added `state` section | Standardize state persistence across shards |
| Added `navigation.badge_endpoint` | Support dynamic indicators in sidebar |
| Removed `ui.uses_shell_theme` | Shell always injects CSS variables; shards choose to use them |
| Added `ui.list_columns` | Explicit column definitions for generic list views |
| Added `ui.primary_action.fields` | Explicit form field definitions for actions |
| Added route collision validation | Frame validates unique routes on startup |

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
  badge_endpoint: string (optional)  # NEW in v2

# OPTIONAL
dependencies: object
capabilities: string[]
events: object
state: object   # NEW in v2
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

  # Optional: Dynamic badge indicator (NEW in v2)
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
      badge_endpoint: /api/ach/pending/count  # Sub-routes can have badges too
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

The Shell polls badge endpoints every 30 seconds (throttled). Badge display rules:
- `badge_type: count` - Show number if count > 0
- `badge_type: dot` - Show red dot if count > 0
- If endpoint returns error or count = 0, hide badge

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

### 4. State Management (OPTIONAL) - NEW in v2

Defines how the shard persists state across navigation and sessions.

```yaml
state:
  # How state is persisted
  strategy: url  # url | local | session | none

  # URL parameters this shard uses (for deep linking)
  url_params:
    - analysisId    # /ach?analysisId=123
    - tab           # /ach?analysisId=123&tab=evidence
    - view          # /ach?view=matrix

  # Keys stored in localStorage (for UI preferences)
  local_keys:
    - ach_collapsed_sections
    - ach_sort_order
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `state.strategy` | string | NO | Primary persistence: `url`, `local`, `session`, `none` |
| `state.url_params` | string[] | NO | URL query params for deep linking |
| `state.local_keys` | string[] | NO | localStorage keys (prefixed with shard name) |

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

### 8. UI Configuration (OPTIONAL) - SIGNIFICANTLY EXPANDED in v2

Controls how the Shell renders this shard.

```yaml
ui:
  # Does this shard provide custom React components?
  has_custom_ui: false

  # ----- GENERIC UI CONFIGURATION -----
  # (Only used when has_custom_ui: false)

  # List view endpoint (MUST support pagination - see contract below)
  list_endpoint: /api/search/results

  # Column definitions for list view (NEW in v2)
  list_columns:
    - field: title
      label: Document
      type: link
      link_route: /document/{id}
      width: 40%

    - field: score
      label: Relevance
      type: number
      format: percent
      width: 15%

    - field: created_at
      label: Date
      type: date
      format: relative
      width: 20%

    - field: status
      label: Status
      type: badge
      width: 15%

  # Detail view endpoint pattern
  detail_endpoint: /api/search/document/{id}

  # Primary action configuration (EXPANDED in v2)
  primary_action:
    label: Search
    endpoint: /api/search/query
    method: POST
    description: Execute a search query

    # Form fields (NEW in v2)
    fields:
      - name: query
        type: text
        label: Search Query
        required: true
        placeholder: Enter search terms...

      - name: limit
        type: number
        label: Max Results
        required: false
        default: 20
        min: 1
        max: 100

      - name: include_archived
        type: checkbox
        label: Include Archived
        required: false
        default: false

      - name: date_range
        type: select
        label: Date Range
        required: false
        options:
          - value: all
            label: All Time
          - value: week
            label: Last Week
          - value: month
            label: Last Month

  # Additional actions
  actions:
    - label: Reindex
      endpoint: /api/search/reindex
      method: POST
      confirm: true
      confirm_message: This will rebuild the entire search index. Continue?
      description: Rebuild search index
      fields: []  # No fields = button only
```

#### List Endpoint Pagination Contract

When `list_endpoint` is specified, the endpoint MUST:

1. Accept query parameters: `?page=N&page_size=M`
2. Return a paginated response:

```json
{
  "items": [...],
  "total": 1000,
  "page": 1,
  "page_size": 20
}
```

The Shell defaults to `page_size=20`. Endpoints should cap page_size at a reasonable maximum (e.g., 100).

#### UI Field Types

| Type | Renders As | Additional Properties |
|------|------------|----------------------|
| `text` | Text input | `placeholder`, `maxLength` |
| `textarea` | Multi-line input | `placeholder`, `rows` |
| `number` | Number input | `min`, `max`, `step` |
| `checkbox` | Checkbox | - |
| `select` | Dropdown | `options: [{value, label}]` |
| `date` | Date picker | `min_date`, `max_date` |
| `file` | File upload | `accept`, `multiple` |

#### List Column Types

| Type | Renders As | Additional Properties |
|------|------------|----------------------|
| `text` | Plain text | - |
| `link` | Clickable link | `link_route` with `{id}` placeholder |
| `number` | Formatted number | `format`: `integer`, `decimal`, `percent` |
| `date` | Formatted date | `format`: `absolute`, `relative` |
| `badge` | Colored badge | Maps value to color automatically |
| `boolean` | Check/X icon | - |

#### Theme CSS Variables

**IMPORTANT CHANGE from v1**: The Shell ALWAYS injects theme CSS variables. There is no `uses_shell_theme` toggle.

Shards can choose to use these variables or ignore them:

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

Generic UI pages always use shell theming. Custom UI shards can use these variables for consistency or define their own styles entirely.

---

## Complete Examples

### Example 1: Simple Shard (Generic UI)

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
  url_params:
    - documentId
    - view

ui:
  has_custom_ui: false

  list_endpoint: /api/embed/documents
  list_columns:
    - field: title
      label: Document
      type: link
      link_route: /document/{id}
      width: 50%
    - field: chunk_count
      label: Chunks
      type: number
      width: 15%
    - field: embedded_at
      label: Embedded
      type: date
      format: relative
      width: 20%
    - field: status
      label: Status
      type: badge
      width: 15%

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

  actions:
    - label: Batch Embed
      endpoint: /api/embed/batch
      method: POST
      description: Embed multiple documents
      fields:
        - name: document_ids
          type: textarea
          label: Document IDs (one per line)
          required: true
```

### Example 2: Complex Shard (Custom UI with State)

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
  url_params:
    - matrixId
    - hypothesisId
    - tab
  local_keys:
    - ach_matrix_zoom
    - ach_show_tooltips
    - ach_color_scheme

ui:
  has_custom_ui: true
  # No list_columns or fields needed - custom UI handles everything
```

### Example 3: Shard with Unreviewed Badge (Contradictions)

```yaml
name: contradictions
version: 0.1.0
description: Contradiction detection engine for multi-document analysis
entry_point: arkham_shard_contradictions:ContradictionsShard

api_prefix: /api/contradictions
requires_frame: ">=0.1.0"

navigation:
  category: Analysis
  order: 31
  icon: GitCompare
  label: Contradictions
  route: /contradictions
  badge_endpoint: /api/contradictions/pending/count
  badge_type: dot  # Just show a dot when there are pending items

# ... rest of manifest
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

If validation fails, the Frame logs a clear error and refuses to start:

```
ERROR: Route collision detected!
  Route: /analysis
  Claimed by: ach (arkham-shard-ach v0.1.0)
  Also claimed by: custom-analysis (arkham-shard-custom v0.2.0)

Resolution: Change one shard's navigation.route to a unique value.
```

### Python Validator

Location: `arkham_frame/shard_interface.py`

```python
@dataclass
class NavigationConfig:
    """Navigation configuration for Shell sidebar."""
    category: str
    order: int
    icon: str
    label: str
    route: str
    badge_endpoint: Optional[str] = None
    badge_type: Optional[str] = None  # "count" or "dot"
    sub_routes: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class StateConfig:
    """State management configuration."""
    strategy: str = "none"  # url, local, session, none
    url_params: List[str] = field(default_factory=list)
    local_keys: List[str] = field(default_factory=list)

@dataclass
class UIFieldConfig:
    """Form field configuration for generic UI."""
    name: str
    type: str  # text, textarea, number, checkbox, select, date, file
    label: str
    required: bool = False
    default: Any = None
    # Type-specific options
    placeholder: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    options: List[Dict[str, str]] = field(default_factory=list)

@dataclass
class UIColumnConfig:
    """List column configuration for generic UI."""
    field: str
    label: str
    type: str  # text, link, number, date, badge, boolean
    width: Optional[str] = None
    link_route: Optional[str] = None
    format: Optional[str] = None

@dataclass
class ShardManifest:
    """Validated shard manifest."""
    name: str
    version: str
    description: str
    entry_point: str
    api_prefix: str
    requires_frame: str

    # Navigation (required for UI)
    navigation: NavigationConfig

    # Optional
    dependencies: Optional[DependenciesConfig] = None
    capabilities: List[str] = field(default_factory=list)
    events: Optional[EventsConfig] = None
    state: Optional[StateConfig] = None
    ui: Optional[UIConfig] = None

    def validate(self) -> List[str]:
        """Return list of validation errors, empty if valid."""
        errors = []

        # Core identity
        if not self.name:
            errors.append("name is required")
        if not re.match(r'^[a-z][a-z0-9-]*$', self.name):
            errors.append("name must be lowercase alphanumeric with hyphens")

        # Frame integration
        if not self.api_prefix.startswith("/api/"):
            errors.append("api_prefix must start with /api/")

        # Navigation
        if not self.navigation.route.startswith("/"):
            errors.append("navigation.route must start with /")
        if not 0 <= self.navigation.order <= 99:
            errors.append("navigation.order must be 0-99")
        if self.navigation.badge_type and self.navigation.badge_type not in ("count", "dot"):
            errors.append("navigation.badge_type must be 'count' or 'dot'")

        # State
        if self.state:
            if self.state.strategy not in ("url", "local", "session", "none"):
                errors.append("state.strategy must be url, local, session, or none")

        return errors
```

---

## Migration Guide

### Migrating from v1.0.0 to v2.0.0

#### 1. Remove `uses_shell_theme` (if present)

```diff
 ui:
   has_custom_ui: true
-  uses_shell_theme: false
```

The Shell now always injects CSS variables. Shards choose whether to use them.

#### 2. Add `state` section (recommended)

```diff
+state:
+  strategy: url
+  url_params:
+    - analysisId
```

#### 3. Add `badge_endpoint` (if applicable)

```diff
 navigation:
   category: Analysis
   order: 30
   icon: Scale
   label: ACH Analysis
   route: /ach
+  badge_endpoint: /api/ach/unreviewed/count
+  badge_type: count
```

#### 4. Add `list_columns` for generic UI shards

```diff
 ui:
   has_custom_ui: false
   list_endpoint: /api/embed/documents
+  list_columns:
+    - field: title
+      label: Document
+      type: link
+      link_route: /document/{id}
+    - field: status
+      label: Status
+      type: badge
```

#### 5. Add `fields` to actions

```diff
 primary_action:
   label: Search
   endpoint: /api/search/query
   method: POST
+  fields:
+    - name: query
+      type: text
+      label: Search Query
+      required: true
```

---

## Schema Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2025-12-22 | Added state, badge_endpoint, list_columns, form fields; removed uses_shell_theme |
| 1.0.0 | 2025-12-21 | Initial schema definition |

---

## See Also

- [UI_SHELL_PLAN_v2.md](UI_SHELL_PLAN_v2.md) - Shell implementation plan
- [Lucide Icons](https://lucide.dev/icons) - Icon reference

---

*This schema is enforced by the Frame during shard loading. Non-conforming shards will fail to load with descriptive error messages.*
