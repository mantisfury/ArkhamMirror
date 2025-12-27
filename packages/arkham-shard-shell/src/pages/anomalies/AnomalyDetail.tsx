/**
 * AnomalyDetail - Detailed view of a single anomaly
 *
 * Provides full details, status management, and investigation tools.
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useToast } from '../../context/ToastContext';
import { useConfirm } from '../../context/ConfirmContext';
import { Icon } from '../../components/common/Icon';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

import * as api from './api';
import type { Anomaly, AnomalyStatus } from './types';
import {
  ANOMALY_TYPE_LABELS,
  ANOMALY_TYPE_ICONS,
  STATUS_LABELS,
  STATUS_OPTIONS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
} from './types';

// ============================================
// Main Component
// ============================================

export function AnomalyDetail({ anomalyId }: { anomalyId: string }) {
  const [_searchParams, setSearchParams] = useSearchParams();
  void _searchParams;
  const { toast } = useToast();
  const confirm = useConfirm();

  const [anomaly, setAnomaly] = useState<Anomaly | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Note dialog
  const [showNoteDialog, setShowNoteDialog] = useState(false);

  // Fetch anomaly data
  const fetchAnomaly = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getAnomaly(anomalyId);
      setAnomaly(response.anomaly);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load anomaly');
    } finally {
      setLoading(false);
    }
  }, [anomalyId]);

  useEffect(() => {
    fetchAnomaly();
  }, [fetchAnomaly]);

  const handleBack = () => {
    setSearchParams({});
  };

  const handleUpdateStatus = async (status: AnomalyStatus) => {
    if (!anomaly) return;

    const confirmed = await confirm({
      title: 'Update Status',
      message: `Change status to "${STATUS_LABELS[status]}"?`,
      confirmLabel: 'Update',
    });

    if (confirmed) {
      try {
        const response = await api.updateAnomalyStatus(
          anomaly.id,
          status,
          undefined,
          'analyst' // TODO: Get from user context
        );
        setAnomaly(response.anomaly);
        toast.success(`Status updated to ${STATUS_LABELS[status]}`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to update status');
      }
    }
  };

  const handleAddNote = async (content: string) => {
    if (!anomaly) return;

    try {
      await api.addNote(anomaly.id, content, 'analyst'); // TODO: Get from user context
      toast.success('Note added');
      setShowNoteDialog(false);
      fetchAnomaly();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add note');
    }
  };

  if (loading) {
    return (
      <div className="anomaly-detail-page">
        <LoadingSkeleton type="detail" />
      </div>
    );
  }

  if (error || !anomaly) {
    return (
      <div className="anomaly-detail-page">
        <div className="anomaly-error">
          <Icon name="AlertCircle" size={48} />
          <h2>Failed to load anomaly</h2>
          <p>{error || 'Anomaly not found'}</p>
          <div className="error-actions">
            <button className="btn btn-secondary" onClick={handleBack}>
              <Icon name="ArrowLeft" size={16} />
              Back to List
            </button>
            <button className="btn btn-primary" onClick={fetchAnomaly}>
              <Icon name="RefreshCw" size={16} />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="anomaly-detail-page">
      {/* Header */}
      <header className="page-header">
        <div className="page-title">
          <button className="btn btn-icon" onClick={handleBack} title="Back to list">
            <Icon name="ArrowLeft" size={20} />
          </button>
          <div>
            <h1>Anomaly Details</h1>
            <p className="page-description">
              {ANOMALY_TYPE_LABELS[anomaly.anomaly_type]} anomaly in {anomaly.doc_id}
            </p>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={() => setShowNoteDialog(true)}>
            <Icon name="MessageSquare" size={16} />
            Add Note
          </button>
        </div>
      </header>

      <div className="anomaly-detail-content">
        {/* Main Info Card */}
        <div className="detail-card">
          <div className="detail-card-header">
            <div className="detail-type">
              <Icon name={ANOMALY_TYPE_ICONS[anomaly.anomaly_type] as any} size={24} />
              <h2>{ANOMALY_TYPE_LABELS[anomaly.anomaly_type]}</h2>
            </div>
            <div className="detail-badges">
              <span
                className="badge badge-lg"
                style={{ backgroundColor: SEVERITY_COLORS[anomaly.severity] }}
              >
                {SEVERITY_LABELS[anomaly.severity]}
              </span>
            </div>
          </div>

          <div className="detail-explanation">
            <h3>Explanation</h3>
            <p>{anomaly.explanation}</p>
          </div>

          <div className="detail-metrics">
            <div className="metric">
              <label>Anomaly Score</label>
              <div className="metric-value">
                <div className="score-meter score-meter-lg">
                  <div
                    className="score-fill"
                    style={{
                      width: `${(anomaly.score / 10) * 100}%`,
                      backgroundColor: getSeverityColor(anomaly.score),
                    }}
                  />
                </div>
                <span className="score-value">{anomaly.score.toFixed(2)}</span>
              </div>
            </div>

            <div className="metric">
              <label>Confidence</label>
              <div className="metric-value">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${anomaly.confidence * 100}%` }}
                  />
                </div>
                <span>{(anomaly.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>

          {anomaly.field_name && (
            <div className="detail-field">
              <label>Affected Field</label>
              <code>{anomaly.field_name}</code>
            </div>
          )}

          {anomaly.expected_range && (
            <div className="detail-comparison">
              <div className="comparison-item">
                <label>Expected</label>
                <span>{anomaly.expected_range}</span>
              </div>
              <Icon name="ArrowRight" size={16} />
              <div className="comparison-item">
                <label>Actual</label>
                <span className="actual-value">{anomaly.actual_value}</span>
              </div>
            </div>
          )}
        </div>

        {/* Status Management */}
        <div className="detail-card">
          <h3>Status Management</h3>
          <div className="status-current">
            <label>Current Status</label>
            <span className={`badge badge-lg badge-${getStatusColor(anomaly.status)}`}>
              {STATUS_LABELS[anomaly.status]}
            </span>
          </div>

          <div className="status-actions">
            {STATUS_OPTIONS.map(opt => (
              <button
                key={opt.value}
                className={`btn btn-status ${anomaly.status === opt.value ? 'btn-status-active' : 'btn-secondary'}`}
                onClick={() => handleUpdateStatus(opt.value)}
                disabled={anomaly.status === opt.value}
              >
                <Icon name={getStatusIcon(opt.value)} size={16} />
                {opt.label}
              </button>
            ))}
          </div>

          {anomaly.reviewed_by && (
            <div className="status-review">
              <p>
                Reviewed by <strong>{anomaly.reviewed_by}</strong>
                {anomaly.reviewed_at && (
                  <> on {new Date(anomaly.reviewed_at).toLocaleString()}</>
                )}
              </p>
            </div>
          )}
        </div>

        {/* Source Document */}
        <div className="detail-card">
          <h3>Source Document</h3>
          <div className="document-link">
            <Icon name="FileText" size={20} />
            <div className="document-info">
              <span className="document-id">{anomaly.doc_id}</span>
              <button className="btn btn-link">
                View Document
                <Icon name="ExternalLink" size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* Technical Details */}
        {anomaly.details && Object.keys(anomaly.details).length > 0 && (
          <div className="detail-card">
            <h3>Technical Details</h3>
            <div className="detail-json">
              <pre>{JSON.stringify(anomaly.details, null, 2)}</pre>
            </div>
          </div>
        )}

        {/* Analyst Notes */}
        <div className="detail-card">
          <div className="card-header">
            <h3>Analyst Notes</h3>
            <button className="btn btn-sm btn-soft" onClick={() => setShowNoteDialog(true)}>
              <Icon name="Plus" size={14} />
              Add Note
            </button>
          </div>

          {anomaly.notes ? (
            <div className="notes-content">
              <p>{anomaly.notes}</p>
            </div>
          ) : (
            <p className="notes-empty">No notes yet. Add investigation notes or observations.</p>
          )}
        </div>

        {/* Tags */}
        {anomaly.tags && anomaly.tags.length > 0 && (
          <div className="detail-card">
            <h3>Tags</h3>
            <div className="tag-list">
              {anomaly.tags.map((tag, i) => (
                <span key={i} className="tag">
                  <Icon name="Tag" size={12} />
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Investigation Actions */}
        <div className="detail-card">
          <h3>Investigation Actions</h3>
          <div className="action-buttons">
            <button className="btn btn-soft">
              <Icon name="Search" size={16} />
              Find Similar Anomalies
            </button>
            <button className="btn btn-soft">
              <Icon name="BarChart3" size={16} />
              View Pattern Analysis
            </button>
            <button className="btn btn-soft">
              <Icon name="Clock" size={16} />
              View Timeline
            </button>
            <button className="btn btn-soft">
              <Icon name="FileText" size={16} />
              Export Report
            </button>
          </div>
        </div>

        {/* Metadata */}
        <div className="detail-card detail-metadata">
          <div className="metadata-item">
            <Icon name="Calendar" size={14} />
            <span>Detected {new Date(anomaly.detected_at).toLocaleString()}</span>
          </div>
          <div className="metadata-item">
            <Icon name="Clock" size={14} />
            <span>Updated {new Date(anomaly.updated_at).toLocaleString()}</span>
          </div>
          <div className="metadata-item">
            <Icon name="Hash" size={14} />
            <span>ID: {anomaly.id}</span>
          </div>
        </div>
      </div>

      {/* Add Note Dialog */}
      {showNoteDialog && (
        <AddNoteDialog
          onSubmit={handleAddNote}
          onCancel={() => setShowNoteDialog(false)}
        />
      )}
    </div>
  );
}

// ============================================
// Add Note Dialog
// ============================================

interface AddNoteDialogProps {
  onSubmit: (content: string) => void;
  onCancel: () => void;
}

function AddNoteDialog({ onSubmit, onCancel }: AddNoteDialogProps) {
  const [content, setContent] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (content.trim()) {
      onSubmit(content.trim());
    }
  };

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={e => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>Add Note</h2>
          <button className="btn btn-icon" onClick={onCancel}>
            <Icon name="X" size={20} />
          </button>
        </div>
        <p className="dialog-description">Add investigation notes or observations about this anomaly.</p>
        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label>Note Content</label>
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="Enter your notes here..."
              rows={6}
              autoFocus
            />
          </div>
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={!content.trim()}>
              <Icon name="Save" size={16} />
              Add Note
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================
// Helper Functions
// ============================================

function getSeverityColor(score: number): string {
  if (score >= 8) return 'var(--arkham-error)';
  if (score >= 5) return 'var(--arkham-warning)';
  if (score >= 3) return 'var(--arkham-info)';
  return 'var(--arkham-text-muted)';
}

function getStatusColor(status: AnomalyStatus): string {
  const colors: Record<AnomalyStatus, string> = {
    detected: 'blue',
    confirmed: 'red',
    dismissed: 'gray',
    false_positive: 'yellow',
  };
  return colors[status];
}

function getStatusIcon(status: AnomalyStatus): string {
  const icons: Record<AnomalyStatus, string> = {
    detected: 'Eye',
    confirmed: 'CheckCircle',
    dismissed: 'XCircle',
    false_positive: 'AlertCircle',
  };
  return icons[status];
}
