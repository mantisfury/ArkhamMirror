/**
 * ProjectsPage - Project workspace management
 *
 * Provides UI for creating, viewing, and managing project workspaces.
 * Projects organize documents, entities, and analyses into collaborative spaces.
 * Each project has isolated vector collections with configurable embedding models.
 */

import { useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';
import { usePaginatedFetch } from '../../hooks';
import { apiDelete, apiFetch, apiGet, apiPost, apiPut } from '../../utils/api';
import './ProjectsPage.css';

// Types
interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
  settings: {
    embedding_model?: string;
    embedding_dimensions?: number;
    [key: string]: unknown;
  };
  metadata: Record<string, unknown>;
  member_count: number;
  document_count: number;
}

interface EmbeddingModel {
  name: string;
  dimensions: number;
  description: string;
}

interface CollectionStats {
  available: boolean;
  collections: Record<string, {
    name: string;
    vector_count?: number;
    dimensions?: number;
    status?: string;
    exists?: boolean;
    error?: string;
  }>;
}

interface ProjectDocument {
  id: string;
  project_id: string;
  document_id: string;
  added_at: string;
  added_by: string;
}

interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  role: string;
  added_at: string;
  added_by: string;
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
  const { user: currentUser } = useAuth();
  const { refreshProjects } = useProject();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([]);

  // Fetch projects with usePaginatedFetch (auth header automatically included)
  const { items: projects, total, loading, error, refetch } = usePaginatedFetch<Project>(
    '/api/projects/',
    {
      params: {
        status: statusFilter || undefined,
        search: searchQuery || undefined,
      },
      itemsKey: 'projects',  // API returns { projects, total, limit, offset }
    }
  );

  // Fetch available embedding models
  useEffect(() => {
    apiGet<EmbeddingModel[]>('/api/projects/embedding-models')
      .then((data) => setEmbeddingModels(Array.isArray(data) ? data : []))
      .catch((err) => console.error('Failed to fetch embedding models:', err));
  }, []);

  const handleCreateProject = useCallback(async (
    name: string,
    description: string,
    status?: string,
    embeddingModel?: string
  ) => {
    try {
      await apiPost('/api/projects/', {
        name,
        description,
        status: status || 'active',
        embedding_model: embeddingModel || 'all-MiniLM-L6-v2',
        create_collections: true,
      });

      toast.success('Project created with isolated vector collections');
      setShowCreateModal(false);
      refetch();
      refreshProjects();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create project');
    }
  }, [toast, refetch, refreshProjects]);

  const handleUpdateProject = useCallback(async (id: string, name: string, description: string, status: string) => {
    try {
      await apiPut(`/api/projects/${id}`, { name, description, status });

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
      await apiPost(`/api/projects/${id}/archive`);

      toast.success('Project archived');
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to archive project');
    }
  }, [toast, refetch]);

  const handleRestoreProject = useCallback(async (id: string) => {
    try {
      await apiPost(`/api/projects/${id}/restore`);

      toast.success('Project restored');
      refetch();
      refreshProjects();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to restore project');
    }
  }, [toast, refetch, refreshProjects]);

  const handleDeleteProject = useCallback(async (id: string) => {
    try {
      await apiDelete(`/api/projects/${id}`);

      toast.success('Project deleted');
      setShowDeleteConfirmModal(false);
      setProjectToDelete(null);
      refetch();
      refreshProjects();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete project');
    }
  }, [toast, refetch, refreshProjects]);

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
                        setShowDetailsModal(true);
                      }}
                      title="View details"
                    >
                      <Icon name="Eye" size={16} />
                    </button>
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
                      onClick={() => {
                        setProjectToDelete(project);
                        setShowDeleteConfirmModal(true);
                      }}
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

                {/* Embedding Model Info */}
                <div className="project-embedding">
                  <Icon name="Brain" size={14} />
                  <span>
                    {project.settings?.embedding_model || 'all-MiniLM-L6-v2'}
                    {project.settings?.embedding_dimensions && (
                      <span className="dim-badge">{project.settings.embedding_dimensions}D</span>
                    )}
                  </span>
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
          embeddingModels={embeddingModels}
          onClose={() => setShowCreateModal(false)}
          onSave={handleCreateProject}
        />
      )}

      {/* Edit Project Modal */}
      {showEditModal && selectedProject && (
        <ProjectModal
          title="Edit Project"
          project={selectedProject}
          embeddingModels={embeddingModels}
          onClose={() => {
            setShowEditModal(false);
            setSelectedProject(null);
          }}
          onSave={(name, description, status) =>
            handleUpdateProject(selectedProject.id, name, description, status || selectedProject.status)
          }
        />
      )}

      {/* Project Details Modal */}
      {showDetailsModal && selectedProject && (
        <ProjectDetailsModal
          project={selectedProject}
          embeddingModels={embeddingModels}
          onClose={() => {
            setShowDetailsModal(false);
            setSelectedProject(null);
          }}
          onRefresh={refetch}
        />
      )}

      {/* Delete Project Confirmation Modal */}
      {showDeleteConfirmModal && projectToDelete && (
        <div className="modal-overlay" onClick={() => { setShowDeleteConfirmModal(false); setProjectToDelete(null); }}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Delete project?</h2>
              <button className="icon-btn" onClick={() => { setShowDeleteConfirmModal(false); setProjectToDelete(null); }}>
                <Icon name="X" size={20} />
              </button>
            </div>
            <div className="modal-content">
              <p>
                <strong>{projectToDelete.name}</strong> and all associated data will be permanently deleted. This includes:
              </p>
              <ul style={{ margin: '0.5rem 0 1rem 1.5rem', color: 'var(--color-muted)' }}>
                <li>Documents and embeddings</li>
                <li>Vector collections</li>
                <li>Analyses (ACH matrices, graphs, anomalies, etc.)</li>
                <li>Members and activity</li>
              </ul>
              <p style={{ marginBottom: '1rem' }}>This action cannot be undone.</p>
              <div className="modal-actions" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => { setShowDeleteConfirmModal(false); setProjectToDelete(null); }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => projectToDelete && handleDeleteProject(projectToDelete.id)}
                >
                  <Icon name="Trash2" size={14} style={{ marginRight: '4px' }} />
                  Delete project
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Modal Component
interface ProjectModalProps {
  title: string;
  project?: Project;
  embeddingModels: EmbeddingModel[];
  onClose: () => void;
  onSave: (name: string, description: string, status?: string, embeddingModel?: string) => void | Promise<void>;
}

function ProjectModal({ title, project, embeddingModels, onClose, onSave }: ProjectModalProps) {
  const [name, setName] = useState(project?.name || '');
  const [description, setDescription] = useState(project?.description || '');
  const [status, setStatus] = useState(project?.status || 'active');
  const [embeddingModel, setEmbeddingModel] = useState(
    project?.settings?.embedding_model || 'all-MiniLM-L6-v2'
  );
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || saving) return;
    
    setSaving(true);
    try {
      await onSave(name, description, status, embeddingModel);
    } finally {
      setSaving(false);
    }
  };

  const selectedModelInfo = embeddingModels.find(m => m.name === embeddingModel);

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

          {/* Embedding Model Selection - only for new projects */}
          {!project && (
            <div className="form-group">
              <label htmlFor="embedding-model">
                <Icon name="Brain" size={14} style={{ marginRight: '4px' }} />
                Embedding Model
              </label>
              <select
                id="embedding-model"
                value={embeddingModel}
                onChange={(e) => setEmbeddingModel(e.target.value)}
              >
                {embeddingModels.map(model => (
                  <option key={model.name} value={model.name}>
                    {model.name} ({model.dimensions}D)
                  </option>
                ))}
              </select>
              {selectedModelInfo && (
                <p className="form-hint">
                  {selectedModelInfo.description}
                  <br />
                  <strong>Note:</strong> Each project has isolated vector collections.
                  Different projects can use different embedding models.
                </p>
              )}
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={!name.trim() || saving}>
              {saving ? (
                <>
                  <Icon name="Loader2" size={16} className="spin" />
                  {project ? 'Saving...' : 'Creating...'}
                </>
              ) : (
                project ? 'Save Changes' : 'Create Project'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Project Details Modal - Shows collection stats and allows model changes
interface ProjectDetailsModalProps {
  project: Project;
  embeddingModels: EmbeddingModel[];
  onClose: () => void;
  onRefresh: () => void;
}

function ProjectDetailsModal({ project, embeddingModels, onClose, onRefresh }: ProjectDetailsModalProps) {
  const { toast } = useToast();
  const { hasRole } = useAuth();
  const [collectionStats, setCollectionStats] = useState<CollectionStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [showChangeModel, setShowChangeModel] = useState(false);
  const [newModel, setNewModel] = useState(project.settings?.embedding_model || 'all-MiniLM-L6-v2');
  const [changing, setChanging] = useState(false);
  const [projectDocuments, setProjectDocuments] = useState<ProjectDocument[]>([]);
  const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [showEditMembersModal, setShowEditMembersModal] = useState(false);

  const fetchDocuments = useCallback(() => {
    setLoadingDocuments(true);
    apiFetch(`/api/projects/${project.id}/documents`)
      .then(res => (res.ok ? res.json() : []))
      .then(data => setProjectDocuments(Array.isArray(data) ? data : []))
      .catch(() => setProjectDocuments([]))
      .finally(() => setLoadingDocuments(false));
  }, [project.id]);

  const fetchMembers = useCallback(() => {
    setLoadingMembers(true);
    apiFetch(`/api/projects/${project.id}/members`)
      .then(res => (res.ok ? res.json() : []))
      .then(data => setProjectMembers(Array.isArray(data) ? data : []))
      .catch(() => setProjectMembers([]))
      .finally(() => setLoadingMembers(false));
  }, [project.id]);

  // Fetch collection stats
  useEffect(() => {
    setLoadingStats(true);
    apiFetch(`/api/projects/${project.id}/collections`)
      .then(res => res.json())
      .then(data => setCollectionStats(data))
      .catch(err => console.error('Failed to fetch collection stats:', err))
      .finally(() => setLoadingStats(false));
  }, [project.id]);

  // Fetch documents and members for this project
  useEffect(() => {
    fetchDocuments();
    fetchMembers();
  }, [fetchDocuments, fetchMembers]);

  const currentModel = project.settings?.embedding_model || 'all-MiniLM-L6-v2';
  const currentDims = project.settings?.embedding_dimensions || 384;
  const newModelInfo = embeddingModels.find(m => m.name === newModel);
  const requiresWipe = newModelInfo && newModelInfo.dimensions !== currentDims;

  const handleChangeModel = async () => {
    if (!newModel || newModel === currentModel) return;

    if (requiresWipe) {
      const confirmed = confirm(
        `Changing from ${currentModel} (${currentDims}D) to ${newModel} (${newModelInfo?.dimensions}D) ` +
        `requires wiping all vectors in this project's collections.\n\n` +
        `This will delete all embedded vectors. You will need to re-embed documents.\n\n` +
        `Are you sure you want to proceed?`
      );
      if (!confirmed) return;
    }

    setChanging(true);
    try {
      const result = await apiPut<{ success?: boolean; wiped?: boolean; message?: string; detail?: string }>(
        `/api/projects/${project.id}/embedding-model`,
        { model: newModel, wipe_collections: requiresWipe },
      );

      if (!result.success) {
        throw new Error(result.message || result.detail || 'Failed to change model');
      }

      toast.success(
        result.wiped
          ? `Model changed to ${newModel}. Collections wiped and recreated.`
          : `Model changed to ${newModel}`
      );
      setShowChangeModel(false);
      onRefresh();

      // Refresh stats
      const statsRes = await apiFetch(`/api/projects/${project.id}/collections`);
      setCollectionStats(await statsRes.json());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to change model');
    } finally {
      setChanging(false);
    }
  };

  const getTotalVectors = () => {
    if (!collectionStats?.collections) return 0;
    return Object.values(collectionStats.collections).reduce(
      (sum, c) => sum + (c.vector_count || 0),
      0
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            <Icon name="FolderKanban" size={20} style={{ marginRight: '8px' }} />
            {project.name}
          </h2>
          <button className="icon-btn" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <div className="modal-content">
          {/* Project Info */}
          <div className="details-section">
            <h3>Project Info</h3>
            <p className="project-description">{project.description || 'No description'}</p>
            <div className="details-grid">
              <div className="detail-item">
                <span className="detail-label">Status</span>
                <span className={`status-badge ${STATUS_COLORS[project.status]}`}>
                  {STATUS_LABELS[project.status]}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Documents</span>
                <span>{project.document_count}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Members</span>
                <span>{project.member_count}</span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Created</span>
                <span>{new Date(project.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          {/* Documents in this project */}
          <div className="details-section">
            <h3>
              <Icon name="FileText" size={16} style={{ marginRight: '8px' }} />
              Documents ({projectDocuments.length})
            </h3>
            {loadingDocuments ? (
              <div className="loading-stats">
                <Icon name="Loader2" size={20} className="spin" />
                <span>Loading documents...</span>
              </div>
            ) : projectDocuments.length === 0 ? (
              <p className="section-empty">No documents in this project yet.</p>
            ) : (
              <ul className="project-doc-list">
                {projectDocuments.map(doc => (
                  <li key={doc.id}>
                    <Link to={`/documents?id=${doc.document_id}`} className="project-doc-link">
                      {doc.document_id}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Members */}
          <div className="details-section">
            <h3>
              <Icon name="Users" size={16} style={{ marginRight: '8px' }} />
              Members ({projectMembers.length})
            </h3>
            {hasRole('admin') && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ marginBottom: '8px' }}
                onClick={() => setShowEditMembersModal(true)}
              >
                <Icon name="UserPlus" size={14} style={{ marginRight: '4px' }} />
                Edit Members
              </button>
            )}
            {loadingMembers ? (
              <div className="loading-stats">
                <Icon name="Loader2" size={20} className="spin" />
                <span>Loading members...</span>
              </div>
            ) : projectMembers.length === 0 ? (
              <p className="section-empty">No members yet.</p>
            ) : (
              <ul className="project-members-list">
                {projectMembers.map(m => (
                  <li key={m.id}>
                    <span className="member-user-id">{m.user_id}</span>
                    <span className="member-role">{m.role}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Embedding Model Section */}
          <div className="details-section">
            <h3>
              <Icon name="Brain" size={16} style={{ marginRight: '8px' }} />
              Embedding Model
            </h3>
            <div className="model-info-card">
              <div className="model-current">
                <strong>{currentModel}</strong>
                <span className="dim-badge">{currentDims}D</span>
              </div>
              <p className="model-description">
                {embeddingModels.find(m => m.name === currentModel)?.description || ''}
              </p>
              {!showChangeModel ? (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowChangeModel(true)}
                >
                  <Icon name="RefreshCw" size={14} />
                  Change Model
                </button>
              ) : (
                <div className="model-change-form">
                  <select
                    value={newModel}
                    onChange={(e) => setNewModel(e.target.value)}
                    disabled={changing}
                  >
                    {embeddingModels.map(model => (
                      <option key={model.name} value={model.name}>
                        {model.name} ({model.dimensions}D)
                      </option>
                    ))}
                  </select>
                  {requiresWipe && (
                    <div className="warning-box">
                      <Icon name="AlertTriangle" size={16} />
                      <span>
                        Dimension mismatch ({currentDims}D → {newModelInfo?.dimensions}D).
                        Collections will be wiped.
                      </span>
                    </div>
                  )}
                  <div className="model-change-actions">
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setShowChangeModel(false);
                        setNewModel(currentModel);
                      }}
                      disabled={changing}
                    >
                      Cancel
                    </button>
                    <button
                      className={`btn btn-sm ${requiresWipe ? 'btn-danger' : 'btn-primary'}`}
                      onClick={handleChangeModel}
                      disabled={changing || newModel === currentModel}
                    >
                      {changing ? (
                        <>
                          <Icon name="Loader2" size={14} className="spin" />
                          Changing...
                        </>
                      ) : requiresWipe ? (
                        'Wipe & Change'
                      ) : (
                        'Apply'
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Vector Collections Section */}
          <div className="details-section">
            <h3>
              <Icon name="Database" size={16} style={{ marginRight: '8px' }} />
              Vector Collections
            </h3>
            {loadingStats ? (
              <div className="loading-stats">
                <Icon name="Loader2" size={20} className="spin" />
                <span>Loading collection stats...</span>
              </div>
            ) : collectionStats?.available ? (
              <div className="collections-grid">
                {Object.entries(collectionStats.collections).map(([type, info]) => (
                  <div key={type} className="collection-card">
                    <div className="collection-header">
                      <Icon
                        name={type === 'documents' ? 'FileText' : type === 'chunks' ? 'Layers' : 'Users'}
                        size={16}
                      />
                      <span>{type}</span>
                    </div>
                    {info.exists === false ? (
                      <div className="collection-empty">Not created</div>
                    ) : info.error ? (
                      <div className="collection-error">{info.error}</div>
                    ) : (
                      <div className="collection-stats">
                        <div className="coll-stat">
                          <span className="coll-stat-value">{info.vector_count?.toLocaleString() || 0}</span>
                          <span className="coll-stat-label">vectors</span>
                        </div>
                        <div className="coll-stat">
                          <span className="coll-stat-value">{info.dimensions || currentDims}</span>
                          <span className="coll-stat-label">dimensions</span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                <div className="collection-total">
                  Total: {getTotalVectors().toLocaleString()} vectors across all collections
                </div>
              </div>
            ) : (
              <div className="collections-unavailable">
                <Icon name="AlertCircle" size={20} />
                <span>Vector service not available</span>
              </div>
            )}
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>

        {showEditMembersModal && (
          <EditProjectMembersModal
            project={project}
            members={projectMembers}
            onClose={() => setShowEditMembersModal(false)}
            onSaved={() => {
              setShowEditMembersModal(false);
              fetchMembers();
              onRefresh();
            }}
          />
        )}
      </div>
    </div>
  );
}

// Edit Project Members Modal - add/remove members (admin only, shown from ProjectDetailsModal)
interface EditProjectMembersModalProps {
  project: Project;
  members: ProjectMember[];
  onClose: () => void;
  onSaved: () => void;
}

function EditProjectMembersModal({ project, members, onClose, onSaved }: EditProjectMembersModalProps) {
  const { toast } = useToast();
  const { user: currentUser } = useAuth();
  const [tenantUsers, setTenantUsers] = useState<Array<{ id: string; email: string; display_name: string | null; role: string }>>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [addUserId, setAddUserId] = useState('');
  const [addRole, setAddRole] = useState('viewer');

  const fetchTenantUsers = useCallback(() => {
    let cancelled = false;
    setLoadingUsers(true);
    apiGet<Array<{ id: string; email: string; display_name: string | null; role: string }>>('/api/auth/tenant/users')
      .then(data => {
        if (!cancelled) {
          const users = Array.isArray(data) ? data : [];
          setTenantUsers(users);
          if (users.length === 0) {
            console.warn('No tenant users found. User may not have admin access or tenant may have no other users.');
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('Failed to fetch tenant users:', err);
          setTenantUsers([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingUsers(false);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    fetchTenantUsers();
  }, [fetchTenantUsers, project.id, members.length]); // Refetch when project changes or members change (modal opens or members updated)

  const memberIds = new Set(members.map(m => m.user_id));
  const availableToAdd = tenantUsers.filter(u => !memberIds.has(u.id));

  const handleAdd = async () => {
    if (!addUserId.trim()) return;
    setAdding(true);
    try {
      await apiPost(`/api/projects/${project.id}/members`, {
        user_id: addUserId.trim(),
        role: addRole,
      });
      toast.success('Member added');
      setAddUserId('');
      // Refetch tenant users to update the dropdown (in case a new user was created elsewhere)
      fetchTenantUsers();
      onSaved();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to add member');
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (userId: string) => {
    if (members.length <= 1) {
      toast.error('Project must have at least one member.');
      return;
    }
    if (currentUser?.id === userId) {
      if (!confirm('You are about to remove yourself from this project. You will lose access. Continue?')) return;
    }
    setRemoving(userId);
    try {
      await apiDelete(`/api/projects/${project.id}/members/${encodeURIComponent(userId)}`);
      toast.success('Member removed');
      onSaved();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to remove member');
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="modal-overlay" style={{ zIndex: 1001 }} onClick={onClose}>
      <div className="modal modal-large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            <Icon name="Users" size={20} style={{ marginRight: '8px' }} />
            Edit Members – {project.name}
          </h2>
          <button type="button" className="icon-btn" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>
        <div className="modal-content">
          <div className="details-section">
            <h3>Current members</h3>
            {members.length === 0 ? (
              <p className="section-empty">No members yet. Add one below.</p>
            ) : (
              <ul className="project-members-list">
                {members.map(m => (
                  <li key={m.id}>
                    <span className="member-user-id">{m.user_id}</span>
                    <span className="member-role">{m.role}</span>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      disabled={members.length <= 1}
                      onClick={() => handleRemove(m.user_id)}
                      title={members.length <= 1 ? 'Project must have at least one member' : 'Remove member'}
                    >
                      {removing === m.user_id ? <Icon name="Loader2" size={14} className="spin" /> : 'Remove'}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="details-section">
            <h3>Add member</h3>
            {loadingUsers ? (
              <div className="loading-stats"><Icon name="Loader2" size={20} className="spin" /> Loading users...</div>
            ) : availableToAdd.length === 0 ? (
              <p className="section-empty">All tenant users are already members.</p>
            ) : (
              <div className="add-member-form">
                <select
                  value={addUserId}
                  onChange={e => setAddUserId(e.target.value)}
                  disabled={adding}
                >
                  <option value="">Select user…</option>
                  {availableToAdd.map(u => (
                    <option key={u.id} value={u.id}>{u.email}{u.display_name ? ` (${u.display_name})` : ''}</option>
                  ))}
                </select>
                <select value={addRole} onChange={e => setAddRole(e.target.value)} disabled={adding}>
                  <option value="viewer">Viewer</option>
                  <option value="editor">Editor</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={!addUserId || adding}
                  onClick={handleAdd}
                >
                  {adding ? <Icon name="Loader2" size={14} className="spin" /> : 'Add'}
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
