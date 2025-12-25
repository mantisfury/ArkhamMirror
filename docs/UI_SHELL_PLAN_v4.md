# UI Shell Shard Implementation Plan

> Version 4.0 - Planning document for the arkham-shard-shell package

---

## Changes from v3

| Change | Rationale |
|--------|-----------|
| **Redesigned URL state management** | v3 had a collision: `useShardState('filters', {})` vs individual `param: q`. Now uses flat URL params following nuqs patterns. |
| **Added `useUrlParams` hook** | Replaces complex `useShardState` for URL params. Manages multiple flat params, not JSON objects. |
| **Simplified `useShardState`** | Now only handles localStorage/sessionStorage. URL params use `useUrlParams`. |
| **Auto-infer URL params from filters** | Removed redundancy: Shell auto-treats `list_filters[].param` as URL params. No need to declare in `state.url_params`. |
| **Added explicit serialization strategy** | Primitives go directly to URL. Only objects/arrays use JSON encoding. |
| **Added form validation** | Added `pattern` (regex) and `error_message` to form fields. |
| **Added ConfirmDialog component** | Replaced `window.confirm()` with themed, accessible dialog. |
| **Documented Hybrid Mode as Phase 6** | Acknowledged limitation of all-or-nothing UI choice. |

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
| URL State | `useUrlParams()` hook with flat params (not JSON objects) |
| Local State | `useLocalState()` hook for localStorage persistence |
| Badge polling | Frame aggregation endpoint, not per-shard polling |
| Confirmations | Custom `ConfirmDialog` component, not `window.confirm()` |

### Related Documents

- [SHARD_MANIFEST_SCHEMA_v4.md](SHARD_MANIFEST_SCHEMA_v4.md) - Formal schema specification for shard.yaml files

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
| `GET /api/frame/badges` | NEEDED | Aggregated badge counts |

### 2.2 Shard Manifest Schema

See [SHARD_MANIFEST_SCHEMA_v4.md](SHARD_MANIFEST_SCHEMA_v4.md) for the complete specification.

Key additions in v4:
- Auto-inferred URL params from `list_filters`
- Form field `pattern` and `error_message` validation
- `custom_components` for hybrid UI mode (Phase 6)

---

## 3. Shell Architecture

### 3.1 Component Hierarchy

```
<App>
  <ThemeProvider>
    <ShellProvider>
      <ToastProvider>
        <ConfirmProvider>
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
        </ConfirmProvider>
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

### 3.4 State Management - REDESIGNED in v4

v3 had a design collision: `useShardState('filters', {})` would create JSON blobs in URLs like `?filters={"q":"moon"}`, but the manifest defined individual params like `param: q`.

**v4 Solution**: Separate hooks for different storage strategies, following [nuqs](https://nuqs.dev) patterns for URL state.

#### 3.4.1 `useUrlParams` Hook - Flat URL Parameters

Manages multiple URL parameters as flat key-value pairs. NO JSON encoding for primitives.

```typescript
// hooks/useUrlParams.ts
import { useSearchParams } from 'react-router-dom';
import { useCallback, useMemo } from 'react';

type ParamValue = string | number | boolean | null;
type ParamDefaults<T extends Record<string, ParamValue>> = T;

/**
 * Manages multiple flat URL parameters with type safety.
 * Follows nuqs patterns: primitives go directly to URL, no JSON blobs.
 *
 * @example
 * const [params, setParams] = useUrlParams({
 *   q: '',
 *   status: 'all',
 *   page: 1,
 *   showArchived: false
 * });
 * // URL: ?q=search&status=pending&page=2&showArchived=true
 */
