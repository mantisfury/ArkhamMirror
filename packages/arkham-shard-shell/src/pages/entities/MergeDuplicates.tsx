/**
 * MergeDuplicates - Find and merge duplicate entities
 *
 * Displays potential duplicate entities and allows users to merge them.
 */

import { useState } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { apiPost } from '../../utils/api';
import './MergeDuplicates.css';

interface EntityInfo {
  id: string;
  name: string;
  entity_type: string;
}

interface MergeCandidate {
  entity_a: EntityInfo;
  entity_b: EntityInfo;
  similarity_score: number;
  reason: string;
  common_mentions: number;
  common_documents: number;
}

interface MergeDuplicatesProps {
  onMergeComplete?: () => void;
}

const ENTITY_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'PERSON', label: 'Person' },
  { value: 'ORGANIZATION', label: 'Organization' },
  { value: 'LOCATION', label: 'Location' },
  { value: 'DATE', label: 'Date' },
  { value: 'EVENT', label: 'Event' },
  { value: 'PRODUCT', label: 'Product' },
  { value: 'OTHER', label: 'Other' },
];

export function MergeDuplicates({ onMergeComplete }: MergeDuplicatesProps) {
  const { toast } = useToast();
  const [typeFilter, setTypeFilter] = useState('');
  const [threshold, setThreshold] = useState(0.8);
  const [selectedPairs, setSelectedPairs] = useState<Set<string>>(new Set());
  const [merging, setMerging] = useState(false);
  const [confirmMerge, setConfirmMerge] = useState<MergeCandidate | null>(null);

  // Build URL with params
  const duplicatesUrl = `/api/entities/duplicates?threshold=${threshold}${typeFilter ? `&entity_type=${typeFilter}` : ''}`;

  // Fetch duplicates
  const { data: duplicates, loading, error, refetch } = useFetch<MergeCandidate[]>(duplicatesUrl);

  const getPairKey = (candidate: MergeCandidate) =>
    `${candidate.entity_a.id}-${candidate.entity_b.id}`;

  const togglePairSelection = (candidate: MergeCandidate) => {
    const key = getPairKey(candidate);
    const newSelected = new Set(selectedPairs);
    if (newSelected.has(key)) {
      newSelected.delete(key);
    } else {
      newSelected.add(key);
    }
    setSelectedPairs(newSelected);
  };

  const handleMerge = async (candidate: MergeCandidate, canonicalId: string) => {
    setMerging(true);
    setConfirmMerge(null);

    try {
      await apiPost('/api/entities/merge', {
        entity_ids: [candidate.entity_a.id, candidate.entity_b.id],
        canonical_id: canonicalId,
      });

      toast.success('Entities merged successfully');

      // Remove from selection and refetch
      const key = getPairKey(candidate);
      const newSelected = new Set(selectedPairs);
      newSelected.delete(key);
      setSelectedPairs(newSelected);

      refetch();
      onMergeComplete?.();

    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Merge failed');
    } finally {
      setMerging(false);
    }
  };

  const handleBatchMerge = async () => {
    if (selectedPairs.size === 0) return;

    setMerging(true);

    try {
      // For each selected pair, merge keeping entity_a as canonical
      const pairsToMerge = duplicates?.filter(d => selectedPairs.has(getPairKey(d))) || [];

      for (const pair of pairsToMerge) {
        await apiPost('/api/entities/merge', {
          entity_ids: [pair.entity_a.id, pair.entity_b.id],
          canonical_id: pair.entity_a.id, // Keep first entity as canonical
        });
      }

      toast.success(`Merged ${pairsToMerge.length} entity pairs`);

      setSelectedPairs(new Set());
      refetch();
      onMergeComplete?.();

    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Batch merge failed');
    } finally {
      setMerging(false);
    }
  };

  const getSimilarityColor = (score: number) => {
    if (score >= 0.95) return 'similarity-high';
    if (score >= 0.85) return 'similarity-medium';
    return 'similarity-low';
  };

  const getTypeIcon = (entityType: string) => {
    const icons: Record<string, string> = {
      PERSON: 'User',
      ORGANIZATION: 'Building',
      LOCATION: 'MapPin',
      DATE: 'Calendar',
      EVENT: 'Sparkles',
      PRODUCT: 'Package',
      DOCUMENT: 'FileText',
      CONCEPT: 'Lightbulb',
      OTHER: 'Tag',
    };
    return icons[entityType] || 'Tag';
  };

  return (
    <div className="merge-duplicates">
      {/* Controls */}
      <div className="merge-controls">
        <div className="control-group">
          <label>Entity Type</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="type-select"
          >
            {ENTITY_TYPES.map(type => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>Similarity Threshold</label>
          <div className="threshold-control">
            <input
              type="range"
              min="0.5"
              max="1"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
            />
            <span className="threshold-value">{Math.round(threshold * 100)}%</span>
          </div>
        </div>

        <button
          className="btn btn-secondary"
          onClick={() => refetch()}
          disabled={loading}
        >
          <Icon name="RefreshCw" size={16} className={loading ? 'spin' : ''} />
          Refresh
        </button>

        {selectedPairs.size > 0 && (
          <button
            className="btn btn-primary"
            onClick={handleBatchMerge}
            disabled={merging}
          >
            <Icon name="Merge" size={16} />
            Merge {selectedPairs.size} Selected
          </button>
        )}
      </div>

      {/* Duplicates List */}
      <div className="duplicates-list">
        {loading ? (
          <div className="duplicates-loading">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Finding duplicates...</span>
          </div>
        ) : error ? (
          <div className="duplicates-error">
            <Icon name="AlertCircle" size={32} />
            <span>Failed to load duplicates</span>
            <button className="btn btn-secondary" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        ) : duplicates && duplicates.length > 0 ? (
          <>
            <div className="duplicates-header">
              <span className="duplicates-count">
                Found {duplicates.length} potential duplicate pairs
              </span>
            </div>

            <div className="duplicate-cards">
              {duplicates.map((candidate) => {
                const key = getPairKey(candidate);
                const isSelected = selectedPairs.has(key);

                return (
                  <div
                    key={key}
                    className={`duplicate-card ${isSelected ? 'selected' : ''}`}
                  >
                    <div className="duplicate-header">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => togglePairSelection(candidate)}
                        className="select-checkbox"
                      />
                      <span className={`similarity-badge ${getSimilarityColor(candidate.similarity_score)}`}>
                        {Math.round(candidate.similarity_score * 100)}% match
                      </span>
                      <span className="entity-type-badge">
                        <Icon name={getTypeIcon(candidate.entity_a.entity_type)} size={12} />
                        {candidate.entity_a.entity_type}
                      </span>
                    </div>

                    <div className="duplicate-entities">
                      <div className="entity-box">
                        <div className="entity-name">{candidate.entity_a.name}</div>
                        <button
                          className="btn btn-sm btn-outline keep-btn"
                          onClick={() => setConfirmMerge(candidate)}
                          disabled={merging}
                          title="Keep this entity"
                        >
                          <Icon name="Check" size={14} />
                          Keep
                        </button>
                      </div>

                      <div className="merge-arrow">
                        <Icon name="ArrowLeftRight" size={20} />
                      </div>

                      <div className="entity-box">
                        <div className="entity-name">{candidate.entity_b.name}</div>
                        <button
                          className="btn btn-sm btn-outline keep-btn"
                          onClick={() => handleMerge(candidate, candidate.entity_b.id)}
                          disabled={merging}
                          title="Keep this entity"
                        >
                          <Icon name="Check" size={14} />
                          Keep
                        </button>
                      </div>
                    </div>

                    <div className="duplicate-reason">
                      <Icon name="Info" size={14} />
                      {candidate.reason}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <div className="duplicates-empty">
            <Icon name="CheckCircle" size={48} />
            <span>No duplicates found</span>
            <p>Try lowering the similarity threshold to find more potential matches.</p>
          </div>
        )}
      </div>

      {/* Confirm Merge Modal */}
      {confirmMerge && (
        <div className="merge-modal-overlay" onClick={() => setConfirmMerge(null)}>
          <div className="merge-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Confirm Merge</h3>
              <button className="close-btn" onClick={() => setConfirmMerge(null)}>
                <Icon name="X" size={20} />
              </button>
            </div>

            <div className="modal-body">
              <p>
                This will merge <strong>"{confirmMerge.entity_b.name}"</strong> into{' '}
                <strong>"{confirmMerge.entity_a.name}"</strong>.
              </p>
              <p className="merge-warning">
                <Icon name="AlertTriangle" size={16} />
                The merged entity will be removed and all references updated.
              </p>
            </div>

            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setConfirmMerge(null)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={() => handleMerge(confirmMerge, confirmMerge.entity_a.id)}
                disabled={merging}
              >
                {merging ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Merging...
                  </>
                ) : (
                  <>
                    <Icon name="Merge" size={16} />
                    Merge Entities
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
