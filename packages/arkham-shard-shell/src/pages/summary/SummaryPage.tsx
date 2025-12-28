/**
 * SummaryPage - AI-powered summary management
 *
 * Provides UI for generating and managing document summaries.
 */

import { useState } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import './SummaryPage.css';

// Types
interface Summary {
  id: string;
  summary_type: string;
  status: string;
  source_type: string;
  source_ids: string[];
  content: string;
  key_points: string[];
  title: string | null;
  model_used: string | null;
  token_count: number;
  word_count: number;
  target_length: string;
  confidence: number;
  processing_time_ms: number;
  created_at: string;
  tags: string[];
}

interface SummaryType {
  value: string;
  label: string;
  description: string;
}

interface Capabilities {
  llm_available: boolean;
  workers_available: boolean;
  summary_types: string[];
  source_types: string[];
  target_lengths: string[];
}

const SOURCE_TYPE_LABELS: Record<string, string> = {
  document: 'Document',
  documents: 'Documents',
  entity: 'Entity',
  project: 'Project',
  claim_set: 'Claim Set',
  timeline: 'Timeline',
  analysis: 'Analysis',
};

const LENGTH_LABELS: Record<string, string> = {
  very_short: 'Very Short (~50 words)',
  short: 'Short (~100 words)',
  medium: 'Medium (~250 words)',
  long: 'Long (~500 words)',
  very_long: 'Very Long (~1000 words)',
};

