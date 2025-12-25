# UI Shell Shard Implementation Plan

> Planning document for the arkham-shard-shell package

---

## 1. Executive Summary

Build a React/TypeScript UI shell that provides:
- Navigation sidebar (auto-generated from shard manifests)
- Top bar (project selector dropdown, connection status, settings)
- Theme system (default dark + hacker cabin)
- Generic UI templates for shards without custom UIs
- Content routing

**Build System**: Monorepo integration - built together with Frame and all shards.

### Decisions Made

| Question | Decision |
|----------|----------|
| Project management | Dropdown selector only (CRUD later if needed) |
| Authentication | Not for v1, design for future |
| Offline support | Degraded state display, but Shell requires Frame |
| Hot-reload shards | No - monorepo build only |
| Theme vs Shard UI conflicts | **Shard UI takes precedence** |
| Phase 1 scope | 3 shards only: ACH, Ingest, Search |
| Build/Dev workflow | Vite proxy (:5173) -> Frame (:8105) for dev; Frame serves static for prod |
| Custom UI location | All UIs in shell package (`pages/ach/`, `pages/graph/`, etc.) |
| Static file serving | Frame serves built React app (FastAPI static middleware) |

### Related Documents

- [SHARD_MANIFEST_SCHEMA.md](SHARD_MANIFEST_SCHEMA.md) - Formal schema specification for shard.yaml files

---

## 2. Current State Analysis

### 2.1 Frame API Readiness

The Frame already provides shard discovery endpoints:

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/shards/` | EXISTS | Returns name, version, loaded status |
| `GET /api/shards/{name}` | EXISTS | Returns shard details + manifest |
| `GET /api/shards/{name}/routes` | EXISTS | Returns API routes |
| `GET /api/frame/projects` | NEEDED | List projects |
| `GET /api/frame/projects/current` | NEEDED | Current project |

**Action Required**: Extend Frame's `/api/shards/` endpoint to return full manifest data including menu items, capabilities, and UI metadata.

### 2.2 Shard Manifest Schema Issues

**Current Problem**: Inconsistent shard.yaml schemas.

Dashboard shard has:
```yaml
menu:
  - id: overview
    label: Overview
    icon: LayoutDashboard
    path: /dashboard
```

Other shards (ACH, Search, etc.) have:
```yaml
capabilities:
  - semantic_search
  - keyword_search
events:
  publishes: [...]
```

**No navigation data** in most shard manifests.

### 2.3 ShardManifest Dataclass

Location: `arkham_frame/shard_interface.py`

```python
@dataclass
class ShardManifest:
    name: str
    version: str
    description: str = ""
    entry_point: str = ""
    schema: Optional[str] = None
    api_prefix: str = ""
    menu: List[Dict[str, Any]] = field(default_factory=list)  # <-- Already exists!
    requires: List[str] = field(default_factory=list)
```

The `menu` field exists but isn't populated by most shards.

---

## 3. Proposed Schema Standardization

### 3.1 Unified shard.yaml Schema

```yaml
# Required fields
name: search
version: 0.1.0
description: Semantic and keyword search for documents
entry_point: arkham_shard_search:SearchShard
api_prefix: /api/search

# Dependencies
requires_frame: ">=0.1.0"
dependencies:
  services: [database, vectors, events]
  optional: [documents, entities]

# Capabilities for introspection
capabilities:
  - semantic_search
  - keyword_search
  - hybrid_search

# Navigation - REQUIRED for all shards
navigation:
  category: Search          # Sidebar category grouping
  order: 20                  # Sort order within category
  icon: Search              # Lucide icon name
  label: Search             # Display label
  route: /search            # Primary route

  # Optional sub-routes
  sub_routes:
    - id: advanced
      label: Advanced Search
      route: /search/advanced
      icon: SlidersHorizontal

# UI hints for generic rendering
ui:
  # Does this shard provide its own UI components?
  has_custom_ui: false

  # Primary list endpoint for generic list view
  list_endpoint: /api/search/results

  # Primary detail endpoint pattern
  detail_endpoint: /api/search/document/{id}

  # Primary action form
  primary_action:
    label: Search
    endpoint: /api/search/query
    method: POST

# Events (existing)
events:
  publishes: [search.query.executed]
  subscribes: [documents.indexed]
