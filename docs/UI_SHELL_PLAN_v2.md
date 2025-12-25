# UI Shell Shard Implementation Plan

> Version 2.0 - Planning document for the arkham-shard-shell package

---

## Changes from v1

| Change | Rationale |
|--------|-----------|
| Phase 1 now uses Dashboard + ACH | Tests both generic UI and custom UI paths |
| Added Error Boundary specification | Prevent shard crashes from killing entire app |
| Added `useShell()` hook for shard-to-shard navigation | Clean API for cross-shard linking |
| Added responsive breakpoints | Mobile/tablet support |
| Added keyboard shortcuts | Power user support |
| Added badge polling (30s) | Dynamic sidebar indicators |
| Removed `uses_shell_theme` toggle | Shell always injects CSS variables |
| Added roadblocks table | Known risks and mitigations |
| Added command palette (Ctrl+K) to Phase 4 | Power user navigation |
| Added service worker for offline caching | Static asset caching, offline indicator |
| Decided: start dark theme (no OS detection) | Simpler, user can manually switch |
| Added pagination contract for list endpoints | Prevents 10k item lists from killing browser |
| Added badge_endpoint to sub_routes | Sub-nav items can have badges too |
| Added known limitations section | Documents v1 constraints explicitly |

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

### Related Documents

- [SHARD_MANIFEST_SCHEMA_v2.md](SHARD_MANIFEST_SCHEMA_v2.md) - Formal schema specification for shard.yaml files

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

**Action Required**: Extend Frame's `/api/shards/` endpoint to return full manifest data including navigation, capabilities, state, and UI metadata per v2 schema.

### 2.2 Shard Manifest Schema

See [SHARD_MANIFEST_SCHEMA_v2.md](SHARD_MANIFEST_SCHEMA_v2.md) for the complete specification.

Key changes in v2:
- Added `state` section for persistence strategy
- Added `navigation.badge_endpoint` for dynamic indicators
- Added `ui.list_columns` and `ui.fields` for generic UI
- Removed `ui.uses_shell_theme` - always inject CSS variables

---

## 3. Shell Architecture

### 3.1 Component Hierarchy

```
<App>
  <ThemeProvider>
    <ShellProvider>
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
    </ShellProvider>
  </ThemeProvider>
</App>
```

### 3.2 Error Isolation (NEW in v2)

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
  return (
    <div className="shard-error">
      <h2>Something went wrong in {shardName}</h2>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try Again</button>
      <button onClick={() => window.location.href = '/'}>Go to Dashboard</button>
    </div>
  );
}

// Usage in ContentArea
<ErrorBoundary
  FallbackComponent={(props) => (
    <ShardErrorFallback {...props} shardName={currentShard.name} />
  )}
  onReset={() => {
    // Clear any cached state that might have caused the error
  }}
  onError={(error, info) => {
    // Log to error tracking service
    console.error('Shard error:', currentShard.name, error, info);
  }}
>
  <Suspense fallback={<ShardLoadingSkeleton shardName={currentShard.name} />}>
    <ShardContent />
  </Suspense>
</ErrorBoundary>
```

**Loading States**:

```typescript
// components/common/ShardLoadingSkeleton.tsx
function ShardLoadingSkeleton({ shardName }: { shardName: string }) {
  return (
    <div className="shard-loading">
      <div className="skeleton-header" />
      <div className="skeleton-content">
        <div className="skeleton-line" />
        <div className="skeleton-line" />
        <div className="skeleton-line short" />
      </div>
      <div className="loading-text">Loading {shardName}...</div>
    </div>
  );
}
```

**Timeout Handling**:

```typescript
// hooks/useShardTimeout.ts
function useShardTimeout(shardName: string, timeoutMs: number = 10000) {
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setTimedOut(true), timeoutMs);
    return () => clearTimeout(timer);
  }, [shardName, timeoutMs]);

  return timedOut;
}

