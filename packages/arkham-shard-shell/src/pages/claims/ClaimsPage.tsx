/**
 * ClaimsPage - Claims management and verification
 *
 * Provides UI for viewing, filtering, and managing factual claims
 * extracted from documents with evidence linking and verification workflow.
 */

import { useState } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import './ClaimsPage.css';

// Types
interface Claim {
  id: string;
  text: string;
  claim_type: string;
  status: string;
  confidence: number;
  source_document_id: string | null;
  source_start_char: number | null;
  source_end_char: number | null;
  source_context: string | null;
  extracted_by: string;
  extraction_model: string | null;
  entity_ids: string[];
  evidence_count: number;
  supporting_count: number;
  refuting_count: number;
  created_at: string;
  updated_at: string;
  verified_at: string | null;
  metadata: Record<string, unknown>;
}

interface Evidence {
  id: string;
  claim_id: string;
  evidence_type: string;
  reference_id: string;
  reference_title: string | null;
  relationship: string;
  strength: string;
  excerpt: string | null;
  notes: string | null;
  added_by: string;
  added_at: string;
  metadata: Record<string, unknown>;
}

const STATUS_FILTERS = [
  { value: '', label: 'All Claims' },
  { value: 'unverified', label: 'Unverified' },
  { value: 'verified', label: 'Verified' },
  { value: 'disputed', label: 'Disputed' },
  { value: 'uncertain', label: 'Uncertain' },
  { value: 'retracted', label: 'Retracted' },
];

const STATUS_COLORS: Record<string, string> = {
  unverified: 'status-warning',
  verified: 'status-success',
  disputed: 'status-error',
  uncertain: 'status-info',
  retracted: 'status-muted',
};

const STATUS_ICONS: Record<string, string> = {
  unverified: 'AlertCircle',
  verified: 'CheckCircle',
  disputed: 'AlertTriangle',
  uncertain: 'HelpCircle',
  retracted: 'XCircle',
};

