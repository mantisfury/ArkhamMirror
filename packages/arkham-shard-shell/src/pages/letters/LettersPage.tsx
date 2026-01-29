/**
 * LettersPage - Letter generation and management
 *
 * Provides UI for creating and managing formal letters from templates
 * including FOIA requests, complaints, legal correspondence, etc.
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import { apiDelete, apiPost, apiPut } from '../../utils/api';
import './LettersPage.css';

// Types
interface Letter {
  id: string;
  title: string;
  letter_type: string;
  status: string;
  content: string;
  template_id: string | null;
  recipient_name: string | null;
  recipient_address: string | null;
  subject: string | null;
  created_at: string;
  updated_at: string;
  finalized_at: string | null;
  sent_at: string | null;
}

interface Template {
  id: string;
  name: string;
  letter_type: string;
  description: string;
  content_template: string;
  subject_template: string | null;
  placeholders: string[];
  required_placeholders: string[];
}

interface SharedTemplate {
  id: string;
  name: string;
  description: string;
  template_type: string;
  content: string;
  placeholders: Array<{
    name: string;
    description: string;
    data_type: string;
    default_value: string | null;
    required: boolean;
  }>;
  created_at: string;
  updated_at: string;
}

interface SharedTemplatesResponse {
  templates: SharedTemplate[];
  count: number;
  source: string;
}

interface Statistics {
  total_letters: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  total_templates: number;
}

type ViewMode = 'list' | 'create' | 'edit' | 'template';

const LETTER_TYPES = [
  { value: 'foia', label: 'FOIA Request', icon: 'FileSearch' },
  { value: 'complaint', label: 'Complaint', icon: 'AlertCircle' },
  { value: 'demand', label: 'Demand Letter', icon: 'Gavel' },
  { value: 'notice', label: 'Notice', icon: 'Bell' },
  { value: 'inquiry', label: 'Inquiry', icon: 'HelpCircle' },
  { value: 'response', label: 'Response', icon: 'Reply' },
  { value: 'cover', label: 'Cover Letter', icon: 'FileText' },
  { value: 'custom', label: 'Custom', icon: 'Edit' },
];

const STATUS_COLORS: Record<string, string> = {
  draft: '#6b7280',
  review: '#f59e0b',
  finalized: '#10b981',
  sent: '#3b82f6',
};

export function LettersPage() {
  const { toast } = useToast();
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [selectedLetter, setSelectedLetter] = useState<Letter | null>(null);
  const [_selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch letters with pagination
  const {
    items: letters,
    loading: loadingLetters,
    error: lettersError,
    refetch: refetchLetters,
  } = usePaginatedFetch<Letter>('/api/letters/', {
    params: {
      status: filterStatus || undefined,
      search: searchQuery || undefined,
    },
  });

  const { data: templates, loading: loadingTemplates } = useFetch<Template[]>(
    '/api/letters/templates'
  );

  // Fetch shared templates from Templates shard
  const { data: sharedTemplatesData, loading: loadingShared } = useFetch<SharedTemplatesResponse>(
    '/api/letters/templates/shared'
  );

  const { data: stats } = useFetch<Statistics>('/api/letters/stats');

  const handleCreateFromTemplate = useCallback((template: Template) => {
    setSelectedTemplate(template);
    setViewMode('template');
  }, []);

  const handleCreateLetter = async (data: {
    title: string;
    letter_type: string;
    content: string;
    recipient_name?: string;
    recipient_address?: string;
    subject?: string;
  }) => {
    try {
      const letter = await apiPost<Letter>('/api/letters/', data);
      toast.success('Letter created successfully');
      setViewMode('list');
      refetchLetters();
      return letter;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create letter');
      throw err;
    }
  };

  const handleUpdateLetter = async (letterId: string, updates: Partial<Letter>) => {
    try {
      await apiPut(`/api/letters/${letterId}`, updates);

      toast.success('Letter updated successfully');
      refetchLetters();
      setViewMode('list');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update letter');
    }
  };

  const handleDeleteLetter = async (letterId: string) => {
    if (!confirm('Are you sure you want to delete this letter?')) {
      return;
    }

    try {
      await apiDelete(`/api/letters/${letterId}`);

      toast.success('Letter deleted');
      refetchLetters();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete letter');
    }
  };

  const handleExportLetter = async (letterId: string, format: string) => {
    try {
      const result = await apiPost<any>(`/api/letters/${letterId}/export`, { export_format: format });
      toast.success(`Letter exported to ${format.toUpperCase()}`);
      refetchLetters();
      return result;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export letter');
    }
  };

  const getTypeIcon = (type: string) => {
    const typeInfo = LETTER_TYPES.find(t => t.value === type);
    return typeInfo?.icon || 'FileText';
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="letters-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="FileSignature" size={28} />
          <div>
            <h1>Letters</h1>
            <p className="page-description">Generate formal letters from templates</p>
          </div>
        </div>

        {viewMode === 'list' && (
          <div className="header-actions">
            <button
              className="btn btn-secondary"
              onClick={() => setViewMode('template')}
            >
              <Icon name="FileText" size={16} />
              Use Template
            </button>
            <button
              className="btn btn-primary"
              onClick={() => setViewMode('create')}
            >
              <Icon name="Plus" size={16} />
              New Letter
            </button>
          </div>
        )}

        {viewMode !== 'list' && (
          <button
            className="btn btn-secondary"
            onClick={() => {
              setViewMode('list');
              setSelectedLetter(null);
              setSelectedTemplate(null);
            }}
          >
            <Icon name="ArrowLeft" size={16} />
            Back to List
          </button>
        )}
      </header>

      {/* Statistics */}
      {viewMode === 'list' && stats && (
        <div className="letters-stats">
          <div className="stat-card">
            <Icon name="FileText" size={20} />
            <div>
              <div className="stat-value">{stats.total_letters}</div>
              <div className="stat-label">Total Letters</div>
            </div>
          </div>
          <div className="stat-card">
            <Icon name="FileEdit" size={20} />
            <div>
              <div className="stat-value">{stats.by_status?.draft || 0}</div>
              <div className="stat-label">Drafts</div>
            </div>
          </div>
          <div className="stat-card">
            <Icon name="FileCheck" size={20} />
            <div>
              <div className="stat-value">{stats.by_status?.finalized || 0}</div>
              <div className="stat-label">Finalized</div>
            </div>
          </div>
          <div className="stat-card">
            <Icon name="Send" size={20} />
            <div>
              <div className="stat-value">{stats.by_status?.sent || 0}</div>
              <div className="stat-label">Sent</div>
            </div>
          </div>
        </div>
      )}

      <main className="letters-content">
        {viewMode === 'list' && (
          <>
            {/* Filters */}
            <div className="letters-filters">
              <div className="filter-group">
                <label>Status</label>
                <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                  <option value="">All</option>
                  <option value="draft">Draft</option>
                  <option value="review">Review</option>
                  <option value="finalized">Finalized</option>
                  <option value="sent">Sent</option>
                </select>
              </div>
              <div className="filter-group search-group">
                <Icon name="Search" size={16} />
                <input
                  type="text"
                  placeholder="Search letters..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            {/* Letters List */}
            {loadingLetters ? (
              <div className="letters-loading">
                <Icon name="Loader2" size={32} className="spin" />
                <span>Loading letters...</span>
              </div>
            ) : lettersError ? (
              <div className="letters-error">
                <Icon name="AlertCircle" size={32} />
                <span>Failed to load letters</span>
                <button className="btn btn-secondary" onClick={() => refetchLetters()}>
                  Retry
                </button>
              </div>
            ) : letters && letters.length > 0 ? (
              <div className="letters-list">
                {letters.map(letter => (
                  <div key={letter.id} className="letter-card">
                    <div className="letter-header">
                      <div className="letter-title">
                        <Icon name={getTypeIcon(letter.letter_type)} size={20} />
                        <h3>{letter.title}</h3>
                      </div>
                      <span
                        className="status-badge"
                        style={{ backgroundColor: STATUS_COLORS[letter.status] }}
                      >
                        {letter.status}
                      </span>
                    </div>

                    <div className="letter-meta">
                      {letter.recipient_name && (
                        <div className="meta-item">
                          <Icon name="User" size={14} />
                          <span>{letter.recipient_name}</span>
                        </div>
                      )}
                      {letter.subject && (
                        <div className="meta-item">
                          <Icon name="Tag" size={14} />
                          <span>{letter.subject}</span>
                        </div>
                      )}
                      <div className="meta-item">
                        <Icon name="Calendar" size={14} />
                        <span>Updated {formatDate(letter.updated_at)}</span>
                      </div>
                    </div>

                    <div className="letter-actions">
                      <button
                        className="btn-icon"
                        onClick={() => {
                          setSelectedLetter(letter);
                          setViewMode('edit');
                        }}
                        title="Edit"
                      >
                        <Icon name="Edit" size={16} />
                      </button>
                      <button
                        className="btn-icon"
                        onClick={() => handleExportLetter(letter.id, 'pdf')}
                        title="Export to PDF"
                      >
                        <Icon name="Download" size={16} />
                      </button>
                      <button
                        className="btn-icon danger"
                        onClick={() => handleDeleteLetter(letter.id)}
                        title="Delete"
                      >
                        <Icon name="Trash2" size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="letters-empty">
                <Icon name="FileSignature" size={48} />
                <h3>No letters yet</h3>
                <p>Create your first letter using a template or from scratch</p>
                <div className="empty-actions">
                  <button className="btn btn-primary" onClick={() => setViewMode('template')}>
                    <Icon name="FileText" size={16} />
                    Browse Templates
                  </button>
                  <button className="btn btn-secondary" onClick={() => setViewMode('create')}>
                    <Icon name="Plus" size={16} />
                    Create From Scratch
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {viewMode === 'template' && (
          <TemplateSelector
            templates={templates || []}
            sharedTemplates={sharedTemplatesData?.templates || []}
            loading={loadingTemplates || loadingShared}
            onSelect={handleCreateFromTemplate}
            onSelectShared={(_template) => {
              // When selecting a shared template, use its content directly
              setViewMode('create');
            }}
          />
        )}

        {viewMode === 'create' && (
          <LetterEditor
            onCreate={handleCreateLetter}
            onCancel={() => setViewMode('list')}
          />
        )}

        {viewMode === 'edit' && selectedLetter && (
          <LetterEditor
            letter={selectedLetter}
            onUpdate={(updates) => handleUpdateLetter(selectedLetter.id, updates)}
            onCancel={() => {
              setViewMode('list');
              setSelectedLetter(null);
            }}
          />
        )}
      </main>
    </div>
  );
}

// Template Selector Component
interface TemplateSelectorProps {
  templates: Template[];
  sharedTemplates: SharedTemplate[];
  loading: boolean;
  onSelect: (template: Template) => void;
  onSelectShared: (template: SharedTemplate) => void;
}

function TemplateSelector({ templates, sharedTemplates, loading, onSelect, onSelectShared }: TemplateSelectorProps) {
  const { toast } = useToast();
  const [filterType, setFilterType] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'local' | 'shared'>('shared');

  const filteredTemplates = templates.filter(t =>
    !filterType || t.letter_type === filterType
  );

  const handleUseSharedTemplate = async (template: SharedTemplate) => {
    try {
      await apiPost('/api/letters/from-shared-template', {
        template_id: template.id,
        title: `Letter from ${template.name}`,
        placeholder_values: {},
      });

      toast.success('Letter created from template');
      onSelectShared(template);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to use template');
    }
  };

  if (loading) {
    return (
      <div className="templates-loading">
        <Icon name="Loader2" size={32} className="spin" />
        <span>Loading templates...</span>
      </div>
    );
  }

  return (
    <div className="template-selector">
      <div className="template-header">
        <h2>Choose a Template</h2>
        <div className="template-tabs">
          <button
            className={`tab-btn ${activeTab === 'shared' ? 'active' : ''}`}
            onClick={() => setActiveTab('shared')}
          >
            <Icon name="Library" size={16} />
            Shared Templates ({sharedTemplates.length})
          </button>
          <button
            className={`tab-btn ${activeTab === 'local' ? 'active' : ''}`}
            onClick={() => setActiveTab('local')}
          >
            <Icon name="FileText" size={16} />
            Local Templates ({templates.length})
          </button>
        </div>
      </div>

      {activeTab === 'shared' && (
        <>
          {sharedTemplates.length > 0 ? (
            <div className="templates-grid">
              {sharedTemplates.map(template => (
                <div key={template.id} className="template-card shared" onClick={() => handleUseSharedTemplate(template)}>
                  <div className="template-icon">
                    <Icon name="Library" size={24} />
                  </div>
                  <h3>{template.name}</h3>
                  <p>{template.description}</p>
                  <div className="template-meta">
                    <span className="type-badge shared">Shared</span>
                    <span className="placeholders-count">
                      {template.placeholders.length} placeholders
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="templates-empty">
              <Icon name="Library" size={48} />
              <p>No shared letter templates available</p>
              <span className="empty-hint">Create LETTER type templates in the Templates shard</span>
            </div>
          )}
        </>
      )}

      {activeTab === 'local' && (
        <>
          <div className="filter-row">
            <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
              <option value="">All Types</option>
              {LETTER_TYPES.map(type => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {filteredTemplates.length > 0 ? (
            <div className="templates-grid">
              {filteredTemplates.map(template => (
                <div key={template.id} className="template-card" onClick={() => onSelect(template)}>
                  <div className="template-icon">
                    <Icon name={LETTER_TYPES.find(t => t.value === template.letter_type)?.icon || 'FileText'} size={24} />
                  </div>
                  <h3>{template.name}</h3>
                  <p>{template.description}</p>
                  <div className="template-meta">
                    <span className="type-badge">{template.letter_type}</span>
                    <span className="placeholders-count">
                      {template.placeholders.length} placeholders
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="templates-empty">
              <Icon name="FileText" size={48} />
              <p>No local templates available</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Letter Editor Component
interface LetterEditorProps {
  letter?: Letter;
  onCreate?: (data: any) => Promise<void>;
  onUpdate?: (updates: Partial<Letter>) => Promise<void>;
  onCancel: () => void;
}

function LetterEditor({ letter, onCreate, onUpdate, onCancel }: LetterEditorProps) {
  const [title, setTitle] = useState(letter?.title || '');
  const [letterType, setLetterType] = useState(letter?.letter_type || 'custom');
  const [content, setContent] = useState(letter?.content || '');
  const [recipientName, setRecipientName] = useState(letter?.recipient_name || '');
  const [recipientAddress, setRecipientAddress] = useState(letter?.recipient_address || '');
  const [subject, setSubject] = useState(letter?.subject || '');
  const [status, setStatus] = useState(letter?.status || 'draft');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!title.trim()) {
      alert('Please enter a title');
      return;
    }

    setSaving(true);
    try {
      if (onCreate) {
        await onCreate({
          title,
          letter_type: letterType,
          content,
          recipient_name: recipientName || undefined,
          recipient_address: recipientAddress || undefined,
          subject: subject || undefined,
        });
      } else if (onUpdate) {
        await onUpdate({
          title,
          content,
          recipient_name: recipientName || null,
          recipient_address: recipientAddress || null,
          subject: subject || null,
          status,
        });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="letter-editor">
      <div className="editor-form">
        <div className="form-row">
          <div className="form-group">
            <label>Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Letter title"
            />
          </div>
          {!letter && (
            <div className="form-group">
              <label>Type</label>
              <select value={letterType} onChange={(e) => setLetterType(e.target.value)}>
                {LETTER_TYPES.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          {letter && (
            <div className="form-group">
              <label>Status</label>
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="draft">Draft</option>
                <option value="review">Review</option>
                <option value="finalized">Finalized</option>
                <option value="sent">Sent</option>
              </select>
            </div>
          )}
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Recipient Name</label>
            <input
              type="text"
              value={recipientName}
              onChange={(e) => setRecipientName(e.target.value)}
              placeholder="Recipient name"
            />
          </div>
          <div className="form-group">
            <label>Subject</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Letter subject"
            />
          </div>
        </div>

        <div className="form-group">
          <label>Recipient Address</label>
          <textarea
            value={recipientAddress}
            onChange={(e) => setRecipientAddress(e.target.value)}
            placeholder="Recipient address"
            rows={3}
          />
        </div>

        <div className="form-group">
          <label>Content</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Letter content"
            rows={12}
            className="letter-content"
          />
        </div>

        <div className="editor-actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={saving}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Saving...
              </>
            ) : (
              <>
                <Icon name="Save" size={16} />
                {letter ? 'Update Letter' : 'Create Letter'}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