// Usage
const timedOut = useShardTimeout(shardName);
if (timedOut) {
  return <ShardTimeoutFallback shardName={shardName} onRetry={refetch} />;
}
```

### 3.3 Shard-to-Shard Navigation (NEW in v2)

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

const ShellContext = createContext<ShellContextValue | null>(null);

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { data: shards } = useShards();

  const navigateToShard = useCallback((shardName: string, params?: Record<string, string>) => {
    const shard = shards?.find(s => s.name === shardName);
    if (!shard) {
      console.warn(`Shard not found: ${shardName}`);
      return;
    }

    let url = shard.navigation.route;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += '?' + searchParams.toString();
    }

    navigate(url);
  }, [shards, navigate]);

  const getShardRoute = useCallback((shardName: string) => {
    const shard = shards?.find(s => s.name === shardName);
    return shard?.navigation.route || null;
  }, [shards]);

  return (
    <ShellContext.Provider value={{
      shards: shards || [],
      currentShard: /* derived from current route */,
      navigateToShard,
      getShardRoute,
    }}>
      {children}
    </ShellContext.Provider>
  );
}

// hooks/useShell.ts
export function useShell() {
  const context = useContext(ShellContext);
  if (!context) {
    throw new Error('useShell must be used within ShellProvider');
  }
  return context;
}
```

**Usage in Shard Component**:

```typescript
// In ACH component, linking to a document in Search
function EvidenceItem({ evidence }) {
  const { navigateToShard } = useShell();

  return (
    <div className="evidence-item">
      <span>{evidence.summary}</span>
      <button onClick={() => navigateToShard('search', { doc: evidence.documentId })}>
        View Source
      </button>
    </div>
  );
}
```

### 3.4 Badge Polling (NEW in v2)

The Shell polls badge endpoints for shards that define them.

**Implementation Choice**: Polling (30s interval) for v1. Simple and sufficient for badge counts.

**Error Handling**:
- `count: 0` - Hide badge (intentional, no items)
- `error/timeout` - Hide badge, log warning to console. Do not show stale data.
- Never cache badge counts across errors

**Future Enhancement**: If real-time features are added (live collaboration, instant notifications), consider upgrading to WebSocket for all real-time updates including badges.

```typescript
// hooks/useBadges.ts
interface BadgeState {
  [shardName: string]: number;
}

export function useBadges(shards: ShardManifest[]) {
  const [badges, setBadges] = useState<BadgeState>({});

  useEffect(() => {
    const shardsWithBadges = shards.filter(s => s.navigation.badge_endpoint);

    if (shardsWithBadges.length === 0) return;

    async function fetchBadges() {
      const results: BadgeState = {};

      await Promise.allSettled(
        shardsWithBadges.map(async (shard) => {
          try {
            const response = await fetch(shard.navigation.badge_endpoint!);
            if (response.ok) {
              const data = await response.json();
              results[shard.name] = data.count || 0;
            }
          } catch {
            // Silently fail - badge is optional enhancement
          }
        })
      );

      setBadges(results);
    }

    // Initial fetch
    fetchBadges();

    // Poll every 30 seconds
    const interval = setInterval(fetchBadges, 30000);

    return () => clearInterval(interval);
  }, [shards]);

  return badges;
}
```

---

## 4. Responsive Design (NEW in v2)

### 4.1 Breakpoints

| Breakpoint | Width | Sidebar Behavior |
|------------|-------|------------------|
| Desktop | >= 1024px | Always visible, fixed width (240px) |
| Tablet | 768-1023px | Collapsible, default collapsed, overlay when open |
| Mobile | < 768px | Hidden, hamburger trigger, full overlay when open |

### 4.2 CSS Implementation

```css
/* styles/responsive.css */

:root {
  --sidebar-width: 240px;
  --topbar-height: 56px;
}

/* Desktop: Sidebar always visible */
@media (min-width: 1024px) {
  .shell {
    display: grid;
    grid-template-columns: var(--sidebar-width) 1fr;
    grid-template-rows: var(--topbar-height) 1fr;
  }

  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: var(--sidebar-width);
    height: 100vh;
  }

  .content-area {
    margin-left: var(--sidebar-width);
  }

  .sidebar-toggle {
    display: none;
  }
}

/* Tablet: Collapsible sidebar */
@media (min-width: 768px) and (max-width: 1023px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: var(--sidebar-width);
    height: 100vh;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    z-index: 100;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .sidebar-overlay {
    display: none;
  }

  .sidebar.open + .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 99;
  }

  .content-area {
    margin-left: 0;
  }
}

/* Mobile: Full overlay sidebar */
@media (max-width: 767px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: 100%;
    max-width: 300px;
    height: 100vh;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    z-index: 100;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .topbar {
    padding-left: 56px; /* Room for hamburger */
  }

  .sidebar-toggle {
    position: fixed;
    left: 8px;
    top: 8px;
    z-index: 101;
  }
}
```

