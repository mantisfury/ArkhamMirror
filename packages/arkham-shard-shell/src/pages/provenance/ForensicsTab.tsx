/**
 * ForensicsTab - Metadata Forensics Analysis
 *
 * Provides UI for forensic metadata analysis:
 * - EXIF extraction (camera info, GPS, timestamps)
 * - PDF metadata extraction
 * - Office document metadata
 * - Timeline reconstruction
 * - Document comparison
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { apiPost } from '../../utils/api';

// Types
interface ExifData {
  make?: string;
  model?: string;
  serial_number?: string;
  datetime_original?: string;
  datetime_digitized?: string;
  datetime_modified?: string;
  gps_latitude?: number;
  gps_longitude?: number;
  gps_altitude?: number;
  software?: string;
  width?: number;
  height?: number;
}

interface PdfMetadata {
  title?: string;
  author?: string;
  subject?: string;
  creator?: string;
  producer?: string;
  creation_date?: string;
  modification_date?: string;
  keywords?: string[];
  page_count?: number;
  pdf_version?: string;
  is_encrypted?: boolean;
}

interface OfficeMetadata {
  title?: string;
  author?: string;
  subject?: string;
  company?: string;
  manager?: string;
  created?: string;
  modified?: string;
  last_modified_by?: string;
  revision?: number;
  keywords?: string[];
  category?: string;
}

interface ForensicFinding {
  finding_type: string;
  severity: string;
  description: string;
  evidence: Record<string, unknown>;
  confidence: number;
}

interface TimelineEvent {
  id: string;
  doc_id: string;
  event_type: string;
  event_timestamp?: string;
  event_source: string;
  event_actor?: string;
  event_details: Record<string, unknown>;
  confidence: number;
  is_estimated: boolean;
}

interface ForensicScan {
  id: string;
  doc_id: string;
  scan_status: string;
  file_hash_md5?: string;
  file_hash_sha256?: string;
  file_hash_sha512?: string;
  file_size?: number;
  exif_data?: ExifData;
  pdf_metadata?: PdfMetadata;
  office_metadata?: OfficeMetadata;
  findings: ForensicFinding[];
  integrity_status: string;
  confidence_score: number;
  timeline_events: TimelineEvent[];
  scanned_at?: string;
}

interface ForensicStats {
  total_scans: number;
  scans_by_status: Record<string, number>;
  documents_with_findings: number;
  integrity_status_counts: Record<string, number>;
  average_confidence: number;
}

interface ForensicsTabProps {
  onScanComplete?: () => void;
}

export function ForensicsTab({ onScanComplete }: ForensicsTabProps) {
  const { toast } = useToast();

  // State
  const [scanning, setScanning] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [selectedScan, setSelectedScan] = useState<ForensicScan | null>(null);
  const [recentScans, setRecentScans] = useState<ForensicScan[]>([]);
  const [comparing, setComparing] = useState(false);
  const [compareSourceId, setCompareSourceId] = useState<string>('');
  const [compareTargetId, setCompareTargetId] = useState<string>('');
  const [comparisonResult, setComparisonResult] = useState<any>(null);

  // Fetch stats
  const { data: statsData, refetch: refetchStats } = useFetch<{ stats: ForensicStats }>(
    '/api/provenance/forensics/stats'
  );
  const stats = statsData?.stats;

  // Fetch documents for selection
  const { data: documentsData } = useFetch<{ items: Array<{ id: string; filename: string; file_type: string }> }>(
    '/api/documents/items?limit=100'
  );
  const documents = documentsData?.items || [];

  // Scan a document
  const handleScan = useCallback(async () => {
    if (!selectedDocId) {
      toast.error('Please select a document to scan');
      return;
    }

    setScanning(true);
    try {
      const result = await apiPost<{ scan: ForensicScan }>('/api/provenance/forensics/scan', { doc_id: selectedDocId });
      setSelectedScan(result.scan);
      setRecentScans(prev => [result.scan, ...prev.slice(0, 9)]);
      refetchStats();

      if (result.scan.findings.length > 0) {
        toast.warning(`Forensic analysis complete. ${result.scan.findings.length} findings detected.`);
      } else {
        toast.success('Forensic analysis complete - no issues detected');
      }
      onScanComplete?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Scan failed');
    } finally {
      setScanning(false);
    }
  }, [selectedDocId, toast, refetchStats, onScanComplete]);

  // Compare documents
  const handleCompare = useCallback(async () => {
    if (!compareSourceId || !compareTargetId) {
      toast.error('Please select both source and target documents');
      return;
    }

    setComparing(true);
    try {
      const result = await apiPost<{ comparison: any }>('/api/provenance/forensics/compare', {
        source_doc_id: compareSourceId,
        target_doc_id: compareTargetId,
      });
      setComparisonResult(result.comparison);
      toast.success('Document comparison complete');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Comparison failed');
    } finally {
      setComparing(false);
    }
  }, [compareSourceId, compareTargetId, toast]);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const getIntegrityBadgeClass = (status: string): string => {
    switch (status) {
      case 'pristine': return 'integrity-pristine';
      case 'modified': return 'integrity-modified';
      case 'suspicious': return 'integrity-suspicious';
      case 'compromised': return 'integrity-compromised';
      default: return 'integrity-unknown';
    }
  };

  const getSeverityClass = (severity: string): string => {
    switch (severity) {
      case 'critical': return 'severity-critical';
      case 'high': return 'severity-high';
      case 'medium': return 'severity-medium';
      case 'low': return 'severity-low';
      default: return 'severity-info';
    }
  };

  return (
    <div className="forensics-tab">
      {/* Stats Overview */}
      <div className="forensics-stats-grid">
        <div className="forensics-stat-card">
          <Icon name="FileSearch" size={24} />
          <div className="forensics-stat-value">{stats?.total_scans ?? 0}</div>
          <div className="forensics-stat-label">Total Scans</div>
        </div>
        <div className="forensics-stat-card">
          <Icon name="AlertCircle" size={24} />
          <div className="forensics-stat-value">{stats?.documents_with_findings ?? 0}</div>
          <div className="forensics-stat-label">With Findings</div>
        </div>
        <div className="forensics-stat-card">
          <Icon name="Shield" size={24} />
          <div className="forensics-stat-value">{stats?.integrity_status_counts?.pristine ?? 0}</div>
          <div className="forensics-stat-label">Pristine</div>
        </div>
        <div className="forensics-stat-card">
          <Icon name="Target" size={24} />
          <div className="forensics-stat-value">
            {stats?.average_confidence ? `${(stats.average_confidence * 100).toFixed(0)}%` : '0%'}
          </div>
          <div className="forensics-stat-label">Avg Confidence</div>
        </div>
      </div>

      {/* Scan Controls */}
      <div className="forensics-scan-controls">
        <div className="forensics-scan-form">
          <label>Select Document for Forensic Analysis</label>
          <select
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            disabled={scanning}
          >
            <option value="">-- Select a document --</option>
            {documents.map(doc => (
              <option key={doc.id} value={doc.id}>
                {doc.filename} ({doc.file_type || 'unknown'})
              </option>
            ))}
          </select>
        </div>

        <div className="forensics-scan-actions">
          <button
            className="btn btn-primary"
            onClick={handleScan}
            disabled={scanning || !selectedDocId}
          >
            {scanning ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Icon name="FileSearch" size={16} />
                Analyze Metadata
              </>
            )}
          </button>
        </div>
      </div>

      {/* Scan Results */}
      {selectedScan && (
        <div className="forensics-scan-results">
          <h3>
            <Icon name="FileSearch" size={20} />
            Forensic Analysis Results
          </h3>

          {/* Summary */}
          <div className="forensics-result-summary">
            <div className={`forensics-integrity-badge ${getIntegrityBadgeClass(selectedScan.integrity_status)}`}>
              <span className="integrity-status">{selectedScan.integrity_status}</span>
              <span className="integrity-label">Integrity Status</span>
            </div>

            <div className="forensics-summary-stats">
              <div className="summary-item">
                <span className="label">Confidence:</span>
                <span className="value">{(selectedScan.confidence_score * 100).toFixed(0)}%</span>
              </div>
              <div className="summary-item">
                <span className="label">Findings:</span>
                <span className={`value ${selectedScan.findings.length > 0 ? 'warning' : ''}`}>
                  {selectedScan.findings.length}
                </span>
              </div>
              <div className="summary-item">
                <span className="label">Timeline Events:</span>
                <span className="value">{selectedScan.timeline_events.length}</span>
              </div>
              <div className="summary-item">
                <span className="label">File Size:</span>
                <span className="value">
                  {selectedScan.file_size ? `${(selectedScan.file_size / 1024).toFixed(1)} KB` : 'N/A'}
                </span>
              </div>
            </div>
          </div>

          {/* File Hashes */}
          {(selectedScan.file_hash_md5 || selectedScan.file_hash_sha256) && (
            <div className="forensics-hashes">
              <h4>
                <Icon name="Hash" size={16} />
                File Hashes
              </h4>
              <div className="hash-grid">
                {selectedScan.file_hash_md5 && (
                  <div className="hash-item">
                    <span className="hash-label">MD5:</span>
                    <code className="hash-value">{selectedScan.file_hash_md5}</code>
                  </div>
                )}
                {selectedScan.file_hash_sha256 && (
                  <div className="hash-item">
                    <span className="hash-label">SHA256:</span>
                    <code className="hash-value">{selectedScan.file_hash_sha256.substring(0, 32)}...</code>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* EXIF Data */}
          {selectedScan.exif_data && Object.values(selectedScan.exif_data).some(v => v !== null && v !== undefined) && (
            <div className="forensics-exif">
              <h4>
                <Icon name="Camera" size={16} />
                EXIF Data (Image Metadata)
              </h4>
              <div className="metadata-grid">
                {selectedScan.exif_data.make && (
                  <div className="metadata-item">
                    <span className="label">Camera Make:</span>
                    <span className="value">{selectedScan.exif_data.make}</span>
                  </div>
                )}
                {selectedScan.exif_data.model && (
                  <div className="metadata-item">
                    <span className="label">Camera Model:</span>
                    <span className="value">{selectedScan.exif_data.model}</span>
                  </div>
                )}
                {selectedScan.exif_data.serial_number && (
                  <div className="metadata-item">
                    <span className="label">Serial Number:</span>
                    <span className="value">{selectedScan.exif_data.serial_number}</span>
                  </div>
                )}
                {selectedScan.exif_data.software && (
                  <div className="metadata-item">
                    <span className="label">Software:</span>
                    <span className="value">{selectedScan.exif_data.software}</span>
                  </div>
                )}
                {selectedScan.exif_data.datetime_original && (
                  <div className="metadata-item">
                    <span className="label">Date Taken:</span>
                    <span className="value">{formatDate(selectedScan.exif_data.datetime_original)}</span>
                  </div>
                )}
                {(selectedScan.exif_data.gps_latitude || selectedScan.exif_data.gps_longitude) && (
                  <div className="metadata-item">
                    <span className="label">GPS Location:</span>
                    <span className="value">
                      {selectedScan.exif_data.gps_latitude?.toFixed(6)}, {selectedScan.exif_data.gps_longitude?.toFixed(6)}
                    </span>
                  </div>
                )}
                {(selectedScan.exif_data.width && selectedScan.exif_data.height) && (
                  <div className="metadata-item">
                    <span className="label">Dimensions:</span>
                    <span className="value">{selectedScan.exif_data.width} x {selectedScan.exif_data.height}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PDF Metadata */}
          {selectedScan.pdf_metadata && Object.values(selectedScan.pdf_metadata).some(v => v !== null && v !== undefined) && (
            <div className="forensics-pdf">
              <h4>
                <Icon name="FileText" size={16} />
                PDF Metadata
              </h4>
              <div className="metadata-grid">
                {selectedScan.pdf_metadata.title && (
                  <div className="metadata-item">
                    <span className="label">Title:</span>
                    <span className="value">{selectedScan.pdf_metadata.title}</span>
                  </div>
                )}
                {selectedScan.pdf_metadata.author && (
                  <div className="metadata-item">
                    <span className="label">Author:</span>
                    <span className="value">{selectedScan.pdf_metadata.author}</span>
                  </div>
                )}
                {selectedScan.pdf_metadata.creator && (
                  <div className="metadata-item">
                    <span className="label">Creator:</span>
                    <span className="value">{selectedScan.pdf_metadata.creator}</span>
                  </div>
                )}
                {selectedScan.pdf_metadata.producer && (
                  <div className="metadata-item">
                    <span className="label">Producer:</span>
                    <span className="value">{selectedScan.pdf_metadata.producer}</span>
                  </div>
                )}
                {selectedScan.pdf_metadata.creation_date && (
                  <div className="metadata-item">
                    <span className="label">Created:</span>
                    <span className="value">{formatDate(selectedScan.pdf_metadata.creation_date)}</span>
                  </div>
                )}
                {selectedScan.pdf_metadata.modification_date && (
                  <div className="metadata-item">
                    <span className="label">Modified:</span>
                    <span className="value">{formatDate(selectedScan.pdf_metadata.modification_date)}</span>
                  </div>
                )}
                {selectedScan.pdf_metadata.page_count && (
                  <div className="metadata-item">
                    <span className="label">Pages:</span>
                    <span className="value">{selectedScan.pdf_metadata.page_count}</span>
                  </div>
                )}
                {selectedScan.pdf_metadata.pdf_version && (
                  <div className="metadata-item">
                    <span className="label">PDF Version:</span>
                    <span className="value">{selectedScan.pdf_metadata.pdf_version}</span>
                  </div>
                )}
                {selectedScan.pdf_metadata.is_encrypted !== undefined && (
                  <div className="metadata-item">
                    <span className="label">Encrypted:</span>
                    <span className={`value ${selectedScan.pdf_metadata.is_encrypted ? 'warning' : ''}`}>
                      {selectedScan.pdf_metadata.is_encrypted ? 'Yes' : 'No'}
                    </span>
                  </div>
                )}
                {selectedScan.pdf_metadata.keywords && selectedScan.pdf_metadata.keywords.length > 0 && (
                  <div className="metadata-item full-width">
                    <span className="label">Keywords:</span>
                    <span className="value">{selectedScan.pdf_metadata.keywords.join(', ')}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Office Metadata */}
          {selectedScan.office_metadata && Object.values(selectedScan.office_metadata).some(v => v !== null && v !== undefined) && (
            <div className="forensics-office">
              <h4>
                <Icon name="FileSpreadsheet" size={16} />
                Office Document Metadata
              </h4>
              <div className="metadata-grid">
                {selectedScan.office_metadata.title && (
                  <div className="metadata-item">
                    <span className="label">Title:</span>
                    <span className="value">{selectedScan.office_metadata.title}</span>
                  </div>
                )}
                {selectedScan.office_metadata.author && (
                  <div className="metadata-item">
                    <span className="label">Author:</span>
                    <span className="value">{selectedScan.office_metadata.author}</span>
                  </div>
                )}
                {selectedScan.office_metadata.company && (
                  <div className="metadata-item">
                    <span className="label">Company:</span>
                    <span className="value">{selectedScan.office_metadata.company}</span>
                  </div>
                )}
                {selectedScan.office_metadata.last_modified_by && (
                  <div className="metadata-item">
                    <span className="label">Last Modified By:</span>
                    <span className="value">{selectedScan.office_metadata.last_modified_by}</span>
                  </div>
                )}
                {selectedScan.office_metadata.created && (
                  <div className="metadata-item">
                    <span className="label">Created:</span>
                    <span className="value">{formatDate(selectedScan.office_metadata.created)}</span>
                  </div>
                )}
                {selectedScan.office_metadata.modified && (
                  <div className="metadata-item">
                    <span className="label">Modified:</span>
                    <span className="value">{formatDate(selectedScan.office_metadata.modified)}</span>
                  </div>
                )}
                {selectedScan.office_metadata.revision && (
                  <div className="metadata-item">
                    <span className="label">Revision:</span>
                    <span className="value">{selectedScan.office_metadata.revision}</span>
                  </div>
                )}
                {selectedScan.office_metadata.subject && (
                  <div className="metadata-item full-width">
                    <span className="label">Subject:</span>
                    <span className="value">{selectedScan.office_metadata.subject}</span>
                  </div>
                )}
                {selectedScan.office_metadata.keywords && selectedScan.office_metadata.keywords.length > 0 && (
                  <div className="metadata-item full-width">
                    <span className="label">Keywords:</span>
                    <span className="value">{selectedScan.office_metadata.keywords.join(', ')}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Findings */}
          {selectedScan.findings.length > 0 && (
            <div className="forensics-findings">
              <h4>
                <Icon name="AlertTriangle" size={16} />
                Findings ({selectedScan.findings.length})
              </h4>
              <div className="findings-list">
                {selectedScan.findings.map((finding, i) => (
                  <div key={i} className={`finding-card ${getSeverityClass(finding.severity)}`}>
                    <div className="finding-header">
                      <span className="finding-type">{finding.finding_type.replace(/_/g, ' ')}</span>
                      <span className={`finding-severity ${getSeverityClass(finding.severity)}`}>
                        {finding.severity}
                      </span>
                    </div>
                    <p className="finding-description">{finding.description}</p>
                    <div className="finding-confidence">
                      {(finding.confidence * 100).toFixed(0)}% confidence
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timeline Events */}
          {selectedScan.timeline_events.length > 0 && (
            <div className="forensics-timeline">
              <h4>
                <Icon name="Clock" size={16} />
                Timeline Reconstruction ({selectedScan.timeline_events.length} events)
              </h4>
              <div className="timeline-list">
                {selectedScan.timeline_events
                  .sort((a, b) => {
                    if (!a.event_timestamp) return 1;
                    if (!b.event_timestamp) return -1;
                    return new Date(a.event_timestamp).getTime() - new Date(b.event_timestamp).getTime();
                  })
                  .map((event, i) => (
                    <div key={event.id || i} className={`timeline-event ${event.is_estimated ? 'estimated' : ''}`}>
                      <div className="event-marker">
                        <Icon name="Circle" size={10} />
                      </div>
                      <div className="event-content">
                        <div className="event-header">
                          <span className="event-type">{event.event_type.replace(/_/g, ' ')}</span>
                          {event.is_estimated && <span className="event-estimated">Estimated</span>}
                        </div>
                        <div className="event-timestamp">
                          {event.event_timestamp ? formatDate(event.event_timestamp) : 'Unknown time'}
                        </div>
                        {event.event_actor && (
                          <div className="event-actor">
                            <Icon name="User" size={12} />
                            {event.event_actor}
                          </div>
                        )}
                        <div className="event-source">
                          Source: {event.event_source}
                        </div>
                        <div className="event-confidence">
                          {(event.confidence * 100).toFixed(0)}% confidence
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Document Comparison */}
      <div className="forensics-comparison">
        <h3>
          <Icon name="GitCompare" size={20} />
          Document Comparison
        </h3>
        <div className="comparison-controls">
          <div className="comparison-select">
            <label>Source Document</label>
            <select
              value={compareSourceId}
              onChange={(e) => setCompareSourceId(e.target.value)}
              disabled={comparing}
            >
              <option value="">-- Select source --</option>
              {documents.map(doc => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
          </div>
          <div className="comparison-arrow">
            <Icon name="ArrowRight" size={20} />
          </div>
          <div className="comparison-select">
            <label>Target Document</label>
            <select
              value={compareTargetId}
              onChange={(e) => setCompareTargetId(e.target.value)}
              disabled={comparing}
            >
              <option value="">-- Select target --</option>
              {documents.map(doc => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn btn-secondary"
            onClick={handleCompare}
            disabled={comparing || !compareSourceId || !compareTargetId}
          >
            {comparing ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Comparing...
              </>
            ) : (
              <>
                <Icon name="GitCompare" size={16} />
                Compare
              </>
            )}
          </button>
        </div>

        {/* Comparison Result */}
        {comparisonResult && (
          <div className="comparison-result">
            <div className="comparison-header">
              <div className="match-score">
                <span className="score-value">{(comparisonResult.match_score * 100).toFixed(0)}%</span>
                <span className="score-label">Match Score</span>
              </div>
              <div className="relationship-type">
                <span className="relationship-label">Relationship:</span>
                <span className={`relationship-value ${comparisonResult.relationship_type}`}>
                  {comparisonResult.relationship_type?.replace(/_/g, ' ') || 'Unknown'}
                </span>
              </div>
              <div className="comparison-confidence">
                <span className="confidence-label">Confidence:</span>
                <span className="confidence-value">{(comparisonResult.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>

            {comparisonResult.similarities && comparisonResult.similarities.length > 0 && (
              <div className="comparison-section">
                <h4>
                  <Icon name="Check" size={16} />
                  Similarities ({comparisonResult.similarities.length})
                </h4>
                <ul className="comparison-list similarities">
                  {comparisonResult.similarities.map((item: string, i: number) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {comparisonResult.differences && comparisonResult.differences.length > 0 && (
              <div className="comparison-section">
                <h4>
                  <Icon name="X" size={16} />
                  Differences ({comparisonResult.differences.length})
                </h4>
                <ul className="comparison-list differences">
                  {comparisonResult.differences.map((item: string, i: number) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recent Scans */}
      {recentScans.length > 0 && (
        <div className="forensics-recent-scans">
          <h3>Recent Scans</h3>
          <div className="recent-scans-list">
            {recentScans.map(scan => (
              <div
                key={scan.id}
                className={`recent-scan-item ${selectedScan?.id === scan.id ? 'selected' : ''}`}
                onClick={() => setSelectedScan(scan)}
              >
                <div className="scan-doc">{scan.doc_id.slice(0, 8)}...</div>
                <div className={`scan-integrity ${getIntegrityBadgeClass(scan.integrity_status)}`}>
                  {scan.integrity_status}
                </div>
                <div className="scan-findings">
                  {scan.findings.length} findings
                </div>
                <div className="scan-date">
                  {scan.scanned_at ? new Date(scan.scanned_at).toLocaleTimeString() : 'N/A'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ForensicsTab;
