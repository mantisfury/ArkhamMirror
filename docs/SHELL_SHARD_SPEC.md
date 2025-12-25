# UI Shell Shard Specification

> The navigation and theming layer for ArkhamMirror Shattered

---

## Overview

The Shell Shard provides the application frame that all other shards render within. It handles:
- Sidebar navigation (auto-generated from installed shards)
- Top bar (project selector, user info, settings)
- Theme system (swappable visual styles)
- Layout management
- Shard routing

**The Shell does NOT:**
- Contain any analytical features
- Make decisions about data
- Know what shards do internally

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Top Bar                                   │
│  [☰ Menu]  ArkhamMirror    [Project: Investigation X ▼]  [⚙️] [👤]  │
├──────────────┬──────────────────────────────────────────────────────┤
│              │                                                       │
│   Sidebar    │                                                       │
│              │                                                       │
│  ┌────────┐  │                   Content Area                        │
│  │Dashboard│  │                                                       │
│  └────────┘  │            (Active Shard Renders Here)                │
│              │                                                       │
│  ANALYSIS    │                                                       │
│  ┌────────┐  │                                                       │
│  │  ACH   │  │                                                       │
│  ├────────┤  │                                                       │
│  │Contradict│ │                                                       │
│  ├────────┤  │                                                       │
│  │Anomalies│  │                                                       │
│  ├────────┤  │                                                       │
│  │Timeline│  │                                                       │
│  └────────┘  │                                                       │
│              │                                                       │
│  SEARCH      │                                                       │
│  ┌────────┐  │                                                       │
│  │ Search │  │                                                       │
│  ├────────┤  │                                                       │
│  │ Graph  │  │                                                       │
│  └────────┘  │                                                       │
│              │                                                       │
│  DATA        │                                                       │
│  ┌────────┐  │                                                       │
│  │ Ingest │  │                                                       │
│  ├────────┤  │                                                       │
│  │ Parse  │  │                                                       │
│  └────────┘  │                                                       │
│              │                                                       │
│  SYSTEM      │                                                       │
│  ┌────────┐  │                                                       │
│  │Dashboard│  │                                                       │
│  └────────┘  │                                                       │
│              │                                                       │
│  ──────────  │                                                       │
│  [🎨 Theme]  │                                                       │
│  [⚙ Settings]│                                                       │
│              │                                                       │
└──────────────┴──────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Shard Discovery

On startup, Shell fetches installed shards from Frame:

```
GET /api/frame/shards
```

Response:
```json
{
  "shards": [
    {
      "name": "arkham-shard-dashboard",
      "display_name": "Dashboard",
      "version": "1.0.0",
      "routes": [
        {"path": "/dashboard", "componentName": "DashboardPage", "lazy": true}
      ],
      "menuItems": [
        {
          "label": "Dashboard",
          "icon": "layout-dashboard",
          "route": "/dashboard",
          "order": 0,
          "category": "System"
        }
      ]
    },
    {
      "name": "arkham-shard-ach",
      "display_name": "Analysis of Competing Hypotheses",
      "version": "1.0.0",
      "routes": [
        {"path": "/ach", "componentName": "ACHPage", "lazy": true},
        {"path": "/ach/:analysisId", "componentName": "ACHDetailPage", "lazy": true}
      ],
      "menuItems": [
        {
          "label": "ACH Analysis",
          "icon": "scale",
          "route": "/ach",
          "order": 10,
          "category": "Analysis"
        }
      ]
    }
    // ... more shards
  ]
}
```

### 2. Dynamic Route Generation

Shell builds React Router config from shard manifests:

```typescript
// Shell dynamically creates routes
const routes = shards.flatMap(shard => 
  shard.routes.map(route => ({
    path: route.path,
    element: <LazyShardComponent shard={shard.name} component={route.componentName} />
  }))
);
```

### 3. Sidebar Generation

Sidebar is auto-generated from `menuItems`:

```typescript
// Group by category, sort by order
const menuGroups = groupBy(
  shards.flatMap(s => s.menuItems),
  item => item.category || 'Other'
);

// Sort within groups
Object.values(menuGroups).forEach(group => 
  group.sort((a, b) => a.order - b.order)
);
```

---

## Component Specification

### Shell (Root Component)