export function useUrlParams<T extends Record<string, ParamValue>>(
  defaults: ParamDefaults<T>
): [T, (updates: Partial<T>) => void, (key: keyof T) => void] {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse current URL params with type coercion
  const params = useMemo(() => {
    const result = { ...defaults } as T;

    for (const key of Object.keys(defaults) as (keyof T)[]) {
      const urlValue = searchParams.get(key as string);
      if (urlValue === null) continue;

      const defaultValue = defaults[key];

      // Type-aware parsing based on default value type
      if (typeof defaultValue === 'number') {
        const parsed = Number(urlValue);
        if (!isNaN(parsed)) {
          result[key] = parsed as T[keyof T];
        }
      } else if (typeof defaultValue === 'boolean') {
        result[key] = (urlValue === 'true') as T[keyof T];
      } else {
        // String (or null treated as string)
        result[key] = urlValue as T[keyof T];
      }
    }

    return result;
  }, [searchParams, defaults]);

  // Update params - only non-default values go to URL
  const setParams = useCallback((updates: Partial<T>) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);

      for (const [key, value] of Object.entries(updates)) {
        const defaultValue = defaults[key as keyof T];

        // Remove from URL if value equals default (keeps URL clean)
        if (value === defaultValue || value === null || value === undefined) {
          next.delete(key);
        } else {
          // Serialize primitives directly (no JSON.stringify)
          next.set(key, String(value));
        }
      }

      return next;
    }, { replace: true });
  }, [defaults, setSearchParams]);

  // Clear a single param
  const clearParam = useCallback((key: keyof T) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.delete(key as string);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  return [params, setParams, clearParam];
}
```

**Key Design Decisions:**

1. **Primitives go directly to URL** - `?page=2` not `?page="2"`
2. **Type coercion based on defaults** - If default is `1` (number), parse as number
3. **Default values omitted from URL** - Keeps URLs clean and shareable
4. **No JSON blobs** - Each param is its own key-value pair

#### 3.4.2 `useLocalState` Hook - localStorage Persistence

For UI preferences that persist across sessions but don't belong in URLs.

```typescript
// hooks/useLocalState.ts
import { useState, useEffect, useCallback } from 'react';

/**
 * Persists state to localStorage with the shard name as prefix.
 *
 * @example
 * const [zoom, setZoom] = useLocalState('ach', 'matrix_zoom', 1.0);
 * // Stored as: localStorage['ach:matrix_zoom'] = '1.0'
 */
export function useLocalState<T>(
  shardName: string,
  key: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const storageKey = `${shardName}:${key}`;

  // Initialize from localStorage or default
  const [state, setState] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored !== null) {
        return JSON.parse(stored);
      }
    } catch {
      // Invalid JSON, use default
    }
    return defaultValue;
  });

  // Persist to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
    } catch (error) {
      console.warn(`Failed to persist ${storageKey}:`, error);
    }
  }, [state, storageKey]);

  // Functional updates support
  const setLocalState = useCallback((value: T | ((prev: T) => T)) => {
    setState(prev => {
      const next = typeof value === 'function' ? (value as (prev: T) => T)(prev) : value;
      return next;
    });
  }, []);

  return [state, setLocalState];
}
```

#### 3.4.3 Usage Examples

```typescript
// In GenericList - filters as flat URL params
function GenericList({ config }: GenericListProps) {
  // Build defaults from manifest filter definitions
  const filterDefaults = useMemo(() => {
    const defaults: Record<string, string | number | boolean> = {};
    for (const filter of config.list_filters || []) {
      if (filter.type === 'search' || filter.type === 'select') {
        defaults[filter.param] = '';
      } else if (filter.type === 'boolean') {
        defaults[filter.param] = false;
      }
    }
    defaults.page = 1;
    defaults.sort = '';
    defaults.order = 'asc';
    return defaults;
  }, [config.list_filters]);

  const [params, setParams] = useUrlParams(filterDefaults);
  // URL: ?q=report&status=pending&page=2&sort=created_at&order=desc
}

// In ACH - specific params for deep linking
function ACHMatrix() {
  const [params, setParams] = useUrlParams({
    matrixId: '',
    tab: 'hypotheses',
    hypothesisId: ''
  });
  // URL: /ach?matrixId=123&tab=evidence&hypothesisId=456
}