### 4.3 Viewport Contract for Custom UI Shards

Custom UI shards MUST respect these constraints:

1. **Never assume fixed width** - Use responsive CSS or container queries
2. **Support touch interactions** - Minimum tap target 44x44px on mobile
3. **Handle viewport changes** - Use ResizeObserver or CSS for layout shifts
4. **Respect safe areas** - Account for mobile notches/status bars

```typescript
// hooks/useViewport.ts
export function useViewport() {
  const [viewport, setViewport] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
    isMobile: window.innerWidth < 768,
    isTablet: window.innerWidth >= 768 && window.innerWidth < 1024,
    isDesktop: window.innerWidth >= 1024,
  });

  useEffect(() => {
    const handleResize = () => {
      setViewport({
        width: window.innerWidth,
        height: window.innerHeight,
        isMobile: window.innerWidth < 768,
        isTablet: window.innerWidth >= 768 && window.innerWidth < 1024,
        isDesktop: window.innerWidth >= 1024,
      });
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return viewport;
}
```

---

## 5. Keyboard Navigation (NEW in v2)

### 5.1 Global Shortcuts

| Shortcut | Action | Phase |
|----------|--------|-------|
| `Ctrl/Cmd + B` | Toggle sidebar | Phase 2 |
| `Ctrl/Cmd + K` | Open command palette (fuzzy search for shards, actions, docs) | Phase 4 |
| `Escape` | Close modals/dialogs, return focus to content | Phase 2 |
| `?` | Show keyboard shortcuts help (when not in input) | Phase 4 |

### 5.2 Navigation Shortcuts

| Shortcut | Action |
|----------|--------|
| `g then d` | Go to Dashboard |
| `g then s` | Go to Search |
| `g then a` | Go to ACH |
| `1-9` | Jump to nav item by position |

### 5.3 Implementation

```typescript
// hooks/useKeyboardNavigation.ts
import { useEffect } from 'react';
import { useShell } from './useShell';

export function useKeyboardNavigation() {
  const { navigateToShard, shards } = useShell();
  const [pendingKey, setPendingKey] = useState<string | null>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Ignore when typing in inputs
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      const isMod = e.ctrlKey || e.metaKey;

      // Ctrl/Cmd + B: Toggle sidebar
      if (isMod && e.key === 'b') {
        e.preventDefault();
        toggleSidebar();
        return;
      }

      // Ctrl/Cmd + K: Command palette (future)
      if (isMod && e.key === 'k') {
        e.preventDefault();
        openCommandPalette();
        return;
      }

      // Escape: Close modals
      if (e.key === 'Escape') {
        closeActiveModal();
        return;
      }

      // ?: Show help
      if (e.key === '?' && !e.shiftKey) {
        showKeyboardHelp();
        return;
      }

      // g + letter: Go to shard
      if (pendingKey === 'g') {
        const shortcuts: Record<string, string> = {
          'd': 'dashboard',
          's': 'search',
          'a': 'ach',
          'c': 'contradictions',
          'i': 'ingest',
        };
        const shardName = shortcuts[e.key];
        if (shardName) {
          e.preventDefault();
          navigateToShard(shardName);
        }
        setPendingKey(null);
        return;
      }

      if (e.key === 'g') {
        setPendingKey('g');
        // Clear after 1 second if no follow-up
        setTimeout(() => setPendingKey(null), 1000);
        return;
      }

      // 1-9: Jump to nav item
      const num = parseInt(e.key);
      if (num >= 1 && num <= 9) {
        const shard = shards[num - 1];
        if (shard) {
          navigateToShard(shard.name);
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [pendingKey, shards, navigateToShard]);
}
```

---

## 6. Generic UI System (EXPANDED in v2)

### 6.1 How It Works

When a shard has `has_custom_ui: false`, the Shell renders a generic page using manifest metadata.

