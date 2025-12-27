/**
 * ProjectsPage - Project workspace management
 *
 * Provides UI for creating, viewing, and managing project workspaces.
 * Projects organize documents, entities, and analyses into collaborative spaces.
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './ProjectsPage.css';

// Types
interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  settings: Record<string, unknown>;
  metadata: Record<string, unknown>;
  member_count: number;
  document_count: number;
}

interface ProjectListResponse {
  projects: Project[];
  total: number;
  limit: number;
  offset: number;
}

const STATUS_COLORS: Record<string, string> = {
  active: 'status-active',
  archived: 'status-archived',
  completed: 'status-completed',
  on_hold: 'status-on-hold',
};

const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  archived: 'Archived',
  completed: 'Completed',
  on_hold: 'On Hold',
};

export function ProjectsPage() {
  const { toast } = useToast();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);

  // Build query string
  const queryParams = new URLSearchParams();
  if (statusFilter) queryParams.append('status', statusFilter);
  if (searchQuery) queryParams.append('search', searchQuery);
  const queryString = queryParams.toString();

  // Fetch projects
  const { data, loading, error, refetch } = useFetch<ProjectListResponse>(
    `/api/projects/${queryString ? `?${queryString}` : ''}`
  );

  const projects = data?.projects || [];
  const total = data?.total || 0;

  const handleCreateProject = useCallback(async (name: string, description: string) => {
    try {
      const response = await fetch('/api/projects/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          owner_id: 'system',
          status: 'active',
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create project');
      }

      toast.success('Project created successfully');
      setShowCreateModal(false);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create project');
    }
  }, [toast, refetch]);

  const handleUpdateProject = useCallback(async (id: string, name: string, description: string, status: string) => {
    try {
      const response = await fetch(`/api/projects/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, status }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update project');
      }

      toast.success('Project updated successfully');
      setShowEditModal(false);
      setSelectedProject(null);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update project');
    }
  }, [toast, refetch]);

  const handleArchiveProject = useCallback(async (id: string) => {
    if (!confirm('Are you sure you want to archive this project?')) return;

    try {
      const response = await fetch(`/api/projects/${id}/archive`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to archive project');
      }

      toast.success('Project archived');
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to archive project');
    }
  }, [toast, refetch]);

  const handleRestoreProject = useCallback(async (id: string) => {
    try {
      const response = await fetch(`/api/projects/${id}/restore`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to restore project');
      }

      toast.success('Project restored');
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to restore project');
    }
  }, [toast, refetch]);

  const handleDeleteProject = useCallback(async (id: string) => {
    if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) return;

    try {
      const response = await fetch(`/api/projects/${id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete project');
      }

      toast.success('Project deleted');
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete project');
    }
  }, [toast, refetch]);

  return (
    <div className="projects-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="FolderKanban" size={28} />
          <div>
            <h1>Projects</h1>
            <p className="page-description">Manage project workspaces and document collections</p>
          </div>
        </div>

        <button
          className="btn btn-primary"
          onClick={() => setShowCreateModal(true)}
        >
          <Icon name="Plus" size={16} />
          New Project
        </button>
      </header>

      {/* Filters */}
      <div className="projects-filters">
        <div className="search-box">
          <Icon name="Search" size={16} />
          <input
            type="text"
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <select
          className="filter-select"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="completed">Completed</option>
          <option value="on_hold">On Hold</option>
        </select>
      </div>

      {/* Projects List */}
      <main className="projects-content">
        {loading ? (
          <div className="projects-loading">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Loading projects...</span>
          </div>
        ) : error ? (
          <div className="projects-error">
            <Icon name="AlertCircle" size={32} />
            <span>Failed to load projects</span>
            <button className="btn btn-secondary" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        ) : projects.length > 0 ? (
          <div className="projects-grid">
            {projects.map((project) => (
              <div key={project.id} className="project-card">
                <div className="project-header">
                  <div className="project-info">
                    <h3>{project.name}</h3>
                    <span className={`status-badge ${STATUS_COLORS[project.status]}`}>
                      {STATUS_LABELS[project.status] || project.status}
                    </span>
                  </div>
                  <div className="project-actions">
                    <button
                      className="icon-btn"
                      onClick={() => {
                        setSelectedProject(project);
                        setShowEditModal(true);
                      }}
                      title="Edit project"
                    >
                      <Icon name="Edit2" size={16} />
                    </button>
                    {project.status === 'archived' ? (
                      <button
                        className="icon-btn"
                        onClick={() => handleRestoreProject(project.id)}
                        title="Restore project"
                      >
                        <Icon name="RotateCcw" size={16} />
                      </button>
                    ) : (
                      <button
                        className="icon-btn"
                        onClick={() => handleArchiveProject(project.id)}
                        title="Archive project"
                      >
                        <Icon name="Archive" size={16} />
                      </button>
                    )}
                    <button
                      className="icon-btn danger"
                      onClick={() => handleDeleteProject(project.id)}
                      title="Delete project"
                    >
                      <Icon name="Trash2" size={16} />
                    </button>
                  </div>
                </div>

                <p className="project-description">{project.description || 'No description'}</p>

                <div className="project-stats">
                  <div className="stat">
                    <Icon name="FileText" size={14} />
                    <span>{project.document_count} documents</span>
                  </div>
                  <div className="stat">
                    <Icon name="Users" size={14} />
                    <span>{project.member_count} members</span>
                  </div>
                </div>

                <div className="project-footer">
                  <span className="project-date">
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="projects-empty">
            <Icon name="FolderKanban" size={48} />
            <h3>No projects found</h3>
            <p>Create your first project to get started</p>
            <button
              className="btn btn-primary"
              onClick={() => setShowCreateModal(true)}
            >
              <Icon name="Plus" size={16} />
              Create Project
            </button>
          </div>
        )}

        {projects.length > 0 && (
          <div className="projects-stats">
            <span>Showing {projects.length} of {total} projects</span>
          </div>
        )}
      </main>

      {/* Create Project Modal */}
      {showCreateModal && (
        <ProjectModal
          title="Create New Project"
          onClose={() => setShowCreateModal(false)}
          onSave={handleCreateProject}
        />
      )}

      {/* Edit Project Modal */}
      {showEditModal && selectedProject && (
        <ProjectModal
          title="Edit Project"
          project={selectedProject}
          onClose={() => {
            setShowEditModal(false);
            setSelectedProject(null);
          }}
          onSave={(name, description, status) =>
            handleUpdateProject(selectedProject.id, name, description, status || selectedProject.status)
          }
        />
      )}
    </div>
  );
}

// Modal Component
interface ProjectModalProps {
  title: string;
  project?: Project;
  onClose: () => void;
  onSave: (name: string, description: string, status?: string) => void;
}

function ProjectModal({ title, project, onClose, onSave }: ProjectModalProps) {
  const [name, setName] = useState(project?.name || '');
  const [description, setDescription] = useState(project?.description || '');
  const [status, setStatus] = useState(project?.status || 'active');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSave(name, description, status);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-content">
          <div className="form-group">
            <label htmlFor="project-name">Project Name *</label>
            <input
              id="project-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter project name"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="project-description">Description</label>
            <textarea
              id="project-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Enter project description"
              rows={4}
            />
          </div>

          {project && (
            <div className="form-group">
              <label htmlFor="project-status">Status</label>
              <select
                id="project-status"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value="active">Active</option>
                <option value="on_hold">On Hold</option>
                <option value="completed">Completed</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={!name.trim()}>
              {project ? 'Save Changes' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
