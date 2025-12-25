# UI Shell Shard Implementation Plan

> Version 3.0 - Planning document for the arkham-shard-shell package

---

## Changes from v2

| Change | Rationale |
|--------|-----------|
| **Added `useShardState` hook** | Critical: Connects React state to the Manifest's strategy (URL/Local) automatically |
| **Added Badge Aggregator** | Performance: Frame provides single `/api/frame/badges` endpoint instead of N calls |
| **Added `useToast` hook** | UX: Standard notification system for actions |
| **Added Generic Filters** | UI: Generic lists now support search, select, date range filtering |
| **Added Bulk Actions** | UI: Support for multi-select operations (Delete, Export) |
| **Added Row Actions** | UI: Per-row action buttons (Edit, View, Delete) |
| **Added Column Sorting** | UI: Click column headers to sort |
| **Updated GenericList** | Complete rewrite with filters, selection, sorting |

---

## 1. Executive Summary

Build a React/TypeScript UI shell that provides:
- Navigation sidebar (auto-generated from shard manifests)
- Top bar (project selector dropdown, connection status, settings)
- Theme system (default dark + hacker cabin)
- Generic UI templates for shards without custom UIs
- Content routing with error isolation
- Responsive layout (desktop/tablet/mobile)

**Build System**: Monorepo integration - built together with Frame and all shards.

### Decisions Made

| Question | Decision |
|----------|----------|
| Project management | Dropdown selector only (CRUD later if needed) |
| Authentication | Not for v1, design for future |
| Offline support | Degraded state display, but Shell requires Frame |
| Hot-reload shards | No - monorepo build only |
| Theme vs Shard UI conflicts | Shell always injects CSS vars; shards choose to use them |
| Phase 1 scope | 2 shards: Dashboard (generic UI) + ACH (custom UI) |
| Build/Dev workflow | Vite proxy (:5173) -> Frame (:8105) for dev; Frame serves static for prod |
| Custom UI location | All UIs in shell package (`pages/ach/`, `pages/graph/`, etc.) |
| Static file serving | Frame serves built React app (FastAPI static middleware) |
| Error isolation | Error boundaries per shard content area |
| Shard-to-shard nav | `useShell()` hook with `navigateToShard()` |
| State management | `useShardState()` hook connects YAML config to React |
| Badge polling | Frame aggregation endpoint, not per-shard polling |

### Related Documents

- [SHARD_MANIFEST_SCHEMA_v3.md](SHARD_MANIFEST_SCHEMA_v3.md) - Formal schema specification for shard.yaml files

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
| `GET /api/frame/badges` | NEEDED (v3) | Aggregated badge counts |

### 2.2 Shard Manifest Schema

See [SHARD_MANIFEST_SCHEMA_v3.md](SHARD_MANIFEST_SCHEMA_v3.md) for the complete specification.

Key additions in v3:
- `ui.list_filters` for search/filter UI
- `ui.bulk_actions` for multi-select operations
- `ui.row_actions` for per-row buttons
- `sortable` flag on columns

---

## 3. Shell Architecture

### 3.1 Component Hierarchy

```
<App>
  <ThemeProvider>
    <ShellProvider>
      <ToastProvider>
        <NotificationProvider>
          <Shell>
            <TopBar />
            <Sidebar>
              <ProjectSelector />
              <Navigation>
                <NavGroup>
                  <NavItem badge={count} />
                </NavGroup>
              </Navigation>
              <ThemeSelector />
            </Sidebar>
            <ContentArea>
              <ErrorBoundary fallback={<ShardErrorFallback />}>
                <Suspense fallback={<ShardLoadingSkeleton />}>
                  <Outlet />  {/* React Router renders shard here */}
                </Suspense>
              </ErrorBoundary>
            </ContentArea>
          </Shell>
        </NotificationProvider>
      </ToastProvider>
    </ShellProvider>
  </ThemeProvider>
</App>
```

### 3.2 Error Isolation

**Problem**: A React error in one shard's UI should not crash the entire Shell.

**Solution**: Wrap each shard's content area in an Error Boundary.

```typescript
// components/common/ShardErrorBoundary.tsx
import { ErrorBoundary } from 'react-error-boundary';

interface ShardErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
  shardName: string;
}

function ShardErrorFallback({ error, resetErrorBoundary, shardName }: ShardErrorFallbackProps) {
  const { toast } = useToast();

  useEffect(() => {
    toast.error(`Error in ${shardName}: ${error.message}`);
  }, [error]);

  return (
    <div className="shard-error">
      <h2>Something went wrong in {shardName}</h2>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try Again</button>
      <button onClick={() => window.location.href = '/'}>Go to Dashboard</button>
    </div>
  );
}
```

