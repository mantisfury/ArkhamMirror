/**
 * Shell - Main application shell layout
 *
 * Component hierarchy:
 * <Shell>
 *   <TopBar />
 *   <Sidebar />
 *   <ContentArea>
 *     <Outlet /> (router content)
 *   </ContentArea>
 * </Shell>
 *
 * SessionReconcile runs on mount so displayed user and project align with server after load/refresh.
 */

import { useEffect, useRef } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { ContentArea } from './ContentArea';
import { useShell } from '../../context/ShellContext';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';

/** On page load/refresh, refresh session data from server so UI (user, project) matches server state. */
function SessionReconcile() {
  const { refreshUser } = useAuth();
  const { refreshActiveProject } = useProject();
  const didReconcile = useRef(false);

  useEffect(() => {
    if (didReconcile.current) return;
    didReconcile.current = true;
    void refreshUser();
    refreshActiveProject();
  }, [refreshUser, refreshActiveProject]);

  return null;
}

export function Shell() {
  const { sidebarCollapsed, setSidebarCollapsed } = useShell();

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+B - Toggle sidebar
      if (e.ctrlKey && e.key === 'b') {
        e.preventDefault();
        setSidebarCollapsed(!sidebarCollapsed);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [sidebarCollapsed, setSidebarCollapsed]);

  return (
    <div className={`shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <SessionReconcile />
      <Sidebar />
      <div className="shell-main">
        <TopBar />
        <ContentArea>
          <Outlet />
        </ContentArea>
      </div>
    </div>
  );
}
