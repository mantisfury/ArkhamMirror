# arkham-shard-shell

> React/TypeScript UI shell that renders all shard interfaces in the SHATTERED architecture

## Overview

The `arkham-shard-shell` is the unified frontend application for the SHATTERED system. It provides:

- **Dynamic Navigation** - Renders sidebar navigation from shard manifests fetched via API
- **Layout Management** - Collapsible sidebar, top bar, and content area
- **Generic Components** - Data-driven list/form components for shards without custom UIs
- **Custom Shard Pages** - Full React pages for shards that need custom interfaces
- **Shared Context** - Toast notifications, confirmations, badges, theming, and project scope

The shell follows the **Voltron** philosophy: a thin rendering layer that combines shard UIs into a cohesive application without containing business logic.

## Architecture

```
                    +-----------------------+
                    |    BrowserRouter      |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |     ThemeProvider     |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |     ShellProvider     |  <-- Fetches shards from /api/shards/
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |    ProjectProvider    |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |     ToastProvider     |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |    ConfirmProvider    |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |     BadgeProvider     |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |        Routes         |
                    +-----------+-----------+
                                |
    +---------------------------+---------------------------+
    |                           |                           |
+---v---+                   +---v---+                   +---v---+
| Shell |                   | Shell |                   | Shell |
+---+---+                   +---+---+                   +---+---+
    |                           |                           |
+---v-------+               +---v-------+               +---v-------+
| Shard     |               | Shard     |               | Generic   |
| Page      |               | Page      |               | ShardPage |
+-----------+               +-----------+               +-----------+
```

## Tech Stack

| Technology | Purpose |
|------------|---------|
| React 18 | UI framework |
| TypeScript 5 | Type safety |
| Vite 5 | Build tool and dev server |
| React Router DOM 6 | Client-side routing |
| Lucide React | Icon library (dynamic by name) |
| D3.js | Data visualization (graphs, timelines) |
| React Force Graph | Network visualization |
| Leaflet + React Leaflet | Map visualization |
| React Markdown | Markdown rendering |
| React Error Boundary | Error handling |

## Project Structure

```
packages/arkham-shard-shell/
├── package.json              # Dependencies and scripts
├── vite.config.ts            # Vite configuration
├── tsconfig.json             # TypeScript configuration
├── index.html                # HTML entry point
└── src/
    ├── main.tsx              # Application entry point
    ├── App.tsx               # Root component with providers and routes
    ├── index.css             # Global styles
    │
    ├── components/           # Shared components
    │   ├── layout/           # Shell layout components
    │   │   ├── Shell.tsx     # Main layout wrapper
    │   │   ├── Sidebar.tsx   # Navigation sidebar
    │   │   ├── TopBar.tsx    # Top navigation bar
    │   │   └── ContentArea.tsx
    │   │
    │   ├── common/           # Reusable UI components
    │   │   ├── Icon.tsx      # Dynamic Lucide icon loader
    │   │   ├── LoadingSkeleton.tsx
    │   │   ├── ShardErrorBoundary.tsx
    │   │   ├── ShardUnavailable.tsx
    │   │   ├── ConnectionLost.tsx
    │   │   ├── BadgeStatusIndicator.tsx
    │   │   └── ProjectSelector.tsx
    │   │
    │   ├── generic/          # Data-driven components
    │   │   ├── GenericList.tsx   # Table with filters, pagination, actions
    │   │   └── GenericForm.tsx   # Form with validation
    │   │
    │   └── AIAnalyst/        # AI Analyst panel components
    │       ├── AIAnalystButton.tsx
    │       └── AIAnalystPanel.tsx
    │
    ├── context/              # React contexts
    │   ├── ShellContext.tsx  # Shard navigation, sidebar state
    │   ├── ThemeContext.tsx  # Light/dark theme
    │   ├── ToastContext.tsx  # Toast notifications
    │   ├── ConfirmContext.tsx # Confirmation dialogs
    │   ├── BadgeContext.tsx  # Navigation badges
    │   └── ProjectContext.tsx # Active project scope
    │
    ├── hooks/                # Custom React hooks
    │   ├── useFetch.ts       # Data fetching with error handling
    │   ├── usePaginatedFetch.ts # Paginated API calls
    │   ├── useUrlParams.ts   # URL state management
    │   ├── useLocalState.ts  # localStorage persistence
    │   ├── useBadges.ts      # Badge polling
    │   └── useSettings.ts    # User settings
    │
    ├── pages/                # Shard page implementations
    │   ├── generic/          # Fallback for unknown shards
    │   │   └── GenericShardPage.tsx
    │   │
    │   ├── dashboard/        # System: Dashboard
    │   ├── settings/         # System: Settings
    │   ├── projects/         # System: Projects
    │   │
    │   ├── ingest/           # Data: Ingest
    │   ├── documents/        # Data: Documents
    │   ├── parse/            # Data: Parse
    │   ├── embed/            # Data: Embed
    │   │
    │   ├── search/           # Search: Search
    │   ├── ocr/              # Search: OCR
    │   │
    │   ├── ach/              # Analysis: ACH
    │   ├── anomalies/        # Analysis: Anomalies
    │   ├── contradictions/   # Analysis: Contradictions
    │   ├── entities/         # Analysis: Entities
    │   ├── claims/           # Analysis: Claims
    │   ├── credibility/      # Analysis: Credibility
    │   ├── patterns/         # Analysis: Patterns
    │   ├── provenance/       # Analysis: Provenance
    │   │
    │   ├── graph/            # Visualize: Graph
    │   ├── timeline/         # Visualize: Timeline
    │   │
    │   ├── export/           # Export: Export
    │   ├── reports/          # Export: Reports
    │   ├── letters/          # Export: Letters
    │   ├── packets/          # Export: Packets
    │   ├── templates/        # Export: Templates
    │   └── summary/          # Export: Summary
    │
    └── types/                # TypeScript type definitions
        └── index.ts          # ShardManifest, UIConfig, etc.
```

