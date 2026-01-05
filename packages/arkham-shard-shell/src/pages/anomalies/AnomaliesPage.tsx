/**
 * AnomaliesPage - Anomaly Detection and Analysis
 *
 * Main page for viewing and managing detected anomalies.
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useToast } from '../../context/ToastContext';
import { Icon } from '../../components/common/Icon';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { AnomalyDetail } from './AnomalyDetail';

import * as api from './api';
import './AnomaliesPage.css';
import type {
  Anomaly,
  DetectionConfig,
} from './types';
import {
  ANOMALY_TYPE_LABELS,
  ANOMALY_TYPE_ICONS,
  STATUS_LABELS,
  STATUS_COLORS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
  ANOMALY_TYPE_OPTIONS,
  STATUS_OPTIONS,
  SEVERITY_OPTIONS,
} from './types';

// ============================================
// Main Page Component
// ============================================

export function AnomaliesPage() {
  const [searchParams, _setSearchParams] = useSearchParams();
  void _setSearchParams;
  const anomalyId = searchParams.get('anomalyId');

  // Show detail view if anomalyId is set
  if (anomalyId) {
    return <AnomalyDetailView anomalyId={anomalyId} />;
  }

  return <AnomaliesListView />;
}

// ============================================
// List View
// ============================================

function AnomaliesListView() {
  const [_searchParams, setSearchParams] = useSearchParams();
  void _searchParams;
  const { toast } = useToast();

  // State
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkActionLoading, setBulkActionLoading] = useState(false);

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [minSeverity, setMinSeverity] = useState<number>(0);
  const [maxSeverity, setMaxSeverity] = useState<number>(10);

  // Detection dialog
  const [showDetectDialog, setShowDetectDialog] = useState(false);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const response = await api.getStats();
      setStats(response.stats);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, []);

  // Fetch anomalies
  const fetchAnomalies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.listAnomalies({
        offset,
        limit: 20,
        anomaly_type: typeFilter || undefined,
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
      });
      setAnomalies(response.items);
      setHasMore(response.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load anomalies');
    } finally {
      setLoading(false);
    }
  }, [offset, typeFilter, statusFilter, severityFilter]);

  useEffect(() => {
    fetchStats();
    fetchAnomalies();
  }, [fetchStats, fetchAnomalies]);

  // Reset offset when filters change
  useEffect(() => {
    setOffset(0);
  }, [typeFilter, statusFilter, severityFilter]);

  // Filter anomalies by score (client-side)
  const filteredAnomalies = anomalies.filter(
    a => a.score >= minSeverity && a.score <= maxSeverity
  );

  const handleOpenAnomaly = (anomalyId: string) => {
    setSearchParams({ anomalyId });
  };

  const handleRunDetection = () => {
    setShowDetectDialog(true);
  };

  const handleClearFilters = () => {
    setTypeFilter('');
    setStatusFilter('');
    setSeverityFilter('');
    setMinSeverity(0);
    setMaxSeverity(10);
  };

  // Bulk selection handlers
  const toggleSelection = (anomalyId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(anomalyId)) {
        next.delete(anomalyId);
      } else {
        next.add(anomalyId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredAnomalies.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredAnomalies.map(a => a.id)));
    }
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
  };

  const handleBulkAction = async (status: string) => {
    if (selectedIds.size === 0) return;

    setBulkActionLoading(true);
    try {
      const result = await api.bulkUpdateStatus(
        Array.from(selectedIds),
        status,
        '',
        'user'
      );

      if (result.success) {
        toast.success(`Updated ${result.updated_count} anomalies to "${status}"`);
        if (result.failed_count > 0) {
          toast.warning(`Failed to update ${result.failed_count} anomalies`);
        }
        setSelectedIds(new Set());
        fetchAnomalies();
        fetchStats();
      } else {
        toast.error('Failed to update anomalies');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update anomalies');
    } finally {
      setBulkActionLoading(false);
    }
  };

  if (loading && anomalies.length === 0) {
    return (
      <div className="anomalies-page">
        <LoadingSkeleton type="list" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="anomalies-page">
        <div className="anomalies-error">
          <Icon name="AlertCircle" size={48} />
          <h2>Failed to load anomalies</h2>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={fetchAnomalies}>
            <Icon name="RefreshCw" size={16} />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="anomalies-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="AlertTriangle" size={28} />
          <div>
            <h1>Anomaly Detection</h1>
            <p className="page-description">Detect and investigate unusual patterns in documents</p>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-primary" onClick={handleRunDetection}>
            <Icon name="Zap" size={16} />
            Run Detection
          </button>
        </div>
      </header>

      {/* Stats Dashboard */}
      {stats && (
        <div className="anomalies-stats">
          <div className="stat-card">
            <div className="stat-icon">
              <Icon name="AlertTriangle" size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{stats.total_anomalies}</div>
              <div className="stat-label">Total Anomalies</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon stat-icon-red">
              <Icon name="CheckCircle" size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{stats.by_status?.confirmed || 0}</div>
              <div className="stat-label">Confirmed</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon stat-icon-blue">
              <Icon name="Clock" size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{stats.detected_last_24h}</div>
              <div className="stat-label">Last 24h</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon stat-icon-yellow">
              <Icon name="TrendingDown" size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{(stats.false_positive_rate * 100).toFixed(1)}%</div>
              <div className="stat-label">False Positive Rate</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon stat-icon-green">
              <Icon name="Target" size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{(stats.avg_confidence * 100).toFixed(0)}%</div>
              <div className="stat-label">Avg Confidence</div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="anomalies-filters">
        <div className="filter-group">
          <label>Type</label>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">All Types</option>
            {ANOMALY_TYPE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All Statuses</option>
            {STATUS_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Severity</label>
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
            <option value="">All Severities</option>
            {SEVERITY_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-group filter-group-range">
          <label>Score Range: {minSeverity.toFixed(1)} - {maxSeverity.toFixed(1)}</label>
          <div className="range-inputs">
            <input
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={minSeverity}
              onChange={(e) => setMinSeverity(Number(e.target.value))}
            />
            <input
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={maxSeverity}
              onChange={(e) => setMaxSeverity(Number(e.target.value))}
            />
          </div>
        </div>

        <button className="btn btn-sm btn-secondary" onClick={handleClearFilters}>
          <Icon name="X" size={14} />
          Clear
        </button>
      </div>

      {/* Bulk Actions Toolbar */}
      {selectedIds.size > 0 && (
        <div className="bulk-actions-toolbar">
          <div className="bulk-selection-info">
            <Icon name="CheckSquare" size={16} />
            <span>{selectedIds.size} selected</span>
          </div>
          <div className="bulk-action-buttons">
            <button
              className="btn btn-sm btn-success"
              onClick={() => handleBulkAction('confirmed')}
              disabled={bulkActionLoading}
            >
              <Icon name="CheckCircle" size={14} />
              Confirm Selected
            </button>
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => handleBulkAction('dismissed')}
              disabled={bulkActionLoading}
            >
              <Icon name="XCircle" size={14} />
              Dismiss Selected
            </button>
            <button
              className="btn btn-sm btn-warning"
              onClick={() => handleBulkAction('false_positive')}
              disabled={bulkActionLoading}
            >
              <Icon name="AlertTriangle" size={14} />
              Mark as False Positive
            </button>
            <button
              className="btn btn-sm btn-ghost"
              onClick={clearSelection}
              disabled={bulkActionLoading}
            >
              <Icon name="X" size={14} />
              Clear Selection
            </button>
          </div>
          {bulkActionLoading && (
            <div className="bulk-loading">
              <Icon name="Loader2" size={16} className="spin" />
            </div>
          )}
        </div>
      )}

      {/* Anomaly List */}
      {filteredAnomalies.length === 0 ? (
        <div className="anomalies-empty">
          <Icon name="Search" size={64} />
          <h2>No Anomalies Found</h2>
          <p>Run detection to find anomalies in your documents, or adjust your filters.</p>
          <button className="btn btn-primary" onClick={handleRunDetection}>
            <Icon name="Zap" size={16} />
            Run Detection
          </button>
        </div>
      ) : (
        <div className="anomalies-list">
          {/* Select All Header */}
          <div className="anomalies-list-header">
            <label className="select-all-checkbox" onClick={(e) => e.stopPropagation()}>
              <input
                type="checkbox"
                checked={selectedIds.size === filteredAnomalies.length && filteredAnomalies.length > 0}
                onChange={toggleSelectAll}
              />
              <span>Select All ({filteredAnomalies.length})</span>
            </label>
          </div>

          {filteredAnomalies.map(anomaly => (
            <div
              key={anomaly.id}
              className={`anomaly-card ${selectedIds.has(anomaly.id) ? 'selected' : ''}`}
              onClick={() => handleOpenAnomaly(anomaly.id)}
            >
              <div className="anomaly-header">
                <div className="anomaly-checkbox" onClick={(e) => toggleSelection(anomaly.id, e)}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(anomaly.id)}
                    onChange={() => {}}
                  />
                </div>
                <div className="anomaly-type">
                  <Icon name={ANOMALY_TYPE_ICONS[anomaly.anomaly_type] as any} size={20} />
                  <span>{ANOMALY_TYPE_LABELS[anomaly.anomaly_type]}</span>
                </div>
                <div className="anomaly-badges">
                  <span className={`badge badge-${STATUS_COLORS[anomaly.status]}`}>
                    {STATUS_LABELS[anomaly.status]}
                  </span>
                  <span
                    className="badge"
                    style={{ backgroundColor: SEVERITY_COLORS[anomaly.severity] }}
                  >
                    {SEVERITY_LABELS[anomaly.severity]}
                  </span>
                </div>
              </div>

              <div className="anomaly-content">
                <p className="anomaly-explanation">{anomaly.explanation}</p>
                <div className="anomaly-meta">
                  <span className="anomaly-doc">
                    <Icon name="FileText" size={14} />
                    {anomaly.doc_id}
                  </span>
                  {anomaly.field_name && (
                    <span className="anomaly-field">
                      <Icon name="Tag" size={14} />
                      {anomaly.field_name}
                    </span>
                  )}
                </div>
              </div>

              <div className="anomaly-footer">
                <div className="anomaly-score">
                  <div className="score-meter">
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
                <span className="anomaly-confidence">
                  {(anomaly.confidence * 100).toFixed(0)}% confidence
                </span>
                <span className="anomaly-date">
                  {new Date(anomaly.detected_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {(offset > 0 || hasMore) && (
        <div className="anomalies-pagination">
          <button
            className="btn btn-secondary"
            onClick={() => setOffset(Math.max(0, offset - 20))}
            disabled={offset === 0}
          >
            <Icon name="ChevronLeft" size={16} />
            Previous
          </button>
          <span className="pagination-info">
            Showing {offset + 1} - {offset + filteredAnomalies.length}
          </span>
          <button
            className="btn btn-secondary"
            onClick={() => setOffset(offset + 20)}
            disabled={!hasMore}
          >
            Next
            <Icon name="ChevronRight" size={16} />
          </button>
        </div>
      )}

      {/* Detection Dialog */}
      {showDetectDialog && (
        <DetectionDialog
          onSubmit={async (config) => {
            try {
              const result = await api.detectAnomalies({ config });
              toast.success(`Detection started - ${result.anomalies_detected} anomalies found`);
              setShowDetectDialog(false);
              fetchAnomalies();
              fetchStats();
            } catch (err) {
              toast.error(err instanceof Error ? err.message : 'Failed to run detection');
            }
          }}
          onCancel={() => setShowDetectDialog(false)}
        />
      )}
    </div>
  );
}

// ============================================
// Detail View (placeholder - see AnomalyDetail.tsx)
// ============================================

function AnomalyDetailView({ anomalyId }: { anomalyId: string }) {
  return <AnomalyDetail anomalyId={anomalyId} />;
}

// ============================================
// Detection Dialog
// ============================================

interface DetectionDialogProps {
  onSubmit: (config: Partial<DetectionConfig>) => void;
  onCancel: () => void;
}

function DetectionDialog({ onSubmit, onCancel }: DetectionDialogProps) {
  const [config, setConfig] = useState<Partial<DetectionConfig>>({
    detect_content: true,
    detect_metadata: true,
    detect_temporal: true,
    detect_structural: true,
    detect_statistical: true,
    detect_red_flags: true,
    z_score_threshold: 3.0,
    min_confidence: 0.5,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(config);
  };

  const toggleDetectionType = (key: keyof DetectionConfig) => {
    setConfig(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog dialog-lg" onClick={e => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>Run Anomaly Detection</h2>
          <button className="btn btn-icon" onClick={onCancel}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-section">
            <h3>Detection Types</h3>
            <div className="checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={config.detect_content ?? true}
                  onChange={() => toggleDetectionType('detect_content')}
                />
                Content Anomalies (semantically distant documents)
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={config.detect_metadata ?? true}
                  onChange={() => toggleDetectionType('detect_metadata')}
                />
                Metadata Anomalies (unusual file properties)
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={config.detect_temporal ?? true}
                  onChange={() => toggleDetectionType('detect_temporal')}
                />
                Temporal Anomalies (unexpected dates)
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={config.detect_structural ?? true}
                  onChange={() => toggleDetectionType('detect_structural')}
                />
                Structural Anomalies (unusual document structure)
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={config.detect_statistical ?? true}
                  onChange={() => toggleDetectionType('detect_statistical')}
                />
                Statistical Anomalies (unusual text patterns)
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={config.detect_red_flags ?? true}
                  onChange={() => toggleDetectionType('detect_red_flags')}
                />
                Red Flags (sensitive content indicators)
              </label>
            </div>
          </div>

          <div className="form-section">
            <h3>Detection Parameters</h3>
            <div className="form-field">
              <label>Z-Score Threshold: {config.z_score_threshold?.toFixed(1)}</label>
              <input
                type="range"
                min="1"
                max="5"
                step="0.1"
                value={config.z_score_threshold ?? 3.0}
                onChange={(e) => setConfig(prev => ({ ...prev, z_score_threshold: Number(e.target.value) }))}
              />
              <p className="form-hint">Higher values = stricter detection (fewer anomalies)</p>
            </div>

            <div className="form-field">
              <label>Minimum Confidence: {((config.min_confidence ?? 0.5) * 100).toFixed(0)}%</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={config.min_confidence ?? 0.5}
                onChange={(e) => setConfig(prev => ({ ...prev, min_confidence: Number(e.target.value) }))}
              />
            </div>
          </div>

          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              <Icon name="Zap" size={16} />
              Run Detection
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
