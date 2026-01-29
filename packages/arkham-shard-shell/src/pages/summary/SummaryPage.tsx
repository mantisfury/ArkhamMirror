/**
 * SummaryPage - AI-powered summary management
 *
 * Provides UI for generating and managing document summaries with:
 * - Source picker/browser for documents, entities, projects, claims
 * - Statistics dashboard
 * - Filtering by type, source type, status
 * - Regenerate functionality
 */

import { useState, useEffect, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { apiDelete, apiGet, apiPost } from '../../utils/api';
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

interface Statistics {
  total_summaries: number;
  by_type: Record<string, number>;
  by_source_type: Record<string, number>;
  by_status: Record<string, number>;
  by_model: Record<string, number>;
  avg_confidence: number;
  avg_completeness: number;
  avg_word_count: number;
  avg_processing_time_ms: number;
  generated_last_24h: number;
  failed_last_24h: number;
  total_words_generated: number;
  total_tokens_used: number;
}

interface SourceItem {
  id: string;
  name: string;
  type: string;
  preview: string;
  created_at: string | null;
  metadata: Record<string, unknown>;
}

interface SourceListResponse {
  items: SourceItem[];
  total: number;
  page: number;
  page_size: number;
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

const SOURCE_ICONS: Record<string, string> = {
  document: 'File',
  documents: 'Files',
  entity: 'User',
  project: 'FolderOpen',
  claim_set: 'MessageSquare',
  timeline: 'Clock',
  analysis: 'BarChart3',
};

type ViewMode = 'list' | 'generate' | 'stats';

export function SummaryPage() {
  const { toast } = useToast();
  const [view, setView] = useState<ViewMode>('list');
  const [selectedSummary, setSelectedSummary] = useState<Summary | null>(null);

  // Filter state
  const [filterType, setFilterType] = useState<string>('');
  const [filterSourceType, setFilterSourceType] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Summaries state
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalSummaries, setTotalSummaries] = useState(0);

  // Fetch capabilities
  const { data: capabilities } = useFetch<Capabilities>('/api/summary/capabilities');

  // Fetch summary types
  const { data: summaryTypesData } = useFetch<{ types: SummaryType[] }>('/api/summary/types');

  // Fetch statistics
  const { data: stats, refetch: refetchStats } = useFetch<Statistics>('/api/summary/stats');

  // Load summaries with filters
  const loadSummaries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('page', page.toString());
      params.set('page_size', '20');
      if (filterType) params.set('summary_type', filterType);
      if (filterSourceType) params.set('source_type', filterSourceType);
      if (filterStatus) params.set('status', filterStatus);
      if (searchQuery) params.set('q', searchQuery);

      const data = await apiGet<{ items?: Summary[]; total?: number }>('/api/summary/?' + params.toString());
      setSummaries(Array.isArray(data.items) ? data.items : []);
      setTotalSummaries(typeof data.total === 'number' ? data.total : 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load summaries');
    } finally {
      setLoading(false);
    }
  }, [page, filterType, filterSourceType, filterStatus, searchQuery]);

  useEffect(() => {
    loadSummaries();
  }, [loadSummaries]);

  // Generate form state
  const [generating, setGenerating] = useState(false);
  const [sourcePickerOpen, setSourcePickerOpen] = useState(false);
  const [selectedSources, setSelectedSources] = useState<SourceItem[]>([]);
  const [formData, setFormData] = useState({
    source_type: 'document',
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

    if (selectedSources.length === 0) {
      toast.error('Please select at least one source');
      return;
    }

    setGenerating(true);

    try {
      const requestBody = {
        source_type: formData.source_type,
        source_ids: selectedSources.map(s => s.id),
        summary_type: formData.summary_type,
        target_length: formData.target_length,
        focus_areas: formData.focus_areas.split(',').map(s => s.trim()).filter(s => s.length > 0),
        exclude_topics: formData.exclude_topics.split(',').map(s => s.trim()).filter(s => s.length > 0),
        include_key_points: formData.include_key_points,
        include_title: formData.include_title,
        tags: formData.tags.split(',').map(s => s.trim()).filter(s => s.length > 0),
      };

      const result = await apiPost<any>('/api/summary/', requestBody);

      if (result.status === 'completed') {
        toast.success('Summary generated successfully');
        setView('list');
        loadSummaries();
        refetchStats();
        setSelectedSources([]);
        setFormData({
          source_type: 'document',
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
    if (!confirm('Are you sure you want to delete this summary?')) return;

    try {
      await apiDelete('/api/summary/' + summaryId);
      toast.success('Summary deleted');
      setSelectedSummary(null);
      loadSummaries();
      refetchStats();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete summary');
    }
  };

  const handleRegenerateSummary = async (summary: Summary) => {
    if (!confirm('Regenerate this summary? This will create a new version.')) return;

    setGenerating(true);
    try {
      const result = await apiPost<any>('/api/summary/', {
        source_type: summary.source_type,
        source_ids: summary.source_ids,
        summary_type: summary.summary_type,
        target_length: summary.target_length,
        include_key_points: summary.key_points.length > 0,
        include_title: !!summary.title,
        tags: [...summary.tags, 'regenerated'],
      });
      if (result.status === 'completed') {
        toast.success('Summary regenerated successfully');
        loadSummaries();
        refetchStats();
        const newSummary = await apiGet<Summary>('/api/summary/' + result.summary_id);
        setSelectedSummary(newSummary);
      } else {
        toast.error(result.error_message || 'Regeneration failed');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to regenerate');
    } finally {
      setGenerating(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const clearFilters = () => {
    setFilterType('');
    setFilterSourceType('');
    setFilterStatus('');
    setSearchQuery('');
    setPage(1);
  };

  const hasFilters = filterType || filterSourceType || filterStatus || searchQuery;

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

          <div className="view-tabs">
            <button className={'view-tab ' + (view === 'list' ? 'active' : '')} onClick={() => setView('list')}>
              <Icon name="List" size={16} />
              Summaries
            </button>
            <button className={'view-tab ' + (view === 'generate' ? 'active' : '')} onClick={() => setView('generate')}>
              <Icon name="Sparkles" size={16} />
              Generate
            </button>
            <button className={'view-tab ' + (view === 'stats' ? 'active' : '')} onClick={() => setView('stats')}>
              <Icon name="BarChart3" size={16} />
              Stats
            </button>
          </div>
        </div>
      </header>

      {view === 'list' && (
        <div className="summary-layout-with-filters">
          {/* Filters Panel */}
          <div className="filters-panel">
            <div className="filters-header">
              <h3>Filters</h3>
              {hasFilters && <button className="btn-link" onClick={clearFilters}>Clear all</button>}
            </div>

            <div className="filter-group">
              <label>Search</label>
              <input type="text" placeholder="Search summaries..." value={searchQuery}
                onChange={e => { setSearchQuery(e.target.value); setPage(1); }} />
            </div>

            <div className="filter-group">
              <label>Summary Type</label>
              <select value={filterType} onChange={e => { setFilterType(e.target.value); setPage(1); }}>
                <option value="">All types</option>
                {summaryTypesData?.types.map(type => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label>Source Type</label>
              <select value={filterSourceType} onChange={e => { setFilterSourceType(e.target.value); setPage(1); }}>
                <option value="">All sources</option>
                {capabilities?.source_types.map(type => (
                  <option key={type} value={type}>{SOURCE_TYPE_LABELS[type] || type}</option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label>Status</label>
              <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setPage(1); }}>
                <option value="">All statuses</option>
                <option value="completed">Completed</option>
                <option value="generating">Generating</option>
                <option value="failed">Failed</option>
                <option value="stale">Stale</option>
              </select>
            </div>

            <div className="filter-stats"><span>{totalSummaries} summaries found</span></div>
          </div>

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
                <span>{error}</span>
                <button className="btn btn-secondary" onClick={loadSummaries}>Retry</button>
              </div>
            ) : summaries && summaries.length > 0 ? (
              <>
                <div className="summary-items">
                  {summaries.map(summary => (
                    <button key={summary.id}
                      className={'summary-item ' + (selectedSummary?.id === summary.id ? 'active' : '')}
                      onClick={() => setSelectedSummary(summary)}>
                      <div className="summary-item-header">
                        <span className="summary-title">{summary.title || (summary.summary_type + ' summary')}</span>
                        <span className={'status-badge status-' + summary.status}>{summary.status}</span>
                      </div>
                      <div className="summary-item-meta">
                        <span className="meta-item">
                          <Icon name={SOURCE_ICONS[summary.source_type] || 'File'} size={12} />
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

                {totalSummaries > 20 && (
                  <div className="pagination">
                    <button className="btn btn-secondary" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
                    <span className="page-info">Page {page} of {Math.ceil(totalSummaries / 20)}</span>
                    <button className="btn btn-secondary" disabled={page >= Math.ceil(totalSummaries / 20)} onClick={() => setPage(p => p + 1)}>Next</button>
                  </div>
                )}
              </>
            ) : (
              <div className="summary-empty">
                <Icon name="FileText" size={48} />
                <span>{hasFilters ? 'No matching summaries' : 'No summaries yet'}</span>
                {!hasFilters && <button className="btn btn-primary" onClick={() => setView('generate')}>Generate Your First Summary</button>}
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
                      <span className="meta-badge"><Icon name="Type" size={14} />{selectedSummary.summary_type}</span>
                      <span className="meta-badge">
                        <Icon name={SOURCE_ICONS[selectedSummary.source_type] || 'File'} size={14} />
                        {SOURCE_TYPE_LABELS[selectedSummary.source_type] || selectedSummary.source_type}
                      </span>
                      <span className="meta-badge"><Icon name="Calendar" size={14} />{formatDate(selectedSummary.created_at)}</span>
                    </div>
                  </div>
                  <div className="detail-actions">
                    <button className="btn btn-secondary" onClick={() => handleRegenerateSummary(selectedSummary)} disabled={generating}>
                      <Icon name="RefreshCw" size={16} />Regenerate
                    </button>
                    <button className="btn btn-danger" onClick={() => handleDeleteSummary(selectedSummary.id)}>
                      <Icon name="Trash2" size={16} />Delete
                    </button>
                  </div>
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
                        {selectedSummary.key_points.map((point, idx) => <li key={idx}>{point}</li>)}
                      </ul>
                    </section>
                  )}

                  <section className="summary-section">
                    <h3>Source Information</h3>
                    <div className="source-info"><p><strong>Source IDs:</strong> {selectedSummary.source_ids.join(', ')}</p></div>
                  </section>

                  <section className="summary-section">
                    <h3>Metadata</h3>
                    <div className="metadata-grid">
                      <div className="metadata-item"><span className="metadata-label">Word Count</span><span className="metadata-value">{selectedSummary.word_count}</span></div>
                      <div className="metadata-item"><span className="metadata-label">Token Count</span><span className="metadata-value">{selectedSummary.token_count}</span></div>
                      <div className="metadata-item"><span className="metadata-label">Confidence</span><span className="metadata-value">{Math.round(selectedSummary.confidence * 100)}%</span></div>
                      <div className="metadata-item"><span className="metadata-label">Processing Time</span><span className="metadata-value">{Math.round(selectedSummary.processing_time_ms)}ms</span></div>
                      {selectedSummary.model_used && <div className="metadata-item"><span className="metadata-label">Model</span><span className="metadata-value">{selectedSummary.model_used}</span></div>}
                      <div className="metadata-item"><span className="metadata-label">Target Length</span><span className="metadata-value">{LENGTH_LABELS[selectedSummary.target_length] || selectedSummary.target_length}</span></div>
                    </div>
                  </section>

                  {selectedSummary.tags.length > 0 && (
                    <section className="summary-section">
                      <h3>Tags</h3>
                      <div className="tags-list">{selectedSummary.tags.map((tag, idx) => <span key={idx} className="tag">{tag}</span>)}</div>
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
      )}

      {view === 'generate' && (
        <div className="summary-generate">
          <form onSubmit={handleGenerateSummary} className="generate-form">
            <h2>Generate New Summary</h2>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="source_type">Source Type</label>
                <select id="source_type" value={formData.source_type} required
                  onChange={e => { setFormData({ ...formData, source_type: e.target.value }); setSelectedSources([]); }}>
                  {capabilities?.source_types.map(type => (
                    <option key={type} value={type}>{SOURCE_TYPE_LABELS[type] || type}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="summary_type">Summary Type</label>
                <select id="summary_type" value={formData.summary_type} required
                  onChange={e => setFormData({ ...formData, summary_type: e.target.value })}>
                  {summaryTypesData?.types.map(type => (
                    <option key={type.value} value={type.value} title={type.description}>{type.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Source Picker */}
            <div className="form-group">
              <label>Selected Sources<span className="label-hint">({selectedSources.length} selected)</span></label>

              {selectedSources.length > 0 && (
                <div className="selected-sources">
                  {selectedSources.map(source => (
                    <div key={source.id} className="selected-source-chip">
                      <Icon name={SOURCE_ICONS[source.type] || 'File'} size={14} />
                      <span className="source-name">{source.name}</span>
                      <button type="button" className="remove-source"
                        onClick={() => setSelectedSources(prev => prev.filter(s => s.id !== source.id))}>
                        <Icon name="X" size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <button type="button" className="btn btn-secondary source-picker-btn" onClick={() => setSourcePickerOpen(true)}>
                <Icon name="Plus" size={16} />Browse & Select Sources
              </button>
            </div>

            <div className="form-group">
              <label htmlFor="target_length">Target Length</label>
              <select id="target_length" value={formData.target_length}
                onChange={e => setFormData({ ...formData, target_length: e.target.value })}>
                {capabilities?.target_lengths.map(length => (
                  <option key={length} value={length}>{LENGTH_LABELS[length] || length}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="focus_areas">Focus Areas<span className="label-hint">(optional, comma-separated)</span></label>
              <input type="text" id="focus_areas" value={formData.focus_areas}
                onChange={e => setFormData({ ...formData, focus_areas: e.target.value })}
                placeholder="e.g., methodology, results, conclusions" />
            </div>

            <div className="form-group">
              <label htmlFor="exclude_topics">Exclude Topics<span className="label-hint">(optional, comma-separated)</span></label>
              <input type="text" id="exclude_topics" value={formData.exclude_topics}
                onChange={e => setFormData({ ...formData, exclude_topics: e.target.value })}
                placeholder="e.g., technical details, references" />
            </div>

            <div className="form-group">
              <label htmlFor="tags">Tags<span className="label-hint">(optional, comma-separated)</span></label>
              <input type="text" id="tags" value={formData.tags}
                onChange={e => setFormData({ ...formData, tags: e.target.value })}
                placeholder="e.g., research, analysis, important" />
            </div>

            <div className="form-options">
              <label className="checkbox-label">
                <input type="checkbox" checked={formData.include_key_points}
                  onChange={e => setFormData({ ...formData, include_key_points: e.target.checked })} />
                <span>Include key points</span>
              </label>

              <label className="checkbox-label">
                <input type="checkbox" checked={formData.include_title}
                  onChange={e => setFormData({ ...formData, include_title: e.target.checked })} />
                <span>Generate title</span>
              </label>
            </div>

            <div className="form-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setView('list')} disabled={generating}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={generating || selectedSources.length === 0}>
                {generating ? (<><Icon name="Loader2" size={16} className="spin" />Generating...</>) : (<><Icon name="Sparkles" size={16} />Generate Summary</>)}
              </button>
            </div>
          </form>
        </div>
      )}

      {view === 'stats' && (
        <div className="summary-stats">
          <div className="stats-header">
            <h2>Summary Statistics</h2>
            <button className="btn btn-secondary" onClick={() => refetchStats()}>
              <Icon name="RefreshCw" size={16} />Refresh
            </button>
          </div>

          {stats ? (
            <div className="stats-grid">
              <div className="stats-card stats-card-large">
                <div className="stats-card-icon"><Icon name="FileText" size={32} /></div>
                <div className="stats-card-content">
                  <span className="stats-card-value">{stats.total_summaries}</span>
                  <span className="stats-card-label">Total Summaries</span>
                </div>
              </div>

              <div className="stats-card">
                <div className="stats-card-icon success"><Icon name="CheckCircle" size={24} /></div>
                <div className="stats-card-content">
                  <span className="stats-card-value">{stats.generated_last_24h}</span>
                  <span className="stats-card-label">Generated (24h)</span>
                </div>
              </div>

              <div className="stats-card">
                <div className="stats-card-icon error"><Icon name="XCircle" size={24} /></div>
                <div className="stats-card-content">
                  <span className="stats-card-value">{stats.failed_last_24h}</span>
                  <span className="stats-card-label">Failed (24h)</span>
                </div>
              </div>

              <div className="stats-card">
                <div className="stats-card-icon"><Icon name="Hash" size={24} /></div>
                <div className="stats-card-content">
                  <span className="stats-card-value">{stats.total_words_generated.toLocaleString()}</span>
                  <span className="stats-card-label">Total Words</span>
                </div>
              </div>

              <div className="stats-card">
                <div className="stats-card-icon"><Icon name="Zap" size={24} /></div>
                <div className="stats-card-content">
                  <span className="stats-card-value">{stats.total_tokens_used.toLocaleString()}</span>
                  <span className="stats-card-label">Total Tokens</span>
                </div>
              </div>

              <div className="stats-section">
                <h3>Averages</h3>
                <div className="stats-row">
                  <div className="stat-item"><span className="stat-label">Confidence</span><span className="stat-value">{Math.round(stats.avg_confidence * 100)}%</span></div>
                  <div className="stat-item"><span className="stat-label">Word Count</span><span className="stat-value">{Math.round(stats.avg_word_count)}</span></div>
                  <div className="stat-item"><span className="stat-label">Processing Time</span><span className="stat-value">{Math.round(stats.avg_processing_time_ms)}ms</span></div>
                </div>
              </div>

              {Object.keys(stats.by_type).length > 0 && (
                <div className="stats-section">
                  <h3>By Summary Type</h3>
                  <div className="stats-breakdown">
                    {Object.entries(stats.by_type).map(([type, count]) => (
                      <div key={type} className="breakdown-item">
                        <span className="breakdown-label">{type}</span>
                        <span className="breakdown-value">{count}</span>
                        <div className="breakdown-bar"><div className="breakdown-fill" style={{ width: (count / stats.total_summaries * 100) + '%' }} /></div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {Object.keys(stats.by_source_type).length > 0 && (
                <div className="stats-section">
                  <h3>By Source Type</h3>
                  <div className="stats-breakdown">
                    {Object.entries(stats.by_source_type).map(([type, count]) => (
                      <div key={type} className="breakdown-item">
                        <span className="breakdown-label"><Icon name={SOURCE_ICONS[type] || 'File'} size={14} />{SOURCE_TYPE_LABELS[type] || type}</span>
                        <span className="breakdown-value">{count}</span>
                        <div className="breakdown-bar"><div className="breakdown-fill source" style={{ width: (count / stats.total_summaries * 100) + '%' }} /></div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {Object.keys(stats.by_status).length > 0 && (
                <div className="stats-section">
                  <h3>By Status</h3>
                  <div className="stats-breakdown">
                    {Object.entries(stats.by_status).map(([status, count]) => (
                      <div key={status} className="breakdown-item">
                        <span className={'breakdown-label status-' + status}>{status}</span>
                        <span className="breakdown-value">{count}</span>
                        <div className="breakdown-bar"><div className={'breakdown-fill status-' + status} style={{ width: (count / stats.total_summaries * 100) + '%' }} /></div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {Object.keys(stats.by_model).length > 0 && (
                <div className="stats-section">
                  <h3>By Model</h3>
                  <div className="stats-breakdown">
                    {Object.entries(stats.by_model).map(([model, count]) => (
                      <div key={model} className="breakdown-item">
                        <span className="breakdown-label">{model}</span>
                        <span className="breakdown-value">{count}</span>
                        <div className="breakdown-bar"><div className="breakdown-fill model" style={{ width: (count / stats.total_summaries * 100) + '%' }} /></div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="stats-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading statistics...</span>
            </div>
          )}
        </div>
      )}

      {sourcePickerOpen && (
        <SourcePickerModal
          sourceType={formData.source_type}
          selectedSources={selectedSources}
          onSelect={setSelectedSources}
          onClose={() => setSourcePickerOpen(false)}
        />
      )}
    </div>
  );
}

function SourcePickerModal({
  sourceType,
  selectedSources,
  onSelect,
  onClose,
}: {
  sourceType: string;
  selectedSources: SourceItem[];
  onSelect: (sources: SourceItem[]) => void;
  onClose: () => void;
}) {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [localSelected, setLocalSelected] = useState<Set<string>>(new Set(selectedSources.map(s => s.id)));

  const getEndpoint = useCallback(() => {
    switch (sourceType) {
      case 'document':
      case 'documents': return '/api/summary/sources/documents';
      case 'entity': return '/api/summary/sources/entities';
      case 'project': return '/api/summary/sources/projects';
      case 'claim_set': return '/api/summary/sources/claims';
      case 'timeline': return '/api/summary/sources/timeline';
      default: return '/api/summary/sources/documents';
    }
  }, [sourceType]);

  useEffect(() => {
    const loadSources = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set('page', page.toString());
        params.set('page_size', '20');
        if (searchQuery) params.set('q', searchQuery);

        const data = await apiGet<SourceListResponse>(getEndpoint() + '?' + params.toString());
        setSources(Array.isArray(data.items) ? data.items : []);
        setTotal(typeof data.total === 'number' ? data.total : 0);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sources');
      } finally {
        setLoading(false);
      }
    };

    loadSources();
  }, [getEndpoint, page, searchQuery]);

  const toggleSource = (source: SourceItem) => {
    const newSelected = new Set(localSelected);
    if (newSelected.has(source.id)) {
      newSelected.delete(source.id);
    } else {
      newSelected.add(source.id);
    }
    setLocalSelected(newSelected);
  };

  const handleConfirm = () => {
    const allSources = [...selectedSources, ...sources];
    const uniqueSources = new Map<string, SourceItem>();
    allSources.forEach(s => uniqueSources.set(s.id, s));

    const finalSelection = Array.from(localSelected)
      .map(id => uniqueSources.get(id))
      .filter((s): s is SourceItem => s !== undefined);

    onSelect(finalSelection);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="source-picker-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Select {SOURCE_TYPE_LABELS[sourceType] || sourceType}s</h3>
          <button className="modal-close" onClick={onClose}><Icon name="X" size={20} /></button>
        </div>

        <div className="modal-search">
          <Icon name="Search" size={16} />
          <input type="text" placeholder="Search..." value={searchQuery} autoFocus
            onChange={e => { setSearchQuery(e.target.value); setPage(1); }} />
        </div>

        <div className="modal-body">
          {loading ? (
            <div className="picker-loading"><Icon name="Loader2" size={24} className="spin" /><span>Loading...</span></div>
          ) : error ? (
            <div className="picker-error"><Icon name="AlertCircle" size={24} /><span>{error}</span></div>
          ) : sources.length > 0 ? (
            <div className="source-list">
              {sources.map(source => (
                <label key={source.id} className="source-option">
                  <input type="checkbox" checked={localSelected.has(source.id)} onChange={() => toggleSource(source)} />
                  <div className="source-option-content">
                    <Icon name={SOURCE_ICONS[source.type] || 'File'} size={16} />
                    <div className="source-option-info">
                      <span className="source-option-name">{source.name}</span>
                      <span className="source-option-preview">{source.preview}</span>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          ) : (
            <div className="picker-empty"><Icon name="Inbox" size={48} /><span>No {SOURCE_TYPE_LABELS[sourceType] || 'sources'}s found</span></div>
          )}
        </div>

        {total > 20 && (
          <div className="modal-pagination">
            <button className="btn btn-secondary btn-sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
            <span>Page {page} of {Math.ceil(total / 20)}</span>
            <button className="btn btn-secondary btn-sm" disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(p => p + 1)}>Next</button>
          </div>
        )}

        <div className="modal-footer">
          <span className="selected-count">{localSelected.size} selected</span>
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" onClick={handleConfirm}>Confirm Selection</button>
          </div>
        </div>
      </div>
    </div>
  );
}
