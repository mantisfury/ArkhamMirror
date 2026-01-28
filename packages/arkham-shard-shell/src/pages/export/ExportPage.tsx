/**
 * ExportPage - Data export management
 *
 * Provides UI for creating and managing data exports in various formats.
 */

import { useState, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './ExportPage.css';

// Types
interface ExportJob {
  id: string;
  format: string;
  target: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  file_path: string | null;
  file_size: number | null;
  download_url: string | null;
  expires_at: string | null;
  error: string | null;
  filters: Record<string, unknown>;
  record_count: number;
  processing_time_ms: number;
  created_by: string;
  metadata: Record<string, unknown>;
}

interface FormatInfo {
  format: string;
  name: string;
  description: string;
  file_extension: string;
  mime_type: string;
  supports_flatten: boolean;
  supports_metadata: boolean;
  max_records: number | null;
  placeholder: boolean;
}

interface TargetInfo {
  target: string;
  name: string;
  description: string;
  available_formats: string[];
  estimated_record_count: number;
  supports_filters: boolean;
}

interface ExportStatistics {
  total_jobs: number;
  by_status: Record<string, number>;
  by_format: Record<string, number>;
  by_target: Record<string, number>;
  jobs_pending: number;
  jobs_processing: number;
  jobs_completed: number;
  jobs_failed: number;
  total_records_exported: number;
  total_file_size_bytes: number;
  avg_processing_time_ms: number;
  oldest_pending_job: string | null;
}

const STATUS_ICONS: Record<string, string> = {
  pending: 'Clock',
  processing: 'Loader2',
  completed: 'CheckCircle',
  failed: 'XCircle',
  cancelled: 'Ban',
};

const STATUS_COLORS: Record<string, string> = {
  pending: '#f59e0b',
  processing: '#3b82f6',
  completed: '#10b981',
  failed: '#ef4444',
  cancelled: '#6b7280',
};

export function ExportPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<'create' | 'jobs' | 'stats'>('create');

  // Export configuration state
  const [selectedFormat, setSelectedFormat] = useState<string>('json');
  const [selectedTarget, setSelectedTarget] = useState<string>('documents');
  const [includeMetadata, setIncludeMetadata] = useState(true);
  const [includeRelationships, setIncludeRelationships] = useState(true);
  const [maxRecords, setMaxRecords] = useState<string>('');
  // Timeline-specific options
  const [includeConflicts, setIncludeConflicts] = useState(false);
  const [includeGaps, setIncludeGaps] = useState(false);
  const [groupBy, setGroupBy] = useState<string>('');

  // Fetch data
  const { data: formats, loading: _formatsLoading } = useFetch<FormatInfo[]>('/api/export/formats');
  const { data: targets, loading: _targetsLoading } = useFetch<TargetInfo[]>('/api/export/targets');
  const { data: jobs, loading: jobsLoading, refetch: refetchJobs } = useFetch<{ jobs: ExportJob[]; total: number }>('/api/export/jobs', { backgroundRefetch: true });
  const { data: stats, loading: statsLoading, refetch: refetchStats } = useFetch<ExportStatistics>('/api/export/stats', { backgroundRefetch: true });

  // Auto-refresh jobs every 5 seconds when there are active jobs
  useEffect(() => {
    if (!jobs) return;

    const hasActiveJobs = jobs.jobs.some(j => j.status === 'pending' || j.status === 'processing');
    if (!hasActiveJobs) return;

    const interval = setInterval(() => {
      refetchJobs();
      refetchStats();
    }, 5000);

    return () => clearInterval(interval);
  }, [jobs, refetchJobs, refetchStats]);

  const handleCreateExport = async () => {
    try {
      const response = await fetch('/api/export/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          format: selectedFormat,
          target: selectedTarget,
          options: {
            include_metadata: includeMetadata,
            include_relationships: includeRelationships,
            max_records: maxRecords ? parseInt(maxRecords, 10) : null,
            // Timeline-specific options
            include_conflicts: selectedTarget === 'timeline' ? includeConflicts : false,
            include_gaps: selectedTarget === 'timeline' ? includeGaps : false,
            group_by: selectedTarget === 'timeline' && groupBy ? groupBy : null,
          },
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create export job');
      }

      const job = await response.json();
      toast.success(`Export job created: ${job.id.substring(0, 8)}`);
      setActiveTab('jobs');
      refetchJobs();
      refetchStats();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create export');
    }
  };

  const handleDownload = async (job: ExportJob) => {
    if (!job.download_url) return;

    try {
      // Trigger download
      window.location.href = job.download_url;
      toast.success('Download started');

      // Emit download event (will be tracked by backend)
    } catch (err) {
      toast.error('Failed to download export file');
    }
  };

  const handleCancelJob = async (jobId: string) => {
    try {
      const response = await fetch(`/api/export/jobs/${jobId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to cancel job');
      }

      toast.success('Export job cancelled');
      refetchJobs();
      refetchStats();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to cancel job');
    }
  };

  const formatFileSize = (bytes: number | null): string => {
    if (!bytes) return 'N/A';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  };

  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const renderCreateTab = () => {
    const currentTarget = targets?.find(t => t.target === selectedTarget);
    const availableFormats = currentTarget ?
      formats?.filter(f => currentTarget.available_formats.includes(f.format)) : formats;

    return (
      <div className="export-create">
        <div className="export-config">
          <div className="config-section">
            <h3>Export Target</h3>
            <p className="section-description">Choose what data to export</p>
            <div className="target-grid">
              {targets?.map(target => (
                <button
                  key={target.target}
                  className={`target-card ${selectedTarget === target.target ? 'active' : ''}`}
                  onClick={() => setSelectedTarget(target.target)}
                >
                  <div className="target-header">
                    <Icon name="Database" size={20} />
                    <span className="target-name">{target.name}</span>
                  </div>
                  <p className="target-description">{target.description}</p>
                  {target.estimated_record_count > 0 && (
                    <div className="target-count">
                      {target.estimated_record_count.toLocaleString()} records
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="config-section">
            <h3>Export Format</h3>
            <p className="section-description">Select output format</p>
            <div className="format-grid">
              {availableFormats?.map(format => (
                <button
                  key={format.format}
                  className={`format-card ${selectedFormat === format.format ? 'active' : ''} ${format.placeholder ? 'placeholder' : ''}`}
                  onClick={() => setSelectedFormat(format.format)}
                  disabled={format.placeholder}
                >
                  <div className="format-header">
                    <Icon name="FileText" size={20} />
                    <span className="format-name">{format.name}</span>
                    {format.placeholder && (
                      <span className="placeholder-badge">Coming Soon</span>
                    )}
                  </div>
                  <p className="format-description">{format.description}</p>
                  <div className="format-extension">{format.file_extension}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="config-section">
            <h3>Export Options</h3>
            <p className="section-description">Customize export output</p>
            <div className="options-grid">
              <label className="option-item">
                <input
                  type="checkbox"
                  checked={includeMetadata}
                  onChange={e => setIncludeMetadata(e.target.checked)}
                />
                <div>
                  <span className="option-label">Include Metadata</span>
                  <span className="option-description">Add system metadata and timestamps</span>
                </div>
              </label>

              <label className="option-item">
                <input
                  type="checkbox"
                  checked={includeRelationships}
                  onChange={e => setIncludeRelationships(e.target.checked)}
                />
                <div>
                  <span className="option-label">Include Relationships</span>
                  <span className="option-description">Export related entities and connections</span>
                </div>
              </label>

              <div className="option-item">
                <label htmlFor="maxRecords" className="option-label">Maximum Records</label>
                <input
                  id="maxRecords"
                  type="number"
                  value={maxRecords}
                  onChange={e => setMaxRecords(e.target.value)}
                  placeholder="Unlimited"
                  className="option-input"
                  min="1"
                />
                <span className="option-description">Limit number of exported records</span>
              </div>
            </div>

            {/* Timeline-specific options */}
            {selectedTarget === 'timeline' && (
              <div className="timeline-options">
                <h4>Timeline Options</h4>
                <label className="option-item">
                  <input
                    type="checkbox"
                    checked={includeConflicts}
                    onChange={e => setIncludeConflicts(e.target.checked)}
                  />
                  <div>
                    <span className="option-label">Include Conflicts</span>
                    <span className="option-description">Add timeline conflicts and contradictions</span>
                  </div>
                </label>

                <label className="option-item">
                  <input
                    type="checkbox"
                    checked={includeGaps}
                    onChange={e => setIncludeGaps(e.target.checked)}
                  />
                  <div>
                    <span className="option-label">Include Gaps</span>
                    <span className="option-description">Add timeline gap analysis</span>
                  </div>
                </label>

                <div className="option-item">
                  <label htmlFor="groupBy" className="option-label">Group Events By</label>
                  <select
                    id="groupBy"
                    value={groupBy}
                    onChange={e => setGroupBy(e.target.value)}
                    className="option-select"
                  >
                    <option value="">Chronological (no grouping)</option>
                    <option value="day">Day</option>
                    <option value="week">Week</option>
                    <option value="month">Month</option>
                    <option value="entity">Entity</option>
                  </select>
                  <span className="option-description">Organize events by time period or entity</span>
                </div>
              </div>
            )}
          </div>

          <div className="export-actions">
            <button
              className="btn btn-primary btn-lg"
              onClick={handleCreateExport}
            >
              <Icon name="Download" size={20} />
              Create Export
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderJobsTab = () => {
    if (jobsLoading) {
      return (
        <div className="export-loading">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading export jobs...</span>
        </div>
      );
    }

    if (!jobs || jobs.jobs.length === 0) {
      return (
        <div className="export-empty">
          <Icon name="FileDown" size={48} />
          <span>No export jobs yet</span>
          <button className="btn btn-secondary" onClick={() => setActiveTab('create')}>
            Create Export
          </button>
        </div>
      );
    }

    return (
      <div className="export-jobs">
        <div className="jobs-header">
          <h3>Export Jobs ({jobs.total})</h3>
          <button className="btn btn-secondary" onClick={refetchJobs}>
            <Icon name="RefreshCw" size={16} />
            Refresh
          </button>
        </div>

        <div className="jobs-list">
          {jobs.jobs.map(job => (
            <div key={job.id} className={`job-card status-${job.status}`}>
              <div className="job-header">
                <div className="job-info">
                  <Icon
                    name={STATUS_ICONS[job.status] || 'FileText'}
                    size={20}
                    style={{ color: STATUS_COLORS[job.status] }}
                  />
                  <div>
                    <div className="job-title">
                      {targets?.find(t => t.target === job.target)?.name || job.target} →{' '}
                      {formats?.find(f => f.format === job.format)?.name || job.format.toUpperCase()}
                    </div>
                    <div className="job-meta">
                      ID: {job.id.substring(0, 8)} • Created: {new Date(job.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
                <div className="job-status">
                  <span className={`status-badge status-${job.status}`}>
                    {job.status}
                  </span>
                </div>
              </div>

              <div className="job-details">
                {job.status === 'completed' && (
                  <>
                    <div className="job-stat">
                      <Icon name="Database" size={14} />
                      <span>{job.record_count.toLocaleString()} records</span>
                    </div>
                    <div className="job-stat">
                      <Icon name="HardDrive" size={14} />
                      <span>{formatFileSize(job.file_size)}</span>
                    </div>
                    <div className="job-stat">
                      <Icon name="Clock" size={14} />
                      <span>{formatDuration(job.processing_time_ms)}</span>
                    </div>
                    {job.expires_at && (
                      <div className="job-stat">
                        <Icon name="Calendar" size={14} />
                        <span>Expires: {new Date(job.expires_at).toLocaleDateString()}</span>
                      </div>
                    )}
                  </>
                )}

                {job.status === 'processing' && (
                  <div className="job-stat">
                    <Icon name="Loader2" size={14} className="spin" />
                    <span>Processing export...</span>
                  </div>
                )}

                {job.status === 'failed' && job.error && (
                  <div className="job-error">
                    <Icon name="AlertCircle" size={14} />
                    <span>{job.error}</span>
                  </div>
                )}
              </div>

              <div className="job-actions">
                {job.status === 'completed' && job.download_url && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => handleDownload(job)}
                  >
                    <Icon name="Download" size={14} />
                    Download
                  </button>
                )}

                {(job.status === 'pending' || job.status === 'processing') && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleCancelJob(job.id)}
                  >
                    <Icon name="X" size={14} />
                    Cancel
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderStatsTab = () => {
    if (statsLoading || !stats) {
      return (
        <div className="export-loading">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading statistics...</span>
        </div>
      );
    }

    return (
      <div className="export-stats">
        <div className="stats-grid">
          <div className="stat-card">
            <Icon name="FileDown" size={24} />
            <div className="stat-value">{stats.total_jobs}</div>
            <div className="stat-label">Total Jobs</div>
          </div>

          <div className="stat-card success">
            <Icon name="CheckCircle" size={24} />
            <div className="stat-value">{stats.jobs_completed}</div>
            <div className="stat-label">Completed</div>
          </div>

          <div className="stat-card warning">
            <Icon name="Clock" size={24} />
            <div className="stat-value">{stats.jobs_pending + stats.jobs_processing}</div>
            <div className="stat-label">Active</div>
          </div>

          <div className="stat-card error">
            <Icon name="XCircle" size={24} />
            <div className="stat-value">{stats.jobs_failed}</div>
            <div className="stat-label">Failed</div>
          </div>
        </div>

        <div className="stats-details">
          <div className="stats-section">
            <h4>Export by Format</h4>
            <div className="stats-breakdown">
              {Object.entries(stats.by_format).map(([format, count]) => (
                <div key={format} className="breakdown-item">
                  <span className="breakdown-label">{format.toUpperCase()}</span>
                  <span className="breakdown-value">{count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="stats-section">
            <h4>Export by Target</h4>
            <div className="stats-breakdown">
              {Object.entries(stats.by_target).map(([target, count]) => (
                <div key={target} className="breakdown-item">
                  <span className="breakdown-label">
                    {targets?.find(t => t.target === target)?.name || target}
                  </span>
                  <span className="breakdown-value">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="stats-summary">
          <div className="summary-item">
            <Icon name="Database" size={16} />
            <span>{stats.total_records_exported.toLocaleString()} records exported</span>
          </div>
          <div className="summary-item">
            <Icon name="HardDrive" size={16} />
            <span>{formatFileSize(stats.total_file_size_bytes)} total file size</span>
          </div>
          <div className="summary-item">
            <Icon name="Zap" size={16} />
            <span>{formatDuration(stats.avg_processing_time_ms)} avg processing time</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="export-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Download" size={28} />
          <div>
            <h1>Export</h1>
            <p className="page-description">Export data in various formats (JSON, CSV, PDF, DOCX)</p>
          </div>
        </div>
      </header>

      <div className="export-tabs">
        <button
          className={`tab ${activeTab === 'create' ? 'active' : ''}`}
          onClick={() => setActiveTab('create')}
        >
          <Icon name="Plus" size={16} />
          Create Export
        </button>
        <button
          className={`tab ${activeTab === 'jobs' ? 'active' : ''}`}
          onClick={() => setActiveTab('jobs')}
        >
          <Icon name="FileDown" size={16} />
          Export Jobs
          {jobs && jobs.total > 0 && (
            <span className="tab-badge">{jobs.total}</span>
          )}
        </button>
        <button
          className={`tab ${activeTab === 'stats' ? 'active' : ''}`}
          onClick={() => setActiveTab('stats')}
        >
          <Icon name="BarChart3" size={16} />
          Statistics
        </button>
      </div>

      <div className="export-content">
        {activeTab === 'create' && renderCreateTab()}
        {activeTab === 'jobs' && renderJobsTab()}
        {activeTab === 'stats' && renderStatsTab()}
      </div>
    </div>
  );
}