### 3.3 Shard-to-Shard Navigation

**Problem**: ACH wants to link to a document in Search. Hardcoding routes is brittle.

**Solution**: Shell provides a navigation helper via context.

```typescript
// context/ShellContext.tsx
interface ShellContextValue {
  shards: ShardManifest[];
  currentShard: ShardManifest | null;
  navigateToShard: (shardName: string, params?: Record<string, string>) => void;
  getShardRoute: (shardName: string) => string | null;
}

export function useShell() {
  const context = useContext(ShellContext);
  if (!context) {
    throw new Error('useShell must be used within ShellProvider');
  }
  return context;
}
```

### 3.4 State Management - `useShardState` Hook (NEW in v3)

**Problem**: The manifest defines WHERE state lives (URL, localStorage) but v2 didn't provide a React hook to actually implement this. Every shard developer would reinvent the wheel.

**Solution**: `useShardState` hook that reads the manifest's state configuration and automatically syncs to the right storage.

```typescript
// hooks/useShardState.ts
import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useShell } from '../context/ShellContext';

/**
 * Synchronizes state between React and the storage strategy defined in shard.yaml.
 *
 * @param key The state key (e.g., 'filters', 'view', 'selectedId')
 * @param defaultValue Initial value if not found in storage
 * @returns [state, setState] tuple that auto-syncs to URL/localStorage
 */
export function useShardState<T>(key: string, defaultValue: T): [T, (value: T) => void] {
  const { currentShard } = useShell();
  const [searchParams, setSearchParams] = useSearchParams();
  const [state, setState] = useState<T>(defaultValue);

  // Determine storage strategy from manifest
  const strategy = currentShard?.state?.strategy || 'none';
  const urlParams = currentShard?.state?.url_params || [];
  const localKeys = currentShard?.state?.local_keys || [];

  const isUrlParam = urlParams.includes(key);
  const isLocalKey = localKeys.includes(key);
  const storageKey = `${currentShard?.name || 'shell'}:${key}`;

  // Hydrate state on mount
  useEffect(() => {
    let initialValue: T | null = null;

    // Priority 1: URL params (if configured)
    if ((strategy === 'url' || strategy === 'session') && isUrlParam) {
      const urlValue = searchParams.get(key);
      if (urlValue !== null) {
        try {
          initialValue = JSON.parse(urlValue);
        } catch {
          initialValue = urlValue as unknown as T;
        }
      }
    }

    // Priority 2: localStorage (if configured and not found in URL)
    if (initialValue === null && isLocalKey) {
      const stored = localStorage.getItem(storageKey);
      if (stored !== null) {
        try {
          initialValue = JSON.parse(stored);
        } catch {
          initialValue = stored as unknown as T;
        }
      }
    }

    // Priority 3: sessionStorage (for session strategy)
    if (initialValue === null && strategy === 'session') {
      const stored = sessionStorage.getItem(storageKey);
      if (stored !== null) {
        try {
          initialValue = JSON.parse(stored);
        } catch {
          initialValue = stored as unknown as T;
        }
      }
    }

    if (initialValue !== null) {
      setState(initialValue);
    }
  }, [currentShard?.name]); // Re-hydrate when shard changes

  // Persist state on change
  const setShardState = useCallback((newValue: T) => {
    setState(newValue);

    const serialized = typeof newValue === 'string'
      ? newValue
      : JSON.stringify(newValue);

    // Sync to URL if configured
    if ((strategy === 'url' || strategy === 'session') && isUrlParam) {
      setSearchParams(prev => {
        if (newValue === null || newValue === undefined || newValue === defaultValue) {
          prev.delete(key);
        } else {
          prev.set(key, serialized);
        }
        return prev;
      }, { replace: true }); // Use replace to avoid polluting history
    }

    // Sync to localStorage if configured
    if (isLocalKey) {
      if (newValue === null || newValue === undefined) {
        localStorage.removeItem(storageKey);
      } else {
        localStorage.setItem(storageKey, serialized);
      }
    }

    // Sync to sessionStorage if session strategy
    if (strategy === 'session' && !isUrlParam && !isLocalKey) {
      if (newValue === null || newValue === undefined) {
        sessionStorage.removeItem(storageKey);
      } else {
        sessionStorage.setItem(storageKey, serialized);
      }
    }
  }, [strategy, isUrlParam, isLocalKey, key, storageKey, defaultValue, setSearchParams]);

  return [state, setShardState];
}
```

**Usage Examples:**

