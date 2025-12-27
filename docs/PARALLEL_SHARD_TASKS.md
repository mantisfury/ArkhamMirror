# Parallel Shard Implementation Tasks

## Overview

This document contains task prompts for parallel agent execution to implement 15 shards.

**Architecture:**
- 15 Worker agents (one per shard) - work in isolation
- 1 Coordinator agent - handles App.tsx consolidation after workers complete

## Shards to Implement

| Shard | Worker | Priority |
|-------|--------|----------|
| graph | Worker 1 | High - visualization |
| timeline | Worker 2 | High - visualization |
| documents | Worker 3 | High - core data |
| entities | Worker 4 | High - core data |
| projects | Worker 5 | High - organization |
| claims | Worker 6 | Medium - analysis |
| credibility | Worker 7 | Medium - analysis |
| patterns | Worker 8 | Medium - analysis |
| provenance | Worker 9 | Medium - tracking |
| export | Worker 10 | Medium - output |
| reports | Worker 11 | Medium - output |
| letters | Worker 12 | Low - specialized |
| packets | Worker 13 | Low - specialized |
| templates | Worker 14 | Low - specialized |
| summary | Worker 15 | Low - specialized |

---

## Worker Agent Task Prompt Template

Copy this template and replace `{SHARD_NAME}` with the specific shard name.

```
You are implementing the {SHARD_NAME} shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-{SHARD_NAME}/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/{SHARD_NAME}/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders
- Any other shard's files

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-{SHARD_NAME}/shard.yaml` - Your shard's manifest

## Implementation Checklist

### Backend (`packages/arkham-shard-{SHARD_NAME}/`)

1. **shard.py** - Update with:
   - [ ] Real `_create_schema()` with CREATE TABLE and indexes
   - [ ] `_parse_jsonb()` helper method (copy from guide)
   - [ ] `_row_to_X()` converter method
   - [ ] Real service methods (not stubs) that query database
   - [ ] Register in app.state: `frame.app.state.{SHARD_NAME}_shard = self`

2. **api.py** - Update with:
   - [ ] `get_shard(request)` helper function
   - [ ] Real endpoint implementations using shard methods
   - [ ] Proper error handling with HTTPException

3. **shard.yaml** - Verify:
   - [ ] `has_custom_ui: true` is set

### Frontend (`packages/arkham-shard-shell/src/pages/{SHARD_NAME}/`)

Create these files:

1. **{ShardName}Page.tsx** - Main page component with:
   - [ ] Data fetching using useFetch hook
   - [ ] Proper loading/error states
   - [ ] Toast notifications using `toast.success()`, `toast.error()` pattern
   - [ ] Actions that call your API endpoints

2. **{ShardName}Page.css** - Styling following existing patterns

3. **index.ts** - Export file:
   ```typescript
   export { {ShardName}Page } from './{ShardName}Page';
   ```

## Verification

Before marking complete:
1. Run: `python -m py_compile packages/arkham-shard-{SHARD_NAME}/arkham_shard_{SHARD_NAME}/shard.py`
2. Run: `python -m py_compile packages/arkham-shard-{SHARD_NAME}/arkham_shard_{SHARD_NAME}/api.py`
3. Verify TypeScript has no errors in your files

## Completion Signal

When done, output this exact line:
SHARD_COMPLETE: {SHARD_NAME}
```

---

## Specific Worker Prompts

### Worker 1: Graph Shard

```
You are implementing the graph shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-graph/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/graph/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-graph/shard.yaml` - Your shard's manifest

## Graph Shard Purpose

The graph shard visualizes entity relationships and connections. Key features:
- Display nodes (entities) and edges (relationships)
- Interactive graph exploration
- Filtering and search within the graph
- Node detail views

## Implementation Checklist

### Backend (`packages/arkham-shard-graph/`)

1. **shard.py** - Update with:
   - [ ] Real `_create_schema()` for graph nodes and edges tables
   - [ ] `_parse_jsonb()` helper method
   - [ ] `_row_to_node()` and `_row_to_edge()` converters
   - [ ] Service methods: get_nodes(), get_edges(), get_graph_data(), etc.
   - [ ] Register: `frame.app.state.graph_shard = self`

2. **api.py** - Update with:
   - [ ] `get_shard(request)` helper
   - [ ] GET /nodes - list nodes
   - [ ] GET /edges - list edges
   - [ ] GET /graph - get full graph data for visualization
   - [ ] Proper error handling

3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/graph/`)

