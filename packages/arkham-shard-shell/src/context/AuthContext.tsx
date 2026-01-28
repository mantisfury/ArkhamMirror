/**
 * AuthContext - Global authentication state management
 *
 * Provides authentication state, login/logout functions, and permission checks
 * throughout the application.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api';

// Types
interface User {
  id: string;
  email: string;
  display_name: string | null;
  role: 'admin' | 'analyst' | 'viewer';
  tenant_id: string;
  is_superuser: boolean;
  created_at: string;
  last_login: string | null;
}

interface Tenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  max_users: number;
  max_documents: number;
  created_at: string;
}

interface AuthState {
  user: User | null;
  tenant: Tenant | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  setupRequired: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string) => boolean;
}

// Constants
const TOKEN_KEY = 'arkham_token';
const API_BASE = '/api/auth';

// Context
const AuthContext = createContext<AuthContextType | null>(null);

// Permission definitions
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ['read', 'write', 'delete', 'admin', 'manage_users'],
  analyst: ['read', 'write', 'delete'],
  viewer: ['read'],
};

const ROLE_HIERARCHY: Record<string, number> = {
  viewer: 0,
  analyst: 1,
  admin: 2,
};

// Provider component
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    tenant: null,
    token: localStorage.getItem(TOKEN_KEY),
    isLoading: true,
    isAuthenticated: false,
    setupRequired: false,
  });

  // Check if initial setup is required
  const checkSetupRequired = useCallback(async (): Promise<boolean> => {
    try {
      const res = await apiFetch(`${API_BASE}/setup-required`);
      if (res.ok) {
        const data = await res.json();
        return data.setup_required === true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  // Fetch current user data
  const fetchUser = useCallback(async (token: string): Promise<boolean> => {
    try {
      const [userRes, tenantRes] = await Promise.all([
        apiFetch(`${API_BASE}/me`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        apiFetch(`${API_BASE}/me/tenant`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!userRes.ok) {
        throw new Error('Invalid token');
      }

      const user = await userRes.json();
      const tenant = tenantRes.ok ? await tenantRes.json() : null;

      setState(prev => ({
        ...prev,
        user,
        tenant,
        token,
        isAuthenticated: true,
        isLoading: false,
        setupRequired: false,
      }));

      return true;
    } catch {
      // Token invalid or expired
      localStorage.removeItem(TOKEN_KEY);
      setState(prev => ({
        ...prev,
        user: null,
        tenant: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
      }));
      return false;
    }
  }, []);

  // Initialize auth state on mount
  useEffect(() => {
    const init = async () => {
      // Check if setup is required first
      const setupRequired = await checkSetupRequired();

      if (setupRequired) {
        setState(prev => ({
          ...prev,
          setupRequired: true,
          isLoading: false,
        }));
        return;
      }

      // Try to restore session from stored token
      const token = localStorage.getItem(TOKEN_KEY);
      if (token) {
        await fetchUser(token);
      } else {
        setState(prev => ({
          ...prev,
          isLoading: false,
        }));
      }
    };

    init();
  }, [checkSetupRequired, fetchUser]);

  // Login function
  const login = async (email: string, password: string): Promise<void> => {
    // FastAPI-Users expects form data for OAuth2 password flow
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const res = await apiFetch(`${API_BASE}/jwt/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || 'Login failed');
    }

    const data = await res.json();
    const token = data.access_token;

    localStorage.setItem(TOKEN_KEY, token);
    await fetchUser(token);
  };

  // Logout function
  const logout = (): void => {
    localStorage.removeItem(TOKEN_KEY);
    setState({
      user: null,
      tenant: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
      setupRequired: false,
    });
  };

  // Refresh user data
  const refreshUser = async (): Promise<void> => {
    if (state.token) {
      await fetchUser(state.token);
    }
  };

  // Check if current user has a specific permission
  const hasPermission = (permission: string): boolean => {
    if (!state.user) return false;
    return ROLE_PERMISSIONS[state.user.role]?.includes(permission) ?? false;
  };

  // Check if current user has at least the specified role level
  const hasRole = (role: string): boolean => {
    if (!state.user) return false;
    const userLevel = ROLE_HIERARCHY[state.user.role] ?? 0;
    const requiredLevel = ROLE_HIERARCHY[role] ?? 0;
    return userLevel >= requiredLevel;
  };

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        logout,
        refreshUser,
        hasPermission,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Hook for consuming auth context
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Export types for use elsewhere
export type { User, Tenant, AuthState, AuthContextType };