// UI preferences in localStorage
function ACHSettings() {
  const [zoom, setZoom] = useLocalState('ach', 'matrix_zoom', 1.0);
  const [showTooltips, setShowTooltips] = useLocalState('ach', 'show_tooltips', true);
  // localStorage: ach:matrix_zoom = "1.0", ach:show_tooltips = "true"
}
```

### 3.5 Badge Aggregation

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

### 3.6 Toast Notifications - `useToast` Hook

**Problem**: Actions need feedback. "Export started", "3 items deleted", "Network error".

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

### 3.7 Confirmation Dialogs - NEW in v4

**Problem**: v3 used `window.confirm()` which is ugly, not themeable, and blocks the main thread.

**Solution**: Custom `ConfirmDialog` component with promise-based API.

```typescript
// context/ConfirmContext.tsx
interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<{
    options: ConfirmOptions;
    resolve: (value: boolean) => void;
  } | null>(null);

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise(resolve => {
      setState({ options, resolve });
    });
  }, []);

  const handleConfirm = () => {
    state?.resolve(true);
    setState(null);
  };

  const handleCancel = () => {
    state?.resolve(false);
    setState(null);
  };

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {state && (
        <ConfirmDialog
          {...state.options}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const context = useContext(ConfirmContext);
  if (!context) {
    throw new Error('useConfirm must be used within ConfirmProvider');
  }
  return context.confirm;
}
```

**ConfirmDialog Component:**

```typescript
// components/common/ConfirmDialog.tsx
interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  onCancel
}: ConfirmDialogProps) {
  // Trap focus within dialog
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onCancel]);

  return (
    <div className="confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <div className="confirm-dialog" ref={dialogRef}>
        <h2 id="confirm-title">{title}</h2>
        <p>{message}</p>
        <div className="confirm-actions">
          <button className="btn btn-secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            className={`btn ${variant === 'danger' ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            autoFocus
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Usage:**

```typescript
function BulkDeleteButton({ selectedIds }) {
  const confirm = useConfirm();
  const { toast } = useToast();

  async function handleDelete() {
    const confirmed = await confirm({
      title: 'Delete Items',
      message: `Are you sure you want to delete ${selectedIds.length} items? This cannot be undone.`,
      confirmLabel: 'Delete',
      variant: 'danger'
    });

    if (!confirmed) return;

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

## 4. Generic UI System

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
  const confirm = useConfirm();
  const { currentShard } = useShell();

  // Build filter defaults from manifest - FLAT params, not a single object
  const filterDefaults = useMemo(() => {
    const defaults: Record<string, string | number | boolean> = {
      page: 1,
      sort: '',
      order: 'asc' as const,
    };

    for (const filter of config.list_filters || []) {
      if (filter.type === 'boolean') {
        defaults[filter.param] = false;
      } else if (filter.type === 'date_range') {
        defaults[filter.param_start!] = '';
        defaults[filter.param_end!] = '';
      } else {
        defaults[filter.param] = '';
      }
    }

    return defaults;
  }, [config.list_filters]);

  // URL state - flat params automatically synced
  const [params, setParams] = useUrlParams(filterDefaults);

  // Local UI state (not in URL)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const pageSize = 20;
  const idField = config.id_field || 'id';

  // Build query string from flat params
  const queryString = useMemo(() => {
    const urlParams = new URLSearchParams();
    urlParams.set('page', String(params.page));
    urlParams.set('page_size', String(pageSize));

    // Add all non-empty filter params
    for (const [key, value] of Object.entries(params)) {
      if (key === 'page') continue;
      if (value !== '' && value !== false && value !== filterDefaults[key]) {
        urlParams.set(key, String(value));
      }
    }

    return urlParams.toString();
  }, [params, filterDefaults]);

  // Fetch data
  const endpoint = `${config.list_endpoint}?${queryString}`;
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
    if (params.sort === field) {
      setParams({ order: params.order === 'asc' ? 'desc' : 'asc' });
    } else {
      setParams({ sort: field, order: 'asc', page: 1 });
    }
  };

  // Filter change handler
  const handleFilterChange = (param: string, value: string | number | boolean) => {
    setParams({ [param]: value, page: 1 });
    setSelectedIds(new Set()); // Clear selection on filter change
  };

  // Bulk action handler - uses confirm dialog instead of window.confirm
  const executeBulkAction = async (action: BulkAction) => {
    if (action.confirm) {
      const message = action.confirm_message?.replace('{count}', String(selectedIds.size))
        || `Are you sure you want to ${action.label.toLowerCase()} ${selectedIds.size} items?`;

      const confirmed = await confirm({
        title: action.label,
        message,
        confirmLabel: action.label,
        variant: action.style === 'danger' ? 'danger' : 'default'
      });

      if (!confirmed) return;
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
      const confirmed = await confirm({
        title: action.label,
        message: action.confirm_message || 'Are you sure?',
        confirmLabel: action.label,
        variant: action.style === 'danger' ? 'danger' : 'default'
      });

      if (!confirmed) return;
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
              value={params[filter.param] ?? ''}
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
                {col.sortable && params.sort === col.field && (
                  <span className="sort-indicator">
                    {params.order === 'asc' ? ' ^' : ' v'}
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
            Showing {(params.page - 1) * pageSize + 1}-{Math.min(params.page * pageSize, data.total)} of {data.total}
          </span>
          <div className="pagination-controls">
            <button disabled={params.page === 1} onClick={() => setParams({ page: 1 })}>First</button>
            <button disabled={params.page === 1} onClick={() => setParams({ page: params.page - 1 })}>Prev</button>
            <span className="page-indicator">Page {params.page} of {totalPages}</span>
            <button disabled={params.page === totalPages} onClick={() => setParams({ page: params.page + 1 })}>Next</button>
            <button disabled={params.page === totalPages} onClick={() => setParams({ page: totalPages })}>Last</button>
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

### 4.6 Form Validation - NEW in v4

Forms now support pattern validation.

```typescript
// components/generic/GenericForm.tsx
interface FormFieldConfig {
  name: string;
  type: 'text' | 'select' | 'textarea' | 'number' | 'email';
  label: string;
  required?: boolean;
  min?: number;
  max?: number;
  pattern?: string;      // NEW: Regex pattern
  error_message?: string; // NEW: Custom error message
  default?: any;
  options?: Array<{ value: string; label: string }>;
}

function validateField(value: any, config: FormFieldConfig): string | null {
  if (config.required && !value) {
    return `${config.label} is required`;
  }

  if (typeof value === 'string' && config.pattern) {
    const regex = new RegExp(config.pattern);
    if (!regex.test(value)) {
      return config.error_message || `${config.label} is invalid`;
    }
  }

  if (typeof value === 'number') {
    if (config.min !== undefined && value < config.min) {
      return `${config.label} must be at least ${config.min}`;
    }
    if (config.max !== undefined && value > config.max) {
      return `${config.label} must be at most ${config.max}`;
    }
  }

  return null;
}

export function GenericForm({ action }: { action: ActionConfig }) {
  const { toast } = useToast();
  const [values, setValues] = useState<Record<string, any>>(() => {
    const initial: Record<string, any> = {};
    for (const field of action.fields) {
      initial[field.name] = field.default ?? '';
    }
    return initial;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    for (const field of action.fields) {
      const error = validateField(values[field.name], field);
      if (error) {
        newErrors[field.name] = error;
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    setSubmitting(true);
    try {
      const response = await fetch(action.endpoint, {
        method: action.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });

      if (response.ok) {
        toast.success(`${action.label} completed`);
      } else {
        const error = await response.text();
        toast.error(`${action.label} failed: ${error}`);
      }
    } catch (err) {
      toast.error(`${action.label} failed: Network error`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="generic-form">
      {action.description && <p className="form-description">{action.description}</p>}

      {action.fields.map(field => (
        <div key={field.name} className={`form-field ${errors[field.name] ? 'has-error' : ''}`}>
          <label htmlFor={field.name}>
            {field.label}
            {field.required && <span className="required">*</span>}
          </label>

          {field.type === 'select' ? (
            <select
              id={field.name}
              value={values[field.name]}
              onChange={e => setValues(v => ({ ...v, [field.name]: e.target.value }))}
            >
              {field.options?.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          ) : field.type === 'textarea' ? (
            <textarea
              id={field.name}
              value={values[field.name]}
              onChange={e => setValues(v => ({ ...v, [field.name]: e.target.value }))}
            />
          ) : (
            <input
              id={field.name}
              type={field.type}
              value={values[field.name]}
              onChange={e => setValues(v => ({ ...v, [field.name]: e.target.value }))}
            />
          )}

          {errors[field.name] && (
            <span className="error-message">{errors[field.name]}</span>
          )}
        </div>
      ))}

      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? 'Submitting...' : action.label}
      </button>
    </form>
  );
}
```

---

## 5. Implementation Phases (Updated for v4)

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
- [ ] **Implement `useUrlParams` hook** (flat URL params, nuqs-style)
- [ ] **Implement `useLocalState` hook** (localStorage persistence)
- [ ] **Implement `useToast` hook and ToastProvider**
- [ ] **Implement `useConfirm` hook and ConfirmProvider** (replaces window.confirm)
- [ ] Add basic responsive breakpoints
- [ ] Hardcode navigation for 2 shards (Dashboard, ACH)
- [ ] Implement default dark theme with CSS variables
- [ ] Add basic routing
- [ ] Create placeholder GenericShardPage for Dashboard
- [ ] Create placeholder custom UI for ACH
- [ ] Implement `useShell()` hook with `navigateToShard()`

**Deliverable**: Shell renders, URL params work correctly, toast and confirm dialogs work, error isolation verified.

### Phase 2: Frame Integration + Generic UI v1

**Goal**: Dynamic shard discovery, badge aggregation, basic generic UI

**Tasks**:
- [ ] Extend Frame API to return full v4 manifest data
- [ ] **Add `/api/frame/badges` aggregation endpoint to Frame**
- [ ] Add route collision validation to Frame startup
- [ ] Update all shard.yaml files with v4 schema
- [ ] Add static file serving to Frame
- [ ] Implement dynamic sidebar generation from API
- [ ] **Implement badge aggregation (single poll to Frame)**
- [ ] Build GenericList with pagination (no filters yet)
- [ ] Build GenericForm for primary actions with pattern validation
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
- [ ] **Auto-infer URL params from list_filters** (no redundant state config)
- [ ] Update list endpoints to support `?sort=field&order=asc`
- [ ] Test with Dashboard shard (should now be fully usable)

**Deliverable**: Generic UI is production-ready with all v4 features.

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

### Phase 6: Hybrid UI Mode (Future)

**Goal**: Allow custom components within generic UI.

**Problem**: With the current all-or-nothing approach, a developer using Generic UI who needs ONE custom dropdown has to rewrite everything as Custom UI.

**Solution**: Allow shards to register custom components that inject into Generic UI slots.

```yaml
# shard.yaml - FUTURE
ui:
  primary_action:
    fields:
      - name: project
        type: custom
        component: ProjectSelector  # Maps to React component
```

**Implementation Notes**:
- Requires a component registry system
- Shards would export React components from a known path
- Shell dynamically imports and renders them
- Need to define clear props contract for custom components

**Tasks** (Future):
- [ ] Design component registry system
- [ ] Define custom component props contract
- [ ] Implement dynamic component loading
- [ ] Add `type: custom` support to form fields
- [ ] Add `type: custom` support to list columns
- [ ] Document custom component API for shard developers

**Deliverable**: Shards can extend Generic UI with custom components without full ejection.

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
| Generic UI too inflexible for real shards | High | High | Phase 6 Hybrid Mode provides escape hatch |
| URL param bloat | Low | Low | Only non-default values in URL, use short param names |

### 7.1 Known Limitations (v1)

| Limitation | Workaround |
|------------|------------|
| Manifest changes require browser refresh | User must refresh if Frame restarts or shard is installed while Shell is open |
| No hot-reload for shards | Monorepo build only; restart dev server for shard changes |
| Badge errors hide badge silently | Check console for warnings; no UI indicator for stale data |
| No hybrid UI mode | Phase 6 will add this; for now, use Custom UI if you need any custom components |

---

## 8. Success Criteria

### Phase 1 Complete When:
- [ ] Shell renders in browser at `http://localhost:5173`
- [ ] Sidebar shows 2 shards (Dashboard, ACH)
- [ ] Clicking nav items changes routes
- [ ] Default dark theme applied consistently
- [ ] **`useUrlParams` correctly manages flat URL params** (`?q=moon&page=2` not `?filters=...`)
- [ ] **Toast notifications appear and auto-dismiss**
- [ ] **Confirm dialogs work (not window.confirm)**
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
- [ ] **Form validation works with `pattern` and `error_message`**
- [ ] Generic page renders lists with pagination
- [ ] Connection status visible
- [ ] Ctrl+B toggles sidebar
- [ ] Frame validates route collisions on startup
- [ ] Production build works (Frame serves static files)

### Phase 3 Complete When:
- [ ] **Search filter works** (type, press enter or debounce, results filter)
- [ ] **Select filter works** (dropdown changes, list reloads)
- [ ] **Row selection works** (checkbox, select all)
- [ ] **Bulk actions work** (delete multiple, with confirmation dialog)
- [ ] **Row actions work** (dropdown menu per row)
- [ ] **Column sorting works** (click header, indicator shows)
- [ ] **Filters persist in URL** (reload page, filters restored)
- [ ] **No redundant param declaration** (Shell auto-infers from list_filters)

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
| URL State management | `useUrlParams` hook with flat params (nuqs-style) |
| Local state persistence | `useLocalState` hook for localStorage |
| List filtering | Yes - via `list_filters` in manifest |
| Bulk actions | Yes - via `bulk_actions` in manifest |
| Row actions | Yes - via `row_actions` in manifest |
| Toast notifications | Yes - `useToast` hook with success/error/info/warning |
| Confirmation dialogs | Custom `ConfirmDialog`, not `window.confirm()` |
| Form validation | Yes - `pattern` and `error_message` fields |
| Hybrid UI mode | Phase 6 - allow custom components in generic UI |

---

## 10. References

- [nuqs - Type-safe URL state management](https://nuqs.dev) - Inspiration for `useUrlParams` design
- [LogRocket - URL State Management](https://blog.logrocket.com/url-state-usesearchparams/) - Best practices
- [React Router State Management](https://reactrouter.com/explanation/state-management) - Official patterns

---

*Last Updated: 2025-12-22*
*Status: PLANNING v4 COMPLETE - Ready for implementation approval*
