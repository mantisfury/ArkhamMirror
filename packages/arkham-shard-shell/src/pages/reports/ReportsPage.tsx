/**
 * ReportsPage - Analytical report generation and management
 *
 * Provides UI for creating, viewing, and managing reports.
 * Includes template selection, report history, and download functionality.
 */

import { useState } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import './ReportsPage.css';

// Types
interface Report {
  id: string;
  report_type: string;
  title: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  parameters: Record<string, unknown>;
  output_format: string;
  file_path: string | null;
  file_size: number | null;
  error: string | null;
  metadata: Record<string, unknown>;
}

interface ReportTemplate {
  id: string;
  name: string;
  report_type: string;
  description: string;
  parameters_schema: Record<string, unknown>;
  default_format: string;
  template_content: string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

const REPORT_TYPES = [
  { value: 'summary', label: 'System Summary', icon: 'FileText' },
  { value: 'entity_profile', label: 'Entity Profile', icon: 'User' },
  { value: 'timeline', label: 'Timeline Report', icon: 'Clock' },
  { value: 'contradiction', label: 'Contradiction Analysis', icon: 'AlertTriangle' },
  { value: 'ach_analysis', label: 'ACH Analysis', icon: 'Network' },
  { value: 'custom', label: 'Custom Report', icon: 'FileCode' },
];

const FORMAT_OPTIONS = [
  { value: 'html', label: 'HTML', icon: 'Code' },
  { value: 'pdf', label: 'PDF', icon: 'FileText' },
  { value: 'markdown', label: 'Markdown', icon: 'FileCode' },
  { value: 'json', label: 'JSON', icon: 'Braces' },
];

export function ReportsPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<'reports' | 'templates'>('reports');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [_selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [reportTitle, setReportTitle] = useState('');
  const [reportType, setReportType] = useState('summary');
  const [outputFormat, setOutputFormat] = useState('html');
  const [creating, setCreating] = useState(false);

  // Fetch reports with pagination
  const {
    items: reports,
    loading: reportsLoading,
    error: reportsError,
    refetch: refetchReports,
  } = usePaginatedFetch<Report>('/api/reports/');

  // Fetch templates
  const { data: templates, loading: templatesLoading, error: templatesError, refetch: refetchTemplates } = useFetch<ReportTemplate[]>(
    '/api/reports/templates'
  );

  const handleCreateReport = async () => {
    if (!reportTitle.trim()) {
      toast.error('Please enter a report title');
      return;
    }

    setCreating(true);
    try {
      const response = await fetch('/api/reports/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_type: reportType,
          title: reportTitle,
          parameters: {},
          output_format: outputFormat,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create report');
      }

      toast.success('Report generation started');
      setShowCreateDialog(false);
      setReportTitle('');
      setReportType('summary');
      setOutputFormat('html');
      refetchReports();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create report');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteReport = async (reportId: string) => {
    try {
      const response = await fetch(`/api/reports/${reportId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete report');
      }

      toast.success('Report deleted');
      refetchReports();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete report');
    }
  };

  const handleDownloadReport = async (reportId: string) => {
    try {
      const response = await fetch(`/api/reports/${reportId}/download`);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to download report');
      }

      const data = await response.json();
      toast.info('Download endpoint (stub): ' + data.file_path);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to download report');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return 'Clock';
      case 'generating':
        return 'Loader2';
      case 'completed':
        return 'CheckCircle';
      case 'failed':
        return 'XCircle';
      default:
        return 'FileText';
    }
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'pending':
        return 'status-pending';
      case 'generating':
        return 'status-generating';
      case 'completed':
        return 'status-completed';
      case 'failed':
        return 'status-failed';
      default:
        return '';
    }
  };

  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  return (
    <div className="reports-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="FileText" size={28} />
          <div>
            <h1>Reports</h1>
            <p className="page-description">Generate and manage analytical reports</p>
          </div>
        </div>

        <div className="header-actions">
          <button
            className="btn btn-primary"
            onClick={() => setShowCreateDialog(true)}
          >
            <Icon name="Plus" size={16} />
            New Report
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === 'reports' ? 'active' : ''}`}
          onClick={() => setActiveTab('reports')}
        >
          <Icon name="FileText" size={16} />
          Reports
        </button>
        <button
          className={`tab ${activeTab === 'templates' ? 'active' : ''}`}
          onClick={() => setActiveTab('templates')}
        >
          <Icon name="FileTemplate" size={16} />
          Templates
        </button>
      </div>

      {/* Reports Tab */}
      {activeTab === 'reports' && (
        <main className="reports-content">
          {reportsLoading ? (
            <div className="reports-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading reports...</span>
            </div>
          ) : reportsError ? (
            <div className="reports-error">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load reports</span>
              <button className="btn btn-secondary" onClick={() => refetchReports()}>
                Retry
              </button>
            </div>
          ) : reports && reports.length > 0 ? (
            <div className="reports-list">
              {reports.map(report => (
                <div key={report.id} className="report-card">
                  <div className="report-header">
                    <div className="report-title-row">
                      <Icon name={getStatusIcon(report.status)} size={20} className={getStatusClass(report.status)} />
                      <h3>{report.title}</h3>
                      <span className={`status-badge ${getStatusClass(report.status)}`}>
                        {report.status}
                      </span>
                    </div>
                  </div>

                  <div className="report-details">
                    <div className="detail-item">
                      <Icon name="Tag" size={14} />
                      <span>Type: {report.report_type}</span>
                    </div>
                    <div className="detail-item">
                      <Icon name="FileType" size={14} />
                      <span>Format: {report.output_format}</span>
                    </div>
                    <div className="detail-item">
                      <Icon name="Clock" size={14} />
                      <span>Created: {formatDate(report.created_at)}</span>
                    </div>
                    {report.completed_at && (
                      <div className="detail-item">
                        <Icon name="CheckCircle" size={14} />
                        <span>Completed: {formatDate(report.completed_at)}</span>
                      </div>
                    )}
                    {report.file_size && (
                      <div className="detail-item">
                        <Icon name="HardDrive" size={14} />
                        <span>Size: {formatFileSize(report.file_size)}</span>
                      </div>
                    )}
                  </div>

                  {report.error && (
                    <div className="report-error">
                      <Icon name="AlertTriangle" size={14} />
                      <span>{report.error}</span>
                    </div>
                  )}

                  <div className="report-actions">
                    {report.status === 'completed' && (
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => handleDownloadReport(report.id)}
                      >
                        <Icon name="Download" size={14} />
                        Download
                      </button>
                    )}
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => handleDeleteReport(report.id)}
                    >
                      <Icon name="Trash2" size={14} />
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="reports-empty">
              <Icon name="FileText" size={48} />
              <span>No reports yet</span>
              <button
                className="btn btn-primary"
                onClick={() => setShowCreateDialog(true)}
              >
                Create your first report
              </button>
            </div>
          )}
        </main>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <main className="templates-content">
          {templatesLoading ? (
            <div className="templates-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading templates...</span>
            </div>
          ) : templatesError ? (
            <div className="templates-error">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load templates</span>
              <button className="btn btn-secondary" onClick={() => refetchTemplates()}>
                Retry
              </button>
            </div>
          ) : templates && templates.length > 0 ? (
            <div className="templates-list">
              {templates.map(template => (
                <div key={template.id} className="template-card">
                  <Icon name="FileTemplate" size={20} />
                  <div className="template-info">
                    <h3>{template.name}</h3>
                    <p>{template.description}</p>
                    <div className="template-meta">
                      <span>Type: {template.report_type}</span>
                      <span>Format: {template.default_format}</span>
                    </div>
                  </div>
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={() => {
                      setSelectedTemplate(template.id);
                      setReportType(template.report_type);
                      setOutputFormat(template.default_format);
                      setShowCreateDialog(true);
                    }}
                  >
                    Use Template
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="templates-empty">
              <Icon name="FileTemplate" size={48} />
              <span>No templates available</span>
            </div>
          )}
        </main>
      )}

      {/* Create Report Dialog */}
      {showCreateDialog && (
        <div className="dialog-overlay" onClick={() => setShowCreateDialog(false)}>
          <div className="dialog" onClick={e => e.stopPropagation()}>
            <div className="dialog-header">
              <h2>Create New Report</h2>
              <button
                className="dialog-close"
                onClick={() => setShowCreateDialog(false)}
              >
                <Icon name="X" size={20} />
              </button>
            </div>

            <div className="dialog-content">
              <div className="form-group">
                <label htmlFor="report-title">Report Title</label>
                <input
                  id="report-title"
                  type="text"
                  className="form-input"
                  value={reportTitle}
                  onChange={e => setReportTitle(e.target.value)}
                  placeholder="Enter report title"
                />
              </div>

              <div className="form-group">
                <label htmlFor="report-type">Report Type</label>
                <select
                  id="report-type"
                  className="form-select"
                  value={reportType}
                  onChange={e => setReportType(e.target.value)}
                >
                  {REPORT_TYPES.map(type => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="output-format">Output Format</label>
                <select
                  id="output-format"
                  className="form-select"
                  value={outputFormat}
                  onChange={e => setOutputFormat(e.target.value)}
                >
                  {FORMAT_OPTIONS.map(format => (
                    <option key={format.value} value={format.value}>
                      {format.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="dialog-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setShowCreateDialog(false)}
                disabled={creating}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCreateReport}
                disabled={creating}
              >
                {creating ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Icon name="FileText" size={16} />
                    Create Report
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
