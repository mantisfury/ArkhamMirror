/**
 * ProjectSelector - Active project selector for TopBar
 *
 * Dropdown to select the active project for embedding/search operations.
 */

import { useState, useRef, useEffect } from 'react';
import { useProject } from '../../context/ProjectContext';
import { Icon } from './Icon';

export function ProjectSelector() {
  const {
    activeProject,
    activeProjectId,
    projects,
    loading,
    setActiveProject,
  } = useProject();

  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const handleSelect = async (projectId: string | null) => {
    await setActiveProject(projectId);
    setIsOpen(false);
  };

  return (
    <div className="project-selector" ref={dropdownRef}>
      <button
        className={`project-selector-button ${activeProjectId ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading}
        title={activeProject ? `Active: ${activeProject.name}` : 'No active project (global mode)'}
      >
        <Icon name="FolderOpen" size={16} />
        <span className="project-name">
          {activeProject ? activeProject.name : 'Global'}
        </span>
        <Icon name={isOpen ? 'ChevronUp' : 'ChevronDown'} size={14} />
      </button>

      {isOpen && (
        <div className="project-selector-dropdown">
          <div className="dropdown-header">
            <span>Select Project</span>
          </div>

          <div className="dropdown-options">
            {/* Global option */}
            <button
              className={`dropdown-option ${!activeProjectId ? 'selected' : ''}`}
              onClick={() => handleSelect(null)}
            >
              <Icon name="Globe" size={16} />
              <div className="option-content">
                <span className="option-name">Global (No Project)</span>
                <span className="option-desc">Use global collections</span>
              </div>
              {!activeProjectId && <Icon name="Check" size={16} className="check-icon" />}
            </button>

            {/* Separator */}
            {projects.length > 0 && <div className="dropdown-separator" />}

            {/* Project options */}
            {projects.map((project) => (
              <button
                key={project.id}
                className={`dropdown-option ${activeProjectId === project.id ? 'selected' : ''}`}
                onClick={() => handleSelect(project.id)}
              >
                <Icon name="Folder" size={16} />
                <div className="option-content">
                  <span className="option-name">{project.name}</span>
                  {project.description && (
                    <span className="option-desc">{project.description}</span>
                  )}
                </div>
                {activeProjectId === project.id && <Icon name="Check" size={16} className="check-icon" />}
              </button>
            ))}

            {projects.length === 0 && (
              <div className="dropdown-empty">
                No projects available
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
