/**
 * PatternsPage - Full Pattern Detection and Analysis UI
 *
 * Features:
 * - Pattern list with filtering and tabbed views
 * - Create/Edit pattern modals
 * - Pattern analysis panel (text & document analysis)
 * - Correlation analysis
 * - Pattern criteria display
 * - Match evidence viewer
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { AIAnalystButton } from '../../components/AIAnalyst';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import { apiDelete, apiGet, apiPost, apiPut } from '../../utils/api';
import './PatternsPage.css';

// Types
interface PatternCriteria {
  keywords?: string[];
  regex_patterns?: string[];
  entity_types?: string[];
  entity_ids?: string[];
  min_occurrences?: number;
  time_window_days?: number;
  similarity_threshold?: number;
}

interface Pattern {
  id: string;
  name: string;
  description: string;
  pattern_type: string;
  status: string;
  confidence: number;
  match_count: number;
  document_count: number;
  entity_count: number;
  first_detected: string;
  last_matched: string | null;
  detection_method: string;
  detection_model: string | null;
  criteria: PatternCriteria;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

interface PatternMatch {
  id: string;
  pattern_id: string;
  source_type: string;
  source_id: string;
  source_title: string | null;
  match_score: number;
  excerpt: string | null;
  context: string | null;
  start_char: number | null;
  end_char: number | null;
  matched_at: string;
  matched_by: string;
}

interface Stats {
  total_patterns: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  by_detection_method: Record<string, number>;
  total_matches: number;
  avg_confidence: number;
  patterns_pending_review: number;
  patterns_confirmed: number;
  patterns_dismissed: number;
}

interface Capabilities {
  llm_available: boolean;
  vectors_available: boolean;
  workers_available: boolean;
  pattern_types: string[];
  detection_methods: string[];
}

interface AnalysisResult {
  patterns_detected: Pattern[];
  matches_found: PatternMatch[];
  documents_analyzed: number;
  processing_time_ms: number;
  errors: string[];
}

const PATTERN_TYPE_LABELS: Record<string, string> = {
  recurring_theme: 'Recurring Theme',
  behavioral: 'Behavioral',
  temporal: 'Temporal',
  correlation: 'Correlation',
  linguistic: 'Linguistic',
  structural: 'Structural',
  custom: 'Custom',
};

const PATTERN_TYPE_ICONS: Record<string, string> = {
  recurring_theme: 'Repeat',
  behavioral: 'Activity',
  temporal: 'Clock',
  correlation: 'GitBranch',
  linguistic: 'Type',
  structural: 'Layout',
  custom: 'Settings',
};

const STATUS_LABELS: Record<string, string> = {
  detected: 'Detected',
  confirmed: 'Confirmed',
  dismissed: 'Dismissed',
  archived: 'Archived',
};


type TabType = 'all' | 'recurring' | 'behavioral' | 'temporal' | 'analyze';

export function PatternsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();

  // State
  const [selectedPattern, setSelectedPattern] = useState<Pattern | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('all');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);

  // Form state
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formType, setFormType] = useState('recurring_theme');
  const [formConfidence, setFormConfidence] = useState(0.5);
  const [formKeywords, setFormKeywords] = useState('');
  const [formRegex, setFormRegex] = useState('');
  const [formMinOccurrences, setFormMinOccurrences] = useState(2);

  // Analysis state
  const [analyzeText, setAnalyzeText] = useState('');
  const [analyzeMinConfidence, setAnalyzeMinConfidence] = useState(0.5);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);

  // Auto-fetch document content for analysis if doc_id param is passed
  useEffect(() => {
    const docId = searchParams.get('doc_id');
    if (docId) {
      // Fetch document content and open analyze modal
      const fetchDocContent = async () => {
        try {
          const data = await apiGet<{ content?: string }>(`/api/documents/${docId}/content`);
          setAnalyzeText(data.content || '');
          setShowAnalyzeModal(true);
          toast.info('Document content loaded for analysis');
        } catch (err) {
          toast.error('Failed to fetch document content');
        }
      };
      fetchDocContent();
      // Clear the URL param
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams, toast]);

  // Build filter params based on active tab
  const getFilterParams = useCallback(() => {
    const params: Record<string, string> = {};

    if (activeTab === 'recurring') params.pattern_type = 'recurring_theme';
    else if (activeTab === 'behavioral') params.pattern_type = 'behavioral';
    else if (activeTab === 'temporal') params.pattern_type = 'temporal';

    if (statusFilter) params.status = statusFilter;
    if (searchQuery) params.q = searchQuery;

    return params;
  }, [activeTab, statusFilter, searchQuery]);

  // Fetch patterns with pagination
  const {
    items: patterns,
    loading,
    error,
    refetch
  } = usePaginatedFetch<Pattern>('/api/patterns/', {
    params: getFilterParams()
  });

  // Fetch stats
  const { data: stats, refetch: refetchStats } = useFetch<Stats>('/api/patterns/stats');

  // Fetch capabilities
  const { data: capabilities } = useFetch<Capabilities>('/api/patterns/capabilities');

  // Fetch matches for selected pattern
  const { data: matchesData, loading: matchesLoading } = useFetch<{ items: PatternMatch[]; total: number }>(
    selectedPattern ? `/api/patterns/${selectedPattern.id}/matches` : null
  );
  const matches = matchesData?.items || [];

  // Refresh patterns when tab changes
  useEffect(() => {
    refetch();
  }, [activeTab, statusFilter, searchQuery]);

  // Reset form when opening create modal
  const openCreateModal = () => {
    setFormName('');
    setFormDescription('');
    setFormType('recurring_theme');
    setFormConfidence(0.5);
    setFormKeywords('');
    setFormRegex('');
    setFormMinOccurrences(2);
    setShowCreateModal(true);
  };

  // Populate form when opening edit modal
  const openEditModal = (pattern: Pattern) => {
    setFormName(pattern.name);
    setFormDescription(pattern.description);
    setFormType(pattern.pattern_type);
    setFormConfidence(pattern.confidence);
    setFormKeywords(pattern.criteria?.keywords?.join(', ') || '');
    setFormRegex(pattern.criteria?.regex_patterns?.join('\n') || '');
    setFormMinOccurrences(pattern.criteria?.min_occurrences || 2);
    setShowEditModal(true);
  };

  // Create pattern
  const handleCreatePattern = async () => {
    try {
      const keywords = formKeywords.split(',').map(k => k.trim()).filter(k => k);
      const regexPatterns = formRegex.split('\n').map(r => r.trim()).filter(r => r);

      await apiPost('/api/patterns/', {
        name: formName,
        description: formDescription,
        pattern_type: formType,
        confidence: formConfidence,
        criteria: {
          keywords,
          regex_patterns: regexPatterns,
          min_occurrences: formMinOccurrences,
        },
      });

      toast.success('Pattern created');
      setShowCreateModal(false);
      refetch();
      refetchStats();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create pattern');
    }
  };

  // Update pattern
  const handleUpdatePattern = async () => {
    if (!selectedPattern) return;

    try {
      const keywords = formKeywords.split(',').map(k => k.trim()).filter(k => k);
      const regexPatterns = formRegex.split('\n').map(r => r.trim()).filter(r => r);

      const updated = await apiPut<Pattern>(`/api/patterns/${selectedPattern.id}`, {
        name: formName,
        description: formDescription,
        confidence: formConfidence,
        criteria: {
          keywords,
          regex_patterns: regexPatterns,
          min_occurrences: formMinOccurrences,
        },
      });
      toast.success('Pattern updated');
      setShowEditModal(false);
      setSelectedPattern(updated);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update pattern');
    }
  };

  // Confirm pattern
  const handleConfirmPattern = async (patternId: string) => {
    try {
      const updated = await apiPost<Pattern>(`/api/patterns/${patternId}/confirm`);
      toast.success('Pattern confirmed');
      refetch();
      refetchStats();
      if (selectedPattern?.id === patternId) {
        setSelectedPattern(updated);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to confirm pattern');
    }
  };

  // Dismiss pattern
  const handleDismissPattern = async (patternId: string) => {
    try {
      await apiPost(`/api/patterns/${patternId}/dismiss`);
      toast.success('Pattern dismissed');
      refetch();
      refetchStats();
      if (selectedPattern?.id === patternId) {
        setSelectedPattern(null);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to dismiss pattern');
    }
  };

  // Delete pattern
  const handleDeletePattern = async (patternId: string) => {
    if (!confirm('Are you sure you want to delete this pattern?')) return;

    try {
      await apiDelete(`/api/patterns/${patternId}`);

      toast.success('Pattern deleted');
      refetch();
      refetchStats();
      if (selectedPattern?.id === patternId) {
        setSelectedPattern(null);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete pattern');
    }
  };

  // Run analysis
  const handleAnalyze = async () => {
    if (!analyzeText.trim()) {
      toast.error('Please enter text to analyze');
      return;
    }

    setAnalyzing(true);
    setAnalysisResult(null);

    try {
      const result = await apiPost<AnalysisResult>('/api/patterns/analyze', {
        text: analyzeText,
        min_confidence: analyzeMinConfidence,
      });
      setAnalysisResult(result);
      toast.success(`Found ${result.patterns_detected.length} patterns`);
      refetch();
      refetchStats();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.8) return 'high';
    if (confidence >= 0.5) return 'medium';
    return 'low';
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="patterns-page">
      {/* Header */}
      <header className="page-header">
        <div className="page-title">
          <Icon name="Fingerprint" size={28} />
          <div>
            <h1>Patterns</h1>
            <p className="page-description">Cross-document pattern detection and analysis</p>
          </div>
        </div>

        <div className="header-actions">
          <button className="btn btn-secondary" onClick={() => setShowAnalyzeModal(true)}>
            <Icon name="Search" size={16} />
            Analyze Text
          </button>
          <button className="btn btn-primary" onClick={openCreateModal}>
            <Icon name="Plus" size={16} />
            New Pattern
          </button>
          <AIAnalystButton
            shard="patterns"
            targetId={selectedPattern?.id || 'overview'}
            context={{
              statistics: stats || null,
              selected_pattern: selectedPattern ? {
                id: selectedPattern.id,
                name: selectedPattern.name,
                description: selectedPattern.description,
                pattern_type: selectedPattern.pattern_type,
                status: selectedPattern.status,
                confidence: selectedPattern.confidence,
                match_count: selectedPattern.match_count,
                criteria: selectedPattern.criteria,
              } : null,
              patterns: patterns.slice(0, 20).map(p => ({
                id: p.id,
                name: p.name,
                pattern_type: p.pattern_type,
                status: p.status,
                confidence: p.confidence,
                match_count: p.match_count,
              })),
              total_count: stats?.total_patterns || 0,
              active_tab: activeTab,
            }}
            label="AI Analysis"
            variant="secondary"
            size="sm"
          />
        </div>

        {stats && (
          <div className="stats-summary">
            <div className="stat">
              <span className="stat-value">{stats.total_patterns}</span>
              <span className="stat-label">Total</span>
            </div>
            <div className="stat stat-warning">
              <span className="stat-value">{stats.patterns_pending_review}</span>
              <span className="stat-label">Pending</span>
            </div>
            <div className="stat stat-success">
              <span className="stat-value">{stats.patterns_confirmed}</span>
              <span className="stat-label">Confirmed</span>
            </div>
            <div className="stat">
              <span className="stat-value">{stats.total_matches}</span>
              <span className="stat-label">Matches</span>
            </div>
          </div>
        )}
      </header>

      {/* Tabs */}
      <div className="tabs-bar">
        <button
          className={`tab ${activeTab === 'all' ? 'active' : ''}`}
          onClick={() => setActiveTab('all')}
        >
          <Icon name="List" size={16} />
          All Patterns
        </button>
        <button
          className={`tab ${activeTab === 'recurring' ? 'active' : ''}`}
          onClick={() => setActiveTab('recurring')}
        >
          <Icon name="Repeat" size={16} />
          Recurring
        </button>
        <button
          className={`tab ${activeTab === 'behavioral' ? 'active' : ''}`}
          onClick={() => setActiveTab('behavioral')}
        >
          <Icon name="Activity" size={16} />
          Behavioral
        </button>
        <button
          className={`tab ${activeTab === 'temporal' ? 'active' : ''}`}
          onClick={() => setActiveTab('temporal')}
        >
          <Icon name="Clock" size={16} />
          Temporal
        </button>
      </div>

      <div className="patterns-layout">
        {/* Filters */}
        <div className="filters-bar">
          <input
            type="text"
            placeholder="Search patterns..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="filter-select"
          >
            <option value="">All Statuses</option>
            <option value="detected">Detected</option>
            <option value="confirmed">Confirmed</option>
            <option value="dismissed">Dismissed</option>
            <option value="archived">Archived</option>
          </select>
          {capabilities && (
            <div className="capabilities-badges">
              {capabilities.llm_available && (
                <span className="capability-badge">
                  <Icon name="Sparkles" size={12} /> LLM
                </span>
              )}
              {capabilities.vectors_available && (
                <span className="capability-badge">
                  <Icon name="Layers" size={12} /> Vectors
                </span>
              )}
            </div>
          )}
        </div>

        {/* Main content */}
        <div className="patterns-content">
          {/* Patterns list */}
          <div className="patterns-list">
            {loading ? (
              <div className="loading-state">
                <Icon name="Loader2" size={32} className="spin" />
                <span>Loading patterns...</span>
              </div>
            ) : error ? (
              <div className="error-state">
                <Icon name="AlertCircle" size={32} />
                <span>Failed to load patterns</span>
                <button className="btn btn-secondary" onClick={() => refetch()}>
                  Retry
                </button>
              </div>
            ) : patterns.length === 0 ? (
              <div className="empty-state">
                <Icon name="Fingerprint" size={48} />
                <span>No patterns found</span>
                <p className="empty-hint">
                  {activeTab === 'all'
                    ? 'Create a pattern or run analysis to get started'
                    : `No ${activeTab} patterns detected yet`}
                </p>
                <button className="btn btn-primary" onClick={openCreateModal}>
                  <Icon name="Plus" size={16} />
                  Create Pattern
                </button>
              </div>
            ) : (
              patterns.map((pattern) => (
                <div
                  key={pattern.id}
                  className={`pattern-item ${selectedPattern?.id === pattern.id ? 'selected' : ''} status-${pattern.status}`}
                  onClick={() => setSelectedPattern(pattern)}
                >
                  <div className="pattern-header">
                    <Icon name={PATTERN_TYPE_ICONS[pattern.pattern_type] || 'Circle'} size={20} />
                    <div className="pattern-info">
                      <h3>{pattern.name}</h3>
                      <p className="pattern-type">{PATTERN_TYPE_LABELS[pattern.pattern_type] || pattern.pattern_type}</p>
                    </div>
                    <span className={`confidence-badge ${getConfidenceBadge(pattern.confidence)}`}>
                      {(pattern.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="pattern-description">{pattern.description}</p>
                  <div className="pattern-stats">
                    <span className="stat-item">
                      <Icon name="Target" size={14} />
                      {pattern.match_count} matches
                    </span>
                    <span className="stat-item">
                      <Icon name="FileText" size={14} />
                      {pattern.document_count} docs
                    </span>
                    <span className={`status-pill status-${pattern.status}`}>
                      {STATUS_LABELS[pattern.status]}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Pattern detail */}
          {selectedPattern && (
            <div className="pattern-detail">
              <div className="detail-header">
                <div className="detail-title">
                  <Icon name={PATTERN_TYPE_ICONS[selectedPattern.pattern_type] || 'Fingerprint'} size={24} />
                  <h2>{selectedPattern.name}</h2>
                  <span className={`status-badge status-${selectedPattern.status}`}>
                    {STATUS_LABELS[selectedPattern.status]}
                  </span>
                </div>
                <div className="detail-actions">
                  {selectedPattern.status === 'detected' && (
                    <>
                      <button
                        className="btn btn-success"
                        onClick={() => handleConfirmPattern(selectedPattern.id)}
                      >
                        <Icon name="CheckCircle" size={16} />
                        Confirm
                      </button>
                      <button
                        className="btn btn-secondary"
                        onClick={() => handleDismissPattern(selectedPattern.id)}
                      >
                        <Icon name="XCircle" size={16} />
                        Dismiss
                      </button>
                    </>
                  )}
                  <button
                    className="btn btn-secondary"
                    onClick={() => openEditModal(selectedPattern)}
                  >
                    <Icon name="Edit" size={16} />
                    Edit
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={() => handleDeletePattern(selectedPattern.id)}
                  >
                    <Icon name="Trash2" size={16} />
                  </button>
                  <button
                    className="btn btn-ghost"
                    onClick={() => setSelectedPattern(null)}
                  >
                    <Icon name="X" size={16} />
                  </button>
                </div>
              </div>

              <div className="detail-body">
                {/* Details Section */}
                <div className="detail-section">
                  <h3>Details</h3>
                  <dl className="detail-list">
                    <dt>Type:</dt>
                    <dd>
                      <Icon name={PATTERN_TYPE_ICONS[selectedPattern.pattern_type] || 'Circle'} size={14} />
                      {PATTERN_TYPE_LABELS[selectedPattern.pattern_type]}
                    </dd>
                    <dt>Confidence:</dt>
                    <dd>
                      <span className={`confidence-badge ${getConfidenceBadge(selectedPattern.confidence)}`}>
                        {(selectedPattern.confidence * 100).toFixed(0)}%
                      </span>
                    </dd>
                    <dt>Detection:</dt>
                    <dd>{selectedPattern.detection_method}</dd>
                    <dt>First Detected:</dt>
                    <dd>{formatDate(selectedPattern.first_detected)}</dd>
                    {selectedPattern.last_matched && (
                      <>
                        <dt>Last Match:</dt>
                        <dd>{formatDate(selectedPattern.last_matched)}</dd>
                      </>
                    )}
                  </dl>
                </div>

                {/* Description */}
                <div className="detail-section">
                  <h3>Description</h3>
                  <p className="description-text">{selectedPattern.description}</p>
                </div>

                {/* Criteria Section */}
                {selectedPattern.criteria && (
                  <div className="detail-section">
                    <h3>Matching Criteria</h3>
                    <div className="criteria-display">
                      {selectedPattern.criteria.keywords && selectedPattern.criteria.keywords.length > 0 && (
                        <div className="criteria-item">
                          <span className="criteria-label">Keywords:</span>
                          <div className="criteria-tags">
                            {selectedPattern.criteria.keywords.map((kw, i) => (
                              <span key={i} className="criteria-tag">{kw}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedPattern.criteria.regex_patterns && selectedPattern.criteria.regex_patterns.length > 0 && (
                        <div className="criteria-item">
                          <span className="criteria-label">Regex:</span>
                          <div className="criteria-patterns">
                            {selectedPattern.criteria.regex_patterns.map((rx, i) => (
                              <code key={i} className="criteria-regex">{rx}</code>
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedPattern.criteria.min_occurrences && selectedPattern.criteria.min_occurrences > 1 && (
                        <div className="criteria-item">
                          <span className="criteria-label">Min Occurrences:</span>
                          <span>{selectedPattern.criteria.min_occurrences}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Evidence from LLM */}
                {(() => {
                  const evidence = selectedPattern.metadata?.evidence;
                  if (!evidence || !Array.isArray(evidence)) return null;
                  const evidenceItems = evidence as string[];
                  return (
                    <div className="detail-section">
                      <h3>Supporting Evidence</h3>
                      <div className="evidence-list">
                        {evidenceItems.map((item, i) => (
                          <div key={i} className="evidence-item">
                            <Icon name="Quote" size={14} />
                            <span>"{String(item)}"</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}

                {/* Matches Section */}
                <div className="detail-section">
                  <h3>Matches ({selectedPattern.match_count})</h3>
                  {matchesLoading ? (
                    <div className="loading-state small">
                      <Icon name="Loader2" size={20} className="spin" />
                      <span>Loading matches...</span>
                    </div>
                  ) : matches.length === 0 ? (
                    <p className="empty-hint">No matches found for this pattern</p>
                  ) : (
                    <div className="matches-list">
                      {matches.map((match) => (
                        <div key={match.id} className="match-item">
                          <div className="match-header">
                            <Icon name="Target" size={16} />
                            <span className="match-source">
                              {match.source_type}: {match.source_title || match.source_id}
                            </span>
                            <span className={`confidence-badge ${getConfidenceBadge(match.match_score)}`}>
                              {(match.match_score * 100).toFixed(0)}%
                            </span>
                          </div>
                          {match.excerpt && (
                            <p className="match-excerpt">"{match.excerpt}"</p>
                          )}
                          <div className="match-meta">
                            <span>Matched: {formatDate(match.matched_at)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Pattern Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create Pattern</h2>
              <button className="btn btn-ghost" onClick={() => setShowCreateModal(false)}>
                <Icon name="X" size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="Pattern name"
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="What does this pattern represent?"
                  className="form-textarea"
                  rows={3}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Type</label>
                  <select
                    value={formType}
                    onChange={(e) => setFormType(e.target.value)}
                    className="form-select"
                  >
                    {Object.entries(PATTERN_TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Confidence</label>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={formConfidence}
                    onChange={(e) => setFormConfidence(parseFloat(e.target.value))}
                    className="form-input"
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Keywords (comma-separated)</label>
                <input
                  type="text"
                  value={formKeywords}
                  onChange={(e) => setFormKeywords(e.target.value)}
                  placeholder="keyword1, keyword2, keyword3"
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label>Regex Patterns (one per line)</label>
                <textarea
                  value={formRegex}
                  onChange={(e) => setFormRegex(e.target.value)}
                  placeholder="Pattern1.*\nPattern2\d+"
                  className="form-textarea"
                  rows={2}
                />
              </div>
              <div className="form-group">
                <label>Minimum Occurrences</label>
                <input
                  type="number"
                  min="1"
                  value={formMinOccurrences}
                  onChange={(e) => setFormMinOccurrences(parseInt(e.target.value))}
                  className="form-input"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleCreatePattern} disabled={!formName.trim()}>
                <Icon name="Plus" size={16} />
                Create Pattern
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Pattern Modal */}
      {showEditModal && selectedPattern && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Edit Pattern</h2>
              <button className="btn btn-ghost" onClick={() => setShowEditModal(false)}>
                <Icon name="X" size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="form-textarea"
                  rows={3}
                />
              </div>
              <div className="form-group">
                <label>Confidence</label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={formConfidence}
                  onChange={(e) => setFormConfidence(parseFloat(e.target.value))}
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label>Keywords (comma-separated)</label>
                <input
                  type="text"
                  value={formKeywords}
                  onChange={(e) => setFormKeywords(e.target.value)}
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label>Regex Patterns (one per line)</label>
                <textarea
                  value={formRegex}
                  onChange={(e) => setFormRegex(e.target.value)}
                  className="form-textarea"
                  rows={2}
                />
              </div>
              <div className="form-group">
                <label>Minimum Occurrences</label>
                <input
                  type="number"
                  min="1"
                  value={formMinOccurrences}
                  onChange={(e) => setFormMinOccurrences(parseInt(e.target.value))}
                  className="form-input"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowEditModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleUpdatePattern} disabled={!formName.trim()}>
                <Icon name="Save" size={16} />
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Analyze Text Modal */}
      {showAnalyzeModal && (
        <div className="modal-overlay" onClick={() => setShowAnalyzeModal(false)}>
          <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Icon name="Search" size={20} />
                Analyze Text for Patterns
              </h2>
              <button className="btn btn-ghost" onClick={() => setShowAnalyzeModal(false)}>
                <Icon name="X" size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Text to Analyze</label>
                <textarea
                  value={analyzeText}
                  onChange={(e) => setAnalyzeText(e.target.value)}
                  placeholder="Paste text here to analyze for patterns..."
                  className="form-textarea"
                  rows={10}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Minimum Confidence</label>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={analyzeMinConfidence}
                    onChange={(e) => setAnalyzeMinConfidence(parseFloat(e.target.value))}
                    className="form-input"
                  />
                </div>
                <div className="form-group">
                  <label>Capabilities</label>
                  <div className="capabilities-info">
                    {capabilities?.llm_available ? (
                      <span className="capability-active">
                        <Icon name="Sparkles" size={14} /> LLM Analysis Available
                      </span>
                    ) : (
                      <span className="capability-inactive">
                        <Icon name="AlertCircle" size={14} /> Keyword Analysis Only
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {analysisResult && (
                <div className="analysis-results">
                  <h3>Analysis Results</h3>
                  <div className="analysis-stats">
                    <span>Patterns Found: {analysisResult.patterns_detected.length}</span>
                    <span>Processing Time: {analysisResult.processing_time_ms.toFixed(0)}ms</span>
                  </div>
                  {analysisResult.patterns_detected.length > 0 && (
                    <div className="detected-patterns">
                      {analysisResult.patterns_detected.map((pattern) => (
                        <div key={pattern.id} className="detected-pattern">
                          <div className="detected-header">
                            <Icon name={PATTERN_TYPE_ICONS[pattern.pattern_type] || 'Circle'} size={16} />
                            <span className="detected-name">{pattern.name}</span>
                            <span className={`confidence-badge ${getConfidenceBadge(pattern.confidence)}`}>
                              {(pattern.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                          <p className="detected-description">{pattern.description}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  {analysisResult.errors.length > 0 && (
                    <div className="analysis-errors">
                      {analysisResult.errors.map((err, i) => (
                        <p key={i} className="error-message">{err}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowAnalyzeModal(false)}>
                Close
              </button>
              <button
                className="btn btn-primary"
                onClick={handleAnalyze}
                disabled={analyzing || !analyzeText.trim()}
              >
                {analyzing ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Icon name="Search" size={16} />
                    Analyze
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