```

### 3.2 Category Definitions

Standard categories for sidebar grouping:

| Category | Order | Description | Shards |
|----------|-------|-------------|--------|
| System | 0 | Infrastructure | Dashboard |
| Data | 10 | Document management | Ingest, Parse |
| Search | 20 | Search & discovery | Search, Embed |
| Analysis | 30 | Analytical tools | ACH, Contradictions, Anomalies, Timeline |
| Visualize | 40 | Visualization | Graph, Map, Influence |
| Export | 50 | Data export | Export |

---

## 4. Generic UI Template System

### 4.1 Feasibility Analysis

After analyzing existing shard APIs, here's what can be auto-generated:

| UI Pattern | Feasibility | Example |
|------------|-------------|---------|
| List View | HIGH | `/api/search/results`, `/api/ach/matrices` |
| Detail View | HIGH | `/api/ach/matrix/{id}` |
| CRUD Forms | MEDIUM | Create/update entities via Pydantic models |
| Action Buttons | HIGH | `/api/contradictions/analyze`, `/api/database/vacuum` |
| Status Cards | HIGH | Health checks, queue stats |
| Complex Visualizations | LOW | ACH matrix, Graph, Timeline |

### 4.2 Generic Shard Page Template

When a shard doesn't have a custom UI, render a generic page with:

```
+------------------------------------------+
|  [Icon] Shard Name                       |
|  Description from manifest               |
+------------------------------------------+
|                                          |
|  +-- Capabilities --+  +-- Actions --+   |
|  | - capability_1   |  | [Button 1]  |   |
|  | - capability_2   |  | [Button 2]  |   |
|  +------------------+  +-------------+   |
|                                          |
|  +-- API Explorer (Collapsed) ----------+|
|  | GET  /api/search/query              ||
|  | POST /api/search/results            ||
|  +--------------------------------------+|
|                                          |
|  +-- Primary Content -------------------+|
|  | (List view from list_endpoint)       ||
|  | [Item 1]                             ||
|  | [Item 2]                             ||
|  +--------------------------------------+|
+------------------------------------------+
```

### 4.3 Auto-Generated UI Components

| Component | Source | Notes |
|-----------|--------|-------|
| ShardListView | `ui.list_endpoint` | Paginated table with search |
| ShardDetailView | `ui.detail_endpoint` | JSON viewer with formatted output |
| ShardActionForm | OpenAPI schema | Auto-generate form from Pydantic |
| ShardStatusCard | Health endpoint | Connection/status display |

### 4.4 Custom UI Override

Shards can provide custom React components:

```yaml
ui:
  has_custom_ui: true
  components:
    page: "@arkham-shard-ach/ui/ACHPage"
    detail: "@arkham-shard-ach/ui/ACHMatrixView"
```

If `has_custom_ui: false` or missing, use generic template.

---

## 5. Architecture Decisions

### 5.1 Build System: Monorepo

**Decision**: Single build, all shards bundled together.

```
packages/
  arkham-frame/           # Python backend
  arkham-shard-shell/     # React frontend (THIS PACKAGE)
    ui/
      src/
        Shell.tsx
        components/
        themes/
        pages/
          generic/        # Generic shard pages
          dashboard/      # Custom dashboard UI (optional)
  arkham-shard-*/         # Other shards (Python backends)
