/**
 * IngestQueuePage - Queue management page
 *
 * Features:
 * - List of pending jobs
 * - Job status (queued, processing, completed, failed)
 * - Retry failed jobs button
 * - Filter by status
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useConfirm } from '../../context/ConfirmContext';
import { usePending, useRetryJob } from './api';
import type { PendingJob } from './api';

type StatusFilter = 'all' | 'pending' | 'processing' | 'completed' | 'failed';

export function IngestQueuePage() {
  const { toast } = useToast();
  const { confirm } = useConfirm();
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [limit, setLimit] = useState(50);

  const { data: pendingData, loading, error, refetch } = usePending(limit);
  const { retry: retryJobMutation, loading: retrying } = useRetryJob();

  // Auto-refresh queue
  useEffect(() => {
    const interval = setInterval(() => {
      refetch();
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, [refetch]);

  const handleRetry = async (jobId: string, filename: string) => {
    const confirmed = await confirm(
      `Retry job for "${filename}"?`,
      'This will requeue the failed job for processing.'
    );

    if (!confirmed) return;

    try {
      await retryJobMutation(jobId);
      toast(`Retrying job: ${filename}`, 'success');
      refetch();
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Retry failed', 'error');
    }
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const getStatusColor = (status: string): string => {
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

  const getStatusIcon = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'CheckCircle';
      case 'processing':
        return 'Loader';
      case 'failed':
      case 'dead':
        return 'XCircle';
      default:
        return 'Clock';
    }
  };

  const filteredJobs = pendingData?.jobs ?? [];
  const jobCount = pendingData?.count ?? 0;

  return (
    <div className="ingest-queue-page">
      <header className="page-header">
        <div className="page-title">
          <button className="back-button" onClick={() => navigate('/ingest')}>
            <Icon name="ArrowLeft" size={20} />
          </button>
          <Icon name="List" size={28} />
          <div>
            <h1>Ingest Queue</h1>
            <p className="page-description">
              {jobCount} job{jobCount !== 1 ? 's' : ''} in queue
            </p>
          </div>
        </div>
        <div className="page-actions">
          <button className="button-secondary" onClick={() => refetch()}>
            <Icon name="RefreshCw" size={18} />
            Refresh
          </button>
        </div>
      </header>

      {/* Filters */}
      <section className="filters-section">
        <div className="filter-group">
          <label>Status:</label>
          <div className="filter-buttons">
            <button
              className={`filter-button ${statusFilter === 'all' ? 'active' : ''}`}
              onClick={() => setStatusFilter('all')}
            >
              All
            </button>
            <button
              className={`filter-button ${statusFilter === 'pending' ? 'active' : ''}`}
              onClick={() => setStatusFilter('pending')}
            >
              Pending
            </button>
            <button
              className={`filter-button ${statusFilter === 'processing' ? 'active' : ''}`}
              onClick={() => setStatusFilter('processing')}
            >
              Processing
            </button>
            <button
              className={`filter-button ${statusFilter === 'completed' ? 'active' : ''}`}
              onClick={() => setStatusFilter('completed')}
            >
              Completed
            </button>
            <button
              className={`filter-button ${statusFilter === 'failed' ? 'active' : ''}`}
              onClick={() => setStatusFilter('failed')}
            >
              Failed
            </button>
          </div>
        </div>

        <div className="filter-group">
          <label>Show:</label>
          <select value={limit} onChange={e => setLimit(Number(e.target.value))}>
            <option value={25}>25 jobs</option>
            <option value={50}>50 jobs</option>
            <option value={100}>100 jobs</option>
            <option value={250}>250 jobs</option>
          </select>
        </div>
      </section>

      {/* Jobs List */}
      <section className="jobs-section">
        {loading && !pendingData ? (
          <div className="loading-state">
            <Icon name="Loader" size={32} className="spinner" />
            <p>Loading queue...</p>
          </div>
        ) : error ? (
          <div className="error-state">
            <Icon name="AlertCircle" size={32} />
            <p>Failed to load queue</p>
            <button className="button-primary" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div className="empty-state">
            <Icon name="Inbox" size={48} />
            <p>No jobs in queue</p>
          </div>
        ) : (
          <div className="jobs-table">
            <div className="table-header">
              <div className="col-status">Status</div>
              <div className="col-filename">Filename</div>
              <div className="col-category">Category</div>
              <div className="col-priority">Priority</div>
              <div className="col-route">Route</div>
              <div className="col-created">Created</div>
              <div className="col-actions">Actions</div>
            </div>
            <div className="table-body">
              {filteredJobs.map((job: PendingJob) => (
                <div key={job.job_id} className="table-row">
                  <div className="col-status">
                    <span
                      className="status-badge"
                      style={{ backgroundColor: getStatusColor('pending') }}
                    >
                      <Icon name={getStatusIcon('pending')} size={14} />
                      Pending
                    </span>
                  </div>
                  <div className="col-filename">
                    <div className="filename-cell">
                      <Icon name="FileText" size={16} />
                      <span title={job.filename}>{job.filename}</span>
                    </div>
                  </div>
                  <div className="col-category">
                    <span className="category-badge">{job.category}</span>
                  </div>
                  <div className="col-priority">
                    <span className={`priority-badge priority-${job.priority}`}>{job.priority}</span>
                  </div>
                  <div className="col-route">
                    <div className="route-cell">
                      {job.route.slice(0, 3).map((worker, idx) => (
                        <span key={idx} className="route-step">
                          {worker}
                        </span>
                      ))}
                      {job.route.length > 3 && (
                        <span className="route-more">+{job.route.length - 3}</span>
                      )}
                    </div>
                  </div>
                  <div className="col-created">{formatDate(job.created_at)}</div>
                  <div className="col-actions">
                    <button
                      className="button-icon"
                      onClick={() => handleRetry(job.job_id, job.filename)}
                      disabled={retrying}
                      title="Retry job"
                    >
                      <Icon name="RotateCw" size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <style>{`
        .ingest-queue-page {
          padding: 2rem;
          max-width: 1600px;
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

        .back-button {
          background: transparent;
          border: none;
          color: #9ca3af;
          cursor: pointer;
          padding: 0.25rem;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 0.375rem;
          transition: all 0.15s;
        }

        .back-button:hover {
          background: #374151;
          color: #f9fafb;
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

        .filters-section {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1.5rem;
          margin-bottom: 1.5rem;
          display: flex;
          gap: 2rem;
          flex-wrap: wrap;
          align-items: center;
        }

        .filter-group {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .filter-group label {
          font-size: 0.875rem;
          font-weight: 500;
          color: #9ca3af;
        }

        .filter-buttons {
          display: flex;
          gap: 0.5rem;
        }

        .filter-button {
          padding: 0.5rem 1rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          color: #9ca3af;
          font-size: 0.875rem;
          cursor: pointer;
          transition: all 0.15s;
        }

        .filter-button:hover {
          background: #1f2937;
          color: #f9fafb;
        }

        .filter-button.active {
          background: #6366f1;
          border-color: #6366f1;
          color: white;
        }

        .filter-group select {
          padding: 0.5rem 1rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          color: #f9fafb;
          font-size: 0.875rem;
          cursor: pointer;
        }

        .jobs-section {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          overflow: hidden;
        }

        .jobs-table {
          width: 100%;
        }

        .table-header,
        .table-row {
          display: grid;
          grid-template-columns: 120px 1fr 120px 100px 200px 180px 80px;
          gap: 1rem;
          padding: 1rem 1.5rem;
          align-items: center;
        }

        .table-header {
          background: #111827;
          border-bottom: 1px solid #374151;
          font-size: 0.75rem;
          font-weight: 600;
          color: #9ca3af;
          text-transform: uppercase;
        }

        .table-row {
          border-bottom: 1px solid #374151;
          font-size: 0.875rem;
          transition: background 0.15s;
        }

        .table-row:hover {
          background: #111827;
        }

        .table-row:last-child {
          border-bottom: none;
        }

        .status-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.375rem 0.75rem;
          border-radius: 0.375rem;
          font-size: 0.75rem;
          font-weight: 500;
          color: white;
        }

        .filename-cell {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: #f9fafb;
          overflow: hidden;
        }

        .filename-cell span {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .category-badge {
          display: inline-block;
          padding: 0.25rem 0.625rem;
          background: #374151;
          border-radius: 0.25rem;
          font-size: 0.75rem;
          color: #9ca3af;
          text-transform: capitalize;
        }

        .priority-badge {
          display: inline-block;
          padding: 0.25rem 0.625rem;
          border-radius: 0.25rem;
          font-size: 0.75rem;
          text-transform: capitalize;
        }

        .priority-user {
          background: #3730a3;
          color: #c7d2fe;
        }

        .priority-batch {
          background: #374151;
          color: #9ca3af;
        }

        .priority-reprocess {
          background: #991b1b;
          color: #fecaca;
        }

        .route-cell {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          flex-wrap: wrap;
        }

        .route-step {
          font-size: 0.75rem;
          padding: 0.125rem 0.5rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.25rem;
          color: #9ca3af;
        }

        .route-more {
          font-size: 0.75rem;
          color: #6b7280;
        }

        .col-created {
          font-size: 0.75rem;
          color: #9ca3af;
        }

        .col-actions {
          display: flex;
          gap: 0.5rem;
          justify-content: flex-end;
        }

        .loading-state,
        .error-state,
        .empty-state {
          padding: 4rem 2rem;
          text-align: center;
          color: #9ca3af;
        }

        .loading-state p,
        .error-state p,
        .empty-state p {
          margin: 1rem 0 0 0;
        }

        .error-state button {
          margin-top: 1rem;
        }

        .button-primary,
        .button-secondary,
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

        .button-secondary {
          background: #374151;
          color: #f9fafb;
          border-color: #4b5563;
        }

        .button-secondary:hover {
          background: #4b5563;
        }

        .button-icon {
          padding: 0.375rem;
          background: transparent;
          color: #9ca3af;
          border: none;
        }

        .button-icon:hover:not(:disabled) {
          background: #374151;
          color: #f9fafb;
        }

        .button-icon:disabled {
          opacity: 0.5;
          cursor: not-allowed;
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