```typescript
// In a shard component - filters sync to URL automatically
function EmbedList() {
  const [filters, setFilters] = useShardState('filters', { q: '', status: '' });
  const [sort, setSort] = useShardState('sort', { field: 'created_at', order: 'desc' });

  // URL updates automatically: /embed?filters={"q":"report"}&sort={"field":"title","order":"asc"}
}

// In ACH - matrix ID syncs to URL for deep linking
function ACHMatrix() {
  const [matrixId, setMatrixId] = useShardState('matrixId', null);
  const [tab, setTab] = useShardState('tab', 'hypotheses');

  // URL: /ach?matrixId=123&tab=evidence
}

// UI preferences sync to localStorage
function ACHSettings() {
  const [zoom, setZoom] = useShardState('ach_matrix_zoom', 1.0);
  const [showTooltips, setShowTooltips] = useShardState('ach_show_tooltips', true);

  // Persists across sessions in localStorage
}
```

### 3.5 Badge Aggregation (NEW in v3)

**Problem**: v2 had the Shell polling each shard's badge endpoint individually. 10 shards = 10 requests every 30 seconds. This is noisy and inefficient.

**Solution**: Frame provides a single aggregation endpoint. Shell polls once, Frame handles the rest.

**New Frame Endpoint**: `GET /api/frame/badges`

```python
# arkham_frame/api/badges.py
@router.get("/badges")
async def get_all_badges(frame: Frame = Depends(get_frame)):
    """Aggregate badge counts from all loaded shards."""
    badges = {}

    for shard in frame.loaded_shards.values():
        manifest = shard.manifest
        nav = manifest.navigation

        # Main nav badge
        if nav.badge_endpoint:
            try:
                # Internal call to shard's badge endpoint
                count = await shard.get_badge_count()
                badges[manifest.name] = {
                    "count": count,
                    "type": nav.badge_type or "count"
                }
            except Exception:
                # Shard badge failed, skip silently
                pass

        # Sub-route badges
        for sub in nav.sub_routes or []:
            if sub.get("badge_endpoint"):
                try:
                    count = await shard.get_subroute_badge_count(sub["id"])
                    badges[f"{manifest.name}:{sub['id']}"] = {
                        "count": count,
                        "type": sub.get("badge_type", "count")
                    }
                except Exception:
                    pass

    return badges
```

**Response Format:**

```json
{
  "ach": { "count": 5, "type": "count" },
  "ach:pending": { "count": 2, "type": "count" },
  "contradictions": { "count": 0, "type": "dot" },
  "embed": { "count": 12, "type": "count" }
}
```

**Shell Implementation:**

```typescript
// hooks/useBadges.ts
interface BadgeInfo {
  count: number;
  type: 'count' | 'dot';
}

interface BadgeState {
  [key: string]: BadgeInfo;  // key is "shardName" or "shardName:subRouteId"
}

export function useBadges() {
  const [badges, setBadges] = useState<BadgeState>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchBadges() {
      try {
        const response = await fetch('/api/frame/badges');
        if (response.ok) {
          const data = await response.json();
          setBadges(data);
        }
      } catch (error) {
        console.warn('Failed to fetch badges:', error);
        // Keep existing badges on error, don't clear
      } finally {
        setLoading(false);
      }
    }

    // Initial fetch
    fetchBadges();

    // Poll every 30 seconds
    const interval = setInterval(fetchBadges, 30000);

    return () => clearInterval(interval);
  }, []);

  // Helper to get badge for a shard or sub-route
  const getBadge = useCallback((shardName: string, subRouteId?: string) => {
    const key = subRouteId ? `${shardName}:${subRouteId}` : shardName;
    return badges[key] || null;
  }, [badges]);

  return { badges, getBadge, loading };
}
```

### 3.6 Toast Notifications - `useToast` Hook (NEW in v3)

**Problem**: Actions need feedback. "Export started", "3 items deleted", "Network error". The v2 plan mentioned notifications but didn't specify the API.

**Solution**: Standard toast hook with success/error/info variants.