```

**Implications**:
- Vite builds entire frontend from shell package
- Shard custom UIs imported statically (no module federation)
- Simpler deployment: single static build + Python backend

### 5.2 State Management

**Decision**: React Context + hooks (not Redux/Zustand)

Rationale:
- Simpler for this scale
- Theme, shards, project state are relatively simple
- Can migrate to Zustand later if needed

### 5.3 Routing

**Decision**: React Router v6 with data loaders

```typescript
const routes = [
  {
    path: "/",
    element: <Shell />,
    children: [
      { path: "dashboard/*", element: <DashboardRoutes /> },
      { path: "ach/*", element: <ACHRoutes /> },
      // Generic routes for shards without custom UI
      { path: ":shardName/*", element: <GenericShardPage /> },
    ],
  },
];
```

---

## 6. Implementation Phases

### Phase 1: Foundation (This Sprint)

**Goal**: Working shell with static navigation for 3 representative shards

**Shard Selection** (different complexity levels):
| Shard | Complexity | Why Selected |
|-------|------------|--------------|
| ACH | HIGH | Complex visualization, LLM integration, many endpoints |
| Ingest | MEDIUM | File upload, progress tracking, job queuing |
| Search | LOW | Simple form + results list, good generic UI candidate |

Tasks:
- [ ] Create `arkham-shard-shell` package structure
- [ ] Set up Vite + React + TypeScript
- [ ] Implement Shell layout (sidebar, topbar, content)
- [ ] Hardcode navigation for 3 shards (ACH, Ingest, Search)
- [ ] Implement default dark theme
- [ ] Add basic routing
- [ ] Create placeholder pages for each shard

Deliverable: Shell renders, navigation works for 3 shards, validates architecture before scaling

### Phase 2: Frame Integration

**Goal**: Dynamic shard discovery + generic pages

Tasks:
- [ ] Extend Frame API to return full manifest data
- [ ] Update all shard.yaml files with navigation section (per SHARD_MANIFEST_SCHEMA.md)
- [ ] **Add static file serving to Frame** (serve built SPA, see Section 12.3)
- [ ] Implement dynamic sidebar generation from API
- [ ] Build GenericShardPage component
- [ ] Add API explorer component
- [ ] Add connection status indicator

Deliverable: Navigation auto-generated from installed shards, generic pages work, production deployment ready

### Phase 3: Theme System

**Goal**: Swappable themes

Tasks:
- [ ] Implement ThemeContext and CSS variable system
- [ ] Create default dark theme (polished)
- [ ] Create light theme
- [ ] Create Hacker Cabin theme (green CRT, dark wood, red accents)
- [ ] Add theme selector to sidebar/topbar
- [ ] Persist theme preference in localStorage

Deliverable: Users can switch between themes

### Phase 4: Enhanced Features

**Goal**: Polish and utilities

Tasks:
- [ ] Add keyboard navigation (Ctrl+B sidebar toggle)
- [ ] Add breadcrumbs for nested routes
- [ ] Add toast notification system
- [ ] Add error boundaries
- [ ] Add skeleton loading states
- [ ] Responsive design (mobile sidebar collapse)

Deliverable: Production-ready shell

### Phase 5: Custom Shard UIs (Future)

**Goal**: Custom UI components for complex shards

Tasks:
- [ ] ACH Matrix UI
- [ ] Graph visualization UI
- [ ] Timeline visualization UI
- [ ] Dashboard widgets

Deliverable: Full UI coverage for all shards

---

## 7. Technical Specifications

### 7.1 Package Structure

```
packages/arkham-shard-shell/
  pyproject.toml                 # Python package (minimal - just shard registration)
  shard.yaml                     # Shard manifest
  arkham_shard_shell/
    __init__.py
    shard.py                     # ShellShard class (serves static files)
    api.py                       # Theme/layout preferences API
  ui/
    package.json
    vite.config.ts
    tsconfig.json
    index.html
    src/
      main.tsx                   # Entry point
      App.tsx                    # Router setup
      Shell.tsx                  # Main shell layout

      components/
        layout/
          Sidebar.tsx
          TopBar.tsx
          ContentArea.tsx
        navigation/
          NavGroup.tsx
          NavItem.tsx
          Breadcrumbs.tsx
        common/
          Icon.tsx               # Lucide icon wrapper
          Button.tsx
          Card.tsx
          LoadingSpinner.tsx
          ErrorBoundary.tsx
        generic/
          GenericShardPage.tsx
          ShardListView.tsx
          ShardDetailView.tsx
          ApiExplorer.tsx

      themes/
        types.ts                 # Theme interface
        default.ts               # Default dark theme
        light.ts                 # Light theme
        hacker-cabin.ts          # Hacker cabin theme
        index.ts                 # Theme registry

      context/
        ThemeContext.tsx
        ShardContext.tsx
        ProjectContext.tsx
        NotificationContext.tsx

      hooks/
        useShards.ts
        useTheme.ts
        useProjects.ts
        useApi.ts

      api/
        client.ts                # Fetch wrapper
        shards.ts                # Shard API calls
        projects.ts              # Project API calls
        health.ts                # Health check API

      styles/
        globals.css              # CSS variables, reset
        shell.css                # Shell-specific styles
```

### 7.2 Key Interfaces

```typescript
// Shard manifest from API
interface ShardManifest {
  name: string;
  version: string;
  description: string;
  api_prefix: string;
  capabilities: string[];
  navigation: {
    category: string;
    order: number;
    icon: string;
    label: string;
    route: string;
    sub_routes?: SubRoute[];
  };
  ui: {
    has_custom_ui: boolean;
    list_endpoint?: string;
    detail_endpoint?: string;
    primary_action?: ActionConfig;
    components?: Record<string, string>;
  };
}

// Navigation item (derived from manifest)
interface NavItem {
  id: string;
  label: string;
  icon: string;
  route: string;
  category: string;
  order: number;
  children?: NavItem[];
}

// Theme definition
interface Theme {
  name: string;
  displayName: string;
  colors: ThemeColors;
  fonts: ThemeFonts;
  spacing: ThemeSpacing;
  effects: ThemeEffects;
}
```

### 7.3 API Endpoints Required

**Frame Extensions** (need to add):
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/frame/manifests` | GET | All shard manifests with full data |
| `/api/frame/projects` | GET | List projects |
| `/api/frame/projects/current` | GET/PUT | Get/set current project |