export function SummaryPage() {
  const { toast } = useToast();
  const [view, setView] = useState<'list' | 'generate'>('list');
  const [selectedSummary, setSelectedSummary] = useState<Summary | null>(null);

  // Fetch summaries with pagination
  const {
    items: summaries,
    loading,
    error,
    refetch,
  } = usePaginatedFetch<Summary>('/api/summary/');

  // Fetch capabilities
  const { data: capabilities } = useFetch<Capabilities>('/api/summary/capabilities');

  // Fetch summary types
  const { data: summaryTypesData } = useFetch<{ types: SummaryType[] }>('/api/summary/types');

  // Generate form state
  const [generating, setGenerating] = useState(false);
  const [formData, setFormData] = useState({
    source_type: 'document',
    source_ids: '',
    summary_type: 'detailed',
    target_length: 'medium',
    focus_areas: '',
    exclude_topics: '',
    include_key_points: true,
    include_title: true,
    tags: '',
  });

  const handleGenerateSummary = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);

    try {
      // Parse source IDs (comma-separated)
      const sourceIds = formData.source_ids
        .split(',')
        .map(id => id.trim())
        .filter(id => id.length > 0);

      if (sourceIds.length === 0) {
        toast.error('Please provide at least one source ID');
        return;
      }

      const requestBody = {
        source_type: formData.source_type,
        source_ids: sourceIds,
        summary_type: formData.summary_type,
        target_length: formData.target_length,
        focus_areas: formData.focus_areas
          .split(',')
          .map(s => s.trim())
          .filter(s => s.length > 0),
        exclude_topics: formData.exclude_topics
          .split(',')
          .map(s => s.trim())
          .filter(s => s.length > 0),
        include_key_points: formData.include_key_points,
        include_title: formData.include_title,
        tags: formData.tags
          .split(',')
          .map(s => s.trim())
          .filter(s => s.length > 0),
      };

      const response = await fetch('/api/summary/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to generate summary');
      }

      const result = await response.json();

      if (result.status === 'completed') {
        toast.success('Summary generated successfully');
        setView('list');
        refetch();
        // Reset form
        setFormData({
          source_type: 'document',
          source_ids: '',
          summary_type: 'detailed',
          target_length: 'medium',
          focus_areas: '',
          exclude_topics: '',
          include_key_points: true,
          include_title: true,
          tags: '',
        });
      } else {
        toast.error(result.error_message || 'Summary generation failed');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to generate summary');
    } finally {
      setGenerating(false);
    }
  };

  const handleDeleteSummary = async (summaryId: string) => {
    if (!confirm('Are you sure you want to delete this summary?')) {
      return;
    }

    try {
      const response = await fetch(`/api/summary/${summaryId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete summary');
      }

      toast.success('Summary deleted');
      setSelectedSummary(null);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete summary');
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  return (
    <div className="summary-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="FileText" size={28} />
          <div>
            <h1>Summaries</h1>
            <p className="page-description">AI-powered document and content summarization</p>
          </div>
        </div>

        <div className="page-actions">
          {capabilities && !capabilities.llm_available && (
            <div className="llm-warning">
              <Icon name="AlertTriangle" size={16} />
              <span>LLM unavailable - using extractive summarization</span>
            </div>
          )}
          <button
            className="btn btn-primary"
            onClick={() => setView(view === 'list' ? 'generate' : 'list')}
          >
            <Icon name={view === 'list' ? 'Sparkles' : 'List'} size={16} />
            {view === 'list' ? 'Generate Summary' : 'View Summaries'}
          </button>
        </div>
      </header>

      {view === 'list' ? (
        <div className="summary-layout">
          {/* Summary List */}
          <aside className="summary-list">
            {loading ? (
              <div className="summary-loading">
                <Icon name="Loader2" size={24} className="spin" />
                <span>Loading summaries...</span>
              </div>
            ) : error ? (
              <div className="summary-error">
                <Icon name="AlertCircle" size={24} />
                <span>Failed to load summaries</span>
                <button className="btn btn-secondary" onClick={() => refetch()}>
                  Retry
                </button>
              </div>
            ) : summaries && summaries.length > 0 ? (
              <div className="summary-items">
                {summaries.map(summary => (
                  <button
                    key={summary.id}
                    className={`summary-item ${selectedSummary?.id === summary.id ? 'active' : ''}`}
                    onClick={() => setSelectedSummary(summary)}
                  >
                    <div className="summary-item-header">
                      <span className="summary-title">
                        {summary.title || `${summary.summary_type} summary`}
                      </span>
                      <span className={`status-badge status-${summary.status}`}>
                        {summary.status}
                      </span>
                    </div>
                    <div className="summary-item-meta">
                      <span className="meta-item">
                        <Icon name="FileText" size={12} />
                        {SOURCE_TYPE_LABELS[summary.source_type] || summary.source_type}
                      </span>
                      <span className="meta-item">
                        <Icon name="Calendar" size={12} />
                        {new Date(summary.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="summary-item-stats">
                      <span>{summary.word_count} words</span>
                      <span>{Math.round(summary.confidence * 100)}% confidence</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="summary-empty">
                <Icon name="FileText" size={48} />
                <span>No summaries yet</span>
                <button className="btn btn-primary" onClick={() => setView('generate')}>
                  Generate Your First Summary
                </button>
              </div>
            )}
          </aside>

          {/* Summary Detail */}
          <main className="summary-detail">
            {selectedSummary ? (
              <div className="summary-content">
                <div className="summary-detail-header">
                  <div>
                    <h2>{selectedSummary.title || 'Summary'}</h2>
                    <div className="summary-meta">
                      <span className="meta-badge">
                        <Icon name="Type" size={14} />
                        {selectedSummary.summary_type}
                      </span>
                      <span className="meta-badge">
                        <Icon name="FileText" size={14} />
                        {SOURCE_TYPE_LABELS[selectedSummary.source_type] || selectedSummary.source_type}
                      </span>
                      <span className="meta-badge">
                        <Icon name="Calendar" size={14} />
                        {formatDate(selectedSummary.created_at)}
                      </span>
                    </div>
                  </div>
                  <button
                    className="btn btn-danger"
                    onClick={() => handleDeleteSummary(selectedSummary.id)}
                  >
                    <Icon name="Trash2" size={16} />
                    Delete
                  </button>
                </div>

                <div className="summary-body">
                  <section className="summary-section">
                    <h3>Summary</h3>
                    <div className="summary-text">{selectedSummary.content}</div>
                  </section>

                  {selectedSummary.key_points.length > 0 && (
                    <section className="summary-section">
                      <h3>Key Points</h3>
                      <ul className="key-points-list">
                        {selectedSummary.key_points.map((point, idx) => (
                          <li key={idx}>{point}</li>
                        ))}
                      </ul>
                    </section>
                  )}

                  <section className="summary-section">
                    <h3>Metadata</h3>
                    <div className="metadata-grid">
                      <div className="metadata-item">
                        <span className="metadata-label">Word Count</span>
                        <span className="metadata-value">{selectedSummary.word_count}</span>
                      </div>
                      <div className="metadata-item">
                        <span className="metadata-label">Token Count</span>
                        <span className="metadata-value">{selectedSummary.token_count}</span>
                      </div>
                      <div className="metadata-item">
                        <span className="metadata-label">Confidence</span>
                        <span className="metadata-value">
                          {Math.round(selectedSummary.confidence * 100)}%
                        </span>
                      </div>
                      <div className="metadata-item">
                        <span className="metadata-label">Processing Time</span>
                        <span className="metadata-value">
                          {Math.round(selectedSummary.processing_time_ms)}ms
                        </span>
                      </div>
                      {selectedSummary.model_used && (
                        <div className="metadata-item">
                          <span className="metadata-label">Model</span>
                          <span className="metadata-value">{selectedSummary.model_used}</span>
                        </div>
                      )}
                      <div className="metadata-item">
                        <span className="metadata-label">Target Length</span>
                        <span className="metadata-value">
                          {LENGTH_LABELS[selectedSummary.target_length] || selectedSummary.target_length}
                        </span>
                      </div>
                    </div>
                  </section>

                  {selectedSummary.tags.length > 0 && (
                    <section className="summary-section">
                      <h3>Tags</h3>
                      <div className="tags-list">
                        {selectedSummary.tags.map((tag, idx) => (
                          <span key={idx} className="tag">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </section>
                  )}
                </div>
              </div>
            ) : (
              <div className="summary-detail-empty">
                <Icon name="FileText" size={64} />
                <span>Select a summary to view details</span>
              </div>
            )}
          </main>
        </div>
      ) : (
        <div className="summary-generate">
          <form onSubmit={handleGenerateSummary} className="generate-form">
            <h2>Generate New Summary</h2>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="source_type">Source Type</label>
                <select
                  id="source_type"
                  value={formData.source_type}
                  onChange={e => setFormData({ ...formData, source_type: e.target.value })}
                  required
                >
                  {capabilities?.source_types.map(type => (
                    <option key={type} value={type}>
                      {SOURCE_TYPE_LABELS[type] || type}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="summary_type">Summary Type</label>
                <select
                  id="summary_type"
                  value={formData.summary_type}
                  onChange={e => setFormData({ ...formData, summary_type: e.target.value })}
                  required
                >
                  {summaryTypesData?.types.map(type => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="source_ids">
                Source IDs
                <span className="label-hint">(comma-separated)</span>
              </label>
              <input
                type="text"
                id="source_ids"
                value={formData.source_ids}
                onChange={e => setFormData({ ...formData, source_ids: e.target.value })}
                placeholder="e.g., doc_123, doc_456"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="target_length">Target Length</label>
              <select
                id="target_length"
                value={formData.target_length}
                onChange={e => setFormData({ ...formData, target_length: e.target.value })}
              >
                {capabilities?.target_lengths.map(length => (
                  <option key={length} value={length}>
                    {LENGTH_LABELS[length] || length}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="focus_areas">
                Focus Areas
                <span className="label-hint">(optional, comma-separated)</span>
              </label>
              <input
                type="text"
                id="focus_areas"
                value={formData.focus_areas}
                onChange={e => setFormData({ ...formData, focus_areas: e.target.value })}
                placeholder="e.g., methodology, results, conclusions"
              />
            </div>

            <div className="form-group">
              <label htmlFor="exclude_topics">
                Exclude Topics
                <span className="label-hint">(optional, comma-separated)</span>
              </label>
              <input
                type="text"
                id="exclude_topics"
                value={formData.exclude_topics}
                onChange={e => setFormData({ ...formData, exclude_topics: e.target.value })}
                placeholder="e.g., technical details, references"
              />
            </div>

            <div className="form-group">
              <label htmlFor="tags">
                Tags
                <span className="label-hint">(optional, comma-separated)</span>
              </label>
              <input
                type="text"
                id="tags"
                value={formData.tags}
                onChange={e => setFormData({ ...formData, tags: e.target.value })}
                placeholder="e.g., research, analysis, important"
              />
            </div>

            <div className="form-options">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={formData.include_key_points}
                  onChange={e =>
                    setFormData({ ...formData, include_key_points: e.target.checked })
                  }
                />
                <span>Include key points</span>
              </label>

              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={formData.include_title}
                  onChange={e => setFormData({ ...formData, include_title: e.target.checked })}
                />
                <span>Generate title</span>
              </label>
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setView('list')}
                disabled={generating}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={generating}>
                {generating ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Icon name="Sparkles" size={16} />
                    Generate Summary
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