## Available Components

### Layout Components

| Component | Description |
|-----------|-------------|
| `Shell` | Main layout with sidebar, top bar, and content area |
| `Sidebar` | Collapsible navigation grouped by category |
| `TopBar` | Breadcrumbs, search, and quick actions |
| `ContentArea` | Main content wrapper with scrolling |

### Common Components

| Component | Description |
|-----------|-------------|
| `Icon` | Dynamic Lucide icon loader by name string |
| `LoadingSkeleton` | Loading state placeholder |
| `ShardErrorBoundary` | Error boundary for shard pages |
| `ShardUnavailable` | Displayed when shard API unreachable |
| `ConnectionLost` | Displayed when Frame connection lost |
| `ProjectSelector` | Project scope selector dropdown |

### Generic Components (Data-Driven)

| Component | Description |
|-----------|-------------|
| `GenericList` | Table with filters, sorting, pagination, bulk/row actions |
| `GenericForm` | Form with validation based on ActionConfig |
| `GenericFormDialog` | Modal wrapper for GenericForm |

## Pages by Category

### System
- **Dashboard** (`/dashboard`) - Health status, LLM config, database stats, workers, events
- **Settings** (`/settings`) - Application configuration
- **Projects** (`/projects`) - Workspace management

### Data
- **Ingest** (`/ingest`) - File upload and ingestion queue
- **Documents** (`/documents`) - Document browser and viewer
- **Parse** (`/parse`) - Document parsing and chunk management
- **Embed** (`/embed`) - Vector embedding management

### Search
- **Search** (`/search`) - Full-text and semantic search
- **OCR** (`/ocr`) - Optical character recognition

### Analysis
- **ACH** (`/ach`) - Analysis of Competing Hypotheses matrices
- **Anomalies** (`/anomalies`) - Anomaly detection results
- **Contradictions** (`/contradictions`) - Contradiction analysis
- **Entities** (`/entities`) - Entity extraction and management
- **Claims** (`/claims`) - Claim extraction and verification
- **Credibility** (`/credibility`) - Source credibility assessment
- **Patterns** (`/patterns`) - Pattern detection
- **Provenance** (`/provenance`) - Information provenance tracking

### Visualize
- **Graph** (`/graph`) - Entity relationship network
- **Timeline** (`/timeline`) - Temporal event visualization

### Export
- **Export** (`/export`) - Data export options
- **Reports** (`/reports`) - Generated reports
- **Letters** (`/letters`) - Letter generation
- **Packets** (`/packets`) - Document packets
- **Templates** (`/templates`) - Report templates
- **Summary** (`/summary`) - Executive summaries

## Development Commands

```bash
# Install dependencies
npm install

# Start development server (hot reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run linting
npm run lint
```

## Configuration

### Environment Variables

Create a `.env` file for local development:

```env
VITE_API_URL=http://127.0.0.1:8100
```

### Vite Configuration

The shell is configured via `vite.config.ts`:

```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
});
```

## Adding New Shard Pages

### 1. Create Page Component

```typescript
// src/pages/myshard/MyShardPage.tsx
import { useState, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import './MyShardPage.css';

export function MyShardPage() {
  const { toast } = useToast();

  return (
    <div className="myshard-page">
      <header className="page-header">
        <Icon name="Star" size={28} />
        <h1>My Shard</h1>
      </header>
      {/* Page content */}
    </div>
  );
}
```

### 2. Create Index Export

```typescript
// src/pages/myshard/index.ts
export { MyShardPage } from './MyShardPage';
```

### 3. Add Route to App.tsx

```typescript
// In src/App.tsx
import { MyShardPage } from './pages/myshard';

// Inside Routes
<Route path="/myshard" element={<MyShardPage />} />
```

### 4. Update Page Index (Optional)

```typescript
// src/pages/index.ts
export * from './myshard';
```

## Shell Design Principles

1. **Non-Authoritative** - The shell only renders what the API provides; it never makes business decisions
2. **Manifest-Driven** - Navigation and UI configuration come from shard manifests
3. **Error Surfacing** - All API errors are displayed to users via toasts
4. **Minimal State** - State is primarily URL-based or API-driven
5. **Offline Resilient** - Fallback navigation when Frame is unreachable

## Context API Reference

### useShell()
```typescript
const {
  shards,           // ShardManifest[]
  currentShard,     // ShardManifest | null
  loading,          // boolean
  connected,        // boolean
  sidebarCollapsed, // boolean
  setSidebarCollapsed,
  navigateToShard,
  getShardRoute,
} = useShell();
```

### useToast()
```typescript
const { toast } = useToast();
toast.success('Operation completed');
toast.error('Something went wrong');
toast.info('Information');
toast.warning('Warning');
```

### useConfirm()
```typescript
const confirm = useConfirm();
const result = await confirm({
  title: 'Delete Item',
  message: 'Are you sure?',
  variant: 'danger',
});
```

### useBadgeContext()
```typescript
const { getBadge } = useBadgeContext();
const badge = getBadge('shard-name'); // { count: 5, type: 'count' }
```

## License

Part of the SHATTERED architecture, licensed under MIT.