1. **GraphPage.tsx** - Graph visualization page
2. **GraphPage.css** - Styling
3. **index.ts** - Export

## Verification

Run syntax checks and verify no TypeScript errors.

## Completion Signal

When done, output: SHARD_COMPLETE: graph
```

### Worker 2: Timeline Shard

```
You are implementing the timeline shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-timeline/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/timeline/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-timeline/shard.yaml` - Your shard's manifest

## Timeline Shard Purpose

The timeline shard displays events in chronological order. Key features:
- Chronological event display
- Date range filtering
- Event categorization
- Zoom and pan controls

## Implementation Checklist

### Backend (`packages/arkham-shard-timeline/`)

1. **shard.py** - Update with:
   - [ ] Real `_create_schema()` for timeline events table
   - [ ] `_parse_jsonb()` helper method
   - [ ] `_row_to_event()` converter
   - [ ] Service methods: get_events(), get_events_in_range(), etc.
   - [ ] Register: `frame.app.state.timeline_shard = self`

2. **api.py** - Update with:
   - [ ] `get_shard(request)` helper
   - [ ] GET /events - list events with date filtering
   - [ ] GET /events/{id} - get single event
   - [ ] Proper error handling

3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/timeline/`)

1. **TimelinePage.tsx** - Timeline visualization page
2. **TimelinePage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: timeline
```

### Worker 3: Documents Shard

```
You are implementing the documents shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-documents/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/documents/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-documents/shard.yaml` - Your shard's manifest

## Documents Shard Purpose

The documents shard manages document storage and retrieval. Key features:
- Document listing with metadata
- Document search and filtering
- Document detail view
- Document status tracking

## Implementation Checklist

### Backend (`packages/arkham-shard-documents/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/documents/`)

1. **DocumentsPage.tsx** - Document list/management page
2. **DocumentsPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: documents
```

### Worker 4: Entities Shard

```
You are implementing the entities shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-entities/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/entities/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-entities/shard.yaml` - Your shard's manifest

## Entities Shard Purpose

The entities shard manages extracted entities (people, places, organizations). Key features:
- Entity listing with type filtering
- Entity search
- Entity detail with mentions/occurrences
- Entity relationship display

## Implementation Checklist

### Backend (`packages/arkham-shard-entities/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/entities/`)

1. **EntitiesPage.tsx** - Entity list/management page
2. **EntitiesPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: entities
```

### Worker 5: Projects Shard

```
You are implementing the projects shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-projects/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/projects/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-projects/shard.yaml` - Your shard's manifest

## Projects Shard Purpose

The projects shard organizes work into projects. Key features:
- Project listing
- Project creation/editing
- Project document association
- Project status tracking

## Implementation Checklist

### Backend (`packages/arkham-shard-projects/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/projects/`)

1. **ProjectsPage.tsx** - Project list/management page
2. **ProjectsPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: projects
```

### Worker 6: Claims Shard

```
You are implementing the claims shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-claims/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/claims/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-claims/shard.yaml` - Your shard's manifest

## Claims Shard Purpose

The claims shard tracks factual claims and their verification status. Key features:
- Claim listing with status filters
- Claim detail with evidence
- Claim verification workflow
- Source attribution

## Implementation Checklist

### Backend (`packages/arkham-shard-claims/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/claims/`)

1. **ClaimsPage.tsx** - Claims list/management page
2. **ClaimsPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: claims
```

### Worker 7: Credibility Shard

```
You are implementing the credibility shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-credibility/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/credibility/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-credibility/shard.yaml` - Your shard's manifest

## Credibility Shard Purpose

The credibility shard assesses source and claim credibility. Key features:
- Credibility score display
- Factor breakdown
- Historical tracking
- Comparison views

## Implementation Checklist

### Backend (`packages/arkham-shard-credibility/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/credibility/`)

1. **CredibilityPage.tsx** - Credibility assessment page
2. **CredibilityPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: credibility
```

### Worker 8: Patterns Shard

```
You are implementing the patterns shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-patterns/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/patterns/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-patterns/shard.yaml` - Your shard's manifest

## Patterns Shard Purpose

