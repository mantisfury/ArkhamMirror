# UI Shell Shard Implementation Plan v5

> Condensed planning document - see [UI_SHELL_IMPL_REF.md](UI_SHELL_IMPL_REF.md) for full code

---

## Shell Invariants (Hard Rules)

**The UI Shell is non-authoritative.**

The Shell MUST NOT:
- Infer business logic from shard data
- Validate shard data beyond schema shape checks
- Retry failed shard actions automatically
- Cache shard manifests beyond in-memory session scope
- Mutate Frame or shard state except via declared API calls
- Normalize, sanitize, or "fix" manifest content
- Add fallback routing for missing shards

**All errors are surfaced, not corrected.**

The Shell assumes shard manifests are trusted and validated by the Frame. The Shell MUST NOT defensively sanitize manifest content beyond TypeScript type checks.

---

## AI Implementation Constraints

When implementing this specification:

- Do NOT introduce additional libraries beyond those listed in Key Dependencies
- Do NOT refactor architecture for "cleanliness" or "best practices"
- Do NOT infer missing behavior - if behavior is unspecified, implement the minimal no-op
- Do NOT add animations, transitions, or visual effects not explicitly specified
- Do NOT add error retry logic, exponential backoff, or "smart" recovery
- Do NOT add state management libraries (Redux, Zustand, etc.) - use only React context
- Do NOT cache API responses beyond component lifecycle
- Do NOT add "helpful" console.log statements beyond error warnings

**If in doubt, do less.**

---

## Non-Goals (Explicit Exclusions)

The following are explicitly out of scope for all phases:

- Multi-tab synchronization
- Cross-shard UI composition
- Live shard hot-reloading
- Offline mutation queuing
- Authentication/authorization (design for future, do not implement)
- Undo/redo functionality
- Drag-and-drop reordering
- Keyboard-driven data entry (beyond basic tab navigation)
- Internationalization/localization
- Analytics/telemetry

---

## Quick Reference

| Aspect | Decision |
|--------|----------|
| Build | Monorepo, Vite + React + TypeScript + React Router |
| Dev | Vite `:5173` -> Frame `:8105` proxy |
| Prod | Frame serves static React build |
| URL State | `useUrlParams()` - flat params only, no JSON blobs |
| Local State | `useLocalState()` - localStorage with shard prefix |
| Badges | Single `/api/frame/badges` poll (30s) |
| Confirmations | `useConfirm()` hook, not `window.confirm()` |
| Toasts | `useToast()` with success/error/info/warning |
| Error Isolation | `react-error-boundary` per shard content |
| Custom UI Location | `pages/ach/`, `pages/graph/`, etc. in shell package |
| Phase 1 Shards | Dashboard (generic), ACH (custom) |

---

## Frame Failure Semantics

### Partial Shard Data

If `/api/shards/` returns partial data:
- Shell renders available shards only
- Missing shards are omitted from sidebar silently
- No error toast for partial availability

### Shard Route Mismatch

If a shard route exists in URL but shard is not loaded:
- Render a "Shard Unavailable" fallback page
- Do NOT redirect automatically
- Do NOT attempt to load the shard
- Show: "This shard is not currently available. Contact your administrator."

### Badge Fetch Failure

If `/api/frame/badges` fails:
- Keep existing badge counts (do not clear)
- Show small warning indicator on sidebar footer
- Tooltip: "Badge data may be stale"
- Continue polling normally

### Frame Unreachable

If Frame is completely unreachable:
- Show full-page "Connection Lost" overlay
- Disable all navigation
- Auto-retry every 5 seconds
- Show last successful connection time

---

## URL State Rules

### Core Principles

1. **URL is the single source of truth** for all shareable state
2. **Flat params only** - no JSON blobs, no nested objects
3. **Primitives serialize directly** - `page=2` not `page="2"`
4. **Default values are omitted** - keeps URLs clean and shareable
5. **Selection is component state** - not persisted in URL (not shareable)

### Mandatory Behaviors

| Action | Required Behavior |
|--------|-------------------|
| Any filter change | Reset `page` to 1, clear selection |
| Any sort change | Reset `page` to 1, clear selection |
| Filter cleared (X button) | Treated as filter change - reset page to 1, clear selection |
| Page change | Selection PERSISTS (allows multi-page bulk operations) |
| Bulk action complete | Clear selection, refetch current page |
| Navigation to different shard | Selection is lost |

