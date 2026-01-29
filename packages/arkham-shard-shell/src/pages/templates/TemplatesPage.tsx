/**
 * TemplatesPage - Template management and editing
 *
 * Provides UI for managing document/report templates with versioning,
 * preview, and rendering capabilities.
 */

import { useState } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { usePaginatedFetch } from '../../hooks';
import { apiDelete, apiGet, apiPost, apiPut } from '../../utils/api';
import './TemplatesPage.css';

// Types
interface Template {
  id: string;
  name: string;
  template_type: string;
  description: string;
  content: string;
  placeholders: Placeholder[];
  version: number;
  is_active: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
}

interface Placeholder {
  name: string;
  description: string;
  data_type: string;
  default_value: unknown;
  required: boolean;
  example: string | null;
}

interface TemplateVersion {
  id: string;
  template_id: string;
  version_number: number;
  content: string;
  placeholders: Placeholder[];
  created_at: string;
  created_by: string | null;
  changes: string;
}

interface PreviewResult {
  rendered_content: string;
  placeholders_used: string[];
  warnings: Array<{ placeholder: string; message: string; severity: string }>;
  output_format: string;
  rendered_at: string;
}

const TEMPLATE_TYPES = [
  { value: 'REPORT', label: 'Report', icon: 'FileText' },
  { value: 'LETTER', label: 'Letter', icon: 'Mail' },
  { value: 'EXPORT', label: 'Export', icon: 'Download' },
  { value: 'EMAIL', label: 'Email', icon: 'Send' },
  { value: 'CUSTOM', label: 'Custom', icon: 'FileCode' },
];

