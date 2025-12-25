/**
 * BadgeStatusIndicator - Shows warning when badge data may be stale
 *
 * Displayed in sidebar footer when badge fetch has failed.
 */

import { AlertTriangle } from 'lucide-react';
import { useBadgeContext } from '../../context/BadgeContext';

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return date.toLocaleDateString();
}

export function BadgeStatusIndicator() {
  const { hasError, lastSuccessTime } = useBadgeContext();

  if (!hasError) return null;

  const timeAgo = lastSuccessTime
    ? formatTimeAgo(lastSuccessTime)
    : 'unknown';

  return (
    <div
      className="badge-status-indicator warning"
      title={`Badge data may be stale. Last updated: ${timeAgo}`}
      role="status"
      aria-label="Badge data may be stale"
    >
      <AlertTriangle size={12} />
      <span className="badge-status-text">Stale</span>
    </div>
  );
}
