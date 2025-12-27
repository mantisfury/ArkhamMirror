/**
 * GenericShardPage - Dynamic shard renderer
 *
 * Renders shards that don't have custom UI using GenericList/GenericForm
 * based on their manifest configuration.
 */

import { useShell } from '../../context/ShellContext';
import { GenericList } from '../../components/generic/GenericList';
import { ShardUnavailable } from '../../components/common/ShardUnavailable';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Icon } from '../../components/common/Icon';

export function GenericShardPage() {
  const { currentShard, loading, connected } = useShell();

  // Show loading while fetching shard manifests
  if (loading) {
    return <LoadingSkeleton type="page" />;
  }

  // No current shard found for this route
  if (!currentShard) {
    return <ShardUnavailable />;
  }

  // Check if shard has list configuration for generic rendering
  // We render generically regardless of has_custom_ui flag, since if we're here
  // it means no custom UI route exists in the router
  const hasListConfig = currentShard.ui?.list_endpoint && currentShard.ui?.list_columns && currentShard.ui.list_columns.length > 0;

  return (
    <div className="generic-shard-page">
      {/* Header */}
      <div className="shard-header">
        <Icon name={currentShard.navigation.icon || 'Package'} size={32} />
        <div>
          <h1>{currentShard.navigation.label}</h1>
          <p className="shard-description">{currentShard.description}</p>
        </div>
        {!connected && (
          <span className="connection-warning">
            <Icon name="WifiOff" size={16} />
            Offline mode
          </span>
        )}
      </div>

      {/* Content */}
      {hasListConfig ? (
        <GenericList
          apiPrefix={currentShard.api_prefix}
          ui={currentShard.ui!}
        />
      ) : (
        <div className="shard-no-ui">
          <Icon name="LayoutList" size={48} />
          <h2>No UI Configuration</h2>
          <p>
            This shard ({currentShard.name}) doesn't have a list view configured.
          </p>
          <p className="api-hint">
            API available at: <code>{currentShard.api_prefix}</code>
          </p>
          <a
            href={`http://localhost:8105/docs#/${currentShard.name}`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
          >
            <Icon name="ExternalLink" size={16} />
            View API Docs
          </a>
        </div>
      )}
    </div>
  );
}
