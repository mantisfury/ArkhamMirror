/**
 * Sidebar - Navigation sidebar with shard links
 *
 * Features:
 * - Collapsible sidebar (horizontal)
 * - Collapsible categories (vertical)
 * - Collapsible sub-routes per shard
 * - Grouped navigation by category
 * - Badge display
 * - Sub-routes support
 * - Persisted collapse state in localStorage
 */

import { useState, useCallback, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { useShell } from '../../context/ShellContext';
import { useBadgeContext } from '../../context/BadgeContext';
import { Icon } from '../common/Icon';
import { BadgeStatusIndicator } from '../common/BadgeStatusIndicator';
import type { ShardManifest } from '../../types';

// LocalStorage key for persisting collapse state
const COLLAPSE_STATE_KEY = 'arkham-sidebar-collapse-state';

// Category order and labels
const CATEGORY_ORDER = ['System', 'Data', 'Search', 'Analysis', 'Visualize', 'Export'] as const;

interface CollapseState {
  categories: Record<string, boolean>;
  shards: Record<string, boolean>;
}

interface NavItemProps {
  manifest: ShardManifest;
  sidebarCollapsed: boolean;
}

function NavBadge({ shardName, subRouteId }: { shardName: string; subRouteId?: string }) {
  const { getBadge } = useBadgeContext();
  const badge = getBadge(shardName, subRouteId);

  if (!badge || badge.count === 0) return null;

  return (
    <span className={`nav-badge nav-badge-${badge.type}`}>
      {badge.type === 'dot' ? '' : badge.count > 99 ? '99+' : badge.count}
    </span>
  );
}

function NavItem({ manifest, sidebarCollapsed }: NavItemProps) {
  const { navigation, name } = manifest;
  

  return (
    <div className="nav-item-wrapper">
      <div className="nav-item-row">
        <NavLink
          to={navigation.route}
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          title={sidebarCollapsed ? navigation.label : undefined}
          end
        >
          <Icon name={navigation.icon} size={20} className="nav-icon" />
          {!sidebarCollapsed && (
            <>
              <span className="nav-label">{navigation.label}</span>
              <NavBadge shardName={name} />
            </>
          )}
        </NavLink>


      </div>

    </div>
  );
}

interface NavGroupProps {
  category: string;
  shards: ShardManifest[];
  sidebarCollapsed: boolean;
  categoryCollapsed: boolean;
  onToggleCategory: () => void;
}

function NavGroup({
  category,
  shards,
  sidebarCollapsed,
  categoryCollapsed,
  onToggleCategory,
}: NavGroupProps) {
  if (shards.length === 0) return null;

  return (
    <div className={`nav-group ${categoryCollapsed ? 'collapsed' : ''}`}>
      {!sidebarCollapsed && (
        <button
          className={`nav-group-header ${categoryCollapsed ? 'collapsed' : ''}`}
          onClick={onToggleCategory}
          title={categoryCollapsed ? `Expand ${category}` : `Collapse ${category}`}
        >
          <span className="nav-group-label">{category}</span>
          <Icon name="ChevronDown" size={14} className="nav-group-chevron" />
        </button>
      )}
      {!categoryCollapsed && shards.map(shard => (
        <NavItem
          key={shard.name}
          manifest={shard}
          sidebarCollapsed={sidebarCollapsed}
        />
      ))}
    </div>
  );
}

export function Sidebar() {
  const { shards, sidebarCollapsed, setSidebarCollapsed } = useShell();

  // Load persisted collapse state from localStorage
  const [collapseState, setCollapseState] = useState<CollapseState>(() => {
    try {
      const saved = localStorage.getItem(COLLAPSE_STATE_KEY);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      // Ignore parse errors
    }
    return { categories: {}, shards: {} };
  });

  // Persist collapse state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_STATE_KEY, JSON.stringify(collapseState));
    } catch (e) {
      // Ignore storage errors
    }
  }, [collapseState]);

  // Toggle category collapse
  const toggleCategory = useCallback((category: string) => {
    setCollapseState(prev => ({
      ...prev,
      categories: {
        ...prev.categories,
        [category]: !prev.categories[category],
      },
    }));
  }, []);

  // Group shards by category
  const groupedShards = CATEGORY_ORDER.reduce((acc, category) => {
    acc[category] = shards
      .filter(s => s.navigation.category === category)
      .sort((a, b) => a.navigation.order - b.navigation.order);
    return acc;
  }, {} as Record<string, ShardManifest[]>);

  return (
    <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
      {/* Header */}
      <div className="sidebar-header">
        {!sidebarCollapsed && (
          <div className="sidebar-brand">
            <Icon name="Layers" size={24} />
            <span className="brand-text">ArkhamMirror: SHATTERED</span>
          </div>
        )}
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={sidebarCollapsed ? 'Expand (Ctrl+B)' : 'Collapse (Ctrl+B)'}
        >
          <Icon name={sidebarCollapsed ? 'PanelLeftOpen' : 'PanelLeftClose'} size={18} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {CATEGORY_ORDER.map(category => (
          <NavGroup
            key={category}
            category={category}
            shards={groupedShards[category]}
            sidebarCollapsed={sidebarCollapsed}
            categoryCollapsed={collapseState.categories[category] ?? false}
            onToggleCategory={() => toggleCategory(category)}
          />
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <BadgeStatusIndicator />
        {!sidebarCollapsed && (
          <div className="sidebar-footer-right">
            <a
              href="https://ko-fi.com/arkhammirror"
              target="_blank"
              rel="noopener noreferrer"
              className="kofi-button"
              title="Support on Ko-fi"
            >
              <Icon name="Coffee" size={16} />
            </a>
            <div className="sidebar-version">v0.1.0</div>
          </div>
        )}
      </div>
    </aside>
  );
}
