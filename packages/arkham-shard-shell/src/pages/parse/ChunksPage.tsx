/**
 * ChunksPage - View all text chunks with pagination
 *
 * Features:
 * - Paginated list of all text chunks
 * - Filter by document
 * - View full chunk text
 * - Navigate to source document
 */

import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useAllChunks } from './api';

const PAGE_SIZE = 20;

export function ChunksPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get('page') || '1', 10);
  const documentId = searchParams.get('document_id') || undefined;

  const offset = (page - 1) * PAGE_SIZE;
  const { data, loading, error, refetch } = useAllChunks(PAGE_SIZE, offset, documentId);

  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);

  const handlePageChange = (newPage: number) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', String(newPage));
    setSearchParams(params);
  };

  const handleClearFilter = () => {
    const params = new URLSearchParams();
    params.set('page', '1');
    setSearchParams(params);
  };

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="chunks-page">
      <header className="page-header">
        <div className="page-title">
          <button className="back-button" onClick={() => navigate('/parse')}>
            <Icon name="ArrowLeft" size={20} />
          </button>
          <Icon name="FileText" size={28} />
          <div>
            <h1>Text Chunks</h1>
            <p className="page-description">
              {data ? `${data.total} chunks` : 'Loading...'}
              {documentId && ' (filtered by document)'}
            </p>
          </div>
        </div>
        <div className="page-actions">
          {documentId && (
            <button className="button-secondary" onClick={handleClearFilter}>
              <Icon name="X" size={16} />
              Clear Filter
            </button>
          )}
          <button className="button-secondary" onClick={() => refetch()}>
            <Icon name="RefreshCw" size={16} />
            Refresh
          </button>
        </div>
      </header>

      {loading && (
        <div className="loading-state">
          <Icon name="Loader" size={32} className="spinner" />
          <span>Loading chunks...</span>
        </div>
      )}

      {error && (
        <div className="error-state">
          <Icon name="AlertCircle" size={32} />
          <span>Failed to load chunks</span>
          <p className="error-detail">{error instanceof Error ? error.message : String(error)}</p>
        </div>
      )}

      {data && data.chunks.length === 0 && (
        <div className="empty-state">
          <Icon name="FileText" size={48} />
          <p>No chunks found</p>
          <span>Upload and parse documents to create text chunks</span>
        </div>
      )}

      {data && data.chunks.length > 0 && (
        <>
          <div className="chunks-list">
            {data.chunks.map((chunk) => (
              <div
                key={chunk.id}
                className={`chunk-card ${expandedChunk === chunk.id ? 'expanded' : ''}`}
              >
                <div
                  className="chunk-header"
                  onClick={() => setExpandedChunk(expandedChunk === chunk.id ? null : chunk.id)}
                >
                  <div className="chunk-info">
                    <div className="chunk-meta">
                      <span className="chunk-index">#{chunk.chunk_index + 1}</span>
                      <span className="document-name" title={chunk.document_name}>
                        <Icon name="File" size={14} />
                        {chunk.document_name || 'Unknown document'}
                      </span>
                      {chunk.page_number && (
                        <span className="page-number">
                          <Icon name="BookOpen" size={14} />
                          Page {chunk.page_number}
                        </span>
                      )}
                      <span className="token-count">
                        <Icon name="Hash" size={14} />
                        {chunk.token_count} tokens
                      </span>
                    </div>
                    <div className="chunk-preview">
                      {chunk.text}
                    </div>
                  </div>
                  <Icon
                    name={expandedChunk === chunk.id ? 'ChevronUp' : 'ChevronDown'}
                    size={20}
                    className="expand-icon"
                  />
                </div>

                {expandedChunk === chunk.id && (
                  <div className="chunk-details">
                    <div className="chunk-full-text">
                      {chunk.full_text}
                    </div>
                    <div className="chunk-actions">
                      <button
                        className="button-secondary"
                        onClick={() => navigate(`/documents?id=${chunk.document_id}`)}
                      >
                        <Icon name="FileText" size={14} />
                        View Document
                      </button>
                      <div className="chunk-stats">
                        <span>Characters: {chunk.start_char} - {chunk.end_char}</span>
                        {chunk.vector_id && (
                          <span className="has-vector">
                            <Icon name="Box" size={12} />
                            Embedded
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div className="pagination">
            <button
              className="pagination-button"
              disabled={page <= 1}
              onClick={() => handlePageChange(page - 1)}
            >
              <Icon name="ChevronLeft" size={16} />
              Previous
            </button>
            <span className="pagination-info">
              Page {page} of {totalPages}
            </span>
            <button
              className="pagination-button"
              disabled={!data.has_more}
              onClick={() => handlePageChange(page + 1)}
            >
              Next
              <Icon name="ChevronRight" size={16} />
            </button>
          </div>
        </>
      )}

      <style>{`
        .chunks-page {
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

        .back-button {
          background: transparent;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          padding: 0.5rem;
          color: #9ca3af;
          cursor: pointer;
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

        .loading-state,
        .error-state,
        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 1rem;
          padding: 4rem;
          color: #9ca3af;
          text-align: center;
        }

        .error-detail {
          color: #ef4444;
          font-size: 0.875rem;
        }

        .chunks-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .chunk-card {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          overflow: hidden;
          transition: border-color 0.15s;
        }

        .chunk-card:hover {
          border-color: #4b5563;
        }

        .chunk-card.expanded {
          border-color: #6366f1;
        }

        .chunk-header {
          display: flex;
          align-items: flex-start;
          gap: 1rem;
          padding: 1rem;
          cursor: pointer;
        }

        .chunk-info {
          flex: 1;
          min-width: 0;
        }

        .chunk-meta {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin-bottom: 0.5rem;
          flex-wrap: wrap;
        }

        .chunk-index {
          font-weight: 600;
          color: #6366f1;
          font-size: 0.875rem;
        }

        .document-name,
        .page-number,
        .token-count {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          font-size: 0.75rem;
          color: #9ca3af;
        }

        .document-name {
          max-width: 200px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .chunk-preview {
          font-size: 0.875rem;
          color: #d1d5db;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          line-height: 1.5;
        }

        .expand-icon {
          color: #6b7280;
          flex-shrink: 0;
        }

        .chunk-details {
          border-top: 1px solid #374151;
          padding: 1rem;
          background: #111827;
        }

        .chunk-full-text {
          font-size: 0.875rem;
          color: #e5e7eb;
          line-height: 1.6;
          white-space: pre-wrap;
          word-break: break-word;
          max-height: 300px;
          overflow-y: auto;
          padding: 1rem;
          background: #1f2937;
          border-radius: 0.375rem;
          margin-bottom: 1rem;
        }

        .chunk-actions {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 1rem;
        }

        .chunk-stats {
          display: flex;
          align-items: center;
          gap: 1rem;
          font-size: 0.75rem;
          color: #6b7280;
        }

        .has-vector {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          color: #22c55e;
        }

        .pagination {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 1rem;
          margin-top: 2rem;
          padding: 1rem;
        }

        .pagination-button {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 1rem;
          background: #374151;
          border: 1px solid #4b5563;
          border-radius: 0.375rem;
          color: #f9fafb;
          cursor: pointer;
          transition: all 0.15s;
        }

        .pagination-button:hover:not(:disabled) {
          background: #4b5563;
        }

        .pagination-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .pagination-info {
          font-size: 0.875rem;
          color: #9ca3af;
        }

        .button-secondary {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 1rem;
          background: #374151;
          border: 1px solid #4b5563;
          border-radius: 0.375rem;
          color: #f9fafb;
          font-size: 0.875rem;
          cursor: pointer;
          transition: all 0.15s;
        }

        .button-secondary:hover {
          background: #4b5563;
        }

        .spinner {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