**Important:** Selection persists across pagination to enable multi-page bulk operations. Users can select items on page 1, navigate to page 2, select more items, then execute a bulk action on all selected items.

### Boolean URL Params

| State | URL Representation |
|-------|-------------------|
| `true` | `param=true` |
| `false` | `param=false` |
| Missing | use manifest default (NOT assumed false) |
| Invalid value | use manifest default |

**Important:** Unlike previous versions, `false` is explicitly represented as `param=false` rather than omitted. This supports boolean filters with `default: true`.

Example with `default: true`:
- User unchecks -> `?show_archived=false` -> filter is OFF
- Fresh page load (no param) -> use default `true` -> filter is ON

Example with `default: false`:
- User checks -> `?include_deleted=true` -> filter is ON
- Fresh page load (no param) -> use default `false` -> filter is OFF

### Date Range Params

Date ranges are ALWAYS two separate flat params:
```
?from=2024-01-01&to=2024-12-31
```

Never:
```
?dateRange={"start":"2024-01-01","end":"2024-12-31"}
```

---

## 1. Architecture

### Component Hierarchy

```
<App>
  <ThemeProvider>
    <ShellProvider>
      <ToastProvider>
        <ConfirmProvider>
          <BadgeProvider>
            <Shell>
              <TopBar />
              <Sidebar>
                <ProjectSelector />
                <Navigation>
                  <NavGroup><NavItem badge={count} /></NavGroup>
                </Navigation>
                <BadgeStatusIndicator />
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
          </BadgeProvider>
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

### Async Hook Error Contract

**All async hooks MUST:**
- Catch errors internally
- Return `{ data, loading, error }` - never throw
- Never throw during render phase
- Log warnings to console, not errors (unless truly fatal)

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
- Booleans: `true` = "true", `false` = "false" (explicit, supports default: true)

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
const { getBadge, hasError, lastSuccessTime } = useBadges();
const badge = getBadge('ach');           // main nav
const sub = getBadge('ach', 'pending');  // sub-route
// badge: { count: 5, type: 'count' | 'dot' } | null
// hasError: boolean - true if last fetch failed
// lastSuccessTime: Date | null - for "stale since" display
```

**Stale-While-Revalidate:** On fetch failure, existing badge counts are PRESERVED (not cleared). Only `hasError` is set to `true`. This prevents badge counts from disappearing during temporary network issues.

**Badge Key Format:** Sub-route badges use colon separator: `{shardName}:{subRouteId}`. This is safe because shard names are validated as "lowercase, alphanumeric + hyphens only" - colons are never valid in shard names.

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
| `GenericFilter` | `{ config, value, onChange }` | Filter by type |
| `DateRangeFilter` | `{ config, startValue, endValue, onStartChange, onEndChange }` | Two flat date inputs |
| `RowActionsMenu` | `{ actions, row, onAction }` | Per-row action dropdown |

### Filter Types

| Type | URL Params | Renders |
|------|------------|---------|
| `search` | `{param}` | Text input with clear button |
| `select` | `{param}` | Dropdown from `options[]` |
| `boolean` | `{param}` (omitted when false) | Checkbox |
| `date_range` | `{param_start}` AND `{param_end}` | Two separate date inputs |

**Important:** Date range filters produce TWO separate URL params, not one object.

### Form Validation

Fields support `pattern` (regex) and `error_message`:

```yaml
fields:
  - name: email
    type: email
    pattern: "^[^@]+@[^@]+$"
    error_message: "Invalid email format"
```

**Security Note:** Pattern validation is client-side only for UX purposes. APIs MUST NOT rely on Shell validation for security. All API endpoints must validate their own inputs independently.

---

## Column Configuration Rules

### Template Substitution (`link_route`)

Template variables use `{fieldName}` syntax where `fieldName` must be a top-level key in the row object.

```yaml
# Supported
link_route: /document/{id}           # Uses row.id
link_route: /document/{doc_id}       # Uses row.doc_id
link_route: /shard/{id}/edit         # Uses row.id

# NOT supported
link_route: /document/{nested.id}    # No nested paths
link_route: /document/{{id}}         # No escaping
```

