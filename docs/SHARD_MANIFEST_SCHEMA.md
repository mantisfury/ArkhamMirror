# Shard Manifest Schema Specification

> Version 1.0.0 - Canonical schema for `shard.yaml` files

This document defines the required and optional fields for all shard manifest files. All shards in the ArkhamMirror Shattered ecosystem MUST conform to this schema.

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

# OPTIONAL
dependencies: object
capabilities: string[]
events: object
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

  # Optional: Sub-navigation items
  sub_routes:
    - id: matrices
      label: All Matrices
      route: /ach/matrices
      icon: List

    - id: new
      label: New Analysis
      route: /ach/new
      icon: Plus
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `navigation.category` | string | YES | See Category Definitions below |
| `navigation.order` | integer | YES | 0-99, determines sort within category |
| `navigation.icon` | string | YES | Lucide icon name (PascalCase) |
| `navigation.label` | string | YES | Human-readable label |
| `navigation.route` | string | YES | Primary route path |
| `navigation.sub_routes` | array | NO | Additional navigation items |

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

### 4. Dependencies (OPTIONAL)

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

### 5. Capabilities (OPTIONAL)

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

### 6. Events (OPTIONAL)

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

### 7. UI Configuration (OPTIONAL)

Controls how the Shell renders this shard.

```yaml
ui:
  # Does this shard provide custom React components?
  has_custom_ui: false

  # Should custom UI use shell theming? (default: false when has_custom_ui: true)
  uses_shell_theme: false

  # For generic UI: primary list endpoint
  list_endpoint: /api/search/results

  # For generic UI: detail view endpoint pattern
  detail_endpoint: /api/search/document/{id}

  # For generic UI: primary action
  primary_action:
    label: Search
    endpoint: /api/search/query
    method: POST
    description: Execute a search query

  # Additional actions for generic UI
  actions:
    - label: Reindex
      endpoint: /api/search/reindex
      method: POST
      confirm: true
      description: Rebuild search index
```

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `ui.has_custom_ui` | boolean | false | True if shard provides React components |
| `ui.uses_shell_theme` | boolean | false | True to inherit shell CSS variables |
| `ui.list_endpoint` | string | null | Endpoint returning array for list view |
| `ui.detail_endpoint` | string | null | Endpoint pattern with `{id}` placeholder |
| `ui.primary_action` | object | null | Main action form |
| `ui.actions` | array | [] | Additional action buttons |

#### UI Decision Tree

```
Has custom UI?
  YES --> uses_shell_theme?
            YES --> Render custom UI with shell theme CSS vars
            NO  --> Render custom UI in unstyled container
  NO  --> Render generic UI using list_endpoint, primary_action, etc.
```

---

## Complete Example

### Simple Shard (Generic UI)

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

ui:
  has_custom_ui: false
  list_endpoint: /api/embed/documents
  detail_endpoint: /api/embed/document/{id}
  primary_action:
    label: Embed Document
    endpoint: /api/embed/generate
    method: POST
    description: Generate embeddings for a document
  actions:
    - label: Batch Embed
      endpoint: /api/embed/batch
      method: POST
      description: Embed multiple documents
```

### Complex Shard (Custom UI)

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

ui:
  has_custom_ui: true
  uses_shell_theme: false  # ACH has its own styling
```

---

## Validation

### Required Field Checklist

Before a shard can be loaded:

- [ ] `name` is present and valid
- [ ] `version` is valid semver
- [ ] `description` is present
- [ ] `entry_point` is valid Python path
- [ ] `api_prefix` starts with `/api/`
- [ ] `requires_frame` is valid semver constraint
- [ ] `navigation.category` is a valid category
- [ ] `navigation.order` is 0-99
- [ ] `navigation.icon` is a valid Lucide icon name
- [ ] `navigation.label` is present
- [ ] `navigation.route` starts with `/`

### Python Validator

Location: `arkham_frame/shard_interface.py`

```python
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
    ui: Optional[UIConfig] = None

    def validate(self) -> List[str]:
        """Return list of validation errors, empty if valid."""
        errors = []
        if not self.name:
            errors.append("name is required")
        if not self.api_prefix.startswith("/api/"):
            errors.append("api_prefix must start with /api/")
        # ... more validation
        return errors
```

---

## Migration Guide

### Updating Existing Shards

For shards created before this schema, add the following:

1. Add `navigation` section (REQUIRED)
2. Add `requires_frame` (REQUIRED)
3. Optionally add `ui` section for generic UI hints

Example diff:

```diff
 name: search
 version: 0.1.0
 description: Semantic and keyword search
+entry_point: arkham_shard_search:SearchShard

-requires_frame: ">=0.1.0"
+api_prefix: /api/search
+requires_frame: ">=0.1.0"

+navigation:
+  category: Search
+  order: 20
+  icon: Search
+  label: Search
+  route: /search

 dependencies:
   services:
     - database
```

---

## Schema Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-21 | Initial schema definition |

---

*This schema is enforced by the Frame during shard loading. Non-conforming shards will fail to load with descriptive error messages.*