```
+------------------------------------------+
|  [Icon] Shard Name                       |
|  Description from manifest               |
+------------------------------------------+
|  [Primary Action Form]                   |
|  +------------------------------------+  |
|  | [Field 1: ___________]             |  |
|  | [Field 2: ___________]             |  |
|  | [Submit Button]                    |  |
|  +------------------------------------+  |
+------------------------------------------+
|  Results / List View                     |
|  +------------------------------------+  |
|  | Column 1 | Column 2 | Column 3    |  |
|  |----------|----------|-------------|  |
|  | Row 1    | Data     | Badge       |  |
|  | Row 2    | Data     | Badge       |  |
|  +------------------------------------+  |
+------------------------------------------+
|  [Collapsible: Additional Actions]       |
|  [Collapsible: API Explorer]             |
+------------------------------------------+
```

### 6.2 Form Generation

Forms are generated from `ui.primary_action.fields`:

```typescript
// components/generic/GenericForm.tsx
interface GenericFormProps {
  action: ActionConfig;
  onSuccess: (result: any) => void;
}

function GenericForm({ action, onSuccess }: GenericFormProps) {
  const [formData, setFormData] = useState<Record<string, any>>(() => {
    // Initialize with defaults
    const defaults: Record<string, any> = {};
    action.fields?.forEach(field => {
      if (field.default !== undefined) {
        defaults[field.name] = field.default;
      }
    });
    return defaults;
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(action.endpoint, {
        method: action.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const result = await response.json();
      onSuccess(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="generic-form">
      {action.fields?.map(field => (
        <GenericField
          key={field.name}
          field={field}
          value={formData[field.name]}
          onChange={(value) => setFormData(prev => ({ ...prev, [field.name]: value }))}
        />
      ))}
      {error && <div className="form-error">{error}</div>}
      <button type="submit" disabled={loading}>
        {loading ? 'Loading...' : action.label}
      </button>
    </form>
  );
}
```

### 6.3 List Generation

Lists are generated from `ui.list_endpoint` and `ui.list_columns`.

**Pagination Contract**: List endpoints MUST return paginated responses:

```json
{
  "items": [...],
  "total": 1000,
  "page": 1,
  "page_size": 20
}
```

The Shell appends `?page=N&page_size=M` to the endpoint. Default page_size is 20.

```typescript
// components/generic/GenericList.tsx
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

interface GenericListProps {
  endpoint: string;
  columns: ColumnConfig[];
  onRowClick?: (row: any) => void;
}

function GenericList({ endpoint, columns, onRowClick }: GenericListProps) {
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const paginatedEndpoint = `${endpoint}?page=${page}&page_size=${pageSize}`;
  const { data, loading, error, refetch } = useFetch<PaginatedResponse<any>>(paginatedEndpoint);

  if (loading) return <TableSkeleton columns={columns.length} rows={5} />;
  if (error) return <ErrorMessage error={error} onRetry={refetch} />;
  if (!data?.items?.length) return <EmptyState message="No items found" />;

  const totalPages = Math.ceil(data.total / pageSize);

  return (
    <div className="generic-list-container">
      <table className="generic-list">
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.field} style={{ width: col.width }}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.items.map((row: any, index: number) => (
            <tr key={row.id || index} onClick={() => onRowClick?.(row)}>
              {columns.map(col => (
                <td key={col.field}>
                  <GenericCell column={col} value={row[col.field]} row={row} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Pagination controls */}
      <div className="pagination">
        <span>Showing {data.items.length} of {data.total}</span>
        <div className="pagination-controls">
          <button disabled={page === 1} onClick={() => setPage(1)}>First</button>
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Prev</button>
          <span>Page {page} of {totalPages}</span>
          <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
          <button disabled={page === totalPages} onClick={() => setPage(totalPages)}>Last</button>
        </div>
      </div>
    </div>
  );
}

function GenericCell({ column, value, row }: { column: ColumnConfig; value: any; row: any }) {
  switch (column.type) {
    case 'link':
      const href = column.link_route?.replace('{id}', row.id);
      return <Link to={href}>{value}</Link>;

    case 'date':
      return column.format === 'relative'
        ? <RelativeTime date={value} />
        : <AbsoluteTime date={value} />;

    case 'number':
      if (column.format === 'percent') return <>{(value * 100).toFixed(1)}%</>;
      return <>{value.toLocaleString()}</>;

    case 'badge':
      return <Badge value={value} />;

    case 'boolean':
      return value ? <CheckIcon /> : <XIcon />;

    default:
      return <>{value}</>;
  }
}
```

