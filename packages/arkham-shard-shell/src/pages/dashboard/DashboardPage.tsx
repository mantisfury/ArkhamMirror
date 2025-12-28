/**
 * DashboardPage - System monitoring and configuration dashboard
 *
 * Provides tabs for:
 * - Overview: Service health and queue status
 * - LLM Config: Configure local LLM connection
 * - Database: Database operations and maintenance
 * - Workers: Queue management and monitoring
 * - Events: System event log
 */

import { useLocation, useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { OverviewTab, LLMConfigTab, DatabaseTab, WorkersTab, EventsTab } from './tabs';
import './DashboardPage.css';

type TabId = 'overview' | 'llm' | 'database' | 'workers' | 'events';

interface TabInfo {
  id: TabId;
  label: string;
  icon: string;
  description: string;
  route: string;
}

const TABS: TabInfo[] = [
  { id: 'overview', label: 'Overview', icon: 'LayoutDashboard', description: 'Service health and queue status', route: '/dashboard' },
  { id: 'llm', label: 'LLM Config', icon: 'Brain', description: 'Configure LLM connection', route: '/dashboard/llm' },
  { id: 'database', label: 'Database', icon: 'Database', description: 'Database operations', route: '/dashboard/database' },
  { id: 'workers', label: 'Workers', icon: 'Cpu', description: 'Queue management', route: '/dashboard/workers' },
  { id: 'events', label: 'Events', icon: 'ScrollText', description: 'System event log', route: '/dashboard/events' },
];

// Map URL paths to tab IDs
function getTabFromPath(pathname: string): TabId {
  if (pathname === '/dashboard' || pathname === '/dashboard/') return 'overview';
  const segment = pathname.replace('/dashboard/', '').split('/')[0];
  if (['llm', 'database', 'workers', 'events'].includes(segment)) {
    return segment as TabId;
  }
  return 'overview';
}

export function DashboardPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = getTabFromPath(location.pathname);

  const renderTab = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab />;
      case 'llm':
        return <LLMConfigTab />;
      case 'database':
        return <DatabaseTab />;
      case 'workers':
        return <WorkersTab />;
      case 'events':
        return <EventsTab />;
      default:
        return <OverviewTab />;
    }
  };

  return (
    <div className="dashboard-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="LayoutDashboard" size={28} />
          <div>
            <h1>Dashboard</h1>
            <p className="page-description">System monitoring and configuration</p>
          </div>
        </div>
      </header>

      <div className="dashboard-layout">
        {/* Tab Navigation */}
        <nav className="dashboard-nav">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => navigate(tab.route)}
            >
              <Icon name={tab.icon} size={20} />
              <div className="nav-content">
                <span className="nav-label">{tab.label}</span>
                <span className="nav-description">{tab.description}</span>
              </div>
            </button>
          ))}
        </nav>

        {/* Tab Content */}
        <main className="dashboard-content">
          {renderTab()}
        </main>
      </div>
    </div>
  );
}