export function TemplatesPage() {
  const { toast } = useToast();
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [showEditor, setShowEditor] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<Record<string, unknown>>({});
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null);
  const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [showVersions, setShowVersions] = useState(false);

  // Fetch templates list with pagination
  const { items: templates, loading, error, refetch } = usePaginatedFetch<Template>(
    '/api/templates/',
    {
      params: selectedType ? { template_type: selectedType } : {},
    }
  );

  const handleCreateTemplate = () => {
    setSelectedTemplate(null);
    setShowEditor(true);
  };

  const handleEditTemplate = (template: Template) => {
    setSelectedTemplate(template);
    setShowEditor(true);
    setShowPreview(false);
  };

  const handleSaveTemplate = async (templateData: Partial<Template>) => {
    try {
      const url = selectedTemplate
        ? `/api/templates/${selectedTemplate.id}`
        : '/api/templates/';

      if (selectedTemplate) {
        await apiPut(url, templateData);
      } else {
        await apiPost(url, templateData);
      }

      toast.success(selectedTemplate ? 'Template updated' : 'Template created');
      setShowEditor(false);
      setSelectedTemplate(null);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save template');
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    if (!confirm('Are you sure you want to delete this template?')) return;

    try {
      await apiDelete(`/api/templates/${id}`);

      toast.success('Template deleted');
      if (selectedTemplate?.id === id) {
        setSelectedTemplate(null);
        setShowEditor(false);
      }
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete template');
    }
  };

  const handleToggleActive = async (template: Template) => {
    try {
      const action = template.is_active ? 'deactivate' : 'activate';
      await apiPost(`/api/templates/${template.id}/${action}`);

      toast.success(`Template ${template.is_active ? 'deactivated' : 'activated'}`);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to toggle template status');
    }
  };

  const handlePreview = async (template: Template) => {
    setSelectedTemplate(template);
    setShowPreview(true);

    // Generate preview data from placeholders
    const sampleData: Record<string, unknown> = {};
    template.placeholders.forEach(p => {
      sampleData[p.name] = p.example || p.default_value || `[${p.name}]`;
    });
    setPreviewData(sampleData);

    // Fetch preview
    try {
      const result = await apiPost<PreviewResult>(`/api/templates/${template.id}/preview`, sampleData);
      setPreviewResult(result);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to preview template');
    }
  };

  const handleViewVersions = async (template: Template) => {
    setSelectedTemplate(template);
    setShowVersions(true);

    try {
      const data = await apiGet<TemplateVersion[]>(`/api/templates/${template.id}/versions`);
      setVersions(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load versions');
    }
  };

  const handleRestoreVersion = async (versionId: string) => {
    if (!selectedTemplate) return;
    if (!confirm('Restore this version? This will create a new version with this content.')) return;

    try {
      await apiPost(`/api/templates/${selectedTemplate.id}/restore/${versionId}`);

      toast.success('Version restored');
      setShowVersions(false);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to restore version');
    }
  };

  if (showEditor) {
    return (
      <TemplateEditor
        template={selectedTemplate}
        onSave={handleSaveTemplate}
        onCancel={() => {
          setShowEditor(false);
          setSelectedTemplate(null);
        }}
      />
    );
  }

  if (showPreview && selectedTemplate) {
    return (
      <TemplatePreview
        template={selectedTemplate}
        previewData={previewData}
        previewResult={previewResult}
        onClose={() => {
          setShowPreview(false);
          setPreviewResult(null);
        }}
        onEdit={() => {
          setShowPreview(false);
          handleEditTemplate(selectedTemplate);
        }}
      />
    );
  }

  if (showVersions && selectedTemplate) {
    return (
      <TemplateVersions
        template={selectedTemplate}
        versions={versions}
        onRestore={handleRestoreVersion}
        onClose={() => {
          setShowVersions(false);
          setVersions([]);
        }}
      />
    );
  }

  return (
    <div className="templates-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="FileTemplate" size={28} />
          <div>
            <h1>Templates</h1>
            <p className="page-description">Manage document and report templates</p>
          </div>
        </div>

        <button className="btn btn-primary" onClick={handleCreateTemplate}>
          <Icon name="Plus" size={16} />
          Create Template
        </button>
      </header>

      <div className="templates-layout">
        {/* Type Filter Sidebar */}
        <nav className="templates-nav">
          <button
            className={`nav-item ${selectedType === null ? 'active' : ''}`}
            onClick={() => setSelectedType(null)}
          >
            <Icon name="Layers" size={20} />
            <span>All Templates</span>
          </button>
          {TEMPLATE_TYPES.map(type => (
            <button
              key={type.value}
              className={`nav-item ${selectedType === type.value ? 'active' : ''}`}
              onClick={() => setSelectedType(type.value)}
            >
              <Icon name={type.icon} size={20} />
              <span>{type.label}</span>
            </button>
          ))}
        </nav>

        {/* Templates List */}
        <main className="templates-content">
          {loading ? (
            <div className="templates-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading templates...</span>
            </div>
          ) : error ? (
            <div className="templates-error">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load templates</span>
              <button className="btn btn-secondary" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : templates.length > 0 ? (
            <div className="templates-grid">
              {templates.map(template => (
                <div
                  key={template.id}
                  className={`template-card ${!template.is_active ? 'inactive' : ''}`}
                >
                  <div className="template-header">
                    <div className="template-info">
                      <h3>{template.name}</h3>
                      <div className="template-meta">
                        <span className="template-type">{template.template_type}</span>
                        <span className="template-version">v{template.version}</span>
                        {!template.is_active && (
                          <span className="template-status">Inactive</span>
                        )}
                      </div>
                    </div>
                    <div className="template-actions">
                      <button
                        className="icon-btn"
                        onClick={() => handlePreview(template)}
                        title="Preview"
                      >
                        <Icon name="Eye" size={16} />
                      </button>
                      <button
                        className="icon-btn"
                        onClick={() => handleEditTemplate(template)}
                        title="Edit"
                      >
                        <Icon name="Edit" size={16} />
                      </button>
                      <button
                        className="icon-btn"
                        onClick={() => handleViewVersions(template)}
                        title="Version history"
                      >
                        <Icon name="History" size={16} />
                      </button>
                      <button
                        className="icon-btn"
                        onClick={() => handleDeleteTemplate(template.id)}
                        title="Delete"
                      >
                        <Icon name="Trash2" size={16} />
                      </button>
                    </div>
                  </div>

                  <p className="template-description">{template.description}</p>

                  <div className="template-stats">
                    <div className="stat">
                      <Icon name="Code" size={14} />
                      <span>{template.placeholders.length} placeholders</span>
                    </div>
                    <div className="stat">
                      <Icon name="Calendar" size={14} />
                      <span>
                        {new Date(template.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <div className="template-footer">
                    <button
                      className={`toggle-btn ${template.is_active ? 'active' : ''}`}
                      onClick={() => handleToggleActive(template)}
                    >
                      {template.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="templates-empty">
              <Icon name="FileTemplate" size={48} />
              <span>
                {selectedType
                  ? `No ${selectedType.toLowerCase()} templates found`
                  : 'No templates yet'}
              </span>
              <button className="btn btn-primary" onClick={handleCreateTemplate}>
                Create Your First Template
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// Template Editor Component
interface TemplateEditorProps {
  template: Template | null;
  onSave: (data: Partial<Template>) => void;
  onCancel: () => void;
}

function TemplateEditor({ template, onSave, onCancel }: TemplateEditorProps) {
  const [name, setName] = useState(template?.name || '');
  const [type, setType] = useState(template?.template_type || 'REPORT');
  const [description, setDescription] = useState(template?.description || '');
  const [content, setContent] = useState(template?.content || '');
  const [isActive, setIsActive] = useState(template?.is_active ?? true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      name,
      template_type: type,
      description,
      content,
      is_active: isActive,
    });
  };

  return (
    <div className="template-editor">
      <header className="page-header">
        <div className="page-title">
          <Icon name="FileEdit" size={28} />
          <h1>{template ? 'Edit Template' : 'Create Template'}</h1>
        </div>
        <div className="editor-actions">
          <button className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            <Icon name="Save" size={16} />
            Save Template
          </button>
        </div>
      </header>

      <form className="editor-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="name">Template Name</label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Enter template name"
            required
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="type">Type</label>
            <select id="type" value={type} onChange={e => setType(e.target.value)}>
              {TEMPLATE_TYPES.map(t => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={isActive}
                onChange={e => setIsActive(e.target.checked)}
              />
              <span>Active</span>
            </label>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Brief description of the template"
            rows={2}
          />
        </div>

        <div className="form-group">
          <label htmlFor="content">
            Template Content
            <span className="label-hint">
              Use {"{{ placeholder_name }}"} for variables
            </span>
          </label>
          <textarea
            id="content"
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Enter template content using Jinja2 syntax"
            rows={15}
            className="code-editor"
            required
          />
        </div>
      </form>
    </div>
  );
}

// Template Preview Component
interface TemplatePreviewProps {
  template: Template;
  previewData: Record<string, unknown>;
  previewResult: PreviewResult | null;
  onClose: () => void;
  onEdit: () => void;
}

function TemplatePreview({
  template,
  previewData,
  previewResult,
  onClose,
  onEdit,
}: TemplatePreviewProps) {
  return (
    <div className="template-preview">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Eye" size={28} />
          <div>
            <h1>{template.name}</h1>
            <p className="page-description">Template Preview</p>
          </div>
        </div>
        <div className="preview-actions">
          <button className="btn btn-secondary" onClick={onEdit}>
            <Icon name="Edit" size={16} />
            Edit
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </header>

      <div className="preview-content">
        <div className="preview-section">
          <h3>Sample Data</h3>
          <div className="placeholders-list">
            {template.placeholders.map(p => (
              <div key={p.name} className="placeholder-item">
                <strong>{p.name}</strong>
                {p.required && <span className="required">*</span>}
                <span className="value">{String(previewData[p.name])}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="preview-section">
          <h3>Rendered Output</h3>
          {previewResult ? (
            <div className="preview-output">
              {previewResult.warnings.length > 0 && (
                <div className="preview-warnings">
                  {previewResult.warnings.map((w, i) => (
                    <div key={i} className={`warning ${w.severity}`}>
                      <Icon name="AlertTriangle" size={14} />
                      <span>{w.message}</span>
                    </div>
                  ))}
                </div>
              )}
              <pre className="rendered-content">{previewResult.rendered_content}</pre>
            </div>
          ) : (
            <div className="preview-loading">
              <Icon name="Loader2" size={24} className="spin" />
              <span>Generating preview...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Template Versions Component
interface TemplateVersionsProps {
  template: Template;
  versions: TemplateVersion[];
  onRestore: (versionId: string) => void;
  onClose: () => void;
}

function TemplateVersions({
  template,
  versions,
  onRestore,
  onClose,
}: TemplateVersionsProps) {
  return (
    <div className="template-versions">
      <header className="page-header">
        <div className="page-title">
          <Icon name="History" size={28} />
          <div>
            <h1>{template.name}</h1>
            <p className="page-description">Version History</p>
          </div>
        </div>
        <button className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      </header>

      <div className="versions-list">
        {versions.map(version => (
          <div key={version.id} className="version-item">
            <div className="version-header">
              <div className="version-info">
                <h3>Version {version.version_number}</h3>
                <span className="version-date">
                  {new Date(version.created_at).toLocaleString()}
                </span>
                {version.created_by && (
                  <span className="version-author">by {version.created_by}</span>
                )}
              </div>
              {version.version_number < template.version && (
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => onRestore(version.id)}
                >
                  <Icon name="RotateCcw" size={14} />
                  Restore
                </button>
              )}
            </div>
            {version.changes && <p className="version-changes">{version.changes}</p>}
            <details className="version-content">
              <summary>View Content</summary>
              <pre>{version.content}</pre>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}
