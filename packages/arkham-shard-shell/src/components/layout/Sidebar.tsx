/**
 * Sidebar - Navigation sidebar with shard links
 *
 * Features:
 * - Collapsible sidebar
 * - Grouped navigation by category
 * - Badge display
 * - Sub-routes support
 */

import { NavLink } from 'react-router-dom';
import { useShell } from '../../context/ShellContext';
import { useBadgeContext } from '../../context/BadgeContext';
import { Icon } from '../common/Icon';
import { BadgeStatusIndicator } from '../common/BadgeStatusIndicator';
import type { ShardManifest } from '../../types';

// Category order and labels
const CATEGORY_ORDER = ['System', 'Data', 'Search', 'Analysis', 'Visualize', 'Export'] as const;

interface NavItemProps {
  manifest: ShardManifest;
  collapsed: boolean;
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

function NavItem({ manifest, collapsed }: NavItemProps) {
  const { navigation, name } = manifest;
  const hasSubRoutes = navigation.sub_routes && navigation.sub_routes.length > 0;

  return (
    <div className="nav-item-wrapper">
      <NavLink
        to={navigation.route}
        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        title={collapsed ? navigation.label : undefined}
        end={!hasSubRoutes}
      >
        <Icon name={navigation.icon} size={20} className="nav-icon" />
        {!collapsed && (
          <>
            <span className="nav-label">{navigation.label}</span>
            <NavBadge shardName={name} />
          </>
        )}
      </NavLink>

      {/* Sub-routes */}
      {!collapsed && hasSubRoutes && (
        <div className="nav-subroutes">
          {navigation.sub_routes!.map(sub => (
            <NavLink
              key={sub.id}
              to={sub.route}
              className={({ isActive }) => `nav-subitem ${isActive ? 'active' : ''}`}
            >
              <Icon name={sub.icon} size={16} className="nav-icon" />
              <span className="nav-label">{sub.label}</span>
              <NavBadge shardName={name} subRouteId={sub.id} />
            </NavLink>
          ))}
        </div>
      )}
    </div>
  );
}

interface NavGroupProps {
  category: string;
  shards: ShardManifest[];
  collapsed: boolean;
}

function NavGroup({ category, shards, collapsed }: NavGroupProps) {
  if (shards.length === 0) return null;

  return (
    <div className="nav-group">
      {!collapsed && <div className="nav-group-label">{category}</div>}
      {shards.map(shard => (
        <NavItem key={shard.name} manifest={shard} collapsed={collapsed} />
      ))}
    </div>
  );
}

export function Sidebar() {
  const { shards, sidebarCollapsed, setSidebarCollapsed } = useShell();

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
            <span className="brand-text">SHATTERED</span>
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
            collapsed={sidebarCollapsed}
          />
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <BadgeStatusIndicator />
        {!sidebarCollapsed && (
          <div className="sidebar-version">v0.1.0</div>
        )}
      </div>
    </aside>
  );
}
