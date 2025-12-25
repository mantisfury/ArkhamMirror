# UI Shell Implementation Reference

> Full code implementations for UI_SHELL_PLAN_v5

---

## Quick Start for AI Implementation

### Implementation Order

1. **Create package structure**
   ```
   arkham-shard-shell/
   ├── src/
   │   ├── hooks/
   │   │   ├── useUrlParams.ts
   │   │   ├── useLocalState.ts
   │   │   ├── useBadges.ts
   │   │   └── useFetch.ts
   │   ├── context/
   │   │   ├── ShellContext.tsx
   │   │   ├── ToastContext.tsx
   │   │   ├── ConfirmContext.tsx
   │   │   └── BadgeContext.tsx
   │   ├── components/
   │   │   ├── common/
   │   │   │   ├── ConfirmDialog.tsx
   │   │   │   ├── ShardErrorBoundary.tsx
   │   │   │   ├── BadgeStatusIndicator.tsx
   │   │   │   └── Icon.tsx
   │   │   └── generic/
   │   │       ├── GenericShardPage.tsx
   │   │       ├── GenericList.tsx
   │   │       ├── GenericFilter.tsx
   │   │       ├── DateRangeFilter.tsx
   │   │       ├── GenericForm.tsx
   │   │       └── RowActionsMenu.tsx
   │   └── App.tsx
   └── package.json
   ```

2. **Implement hooks** (in order, no dependencies between them):
   - `useFetch` - Generic data fetching with error state (NEVER throws)
   - `useUrlParams` - URL state management
   - `useLocalState` - localStorage persistence
   - `useBadges` - Badge polling with error indicator

3. **Implement contexts** (in order):
   - `ToastContext` - Toast notifications (no dependencies)
   - `ConfirmContext` - Confirmation dialogs (no dependencies)
   - `BadgeContext` - Badge state with error tracking (no dependencies)
   - `ShellContext` - Shell navigation (depends on router)

4. **Implement components** (in order):
   - `Icon` - Dynamic Lucide icon renderer (used by all other components)
   - `ConfirmDialog` - Used by ConfirmContext
   - `ShardErrorBoundary` - Error isolation
   - `BadgeStatusIndicator` - Shows warning when badges stale
   - `GenericFilter` - Filter inputs (search, select, boolean) - handles empty options
   - `DateRangeFilter` - Separate component for date range (flat params)
   - `GenericForm` - Form with validation (uses ToastContext)
   - `RowActionsMenu` - Row action dropdown
   - `GenericList` - Full list (selection persists across pages, clears on filter/sort)
   - `GenericShardPage` - Page wrapper (uses GenericList, GenericForm)

5. **Wire up routing** with React Router, wrap in providers

### Key Dependencies

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "react-error-boundary": "^4.0.0",
    "lucide-react": "^0.294.0"
  }
}
```

### Provider Nesting Order

```tsx
<ThemeProvider>
  <ShellProvider>
    <ToastProvider>
      <ConfirmProvider>
        <BadgeProvider>
          <Shell>
            <Outlet />
          </Shell>
        </BadgeProvider>
      </ConfirmProvider>
    </ToastProvider>
  </ShellProvider>
</ThemeProvider>
```

---

## Hooks

### useUrlParams.ts

```typescript
import { useSearchParams } from 'react-router-dom';
import { useCallback, useMemo } from 'react';

type ParamValue = string | number | boolean | null;
type ParamDefaults<T extends Record<string, ParamValue>> = T;