```typescript
// packages/arkham-shard-shell/src/Shell.tsx

interface ShellProps {
  children?: React.ReactNode;
}

export function Shell({ children }: ShellProps) {
  const [shards, setShards] = useState<ShardManifest[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [theme, setTheme] = useState<ThemeName>('default');
  
  useEffect(() => {
    fetchShards().then(setShards);
  }, []);
  
  return (
    <ThemeProvider theme={theme}>
      <div className="shell">
        <TopBar 
          onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          onThemeChange={setTheme}
        />
        <div className="shell-body">
          <Sidebar 
            shards={shards} 
            open={sidebarOpen}
          />
          <main className="shell-content">
            <Outlet /> {/* React Router renders active shard here */}
          </main>
        </div>
      </div>
    </ThemeProvider>
  );
}
```

### Sidebar

```typescript
// packages/arkham-shard-shell/src/components/Sidebar.tsx

interface SidebarProps {
  shards: ShardManifest[];
  open: boolean;
}

export function Sidebar({ shards, open }: SidebarProps) {
  const menuGroups = useMemo(() => {
    const items = shards.flatMap(s => s.menuItems);
    return groupByCategory(items);
  }, [shards]);
  
  const location = useLocation();
  
  return (
    <aside className={`sidebar ${open ? 'open' : 'collapsed'}`}>
      <nav>
        {Object.entries(menuGroups).map(([category, items]) => (
          <div key={category} className="sidebar-group">
            <h3 className="sidebar-group-title">{category}</h3>
            {items.map(item => (
              <NavLink
                key={item.route}
                to={item.route}
                className={({ isActive }) => 
                  `sidebar-item ${isActive ? 'active' : ''}`
                }
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      
      <div className="sidebar-footer">
        <ThemeSelector />
        <SettingsLink />
      </div>
    </aside>
  );
}
```

### TopBar

```typescript
// packages/arkham-shard-shell/src/components/TopBar.tsx

interface TopBarProps {
  onMenuClick: () => void;
  onThemeChange: (theme: ThemeName) => void;
}

export function TopBar({ onMenuClick, onThemeChange }: TopBarProps) {
  const { currentProject, projects, switchProject } = useProjects();
  
  return (
    <header className="topbar">
      <button className="menu-toggle" onClick={onMenuClick}>
        <Icon name="menu" />
      </button>
      
      <div className="topbar-brand">
        <span className="brand-name">ArkhamMirror</span>
      </div>
      
      <div className="topbar-center">
        <ProjectSelector
          current={currentProject}
          projects={projects}
          onChange={switchProject}
        />
      </div>
      
      <div className="topbar-actions">
        <ThemeToggle onChange={onThemeChange} />
        <NotificationsButton />
        <SettingsButton />
      </div>
    </header>
  );
}
```

---

## Theme System

### Theme Structure

```typescript
// packages/arkham-shard-shell/src/themes/types.ts

interface Theme {
  name: string;
  displayName: string;
  description: string;
  
  colors: {
    // Backgrounds
    bgPrimary: string;      // Main background
    bgSecondary: string;    // Sidebar, cards
    bgTertiary: string;     // Inputs, nested elements
    bgAccent: string;       // Highlighted areas
    
    // Text
    textPrimary: string;
    textSecondary: string;
    textMuted: string;
    textAccent: string;
    
    // Borders
    border: string;
    borderAccent: string;
    
    // Status
    success: string;
    warning: string;
    error: string;
    info: string;
    
    // Interactive
    linkColor: string;
    linkHover: string;
    buttonBg: string;
    buttonText: string;
    
    // Sidebar specific
    sidebarBg: string;
    sidebarText: string;
    sidebarActive: string;
    sidebarHover: string;
  };
  
  fonts: {
    body: string;
    heading: string;
    mono: string;
  };
  
  spacing: {
    sidebarWidth: string;
    sidebarCollapsed: string;
    topbarHeight: string;
  };
  
  effects: {
    borderRadius: string;
    shadow: string;
    shadowHover: string;
  };
}
```

### Default Theme (Professional Dark)

