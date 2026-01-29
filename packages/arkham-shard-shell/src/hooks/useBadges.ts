/**
 * useBadges - Badge polling hook with error tracking
 *
 * STALE-WHILE-REVALIDATE PATTERN:
 * - On success: update badges, clear error
 * - On failure: KEEP existing badges, set hasError
 * - Badges are NEVER cleared on error
 *
 * Returns hasError for UI indication when badge data may be stale.
 */

import { useState, useEffect, useCallback } from 'react';
import type { BadgeInfo, BadgeState } from '../types';
import { apiFetch } from '../utils/api';

interface UseBadgesResult {
  badges: BadgeState;
  getBadge: (shardName: string, subRouteId?: string) => BadgeInfo | null;
  loading: boolean;
  hasError: boolean;
  lastSuccessTime: Date | null;
}

const POLL_INTERVAL = 30000; // 30 seconds

export function useBadges(): UseBadgesResult {
  const [badges, setBadges] = useState<BadgeState>({});
  const [loading, setLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [lastSuccessTime, setLastSuccessTime] = useState<Date | null>(null);

  useEffect(() => {
    async function fetchBadges() {
      try {
        const response = await apiFetch('/api/frame/badges');
        if (response.ok) {
          const data = await response.json();
          // SUCCESS: update badges and clear error state
          setBadges(data);
          setHasError(false);
          setLastSuccessTime(new Date());
        } else {
          // NON-OK RESPONSE: keep existing badges (stale-while-revalidate)
          // Only set error flag - do NOT clear badges
          setHasError(true);
          console.warn('Badge fetch failed:', response.status);
        }
      } catch (error) {
        // NETWORK ERROR: keep existing badges (stale-while-revalidate)
        // Only set error flag - do NOT clear badges
        setHasError(true);
        console.warn('Badge fetch error:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchBadges();
    const interval = setInterval(fetchBadges, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  const getBadge = useCallback((shardName: string, subRouteId?: string) => {
    // Badge key format: {shardName}:{subRouteId} for sub-routes
    const key = subRouteId ? `${shardName}:${subRouteId}` : shardName;
    return badges[key] || null;
  }, [badges]);

  return { badges, getBadge, loading, hasError, lastSuccessTime };
}