The patterns shard detects and displays recurring patterns. Key features:
- Pattern listing
- Pattern detail with occurrences
- Pattern matching configuration
- Pattern statistics

## Implementation Checklist

### Backend (`packages/arkham-shard-patterns/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/patterns/`)

1. **PatternsPage.tsx** - Patterns list/management page
2. **PatternsPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: patterns
```

### Worker 9: Provenance Shard

```
You are implementing the provenance shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-provenance/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/provenance/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-provenance/shard.yaml` - Your shard's manifest

## Provenance Shard Purpose

The provenance shard tracks data origin and chain of custody. Key features:
- Source tracking
- Transformation history
- Audit trail
- Chain visualization

## Implementation Checklist

### Backend (`packages/arkham-shard-provenance/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/provenance/`)

1. **ProvenancePage.tsx** - Provenance tracking page
2. **ProvenancePage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: provenance
```

### Worker 10: Export Shard

```
You are implementing the export shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-export/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/export/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-export/shard.yaml` - Your shard's manifest

## Export Shard Purpose

The export shard handles data export in various formats. Key features:
- Export format selection (JSON, CSV, PDF, etc.)
- Export configuration
- Export history
- Scheduled exports

## Implementation Checklist

### Backend (`packages/arkham-shard-export/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/export/`)

1. **ExportPage.tsx** - Export configuration page
2. **ExportPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: export
```

### Worker 11: Reports Shard

```
You are implementing the reports shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-reports/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/reports/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-reports/shard.yaml` - Your shard's manifest

## Reports Shard Purpose

The reports shard generates analysis reports. Key features:
- Report template selection
- Report generation
- Report history
- Report scheduling

## Implementation Checklist

### Backend (`packages/arkham-shard-reports/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/reports/`)

1. **ReportsPage.tsx** - Reports management page
2. **ReportsPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: reports
```

### Worker 12: Letters Shard

```
You are implementing the letters shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-letters/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/letters/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-letters/shard.yaml` - Your shard's manifest

## Letters Shard Purpose

The letters shard manages correspondence/letter documents. Key features:
- Letter listing
- Letter metadata
- Correspondence tracking
- Threading/conversation view

## Implementation Checklist

### Backend (`packages/arkham-shard-letters/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/letters/`)

1. **LettersPage.tsx** - Letters management page
2. **LettersPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: letters
```

### Worker 13: Packets Shard

```
You are implementing the packets shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-packets/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/packets/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-packets/shard.yaml` - Your shard's manifest

## Packets Shard Purpose

The packets shard manages document packets/bundles. Key features:
- Packet listing
- Packet contents management
- Packet assembly
- Packet export

## Implementation Checklist

### Backend (`packages/arkham-shard-packets/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/packets/`)

1. **PacketsPage.tsx** - Packets management page
2. **PacketsPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: packets
```

### Worker 14: Templates Shard

```
You are implementing the templates shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-templates/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/templates/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-templates/shard.yaml` - Your shard's manifest

## Templates Shard Purpose

The templates shard manages document/report templates. Key features:
- Template listing
- Template editor
- Template variables
- Template preview

## Implementation Checklist

### Backend (`packages/arkham-shard-templates/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/templates/`)

1. **TemplatesPage.tsx** - Templates management page
2. **TemplatesPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: templates
```

### Worker 15: Summary Shard

```
You are implementing the summary shard for the SHATTERED application.

## Your Scope (STRICTLY ENFORCED)

You may ONLY modify files in these locations:
1. `packages/arkham-shard-summary/` - Backend implementation
2. `packages/arkham-shard-shell/src/pages/summary/` - Frontend UI (create this folder)

You must NOT modify:
- `packages/arkham-shard-shell/src/App.tsx` - The coordinator handles this
- Any files outside your assigned folders

## Reference Materials

Read these files first:
1. `docs/SHARD_IMPLEMENTATION_GUIDE.md` - Complete implementation guide
2. `packages/arkham-shard-settings/arkham_shard_settings/shard.py` - Reference backend
3. `packages/arkham-shard-settings/arkham_shard_settings/api.py` - Reference API
4. `packages/arkham-shard-shell/src/pages/settings/SettingsPage.tsx` - Reference UI
5. `packages/arkham-shard-summary/shard.yaml` - Your shard's manifest

