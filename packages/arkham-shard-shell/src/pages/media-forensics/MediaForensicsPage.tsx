/**
 * MediaForensicsPage - Media Forensics Analysis
 *
 * Main page for analyzing images and media files for authenticity,
 * including EXIF metadata, C2PA credentials, ELA, and more.
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { AIAnalystButton } from '../../components/AIAnalyst';

import * as api from './api';
import { ExifPanel } from './components/ExifPanel';
import { C2PAPanel } from './components/C2PAPanel';
import { ELAViewer } from './components/ELAViewer';
import { SunPositionPanel } from './components/SunPositionPanel';
import { SimilarImagesPanel } from './components/SimilarImagesPanel';
import { WarningsPanel } from './components/WarningsPanel';

import type {
  MediaAnalysis,
  AnalysisStats,
  AnalysisStatus,
  VerificationStatus,
} from './types';
import {
  STATUS_LABELS,
  STATUS_COLORS,
  VERIFICATION_LABELS,
  VERIFICATION_COLORS,
  STATUS_OPTIONS,
  VERIFICATION_OPTIONS,
} from './types';

import './MediaForensicsPage.css';

// Detail tab types
type DetailTab = 'exif' | 'c2pa' | 'ela' | 'sun' | 'similar' | 'warnings';

// Document item for selection
interface DocumentItem {
  id: string;
  filename: string;
  file_type: string;
  status: string;
}

export function MediaForensicsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();

  // State
  const [analyses, setAnalyses] = useState<MediaAnalysis[]>([]);
  const [selectedAnalysis, setSelectedAnalysis] = useState<MediaAnalysis | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>('exif');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [verificationFilter, setVerificationFilter] = useState<string>('');
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Modal states
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeOptions, setAnalyzeOptions] = useState({
    run_ela: true,
    run_sun_position: false,
    run_similar_search: false,
  });

  // Upload states
  const [uploadMode, setUploadMode] = useState<'select' | 'upload'>('upload');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // Fetch stats
  const { data: statsData, refetch: refetchStats } = useFetch<{ stats: AnalysisStats }>(
    '/api/media-forensics/stats'
  );
  const stats = statsData?.stats;

  // Fetch documents for selection
  const { data: documentsData } = useFetch<{
    items: DocumentItem[];
  }>('/api/documents/items?status=processed&limit=100&file_type=image');
  const documents = documentsData?.items || [];

  // Fetch analyses
  const fetchAnalyses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.listAnalyses({
        offset,
        limit: 20,
        status: statusFilter || undefined,
        verification_status: verificationFilter || undefined,
      });
      setAnalyses(response.items);
      setHasMore(response.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analyses');
    } finally {
      setLoading(false);
    }
  }, [offset, statusFilter, verificationFilter]);

  useEffect(() => {
    fetchAnalyses();
  }, [fetchAnalyses]);

  // Reset offset when filters change
  useEffect(() => {
    setOffset(0);
  }, [statusFilter, verificationFilter]);

  // Handle URL params for direct linking
  useEffect(() => {
    const analysisId = searchParams.get('id');
    if (analysisId && analyses.length > 0) {
      const analysis = analyses.find((a) => a.id === analysisId);
      if (analysis) {
        setSelectedAnalysis(analysis);
      }
    }
  }, [searchParams, analyses]);

  const handleSelectAnalysis = useCallback(
    (analysis: MediaAnalysis) => {
      setSelectedAnalysis(analysis);
      setDetailTab('exif');
      setSearchParams({ id: analysis.id });
    },
    [setSearchParams]
  );

  const handleCloseDetail = useCallback(() => {
    setSelectedAnalysis(null);
    setSearchParams({});
  }, [setSearchParams]);

  const handleAnalyzeDocument = async () => {
    // Validate input based on mode
    if (uploadMode === 'upload' && !selectedFile) {
      toast.error('Please select a file to upload');
      return;
    }
    if (uploadMode === 'select' && !selectedDocId) {
      toast.error('Please select a document to analyze');
      return;
    }

    setAnalyzing(true);
    try {
      let analysis: MediaAnalysis | undefined;

      if (uploadMode === 'upload' && selectedFile) {
        // Upload file directly
        analysis = await api.uploadAndAnalyze(selectedFile, {
          run_ela: analyzeOptions.run_ela,
        });
        toast.success('File uploaded and analyzed successfully');
      } else {
        // Analyze existing document
        const response = await api.analyzeDocument({
          doc_id: selectedDocId,
          ...analyzeOptions,
        });
        analysis = response.analysis;
        toast.success('Analysis started successfully');
      }

      setShowAnalyzeModal(false);
      setSelectedDocId('');
      setSelectedFile(null);
      fetchAnalyses();
      refetchStats();

      // Select the new analysis
      if (analysis) {
        setSelectedAnalysis(analysis);
        setSearchParams({ id: analysis.id });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start analysis');
    } finally {
      setAnalyzing(false);
    }
  };

  // Handle file drop
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      // Validate file type
      const validTypes = ['image/jpeg', 'image/png', 'image/tiff', 'image/webp', 'image/gif', 'image/bmp'];
      if (validTypes.includes(file.type) || /\.(jpg|jpeg|png|tiff|tif|webp|gif|bmp)$/i.test(file.name)) {
        setSelectedFile(file);
      } else {
        toast.error('Unsupported file type. Please upload JPEG, PNG, TIFF, WebP, GIF, or BMP.');
      }
    }
  }, [toast]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      setSelectedFile(files[0]);
    }
  }, []);

  const handleDeleteAnalysis = async (analysisId: string) => {
    if (!confirm('Are you sure you want to delete this analysis?')) {
      return;
    }

    try {
      await api.deleteAnalysis(analysisId);
      toast.success('Analysis deleted');
      fetchAnalyses();
      refetchStats();
      if (selectedAnalysis?.id === analysisId) {
        setSelectedAnalysis(null);
        setSearchParams({});
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete analysis');
    }
  };

  const handleReanalyze = async (analysisId: string) => {
    try {
      const response = await api.reanalyze(analysisId);
      toast.success('Re-analysis started');
      fetchAnalyses();
      if (response.analysis) {
        setSelectedAnalysis(response.analysis);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start re-analysis');
    }
  };

  const getVerificationIcon = (status: VerificationStatus): string => {
    switch (status) {
      case 'verified':
        return 'CheckCircle';
      case 'flagged':
        return 'AlertTriangle';
      case 'tampered':
        return 'XCircle';
      default:
        return 'HelpCircle';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string): string => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  // Build AI Analyst context from selected analysis
  const aiAnalystContext = useMemo(() => {
    if (!selectedAnalysis) return {};

    return {
      filename: selectedAnalysis.filename,
      file_type: selectedAnalysis.file_type,
      file_size: selectedAnalysis.file_size,
      verification_status: selectedAnalysis.verification_status,
      integrity_status: selectedAnalysis.integrity_status,
      findings_count: selectedAnalysis.findings_count,
      critical_findings: selectedAnalysis.critical_findings,
      exif_data: selectedAnalysis.exif_data,
      c2pa_data: selectedAnalysis.c2pa_data,
      ela_result: selectedAnalysis.ela_result,
      perceptual_hashes: selectedAnalysis.perceptual_hashes,
      analyzed_at: selectedAnalysis.analyzed_at,
    };
  }, [selectedAnalysis]);

  if (loading && analyses.length === 0) {
    return (
      <div className="media-forensics-page">
        <div className="content-loading">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading analyses...</span>
        </div>
      </div>
    );
  }

  if (error && analyses.length === 0) {
    return (
      <div className="media-forensics-page">
        <div className="content-error">
          <Icon name="AlertCircle" size={48} />
          <h2>Failed to load analyses</h2>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={fetchAnalyses}>
            <Icon name="RefreshCw" size={16} />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="media-forensics-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="ImageOff" size={28} />
          <div>
            <h1>Media Forensics</h1>
            <p className="page-description">
              Analyze images for authenticity, metadata, and manipulation
            </p>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-primary" onClick={() => setShowAnalyzeModal(true)}>
            <Icon name="Plus" size={16} />
            New Analysis
          </button>
        </div>
      </header>

      {/* Stats Dashboard */}
      {stats && (
        <div className="forensics-stats-grid">
          <div className="forensics-stat-card">
            <Icon name="Image" size={24} />
            <div className="forensics-stat-value">{stats.total_analyses}</div>
            <div className="forensics-stat-label">Total Analyses</div>
          </div>
          <div className="forensics-stat-card">
            <Icon name="ShieldCheck" size={24} />
            <div className="forensics-stat-value">{stats.with_c2pa}</div>
            <div className="forensics-stat-label">With C2PA</div>
          </div>
          <div className="forensics-stat-card">
            <Icon name="AlertTriangle" size={24} />
            <div className="forensics-stat-value">{stats.with_findings}</div>
            <div className="forensics-stat-label">With Findings</div>
          </div>
          <div className="forensics-stat-card stat-card-warning">
            <Icon name="XCircle" size={24} />
            <div className="forensics-stat-value">{stats.critical_findings_total}</div>
            <div className="forensics-stat-label">Critical Issues</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="forensics-filters">
        <div className="filter-group">
          <label>Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All Statuses</option>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Verification</label>
          <select
            value={verificationFilter}
            onChange={(e) => setVerificationFilter(e.target.value)}
          >
            <option value="">All</option>
            {VERIFICATION_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <button
          className="btn btn-sm btn-secondary"
          onClick={() => {
            setStatusFilter('');
            setVerificationFilter('');
          }}
        >
          <Icon name="X" size={14} />
          Clear
        </button>
      </div>

      <div className="forensics-layout">
        {/* Analysis List */}
        <div className="forensics-list-container">
          {analyses.length === 0 ? (
            <div className="content-empty">
              <Icon name="ImageOff" size={64} />
              <h2>No Analyses Found</h2>
              <p>Analyze an image to detect manipulation and verify authenticity.</p>
              <button className="btn btn-primary" onClick={() => setShowAnalyzeModal(true)}>
                <Icon name="Plus" size={16} />
                New Analysis
              </button>
            </div>
          ) : (
            <div className="forensics-list">
              {analyses.map((analysis) => (
                <div
                  key={analysis.id}
                  className={`analysis-card ${selectedAnalysis?.id === analysis.id ? 'selected' : ''}`}
                  onClick={() => handleSelectAnalysis(analysis)}
                >
                  {selectedAnalysis?.id === analysis.id && (
                    <div className="selection-indicator" />
                  )}

                  <div className="analysis-header">
                    <div className="analysis-file-info">
                      <Icon name="Image" size={18} />
                      <div className="file-details">
                        <span className="filename">{analysis.filename}</span>
                        <span className="file-meta">
                          {analysis.file_type} - {formatFileSize(analysis.file_size)}
                        </span>
                      </div>
                    </div>
                    <div className="analysis-badges">
                      <span
                        className={`badge badge-${STATUS_COLORS[analysis.status as AnalysisStatus]}`}
                      >
                        {STATUS_LABELS[analysis.status as AnalysisStatus]}
                      </span>
                      <span
                        className="verification-badge"
                        style={{
                          backgroundColor:
                            VERIFICATION_COLORS[analysis.verification_status as VerificationStatus],
                        }}
                      >
                        <Icon
                          name={getVerificationIcon(analysis.verification_status) as any}
                          size={12}
                        />
                        {VERIFICATION_LABELS[analysis.verification_status as VerificationStatus]}
                      </span>
                    </div>
                  </div>

                  <div className="analysis-indicators">
                    {analysis.exif_data && (
                      <span className="indicator" title="Has EXIF data">
                        <Icon name="Camera" size={14} />
                        EXIF
                      </span>
                    )}
                    {analysis.c2pa_data?.has_manifest && (
                      <span className="indicator indicator-c2pa" title="Has C2PA credentials">
                        <Icon name="ShieldCheck" size={14} />
                        C2PA
                      </span>
                    )}
                    {analysis.ela_result && (
                      <span className="indicator" title="ELA analysis">
                        <Icon name="Layers" size={14} />
                        ELA
                      </span>
                    )}
                    {analysis.exif_data?.gps?.latitude && (
                      <span className="indicator" title="Has GPS data">
                        <Icon name="MapPin" size={14} />
                        GPS
                      </span>
                    )}
                  </div>

                  {analysis.findings_count > 0 && (
                    <div className="analysis-findings-summary">
                      <Icon name="AlertTriangle" size={14} />
                      <span>
                        {analysis.findings_count} finding{analysis.findings_count !== 1 ? 's' : ''}
                        {analysis.critical_findings > 0 && (
                          <span className="critical-count">
                            ({analysis.critical_findings} critical)
                          </span>
                        )}
                      </span>
                    </div>
                  )}

                  <div className="analysis-meta">
                    <span className="meta-item">
                      <Icon name="Clock" size={12} />
                      {formatDate(analysis.analyzed_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {(offset > 0 || hasMore) && (
            <div className="forensics-pagination">
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setOffset(Math.max(0, offset - 20))}
                disabled={offset === 0}
              >
                <Icon name="ChevronLeft" size={14} />
                Previous
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setOffset(offset + 20)}
                disabled={!hasMore}
              >
                Next
                <Icon name="ChevronRight" size={14} />
              </button>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {selectedAnalysis && (
          <div className="forensics-detail-panel">
            <div className="detail-header">
              <h3>{selectedAnalysis.filename}</h3>
              <div className="detail-header-actions">
                <AIAnalystButton
                  shard="media-forensics"
                  targetId={selectedAnalysis.id}
                  context={aiAnalystContext}
                  label="AI Analysis"
                  variant="secondary"
                  size="sm"
                />
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => handleReanalyze(selectedAnalysis.id)}
                  title="Re-analyze"
                >
                  <Icon name="RefreshCw" size={14} />
                </button>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => handleDeleteAnalysis(selectedAnalysis.id)}
                  title="Delete"
                >
                  <Icon name="Trash2" size={14} />
                </button>
                <button className="close-btn" onClick={handleCloseDetail} title="Close">
                  <Icon name="X" size={16} />
                </button>
              </div>
            </div>

            {/* Verification Status Banner */}
            <div
              className="verification-banner"
              style={{
                backgroundColor:
                  VERIFICATION_COLORS[selectedAnalysis.verification_status as VerificationStatus],
              }}
            >
              <Icon
                name={getVerificationIcon(selectedAnalysis.verification_status) as any}
                size={20}
              />
              <span>
                {VERIFICATION_LABELS[selectedAnalysis.verification_status as VerificationStatus]}
              </span>
            </div>

            {/* Detail Tabs */}
            <div className="detail-tabs">
              <button
                className={`detail-tab ${detailTab === 'exif' ? 'active' : ''}`}
                onClick={() => setDetailTab('exif')}
              >
                <Icon name="Camera" size={14} />
                EXIF
              </button>
              <button
                className={`detail-tab ${detailTab === 'c2pa' ? 'active' : ''}`}
                onClick={() => setDetailTab('c2pa')}
                disabled={!selectedAnalysis.c2pa_data?.has_manifest}
              >
                <Icon name="ShieldCheck" size={14} />
                C2PA
                {selectedAnalysis.c2pa_data?.has_manifest && (
                  <span className="tab-badge">
                    <Icon name="Check" size={10} />
                  </span>
                )}
              </button>
              <button
                className={`detail-tab ${detailTab === 'ela' ? 'active' : ''}`}
                onClick={() => setDetailTab('ela')}
              >
                <Icon name="Layers" size={14} />
                ELA
              </button>
              <button
                className={`detail-tab ${detailTab === 'sun' ? 'active' : ''}`}
                onClick={() => setDetailTab('sun')}
                disabled={!selectedAnalysis.exif_data?.gps?.latitude}
              >
                <Icon name="Sun" size={14} />
                Sun
              </button>
              <button
                className={`detail-tab ${detailTab === 'similar' ? 'active' : ''}`}
                onClick={() => setDetailTab('similar')}
              >
                <Icon name="Images" size={14} />
                Similar
              </button>
              <button
                className={`detail-tab ${detailTab === 'warnings' ? 'active' : ''}`}
                onClick={() => setDetailTab('warnings')}
              >
                <Icon name="AlertTriangle" size={14} />
                Warnings
                {selectedAnalysis.findings_count > 0 && (
                  <span className="tab-count">{selectedAnalysis.findings_count}</span>
                )}
              </button>
            </div>

            {/* Tab Content */}
            <div className="detail-content">
              {detailTab === 'exif' && <ExifPanel analysis={selectedAnalysis} />}
              {detailTab === 'c2pa' && <C2PAPanel analysis={selectedAnalysis} />}
              {detailTab === 'ela' && (
                <ELAViewer analysis={selectedAnalysis} onRegenerate={fetchAnalyses} />
              )}
              {detailTab === 'sun' && <SunPositionPanel analysis={selectedAnalysis} />}
              {detailTab === 'similar' && (
                <SimilarImagesPanel analysis={selectedAnalysis} onSearch={fetchAnalyses} />
              )}
              {detailTab === 'warnings' && <WarningsPanel analysis={selectedAnalysis} />}
            </div>
          </div>
        )}
      </div>

      {/* Analyze Modal */}
      {showAnalyzeModal && (
        <div className="modal-overlay" onClick={() => setShowAnalyzeModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <Icon name="ImagePlus" size={20} />
                New Media Analysis
              </h3>
              <button className="close-btn" onClick={() => setShowAnalyzeModal(false)}>
                <Icon name="X" size={16} />
              </button>
            </div>
            <div className="modal-body">
              {/* Mode Toggle */}
              <div className="mode-toggle">
                <button
                  className={`mode-btn ${uploadMode === 'upload' ? 'active' : ''}`}
                  onClick={() => setUploadMode('upload')}
                  disabled={analyzing}
                >
                  <Icon name="Upload" size={16} />
                  Upload File
                </button>
                <button
                  className={`mode-btn ${uploadMode === 'select' ? 'active' : ''}`}
                  onClick={() => setUploadMode('select')}
                  disabled={analyzing}
                >
                  <Icon name="FileSearch" size={16} />
                  Select Document
                </button>
              </div>

              {uploadMode === 'upload' ? (
                <div className="form-group">
                  <label>Upload Image File</label>
                  <div
                    className={`upload-dropzone ${dragActive ? 'drag-active' : ''} ${selectedFile ? 'has-file' : ''}`}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                  >
                    {selectedFile ? (
                      <div className="selected-file">
                        <Icon name="Image" size={24} />
                        <div className="file-info">
                          <span className="file-name">{selectedFile.name}</span>
                          <span className="file-size">
                            {(selectedFile.size / 1024).toFixed(1)} KB
                          </span>
                        </div>
                        <button
                          className="btn btn-sm btn-ghost"
                          onClick={() => setSelectedFile(null)}
                          title="Remove file"
                        >
                          <Icon name="X" size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="dropzone-content">
                        <Icon name="Upload" size={32} />
                        <p>Drag & drop an image here, or click to browse</p>
                        <span className="supported-formats">
                          Supports: JPEG, PNG, TIFF, WebP, GIF, BMP
                        </span>
                      </div>
                    )}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/tiff,image/webp,image/gif,image/bmp,.jpg,.jpeg,.png,.tiff,.tif,.webp,.gif,.bmp"
                      onChange={handleFileSelect}
                      disabled={analyzing}
                      style={{ display: 'none' }}
                      id="file-upload-input"
                    />
                    {!selectedFile && (
                      <label htmlFor="file-upload-input" className="btn btn-secondary btn-sm">
                        <Icon name="FolderOpen" size={14} />
                        Browse Files
                      </label>
                    )}
                  </div>
                </div>
              ) : (
                <div className="form-group">
                  <label>Select Image Document</label>
                  <select
                    value={selectedDocId}
                    onChange={(e) => setSelectedDocId(e.target.value)}
                    disabled={analyzing}
                  >
                    <option value="">-- Select an image --</option>
                    {documents.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.filename} ({doc.file_type})
                      </option>
                    ))}
                  </select>
                  {documents.length === 0 && (
                    <span className="form-hint">
                      No processed image documents found. Use "Upload File" to add new images.
                    </span>
                  )}
                </div>
              )}

              <div className="form-group">
                <label>Analysis Options</label>
                <div className="checkbox-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={analyzeOptions.run_ela}
                      onChange={(e) =>
                        setAnalyzeOptions({ ...analyzeOptions, run_ela: e.target.checked })
                      }
                    />
                    <span>Run Error Level Analysis (ELA)</span>
                  </label>
                  {uploadMode === 'select' && (
                    <>
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={analyzeOptions.run_sun_position}
                          onChange={(e) =>
                            setAnalyzeOptions({ ...analyzeOptions, run_sun_position: e.target.checked })
                          }
                        />
                        <span>Verify Sun Position (requires GPS)</span>
                      </label>
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={analyzeOptions.run_similar_search}
                          onChange={(e) =>
                            setAnalyzeOptions({
                              ...analyzeOptions,
                              run_similar_search: e.target.checked,
                            })
                          }
                        />
                        <span>Search for Similar Images</span>
                      </label>
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowAnalyzeModal(false)}
                disabled={analyzing}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleAnalyzeDocument}
                disabled={analyzing || (uploadMode === 'upload' ? !selectedFile : !selectedDocId)}
              >
                {analyzing ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Icon name="Zap" size={16} />
                    Analyze
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

export default MediaForensicsPage;
