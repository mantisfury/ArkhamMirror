/**
 * BadgeContext - Badge state with error tracking
 *
 * Wraps useBadges hook for global access
 */

import { createContext, useContext, ReactNode } from 'react';
import { useBadges } from '../hooks/useBadges';
import type { BadgeInfo, BadgeState } from '../types';

interface BadgeContextValue {
  badges: BadgeState;
  getBadge: (shardName: string, subRouteId?: string) => BadgeInfo | null;
  loading: boolean;
  hasError: boolean;
  lastSuccessTime: Date | null;
}

const BadgeContext = createContext<BadgeContextValue | null>(null);

export function BadgeProvider({ children }: { children: ReactNode }) {
  const badgeState = useBadges();

  return (
    <BadgeContext.Provider value={badgeState}>
      {children}
    </BadgeContext.Provider>
  );
}

export function useBadgeContext() {
  const context = useContext(BadgeContext);
  if (!context) {
    throw new Error('useBadgeContext must be used within BadgeProvider');
  }
  return context;
}
