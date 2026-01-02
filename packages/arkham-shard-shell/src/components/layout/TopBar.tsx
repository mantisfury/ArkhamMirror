/**
 * TopBar - Top navigation bar
 *
 * Shows current shard info, connection status, project selector, and quick actions.
 */

import { useShell } from '../../context/ShellContext';
import { Icon } from '../common/Icon';
import { ProjectSelector } from '../common/ProjectSelector';

export function TopBar() {
  const { currentShard, loading, error, connected, refetchShards } = useShell();

  // Determine connection state
  const getConnectionStatus = () => {
    if (loading) {
      return { icon: 'Loader2', className: 'loading', title: 'Connecting to Frame...', spin: true };
    }
    if (error) {
      return { icon: 'WifiOff', className: 'disconnected', title: `Disconnected: ${error.message}`, spin: false };
    }
    if (connected) {
      return { icon: 'Wifi', className: 'connected', title: 'Connected to Frame', spin: false };
    }
    return { icon: 'WifiOff', className: 'disconnected', title: 'Not connected', spin: false };
  };

  const status = getConnectionStatus();

  return (
    <header className="topbar">
      <div className="topbar-left">
        {currentShard && (
          <div className="current-shard">
            <Icon name={currentShard.navigation.icon} size={20} />
            <span className="shard-label">{currentShard.navigation.label}</span>
          </div>
        )}
      </div>

      <div className="topbar-center">
        {/* Placeholder for future command palette trigger */}
      </div>

      <div className="topbar-right">
        {/* Project selector */}
        <ProjectSelector />

        {/* Connection status indicator */}
        <div className="topbar-status">
          <button
            className={`status-indicator ${status.className}`}
            title={status.title}
            onClick={!connected ? refetchShards : undefined}
            disabled={loading}
          >
            <Icon
              name={status.icon}
              size={16}
              className={status.spin ? 'spin' : undefined}
            />
            {error && <span className="status-text">Retry</span>}
          </button>
        </div>

        {/* User actions */}
        <button className="topbar-action" title="Settings">
          <Icon name="Settings" size={18} />
        </button>
      </div>
    </header>
  );
}