```typescript
// context/ToastContext.tsx
import { createContext, useContext, useState, useCallback } from 'react';

interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  duration: number;
}

interface ToastContextValue {
  toasts: Toast[];
  toast: {
    success: (message: string, options?: ToastOptions) => void;
    error: (message: string, options?: ToastOptions) => void;
    info: (message: string, options?: ToastOptions) => void;
    warning: (message: string, options?: ToastOptions) => void;
  };
  dismiss: (id: string) => void;
}

interface ToastOptions {
  duration?: number;  // ms, default 4000
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: Toast['type'], message: string, options?: ToastOptions) => {
    const id = crypto.randomUUID();
    const duration = options?.duration ?? (type === 'error' ? 6000 : 4000);

    setToasts(prev => [...prev, { id, type, message, duration }]);

    // Auto-dismiss
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, duration);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const toast = {
    success: (msg: string, opts?: ToastOptions) => addToast('success', msg, opts),
    error: (msg: string, opts?: ToastOptions) => addToast('error', msg, opts),
    info: (msg: string, opts?: ToastOptions) => addToast('info', msg, opts),
    warning: (msg: string, opts?: ToastOptions) => addToast('warning', msg, opts),
  };

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
```

**Toast Container Component:**

```typescript
// components/common/ToastContainer.tsx
function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <div className="toast-container" aria-live="polite">
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`toast toast-${toast.type}`}
          role="alert"
        >
          <span className="toast-icon">
            {toast.type === 'success' && <CheckCircle />}
            {toast.type === 'error' && <XCircle />}
            {toast.type === 'info' && <Info />}
            {toast.type === 'warning' && <AlertTriangle />}
          </span>
          <span className="toast-message">{toast.message}</span>
          <button className="toast-dismiss" onClick={() => onDismiss(toast.id)}>
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
```

**Usage:**

```typescript
function BulkDeleteButton({ selectedIds }) {
  const { toast } = useToast();

  async function handleDelete() {
    try {
      const response = await fetch('/api/embed/batch/delete', {
        method: 'DELETE',
        body: JSON.stringify({ ids: selectedIds }),
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(`${result.processed} items deleted`);
      } else {
        toast.error('Failed to delete items');
      }
    } catch (error) {
      toast.error('Network error');
    }
  }

  return <button onClick={handleDelete}>Delete {selectedIds.length} items</button>;
}
```

---

## 4. Generic UI System (COMPLETE REWRITE in v3)

### 4.1 Overview

When a shard has `has_custom_ui: false`, the Shell renders a fully-featured generic page with:
- Search and filter bar
- Sortable data table
- Row selection with bulk actions
- Per-row action buttons
- Pagination

```
+------------------------------------------+
|  [Icon] Shard Name                       |
|  Description from manifest               |
+------------------------------------------+
|  [Search...] [Status: All v] [Type: v]   |  <- Filters
+------------------------------------------+
|  [x] 3 selected  [Delete] [Export]       |  <- Bulk actions (when items selected)
+------------------------------------------+
|  [ ] | Title ^    | Status | Date    | * |  <- Sortable columns, action column
|  [x] | Document 1 | Done   | 2h ago  |...|
|  [x] | Document 2 | Pending| 1d ago  |...|
|  [ ] | Document 3 | Failed | 3d ago  |...|
+------------------------------------------+
|  Showing 1-20 of 150  [<] [1] [2] [>]    |  <- Pagination
+------------------------------------------+
```

### 4.2 GenericShardPage Component

```typescript
// components/generic/GenericShardPage.tsx
interface GenericShardPageProps {
  shard: ShardManifest;
}

export function GenericShardPage({ shard }: GenericShardPageProps) {
  const ui = shard.ui!;

  return (
    <div className="generic-shard-page">
      {/* Header */}
      <header className="shard-header">
        <Icon name={shard.navigation.icon} size={32} />
        <div>
          <h1>{shard.navigation.label}</h1>
          <p>{shard.description}</p>
        </div>
      </header>

      {/* Primary Action (if defined) */}
      {ui.primary_action && (
        <section className="primary-action-section">
          <GenericForm action={ui.primary_action} />
        </section>
      )}

      {/* List View (if list_endpoint defined) */}
      {ui.list_endpoint && (
        <section className="list-section">
          <GenericList config={ui} />
        </section>
      )}

      {/* Additional Actions */}
      {ui.actions?.length > 0 && (
        <section className="actions-section">
          <h3>Actions</h3>
          {ui.actions.map(action => (
            <GenericActionButton key={action.label} action={action} />
          ))}
        </section>
      )}
    </div>
  );
}
```

### 4.3 GenericList Component (Complete Implementation)

