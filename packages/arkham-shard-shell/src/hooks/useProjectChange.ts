/**
 * useProjectChange - Hook to react to project changes
 *
 * Listens to 'projectChanged' events and triggers a callback when the active project changes.
 * Useful for pages that need to refetch data when the project switches.
 */

import { useEffect, useRef } from 'react';
import { useProject } from '../context/ProjectContext';

interface UseProjectChangeOptions {
  /** Callback to execute when project changes */
  onProjectChange?: (projectId: string | null) => void;
  /** Whether to trigger callback on mount if project is already set */
  triggerOnMount?: boolean;
}

/**
 * Hook that listens to project changes and triggers a callback.
 *
 * @param options Configuration options
 * @returns Current active project ID
 */
export function useProjectChange(options: UseProjectChangeOptions = {}) {
  const { activeProjectId } = useProject();
  const { onProjectChange, triggerOnMount = false } = options;
  const previousProjectIdRef = useRef<string | null>(null);
  const callbackRef = useRef(onProjectChange);
  
  // Update callback ref when it changes
  useEffect(() => {
    callbackRef.current = onProjectChange;
  }, [onProjectChange]);

  // Listen to projectChanged events
  useEffect(() => {
    const handleProjectChange = (event: CustomEvent<{ projectId: string | null }>) => {
      const newProjectId = event.detail.projectId;
      if (newProjectId !== previousProjectIdRef.current && callbackRef.current) {
        callbackRef.current(newProjectId);
        previousProjectIdRef.current = newProjectId;
      }
    };

    window.addEventListener('projectChanged', handleProjectChange as EventListener);
    
    return () => {
      window.removeEventListener('projectChanged', handleProjectChange as EventListener);
    };
  }, []);

  // Trigger callback on mount if project is already set
  useEffect(() => {
    if (triggerOnMount && activeProjectId && callbackRef.current) {
      callbackRef.current(activeProjectId);
      previousProjectIdRef.current = activeProjectId;
    }
  }, [triggerOnMount, activeProjectId]);

  return activeProjectId;
}
