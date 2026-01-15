/**
 * Deduplication Panel
 *
 * Shows duplicate detection status and actions for a document.
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import {
  useExactDuplicates,
  useSimilarDuplicates,
  useComputeHash,
  useMergeDuplicates,
} from './api';
import type { DuplicateResult, MergeRequest } from './api';
import './DeduplicationPanel.css';

interface DeduplicationPanelProps {
  documentId: string;
  onViewDocument?: (docId: string) => void;
  onRefresh?: () => void;
}

export function DeduplicationPanel({
  documentId,
  onViewDocument,
  onRefresh,
}: DeduplicationPanelProps) {
  const [showExact, setShowExact] = useState(true);
  const [showSimilar, setShowSimilar] = useState(true);
  const [similarThreshold, setSimilarThreshold] = useState(0.8);
  const [selectedDuplicates, setSelectedDuplicates] = useState<Set<string>>(new Set());
  const [mergeStrategy, setMergeStrategy] = useState<MergeRequest['strategy']>('soft_delete');

  const { computeHash, loading: hashLoading, error: hashError } = useComputeHash();
  const { merge, loading: mergeLoading } = useMergeDuplicates();

  const {
    data: exactDuplicates,
    loading: exactLoading,
    error: exactError,
    refetch: refetchExact,
  } = useExactDuplicates(documentId);

  const {
    data: similarDuplicates,
    loading: similarLoading,
    error: similarError,
    refetch: refetchSimilar,
  } = useSimilarDuplicates(documentId, similarThreshold);

  const handleComputeHash = useCallback(async () => {
    try {
      await computeHash(documentId);
      refetchExact();
      refetchSimilar();
      onRefresh?.();
    } catch {
      // Error handled by hook
    }
  }, [documentId, computeHash, refetchExact, refetchSimilar, onRefresh]);

  const toggleDuplicateSelection = useCallback((dupId: string) => {
    setSelectedDuplicates((prev) => {
      const next = new Set(prev);
      if (next.has(dupId)) {
        next.delete(dupId);
      } else {
        next.add(dupId);
      }
      return next;
    });
  }, []);

  const handleMerge = useCallback(async () => {
    if (selectedDuplicates.size === 0) return;

    try {
      await merge({
        source_ids: Array.from(selectedDuplicates),
        target_id: documentId,
        strategy: mergeStrategy,
      });
      setSelectedDuplicates(new Set());
      refetchExact();
      refetchSimilar();
      onRefresh?.();
    } catch {
      // Error handled by hook
    }
  }, [selectedDuplicates, documentId, mergeStrategy, merge, refetchExact, refetchSimilar, onRefresh]);

  const renderDuplicateList = (
    duplicates: DuplicateResult[] | undefined,
    loading: boolean,
    error: Error | null,
    type: 'exact' | 'similar'
  ) => {
    if (loading) {
      return (
        <div className="dedup-loading">
          <Icon name="Loader2" size={16} className="spin" />
          <span>Finding {type} duplicates...</span>
        </div>
      );
    }

    if (error) {
      return (
        <div className="dedup-error">
          <Icon name="AlertTriangle" size={16} />
          <span>{error.message}</span>
        </div>
      );
    }

    if (!duplicates || duplicates.length === 0) {
      return (
        <div className="dedup-empty">
          <Icon name="Check" size={16} />
          <span>No {type} duplicates found</span>
        </div>
      );
    }

    return (
      <div className="dedup-list">
        {duplicates.map((dup) => (
          <div key={dup.document_id} className="dedup-item">
            <input
              type="checkbox"
              checked={selectedDuplicates.has(dup.document_id)}
              onChange={() => toggleDuplicateSelection(dup.document_id)}
              className="dedup-checkbox"
            />
            <Icon name="FileText" size={16} />
            <div className="dedup-item-info">
              <div className="dedup-item-title">{dup.title}</div>
              <div className="dedup-item-meta">
                {type === 'exact' ? (
                  <span className="dedup-exact">Exact match (100%)</span>
                ) : (
                  <span className="dedup-similar">
                    {(dup.similarity_score * 100).toFixed(1)}% similar
                    (hamming: {dup.hamming_distance})
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={() => onViewDocument?.(dup.document_id)}
              className="btn-icon"
              title="View document"
            >
              <Icon name="Eye" size={16} />
            </button>
          </div>
        ))}
      </div>
    );
  };

  const totalDuplicates =
    (exactDuplicates?.length || 0) + (similarDuplicates?.length || 0);

  return (
    <div className="dedup-panel">
      {/* Header */}
      <div className="dedup-header">
        <div className="dedup-header-title">
          <Icon name="Copy" size={18} />
          <h3>Deduplication</h3>
          {totalDuplicates > 0 && (
            <span className="dedup-badge dedup-badge-warning">
              {totalDuplicates} found
            </span>
          )}
        </div>
        <button
          onClick={handleComputeHash}
          disabled={hashLoading}
          className="btn btn-secondary"
        >
          {hashLoading ? (
            <Icon name="Loader2" size={16} className="spin" />
          ) : (
            <Icon name="Hash" size={16} />
          )}
          Compute Hash
        </button>
      </div>

      {hashError && (
        <div className="dedup-alert dedup-alert-error">
          <Icon name="AlertTriangle" size={16} />
          <span>{hashError.message}</span>
        </div>
      )}

      {/* Exact Duplicates Section */}
      <div className="dedup-section">
        <button
          onClick={() => setShowExact(!showExact)}
          className="dedup-section-header"
        >
          <div className="dedup-section-title">
            <span>Exact Duplicates</span>
            {exactDuplicates && exactDuplicates.length > 0 && (
              <span className="dedup-badge dedup-badge-error">
                {exactDuplicates.length}
              </span>
            )}
          </div>
          <Icon name={showExact ? 'ChevronUp' : 'ChevronDown'} size={16} />
        </button>
        {showExact && renderDuplicateList(exactDuplicates ?? undefined, exactLoading, exactError, 'exact')}
      </div>

      {/* Similar Duplicates Section */}
      <div className="dedup-section">
        <button
          onClick={() => setShowSimilar(!showSimilar)}
          className="dedup-section-header"
        >
          <div className="dedup-section-title">
            <span>Similar Documents</span>
            {similarDuplicates && similarDuplicates.length > 0 && (
              <span className="dedup-badge dedup-badge-warning">
                {similarDuplicates.length}
              </span>
            )}
          </div>
          <Icon name={showSimilar ? 'ChevronUp' : 'ChevronDown'} size={16} />
        </button>
        {showSimilar && (
          <>
            <div className="dedup-threshold">
              <label>Similarity Threshold</label>
              <div className="dedup-threshold-control">
                <input
                  type="range"
                  min="0.5"
                  max="1"
                  step="0.05"
                  value={similarThreshold}
                  onChange={(e) => setSimilarThreshold(parseFloat(e.target.value))}
                />
                <span>{(similarThreshold * 100).toFixed(0)}%</span>
              </div>
            </div>
            {renderDuplicateList(similarDuplicates ?? undefined, similarLoading, similarError, 'similar')}
          </>
        )}
      </div>

      {/* Merge Actions */}
      {selectedDuplicates.size > 0 && (
        <div className="dedup-merge">
          <span className="dedup-merge-count">
            {selectedDuplicates.size} selected for merge
          </span>
          <select
            value={mergeStrategy}
            onChange={(e) => setMergeStrategy(e.target.value as MergeRequest['strategy'])}
            className="dedup-select"
          >
            <option value="soft_delete">Soft Delete</option>
            <option value="archive">Archive</option>
            <option value="permanent_delete">Permanent Delete</option>
          </select>
          <button
            onClick={handleMerge}
            disabled={mergeLoading}
            className="btn btn-primary"
          >
            {mergeLoading ? (
              <Icon name="Loader2" size={16} className="spin" />
            ) : (
              <Icon name="Merge" size={16} />
            )}
            Merge
          </button>
        </div>
      )}
    </div>
  );
}

export default DeduplicationPanel;