---

## 7. Theme System

### 7.1 CSS Variable Injection

The Shell always injects theme CSS variables at the `:root` level. Shards can use them or ignore them.

```typescript
// themes/types.ts
interface Theme {
  name: string;
  displayName: string;
  colors: {
    bgPrimary: string;
    bgSecondary: string;
    bgTertiary: string;
    textPrimary: string;
    textSecondary: string;
    textMuted: string;
    accentPrimary: string;
    accentSecondary: string;
    border: string;
    success: string;
    warning: string;
    error: string;
  };
  fonts: {
    mono: string;
    sans: string;
  };
  effects: {
    shadowSm: string;
    shadowMd: string;
    radiusSm: string;
    radiusMd: string;
  };
}

// themes/default.ts
export const defaultTheme: Theme = {
  name: 'default',
  displayName: 'Default Dark',
  colors: {
    bgPrimary: '#1a1a2e',
    bgSecondary: '#16213e',
    bgTertiary: '#0f3460',
    textPrimary: '#eaeaea',
    textSecondary: '#a0a0a0',
    textMuted: '#6b6b6b',
    accentPrimary: '#e94560',
    accentSecondary: '#533483',
    border: '#2a2a4a',
    success: '#4ade80',
    warning: '#fbbf24',
    error: '#f87171',
  },
  fonts: {
    mono: "'JetBrains Mono', monospace",
    sans: "'Inter', sans-serif",
  },
  effects: {
    shadowSm: '0 1px 2px rgba(0,0,0,0.3)',
    shadowMd: '0 4px 6px rgba(0,0,0,0.4)',
    radiusSm: '4px',
    radiusMd: '8px',
  },
};

// themes/hacker-cabin.ts
export const hackerCabinTheme: Theme = {
  name: 'hacker-cabin',
  displayName: 'Hacker Cabin',
  colors: {
    bgPrimary: '#1a1510',        // Dark wood
    bgSecondary: '#2a2015',      // Warmer wood
    bgTertiary: '#3a3025',       // Lighter wood
    textPrimary: '#33ff33',      // CRT green
    textSecondary: '#22cc22',    // Dimmer green
    textMuted: '#116611',        // Very dim green
    accentPrimary: '#cc3333',    // Red string
    accentSecondary: '#ff6633',  // Amber/orange
    border: '#4a4035',           // Wood grain
    success: '#33ff33',
    warning: '#ffcc00',
    error: '#ff3333',
  },
  fonts: {
    mono: "'VT323', 'Courier New', monospace",  // CRT-style font
    sans: "'VT323', 'Courier New', monospace",
  },
  effects: {
    shadowSm: '0 0 4px rgba(51,255,51,0.3)',    // Green glow
    shadowMd: '0 0 8px rgba(51,255,51,0.4)',
    radiusSm: '2px',
    radiusMd: '4px',
  },
};
```

### 7.2 Theme Application

```typescript
// context/ThemeContext.tsx
function applyTheme(theme: Theme) {
  const root = document.documentElement;

  // Colors
  root.style.setProperty('--arkham-bg-primary', theme.colors.bgPrimary);
  root.style.setProperty('--arkham-bg-secondary', theme.colors.bgSecondary);
  root.style.setProperty('--arkham-bg-tertiary', theme.colors.bgTertiary);
  root.style.setProperty('--arkham-text-primary', theme.colors.textPrimary);
  root.style.setProperty('--arkham-text-secondary', theme.colors.textSecondary);
  root.style.setProperty('--arkham-text-muted', theme.colors.textMuted);
  root.style.setProperty('--arkham-accent-primary', theme.colors.accentPrimary);
  root.style.setProperty('--arkham-accent-secondary', theme.colors.accentSecondary);
  root.style.setProperty('--arkham-border', theme.colors.border);
  root.style.setProperty('--arkham-success', theme.colors.success);
  root.style.setProperty('--arkham-warning', theme.colors.warning);
  root.style.setProperty('--arkham-error', theme.colors.error);

  // Fonts
  root.style.setProperty('--arkham-font-mono', theme.fonts.mono);
  root.style.setProperty('--arkham-font-sans', theme.fonts.sans);

  // Effects
  root.style.setProperty('--arkham-shadow-sm', theme.effects.shadowSm);
  root.style.setProperty('--arkham-shadow-md', theme.effects.shadowMd);
  root.style.setProperty('--arkham-radius-sm', theme.effects.radiusSm);
  root.style.setProperty('--arkham-radius-md', theme.effects.radiusMd);

  // Store preference
  localStorage.setItem('arkham-theme', theme.name);
}
```

