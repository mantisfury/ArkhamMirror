# UI Shell Shard Implementation Plan v4.1

> Condensed planning document - see [UI_SHELL_IMPL_REF.md](UI_SHELL_IMPL_REF.md) for full code

---

## Quick Reference

| Aspect | Decision |
|--------|----------|
| Build | Monorepo, Vite + React + TypeScript + React Router |
| Dev | Vite `:5173` -> Frame `:8105` proxy |
| Prod | Frame serves static React build |
| URL State | `useUrlParams()` - flat params, nuqs-style |
| Local State | `useLocalState()` - localStorage with shard prefix |
| Badges | Single `/api/frame/badges` poll (30s) |
| Confirmations | `useConfirm()` hook, not `window.confirm()` |
| Toasts | `useToast()` with success/error/info/warning |
| Error Isolation | `react-error-boundary` per shard content |
| Custom UI Location | `pages/ach/`, `pages/graph/`, etc. in shell package |
| Phase 1 Shards | Dashboard (generic), ACH (custom) |

---

## 1. Architecture

### Component Hierarchy

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
                  <NavGroup><NavItem badge={count} /></NavGroup>
                </Navigation>
                <ThemeSelector />
              </Sidebar>
              <ContentArea>
                <ErrorBoundary fallback={<ShardErrorFallback />}>
                  <Suspense fallback={<ShardLoadingSkeleton />}>
                    <Outlet />
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

### Frame API Endpoints

| Endpoint | Status | Purpose |
|----------|--------|---------|
| `GET /api/shards/` | EXISTS | List shards (name, version, loaded) |
| `GET /api/shards/{name}` | EXISTS | Shard details + manifest |
| `GET /api/shards/{name}/routes` | EXISTS | API routes |
| `GET /api/frame/projects` | NEEDED | List projects |
| `GET /api/frame/projects/current` | NEEDED | Current project |
| `GET /api/frame/badges` | NEEDED | Aggregated badge counts |

---

## 2. Core Hooks

### `useUrlParams<T>(defaults: T)` - Flat URL State

```typescript
// Returns: [params: T, setParams: (updates: Partial<T>) => void, clearParam: (key) => void]
const [params, setParams] = useUrlParams({ q: '', status: 'all', page: 1 });
// URL: ?q=search&status=pending&page=2
```

**Rules:**
- Type coercion from defaults (number default = parse as number)
- Default values omitted from URL
- No JSON blobs - each param is flat key-value

### `useLocalState(shardName, key, default)` - localStorage

```typescript
const [zoom, setZoom] = useLocalState('ach', 'matrix_zoom', 1.0);
// localStorage: ach:matrix_zoom = "1.0"
```

### `useShell()` - Navigation Context

```typescript
interface ShellContextValue {
  shards: ShardManifest[];
  currentShard: ShardManifest | null;
  navigateToShard: (shardName: string, params?: Record<string, string>) => void;
  getShardRoute: (shardName: string) => string | null;
}
```

### `useToast()` - Notifications

```typescript
const { toast } = useToast();
toast.success('Saved');
toast.error('Failed', { duration: 6000 });
toast.info('Processing...');
toast.warning('Check input');
```

### `useConfirm()` - Dialogs

```typescript
const confirm = useConfirm();
const ok = await confirm({
  title: 'Delete Items',
  message: `Delete ${count} items?`,
  confirmLabel: 'Delete',
  variant: 'danger'
});
```

### `useBadges()` - Badge Aggregation

```typescript
const { getBadge } = useBadges();
const badge = getBadge('ach');           // main nav
const sub = getBadge('ach', 'pending');  // sub-route
// badge: { count: 5, type: 'count' | 'dot' } | null
```

---

## 3. Generic UI System

When `has_custom_ui: false`, Shell renders:

```
+------------------------------------------+
|  [Icon] Shard Name                       |
|  Description                             |
+------------------------------------------+
|  [Search...] [Status: v] [Type: v]       |  <- list_filters
+------------------------------------------+
|  [x] 3 selected  [Delete] [Export]       |  <- bulk_actions (when selected)
+------------------------------------------+
|  [ ] | Title ^   | Status | Date    | * |  <- list_columns + row_actions
|  [x] | Doc 1     | Done   | 2h ago  |...|
+------------------------------------------+
|  Showing 1-20 of 150  [<] [1] [2] [>]    |
+------------------------------------------+
```

### Components

| Component | Props | Purpose |
|-----------|-------|---------|
| `GenericShardPage` | `{ shard }` | Full page wrapper |
| `GenericList` | `{ config: UIConfig }` | Table with filters, selection, pagination |
| `GenericForm` | `{ action: ActionConfig }` | Form with validation |
| `GenericFilter` | `{ config, value, onChange }` | Filter by type (search/select/boolean/date_range) |
| `RowActionsMenu` | `{ actions, row, onAction }` | Per-row action dropdown |

### Filter Types

| Type | Param | Renders |
|------|-------|---------|
| `search` | `param: q` | Text input with clear button |
| `select` | `param: status` | Dropdown from `options[]` |
| `boolean` | `param: archived` | Checkbox |
| `date_range` | `param_start/param_end` | Two date inputs |

