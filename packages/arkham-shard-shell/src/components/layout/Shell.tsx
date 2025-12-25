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
 */

import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { ContentArea } from './ContentArea';
import { useShell } from '../../context/ShellContext';

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