```typescript
// components/generic/GenericList.tsx
interface GenericListProps {
  config: UIConfig;
}

export function GenericList({ config }: GenericListProps) {
  const { toast } = useToast();
  const { currentShard } = useShell();

  // State management using useShardState for persistence
  const [filters, setFilters] = useShardState<Record<string, any>>('filters', {});
  const [sort, setSort] = useShardState<{ field: string; order: 'asc' | 'desc' } | null>('sort', null);
  const [page, setPage] = useShardState('page', 1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const pageSize = 20;
  const idField = config.id_field || 'id';

  // Build query string
  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('page_size', String(pageSize));

    // Add filter params
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        params.set(key, String(value));
      }
    });

    // Add sort params
    if (sort) {
      params.set('sort', sort.field);
      params.set('order', sort.order);
    }

    return params.toString();
  }, [page, filters, sort]);

  // Fetch data
  const endpoint = `${config.list_endpoint}?${queryParams}`;
  const { data, loading, error, refetch } = useFetch<PaginatedResponse>(endpoint);

  // Selection handlers
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (!data) return;
    const allIds = data.items.map(item => item[idField]);
    const allSelected = allIds.every(id => selectedIds.has(id));

    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(allIds));
    }
  };

  // Sort handler
  const handleSort = (field: string) => {
    setSort(prev => {
      if (prev?.field === field) {
        return { field, order: prev.order === 'asc' ? 'desc' : 'asc' };
      }
      return { field, order: 'asc' };
    });
    setPage(1); // Reset to first page on sort change
  };

  // Filter change handler
  const handleFilterChange = (param: string, value: any) => {
    setFilters(prev => ({ ...prev, [param]: value }));
    setPage(1); // Reset to first page on filter change
    setSelectedIds(new Set()); // Clear selection on filter change
  };

  // Bulk action handler
  const executeBulkAction = async (action: BulkAction) => {
    if (action.confirm) {
      const message = action.confirm_message?.replace('{count}', String(selectedIds.size))
        || `Are you sure you want to ${action.label.toLowerCase()} ${selectedIds.size} items?`;
      if (!window.confirm(message)) return;
    }

    try {
      const response = await fetch(action.endpoint, {
        method: action.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: Array.from(selectedIds) }),
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(result.message || `${action.label} completed`);
        setSelectedIds(new Set());
        refetch();
      } else {
        const error = await response.text();
        toast.error(`${action.label} failed: ${error}`);
      }
    } catch (err) {
      toast.error(`${action.label} failed: Network error`);
    }
  };

  // Row action handler
  const executeRowAction = async (action: RowAction, row: any) => {
    const id = row[idField];

    if (action.type === 'link') {
      const route = action.route.replace('{id}', id);
      // Use React Router navigation
      return;
    }

    if (action.confirm) {
      const message = action.confirm_message || `Are you sure?`;
      if (!window.confirm(message)) return;
    }

    try {
      const endpoint = action.endpoint.replace('{id}', id);
      const response = await fetch(endpoint, { method: action.method });

      if (response.ok) {
        toast.success(`${action.label} completed`);
        refetch();
      } else {
        toast.error(`${action.label} failed`);
      }
    } catch (err) {
      toast.error(`${action.label} failed: Network error`);
    }
  };

  // Render
  if (loading && !data) return <TableSkeleton columns={config.list_columns?.length || 4} rows={5} />;
  if (error) return <ErrorMessage error={error} onRetry={refetch} />;

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;
  const hasSelection = selectedIds.size > 0;
  const selectable = config.selectable !== false && (config.bulk_actions?.length || 0) > 0;

  return (
    <div className="generic-list">
      {/* Filters Bar */}
      {config.list_filters && config.list_filters.length > 0 && (
        <div className="filters-bar">
          {config.list_filters.map(filter => (
            <GenericFilter
              key={filter.name}
              config={filter}
              value={filters[filter.param] ?? ''}
              onChange={value => handleFilterChange(filter.param, value)}
            />
          ))}
        </div>
      )}

      {/* Bulk Actions Bar */}
      {hasSelection && config.bulk_actions && (
        <div className="bulk-actions-bar">
          <span className="selection-count">{selectedIds.size} selected</span>
          <div className="bulk-actions">
            {config.bulk_actions.map(action => (
              <button
                key={action.label}
                className={`btn btn-${action.style || 'default'}`}
                onClick={() => executeBulkAction(action)}
              >
                {action.icon && <Icon name={action.icon} size={16} />}
                {action.label}
              </button>
            ))}
          </div>
          <button className="btn-link" onClick={() => setSelectedIds(new Set())}>
            Clear selection
          </button>
        </div>
      )}

      {/* Data Table */}
      <table className="data-table">
        <thead>
          <tr>
            {selectable && (
              <th className="checkbox-col">
                <input
                  type="checkbox"
                  checked={data?.items.length > 0 && data.items.every(item => selectedIds.has(item[idField]))}
                  onChange={toggleSelectAll}
                />
              </th>
            )}
            {config.list_columns?.map(col => (
              <th
                key={col.field}
                style={{ width: col.width }}
                className={col.sortable ? 'sortable' : ''}
                onClick={() => col.sortable && handleSort(col.field)}
              >
                {col.label}
                {col.sortable && sort?.field === col.field && (
                  <span className="sort-indicator">
                    {sort.order === 'asc' ? ' ^' : ' v'}
                  </span>
                )}
              </th>
            ))}
            {config.row_actions && <th className="actions-col">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {data?.items.map(row => (
            <tr key={row[idField]} className={selectedIds.has(row[idField]) ? 'selected' : ''}>
              {selectable && (
                <td className="checkbox-col">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(row[idField])}
                    onChange={() => toggleSelect(row[idField])}
                  />
                </td>
              )}
              {config.list_columns?.map(col => (
                <td key={col.field}>
                  <GenericCell column={col} value={row[col.field]} row={row} idField={idField} />
                </td>
              ))}
              {config.row_actions && (
                <td className="actions-col">
                  <RowActionsMenu
                    actions={config.row_actions}
                    row={row}
                    onAction={action => executeRowAction(action, row)}
                  />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Empty State */}
      {data?.items.length === 0 && (
        <EmptyState message="No items found" />
      )}

      {/* Pagination */}
      {data && data.total > pageSize && (
        <div className="pagination">
          <span className="pagination-info">
            Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, data.total)} of {data.total}
          </span>
          <div className="pagination-controls">
            <button disabled={page === 1} onClick={() => setPage(1)}>First</button>
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Prev</button>
            <span className="page-indicator">Page {page} of {totalPages}</span>
            <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
            <button disabled={page === totalPages} onClick={() => setPage(totalPages)}>Last</button>
          </div>
        </div>
      )}
    </div>
  );
}
```

