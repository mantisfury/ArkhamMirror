/**
 * DocumentsPage - Document browser and viewer
 *
 * Provides UI for browsing, searching, and viewing documents.
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import { DocumentViewer } from './DocumentViewer';
import './DocumentsPage.css';

// Types
interface Document {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: string;
  page_count: number;
  chunk_count: number;
  entity_count: number;
  created_at: string;
  updated_at: string;
  project_id?: string;
  tags: string[];
  custom_metadata: Record<string, unknown>;
}

interface DocumentStats {
  total_documents: number;
  processed_documents: number;
  processing_documents: number;
  failed_documents: number;
  total_size_bytes: number;
  total_pages: number;
  total_chunks: number;
}

const STATUS_COLORS: Record<string, string> = {
  uploaded: '#6b7280',
  processing: '#3b82f6',
  processed: '#10b981',
  failed: '#ef4444',
  archived: '#8b5cf6',
};

const STATUS_ICONS: Record<string, string> = {
  uploaded: 'Upload',
  processing: 'Loader2',
  processed: 'CheckCircle2',
  failed: 'XCircle',
  archived: 'Archive',
};

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(dateString: string): string {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function DocumentsPage() {
  const { toast } = useToast();
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');

  // Fetch documents with pagination
  const { items: documents, total, loading, error, refetch } = usePaginatedFetch<Document>(
    '/api/documents/items',
    {
      params: {
        ...(searchQuery && { q: searchQuery }),
        ...(statusFilter && { status: statusFilter }),
      },
      syncToUrl: false, // This page doesn't use URL-based pagination
    }
  );

  // Fetch stats
  const { data: stats } = useFetch<DocumentStats>('/api/documents/stats');

  // Handle document selection
  const handleSelectDocument = useCallback((docId: string) => {
    setSelectedDoc(docId === selectedDoc ? null : docId);
  }, [selectedDoc]);

  // Handle document deletion
  const handleDeleteDocument = async (docId: string, title: string) => {
    if (!confirm(`Delete document "${title}"?`)) return;

    try {
      const response = await fetch(`/api/documents/items/${docId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete document');
      }

      toast.success('Document deleted successfully');
      refetch();
      if (selectedDoc === docId) {
        setSelectedDoc(null);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete document');
    }
  };

  // Handle search
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    refetch();
  };

  // Clear filters
  const handleClearFilters = () => {
    setSearchQuery('');
    setStatusFilter('');
  };

  const hasFilters = searchQuery || statusFilter;

  return (
    <div className={`documents-page ${selectedDoc ? 'with-viewer' : ''}`}>
      <div className="documents-list-panel">
        <header className="page-header">
          <div className="page-title">
            <Icon name="FileText" size={28} />
            <div>
              <h1>Documents</h1>
              <p className="page-description">Browse and manage documents</p>
            </div>
          </div>

          {stats && (
            <div className="stats-bar">
              <div className="stat-item">
                <Icon name="FileText" size={16} />
                <span>{stats.total_documents} total</span>
              </div>
              <div className="stat-item">
                <Icon name="CheckCircle2" size={16} />
                <span>{stats.processed_documents} processed</span>
              </div>
              <div className="stat-item">
                <Icon name="Loader2" size={16} />
                <span>{stats.processing_documents} processing</span>
              </div>
              {stats.failed_documents > 0 && (
                <div className="stat-item error">
                  <Icon name="XCircle" size={16} />
                  <span>{stats.failed_documents} failed</span>
                </div>
              )}
            </div>
          )}
        </header>

        <div className="documents-controls">
          <form className="search-bar" onSubmit={handleSearch}>
            <Icon name="Search" size={16} />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className="clear-search"
                onClick={() => setSearchQuery('')}
                title="Clear search"
              >
                <Icon name="X" size={14} />
              </button>
            )}
          </form>

          <div className="filters">
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="filter-select"
            >
              <option value="">All statuses</option>
              <option value="uploaded">Uploaded</option>
              <option value="processing">Processing</option>
              <option value="processed">Processed</option>
              <option value="failed">Failed</option>
              <option value="archived">Archived</option>
            </select>

            {hasFilters && (
              <button className="btn btn-secondary" onClick={handleClearFilters}>
                <Icon name="X" size={14} />
                Clear filters
              </button>
            )}
          </div>

          <div className="view-toggle">
            <button
              className={`view-btn ${viewMode === 'list' ? 'active' : ''}`}
              onClick={() => setViewMode('list')}
              title="List view"
            >
              <Icon name="List" size={16} />
            </button>
            <button
              className={`view-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              title="Grid view"
            >
              <Icon name="Grid3x3" size={16} />
            </button>
          </div>
        </div>

        <main className="documents-content">
          {loading ? (
            <div className="documents-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading documents...</span>
            </div>
          ) : error ? (
            <div className="documents-error">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load documents</span>
              <button className="btn btn-secondary" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : documents.length > 0 ? (
            <div className={`documents-${viewMode}`}>
              {documents.map(doc => (
                <div
                  key={doc.id}
                  className={`document-item ${selectedDoc === doc.id ? 'selected' : ''}`}
                  onClick={() => handleSelectDocument(doc.id)}
                >
                  <div className="document-header">
                    <div className="document-icon">
                      <Icon name="FileText" size={20} />
                    </div>
                    <div className="document-info">
                      <h3 className="document-title">{doc.title}</h3>
                      <p className="document-filename">{doc.filename}</p>
                    </div>
                    <div
                      className="document-status"
                      style={{ color: STATUS_COLORS[doc.status] }}
                    >
                      <Icon name={STATUS_ICONS[doc.status] || 'Circle'} size={14} />
                      <span>{doc.status}</span>
                    </div>
                  </div>

                  <div className="document-meta">
                    <div className="meta-item">
                      <Icon name="FileType" size={12} />
                      <span>{doc.file_type || 'Unknown'}</span>
                    </div>
                    <div className="meta-item">
                      <Icon name="HardDrive" size={12} />
                      <span>{formatFileSize(doc.file_size)}</span>
                    </div>
                    {doc.page_count > 0 && (
                      <div className="meta-item">
                        <Icon name="FileText" size={12} />
                        <span>{doc.page_count} pages</span>
                      </div>
                    )}
                    {doc.chunk_count > 0 && (
                      <div className="meta-item">
                        <Icon name="Package" size={12} />
                        <span>{doc.chunk_count} chunks</span>
                      </div>
                    )}
                  </div>

                  <div className="document-footer">
                    <div className="document-date">
                      <Icon name="Clock" size={12} />
                      <span>{formatDate(doc.created_at)}</span>
                    </div>
                    <div className="document-actions">
                      <button
                        className="action-btn view-btn-inline"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedDoc(doc.id);
                        }}
                        title="View document"
                      >
                        <Icon name="Eye" size={14} />
                      </button>
                      <button
                        className="action-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteDocument(doc.id, doc.title);
                        }}
                        title="Delete document"
                      >
                        <Icon name="Trash2" size={14} />
                      </button>
                    </div>
                  </div>

                  {doc.tags.length > 0 && (
                    <div className="document-tags">
                      {doc.tags.map((tag, idx) => (
                        <span key={idx} className="tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="documents-empty">
              <Icon name="FileText" size={48} />
              <span>No documents found</span>
              {hasFilters && (
                <button className="btn btn-secondary" onClick={handleClearFilters}>
                  Clear filters
                </button>
              )}
            </div>
          )}
        </main>

        {total > 0 && (
          <div className="pagination">
            <span>
              Showing {documents.length} of {total} documents
            </span>
          </div>
        )}
      </div>

      {selectedDoc && (
        <div className="documents-viewer-panel">
          <DocumentViewer
            documentId={selectedDoc}
            onClose={() => setSelectedDoc(null)}
          />
        </div>
      )}
    </div>
  );
}
