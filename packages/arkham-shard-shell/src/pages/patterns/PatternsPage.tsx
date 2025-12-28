/**
 * PatternsPage - Pattern detection and analysis
 *
 * Provides UI for viewing patterns, pattern matches, and running pattern analysis.
 */

import { useState } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import './PatternsPage.css';

// Types
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
  created_at: string;
  updated_at: string;
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
  total_matches: number;
  avg_confidence: number;
  patterns_pending_review: number;
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

const STATUS_LABELS: Record<string, string> = {
  detected: 'Detected',
  confirmed: 'Confirmed',
  dismissed: 'Dismissed',
  archived: 'Archived',
};

const STATUS_ICONS: Record<string, string> = {
  detected: 'AlertCircle',
  confirmed: 'CheckCircle',
  dismissed: 'XCircle',
  archived: 'Archive',
};

export function PatternsPage() {
  const { toast } = useToast();
  const [selectedPattern, setSelectedPattern] = useState<Pattern | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  // Build filter params
  const filterParams: Record<string, string> = {};
  if (statusFilter) filterParams.status = statusFilter;
  if (typeFilter) filterParams.pattern_type = typeFilter;
  if (searchQuery) filterParams.q = searchQuery;

  // Fetch patterns with pagination
  const { items: patterns, loading, error, refetch } = usePaginatedFetch<Pattern>(
    '/api/patterns/',
    { params: filterParams }
  );

  // Fetch stats
  const { data: stats } = useFetch<Stats>('/api/patterns/stats');

  // Fetch matches for selected pattern (keep as useFetch - secondary detail fetch)
  const { data: matchesData, loading: matchesLoading } = useFetch<{ items: PatternMatch[]; total: number }>(
    selectedPattern ? `/api/patterns/${selectedPattern.id}/matches` : null
  );

  const matches = matchesData?.items || [];

  const handleConfirmPattern = async (patternId: string) => {
    try {
      const response = await fetch(`/api/patterns/${patternId}/confirm`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to confirm pattern');
      }

      toast.success('Pattern confirmed');
      refetch();
      if (selectedPattern?.id === patternId) {
        const updated = await response.json();
        setSelectedPattern(updated);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to confirm pattern');
    }
  };

  const handleDismissPattern = async (patternId: string) => {
    try {
      const response = await fetch(`/api/patterns/${patternId}/dismiss`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to dismiss pattern');
      }

      toast.success('Pattern dismissed');
      refetch();
      if (selectedPattern?.id === patternId) {
        setSelectedPattern(null);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to dismiss pattern');
    }
  };

  const handleDeletePattern = async (patternId: string) => {
    if (!confirm('Are you sure you want to delete this pattern?')) return;

    try {
      const response = await fetch(`/api/patterns/${patternId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete pattern');
      }

      toast.success('Pattern deleted');
      refetch();
      if (selectedPattern?.id === patternId) {
        setSelectedPattern(null);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete pattern');
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
      <header className="page-header">
        <div className="page-title">
          <Icon name="Fingerprint" size={28} />
          <div>
            <h1>Patterns</h1>
            <p className="page-description">Cross-document pattern detection and analysis</p>
          </div>
        </div>

        {stats && (
          <div className="stats-summary">
            <div className="stat">
              <span className="stat-value">{stats.total_patterns}</span>
              <span className="stat-label">Total Patterns</span>
            </div>
            <div className="stat">
              <span className="stat-value">{stats.patterns_pending_review}</span>
              <span className="stat-label">Pending Review</span>
            </div>
            <div className="stat">
              <span className="stat-value">{stats.total_matches}</span>
              <span className="stat-label">Total Matches</span>
            </div>
            <div className="stat">
              <span className="stat-value">{(stats.avg_confidence * 100).toFixed(0)}%</span>
              <span className="stat-label">Avg Confidence</span>
            </div>
          </div>
        )}
      </header>

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
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="filter-select"
          >
            <option value="">All Types</option>
            <option value="recurring_theme">Recurring Theme</option>
            <option value="behavioral">Behavioral</option>
            <option value="temporal">Temporal</option>
            <option value="correlation">Correlation</option>
            <option value="linguistic">Linguistic</option>
            <option value="structural">Structural</option>
          </select>
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
                <p className="empty-hint">Patterns will appear here as they are detected</p>
              </div>
            ) : (
              patterns.map((pattern) => (
                <div
                  key={pattern.id}
                  className={`pattern-item ${selectedPattern?.id === pattern.id ? 'selected' : ''} status-${pattern.status}`}
                  onClick={() => setSelectedPattern(pattern)}
                >
                  <div className="pattern-header">
                    <Icon name={STATUS_ICONS[pattern.status] || 'Circle'} size={20} />
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
                    <span className="stat-item">
                      <Icon name="Users" size={14} />
                      {pattern.entity_count} entities
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
                  <Icon name="Fingerprint" size={24} />
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
                    className="btn btn-danger"
                    onClick={() => handleDeletePattern(selectedPattern.id)}
                  >
                    <Icon name="Trash2" size={16} />
                    Delete
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
                <div className="detail-section">
                  <h3>Details</h3>
                  <dl className="detail-list">
                    <dt>Type:</dt>
                    <dd>{PATTERN_TYPE_LABELS[selectedPattern.pattern_type]}</dd>
                    <dt>Confidence:</dt>
                    <dd>
                      <span className={`confidence-badge ${getConfidenceBadge(selectedPattern.confidence)}`}>
                        {(selectedPattern.confidence * 100).toFixed(0)}%
                      </span>
                    </dd>
                    <dt>Detection Method:</dt>
                    <dd>{selectedPattern.detection_method}</dd>
                    {selectedPattern.detection_model && (
                      <>
                        <dt>Model:</dt>
                        <dd>{selectedPattern.detection_model}</dd>
                      </>
                    )}
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

                <div className="detail-section">
                  <h3>Description</h3>
                  <p>{selectedPattern.description}</p>
                </div>

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
                            <span className="match-source">{match.source_type}: {match.source_title || match.source_id}</span>
                            <span className={`confidence-badge ${getConfidenceBadge(match.match_score)}`}>
                              {(match.match_score * 100).toFixed(0)}%
                            </span>
                          </div>
                          {match.excerpt && (
                            <p className="match-excerpt">"{match.excerpt}"</p>
                          )}
                          <div className="match-meta">
                            <span>Matched: {formatDate(match.matched_at)}</span>
                            <span>By: {match.matched_by}</span>
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
    </div>
  );
}