### 4.4 Filter Components

```typescript
// components/generic/GenericFilter.tsx
interface GenericFilterProps {
  config: FilterConfig;
  value: any;
  onChange: (value: any) => void;
}

export function GenericFilter({ config, value, onChange }: GenericFilterProps) {
  switch (config.type) {
    case 'search':
      return (
        <div className="filter filter-search">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder={config.label}
            value={value}
            onChange={e => onChange(e.target.value)}
          />
          {value && (
            <button className="clear-btn" onClick={() => onChange('')}>
              <X size={14} />
            </button>
          )}
        </div>
      );

    case 'select':
      return (
        <div className="filter filter-select">
          <label>{config.label}</label>
          <select value={value} onChange={e => onChange(e.target.value)}>
            {config.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      );

    case 'date_range':
      return (
        <div className="filter filter-date-range">
          <label>{config.label}</label>
          <input
            type="date"
            value={value?.start || ''}
            onChange={e => onChange({ ...value, start: e.target.value })}
          />
          <span>to</span>
          <input
            type="date"
            value={value?.end || ''}
            onChange={e => onChange({ ...value, end: e.target.value })}
          />
        </div>
      );

    case 'boolean':
      return (
        <div className="filter filter-boolean">
          <label>
            <input
              type="checkbox"
              checked={value === true || value === 'true'}
              onChange={e => onChange(e.target.checked)}
            />
            {config.label}
          </label>
        </div>
      );

    default:
      return null;
  }
}
```

### 4.5 Row Actions Menu