export function useUrlParams<T extends Record<string, ParamValue>>(
  defaults: ParamDefaults<T>
): [T, (updates: Partial<T>) => void, (key: keyof T) => void] {
  const [searchParams, setSearchParams] = useSearchParams();

  const params = useMemo(() => {
    const result = { ...defaults } as T;

    for (const key of Object.keys(defaults) as (keyof T)[]) {
      const urlValue = searchParams.get(key as string);
      if (urlValue === null) continue;

      const defaultValue = defaults[key];

      if (typeof defaultValue === 'number') {
        const parsed = Number(urlValue);
        if (!isNaN(parsed)) {
          result[key] = parsed as T[keyof T];
        }
      } else if (typeof defaultValue === 'boolean') {
        result[key] = (urlValue === 'true') as T[keyof T];
      } else {
        result[key] = urlValue as T[keyof T];
      }
    }

    return result;
  }, [searchParams, defaults]);

  const setParams = useCallback((updates: Partial<T>) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);

      for (const [key, value] of Object.entries(updates)) {
        const defaultValue = defaults[key as keyof T];

        if (value === null || value === undefined) {
          next.delete(key);
        } else if (typeof value === 'boolean') {
          // v5.1: Booleans are ALWAYS explicit (true/false), never omitted
          // This supports filters with default: true
          next.set(key, String(value));
        } else if (value === defaultValue) {
          // Non-boolean defaults are omitted to keep URLs clean
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      }

      return next;
    }, { replace: true });
  }, [defaults, setSearchParams]);

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

### useLocalState.ts

```typescript
import { useState, useEffect, useCallback } from 'react';

export function useLocalState<T>(
  shardName: string,
  key: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const storageKey = `${shardName}:${key}`;

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

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
    } catch (error) {
      console.warn(`Failed to persist ${storageKey}:`, error);
    }
  }, [state, storageKey]);

  const setLocalState = useCallback((value: T | ((prev: T) => T)) => {
    setState(prev => {
      const next = typeof value === 'function' ? (value as (prev: T) => T)(prev) : value;
      return next;
    });
  }, []);

  return [state, setLocalState];
}
```

### useFetch.ts

**Async Hook Error Contract:** All async hooks MUST return `{ data, loading, error }` and NEVER throw during render.

```typescript
import { useState, useEffect, useCallback, useRef } from 'react';

interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

/**
 * Generic data fetching hook.
 * NEVER throws - always returns error state.
 */
export function useFetch<T>(url: string | null): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    if (!url) {
      setLoading(false);
      return;
    }

    // Abort previous request
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(url, {
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      setData(result);
      setError(null);
    } catch (err) {
      // Don't set error for aborted requests
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      setError(err instanceof Error ? err : new Error('Unknown error'));
      // Keep existing data on error (stale-while-revalidate pattern)
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    fetchData();
    return () => abortRef.current?.abort();
  }, [fetchData]);

  const refetch = useCallback(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch };
}
```

### useBadges.ts

**Returns `hasError` for UI indicator when badge data may be stale.**

```typescript
import { useState, useEffect, useCallback, useRef } from 'react';

interface BadgeInfo {
  count: number;
  type: 'count' | 'dot';
}

interface BadgeState {
  [key: string]: BadgeInfo;
}

interface UseBadgesResult {
  badges: BadgeState;
  getBadge: (shardName: string, subRouteId?: string) => BadgeInfo | null;
  loading: boolean;
  hasError: boolean;
  lastSuccessTime: Date | null;
}

/**
 * Badge polling hook with error tracking.
 * NEVER throws - returns hasError for UI indication.
 *
 * STALE-WHILE-REVALIDATE PATTERN:
 * - On success: update badges, clear error
 * - On failure: KEEP existing badges, set hasError
 * - Badges are NEVER cleared on error
 */
export function useBadges(): UseBadgesResult {
  const [badges, setBadges] = useState<BadgeState>({});
  const [loading, setLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [lastSuccessTime, setLastSuccessTime] = useState<Date | null>(null);

  useEffect(() => {
    async function fetchBadges() {
      try {
        const response = await fetch('/api/frame/badges');
        if (response.ok) {
          const data = await response.json();
          // SUCCESS: update badges and clear error state
          setBadges(data);
          setHasError(false);
          setLastSuccessTime(new Date());
        } else {
          // NON-OK RESPONSE: keep existing badges (stale-while-revalidate)
          // Only set error flag - do NOT clear badges
          setHasError(true);
          console.warn('Badge fetch failed:', response.status);
        }
      } catch (error) {
        // NETWORK ERROR: keep existing badges (stale-while-revalidate)
        // Only set error flag - do NOT clear badges
        setHasError(true);
        console.warn('Badge fetch error:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchBadges();
    const interval = setInterval(fetchBadges, 30000);
    return () => clearInterval(interval);
  }, []);

  const getBadge = useCallback((shardName: string, subRouteId?: string) => {
    const key = subRouteId ? `${shardName}:${subRouteId}` : shardName;
    return badges[key] || null;
  }, [badges]);

  return { badges, getBadge, loading, hasError, lastSuccessTime };
}
```