## Summary Shard Purpose

The summary shard generates AI-powered summaries. Key features:
- Summary generation
- Summary listing
- Summary configuration
- Multi-document summaries

## Implementation Checklist

### Backend (`packages/arkham-shard-summary/`)

1. **shard.py** - Update with real database operations
2. **api.py** - Update with real endpoints
3. **shard.yaml** - Set `has_custom_ui: true`

### Frontend (`packages/arkham-shard-shell/src/pages/summary/`)

1. **SummaryPage.tsx** - Summary management page
2. **SummaryPage.css** - Styling
3. **index.ts** - Export

## Completion Signal

When done, output: SHARD_COMPLETE: summary
```

---

## Coordinator Agent Prompt

```
You are the COORDINATOR agent for the SHATTERED parallel shard implementation.

## Your Responsibilities

1. DO NOT implement any shards yourself
2. Wait for worker agents to complete their implementations
3. After ALL workers complete, consolidate changes to App.tsx

## Worker Completion Tracking

Track completion signals from workers:
- [ ] Worker 1: graph
- [ ] Worker 2: timeline
- [ ] Worker 3: documents
- [ ] Worker 4: entities
- [ ] Worker 5: projects
- [ ] Worker 6: claims
- [ ] Worker 7: credibility
- [ ] Worker 8: patterns
- [ ] Worker 9: provenance
- [ ] Worker 10: export
- [ ] Worker 11: reports
- [ ] Worker 12: letters
- [ ] Worker 13: packets
- [ ] Worker 14: templates
- [ ] Worker 15: summary

## App.tsx Consolidation

Once all workers complete, update `packages/arkham-shard-shell/src/App.tsx`:

### Add Imports (after existing imports around line 40)

```typescript
import { GraphPage } from './pages/graph';
import { TimelinePage } from './pages/timeline';
import { DocumentsPage } from './pages/documents';
import { EntitiesPage } from './pages/entities';
import { ProjectsPage } from './pages/projects';
import { ClaimsPage } from './pages/claims';
import { CredibilityPage } from './pages/credibility';
import { PatternsPage } from './pages/patterns';
import { ProvenancePage } from './pages/provenance';
import { ExportPage } from './pages/export';
import { ReportsPage } from './pages/reports';
import { LettersPage } from './pages/letters';
import { PacketsPage } from './pages/packets';
import { TemplatesPage } from './pages/templates';
import { SummaryPage } from './pages/summary';
```

### Add Routes (before the catch-all route)

```typescript
{/* Graph shard */}
<Route path="/graph" element={<GraphPage />} />

{/* Timeline shard */}
<Route path="/timeline" element={<TimelinePage />} />

{/* Documents shard */}
<Route path="/documents" element={<DocumentsPage />} />

{/* Entities shard */}
<Route path="/entities" element={<EntitiesPage />} />

{/* Projects shard */}
<Route path="/projects" element={<ProjectsPage />} />

{/* Claims shard */}
<Route path="/claims" element={<ClaimsPage />} />

{/* Credibility shard */}
<Route path="/credibility" element={<CredibilityPage />} />

{/* Patterns shard */}
<Route path="/patterns" element={<PatternsPage />} />

{/* Provenance shard */}
<Route path="/provenance" element={<ProvenancePage />} />

{/* Export shard */}
<Route path="/export" element={<ExportPage />} />

{/* Reports shard */}
<Route path="/reports" element={<ReportsPage />} />

{/* Letters shard */}
<Route path="/letters" element={<LettersPage />} />

{/* Packets shard */}
<Route path="/packets" element={<PacketsPage />} />

{/* Templates shard */}
<Route path="/templates" element={<TemplatesPage />} />

{/* Summary shard */}
<Route path="/summary" element={<SummaryPage />} />
```

## Final Verification

After updating App.tsx:
1. Run: `cd packages/arkham-shard-shell && npm run build`
2. Fix any TypeScript errors
3. Report final status

## Completion Signal

When done, output: COORDINATION_COMPLETE: All 15 shards integrated
```

---

## Execution Instructions

1. Launch 15 worker agents in parallel with their respective prompts
2. Launch 1 coordinator agent
3. Workers implement shards independently (no conflicts)
4. When all workers signal completion, coordinator updates App.tsx
5. Coordinator runs final build verification