```typescript
// components/generic/RowActionsMenu.tsx
interface RowActionsMenuProps {
  actions: RowAction[];
  row: any;
  onAction: (action: RowAction) => void;
}

export function RowActionsMenu({ actions, row, onAction }: RowActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="row-actions-menu" ref={menuRef}>
      <button
        className="menu-trigger"
        onClick={() => setOpen(!open)}
        aria-label="Row actions"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <MoreVertical size={16} />
      </button>
      {open && (
        <div className="menu-dropdown" role="menu">
          {actions.map(action => (
            <button
              key={action.label}
              role="menuitem"
              className={`menu-item ${action.style === 'danger' ? 'danger' : ''}`}
              aria-label={action.label}
              onClick={() => {
                setOpen(false);
                onAction(action);
              }}
            >
              {action.icon && <Icon name={action.icon} size={14} />}
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## 5. Implementation Phases (Updated for v3)

### Phase 1: Foundation

**Goal**: Working shell with 2 shards that exercise both generic and custom UI paths.

**Shard Selection**:
| Shard | Complexity | Why Selected |
|-------|------------|--------------|
| Dashboard | LOW | Uses generic UI, validates auto-generation |
| ACH | HIGH | Uses custom UI, has sub-routes, has state, complex visualization |

**Tasks**:
- [ ] Create `arkham-shard-shell` package structure
- [ ] Set up Vite + React + TypeScript + React Router
- [ ] Install `react-error-boundary` package
- [ ] Implement Shell layout (sidebar, topbar, content)
- [ ] Implement error boundaries around content area
- [ ] Implement Suspense with loading skeletons
- [ ] **Implement `useShardState` hook** (Critical for ACH deep linking)
- [ ] **Implement `useToast` hook and ToastProvider**
- [ ] Add basic responsive breakpoints
- [ ] Hardcode navigation for 2 shards (Dashboard, ACH)
- [ ] Implement default dark theme with CSS variables
- [ ] Add basic routing
- [ ] Create placeholder GenericShardPage for Dashboard
- [ ] Create placeholder custom UI for ACH
- [ ] Implement `useShell()` hook with `navigateToShard()`

**Deliverable**: Shell renders, useShardState works, toast notifications work, error isolation verified.

### Phase 2: Frame Integration + Generic UI v1

**Goal**: Dynamic shard discovery, badge aggregation, basic generic UI

**Tasks**:
- [ ] Extend Frame API to return full v3 manifest data
- [ ] **Add `/api/frame/badges` aggregation endpoint to Frame**
- [ ] Add route collision validation to Frame startup
- [ ] Update all shard.yaml files with v3 schema
- [ ] Add static file serving to Frame
- [ ] Implement dynamic sidebar generation from API
- [ ] **Implement badge aggregation (single poll to Frame)**
- [ ] Build GenericList with pagination (no filters yet)
- [ ] Build GenericForm for primary actions
- [ ] Add connection status indicator
- [ ] Add keyboard shortcuts (Ctrl+B, Escape)

**Deliverable**: Navigation auto-generated, badges work efficiently, basic generic pages functional.

### Phase 3: Generic UI v2 (Filters, Bulk, Row Actions)

**Goal**: Full-featured generic UI system

**Tasks**:
- [ ] **Implement filter components** (Search, Select, DateRange, Boolean)
- [ ] **Implement bulk action bar** (selection, actions, clear)
- [ ] **Implement row actions menu** (dropdown per row)
- [ ] **Implement column sorting** (click to sort, sort indicators)
- [ ] Update list endpoints to support `?sort=field&order=asc`
- [ ] Add filter state persistence via `useShardState`
- [ ] Test with Dashboard shard (should now be fully usable)

**Deliverable**: Generic UI is production-ready with all v3 features.

### Phase 4: Theme System

**Goal**: Swappable themes with persistence

**Tasks**:
- [ ] Implement ThemeContext and CSS variable system
- [ ] Create default dark theme (polished)
- [ ] Create light theme
- [ ] Create Hacker Cabin theme (green CRT, dark wood, red accents)
- [ ] Add theme selector to sidebar
- [ ] Persist theme preference in localStorage
- [ ] Add theme transition animations (no flicker)

**Deliverable**: Users can switch between themes.

### Phase 5: Polish

**Goal**: Production-ready UX

**Tasks**:
- [ ] Full responsive design (tablet, mobile)
- [ ] Complete keyboard navigation (g+letter, 1-9)
- [ ] **Command palette (Ctrl/Cmd+K)** - fuzzy search for shards, actions, and recent documents (via Frame search endpoint)
- [ ] Add breadcrumbs for nested routes
- [ ] Refine toast notification styling
- [ ] Add skeleton loading states for all async content
- [ ] **Service worker for offline caching** - cache static assets, show offline indicator
- [ ] Performance optimization (lazy load routes, tree-shake icons)
- [ ] Accessibility audit (focus management, ARIA)

**Deliverable**: Production-ready shell.

### Phase 6: Custom Shard UIs (Future)

**Goal**: Custom UI components for complex shards

**Tasks**:
- [ ] ACH Matrix UI (full implementation)
- [ ] Graph visualization UI
- [ ] Timeline visualization UI
- [ ] Dashboard widgets

**Deliverable**: Full UI coverage for all shards.

---

## 6. Keyboard Navigation

### 6.1 Global Shortcuts

| Shortcut | Action | Phase |
|----------|--------|-------|
| `Ctrl/Cmd + B` | Toggle sidebar | Phase 2 |
| `Ctrl/Cmd + K` | Open command palette | Phase 5 |
| `Escape` | Close modals/dialogs, return focus to content | Phase 2 |
| `?` | Show keyboard shortcuts help (when not in input) | Phase 5 |

### 6.2 Navigation Shortcuts

| Shortcut | Action |
|----------|--------|
| `g then d` | Go to Dashboard |
| `g then s` | Go to Search |
| `g then a` | Go to ACH |
| `1-9` | Jump to nav item by position |

---

## 7. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Lazy loading race conditions | High | Medium | Test with slow network simulation, add timeouts |
| Theme CSS bleeding between shards | High | Medium | Use CSS variables (not direct styles), test theme switch thoroughly |
| Route collisions between shards | Medium | High | Frame validates on startup, fail loudly |
| Generic UI not flexible enough | High | Medium | Build Dashboard + Search with it before finalizing, iterate schema |
| Mobile layout breaks custom UI shards | High | Medium | Define viewport contract, require responsive design |
| Shard upgrade breaks shell | Medium | High | Manifest versioning, shell validates manifest version |
| Bundle size bloat | Medium | Medium | Measure after 5 shards, code-split routes, tree-shake icons |
| Error boundary doesn't catch async errors | Medium | Medium | Use error boundaries + try/catch in data fetching hooks |
| Generic UI too inflexible for real shards | High | High | Build Dashboard + Search with it first; accept that some shards need custom UI |
| `useShardState` causes URL bloat | Medium | Low | Use short param names, omit default values from URL |

### 7.1 Known Limitations (v1)

| Limitation | Workaround |
|------------|------------|
| Manifest changes require browser refresh | User must refresh if Frame restarts or shard is installed while Shell is open |
| No hot-reload for shards | Monorepo build only; restart dev server for shard changes |
| Badge errors hide badge silently | Check console for warnings; no UI indicator for stale data |
| Complex filters (multi-value) are verbose in URL | Consider compressing filter state in future |

---

## 8. Success Criteria

### Phase 1 Complete When:
- [ ] Shell renders in browser at `http://localhost:5173`
- [ ] Sidebar shows 2 shards (Dashboard, ACH)
- [ ] Clicking nav items changes routes
- [ ] Default dark theme applied consistently
- [ ] **`useShardState` persists state to URL correctly**
- [ ] **Toast notifications appear and auto-dismiss**
- [ ] Error in one shard doesn't crash Shell (error boundary works)
- [ ] Loading state shows skeleton while shard loads
- [ ] `navigateToShard('ach', { matrixId: '123' })` works
- [ ] No TypeScript errors
- [ ] No console errors
- [ ] Frame API connectivity verified (health check)