export function ClaimsPage() {
  const { toast } = useToast();
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);

  // Fetch claims with filtering using usePaginatedFetch
  const { items: claims, total, loading, error, refetch } = usePaginatedFetch<Claim>(
    '/api/claims/',
    {
      params: {
        status: statusFilter || undefined,
        search: searchQuery || undefined,
      },
    }
  );

  // Fetch evidence for selected claim
  const { data: evidence, loading: evidenceLoading } = useFetch<Evidence[]>(
    selectedClaim ? `/api/claims/${selectedClaim.id}/evidence` : null
  );

  const handleStatusChange = async (claimId: string, newStatus: string) => {
    try {
      const response = await fetch(`/api/claims/${claimId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update claim status');
      }

      toast.success(`Claim marked as ${newStatus}`);
      refetch();

      // Update selected claim if it's the one we changed
      if (selectedClaim?.id === claimId) {
        const updated = await response.json();
        setSelectedClaim(updated);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update claim');
    }
  };

  const handleViewEvidence = (claim: Claim) => {
    setSelectedClaim(claim);
    setShowEvidence(true);
  };

  const handleCloseDetails = () => {
    setSelectedClaim(null);
    setShowEvidence(false);
  };

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.5) return 'confidence-medium';
    return 'confidence-low';
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  return (
    <div className="claims-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Quote" size={28} />
          <div>
            <h1>Claims</h1>
            <p className="page-description">
              Extracted factual claims with verification status and evidence
            </p>
          </div>
        </div>
      </header>

      <div className="claims-filters">
        <div className="filter-group">
          <label htmlFor="status-filter">Status</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="filter-select"
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="search-input">Search Claims</label>
          <input
            id="search-input"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search claim text..."
            className="search-input"
          />
        </div>

        <div className="filter-info">
          Showing {claims.length} of {total} claims
        </div>
      </div>

      <main className="claims-content">
        {loading ? (
          <div className="claims-loading">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Loading claims...</span>
          </div>
        ) : error ? (
          <div className="claims-error">
            <Icon name="AlertCircle" size={32} />
            <span>Failed to load claims</span>
            <button className="btn btn-secondary" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        ) : claims.length > 0 ? (
          <div className="claims-list">
            {claims.map((claim) => (
              <div
                key={claim.id}
                className={`claim-card ${selectedClaim?.id === claim.id ? 'selected' : ''}`}
                onClick={() => setSelectedClaim(claim)}
              >
                <div className="claim-header">
                  <div className="claim-status-badges">
                    <span className={`status-badge ${STATUS_COLORS[claim.status]}`}>
                      <Icon name={STATUS_ICONS[claim.status]} size={14} />
                      {claim.status}
                    </span>
                    <span className={`confidence-badge ${getConfidenceColor(claim.confidence)}`}>
                      {Math.round(claim.confidence * 100)}% confidence
                    </span>
                  </div>
                  <div className="claim-actions">
                    <button
                      className="btn-icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleViewEvidence(claim);
                      }}
                      title="View evidence"
                    >
                      <Icon name="FileText" size={16} />
                      <span className="evidence-count">{claim.evidence_count}</span>
                    </button>
                  </div>
                </div>

                <p className="claim-text">{claim.text}</p>

                <div className="claim-meta">
                  <span className="meta-item">
                    <Icon name="Calendar" size={12} />
                    {formatDate(claim.created_at)}
                  </span>
                  <span className="meta-item">
                    <Icon name="Tag" size={12} />
                    {claim.claim_type}
                  </span>
                  {claim.evidence_count > 0 && (
                    <span className="meta-item">
                      <Icon name="CheckSquare" size={12} />
                      {claim.supporting_count} supporting
                      {claim.refuting_count > 0 && `, ${claim.refuting_count} refuting`}
                    </span>
                  )}
                </div>

                {selectedClaim?.id === claim.id && (
                  <div className="claim-quick-actions">
                    <button
                      className="btn btn-sm btn-success"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleStatusChange(claim.id, 'verified');
                      }}
                      disabled={claim.status === 'verified'}
                    >
                      <Icon name="CheckCircle" size={14} />
                      Verify
                    </button>
                    <button
                      className="btn btn-sm btn-warning"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleStatusChange(claim.id, 'disputed');
                      }}
                      disabled={claim.status === 'disputed'}
                    >
                      <Icon name="AlertTriangle" size={14} />
                      Dispute
                    </button>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleStatusChange(claim.id, 'uncertain');
                      }}
                      disabled={claim.status === 'uncertain'}
                    >
                      <Icon name="HelpCircle" size={14} />
                      Uncertain
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="claims-empty">
            <Icon name="FileQuestion" size={48} />
            <span>No claims found</span>
            {(statusFilter || searchQuery) && (
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setStatusFilter('');
                  setSearchQuery('');
                }}
              >
                Clear Filters
              </button>
            )}
          </div>
        )}
      </main>

      {/* Evidence Panel */}
      {showEvidence && selectedClaim && (
        <aside className="evidence-panel">
          <div className="panel-header">
            <h3>Evidence for Claim</h3>
            <button className="btn-icon" onClick={handleCloseDetails}>
              <Icon name="X" size={20} />
            </button>
          </div>

          <div className="panel-content">
            <div className="claim-details">
              <p className="claim-text-detail">{selectedClaim.text}</p>
              <div className="claim-metadata">
                <div className="metadata-row">
                  <span className="label">Status:</span>
                  <span className={`status-badge ${STATUS_COLORS[selectedClaim.status]}`}>
                    <Icon name={STATUS_ICONS[selectedClaim.status]} size={12} />
                    {selectedClaim.status}
                  </span>
                </div>
                <div className="metadata-row">
                  <span className="label">Confidence:</span>
                  <span>{Math.round(selectedClaim.confidence * 100)}%</span>
                </div>
                <div className="metadata-row">
                  <span className="label">Evidence:</span>
                  <span>
                    {selectedClaim.evidence_count} total
                    ({selectedClaim.supporting_count} supporting, {selectedClaim.refuting_count} refuting)
                  </span>
                </div>
              </div>
            </div>

            <div className="evidence-list">
              <h4>Evidence Items</h4>
              {evidenceLoading ? (
                <div className="evidence-loading">
                  <Icon name="Loader2" size={24} className="spin" />
                  <span>Loading evidence...</span>
                </div>
              ) : evidence && evidence.length > 0 ? (
                evidence.map((ev) => (
                  <div key={ev.id} className="evidence-item">
                    <div className="evidence-header">
                      <span className={`relationship-badge relationship-${ev.relationship}`}>
                        <Icon
                          name={ev.relationship === 'supports' ? 'ThumbsUp' : ev.relationship === 'refutes' ? 'ThumbsDown' : 'Link'}
                          size={12}
                        />
                        {ev.relationship}
                      </span>
                      <span className={`strength-badge strength-${ev.strength}`}>
                        {ev.strength} strength
                      </span>
                    </div>
                    {ev.reference_title && (
                      <p className="evidence-title">{ev.reference_title}</p>
                    )}
                    {ev.excerpt && (
                      <p className="evidence-excerpt">{ev.excerpt}</p>
                    )}
                    {ev.notes && (
                      <p className="evidence-notes">{ev.notes}</p>
                    )}
                    <div className="evidence-meta">
                      <span>Added {formatDate(ev.added_at)}</span>
                      <span>by {ev.added_by}</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="evidence-empty">
                  <Icon name="FileQuestion" size={32} />
                  <span>No evidence linked to this claim</span>
                </div>
              )}
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}
