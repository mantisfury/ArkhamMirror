/**
 * DocumentViewer - Document content viewer with tabs
 *
 * Displays document content, chunks, and entities in a tabbed interface.
 */

import { useState, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import {
  useDocument,
  useDocumentContent,
  useDocumentChunks,
  useDocumentEntities,
  type DocumentChunk,
  type DocumentEntity,
} from './api';
import './DocumentViewer.css';

interface DocumentViewerProps {
  documentId: string;
  onClose: () => void;
}

type ViewerTab = 'content' | 'chunks' | 'entities' | 'metadata';

const ENTITY_TYPE_COLORS: Record<string, string> = {
  PERSON: '#3b82f6',
  ORG: '#10b981',
  GPE: '#f59e0b',
  DATE: '#8b5cf6',
  MONEY: '#ef4444',
  EVENT: '#ec4899',
  LAW: '#6366f1',
  PRODUCT: '#14b8a6',
  WORK_OF_ART: '#f97316',
  default: '#6b7280',
};

function getEntityColor(entityType: string): string {
  return ENTITY_TYPE_COLORS[entityType] || ENTITY_TYPE_COLORS.default;
}

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
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

export function DocumentViewer({ documentId, onClose }: DocumentViewerProps) {
  const [activeTab, setActiveTab] = useState<ViewerTab>('content');
  const [currentPage, setCurrentPage] = useState(1);
  const [chunksPage, setChunksPage] = useState(1);
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>('');

  // Fetch document metadata
  const { data: document, loading: loadingDoc } = useDocument(documentId);

  // Fetch content for current page
  const {
    data: contentData,
    loading: loadingContent,
    error: contentError,
    refetch: refetchContent,
  } = useDocumentContent(documentId, currentPage);

  // Fetch chunks
  const {
    data: chunksData,
    loading: loadingChunks,
    error: chunksError,
    refetch: refetchChunks,
  } = useDocumentChunks(documentId, chunksPage, 20);

  // Fetch entities
  const {
    data: entitiesData,
    loading: loadingEntities,
    error: entitiesError,
    refetch: refetchEntities,
  } = useDocumentEntities(documentId, entityTypeFilter || undefined);

  // Refetch when page changes
  useEffect(() => {
    if (activeTab === 'content') {
      refetchContent();
    }
  }, [currentPage, activeTab, refetchContent]);

  useEffect(() => {
    if (activeTab === 'chunks') {
      refetchChunks();
    }
  }, [chunksPage, activeTab, refetchChunks]);

  useEffect(() => {
    if (activeTab === 'entities') {
      refetchEntities();
    }
  }, [entityTypeFilter, activeTab, refetchEntities]);

  const totalPages = contentData?.total_pages || document?.page_count || 1;

  const handlePrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'content':
        return renderContentTab();
      case 'chunks':
        return renderChunksTab();
      case 'entities':
        return renderEntitiesTab();
      case 'metadata':
        return renderMetadataTab();
      default:
        return null;
    }
  };

  const renderContentTab = () => {
    if (loadingContent) {
      return (
        <div className="viewer-loading">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading content...</span>
        </div>
      );
    }

    if (contentError) {
      return (
        <div className="viewer-error">
          <Icon name="AlertCircle" size={32} />
          <span>Failed to load content</span>
          <p className="error-detail">{contentError.message}</p>
          <button className="btn btn-secondary" onClick={() => refetchContent()}>
            Retry
          </button>
        </div>
      );
    }

    if (!contentData?.content) {
      return (
        <div className="viewer-empty">
          <Icon name="FileText" size={48} />
          <span>No content available</span>
          <p>This document may not have been processed yet.</p>
        </div>
      );
    }

    return (
      <div className="content-view">
        {totalPages > 1 && (
          <div className="page-navigation">
            <button
              className="btn btn-icon"
              onClick={handlePrevPage}
              disabled={currentPage <= 1}
              title="Previous page"
            >
              <Icon name="ChevronLeft" size={18} />
            </button>
            <span className="page-info">
              Page {currentPage} of {totalPages}
            </span>
            <button
              className="btn btn-icon"
              onClick={handleNextPage}
              disabled={currentPage >= totalPages}
              title="Next page"
            >
              <Icon name="ChevronRight" size={18} />
            </button>
          </div>
        )}
        <div className="content-text">
          <pre>{contentData.content}</pre>
        </div>
      </div>
    );
  };

  const renderChunksTab = () => {
    if (loadingChunks) {
      return (
        <div className="viewer-loading">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading chunks...</span>
        </div>
      );
    }

    if (chunksError) {
      return (
        <div className="viewer-error">
          <Icon name="AlertCircle" size={32} />
          <span>Failed to load chunks</span>
          <button className="btn btn-secondary" onClick={() => refetchChunks()}>
            Retry
          </button>
        </div>
      );
    }

    if (!chunksData?.items?.length) {
      return (
        <div className="viewer-empty">
          <Icon name="Package" size={48} />
          <span>No chunks available</span>
          <p>This document may not have been chunked yet.</p>
        </div>
      );
    }

    const totalChunkPages = Math.ceil(chunksData.total / 20);

    return (
      <div className="chunks-view">
        <div className="chunks-header">
          <span className="chunks-count">
            {chunksData.total} chunks total
          </span>
          {totalChunkPages > 1 && (
            <div className="chunks-pagination">
              <button
                className="btn btn-icon"
                onClick={() => setChunksPage(p => Math.max(1, p - 1))}
                disabled={chunksPage <= 1}
              >
                <Icon name="ChevronLeft" size={16} />
              </button>
              <span>
                {chunksPage} / {totalChunkPages}
              </span>
              <button
                className="btn btn-icon"
                onClick={() => setChunksPage(p => Math.min(totalChunkPages, p + 1))}
                disabled={chunksPage >= totalChunkPages}
              >
                <Icon name="ChevronRight" size={16} />
              </button>
            </div>
          )}
        </div>
        <div className="chunks-list">
          {chunksData.items.map((chunk: DocumentChunk) => (
            <div key={chunk.id} className="chunk-item">
              <div className="chunk-header">
                <span className="chunk-index">#{chunk.chunk_index}</span>
                {chunk.page_number && (
                  <span className="chunk-page">Page {chunk.page_number}</span>
                )}
                <span className="chunk-tokens">{chunk.token_count} tokens</span>
                {chunk.embedding_id && (
                  <span className="chunk-embedded" title="Has embedding">
                    <Icon name="Zap" size={12} />
                  </span>
                )}
              </div>
              <div className="chunk-content">{chunk.content}</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderEntitiesTab = () => {
    if (loadingEntities) {
      return (
        <div className="viewer-loading">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading entities...</span>
        </div>
      );
    }

    if (entitiesError) {
      return (
        <div className="viewer-error">
          <Icon name="AlertCircle" size={32} />
          <span>Failed to load entities</span>
          <button className="btn btn-secondary" onClick={() => refetchEntities()}>
            Retry
          </button>
        </div>
      );
    }

    if (!entitiesData?.items?.length) {
      return (
        <div className="viewer-empty">
          <Icon name="Users" size={48} />
          <span>No entities found</span>
          <p>No entities have been extracted from this document.</p>
        </div>
      );
    }

    // Get unique entity types for filter
    const entityTypes = [...new Set(entitiesData.items.map((e: DocumentEntity) => e.entity_type))];

    return (
      <div className="entities-view">
        <div className="entities-header">
          <span className="entities-count">
            {entitiesData.total} entities
          </span>
          <select
            className="entity-filter"
            value={entityTypeFilter}
            onChange={e => setEntityTypeFilter(e.target.value)}
          >
            <option value="">All types</option>
            {entityTypes.map(type => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <div className="entities-list">
          {entitiesData.items.map((entity: DocumentEntity) => (
            <div key={entity.id} className="entity-item">
              <div className="entity-header">
                <span
                  className="entity-type"
                  style={{ backgroundColor: getEntityColor(entity.entity_type) }}
                >
                  {entity.entity_type}
                </span>
                <span className="entity-text">{entity.text}</span>
                <span className="entity-occurrences">
                  {entity.occurrences}x
                </span>
              </div>
              {entity.confidence > 0 && (
                <div className="entity-confidence">
                  <div
                    className="confidence-bar"
                    style={{ width: `${entity.confidence * 100}%` }}
                  />
                  <span>{(entity.confidence * 100).toFixed(0)}%</span>
                </div>
              )}
              {entity.context.length > 0 && (
                <div className="entity-context">
                  {entity.context.map((ctx, idx) => (
                    <div key={idx} className="context-item">
                      "...{ctx}..."
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderMetadataTab = () => {
    if (loadingDoc) {
      return (
        <div className="viewer-loading">
          <Icon name="Loader2" size={32} className="spin" />
          <span>Loading metadata...</span>
        </div>
      );
    }

    if (!document) {
      return (
        <div className="viewer-error">
          <Icon name="AlertCircle" size={32} />
          <span>Document not found</span>
        </div>
      );
    }

    return (
      <div className="metadata-view">
        <div className="metadata-section">
          <h3>Basic Information</h3>
          <dl className="metadata-list">
            <dt>Title</dt>
            <dd>{document.title}</dd>
            <dt>Filename</dt>
            <dd className="mono">{document.filename}</dd>
            <dt>File Type</dt>
            <dd>{document.file_type || 'Unknown'}</dd>
            <dt>File Size</dt>
            <dd>{formatFileSize(document.file_size)}</dd>
            <dt>Status</dt>
            <dd className={`status-${document.status}`}>{document.status}</dd>
          </dl>
        </div>

        <div className="metadata-section">
          <h3>Processing Stats</h3>
          <dl className="metadata-list">
            <dt>Pages</dt>
            <dd>{document.page_count}</dd>
            <dt>Chunks</dt>
            <dd>{document.chunk_count}</dd>
            <dt>Entities</dt>
            <dd>{document.entity_count}</dd>
          </dl>
        </div>

        <div className="metadata-section">
          <h3>Timestamps</h3>
          <dl className="metadata-list">
            <dt>Created</dt>
            <dd>{formatDate(document.created_at)}</dd>
            <dt>Updated</dt>
            <dd>{formatDate(document.updated_at)}</dd>
          </dl>
        </div>

        {document.tags.length > 0 && (
          <div className="metadata-section">
            <h3>Tags</h3>
            <div className="tags-list">
              {document.tags.map((tag, idx) => (
                <span key={idx} className="tag">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {Object.keys(document.custom_metadata).length > 0 && (
          <div className="metadata-section">
            <h3>Custom Metadata</h3>
            <pre className="custom-metadata">
              {JSON.stringify(document.custom_metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="document-viewer">
      <div className="viewer-header">
        <div className="viewer-title">
          <Icon name="FileText" size={20} />
          <h2>{document?.title || 'Loading...'}</h2>
        </div>
        <button className="btn btn-icon" onClick={onClose} title="Close viewer">
          <Icon name="X" size={20} />
        </button>
      </div>

      <div className="viewer-tabs">
        <button
          className={`tab-btn ${activeTab === 'content' ? 'active' : ''}`}
          onClick={() => setActiveTab('content')}
        >
          <Icon name="FileText" size={16} />
          Content
        </button>
        <button
          className={`tab-btn ${activeTab === 'chunks' ? 'active' : ''}`}
          onClick={() => setActiveTab('chunks')}
        >
          <Icon name="Package" size={16} />
          Chunks
          {document?.chunk_count ? (
            <span className="tab-badge">{document.chunk_count}</span>
          ) : null}
        </button>
        <button
          className={`tab-btn ${activeTab === 'entities' ? 'active' : ''}`}
          onClick={() => setActiveTab('entities')}
        >
          <Icon name="Users" size={16} />
          Entities
          {document?.entity_count ? (
            <span className="tab-badge">{document.entity_count}</span>
          ) : null}
        </button>
        <button
          className={`tab-btn ${activeTab === 'metadata' ? 'active' : ''}`}
          onClick={() => setActiveTab('metadata')}
        >
          <Icon name="Info" size={16} />
          Metadata
        </button>
      </div>

      <div className="viewer-content">{renderTabContent()}</div>
    </div>
  );
}