```typescript
// packages/arkham-shard-shell/src/themes/default.ts

export const defaultTheme: Theme = {
  name: 'default',
  displayName: 'Default Dark',
  description: 'Clean professional dark theme',
  
  colors: {
    bgPrimary: '#0f1419',
    bgSecondary: '#1a1f2e',
    bgTertiary: '#242b3d',
    bgAccent: '#2d3548',
    
    textPrimary: '#e6e8eb',
    textSecondary: '#a0a8b7',
    textMuted: '#6b7280',
    textAccent: '#60a5fa',
    
    border: '#2d3548',
    borderAccent: '#3b4559',
    
    success: '#34d399',
    warning: '#fbbf24',
    error: '#f87171',
    info: '#60a5fa',
    
    linkColor: '#60a5fa',
    linkHover: '#93c5fd',
    buttonBg: '#3b82f6',
    buttonText: '#ffffff',
    
    sidebarBg: '#1a1f2e',
    sidebarText: '#a0a8b7',
    sidebarActive: '#60a5fa',
    sidebarHover: '#2d3548',
  },
  
  fonts: {
    body: 'Inter, system-ui, sans-serif',
    heading: 'Inter, system-ui, sans-serif',
    mono: 'JetBrains Mono, Consolas, monospace',
  },
  
  spacing: {
    sidebarWidth: '260px',
    sidebarCollapsed: '64px',
    topbarHeight: '56px',
  },
  
  effects: {
    borderRadius: '8px',
    shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
    shadowHover: '0 10px 15px -3px rgba(0, 0, 0, 0.4)',
  },
};
```

### Hacker Cabin Theme (Future)

```typescript
// packages/arkham-shard-shell/src/themes/hacker-cabin.ts

export const hackerCabinTheme: Theme = {
  name: 'hacker-cabin',
  displayName: 'Hacker Cabin',
  description: 'Dark wood, green CRTs, red string conspiracy boards',
  
  colors: {
    bgPrimary: '#1a1510',        // Dark wood
    bgSecondary: '#2a2318',       // Lighter wood
    bgTertiary: '#3a3020',        // Highlighted wood
    bgAccent: '#4a3f2a',          // Cork board
    
    textPrimary: '#33ff33',       // CRT green
    textSecondary: '#22cc22',     // Dimmer green
    textMuted: '#116611',         // Dark green
    textAccent: '#ff3333',        // Red string
    
    border: '#4a3f2a',
    borderAccent: '#ff3333',      // Red string accent
    
    success: '#33ff33',
    warning: '#ffaa00',
    error: '#ff3333',
    info: '#33aaff',
    
    linkColor: '#33ff33',
    linkHover: '#66ff66',
    buttonBg: '#33ff33',
    buttonText: '#1a1510',
    
    sidebarBg: '#2a2318',
    sidebarText: '#33ff33',
    sidebarActive: '#ff3333',
    sidebarHover: '#3a3020',
  },
  
  fonts: {
    body: '"VT323", "Courier New", monospace',  // CRT font
    heading: '"VT323", "Courier New", monospace',
    mono: '"VT323", "Courier New", monospace',
  },
  
  spacing: {
    sidebarWidth: '240px',
    sidebarCollapsed: '60px',
    topbarHeight: '52px',
  },
  
  effects: {
    borderRadius: '2px',          // Sharp edges for retro feel
    shadow: '0 0 10px rgba(51, 255, 51, 0.2)',  // Green glow
    shadowHover: '0 0 20px rgba(51, 255, 51, 0.4)',
  },
};
```

---

## File Structure

```
packages/arkham-shard-shell/
├── pyproject.toml
├── shard.yaml
├── README.md
├── arkham_shard_shell/
│   ├── __init__.py
│   ├── shard.py              # ShellShard class
│   └── api.py                # Theme preferences API
└── ui/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    └── src/
        ├── index.tsx         # Entry point
        ├── Shell.tsx         # Main shell component
        ├── router.tsx        # Dynamic route generation
        │
        ├── components/
        │   ├── Sidebar.tsx
        │   ├── TopBar.tsx
        │   ├── ProjectSelector.tsx
        │   ├── ThemeSelector.tsx
        │   ├── Icon.tsx      # Lucide icon wrapper
        │   └── NavLink.tsx
        │
        ├── themes/
        │   ├── types.ts      # Theme interface
        │   ├── default.ts    # Default dark theme
        │   ├── light.ts      # Light theme
        │   ├── hacker-cabin.ts  # (future)
        │   ├── professional.ts  # (future)
        │   └── index.ts      # Theme registry
        │
        ├── context/
        │   ├── ThemeContext.tsx
        │   ├── ShardContext.tsx
        │   └── ProjectContext.tsx
        │
        ├── hooks/
        │   ├── useShards.ts
        │   ├── useTheme.ts
        │   └── useProjects.ts
        │
        ├── api/
        │   └── shellApi.ts   # API client
        │
        └── styles/
            ├── base.css      # Reset, variables
            ├── shell.css     # Shell layout
            └── components.css
```