---

## Context Providers

### ShellContext.tsx

```typescript
import { createContext, useContext } from 'react';

interface ShardManifest {
  name: string;
  navigation: { label: string; icon: string; route: string };
  // ... full manifest type
}

interface ShellContextValue {
  shards: ShardManifest[];
  currentShard: ShardManifest | null;
  navigateToShard: (shardName: string, params?: Record<string, string>) => void;
  getShardRoute: (shardName: string) => string | null;
}

const ShellContext = createContext<ShellContextValue | null>(null);

export function useShell() {
  const context = useContext(ShellContext);
  if (!context) {
    throw new Error('useShell must be used within ShellProvider');
  }
  return context;
}
```

### ToastContext.tsx

```typescript
import { createContext, useContext, useState, useCallback } from 'react';

interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  duration: number;
}

interface ToastOptions {
  duration?: number;
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

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: Toast['type'], message: string, options?: ToastOptions) => {
    const id = crypto.randomUUID();
    const duration = options?.duration ?? (type === 'error' ? 6000 : 4000);

    setToasts(prev => [...prev, { id, type, message, duration }]);

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

### ConfirmContext.tsx

```typescript
import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

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

---

## Components

### ShardErrorBoundary.tsx

```typescript
import { ErrorBoundary } from 'react-error-boundary';
import { useEffect } from 'react';

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

### ConfirmDialog.tsx

```typescript
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

### BadgeStatusIndicator.tsx

**Shows warning when badge data may be stale (sidebar footer).**

```typescript
import { AlertTriangle } from 'lucide-react';
import { useBadges } from '../hooks/useBadges';

/**
 * Small indicator for sidebar footer showing badge fetch status.
 * Shows warning dot with tooltip when hasError is true.
 */
export function BadgeStatusIndicator() {
  const { hasError, lastSuccessTime } = useBadges();

  if (!hasError) return null;

  const timeAgo = lastSuccessTime
    ? formatTimeAgo(lastSuccessTime)
    : 'unknown';

  return (
    <div
      className="badge-status-indicator warning"
      title={`Badge data may be stale. Last updated: ${timeAgo}`}
      role="status"
      aria-label="Badge data may be stale"
    >
      <AlertTriangle size={12} />
    </div>
  );
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return date.toLocaleDateString();
}
```

### GenericShardPage.tsx

```typescript
interface GenericShardPageProps {
  shard: ShardManifest;
}

export function GenericShardPage({ shard }: GenericShardPageProps) {
  const ui = shard.ui!;

  return (
    <div className="generic-shard-page">
      <header className="shard-header">
        <Icon name={shard.navigation.icon} size={32} />
        <div>
          <h1>{shard.navigation.label}</h1>
          <p>{shard.description}</p>
        </div>
      </header>

      {ui.primary_action && (
        <section className="primary-action-section">
          <GenericForm action={ui.primary_action} />
        </section>
      )}

      {ui.list_endpoint && (
        <section className="list-section">
          <GenericList config={ui} />
        </section>
      )}

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

### GenericList.tsx

```typescript
interface GenericListProps {
  config: UIConfig;
}

