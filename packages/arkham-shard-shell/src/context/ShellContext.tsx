/**
 * ShellContext - Navigation context
 *
 * Provides shard navigation and manifest access.
 * Dynamically fetches shards from Frame API.
 */

import { createContext, useContext, useState, useCallback, useEffect, useMemo, ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import type { ShardManifest } from '../types';
import { useFetch } from '../hooks/useFetch';

// API response type
interface ShardsApiResponse {
  shards: ShardManifest[];
  count: number;
}

interface ShellContextValue {
  shards: ShardManifest[];
  currentShard: ShardManifest | null;
  loading: boolean;
  error: Error | null;
  connected: boolean;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  navigateToShard: (shardName: string, params?: Record<string, string>) => void;
  getShardRoute: (shardName: string) => string | null;
  refetchShards: () => void;
}

const ShellContext = createContext<ShellContextValue | null>(null);

// Fallback shards for offline mode or when Frame is unavailable
const FALLBACK_SHARDS: ShardManifest[] = [
  {
    name: 'dashboard',
    version: '0.1.0',
    description: 'System monitoring and status dashboard',
    entry_point: 'arkham_shard_dashboard:DashboardShard',
    api_prefix: '/api/dashboard',
    requires_frame: '>=0.1.0',
    navigation: {
      category: 'System',
      order: 0,
      icon: 'LayoutDashboard',
      label: 'Dashboard',
      route: '/dashboard',
    },
    ui: {
      has_custom_ui: false,
    },
  },
];

export function ShellProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();

  // Fetch shards from Frame API with background refetch for polling
  const { data: shardsData, loading, error, refetch: refetchShards } = useFetch<ShardsApiResponse>(
    '/api/shards/',
    { backgroundRefetch: true }
  );

  // Poll shards list periodically (every 60 seconds)
  useEffect(() => {
    const pollInterval = setInterval(() => {
      refetchShards();
    }, 60000); // Poll every 60 seconds

    return () => {
      clearInterval(pollInterval);
    };
  }, [refetchShards]);

  // Filter shards that have navigation config (can be displayed in sidebar)
  // Use fallback shards if API fails or returns empty
  const shards = useMemo(() => {
    if (shardsData?.shards && shardsData.shards.length > 0) {
      // Filter to only shards with navigation
      return shardsData.shards.filter(s => s.navigation && s.navigation.route);
    }
    // Use fallback when API unavailable
    return FALLBACK_SHARDS;
  }, [shardsData]);

  // Connection status - true if we successfully got data from API
  const connected = !loading && !error && !!shardsData;

  // Sidebar state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('shell:sidebar_collapsed') === 'true';
    } catch {
      return false;
    }
  });

  // Persist sidebar state
  useEffect(() => {
    try {
      localStorage.setItem('shell:sidebar_collapsed', String(sidebarCollapsed));
    } catch {
      // Ignore storage errors
    }
  }, [sidebarCollapsed]);

  // Find current shard based on route
  const currentShard = shards.find(s => {
    const route = s.navigation.route;
    return location.pathname === route || location.pathname.startsWith(route + '/');
  }) || null;

  const navigateToShard = useCallback((shardName: string, params?: Record<string, string>) => {
    const shard = shards.find(s => s.name === shardName);
    if (!shard) {
      console.warn(`Shard "${shardName}" not found`);
      return;
    }

    let url = shard.navigation.route;
    if (params && Object.keys(params).length > 0) {
      const searchParams = new URLSearchParams(params);
      url += '?' + searchParams.toString();
    }
    navigate(url);
  }, [shards, navigate]);

  const getShardRoute = useCallback((shardName: string): string | null => {
    const shard = shards.find(s => s.name === shardName);
    return shard?.navigation.route || null;
  }, [shards]);

  return (
    <ShellContext.Provider
      value={{
        shards,
        currentShard,
        loading,
        error,
        connected,
        sidebarCollapsed,
        setSidebarCollapsed,
        navigateToShard,
        getShardRoute,
        refetchShards,
      }}
    >
      {children}
    </ShellContext.Provider>
  );
}

export function useShell() {
  const context = useContext(ShellContext);
  if (!context) {
    throw new Error('useShell must be used within ShellProvider');
  }
  return context;
}