---

## API Endpoints

### Frame Endpoints (Shell Consumes)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/frame/shards` | GET | List installed shards with manifests |
| `/api/frame/projects` | GET | List projects |
| `/api/frame/projects/current` | GET | Current project |
| `/api/frame/projects/switch` | POST | Switch project |
| `/api/frame/state` | GET | Global app state |

### Shell Endpoints (Shell Provides)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/shell/theme` | GET | Get current theme preference |
| `/api/shell/theme` | PUT | Update theme preference |
| `/api/shell/layout` | GET | Get layout preferences (sidebar state) |
| `/api/shell/layout` | PUT | Update layout preferences |

---

## Shard Manifest

```yaml
# shard.yaml
name: "arkham-shard-shell"
display_name: "Shell"
version: "1.0.0"
description: "Application shell with navigation and theming"
author: "ArkhamMirror Team"
license: "MIT"

frame_version: ">=1.0.0"
schema: "shell"

tags:
  - "core"
  - "ui"
  - "navigation"

# Shell is special - it doesn't appear in its own sidebar
menu: null

# No workers needed
workers: []

# Events
emits:
  - "shell.theme_changed"
  - "shell.sidebar_toggled"

subscribes:
  - event: "shard.installed"
    handler: "on_shard_installed"
  - event: "shard.uninstalled"
    handler: "on_shard_uninstalled"

dependencies: []
```

---

## Implementation Notes

### 1. Icon System

Use Lucide React icons. Each shard specifies icon by name in manifest:

```typescript
import { icons } from 'lucide-react';

interface IconProps {
  name: string;
  size?: number;
}

export function Icon({ name, size = 20 }: IconProps) {
  const LucideIcon = icons[name as keyof typeof icons];
  if (!LucideIcon) {
    console.warn(`Unknown icon: ${name}`);
    return <icons.HelpCircle size={size} />;
  }
  return <LucideIcon size={size} />;
}
```

### 2. Lazy Loading

Shard components are loaded lazily to reduce initial bundle size:

```typescript
const ShardComponent = lazy(() => 
  import(`@arkham-shards/${shardName}/src/pages/${componentName}`)
);
```

### 3. Responsive Design

- Sidebar collapses to icons on smaller screens
- Hamburger menu on mobile
- Content area is always full-width on mobile

### 4. Keyboard Navigation

- `Ctrl+B` or `Cmd+B`: Toggle sidebar
- `Ctrl+K` or `Cmd+K`: Quick search / command palette (future)
- Arrow keys navigate sidebar when focused

### 5. State Persistence

Theme and sidebar state stored in localStorage:

```typescript
const STORAGE_KEYS = {
  theme: 'arkham-theme',
  sidebarOpen: 'arkham-sidebar-open',
};
```

---

## Visual Reference

### Default Dark Theme
- Clean, professional appearance
- Blue accents
- High contrast text
- Suitable for extended use

### Hacker Cabin Theme (Target Aesthetic)
- Dark wood textures
- Green CRT text (#33ff33)
- Red string accents
- Monospace fonts throughout
- Subtle scan lines effect (CSS)
- Cork board texture for cards/panels
- Vintage dial/gauge aesthetics for metrics

Reference image: The uploaded cabin workspace with cork boards, CRT monitors, green terminal text, stacks of documents, conspiracy boards with red string.

---

## Next Steps

1. **Phase 1**: Basic shell with sidebar, routing, default theme
2. **Phase 2**: Project selector, theme switching
3. **Phase 3**: Additional themes (hacker cabin, professional, etc.)
4. **Phase 4**: Command palette, keyboard shortcuts
5. **Phase 5**: Mobile responsiveness

---

*This specification is for the AI dev team. Build Phase 1 first, validate it works, then iterate.*