---

## 8. Implementation Phases

### Phase 1: Foundation (This Sprint)

**Goal**: Working shell with 2 shards that exercise both generic and custom UI paths.

**Shard Selection**:
| Shard | Complexity | Why Selected |
|-------|------------|--------------|
| Dashboard | LOW | Uses generic UI, validates auto-generation |
| ACH | HIGH | Uses custom UI, has sub-routes, has state, complex visualization |

These two shards together exercise every part of the system.

**Tasks**:
- [ ] Create `arkham-shard-shell` package structure
- [ ] Set up Vite + React + TypeScript + React Router
- [ ] Install `react-error-boundary` package
- [ ] Implement Shell layout (sidebar, topbar, content)
- [ ] Implement error boundaries around content area
- [ ] Implement Suspense with loading skeletons
- [ ] Add basic responsive breakpoints
- [ ] Hardcode navigation for 2 shards (Dashboard, ACH)
- [ ] Implement default dark theme with CSS variables
- [ ] Add basic routing
- [ ] Create GenericShardPage for Dashboard
- [ ] Create placeholder custom UI for ACH
- [ ] Implement `useShell()` hook with `navigateToShard()`

**Deliverable**: Shell renders, both generic and custom UI paths work, error isolation verified.

### Phase 2: Frame Integration

**Goal**: Dynamic shard discovery + full generic UI + production deployment

**Tasks**:
- [ ] Extend Frame API to return full v2 manifest data
- [ ] Add route collision validation to Frame startup
- [ ] Update all shard.yaml files with v2 schema
- [ ] **Add static file serving to Frame** (serve built SPA)
- [ ] Implement dynamic sidebar generation from API
- [ ] Implement badge polling for shards with badge_endpoint
- [ ] Build complete GenericShardPage with forms and lists
- [ ] Add API explorer component
- [ ] Add connection status indicator
- [ ] Add keyboard shortcuts (Ctrl+B, Escape)

**Deliverable**: Navigation auto-generated, generic pages fully functional, production deployment ready.

### Phase 3: Theme System

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

### Phase 4: Polish

**Goal**: Production-ready UX

**Tasks**:
- [ ] Full responsive design (tablet, mobile)
- [ ] Complete keyboard navigation (g+letter, 1-9)
- [ ] **Command palette (Ctrl/Cmd+K)** - fuzzy search for shards, actions, documents
- [ ] Add breadcrumbs for nested routes
- [ ] Add toast notification system
- [ ] Add skeleton loading states for all async content
- [ ] **Service worker for offline caching** - cache static assets, show offline indicator
- [ ] Performance optimization (lazy load routes, tree-shake icons)
- [ ] Accessibility audit (focus management, ARIA)

**Deliverable**: Production-ready shell.

### Phase 5: Custom Shard UIs (Future)

**Goal**: Custom UI components for complex shards

**Tasks**:
- [ ] ACH Matrix UI (full implementation)
- [ ] Graph visualization UI
- [ ] Timeline visualization UI
- [ ] Dashboard widgets

**Deliverable**: Full UI coverage for all shards.

---

## 9. Risks and Mitigations

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

### 9.1 Known Limitations (v1)

| Limitation | Workaround |
|------------|------------|
| Manifest changes require browser refresh | User must refresh if Frame restarts or shard is installed while Shell is open |
| No hot-reload for shards | Monorepo build only; restart dev server for shard changes |
| Badge errors hide badge silently | Check console for warnings; no UI indicator for stale data |

---

## 10. Technical Specifications

