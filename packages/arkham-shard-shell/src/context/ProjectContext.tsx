/**
 * ProjectContext - Active project management
 *
 * Tracks the currently active project and provides methods to change it.
 * All embedding and search operations route to the active project's collections.
 */

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { useFetch } from '../hooks/useFetch';

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
  items: Project[];
  total: number;
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

  // Fetch active project state
  const {
    data: activeData,
    loading: activeLoading,
    error: activeError,
    refetch: refreshActiveProject,
  } = useFetch<ActiveProjectResponse>('/api/projects/active');

  // Fetch all projects for the selector
  const {
    data: projectsData,
    loading: projectsLoading,
    error: projectsError,
    refetch: refreshProjects,
  } = useFetch<ProjectsListResponse>('/api/projects/?page_size=100');

  // Set active project
  const setActiveProject = useCallback(async (projectId: string | null): Promise<boolean> => {
    setSettingProject(true);
    setSetError(null);

    try {
      const response = await fetch('/api/projects/active', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to set active project: ${response.status}`);
      }

      // Refresh active project state
      refreshActiveProject();
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
        activeProjectId: activeData?.project_id || null,
        isActive: activeData?.active || false,
        collections: activeData?.collections || null,

        // All projects
        projects: projectsData?.items || [],
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
