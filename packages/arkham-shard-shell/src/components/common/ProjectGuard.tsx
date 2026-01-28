/**
 * ProjectGuard - Component that ensures an active project is selected
 *
 * Shows a message prompting the user to select a project if none is active.
 * Can optionally redirect or show empty state.
 */

import { ReactNode } from 'react';
import { useProject } from '../../context/ProjectContext';
import { Icon } from './Icon';

interface ProjectGuardProps {
  /** Children to render when project is active */
  children: ReactNode;
  /** Custom message to show when no project is selected */
  message?: string;
  /** Whether to show an empty state instead of a message */
  showEmptyState?: boolean;
  /** Custom empty state component */
  emptyState?: ReactNode;
}

/**
 * Guard component that ensures an active project is selected.
 *
 * If no project is active, shows a message prompting selection.
 * Otherwise, renders children.
 */
export function ProjectGuard({
  children,
  message,
  showEmptyState = false,
  emptyState,
}: ProjectGuardProps) {
  const { activeProjectId, loading } = useProject();

  // Show loading state
  if (loading) {
    return (
      <div className="project-guard-loading">
        <div className="loading-spinner" />
        <p>Loading project...</p>
      </div>
    );
  }

  // Show empty state or message if no project
  if (!activeProjectId) {
    if (showEmptyState && emptyState) {
      return <>{emptyState}</>;
    }

    if (showEmptyState) {
      return (
        <div className="project-guard-empty">
          <Icon name="FolderOpen" size={48} />
          <h3>No Project Selected</h3>
          <p>
            {message ||
              'Please select a project from the project selector in the top bar to view data.'}
          </p>
        </div>
      );
    }

    return (
      <div className="project-guard-message">
        <Icon name="Info" size={24} />
        <p>{message || 'Please select a project to continue.'}</p>
      </div>
    );
  }

  // Project is active, render children
  return <>{children}</>;
}