### 10.1 Package Structure

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
          NavBadge.tsx
          Breadcrumbs.tsx
        common/
          Icon.tsx               # Lucide icon wrapper
          Button.tsx
          Card.tsx
          LoadingSpinner.tsx
          ShardErrorBoundary.tsx
          ShardLoadingSkeleton.tsx
        generic/
          GenericShardPage.tsx
          GenericForm.tsx
          GenericField.tsx
          GenericList.tsx
          GenericCell.tsx
          ApiExplorer.tsx

      pages/
        generic/                 # Generic shard page components
        dashboard/               # Dashboard placeholder
        ach/                     # ACH custom components

      themes/
        types.ts                 # Theme interface
        default.ts               # Default dark theme
        light.ts                 # Light theme
        hacker-cabin.ts          # Hacker cabin theme
        index.ts                 # Theme registry

      context/
        ThemeContext.tsx
        ShellContext.tsx
        ProjectContext.tsx
        NotificationContext.tsx

      hooks/
        useShards.ts
        useShell.ts
        useTheme.ts
        useProjects.ts
        useBadges.ts
        useApi.ts
        useViewport.ts
        useKeyboardNavigation.ts
        useShardTimeout.ts

      api/
        client.ts                # Fetch wrapper
        shards.ts                # Shard API calls
        projects.ts              # Project API calls
        health.ts                # Health check API

      styles/
        globals.css              # CSS variables, reset
        shell.css                # Shell-specific styles
        responsive.css           # Breakpoints
```

### 10.2 Key Interfaces

```typescript
// Shard manifest from API (v2 schema)
interface ShardManifest {
  name: string;
  version: string;
  description: string;
  entry_point: string;
  api_prefix: string;
  requires_frame: string;
  capabilities: string[];

  navigation: {
    category: string;
    order: number;
    icon: string;
    label: string;
    route: string;
    badge_endpoint?: string;
    badge_type?: 'count' | 'dot';
    sub_routes?: SubRoute[];
  };

  state?: {
    strategy: 'url' | 'local' | 'session' | 'none';
    url_params?: string[];
    local_keys?: string[];
  };

  ui?: {
    has_custom_ui: boolean;
    list_endpoint?: string;
    list_columns?: ColumnConfig[];
    detail_endpoint?: string;
    primary_action?: ActionConfig;
    actions?: ActionConfig[];
  };

  dependencies?: {
    services?: string[];
    optional?: string[];
    shards?: string[];
  };

  events?: {
    publishes?: string[];
    subscribes?: string[];
  };
}

interface ColumnConfig {
  field: string;
  label: string;
  type: 'text' | 'link' | 'number' | 'date' | 'badge' | 'boolean';
  width?: string;
  link_route?: string;
  format?: string;
}

interface FieldConfig {
  name: string;
  type: 'text' | 'textarea' | 'number' | 'checkbox' | 'select' | 'date' | 'file';
  label: string;
  required?: boolean;
  default?: any;
  placeholder?: string;
  min?: number;
  max?: number;
  options?: { value: string; label: string }[];
}

interface ActionConfig {
  label: string;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  description?: string;
  confirm?: boolean;
  confirm_message?: string;
  fields?: FieldConfig[];
}
```

### 10.3 API Endpoints Required

**Frame Extensions** (need to add):
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/frame/manifests` | GET | All shard manifests with full v2 data |
| `/api/frame/projects` | GET | List projects |
| `/api/frame/projects/current` | GET/PUT | Get/set current project |

**Shell Endpoints** (new):
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/shell/preferences` | GET/PUT | User preferences (theme, sidebar state) |

---

## 11. Success Criteria

### Phase 1 Complete When:
- [ ] Shell renders in browser at `http://localhost:5173`
- [ ] Sidebar shows 2 shards (Dashboard, ACH)
- [ ] Clicking nav items changes routes
- [ ] Default dark theme applied consistently
- [ ] Dashboard renders with generic UI (if manifest has list_endpoint)
- [ ] ACH renders with placeholder custom UI
- [ ] Error in one shard doesn't crash Shell (error boundary works)
- [ ] Loading state shows skeleton while shard loads
- [ ] `navigateToShard('ach', { id: '123' })` works
- [ ] No TypeScript errors
- [ ] No console errors
- [ ] Frame API connectivity verified (health check)

### Phase 2 Complete When:
- [ ] Sidebar generated from API response
- [ ] Generic page renders forms from `primary_action.fields`
- [ ] Generic page renders lists from `list_columns`
- [ ] Badge counts appear for shards with `badge_endpoint`
- [ ] API explorer shows shard endpoints
- [ ] Connection status visible
- [ ] Ctrl+B toggles sidebar
- [ ] Frame validates route collisions on startup
- [ ] Production build works (Frame serves static files)