**Implementation:** Replace all `{fieldName}` occurrences with `row[fieldName]`. If field is missing or undefined, render link with literal `{fieldName}` (don't crash).

### Default Sort Rules

**Only ONE column may specify `default_sort`.** If multiple columns have `default_sort`, Frame validation fails on shard load with error: "Multiple default_sort columns not allowed".

```yaml
# VALID
list_columns:
  - field: created_at
    sortable: true
    default_sort: desc

# INVALID - Frame rejects manifest
list_columns:
  - field: created_at
    default_sort: desc
  - field: title
    default_sort: asc
```

If no column has `default_sort`, the list is unsorted (API determines order).

### Empty Options Handling

If a select filter or field has `options: []` (empty array):
- Render the select as disabled
- Show placeholder text: "No options available"
- Do not crash on `.map()` of empty array

```yaml
# This shouldn't happen but if it does:
- name: status
  type: select
  options: []  # Renders as disabled with "No options available"
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
| Frame API | Return full v5 manifest, add `/api/frame/badges` |
| Route validation | Frame validates collisions on startup |
| Static serving | Frame serves built React app |
| Dynamic sidebar | Generated from API |
| Badge polling | Single call, 30s interval, with error indicator |
| GenericList | Pagination only |
| GenericForm | With pattern validation |
| Connection status | Indicator in UI |
| Keyboard | Ctrl+B toggle sidebar |
| Shard unavailable page | For missing shard routes |

### Phase 3: Generic UI v2

**Goal:** Full-featured generic UI

| Task | Details |
|------|---------|
| Filters | Search, Select, DateRange (flat), Boolean |
| Bulk actions | Selection, confirm dialog, execute |
| Row actions | Dropdown menu per row |
| Sorting | Click header, indicators |
| URL params | Auto-infer from `list_filters` |
| API updates | Support `?sort=field&order=asc` |
| Page reset | Enforce reset on filter/sort change |

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
| Error boundary async gaps | All hooks return errors, never throw |
| Date range filter mismatch | Use flat params consistently |

### Known v1 Limitations

| Limitation | Workaround |
|------------|------------|
| Manifest changes need refresh | User refreshes if Frame restarts |
| No hot-reload shards | Restart dev server |
| Badge errors show indicator | Small warning dot, tooltip explains |
| No hybrid UI | Use custom UI if any custom needed |

---

## 7. Related Documents

- [SHARD_MANIFEST_SCHEMA_v5.md](SHARD_MANIFEST_SCHEMA_v5.md) - Manifest schema
- [UI_SHELL_IMPL_REF.md](UI_SHELL_IMPL_REF.md) - Full code implementations

---

## Changes from v4.2

| Change | Rationale |
|--------|-----------|
| Added Shell Invariants section | Prevents AI "helpfulness" that violates non-authoritative model |
| Added AI Implementation Constraints | Explicit "do less" guidance for AI developers |
| Added Non-Goals section | Prevents feature creep |
| Added Frame Failure Semantics | Defines behavior for partial data, missing shards, badge failures |
| Added URL State Rules | Explicit reset behavior, boolean handling, date range contract |
| Fixed date_range filter contract | Now explicitly two flat params, not an object |
| Added Async Hook Error Contract | Hooks return errors, never throw |
| Added badge error indicator | UI affordance for stale badge data |
| Added DateRangeFilter component | Separate component for proper flat param handling |

## Changes in v5.1 (Current)

| Change | Rationale |
|--------|-----------|
| Selection persists across pagination | Enables multi-page bulk operations (FATAL FIX) |
| Boolean params explicit for false | Supports `default: true` booleans (FATAL FIX) |
| Template substitution rules | `{fieldName}` must be top-level key, no nested paths |
| Single default_sort rule | Frame validation rejects multiple default_sort columns |
| Filter clear = filter change | Clearing filter resets page to 1 |
| Empty options handling | Render disabled select with "No options available" |
| Client-side validation is UX only | Security note: APIs must validate independently |
| Badge stale-while-revalidate explicit | Existing counts preserved on fetch failure |
| Badge key format clarified | Colon separator safe because colons invalid in shard names |

---

*v5.1 - Critical fixes for multi-page selection and boolean defaults 2025-12-22*
