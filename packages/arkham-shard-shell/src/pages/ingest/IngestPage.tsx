/**
 * IngestPage - Main ingest page
 *
 * Features:
 * - File upload dropzone (drag & drop)
 * - Upload button
 * - Queue statistics display
 * - Recent jobs list
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useUploadBatch, useQueue, usePending, useIngestSettings, useUpdateIngestSettings } from './api';
import type { PendingJob, OcrMode, IngestSettings, IngestSettingsUpdate } from './api';

export function IngestPage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [ocrMode, setOcrMode] = useState<OcrMode>('auto');
  const [showSettings, setShowSettings] = useState(false);

  const { uploadBatch, loading: uploading } = useUploadBatch();
  const { data: queueStats, loading: loadingQueue, refetch: refetchQueue } = useQueue();
  const { data: pendingData, loading: loadingPending, refetch: refetchPending } = usePending(10);
  const { data: settings, loading: loadingSettings, refetch: refetchSettings } = useIngestSettings();
  const { update: updateSettings, loading: savingSettings } = useUpdateIngestSettings();

  // Auto-refresh queue stats and pending jobs
  useEffect(() => {
    const interval = setInterval(() => {
      refetchQueue();
      refetchPending();
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, [refetchQueue, refetchPending]);

  // Drag and drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      setSelectedFiles(prev => [...prev, ...files]);
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    if (files.length > 0) {
      setSelectedFiles(prev => [...prev, ...files]);
    }
  }, []);

  const handleRemoveFile = useCallback((index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) {
      toast.error('Please select files to upload');
      return;
    }

    try {
      const result = await uploadBatch(selectedFiles, 'user', ocrMode);
      if (result.failed > 0) {
        toast.warning(`Uploaded ${result.total_files} file(s), ${result.failed} failed`);
      } else {
        toast.success(`Uploaded ${result.total_files} file(s)`);
      }
      setSelectedFiles([]);
      refetchQueue();
      refetchPending();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Upload failed');
    }
  }, [selectedFiles, uploadBatch, toast, refetchQueue, refetchPending, ocrMode]);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSettingChange = useCallback(
    async (key: keyof IngestSettings, value: boolean | number | string) => {
      try {
        await updateSettings({ [key]: value } as IngestSettingsUpdate);
        refetchSettings();
        toast.success('Setting updated');
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Failed to update setting');
      }
    },
    [updateSettings, refetchSettings, toast]
  );

  const _getStatusColor = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'completed':
        return '#22c55e';
      case 'processing':
        return '#3b82f6';
      case 'failed':
      case 'dead':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };
  void _getStatusColor;

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="ingest-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Upload" size={28} />
          <div>
            <h1>Ingest</h1>
            <p className="page-description">Upload and process documents</p>
          </div>
        </div>
        <div className="page-actions">
          <button
            className={`button-secondary ${showSettings ? 'active' : ''}`}
            onClick={() => setShowSettings(!showSettings)}
          >
            <Icon name="Settings" size={18} />
            Settings
          </button>
          <button className="button-secondary" onClick={() => navigate('/ingest/queue')}>
            <Icon name="List" size={18} />
            View Queue
          </button>
        </div>
      </header>

      {/* Queue Statistics – click a card to open View Queue with that filter */}
      <section className="stats-grid">
        <button
          type="button"
          className="stat-card stat-card-clickable"
          onClick={() => navigate('/ingest/queue?status=pending')}
          title="View queue filtered by Pending"
        >
          <Icon name="Clock" size={24} className="stat-icon" style={{ color: '#6b7280' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingQueue ? '...' : queueStats?.pending ?? 0}</div>
            <div className="stat-label">Pending</div>
          </div>
        </button>
        <button
          type="button"
          className="stat-card stat-card-clickable"
          onClick={() => navigate('/ingest/queue?status=processing')}
          title="View queue filtered by Processing"
        >
          <Icon name="Loader" size={24} className="stat-icon" style={{ color: '#3b82f6' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingQueue ? '...' : queueStats?.processing ?? 0}</div>
            <div className="stat-label">Processing</div>
          </div>
        </button>
        <button
          type="button"
          className="stat-card stat-card-clickable"
          onClick={() => navigate('/ingest/queue?status=completed')}
          title="View queue filtered by Completed"
        >
          <Icon name="CheckCircle" size={24} className="stat-icon" style={{ color: '#22c55e' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingQueue ? '...' : queueStats?.completed ?? 0}</div>
            <div className="stat-label">Completed</div>
          </div>
        </button>
        <button
          type="button"
          className="stat-card stat-card-clickable"
          onClick={() => navigate('/ingest/queue?status=failed')}
          title="View queue filtered by Failed"
        >
          <Icon name="XCircle" size={24} className="stat-icon" style={{ color: '#ef4444' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingQueue ? '...' : queueStats?.failed ?? 0}</div>
            <div className="stat-label">Failed</div>
          </div>
        </button>
      </section>

      {/* Pipeline Settings Panel */}
      {showSettings && (
        <section className="settings-panel">
          <div className="settings-header">
            <h2>
              <Icon name="Settings" size={20} />
              Pipeline Settings
            </h2>
            <p className="settings-description">
              Configure optimization features for the ingest pipeline. Changes apply to new uploads.
            </p>
          </div>

          {loadingSettings ? (
            <div className="loading-state">
              <Icon name="Loader" size={24} className="spinner" />
              Loading settings...
            </div>
          ) : settings ? (
            <div className="settings-content">
              {/* Ingest Optimizations */}
              <div className="settings-group">
                <h3>Ingest Optimizations</h3>
                <div className="settings-grid">
                  <label className="setting-toggle">
                    <input
                      type="checkbox"
                      checked={settings.ingest_enable_deduplication}
                      onChange={e =>
                        handleSettingChange('ingest_enable_deduplication', e.target.checked)
                      }
                      disabled={savingSettings}
                    />
                    <span className="toggle-slider" />
                    <div className="toggle-content">
                      <span className="toggle-label">Deduplication</span>
                      <span className="toggle-description">
                        Skip processing duplicate files (by checksum)
                      </span>
                    </div>
                  </label>

                  <label className="setting-toggle">
                    <input
                      type="checkbox"
                      checked={settings.ingest_enable_validation}
                      onChange={e =>
                        handleSettingChange('ingest_enable_validation', e.target.checked)
                      }
                      disabled={savingSettings}
                    />
                    <span className="toggle-slider" />
                    <div className="toggle-content">
                      <span className="toggle-label">File Validation</span>
                      <span className="toggle-description">
                        Verify file integrity before processing
                      </span>
                    </div>
                  </label>

                  <label className="setting-toggle">
                    <input
                      type="checkbox"
                      checked={settings.ingest_enable_downscale}
                      onChange={e =>
                        handleSettingChange('ingest_enable_downscale', e.target.checked)
                      }
                      disabled={savingSettings}
                    />
                    <span className="toggle-slider" />
                    <div className="toggle-content">
                      <span className="toggle-label">DPI Downscaling</span>
                      <span className="toggle-description">
                        Downscale high-DPI images (&gt;200) for memory savings
                      </span>
                    </div>
                  </label>

                  <label className="setting-toggle">
                    <input
                      type="checkbox"
                      checked={settings.ingest_skip_blank_pages}
                      onChange={e =>
                        handleSettingChange('ingest_skip_blank_pages', e.target.checked)
                      }
                      disabled={savingSettings}
                    />
                    <span className="toggle-slider" />
                    <div className="toggle-content">
                      <span className="toggle-label">Skip Blank Pages</span>
                      <span className="toggle-description">
                        Automatically detect and skip blank/empty pages
                      </span>
                    </div>
                  </label>
                </div>
              </div>

              {/* OCR Optimizations */}
              <div className="settings-group">
                <h3>OCR Optimizations</h3>
                <div className="settings-grid">
                  <label className="setting-toggle">
                    <input
                      type="checkbox"
                      checked={settings.ocr_enable_escalation}
                      onChange={e =>
                        handleSettingChange('ocr_enable_escalation', e.target.checked)
                      }
                      disabled={savingSettings}
                    />
                    <span className="toggle-slider" />
                    <div className="toggle-content">
                      <span className="toggle-label">Confidence Escalation</span>
                      <span className="toggle-description">
                        Re-OCR with Qwen when Paddle confidence is low
                      </span>
                    </div>
                  </label>

                  <label className="setting-toggle">
                    <input
                      type="checkbox"
                      checked={settings.ocr_enable_cache}
                      onChange={e => handleSettingChange('ocr_enable_cache', e.target.checked)}
                      disabled={savingSettings}
                    />
                    <span className="toggle-slider" />
                    <div className="toggle-content">
                      <span className="toggle-label">Result Caching</span>
                      <span className="toggle-description">
                        Cache OCR results to skip re-processing identical images
                      </span>
                    </div>
                  </label>
                </div>

                <div className="settings-row">
                  <div className="setting-input">
                    <label htmlFor="ocr-parallel">Parallel Pages</label>
                    <input
                      id="ocr-parallel"
                      type="number"
                      min="1"
                      max="16"
                      value={settings.ocr_parallel_pages}
                      onChange={e =>
                        handleSettingChange('ocr_parallel_pages', parseInt(e.target.value, 10))
                      }
                      disabled={savingSettings}
                    />
                    <span className="input-hint">Max concurrent page OCR (1-16)</span>
                  </div>

                  <div className="setting-input">
                    <label htmlFor="ocr-threshold">Confidence Threshold</label>
                    <input
                      id="ocr-threshold"
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      value={settings.ocr_confidence_threshold}
                      onChange={e =>
                        handleSettingChange('ocr_confidence_threshold', parseFloat(e.target.value))
                      }
                      disabled={savingSettings}
                    />
                    <span className="input-hint">Escalate below this (0.0-1.0)</span>
                  </div>

                  <div className="setting-input">
                    <label htmlFor="cache-ttl">Cache TTL (days)</label>
                    <input
                      id="cache-ttl"
                      type="number"
                      min="1"
                      max="90"
                      value={settings.ocr_cache_ttl_days}
                      onChange={e =>
                        handleSettingChange('ocr_cache_ttl_days', parseInt(e.target.value, 10))
                      }
                      disabled={savingSettings}
                    />
                    <span className="input-hint">Days to keep cached results</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <Icon name="AlertCircle" size={24} />
              <p>Failed to load settings</p>
            </div>
          )}
        </section>
      )}

      {/* File Upload Dropzone */}
      <section className="upload-section">
        <div
          className={`dropzone ${isDragging ? 'dragging' : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <Icon name="Upload" size={48} />
          <h3>Drop files here or click to browse</h3>
          <p>Supports PDF, images, text documents, and archives</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </div>

        {/* Selected Files */}
        {selectedFiles.length > 0 && (
          <div className="selected-files">
            <div className="selected-files-header">
              <h3>Selected Files ({selectedFiles.length})</h3>
              <button className="button-secondary" onClick={() => setSelectedFiles([])}>
                Clear All
              </button>
            </div>
            <div className="files-list">
              {selectedFiles.map((file, index) => (
                <div key={index} className="file-item">
                  <Icon name="FileText" size={20} />
                  <div className="file-info">
                    <div className="file-name">{file.name}</div>
                    <div className="file-size">{formatFileSize(file.size)}</div>
                  </div>
                  <button
                    className="button-icon"
                    onClick={e => {
                      e.stopPropagation();
                      handleRemoveFile(index);
                    }}
                  >
                    <Icon name="X" size={16} />
                  </button>
                </div>
              ))}
            </div>
            <div className="upload-options">
              <div className="option-group">
                <label className="option-label">
                  <Icon name="ScanText" size={16} />
                  OCR Engine
                </label>
                <div className="ocr-mode-selector">
                  <button
                    className={`mode-button ${ocrMode === 'auto' ? 'active' : ''}`}
                    onClick={() => setOcrMode('auto')}
                    title="Automatically select based on image quality"
                  >
                    <Icon name="Wand2" size={14} />
                    Auto
                  </button>
                  <button
                    className={`mode-button ${ocrMode === 'paddle_only' ? 'active' : ''}`}
                    onClick={() => setOcrMode('paddle_only')}
                    title="Fast OCR for printed/clear text"
                  >
                    <Icon name="Zap" size={14} />
                    Fast (Paddle)
                  </button>
                  <button
                    className={`mode-button ${ocrMode === 'qwen_only' ? 'active' : ''}`}
                    onClick={() => setOcrMode('qwen_only')}
                    title="VLM-based OCR for handwriting and complex layouts"
                  >
                    <Icon name="Brain" size={14} />
                    Quality (Qwen)
                  </button>
                </div>
              </div>
            </div>
            <div className="upload-actions">
              <button className="button-primary" onClick={handleUpload} disabled={uploading}>
                {uploading ? (
                  <>
                    <Icon name="Loader" size={18} className="spinner" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Icon name="Upload" size={18} />
                    Upload {selectedFiles.length} File{selectedFiles.length > 1 ? 's' : ''}
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </section>

      {/* Recent Jobs */}
      <section className="recent-jobs-section">
        <div className="section-header">
          <h2>
            <Icon name="Clock" size={20} />
            Recent Jobs
          </h2>
          {pendingData && pendingData.count > 10 && (
            <button className="button-link" onClick={() => navigate('/ingest/queue')}>
              View all {pendingData.count} jobs
            </button>
          )}
        </div>

        {loadingPending ? (
          <div className="loading-state">
            <Icon name="Loader" size={24} className="spinner" />
            Loading jobs...
          </div>
        ) : pendingData && pendingData.jobs.length > 0 ? (
          <div className="jobs-list">
            {pendingData.jobs.map((job: PendingJob) => (
              <div key={job.job_id} className="job-card">
                <div className="job-header">
                  <Icon name="FileText" size={20} />
                  <div className="job-info">
                    <div className="job-filename">{job.filename}</div>
                    <div className="job-meta">
                      <span className="job-category">{job.category}</span>
                      <span className="job-separator">•</span>
                      <span className="job-priority">Priority: {job.priority}</span>
                      <span className="job-separator">•</span>
                      <span className="job-time">{formatDate(job.created_at)}</span>
                    </div>
                  </div>
                </div>
                <div className="job-route">
                  {job.route.map((worker, idx) => (
                    <span key={idx} className="route-step">
                      {worker}
                      {idx < job.route.length - 1 && <Icon name="ChevronRight" size={14} />}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <Icon name="Inbox" size={48} />
            <p>No jobs in queue</p>
          </div>
        )}
      </section>

      <style>{`
        .ingest-page {
          padding: 2rem;
          max-width: 1400px;
          margin: 0 auto;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 2rem;
        }

        .page-title {
          display: flex;
          gap: 1rem;
          align-items: flex-start;
        }

        .page-title h1 {
          margin: 0;
          font-size: 1.875rem;
          font-weight: 600;
          color: #f9fafb;
        }

        .page-description {
          margin: 0.25rem 0 0 0;
          color: #9ca3af;
          font-size: 0.875rem;
        }

        .page-actions {
          display: flex;
          gap: 0.75rem;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem;
          margin-bottom: 2rem;
        }

        .stat-card {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1.25rem;
          display: flex;
          gap: 1rem;
          align-items: center;
        }

        .stat-card-clickable {
          cursor: pointer;
          text-align: center;
          font: inherit;
          color: inherit;
        }

        .stat-card-clickable:hover {
          border-color: #6366f1;
          background: #252d3a;
        }

        .stat-icon {
          opacity: 0.8;
        }

        .stat-content {
          flex: 1;
        }

        .stat-value {
          font-size: 1.875rem;
          font-weight: 600;
          color: #f9fafb;
          line-height: 1;
        }

        .stat-label {
          font-size: 0.875rem;
          color: #9ca3af;
          margin-top: 0.25rem;
        }

        .upload-section {
          margin-bottom: 2rem;
        }

        .dropzone {
          background: #1f2937;
          border: 2px dashed #4b5563;
          border-radius: 0.75rem;
          padding: 3rem;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
        }

        .dropzone:hover {
          border-color: #6366f1;
          background: #1f2937;
        }

        .dropzone.dragging {
          border-color: #6366f1;
          background: #1e293b;
        }

        .dropzone h3 {
          margin: 1rem 0 0.5rem 0;
          color: #f9fafb;
          font-weight: 500;
        }

        .dropzone p {
          margin: 0;
          color: #9ca3af;
          font-size: 0.875rem;
        }

        .selected-files {
          margin-top: 1.5rem;
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1.5rem;
        }

        .selected-files-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }

        .selected-files-header h3 {
          margin: 0;
          font-size: 1rem;
          font-weight: 600;
          color: #f9fafb;
        }

        .files-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          margin-bottom: 1rem;
        }

        .file-item {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
        }

        .file-info {
          flex: 1;
        }

        .file-name {
          font-size: 0.875rem;
          color: #f9fafb;
        }

        .file-size {
          font-size: 0.75rem;
          color: #9ca3af;
          margin-top: 0.125rem;
        }

        .upload-options {
          margin-bottom: 1rem;
          padding: 1rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
        }

        .option-group {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .option-label {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.875rem;
          font-weight: 500;
          color: #d1d5db;
        }

        .ocr-mode-selector {
          display: flex;
          gap: 0.5rem;
        }

        .mode-button {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.5rem 0.75rem;
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          color: #9ca3af;
          font-size: 0.8125rem;
          cursor: pointer;
          transition: all 0.15s;
        }

        .mode-button:hover {
          background: #374151;
          color: #f9fafb;
        }

        .mode-button.active {
          background: #4f46e5;
          border-color: #6366f1;
          color: white;
        }

        .upload-actions {
          display: flex;
          justify-content: flex-end;
        }

        .recent-jobs-section {
          margin-bottom: 2rem;
        }

        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }

        .section-header h2 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .jobs-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .job-card {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1rem;
        }

        .job-header {
          display: flex;
          gap: 0.75rem;
          align-items: flex-start;
          margin-bottom: 0.75rem;
        }

        .job-info {
          flex: 1;
        }

        .job-filename {
          font-size: 0.875rem;
          font-weight: 500;
          color: #f9fafb;
        }

        .job-meta {
          font-size: 0.75rem;
          color: #9ca3af;
          margin-top: 0.25rem;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .job-separator {
          color: #4b5563;
        }

        .job-route {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          flex-wrap: wrap;
          font-size: 0.75rem;
          color: #9ca3af;
        }

        .route-step {
          display: flex;
          align-items: center;
          gap: 0.25rem;
        }

        .loading-state,
        .empty-state {
          padding: 3rem;
          text-align: center;
          color: #9ca3af;
        }

        .empty-state {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
        }

        .empty-state p {
          margin: 0.5rem 0 0 0;
        }

        .button-primary,
        .button-secondary,
        .button-link,
        .button-icon {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 1rem;
          border-radius: 0.375rem;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s;
          border: 1px solid transparent;
        }

        .button-primary {
          background: #6366f1;
          color: white;
          border-color: #6366f1;
        }

        .button-primary:hover:not(:disabled) {
          background: #4f46e5;
        }

        .button-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .button-secondary {
          background: #374151;
          color: #f9fafb;
          border-color: #4b5563;
        }

        .button-secondary:hover {
          background: #4b5563;
        }

        .button-secondary.active {
          background: #4f46e5;
          border-color: #6366f1;
          color: white;
        }

        .button-link {
          background: transparent;
          color: #6366f1;
          padding: 0.25rem 0.5rem;
        }

        .button-link:hover {
          color: #4f46e5;
        }

        .button-icon {
          padding: 0.375rem;
          background: transparent;
          color: #9ca3af;
        }

        .button-icon:hover {
          background: #374151;
          color: #f9fafb;
        }

        .spinner {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }

        /* Settings Panel */
        .settings-panel {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1.5rem;
          margin-bottom: 2rem;
        }

        .settings-header h2 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .settings-description {
          margin: 0.5rem 0 0 0;
          color: #9ca3af;
          font-size: 0.875rem;
        }

        .settings-content {
          margin-top: 1.5rem;
        }

        .settings-group {
          margin-bottom: 1.5rem;
        }

        .settings-group:last-child {
          margin-bottom: 0;
        }

        .settings-group h3 {
          margin: 0 0 1rem 0;
          font-size: 0.875rem;
          font-weight: 600;
          color: #d1d5db;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .settings-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 1rem;
        }

        .setting-toggle {
          display: flex;
          align-items: flex-start;
          gap: 0.75rem;
          padding: 0.875rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          cursor: pointer;
          transition: all 0.15s;
        }

        .setting-toggle:hover {
          border-color: #4b5563;
        }

        .setting-toggle input[type="checkbox"] {
          opacity: 0;
          width: 0;
          height: 0;
          position: absolute;
        }

        .toggle-slider {
          flex-shrink: 0;
          width: 2.75rem;
          height: 1.5rem;
          background: #374151;
          border-radius: 1.5rem;
          position: relative;
          transition: background-color 0.2s;
          cursor: pointer;
        }

        .toggle-slider::before {
          content: '';
          position: absolute;
          top: 2px;
          left: 2px;
          width: 1.25rem;
          height: 1.25rem;
          background: #9ca3af;
          border-radius: 50%;
          transition: transform 0.2s, background-color 0.2s;
        }

        .setting-toggle input:checked + .toggle-slider {
          background: #4f46e5;
        }

        .setting-toggle input:checked + .toggle-slider::before {
          transform: translateX(1.25rem);
          background: white;
        }

        .setting-toggle input:disabled + .toggle-slider {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .toggle-content {
          flex: 1;
        }

        .toggle-label {
          display: block;
          font-size: 0.875rem;
          font-weight: 500;
          color: #f9fafb;
        }

        .toggle-description {
          display: block;
          font-size: 0.75rem;
          color: #9ca3af;
          margin-top: 0.25rem;
        }

        .settings-row {
          display: flex;
          gap: 1rem;
          margin-top: 1rem;
          flex-wrap: wrap;
        }

        .setting-input {
          flex: 1;
          min-width: 140px;
        }

        .setting-input label {
          display: block;
          font-size: 0.75rem;
          font-weight: 500;
          color: #d1d5db;
          margin-bottom: 0.375rem;
        }

        .setting-input input[type="number"] {
          width: 100%;
          padding: 0.5rem 0.75rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          color: #f9fafb;
          font-size: 0.875rem;
        }

        .setting-input input[type="number"]:focus {
          outline: none;
          border-color: #6366f1;
        }

        .input-hint {
          display: block;
          font-size: 0.6875rem;
          color: #6b7280;
          margin-top: 0.25rem;
        }
      `}</style>
    </div>
  );
}