### Phase 3 Complete When:
- [ ] Three themes available (default, light, hacker cabin)
- [ ] Theme persists across sessions
- [ ] Theme switch is instant (no flicker)
- [ ] All shell components use CSS variables

### Phase 4 Complete When:
- [ ] Tablet breakpoint works (sidebar collapses)
- [ ] Mobile breakpoint works (hamburger menu)
- [ ] All keyboard shortcuts work
- [ ] Breadcrumbs show for nested routes
- [ ] Toast notifications work
- [ ] Lighthouse accessibility score > 90

---

## 12. Architecture Decisions (Resolved)

### 12.1 Build/Dev Workflow

**Decision**: Vite dev server for development, Frame serves static for production.

```
Development:
  Shell (Vite :5173) --> proxy /api/* --> Frame (uvicorn :8105)

Production:
  Frame serves /static/* from shell/ui/dist/
  Frame serves index.html for all non-API routes (SPA routing)
```

Vite config:
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8105'
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  }
})
```

### 12.2 Custom UI Component Location

**Decision**: All UIs in shell package.

```
arkham-shard-shell/ui/src/
  pages/
    generic/           # Generic shard page components
    dashboard/         # Dashboard (may be generic initially)
    ach/               # ACH custom components
    graph/             # Graph custom components (future)
    timeline/          # Timeline custom components (future)
```

Rationale: Single Vite build, simpler configuration, custom UIs are optional extensions to the shell.

### 12.3 Static File Serving (Frame Task)

**Requirement**: Frame must serve the built React SPA.

Implementation needed in `arkham_frame/main.py`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# Find the built UI
UI_DIST = Path(__file__).parent.parent / "arkham-shard-shell" / "ui" / "dist"

if UI_DIST.exists():
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

    # Catch-all for SPA routing (after all API routes)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't catch /api/* routes
        if full_path.startswith("api/"):
            raise HTTPException(404)
        return FileResponse(UI_DIST / "index.html")
```

### 12.4 Error Handling Strategy

**Decision**: Use `react-error-boundary` library with per-shard boundaries.

- Each shard content area wrapped in ErrorBoundary
- ErrorBoundary catches render errors, not async errors
- Async errors caught in data fetching hooks with try/catch
- Errors logged to console (future: error tracking service)
- User can retry or navigate away

### 12.5 Theme CSS Variable Strategy

**Decision**: Shell always injects CSS variables. No opt-out toggle.

- CSS variables injected at `:root`
- Generic UI uses these variables exclusively
- Custom UI can use variables or ignore them
- Theme switch updates variables, components re-render automatically
- No Shadow DOM (complexity not worth isolation benefit)

---

## 13. Appendix: Implementation Notes

### A. Testing Error Boundaries

```typescript
// For testing: component that throws
function BuggyComponent() {
  throw new Error('Test error from BuggyComponent');
}

// In tests
render(
  <ErrorBoundary FallbackComponent={ShardErrorFallback}>
    <BuggyComponent />
  </ErrorBoundary>
);

expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
```

### B. Testing Responsive Breakpoints

Use Playwright or Cypress viewport commands:

```typescript
// Playwright
await page.setViewportSize({ width: 375, height: 667 }); // Mobile
expect(await page.locator('.sidebar-toggle').isVisible()).toBe(true);

await page.setViewportSize({ width: 1280, height: 800 }); // Desktop
expect(await page.locator('.sidebar').isVisible()).toBe(true);
```

### C. Performance Budgets

| Metric | Target |
|--------|--------|
| Initial bundle | < 200KB gzipped |
| Per-route chunk | < 50KB gzipped |
| First Contentful Paint | < 1.5s |
| Time to Interactive | < 3s |
| Lighthouse Performance | > 80 |

---

## 14. Resolved Enhancement Questions

| Question | Decision |
|----------|----------|
| Command Palette (Ctrl+K) | Yes - implement in Phase 4 |
| Offline Caching | Yes - service worker for static assets in Phase 4 |
| Dark Mode System Preference | No - start with dark theme, user can manually switch |
| Badge Update Mechanism | Polling (30s) for v1; WebSocket if real-time features added later |

---

*Last Updated: 2025-12-22*
*Status: PLANNING v2 COMPLETE - Ready for implementation approval*
