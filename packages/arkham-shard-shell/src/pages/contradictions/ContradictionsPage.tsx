/**
 * ContradictionsPage - Main contradictions list view
 *
 * Displays all detected contradictions with filtering and stats.
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { useToast } from '../../context/ToastContext';

import * as api from './api';
import type {
  ContradictionListItem,
  StatsResponse,
  ContradictionStatus,
  Severity,
  ContradictionType,
} from './types';
import {
  STATUS_LABELS,
  STATUS_COLORS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
  TYPE_LABELS,
  TYPE_ICONS,
  STATUS_OPTIONS,
  SEVERITY_OPTIONS,
  TYPE_OPTIONS,
} from './types';

export function ContradictionsPage() {
  const [searchParams, _setSearchParams] = useSearchParams();
  void _setSearchParams;
  const contradictionId = searchParams.get('id');

  // Show detail view if ID is set, otherwise show list
  if (contradictionId) {
    return <ContradictionDetailView contradictionId={contradictionId} />;
  }

  return <ContradictionListView />;
}

// ============================================
// Contradiction List View
// ============================================

function ContradictionListView() {
  const [_searchParams, setSearchParams] = useSearchParams();
  void _searchParams;
  const _toast = useToast();
  void _toast;

  const [contradictions, setContradictions] = useState<ContradictionListItem[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [listData, statsData] = await Promise.all([
        api.listContradictions(1, 100, statusFilter || undefined, severityFilter || undefined, typeFilter || undefined),
        api.getStats(),
      ]);
      setContradictions(listData.contradictions);
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load contradictions');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter, typeFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenContradiction = (id: string) => {
    setSearchParams({ id });
  };

  if (loading) {
    return (
      <div className="contradictions-page">
        <LoadingSkeleton type="list" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="contradictions-page">
        <div className="ach-error">
          <Icon name="AlertCircle" size={48} />
          <h2>Failed to load contradictions</h2>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={fetchData}>
            <Icon name="RefreshCw" size={16} />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="contradictions-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="AlertTriangle" size={28} />
          <div>
            <h1>Contradictions</h1>
            <p className="page-description">Detect and analyze contradictions across documents</p>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={fetchData}>
            <Icon name="RefreshCw" size={16} />
            Refresh
          </button>
        </div>
      </header>

      {/* Stats Summary */}
      {stats && (
        <section className="stats-grid">
          <div className="stat-card">
            <Icon name="AlertTriangle" size={24} className="stat-icon" />
            <div className="stat-content">
              <div className="stat-value">{stats.total_contradictions}</div>
              <div className="stat-label">Total</div>
            </div>
          </div>
          <div className="stat-card">
            <Icon name="Clock" size={24} className="stat-icon" style={{ color: 'var(--arkham-info)' }} />
            <div className="stat-content">
              <div className="stat-value">{stats.by_status.detected || 0}</div>
              <div className="stat-label">Pending Review</div>
            </div>
          </div>
          <div className="stat-card">
            <Icon name="CheckCircle" size={24} className="stat-icon" style={{ color: 'var(--arkham-error)' }} />
            <div className="stat-content">
              <div className="stat-value">{stats.by_status.confirmed || 0}</div>
              <div className="stat-label">Confirmed</div>
            </div>
          </div>
          <div className="stat-card">
            <Icon name="XCircle" size={24} className="stat-icon" style={{ color: 'var(--arkham-text-muted)' }} />
            <div className="stat-content">
              <div className="stat-value">{stats.by_status.dismissed || 0}</div>
              <div className="stat-label">Dismissed</div>
            </div>
          </div>
        </section>
      )}

      {/* Filters */}
      <section className="contradictions-filters">
        <div className="filter-group">
          <label htmlFor="status-filter">Status</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="filter-select"
          >
            <option value="">All Status</option>
            {STATUS_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="severity-filter">Severity</label>
          <select
            id="severity-filter"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="filter-select"
          >
            <option value="">All Severity</option>
            {SEVERITY_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label htmlFor="type-filter">Type</label>
          <select
            id="type-filter"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="filter-select"
          >
            <option value="">All Types</option>
            {TYPE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </section>

      {/* Contradictions List */}
      {contradictions.length === 0 ? (
        <div className="ach-empty">
          <Icon name="CheckCircle" size={64} />
          <h2>No Contradictions Found</h2>
          <p>No contradictions match the current filters.</p>
        </div>
      ) : (
        <div className="contradictions-list">
          {contradictions.map(contradiction => (
            <div
              key={contradiction.id}
              className="contradiction-card"
              onClick={() => handleOpenContradiction(contradiction.id)}
            >
              <div className="contradiction-header">
                <div className="contradiction-badges">
                  <span
                    className="badge"
                    style={{ backgroundColor: SEVERITY_COLORS[contradiction.severity as Severity] }}
                  >
                    {SEVERITY_LABELS[contradiction.severity as Severity]}
                  </span>
                  <span className="badge badge-outline">
                    <Icon name={TYPE_ICONS[contradiction.contradiction_type as ContradictionType]} size={12} />
                    {TYPE_LABELS[contradiction.contradiction_type as ContradictionType]}
                  </span>
                </div>
                <span
                  className="status-badge"
                  style={{ backgroundColor: STATUS_COLORS[contradiction.status as ContradictionStatus] }}
                >
                  {STATUS_LABELS[contradiction.status as ContradictionStatus]}
                </span>
              </div>

              <div className="contradiction-content">
                <div className="contradiction-claims">
                  <div className="claim-item">
                    <Icon name="FileText" size={14} />
                    <span className="claim-label">Claim A:</span>
                    <span className="claim-text">{contradiction.claim_a}</span>
                  </div>
                  <Icon name="ArrowRight" size={16} className="claim-arrow" />
                  <div className="claim-item">
                    <Icon name="FileText" size={14} />
                    <span className="claim-label">Claim B:</span>
                    <span className="claim-text">{contradiction.claim_b}</span>
                  </div>
                </div>

                {contradiction.explanation && (
                  <p className="contradiction-explanation">{contradiction.explanation}</p>
                )}

                <div className="contradiction-meta">
                  <span className="meta-item">
                    <Icon name="Link" size={12} />
                    {contradiction.doc_a_id} ↔ {contradiction.doc_b_id}
                  </span>
                  <span className="meta-item">
                    <Icon name="Activity" size={12} />
                    Confidence: {Math.round(contradiction.confidence_score * 100)}%
                  </span>
                  <span className="meta-item">
                    <Icon name="Clock" size={12} />
                    {new Date(contradiction.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// Contradiction Detail View
// ============================================

function ContradictionDetailView({ contradictionId }: { contradictionId: string }) {
  const [_searchParams, setSearchParams] = useSearchParams();
  void _searchParams;
  const { toast } = useToast();

  const [contradiction, setContradiction] = useState<ContradictionListItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchContradiction = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getContradiction(contradictionId);
      setContradiction(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load contradiction');
    } finally {
      setLoading(false);
    }
  }, [contradictionId]);

  useEffect(() => {
    fetchContradiction();
  }, [fetchContradiction]);

  const handleBack = () => {
    setSearchParams({});
  };

  const handleUpdateStatus = async (status: ContradictionStatus) => {
    if (!contradiction) return;
    setSubmitting(true);
    try {
      await api.updateStatus(contradiction.id, status);
      toast.success(`Status updated to ${STATUS_LABELS[status]}`);
      await fetchContradiction();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update status');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contradiction || !noteText.trim()) return;

    setSubmitting(true);
    try {
      await api.addNote(contradiction.id, noteText.trim());
      toast.success('Note added');
      setNoteText('');
      await fetchContradiction();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add note');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="contradictions-page">
        <LoadingSkeleton type="list" />
      </div>
    );
  }

  if (error || !contradiction) {
    return (
      <div className="contradictions-page">
        <div className="ach-error">
          <Icon name="AlertCircle" size={48} />
          <h2>Failed to load contradiction</h2>
          <p>{error || 'Contradiction not found'}</p>
          <div className="error-actions">
            <button className="btn btn-secondary" onClick={handleBack}>
              <Icon name="ArrowLeft" size={16} />
              Back to List
            </button>
            <button className="btn btn-primary" onClick={fetchContradiction}>
              <Icon name="RefreshCw" size={16} />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="contradictions-page contradiction-detail">
      <header className="page-header">
        <div className="page-title">
          <button className="btn btn-icon" onClick={handleBack} title="Back to list">
            <Icon name="ArrowLeft" size={20} />
          </button>
          <div>
            <h1>Contradiction Details</h1>
            <div className="contradiction-badges">
              <span
                className="badge"
                style={{ backgroundColor: SEVERITY_COLORS[contradiction.severity as Severity] }}
              >
                {SEVERITY_LABELS[contradiction.severity as Severity]}
              </span>
              <span className="badge badge-outline">
                <Icon name={TYPE_ICONS[contradiction.contradiction_type as ContradictionType]} size={12} />
                {TYPE_LABELS[contradiction.contradiction_type as ContradictionType]}
              </span>
              <span
                className="status-badge"
                style={{ backgroundColor: STATUS_COLORS[contradiction.status as ContradictionStatus] }}
              >
                {STATUS_LABELS[contradiction.status as ContradictionStatus]}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Status Actions */}
      <section className="status-actions">
        <h3>Update Status</h3>
        <div className="status-buttons">
          <button
            className="btn btn-secondary"
            onClick={() => handleUpdateStatus('confirmed')}
            disabled={submitting || contradiction.status === 'confirmed'}
          >
            <Icon name="CheckCircle" size={16} />
            Confirm
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleUpdateStatus('investigating')}
            disabled={submitting || contradiction.status === 'investigating'}
          >
            <Icon name="Search" size={16} />
            Investigate
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleUpdateStatus('dismissed')}
            disabled={submitting || contradiction.status === 'dismissed'}
          >
            <Icon name="XCircle" size={16} />
            Dismiss
          </button>
        </div>
      </section>

      {/* Side-by-Side Comparison */}
      <section className="contradiction-comparison">
        <div className="comparison-side">
          <div className="comparison-header">
            <Icon name="FileText" size={18} />
            <h3>Claim A</h3>
            <span className="badge badge-outline">{contradiction.doc_a_id}</span>
          </div>
          <div className="claim-content highlighted">
            <p>{contradiction.claim_a}</p>
          </div>
        </div>

        <div className="comparison-divider">
          <Icon name="ArrowLeftRight" size={24} />
        </div>

        <div className="comparison-side">
          <div className="comparison-header">
            <Icon name="FileText" size={18} />
            <h3>Claim B</h3>
            <span className="badge badge-outline">{contradiction.doc_b_id}</span>
          </div>
          <div className="claim-content highlighted">
            <p>{contradiction.claim_b}</p>
          </div>
        </div>
      </section>

      {/* Explanation */}
      {contradiction.explanation && (
        <section className="contradiction-explanation-section">
          <h3>
            <Icon name="Info" size={18} />
            Explanation
          </h3>
          <div className="explanation-content">
            <p>{contradiction.explanation}</p>
            <div className="explanation-meta">
              <span>Confidence: {Math.round(contradiction.confidence_score * 100)}%</span>
              <span>Detected: {new Date(contradiction.created_at).toLocaleString()}</span>
            </div>
          </div>
        </section>
      )}

      {/* Analyst Notes */}
      <section className="analyst-notes-section">
        <h3>
          <Icon name="MessageSquare" size={18} />
          Analyst Notes
        </h3>

        {contradiction.analyst_notes && contradiction.analyst_notes.length > 0 ? (
          <div className="notes-list">
            {contradiction.analyst_notes.map((note, idx) => (
              <div key={idx} className="note-item">
                <Icon name="FileText" size={14} />
                <p>{note}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="notes-empty">No notes yet</p>
        )}

        <form className="add-note-form" onSubmit={handleAddNote}>
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Add analysis notes..."
            rows={3}
            disabled={submitting}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting || !noteText.trim()}
          >
            {submitting ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Adding...
              </>
            ) : (
              <>
                <Icon name="Plus" size={16} />
                Add Note
              </>
            )}
          </button>
        </form>
      </section>
    </div>
  );
}
