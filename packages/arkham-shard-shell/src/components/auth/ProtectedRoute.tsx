/**
 * ProtectedRoute - Route guard for authenticated routes
 *
 * Redirects to login if user is not authenticated, or to setup if setup is required.
 * Can also enforce role requirements.
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Icon } from '../common/Icon';

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** Minimum role required to access this route */
  requiredRole?: 'viewer' | 'analyst' | 'admin';
  /** Specific permission required */
  requiredPermission?: string;
}

export function ProtectedRoute({
  children,
  requiredRole,
  requiredPermission,
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, setupRequired, hasRole, hasPermission } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking auth state
  if (isLoading) {
    return (
      <div className="auth-loading-screen">
        <Icon name="Loader2" size={48} className="spin" />
        <p>Loading...</p>
      </div>
    );
  }

  // Redirect to setup wizard if setup is required
  if (setupRequired) {
    return <Navigate to="/setup" replace />;
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role requirement
  if (requiredRole && !hasRole(requiredRole)) {
    return (
      <div className="auth-forbidden">
        <Icon name="ShieldX" size={48} />
        <h2>Access Denied</h2>
        <p>You need {requiredRole} permissions to access this page.</p>
      </div>
    );
  }

  // Check permission requirement
  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <div className="auth-forbidden">
        <Icon name="ShieldX" size={48} />
        <h2>Access Denied</h2>
        <p>You don't have the required permissions to access this page.</p>
      </div>
    );
  }

  return <>{children}</>;
}

/**
 * AdminRoute - Shorthand for routes requiring admin role
 */
export function AdminRoute({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute requiredRole="admin">{children}</ProtectedRoute>;
}

/**
 * AnalystRoute - Shorthand for routes requiring analyst role or higher
 */
export function AnalystRoute({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute requiredRole="analyst">{children}</ProtectedRoute>;
}
