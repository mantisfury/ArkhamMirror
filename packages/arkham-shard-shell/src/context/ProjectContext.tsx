/**
 * ProjectContext - Active project management
 *
 * Tracks the currently active project and provides methods to change it.
 * All embedding and search operations route to the active project's collections.
 */

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { useFetch } from '../hooks/useFetch';
import { apiFetch } from '../utils/api';

export interface Project {
  id: string;
  name: string;
  description?: string;
  status?: string;
  settings?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

interface ActiveProjectResponse {
  active: boolean;
  project_id: string | null;
  project: Project | null;
  collections: {
    documents: string;
    chunks: string;
    entities: string;
  };
}

interface ProjectsListResponse {
  projects: Project[];
  items?: Project[]; // For backwards compatibility
  total: number;
  limit?: number;
  offset?: number;
}

interface ProjectContextValue {
  // Active project state
  activeProject: Project | null;
  activeProjectId: string | null;
  isActive: boolean;
  collections: { documents: string; chunks: string; entities: string } | null;

  // All projects for selection
  projects: Project[];
  projectsLoading: boolean;
  projectsError: Error | null;

  // Loading state
  loading: boolean;
  error: Error | null;

  // Actions
  setActiveProject: (projectId: string | null) => Promise<boolean>;
  refreshProjects: () => void;
  refreshActiveProject: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [settingProject, setSettingProject] = useState(false);
  const [setError, setSetError] = useState<Error | null>(null);
  const [projectsCacheKey, setProjectsCacheKey] = useState(0);

  // Fetch active project state
  const {
    data: activeData,
    loading: activeLoading,
    error: activeError,
    refetch: refreshActiveProject,
  } = useFetch<ActiveProjectResponse>('/api/frame/active-project');

  // Fetch all projects for the selector (with cache-busting)
  const {
    data: projectsData,
    loading: projectsLoading,
    error: projectsError,
    refetch: refreshProjectsInternal,
  } = useFetch<ProjectsListResponse>(`/api/projects/?page_size=100&_t=${projectsCacheKey}`);

  const activeProjectId = activeData?.project_id ?? null;

  // Log errors for debugging
  useEffect(() => {
    if (projectsError) {
      console.error('Failed to fetch projects:', projectsError);
    }
    if (projectsData && (projectsData.projects?.length === 0 && projectsData.items?.length === 0)) {
      console.warn('Projects list is empty. User may not have access to any projects or may not be authenticated.');
    }
  }, [projectsError, projectsData]);

  // Watch for activeProjectId changes and emit event
  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent('projectChanged', {
        detail: { projectId: activeProjectId },
      })
    );
  }, [activeProjectId]);

  // Wrapper to refresh projects with cache-busting
  const refreshProjects = useCallback(() => {
    setProjectsCacheKey(prev => prev + 1);
    // URL change will trigger refetch automatically, but we can also call it explicitly for immediate refresh
    refreshProjectsInternal();
  }, [refreshProjectsInternal]);

  // Set active project
  const setActiveProject = useCallback(async (projectId: string | null): Promise<boolean> => {
    setSettingProject(true);
    setSetError(null);

    try {
      const response = await apiFetch('/api/frame/active-project', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to set active project: ${response.status}`);
      }

      // Store in localStorage as fallback
      if (projectId) {
        localStorage.setItem('arkham_last_active_project', projectId);
      } else {
        localStorage.removeItem('arkham_last_active_project');
      }

      // Refresh active project state
      refreshActiveProject();
      
      // Emit custom event for pages to react to project change
      window.dispatchEvent(new CustomEvent('projectChanged', {
        detail: { projectId }
      }));
      
      return true;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      setSetError(error);
      console.error('Failed to set active project:', error);
      return false;
    } finally {
      setSettingProject(false);
    }
  }, [refreshActiveProject]);

  return (
    <ProjectContext.Provider
      value={{
        // Active project state
        activeProject: activeData?.project || null,
        activeProjectId,
        isActive: activeData?.active || false,
        collections: activeData?.collections || null,

        // All projects (API returns 'projects', but some endpoints use 'items')
        projects: projectsData?.projects || projectsData?.items || [],
        projectsLoading,
        projectsError,

        // Combined loading/error
        loading: activeLoading || settingProject,
        error: activeError || setError,

        // Actions
        setActiveProject,
        refreshProjects,
        refreshActiveProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within ProjectProvider');
  }
  return context;
}
