/**
 * ContradictionsPage - Main contradictions list view
 *
 * Displays all detected contradictions with filtering, bulk actions, and stats.
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { AIAnalystButton } from '../../components/AIAnalyst';
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

import './ContradictionsPage.css';

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
  const { toast } = useToast();

  const [contradictions, setContradictions] = useState<ContradictionListItem[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');

  // Bulk Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);

  // Analysis Dialog
  const [showAnalyzeDialog, setShowAnalyzeDialog] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [listData, statsData] = await Promise.all([
        api.listContradictions(page, pageSize, statusFilter || undefined, severityFilter || undefined, typeFilter || undefined),
        api.getStats(),
      ]);
      setContradictions(listData.contradictions);
      setTotal(listData.total);
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load contradictions');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter, severityFilter, typeFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenContradiction = (id: string) => {
    setSearchParams({ id });
  };

  const handleClearFilters = () => {
    setStatusFilter('');
    setSeverityFilter('');
    setTypeFilter('');
    setPage(1);
  };

  // Bulk Selection Handlers
  const handleSelectAll = () => {
    if (selectedIds.size === contradictions.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(contradictions.map(c => c.id)));
    }
  };

  const handleSelectOne = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleBulkStatus = async (status: ContradictionStatus) => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      const result = await api.bulkUpdateStatus(Array.from(selectedIds), status);
      toast.success(`Updated ${result.updated} contradictions to ${STATUS_LABELS[status]}`);
      setSelectedIds(new Set());
      await fetchData();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Bulk update failed');
    } finally {
      setBulkLoading(false);
    }
  };

  // Pagination
  const totalPages = Math.ceil(total / pageSize);
  const hasNext = page < totalPages;
  const hasPrev = page > 1;

  if (loading && contradictions.length === 0) {
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
          <Icon name="Scale" size={28} />
          <div>
            <h1>Contradictions</h1>
            <p className="page-description">Detect and analyze contradictions across documents</p>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-primary" onClick={() => setShowAnalyzeDialog(true)}>
            <Icon name="Search" size={16} />
            Run Analysis
          </button>
          <button className="btn btn-secondary" onClick={fetchData}>
            <Icon name="RefreshCw" size={16} />
            Refresh
          </button>
          <AIAnalystButton
            shard="contradictions"
            targetId="overview"
            context={{
              statistics: stats || null,
              filters: {
                status: statusFilter || null,
                severity: severityFilter || null,
                type: typeFilter || null,
              },
              contradictions: contradictions.slice(0, 20).map(c => ({
                id: c.id,
                doc_a_id: c.doc_a_id,
                doc_b_id: c.doc_b_id,
                claim_a: c.claim_a,
                claim_b: c.claim_b,
                contradiction_type: c.contradiction_type,
                severity: c.severity,
                status: c.status,
                confidence_score: c.confidence_score,
              })),
              total_count: total,
            }}
            label="AI Analysis"
            variant="secondary"
            size="sm"
            disabled={contradictions.length === 0}
          />
        </div>
      </header>

      {/* Stats Summary */}
      {stats && (
        <section className="stats-grid">
          <div className="stat-card">
            <Icon name="Scale" size={24} className="stat-icon" />
            <div className="stat-content">
              <div className="stat-value">{stats.total_contradictions}</div>
              <div className="stat-label">Total</div>
            </div>
          </div>
          <div className="stat-card">
            <Icon name="Clock" size={24} className="stat-icon" style={{ color: 'var(--arkham-info)' }} />
            <div className="stat-content">
              <div className="stat-value">{(stats.by_status.detected || 0) + (stats.by_status.investigating || 0)}</div>
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
            <Icon name="GitBranch" size={24} className="stat-icon" style={{ color: 'var(--arkham-warning)' }} />
            <div className="stat-content">
              <div className="stat-value">{stats.chains_detected || 0}</div>
              <div className="stat-label">Chains</div>
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
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
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
            onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
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
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
            className="filter-select"
          >
            <option value="">All Types</option>
            {TYPE_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div className="filter-actions">
          {(statusFilter || severityFilter || typeFilter) && (
            <button className="btn btn-ghost" onClick={handleClearFilters}>
              <Icon name="X" size={14} />
              Clear Filters
            </button>
          )}
        </div>
      </section>

      {/* Bulk Actions Toolbar */}
      {selectedIds.size > 0 && (
        <section className="bulk-actions-toolbar">
          <div className="bulk-selection-info">
            <Icon name="CheckSquare" size={18} />
            <span>{selectedIds.size} selected</span>
          </div>
          {bulkLoading ? (
            <div className="bulk-loading">
              <Icon name="Loader2" size={18} className="spin" />
              <span>Updating...</span>
            </div>
          ) : (
            <div className="bulk-action-buttons">
              <button className="btn btn-sm btn-light" onClick={() => handleBulkStatus('confirmed')}>
                <Icon name="CheckCircle" size={14} />
                Confirm
              </button>
              <button className="btn btn-sm btn-light" onClick={() => handleBulkStatus('dismissed')}>
                <Icon name="XCircle" size={14} />
                Dismiss
              </button>
              <button className="btn btn-sm btn-light" onClick={() => handleBulkStatus('investigating')}>
                <Icon name="Search" size={14} />
                Investigate
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => setSelectedIds(new Set())}>
                <Icon name="X" size={14} />
                Clear
              </button>
            </div>
          )}
        </section>
      )}

      {/* Contradictions List */}
      {contradictions.length === 0 ? (
        <div className="ach-empty">
          <Icon name="CheckCircle" size={64} />
          <h2>No Contradictions Found</h2>
          <p>No contradictions match the current filters. Try running analysis on documents.</p>
          <button className="btn btn-primary" onClick={() => setShowAnalyzeDialog(true)}>
            <Icon name="Search" size={16} />
            Run Analysis
          </button>
        </div>
      ) : (
        <>
          {/* List Header with Select All */}
          <div className="contradictions-list-header">
            <label className="select-all-checkbox">
              <input
                type="checkbox"
                checked={selectedIds.size === contradictions.length && contradictions.length > 0}
                onChange={handleSelectAll}
              />
              <span>Select All ({contradictions.length})</span>
            </label>
          </div>

          <div className="contradictions-list">
            {contradictions.map(contradiction => (
              <div
                key={contradiction.id}
                className={`contradiction-card ${selectedIds.has(contradiction.id) ? 'selected' : ''}`}
                onClick={() => handleOpenContradiction(contradiction.id)}
              >
                <div
                  className="contradiction-checkbox"
                  onClick={(e) => handleSelectOne(contradiction.id, e)}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(contradiction.id)}
                    onChange={() => {}}
                  />
                </div>
                <div className="contradiction-main">
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
                        <span className="claim-text">{contradiction.claim_a}</span>
                      </div>
                      <Icon name="ArrowRight" size={16} className="claim-arrow" />
                      <div className="claim-item">
                        <Icon name="FileText" size={14} />
                        <span className="claim-text">{contradiction.claim_b}</span>
                      </div>
                    </div>

                    {contradiction.explanation && (
                      <p className="contradiction-explanation">{contradiction.explanation}</p>
                    )}

                    <div className="contradiction-meta">
                      <span className="meta-item">
                        <Icon name="Link" size={12} />
                        {contradiction.doc_a_id.slice(0, 8)} ↔ {contradiction.doc_b_id.slice(0, 8)}
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
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="contradictions-pagination">
              <button
                className="btn btn-secondary"
                onClick={() => setPage(p => p - 1)}
                disabled={!hasPrev}
              >
                <Icon name="ChevronLeft" size={16} />
                Previous
              </button>
              <span className="pagination-info">
                Page {page} of {totalPages} ({total} total)
              </span>
              <button
                className="btn btn-secondary"
                onClick={() => setPage(p => p + 1)}
                disabled={!hasNext}
              >
                Next
                <Icon name="ChevronRight" size={16} />
              </button>
            </div>
          )}
        </>
      )}

      {/* Analysis Dialog */}
      {showAnalyzeDialog && (
        <AnalyzeDialog
          onClose={() => setShowAnalyzeDialog(false)}
          onComplete={() => {
            setShowAnalyzeDialog(false);
            fetchData();
          }}
        />
      )}
    </div>
  );
}