### Phase 2 Complete When:
- [ ] Sidebar generated from API response
- [ ] **Badge counts load from single `/api/frame/badges` call**
- [ ] Generic page renders forms from `primary_action.fields`
- [ ] Generic page renders lists with pagination
- [ ] Connection status visible
- [ ] Ctrl+B toggles sidebar
- [ ] Frame validates route collisions on startup
- [ ] Production build works (Frame serves static files)

### Phase 3 Complete When:
- [ ] **Search filter works** (type, press enter or debounce, results filter)
- [ ] **Select filter works** (dropdown changes, list reloads)
- [ ] **Row selection works** (checkbox, select all)
- [ ] **Bulk actions work** (delete multiple, with confirmation)
- [ ] **Row actions work** (dropdown menu per row)
- [ ] **Column sorting works** (click header, indicator shows)
- [ ] **Filters persist in URL** (reload page, filters restored)

### Phase 4 Complete When:
- [ ] Three themes available (default, light, hacker cabin)
- [ ] Theme persists across sessions
- [ ] Theme switch is instant (no flicker)

### Phase 5 Complete When:
- [ ] Tablet breakpoint works (sidebar collapses)
- [ ] Mobile breakpoint works (hamburger menu)
- [ ] Command palette works (Ctrl+K opens, fuzzy search works)
- [ ] All keyboard shortcuts work
- [ ] Breadcrumbs show for nested routes
- [ ] Toast notifications styled nicely
- [ ] Lighthouse accessibility score > 90

---

## 9. Resolved Enhancement Questions

| Question | Decision |
|----------|----------|
| Command Palette (Ctrl+K) | Yes - implement in Phase 5 |
| Offline Caching | Yes - service worker for static assets in Phase 5 |
| Dark Mode System Preference | No - start with dark theme, user can manually switch |
| Badge Update Mechanism | Frame aggregation endpoint (single call), polling 30s |
| State persistence hook | Yes - `useShardState` connects YAML config to React |
| List filtering | Yes - via `list_filters` in manifest |
| Bulk actions | Yes - via `bulk_actions` in manifest |
| Row actions | Yes - via `row_actions` in manifest |
| Toast notifications | Yes - `useToast` hook with success/error/info/warning |

---

*Last Updated: 2025-12-22*
*Status: PLANNING v3 COMPLETE - Ready for implementation approval*
