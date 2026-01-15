/**
 * HiddenContentTab - Steganography and Hidden Data Detection
 *
 * Provides UI for detecting hidden content in documents:
 * - Entropy analysis (encrypted/compressed data detection)
 * - LSB pattern analysis (image steganography)
 * - File type mismatch detection
 * - Chi-square statistical tests
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import * as api from './api';
import type {
  HiddenContentScan,
  HiddenContentStats,
  EntropyRegion,
  StegoIndicator,
} from './api';

// Props
interface HiddenContentTabProps {
  onScanComplete?: () => void;
}

export function HiddenContentTab({ onScanComplete }: HiddenContentTabProps) {
  const { toast } = useToast();

  // State
  const [scanning, setScanning] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [selectedScan, setSelectedScan] = useState<HiddenContentScan | null>(null);
  const [recentScans, setRecentScans] = useState<HiddenContentScan[]>([]);

  // Fetch stats
  const { data: statsData, refetch: refetchStats } = useFetch<{ stats: HiddenContentStats }>(
    '/api/anomalies/hidden-content/stats'
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
      const result = await api.scanHiddenContent({ doc_id: selectedDocId });
      setSelectedScan(result.scan);
      setRecentScans(prev => [result.scan, ...prev.slice(0, 9)]);
      refetchStats();

      if (result.anomaly_created) {
        toast.warning('Hidden content detected! Anomaly created.');
        onScanComplete?.();
      } else if (result.scan.stego_confidence > 0.5) {
        toast.warning(`Suspicious patterns detected (${(result.scan.stego_confidence * 100).toFixed(0)}% confidence)`);
      } else {
        toast.success('Scan complete - no hidden content detected');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Scan failed');
    } finally {
      setScanning(false);
    }
  }, [selectedDocId, toast, refetchStats, onScanComplete]);

  // Quick scan multiple documents
  const handleQuickScan = useCallback(async () => {
    const docIds = documents.slice(0, 20).map(d => d.id);
    if (docIds.length === 0) {
      toast.error('No documents available for scanning');
      return;
    }

    setScanning(true);
    try {
      const result = await api.quickScanHiddenContent(docIds);
      toast.success(`Scanned ${result.scanned} documents. ${result.requires_full_scan_count} need full analysis.`);

      if (result.requires_full_scan_count > 0) {
        toast.warning(`High entropy detected in: ${result.requires_full_scan.join(', ')}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Quick scan failed');
    } finally {
      setScanning(false);
    }
  }, [documents, toast]);

  return (
    <div className="hidden-content-tab">
      {/* Stats Overview */}
      <div className="hc-stats-grid">
        <div className="hc-stat-card">
          <Icon name="ScanSearch" size={24} />
          <div className="hc-stat-value">{stats?.total_scans ?? 0}</div>
          <div className="hc-stat-label">Total Scans</div>
        </div>
        <div className="hc-stat-card">
          <Icon name="AlertTriangle" size={24} />
          <div className="hc-stat-value">{stats?.documents_with_findings ?? 0}</div>
          <div className="hc-stat-label">With Findings</div>
        </div>
        <div className="hc-stat-card">
          <Icon name="Zap" size={24} />
          <div className="hc-stat-value">{stats?.high_entropy_files ?? 0}</div>
          <div className="hc-stat-label">High Entropy</div>
        </div>
        <div className="hc-stat-card">
          <Icon name="Eye" size={24} />
          <div className="hc-stat-value">{stats?.stego_candidates ?? 0}</div>
          <div className="hc-stat-label">Stego Candidates</div>
        </div>
      </div>

      {/* Scan Controls */}
      <div className="hc-scan-controls">
        <div className="hc-scan-form">
          <label>Select Document</label>
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

        <div className="hc-scan-actions">
          <button
            className="btn btn-primary"
            onClick={handleScan}
            disabled={scanning || !selectedDocId}
          >
            {scanning ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Scanning...
              </>
            ) : (
              <>
                <Icon name="ScanSearch" size={16} />
                Full Scan
              </>
            )}
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleQuickScan}
            disabled={scanning || documents.length === 0}
          >
            <Icon name="Zap" size={16} />
            Quick Scan All
          </button>
        </div>
      </div>

      {/* Scan Results */}
      {selectedScan && (
        <div className="hc-scan-results">
          <h3>
            <Icon name="FileSearch" size={20} />
            Scan Results
          </h3>

          {/* Summary */}
          <div className="hc-result-summary">
            <div className={`hc-confidence-badge ${getConfidenceClass(selectedScan.stego_confidence)}`}>
              <span className="confidence-value">
                {(selectedScan.stego_confidence * 100).toFixed(0)}%
              </span>
              <span className="confidence-label">Stego Confidence</span>
            </div>

            <div className="hc-summary-stats">
              <div className="summary-item">
                <span className="label">Global Entropy:</span>
                <span className={`value ${selectedScan.entropy_global > 7 ? 'high' : selectedScan.entropy_global > 6 ? 'medium' : ''}`}>
                  {selectedScan.entropy_global.toFixed(3)} / 8.0
                </span>
              </div>
              <div className="summary-item">
                <span className="label">File Type Match:</span>
                <span className={`value ${selectedScan.file_mismatch ? 'error' : 'success'}`}>
                  {selectedScan.file_mismatch ? 'MISMATCH' : 'OK'}
                </span>
              </div>
              <div className="summary-item">
                <span className="label">Indicators Found:</span>
                <span className="value">{selectedScan.stego_indicators.length}</span>
              </div>
            </div>
          </div>

          {/* Findings */}
          {selectedScan.findings.length > 0 && (
            <div className="hc-findings">
              <h4>
                <Icon name="AlertCircle" size={16} />
                Findings
              </h4>
              <ul>
                {selectedScan.findings.map((finding, i) => (
                  <li key={i}>{finding}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Entropy Regions */}
          {selectedScan.entropy_regions.length > 0 && (
            <div className="hc-entropy-regions">
              <h4>
                <Icon name="BarChart3" size={16} />
                Entropy Analysis by Region
              </h4>
              <div className="entropy-chart">
                {selectedScan.entropy_regions.map((region, i) => (
                  <EntropyRegionBar key={i} region={region} index={i} />
                ))}
              </div>
            </div>
          )}

          {/* Stego Indicators */}
          {selectedScan.stego_indicators.length > 0 && (
            <div className="hc-indicators">
              <h4>
                <Icon name="Eye" size={16} />
                Steganography Indicators
              </h4>
              <div className="indicators-list">
                {selectedScan.stego_indicators.map((indicator, i) => (
                  <StegoIndicatorCard key={i} indicator={indicator} />
                ))}
              </div>
            </div>
          )}

          {/* LSB Analysis */}
          {selectedScan.lsb_result && (
            <div className="hc-lsb-analysis">
              <h4>
                <Icon name="Binary" size={16} />
                LSB (Least Significant Bit) Analysis
              </h4>
              <div className="lsb-details">
                <div className="lsb-item">
                  <span className="label">Bit Ratio:</span>
                  <span className="value">{(selectedScan.lsb_result.bit_ratio * 100).toFixed(2)}%</span>
                </div>
                <div className="lsb-item">
                  <span className="label">Chi-Square Value:</span>
                  <span className="value">{selectedScan.lsb_result.chi_square_value.toFixed(4)}</span>
                </div>
                <div className="lsb-item">
                  <span className="label">P-Value:</span>
                  <span className={`value ${selectedScan.lsb_result.chi_square_p_value < 0.05 ? 'suspicious' : ''}`}>
                    {selectedScan.lsb_result.chi_square_p_value.toFixed(6)}
                  </span>
                </div>
                <div className="lsb-item">
                  <span className="label">Suspicious:</span>
                  <span className={`value ${selectedScan.lsb_result.is_suspicious ? 'error' : 'success'}`}>
                    {selectedScan.lsb_result.is_suspicious ? 'YES' : 'NO'}
                  </span>
                </div>
                <div className="lsb-item">
                  <span className="label">Confidence:</span>
                  <span className="value">{(selectedScan.lsb_result.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          )}

          {/* Magic Bytes */}
          <div className="hc-magic-bytes">
            <h4>
              <Icon name="FileType" size={16} />
              File Type Detection
            </h4>
            <div className="magic-details">
              <div className="magic-item">
                <span className="label">Expected Type:</span>
                <span className="value">{selectedScan.magic_expected || 'Unknown'}</span>
              </div>
              <div className="magic-item">
                <span className="label">Actual Type:</span>
                <span className="value">{selectedScan.magic_actual || 'Unknown'}</span>
              </div>
              {selectedScan.file_mismatch && (
                <div className="magic-warning">
                  <Icon name="AlertTriangle" size={16} />
                  File extension does not match actual file type!
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Recent Scans */}
      {recentScans.length > 0 && (
        <div className="hc-recent-scans">
          <h3>Recent Scans</h3>
          <div className="recent-scans-list">
            {recentScans.map(scan => (
              <div
                key={scan.id}
                className={`recent-scan-item ${selectedScan?.id === scan.id ? 'selected' : ''}`}
                onClick={() => setSelectedScan(scan)}
              >
                <div className="scan-doc">{scan.doc_id.slice(0, 8)}...</div>
                <div className={`scan-confidence ${getConfidenceClass(scan.stego_confidence)}`}>
                  {(scan.stego_confidence * 100).toFixed(0)}%
                </div>
                <div className="scan-date">
                  {new Date(scan.created_at).toLocaleTimeString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Helper Components

function EntropyRegionBar({ region, index }: { region: EntropyRegion; index: number }) {
  const percentage = (region.entropy_value / 8) * 100;
  const colorClass = region.is_anomalous ? 'anomalous' : percentage > 87.5 ? 'high' : percentage > 75 ? 'medium' : 'normal';

  return (
    <div className="entropy-region">
      <div className="region-label">
        Region {index + 1}
        <span className="region-range">
          ({region.start_offset} - {region.end_offset})
        </span>
      </div>
      <div className="region-bar-container">
        <div
          className={`region-bar ${colorClass}`}
          style={{ width: `${percentage}%` }}
        />
        <span className="region-value">{region.entropy_value.toFixed(3)}</span>
      </div>
      {region.description && (
        <div className={`region-desc ${region.is_anomalous ? 'warning' : ''}`}>
          {region.description}
        </div>
      )}
    </div>
  );
}

function StegoIndicatorCard({ indicator }: { indicator: StegoIndicator }) {
  const iconMap: Record<string, string> = {
    entropy_spike: 'TrendingUp',
    high_global_entropy: 'Thermometer',
    lsb_anomaly: 'Binary',
    histogram_anomaly: 'BarChart',
    file_mismatch: 'FileWarning',
  };

  return (
    <div className={`indicator-card ${indicator.confidence > 0.7 ? 'high-conf' : ''}`}>
      <div className="indicator-icon">
        <Icon name={(iconMap[indicator.indicator_type] || 'AlertCircle') as any} size={20} />
      </div>
      <div className="indicator-content">
        <div className="indicator-type">
          {indicator.indicator_type.replace(/_/g, ' ')}
        </div>
        <div className="indicator-location">
          Location: {indicator.location}
        </div>
        <div className="indicator-confidence">
          {(indicator.confidence * 100).toFixed(0)}% confidence
        </div>
      </div>
    </div>
  );
}

// Helper Functions

function getConfidenceClass(confidence: number): string {
  if (confidence >= 0.8) return 'critical';
  if (confidence >= 0.6) return 'high';
  if (confidence >= 0.4) return 'medium';
  return 'low';
}

export default HiddenContentTab;