export function GenericList({ config }: GenericListProps) {
  const { toast } = useToast();
  const confirm = useConfirm();
  const { currentShard } = useShell();

  // Build filter defaults from manifest
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

  const [params, setParams] = useUrlParams(filterDefaults);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const pageSize = 20;
  const idField = config.id_field || 'id';

  // Build query string
  const queryString = useMemo(() => {
    const urlParams = new URLSearchParams();
    urlParams.set('page', String(params.page));
    urlParams.set('page_size', String(pageSize));

    for (const [key, value] of Object.entries(params)) {
      if (key === 'page') continue;
      if (value !== '' && value !== false && value !== filterDefaults[key]) {
        urlParams.set(key, String(value));
      }
    }

    return urlParams.toString();
  }, [params, filterDefaults]);

  const endpoint = `${config.list_endpoint}?${queryString}`;
  const { data, loading, error, refetch } = useFetch<PaginatedResponse>(endpoint);

  // Selection
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (!data) return;
    const allIds = data.items.map(item => item[idField]);
    const allSelected = allIds.every(id => selectedIds.has(id));
    setSelectedIds(allSelected ? new Set() : new Set(allIds));
  };

  // Sort - clears selection (user intent changed)
  const handleSort = (field: string) => {
    setSelectedIds(new Set()); // v5.1: Clear selection on sort change
    if (params.sort === field) {
      setParams({ order: params.order === 'asc' ? 'desc' : 'asc' });
    } else {
      setParams({ sort: field, order: 'asc', page: 1 });
    }
  };

  // Filter - clears selection (results changed)
  const handleFilterChange = (param: string, value: string | number | boolean) => {
    setSelectedIds(new Set()); // v5.1: Clear selection on filter change
    setParams({ [param]: value, page: 1 });
  };

  // Page change - selection PERSISTS (v5.1: enables multi-page bulk operations)
  const handlePageChange = (newPage: number) => {
    // NOTE: Do NOT clear selection here - users need to select across pages
    setParams({ page: newPage });
  };

  // Bulk action
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

  // Row action
  const executeRowAction = async (action: RowAction, row: any) => {
    const id = row[idField];

    if (action.type === 'link') {
      const route = action.route.replace('{id}', id);
      return; // Use React Router navigation
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

  if (loading && !data) return <TableSkeleton columns={config.list_columns?.length || 4} rows={5} />;
  if (error) return <ErrorMessage error={error} onRetry={refetch} />;

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;
  const hasSelection = selectedIds.size > 0;
  const selectable = config.selectable !== false && (config.bulk_actions?.length || 0) > 0;

  return (
    <div className="generic-list">
      {/* Filters */}
      {config.list_filters && config.list_filters.length > 0 && (
        <div className="filters-bar">
          {config.list_filters.map(filter => {
            // Date range uses separate component with two flat params
            if (filter.type === 'date_range') {
              return (
                <DateRangeFilter
                  key={filter.name}
                  config={filter}
                  startValue={params[filter.param_start!] as string ?? ''}
                  endValue={params[filter.param_end!] as string ?? ''}
                  onStartChange={value => handleFilterChange(filter.param_start!, value)}
                  onEndChange={value => handleFilterChange(filter.param_end!, value)}
                />
              );
            }
            // All other filter types
            return (
              <GenericFilter
                key={filter.name}
                config={filter}
                value={params[filter.param] ?? ''}
                onChange={value => handleFilterChange(filter.param, value)}
              />
            );
          })}
        </div>
      )}

      {/* Bulk Actions */}
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

      {/* Table */}
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
      {data?.items.length === 0 && <EmptyState message="No items found" />}

      {/* Pagination - uses handlePageChange to preserve selection across pages */}
      {data && data.total > pageSize && (
        <div className="pagination">
          <span className="pagination-info">
            Showing {(params.page - 1) * pageSize + 1}-{Math.min(params.page * pageSize, data.total)} of {data.total}
            {selectedIds.size > 0 && (
              <span className="selection-indicator"> ({selectedIds.size} selected across pages)</span>
            )}
          </span>
          <div className="pagination-controls">
            <button disabled={params.page === 1} onClick={() => handlePageChange(1)}>First</button>
            <button disabled={params.page === 1} onClick={() => handlePageChange(params.page - 1)}>Prev</button>
            <span className="page-indicator">Page {params.page} of {totalPages}</span>
            <button disabled={params.page === totalPages} onClick={() => handlePageChange(params.page + 1)}>Next</button>
            <button disabled={params.page === totalPages} onClick={() => handlePageChange(totalPages)}>Last</button>
          </div>
        </div>
      )}
    </div>
  );
}
```

### GenericFilter.tsx

**Handles search, select, and boolean filters. Date ranges use separate DateRangeFilter.**

```typescript
interface GenericFilterProps {
  config: FilterConfig;
  value: string | boolean;
  onChange: (value: string | boolean) => void;
}

/**
 * Generic filter for search, select, and boolean types.
 * NOTE: date_range filters must use DateRangeFilter component instead.
 */
export function GenericFilter({ config, value, onChange }: GenericFilterProps) {
  switch (config.type) {
    case 'search':
      return (
        <div className="filter filter-search">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder={config.label}
            value={value as string}
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
      // Handle empty options array (edge case)
      if (!config.options || config.options.length === 0) {
        return (
          <div className="filter filter-select">
            <label>{config.label}</label>
            <select disabled>
              <option>No options available</option>
            </select>
          </div>
        );
      }
      return (
        <div className="filter filter-select">
          <label>{config.label}</label>
          <select value={value as string} onChange={e => onChange(e.target.value)}>
            {config.options.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
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

    case 'date_range':
      // DateRangeFilter must be used for date_range - it requires two separate params
      console.warn('date_range filter type must use DateRangeFilter component');
      return null;

    default:
      return null;
  }
}
```

### DateRangeFilter.tsx

**Date ranges ALWAYS use two separate flat URL params, never an object.**

```typescript
interface DateRangeFilterProps {
  config: {
    label: string;
    param_start: string;
    param_end: string;
  };
  startValue: string;
  endValue: string;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
}

/**
 * Date range filter with two SEPARATE flat URL params.
 *
 * URL: ?from=2024-01-01&to=2024-12-31
 * NOT: ?dateRange={"start":"2024-01-01","end":"2024-12-31"}
 */
export function DateRangeFilter({
  config,
  startValue,
  endValue,
  onStartChange,
  onEndChange,
}: DateRangeFilterProps) {
  return (
    <div className="filter filter-date-range">
      <label>{config.label}</label>
      <input
        type="date"
        value={startValue}
        onChange={e => onStartChange(e.target.value)}
        aria-label={`${config.label} start date`}
      />
      <span className="date-separator">to</span>
      <input
        type="date"
        value={endValue}
        onChange={e => onEndChange(e.target.value)}
        aria-label={`${config.label} end date`}
      />
      {(startValue || endValue) && (
        <button
          className="clear-btn"
          onClick={() => {
            onStartChange('');
            onEndChange('');
          }}
          aria-label="Clear date range"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}
```

### Icon.tsx

**Dynamic Lucide icon component for manifest-driven icon names.**

```typescript
import * as LucideIcons from 'lucide-react';
import { LucideProps } from 'lucide-react';

interface IconProps extends LucideProps {
  name: string;
}

/**
 * Renders a Lucide icon by name.
 * Falls back to HelpCircle if icon not found.
 *
 * Usage: <Icon name="Trash2" size={16} />
 */
export function Icon({ name, ...props }: IconProps) {
  // Get icon component from Lucide
  const LucideIcon = (LucideIcons as Record<string, React.ComponentType<LucideProps>>)[name];

  if (!LucideIcon) {
    // Fallback for invalid icon names - don't crash, show placeholder
    console.warn(`Icon "${name}" not found in Lucide icons`);
    return <LucideIcons.HelpCircle {...props} />;
  }

  return <LucideIcon {...props} />;
}
```

**Note:** This uses dynamic import from lucide-react. For production, consider tree-shaking by importing only used icons if bundle size is a concern.

---

### RowActionsMenu.tsx

```typescript
interface RowActionsMenuProps {
  actions: RowAction[];
  row: any;
  onAction: (action: RowAction) => void;
}

export function RowActionsMenu({ actions, row, onAction }: RowActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

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

### GenericForm.tsx

```typescript
interface FormFieldConfig {
  name: string;
  type: 'text' | 'select' | 'textarea' | 'number' | 'email';
  label: string;
  required?: boolean;
  min?: number;
  max?: number;
  pattern?: string;
  error_message?: string;
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

## Frame API

### badges.py

```python
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
                count = await shard.get_badge_count()
                badges[manifest.name] = {
                    "count": count,
                    "type": nav.badge_type or "count"
                }
            except Exception:
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

**Response format:**

```json
{
  "ach": { "count": 5, "type": "count" },
  "ach:pending": { "count": 2, "type": "count" },
  "contradictions": { "count": 0, "type": "dot" },
  "embed": { "count": 12, "type": "count" }
}
```

---

*Implementation Reference for UI_SHELL_PLAN_v5.1 - Critical fixes for multi-page selection and boolean defaults 2025-12-22*
