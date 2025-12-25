/**
 * ShardUnavailable - Fallback page for missing shard routes
 *
 * Rendered when a shard route exists in URL but shard is not loaded.
 */

import { Icon } from './Icon';

export function ShardUnavailable() {
  return (
    <div className="shard-unavailable">
      <div className="shard-unavailable-content">
        <Icon name="PackageX" size={64} className="unavailable-icon" />
        <h1>Shard Unavailable</h1>
        <p>This shard is not currently available. Contact your administrator.</p>
        <button
          className="btn btn-primary"
          onClick={() => window.location.href = '/'}
        >
          <Icon name="Home" size={16} />
          Return to Dashboard
        </button>
      </div>
    </div>
  );
}