### Form Validation

Fields support `pattern` (regex) and `error_message`:

```yaml
fields:
  - name: email
    type: email
    pattern: "^[^@]+@[^@]+$"
    error_message: "Invalid email format"
```

---

## 4. Implementation Phases

### Phase 1: Foundation

**Goal:** Working shell with Dashboard (generic) + ACH (custom)

| Task | Details |
|------|---------|
| Package setup | `arkham-shard-shell`, Vite + React + TS + React Router |
| Shell layout | Sidebar, topbar, content area |
| Error isolation | `react-error-boundary` around content |
| Suspense | Loading skeletons |
| `useUrlParams` | Flat URL params, nuqs-style |
| `useLocalState` | localStorage persistence |
| `useToast` | Toast notifications |
| `useConfirm` | Custom confirm dialogs |
| `useShell` | `navigateToShard()` helper |
| Theme | Default dark theme with CSS vars |
| Routing | Hardcoded for 2 shards |
| Placeholders | GenericShardPage (Dashboard), custom (ACH) |

**Done when:**
- Shell renders at `:5173`
- URL params work: `?q=moon&page=2`
- Toasts appear/dismiss
- Confirm dialogs work
- Error in shard doesn't crash Shell
- `navigateToShard('ach', { matrixId: '123' })` works

### Phase 2: Frame Integration + Generic UI v1

**Goal:** Dynamic discovery, badge aggregation, basic generic UI

| Task | Details |
|------|---------|
| Frame API | Return full v4 manifest, add `/api/frame/badges` |
| Route validation | Frame validates collisions on startup |
| Static serving | Frame serves built React app |
| Dynamic sidebar | Generated from API |
| Badge polling | Single call, 30s interval |
| GenericList | Pagination only |
| GenericForm | With pattern validation |
| Connection status | Indicator in UI |
| Keyboard | Ctrl+B toggle sidebar |

### Phase 3: Generic UI v2

**Goal:** Full-featured generic UI

| Task | Details |
|------|---------|
| Filters | Search, Select, DateRange, Boolean |
| Bulk actions | Selection, confirm dialog, execute |
| Row actions | Dropdown menu per row |
| Sorting | Click header, indicators |
| URL params | Auto-infer from `list_filters` |
| API updates | Support `?sort=field&order=asc` |

### Phase 4: Theme System

| Task | Details |
|------|---------|
| ThemeContext | CSS variable system |
| Themes | Default dark, light, hacker cabin |
| Selector | In sidebar |
| Persistence | localStorage |
| Transitions | No flicker |

### Phase 5: Polish

| Task | Details |
|------|---------|
| Responsive | Tablet (collapse), mobile (hamburger) |
| Keyboard | g+letter, 1-9 nav, ? help |
| Command palette | Ctrl+K fuzzy search |
| Breadcrumbs | Nested routes |
| Service worker | Offline caching |
| A11y audit | Lighthouse > 90 |

### Phase 6: Hybrid UI Mode (Future)

Allow custom components in generic UI:

```yaml
ui:
  primary_action:
    fields:
      - name: project
        type: custom
        component: ProjectSelector
```

Requires component registry, dynamic imports, props contract.

---

## 5. Keyboard Shortcuts

| Shortcut | Action | Phase |
|----------|--------|-------|
| `Ctrl+B` | Toggle sidebar | 2 |
| `Ctrl+K` | Command palette | 5 |
| `Escape` | Close modals | 2 |
| `?` | Show shortcuts | 5 |
| `g then d/s/a` | Go to Dashboard/Search/ACH | 5 |
| `1-9` | Jump to nav item | 5 |

---

## 6. Risks

| Risk | Mitigation |
|------|------------|
| Lazy load race conditions | Test with slow network, add timeouts |
| Theme CSS bleeding | Use CSS vars only, test switches |
| Route collisions | Frame validates on startup |
| Generic UI inflexible | Phase 6 hybrid mode escape hatch |
| Bundle bloat | Code-split routes, tree-shake icons |
| Error boundary async gaps | Combine with try/catch in hooks |

### Known v1 Limitations

| Limitation | Workaround |
|------------|------------|
| Manifest changes need refresh | User refreshes if Frame restarts |
| No hot-reload shards | Restart dev server |
| Badge errors silent | Check console |
| No hybrid UI | Use custom UI if any custom needed |

---

## 7. Related Documents

- [SHARD_MANIFEST_SCHEMA_v4.md](SHARD_MANIFEST_SCHEMA_v4.md) - Manifest schema
- [UI_SHELL_IMPL_REF.md](UI_SHELL_IMPL_REF.md) - Full code implementations

---

## Changes from v3

| Change | Rationale |
|--------|-----------|
| Redesigned URL state | Flat params via `useUrlParams`, not JSON objects |
| Simplified `useShardState` | Now only localStorage; URL uses `useUrlParams` |
| Auto-infer URL params | From `list_filters[].param`, no redundant declaration |
| Added form validation | `pattern` regex + `error_message` |
| Added ConfirmDialog | Themed, accessible, replaces `window.confirm()` |
| Documented Hybrid Mode | Phase 6 for custom components in generic UI |

---

*v4.1 - Condensed 2025-12-22*
