/**
 * ContradictionDetail - Detailed view of a single contradiction
 *
 * Shows side-by-side comparison with status management and notes.
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { useToast } from '../../context/ToastContext';

import * as api from './api';
import type { Contradiction, ContradictionStatus, Severity, ContradictionType } from './types';
import {
  STATUS_LABELS,
  STATUS_COLORS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
  TYPE_LABELS,
  TYPE_ICONS,
} from './types';

interface ContradictionDetailProps {
  contradictionId: string;
}

export function ContradictionDetail({ contradictionId }: ContradictionDetailProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();

  const [contradiction, setContradiction] = useState<Contradiction | null>(null);
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
      toast(`Status updated to ${STATUS_LABELS[status]}`, 'success');
      await fetchContradiction();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to update status', 'error');
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
      toast('Note added', 'success');
      setNoteText('');
      await fetchContradiction();
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to add note', 'error');
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
