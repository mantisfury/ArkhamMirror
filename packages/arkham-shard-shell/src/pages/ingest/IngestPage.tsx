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
import { useUploadBatch, useQueue, usePending } from './api';
import type { PendingJob } from './api';

export function IngestPage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const { uploadBatch, loading: uploading } = useUploadBatch();
  const { data: queueStats, loading: loadingQueue, refetch: refetchQueue } = useQueue();
  const { data: pendingData, loading: loadingPending, refetch: refetchPending } = usePending(10);

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
      const result = await uploadBatch(selectedFiles, 'user');
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
  }, [selectedFiles, uploadBatch, toast, refetchQueue, refetchPending]);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

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
          <button className="button-secondary" onClick={() => navigate('/ingest/queue')}>
            <Icon name="List" size={18} />
            View Queue
          </button>
        </div>
      </header>

      {/* Queue Statistics */}
      <section className="stats-grid">
        <div className="stat-card">
          <Icon name="Clock" size={24} className="stat-icon" style={{ color: '#6b7280' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingQueue ? '...' : queueStats?.pending ?? 0}</div>
            <div className="stat-label">Pending</div>
          </div>
        </div>
        <div className="stat-card">
          <Icon name="Loader" size={24} className="stat-icon" style={{ color: '#3b82f6' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingQueue ? '...' : queueStats?.processing ?? 0}</div>
            <div className="stat-label">Processing</div>
          </div>
        </div>
        <div className="stat-card">
          <Icon name="CheckCircle" size={24} className="stat-icon" style={{ color: '#22c55e' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingQueue ? '...' : queueStats?.completed ?? 0}</div>
            <div className="stat-label">Completed</div>
          </div>
        </div>
        <div className="stat-card">
          <Icon name="XCircle" size={24} className="stat-icon" style={{ color: '#ef4444' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingQueue ? '...' : queueStats?.failed ?? 0}</div>
            <div className="stat-label">Failed</div>
          </div>
        </div>
      </section>

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
      `}</style>
    </div>
  );
}