// ============================================
// Analysis Dialog - Multi-Document Selection
// ============================================

interface AnalyzeDialogProps {
  onClose: () => void;
  onComplete: () => void;
}

function AnalyzeDialog({ onClose, onComplete }: AnalyzeDialogProps) {
  const { toast } = useToast();
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [threshold, setThreshold] = useState(0.7);
  const [useLLM, setUseLLM] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [documents, setDocuments] = useState<Array<{ id: string; filename: string; title: string; status: string }>>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [progress, setProgress] = useState({ current: 0, total: 0, found: 0 });
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    // Fetch available documents from the correct endpoint
    const loadDocuments = async () => {
      try {
        console.log('Fetching documents from /api/documents/items...');
        const data = await api.fetchDocuments(1, 100);
        console.log('Received data:', data);
        // Only include processed documents
        const processedDocs = (data.items || []).filter(
          (doc: { status: string }) => doc.status === 'processed' || doc.status === 'indexed'
        );
        console.log('Filtered to', processedDocs.length, 'processed documents');
        setDocuments(processedDocs);
      } catch (err) {
        console.error('Failed to fetch documents:', err);
      } finally {
        setLoadingDocs(false);
      }
    };
    loadDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Filter documents by search query
  const filteredDocuments = documents.filter(doc => {
    const query = searchQuery.toLowerCase();
    return doc.filename.toLowerCase().includes(query) ||
           (doc.title && doc.title.toLowerCase().includes(query));
  });

  // Generate all unique pairs from selected documents
  const generatePairs = (docIds: string[]): Array<[string, string]> => {
    const pairs: Array<[string, string]> = [];
    for (let i = 0; i < docIds.length; i++) {
      for (let j = i + 1; j < docIds.length; j++) {
        pairs.push([docIds[i], docIds[j]]);
      }
    }
    return pairs;
  };

  const handleToggleDocument = (docId: string) => {
    const newSelected = new Set(selectedDocIds);
    if (newSelected.has(docId)) {
      newSelected.delete(docId);
    } else {
      newSelected.add(docId);
    }
    setSelectedDocIds(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedDocIds.size === filteredDocuments.length) {
      setSelectedDocIds(new Set());
    } else {
      setSelectedDocIds(new Set(filteredDocuments.map(d => d.id)));
    }
  };

  const handleAnalyze = async () => {
    if (selectedDocIds.size < 2) {
      toast.error('Please select at least 2 documents to compare');
      return;
    }

    const docIds = Array.from(selectedDocIds);
    const pairs = generatePairs(docIds);

    setAnalyzing(true);
    setProgress({ current: 0, total: pairs.length, found: 0 });

    try {
      // Use batch API for efficiency
      const result = await api.batchAnalyze(pairs, threshold, useLLM);

      setProgress({ current: pairs.length, total: pairs.length, found: result.count });

      if (result.count > 0) {
        toast.success(`Analysis complete! Found ${result.count} contradictions across ${pairs.length} document pairs`);
      } else {
        toast.info(`No contradictions found across ${pairs.length} document pairs`);
      }
      onComplete();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const pairCount = selectedDocIds.size >= 2
    ? (selectedDocIds.size * (selectedDocIds.size - 1)) / 2
    : 0;

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog dialog-large" onClick={e => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>
            <Icon name="Search" size={20} />
            Cross-Examine Documents for Contradictions
          </h2>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={18} />
          </button>
        </div>

        <div className="dialog-body">
          {/* Document Selection */}
          <div className="form-field">
            <label>
              Select Documents to Cross-Examine
              <span className="label-hint">
                ({selectedDocIds.size} selected = {pairCount} pairs to analyze)
              </span>
            </label>

            {/* Search Filter */}
            <div className="document-search">
              <Icon name="Search" size={16} />
              <input
                type="text"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button className="btn btn-icon btn-sm" onClick={() => setSearchQuery('')}>
                  <Icon name="X" size={14} />
                </button>
              )}
            </div>

            {loadingDocs ? (
              <div className="document-list-loading">
                <Icon name="Loader2" size={24} className="spin" />
                <span>Loading documents...</span>
              </div>
            ) : documents.length === 0 ? (
              <div className="document-list-empty">
                <Icon name="FileText" size={32} />
                <p>No processed documents found. Please ingest and process documents first.</p>
              </div>
            ) : (
              <>
                {/* Select All */}
                <div className="document-select-all">
                  <label className="document-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedDocIds.size === filteredDocuments.length && filteredDocuments.length > 0}
                      onChange={handleSelectAll}
                    />
                    <span>Select All ({filteredDocuments.length} documents)</span>
                  </label>
                </div>

                {/* Document List */}
                <div className="document-checklist">
                  {filteredDocuments.map(doc => (
                    <label
                      key={doc.id}
                      className={`document-checkbox ${selectedDocIds.has(doc.id) ? 'selected' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocIds.has(doc.id)}
                        onChange={() => handleToggleDocument(doc.id)}
                      />
                      <Icon name="FileText" size={16} />
                      <span className="document-name">{doc.filename}</span>
                      {doc.title && doc.title !== doc.filename && (
                        <span className="document-title">({doc.title})</span>
                      )}
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Analysis Settings */}
          <div className="form-field">
            <label>Similarity Threshold: {(threshold * 100).toFixed(0)}%</label>
            <input
              type="range"
              min="0.5"
              max="0.95"
              step="0.05"
              value={threshold}
              onChange={e => setThreshold(parseFloat(e.target.value))}
            />
            <p className="form-hint">
              Higher threshold = stricter matching. Lower = more potential contradictions found.
            </p>
          </div>

          <div className="form-field">
            <div className="checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={useLLM}
                  onChange={e => setUseLLM(e.target.checked)}
                />
                <span>Use LLM for claim extraction and verification (more accurate but slower)</span>
              </label>
            </div>
          </div>

          {/* Progress */}
          {analyzing && (
            <div className="analysis-progress">
              <div className="progress-header">
                <Icon name="Loader2" size={18} className="spin" />
                <span>Analyzing {pairCount} document pairs...</span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%` }}
                />
              </div>
              <div className="progress-stats">
                <span>Progress: {progress.current} / {progress.total} pairs</span>
                <span>Contradictions found: {progress.found}</span>
              </div>
            </div>
          )}
        </div>

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={analyzing}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleAnalyze}
            disabled={analyzing || selectedDocIds.size < 2}
          >
            {analyzing ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Icon name="Search" size={16} />
                Analyze {pairCount > 0 ? `${pairCount} Pairs` : ''}
              </>
            )}
          </button>
        </div>
      </div>
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
  const [chains, setChains] = useState<Array<{ id: string; description: string; contradiction_count: number }>>([]);

  const fetchContradiction = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, chainsData] = await Promise.all([
        api.getContradiction(contradictionId),
        api.listChains(),
      ]);
      setContradiction(data);
      setChains(chainsData.chains || []);
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

  const handleDetectChains = async () => {
    setSubmitting(true);
    try {
      const result = await api.detectChains();
      if (result.chains_detected > 0) {
        toast.success(`Detected ${result.chains_detected} contradiction chains`);
        await fetchContradiction();
      } else {
        toast.info('No new chains detected');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to detect chains');
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
            <span className="badge badge-outline">{contradiction.doc_a_id.slice(0, 8)}...</span>
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
            <span className="badge badge-outline">{contradiction.doc_b_id.slice(0, 8)}...</span>
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

      {/* Chains Section */}
      <section className="chain-section">
        <h3>
          <Icon name="GitBranch" size={18} />
          Contradiction Chains
        </h3>
        {chains.length > 0 ? (
          <div className="chain-list">
            {chains.map(chain => (
              <div key={chain.id} className="chain-item">
                <Icon name="Link" size={16} />
                <div className="chain-info">
                  <p className="chain-description">{chain.description}</p>
                  <p className="chain-meta">{chain.contradiction_count} contradictions in chain</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="notes-empty">No chains detected yet</p>
        )}
        <button
          className="btn btn-secondary"
          onClick={handleDetectChains}
          disabled={submitting}
          style={{ marginTop: '1rem' }}
        >
          <Icon name="Search" size={16} />
          Detect Chains
        </button>
      </section>

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
