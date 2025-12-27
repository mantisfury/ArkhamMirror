/**
 * ProvenancePage - Data provenance and chain of custody tracking
 *
 * Provides UI for viewing provenance records, transformation history,
 * and audit trails for tracked entities.
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './ProvenancePage.css';

// Types
interface ProvenanceRecord {
  id: string;
  entity_type: string;
  entity_id: string;
  source_type?: string;
  source_id?: string;
  source_url?: string;
  imported_at?: string;
  imported_by?: string;
  metadata: Record<string, unknown>;
  created_at?: string;
}

interface Transformation {
  id: string;
  record_id: string;
  transformation_type: string;
  input_hash?: string;
  output_hash?: string;
  transformed_at?: string;
  transformer?: string;
  parameters: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

interface AuditRecord {
  id: string;
  record_id: string;
  action: string;
  actor?: string;
  details: Record<string, unknown>;
  occurred_at?: string;
}

export function ProvenancePage() {
  // Toast available for future use
  const { toast: _toast } = useToast();
  void _toast; // Suppress unused warning
  const [selectedRecord, setSelectedRecord] = useState<ProvenanceRecord | null>(null);
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'overview' | 'transformations' | 'audit'>('overview');

  // Fetch records
  const { data: records, loading, error, refetch } = useFetch<ProvenanceRecord[]>(
    `/api/provenance/${entityTypeFilter ? `?entity_type=${entityTypeFilter}` : ''}`
  );

  // Fetch transformations for selected record
  const { data: transformations, loading: transformationsLoading } = useFetch<Transformation[]>(
    selectedRecord ? `/api/provenance/${selectedRecord.id}/transformations` : null
  );

  // Fetch audit trail for selected record
  const { data: auditRecords, loading: auditLoading } = useFetch<AuditRecord[]>(
    selectedRecord ? `/api/provenance/${selectedRecord.id}/audit` : null
  );

  const handleSelectRecord = useCallback((record: ProvenanceRecord) => {
    setSelectedRecord(record);
    setActiveTab('overview');
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedRecord(null);
  }, []);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const renderRecordsList = () => {
    if (loading) {
      return (
        <div className="loading-state">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading provenance records...</span>
        </div>
      );
    }

    if (error) {
      return (
        <div className="error-state">
          <Icon name="AlertCircle" size={32} />
          <span>Failed to load provenance records</span>
          <button className="btn btn-secondary" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      );
    }

    if (!records || records.length === 0) {
      return (
        <div className="empty-state">
          <Icon name="GitBranch" size={48} />
          <span>No provenance records found</span>
          <p className="empty-hint">Records will appear as entities are tracked through the system</p>
        </div>
      );
    }

    return (
      <div className="records-list">
        {records.map(record => (
          <div
            key={record.id}
            className={`record-card ${selectedRecord?.id === record.id ? 'selected' : ''}`}
            onClick={() => handleSelectRecord(record)}
          >
            <div className="record-header">
              <Icon name="FileText" size={20} />
              <div className="record-info">
                <h3 className="record-title">{record.entity_type}</h3>
                <p className="record-id">{record.entity_id}</p>
              </div>
            </div>
            <div className="record-meta">
              {record.source_type && (
                <div className="meta-item">
                  <Icon name="Database" size={14} />
                  <span>{record.source_type}</span>
                </div>
              )}
              {record.imported_at && (
                <div className="meta-item">
                  <Icon name="Clock" size={14} />
                  <span>{formatDate(record.imported_at)}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderOverviewTab = () => {
    if (!selectedRecord) return null;

    return (
      <div className="overview-tab">
        <div className="detail-section">
          <h3>Entity Information</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <label>Entity Type</label>
              <span>{selectedRecord.entity_type}</span>
            </div>
            <div className="detail-item">
              <label>Entity ID</label>
              <span>{selectedRecord.entity_id}</span>
            </div>
            <div className="detail-item">
              <label>Source Type</label>
              <span>{selectedRecord.source_type || 'N/A'}</span>
            </div>
            <div className="detail-item">
              <label>Source ID</label>
              <span>{selectedRecord.source_id || 'N/A'}</span>
            </div>
          </div>
        </div>

        {selectedRecord.source_url && (
          <div className="detail-section">
            <h3>Source URL</h3>
            <a href={selectedRecord.source_url} target="_blank" rel="noopener noreferrer" className="source-link">
              <Icon name="ExternalLink" size={16} />
              {selectedRecord.source_url}
            </a>
          </div>
        )}

        <div className="detail-section">
          <h3>Import Information</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <label>Imported At</label>
              <span>{formatDate(selectedRecord.imported_at)}</span>
            </div>
            <div className="detail-item">
              <label>Imported By</label>
              <span>{selectedRecord.imported_by || 'System'}</span>
            </div>
            <div className="detail-item">
              <label>Created At</label>
              <span>{formatDate(selectedRecord.created_at)}</span>
            </div>
          </div>
        </div>

        {Object.keys(selectedRecord.metadata).length > 0 && (
          <div className="detail-section">
            <h3>Metadata</h3>
            <pre className="metadata-display">{JSON.stringify(selectedRecord.metadata, null, 2)}</pre>
          </div>
        )}
      </div>
    );
  };

  const renderTransformationsTab = () => {
    if (!selectedRecord) return null;

    if (transformationsLoading) {
      return (
        <div className="loading-state">
          <Icon name="Loader2" size={24} className="spin" />
          <span>Loading transformations...</span>
        </div>
      );
    }

    if (!transformations || transformations.length === 0) {
      return (
        <div className="empty-state">
          <Icon name="GitMerge" size={32} />
          <span>No transformations recorded</span>
        </div>
      );
    }

    return (
      <div className="transformations-tab">
        <div className="transformation-timeline">
          {transformations.map((transform) => (
            <div key={transform.id} className="timeline-item">
              <div className="timeline-marker">
                <Icon name="ArrowRight" size={16} />
              </div>
              <div className="timeline-content">
                <div className="timeline-header">
                  <h4>{transform.transformation_type}</h4>
                  <span className="timeline-date">{formatDate(transform.transformed_at)}</span>
                </div>
                <div className="timeline-details">
                  {transform.transformer && (
                    <div className="detail-item">
                      <Icon name="User" size={14} />
                      <span>{transform.transformer}</span>
                    </div>
                  )}
                  {transform.input_hash && (
                    <div className="detail-item">
                      <label>Input Hash:</label>
                      <code>{transform.input_hash.substring(0, 16)}...</code>
                    </div>
                  )}
                  {transform.output_hash && (
                    <div className="detail-item">
                      <label>Output Hash:</label>
                      <code>{transform.output_hash.substring(0, 16)}...</code>
                    </div>
                  )}
                </div>
                {Object.keys(transform.parameters).length > 0 && (
                  <details className="parameters-details">
                    <summary>Parameters</summary>
                    <pre>{JSON.stringify(transform.parameters, null, 2)}</pre>
                  </details>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderAuditTab = () => {
    if (!selectedRecord) return null;

    if (auditLoading) {
      return (
        <div className="loading-state">
          <Icon name="Loader2" size={24} className="spin" />
          <span>Loading audit trail...</span>
        </div>
      );
    }

    if (!auditRecords || auditRecords.length === 0) {
      return (
        <div className="empty-state">
          <Icon name="FileCheck" size={32} />
          <span>No audit records found</span>
        </div>
      );
    }

    return (
      <div className="audit-tab">
        <div className="audit-timeline">
          {auditRecords.map(audit => (
            <div key={audit.id} className="audit-item">
              <div className="audit-header">
                <Icon name="Activity" size={16} />
                <h4>{audit.action}</h4>
                <span className="audit-date">{formatDate(audit.occurred_at)}</span>
              </div>
              <div className="audit-body">
                {audit.actor && (
                  <div className="audit-actor">
                    <Icon name="User" size={14} />
                    <span>{audit.actor}</span>
                  </div>
                )}
                {Object.keys(audit.details).length > 0 && (
                  <details className="audit-details">
                    <summary>Details</summary>
                    <pre>{JSON.stringify(audit.details, null, 2)}</pre>
                  </details>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="provenance-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="GitBranch" size={28} />
          <div>
            <h1>Provenance</h1>
            <p className="page-description">Track data origin and chain of custody</p>
          </div>
        </div>

        <div className="header-actions">
          <select
            className="entity-filter"
            value={entityTypeFilter}
            onChange={(e) => setEntityTypeFilter(e.target.value)}
          >
            <option value="">All Entity Types</option>
            <option value="document">Documents</option>
            <option value="entity">Entities</option>
            <option value="claim">Claims</option>
            <option value="matrix">Matrices</option>
            <option value="report">Reports</option>
          </select>
        </div>
      </header>

      <div className="provenance-layout">
        {/* Records List */}
        <aside className="records-sidebar">
          <div className="sidebar-header">
            <h2>Records</h2>
            <span className="record-count">{records?.length || 0}</span>
          </div>
          {renderRecordsList()}
        </aside>

        {/* Detail Panel */}
        <main className="detail-panel">
          {selectedRecord ? (
            <>
              <div className="detail-header">
                <h2>Provenance Details</h2>
                <button className="btn-icon" onClick={handleClearSelection} title="Close">
                  <Icon name="X" size={20} />
                </button>
              </div>

              <div className="detail-tabs">
                <button
                  className={`tab-button ${activeTab === 'overview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('overview')}
                >
                  <Icon name="Info" size={16} />
                  Overview
                </button>
                <button
                  className={`tab-button ${activeTab === 'transformations' ? 'active' : ''}`}
                  onClick={() => setActiveTab('transformations')}
                >
                  <Icon name="GitMerge" size={16} />
                  Transformations
                  {transformations && transformations.length > 0 && (
                    <span className="tab-badge">{transformations.length}</span>
                  )}
                </button>
                <button
                  className={`tab-button ${activeTab === 'audit' ? 'active' : ''}`}
                  onClick={() => setActiveTab('audit')}
                >
                  <Icon name="FileCheck" size={16} />
                  Audit Trail
                  {auditRecords && auditRecords.length > 0 && (
                    <span className="tab-badge">{auditRecords.length}</span>
                  )}
                </button>
              </div>

              <div className="detail-content">
                {activeTab === 'overview' && renderOverviewTab()}
                {activeTab === 'transformations' && renderTransformationsTab()}
                {activeTab === 'audit' && renderAuditTab()}
              </div>
            </>
          ) : (
            <div className="no-selection">
              <Icon name="GitBranch" size={64} />
              <h2>Select a Record</h2>
              <p>Choose a provenance record from the list to view its details, transformations, and audit trail</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