**Shell Endpoints** (new):
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/shell/preferences` | GET/PUT | User preferences (theme, sidebar) |

---

## 8. Shard YAML Updates Required

Each existing shard needs navigation added. Here's the plan:

| Shard | Category | Order | Icon | Route |
|-------|----------|-------|------|-------|
| Dashboard | System | 0 | LayoutDashboard | /dashboard |
| Ingest | Data | 10 | Upload | /ingest |
| Parse | Data | 11 | FileText | /parse |
| Search | Search | 20 | Search | /search |
| Embed | Search | 21 | Binary | /embed |
| ACH | Analysis | 30 | Scale | /ach |
| Contradictions | Analysis | 31 | GitCompare | /contradictions |
| Anomalies | Analysis | 32 | AlertTriangle | /anomalies |
| Timeline | Analysis | 33 | Clock | /timeline |
| Graph | Visualize | 40 | Share2 | /graph |

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Shard manifest schema changes break existing code | Medium | Medium | Version the schema, add migration script |
| Generic UI doesn't meet needs for complex shards | High | Low | Always fallback to custom UI |
| Bundle size too large | Low | Medium | Tree-shake Lucide icons, lazy load routes |
| Theme CSS conflicts with shard UIs | Medium | Medium | Shard UI takes precedence (see below) |

### 9.1 Theme vs Shard UI Conflict Resolution

**Policy**: When shell themes conflict with shard custom UIs, the **shard UI takes precedence**.

Implementation:
1. Shard custom UI components render in an **unstyled container**
2. Shell theme CSS variables are available but not forced
3. Shard can opt-in to shell theming via `ui.uses_shell_theme: true` in manifest
4. Generic UI pages always use shell theming

```yaml
# Shard opts OUT of shell theming (default for custom UI)
ui:
  has_custom_ui: true
  uses_shell_theme: false  # Default when has_custom_ui: true

# Shard opts IN to shell theming
ui:
  has_custom_ui: true
  uses_shell_theme: true   # Shard's custom UI uses shell CSS variables
```

---

## 10. Resolved Questions

| Question | Decision | Notes |
|----------|----------|-------|
| Project Management | Selector only | CRUD later if needed |
| Authentication | Not for v1 | Design for future addition |
| Offline Support | Degraded state | Shell requires Frame to function |
| Shard Hot-Reload | No | Monorepo build only |

---

## 11. Success Criteria

### Phase 1 Complete When:
- [ ] Shell renders in browser at `http://localhost:5173`
- [ ] Sidebar shows 3 shards (ACH, Ingest, Search)
- [ ] Clicking nav items changes routes
- [ ] Default dark theme applied consistently
- [ ] Placeholder content renders for each shard route
- [ ] No TypeScript errors
- [ ] No console errors
- [ ] Frame API connectivity verified (health check)

### Phase 2 Complete When:
- [ ] Sidebar generated from API response
- [ ] Generic page renders for any shard
- [ ] API explorer shows shard endpoints
- [ ] Connection status visible

### Phase 3 Complete When:
- [ ] Three themes available (default, light, hacker cabin)
- [ ] Theme persists across sessions
- [ ] Theme switch is instant (no flicker)

---

## 12. Architecture Decisions (Resolved)

### 12.1 Build/Dev Workflow

**Decision**: Option A for development, Option B for production.

```
Development:
  Shell (Vite :5173) --> proxy /api/* --> Frame (uvicorn :8105)

Production:
  Frame serves /static/* from shell/ui/dist/
  Frame serves index.html for all non-API routes (SPA routing)
```

Vite config will include proxy configuration:
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8105'
    }
  }
})
```

### 12.2 Custom UI Component Location

**Decision**: Option B - All UIs in shell package.

```
arkham-shard-shell/ui/src/
  pages/
    generic/           # Generic shard page components
    ach/               # ACH custom components (future)
    graph/             # Graph custom components (future)
    timeline/          # Timeline custom components (future)
```

Rationale: Single Vite build, simpler configuration, custom UIs are optional extensions to the shell.

### 12.3 Static File Serving (Frame Task)

**Requirement**: Frame must serve the built React SPA.

Implementation needed in `arkham_frame/main.py`:
- Serve `index.html` for all non-API routes (SPA client-side routing)
- Serve static assets from `/assets/*`
- Add to Phase 2 tasks

```python
# Example FastAPI static file serving
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Serve static assets
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

# Catch-all for SPA routing
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse("static/index.html")
```

---

## 13. Next Steps

1. **Review SHARD_MANIFEST_SCHEMA.md** - formal schema spec (if not already reviewed)
2. **Approve plan** to proceed with implementation
3. **Create package structure** for arkham-shard-shell
4. **Build Phase 1** foundation (3 shards: ACH, Ingest, Search)
5. **Iterate** through remaining phases

---

*Last Updated: 2025-12-21*
*Status: PLANNING COMPLETE - Ready for implementation approval*
