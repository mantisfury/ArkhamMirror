/**
 * EmbedPage - Main embed page
 *
 * Features:
 * - Model info display
 * - Similarity calculator
 * - Nearest neighbor search
 * - Cache statistics
 * - Document embedding queue
 */

import { useState, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { SimilarityCalculator } from './SimilarityCalculator';
import { useModels, useCacheStats, useNearest, useEmbedDocument, useClearCache } from './api';

export function EmbedPage() {
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLimit, setSearchLimit] = useState(10);
  const [docIdInput, setDocIdInput] = useState('');

  const { data: models, loading: loadingModels } = useModels();
  const { data: cacheStats, loading: loadingCache, refetch: refetchCache } = useCacheStats();
  const { search, data: searchResults, loading: searching } = useNearest();
  const { embed: embedDoc, loading: embeddingDoc } = useEmbedDocument();
  const { clear: clearCacheAPI, loading: clearingCache } = useClearCache();

  // Auto-refresh cache stats
  useEffect(() => {
    const interval = setInterval(() => {
      refetchCache();
    }, 10000); // Refresh every 10 seconds

    return () => clearInterval(interval);
  }, [refetchCache]);

  const currentModel = models?.find(m => m.loaded);

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      toast.warning('Please enter a search query');
      return;
    }

    try {
      await search(searchQuery, { limit: searchLimit });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Search failed');
    }
  };

  const handleEmbedDocument = async () => {
    if (!docIdInput.trim()) {
      toast.warning('Please enter a document ID');
      return;
    }

    try {
      const result = await embedDoc(docIdInput);
      toast.success(`Document embedding queued: ${result.job_id}`);
      setDocIdInput('');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Embedding failed');
    }
  };

  const handleClearCache = async () => {
    try {
      await clearCacheAPI();
      toast.success('Cache cleared successfully');
      refetchCache();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Clear cache failed');
    }
  };

  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  const _formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };
  void _formatBytes;

  return (
    <div className="embed-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Sparkles" size={28} />
          <div>
            <h1>Embeddings</h1>
            <p className="page-description">
              Vector embeddings and semantic similarity operations
            </p>
          </div>
        </div>
      </header>

      {/* Model Info Section */}
      <section className="model-info-section">
        <div className="section-header">
          <h2>
            <Icon name="Cpu" size={20} />
            Model Information
          </h2>
        </div>

        {loadingModels ? (
          <div className="loading-state">
            <Icon name="Loader" size={24} className="spinner" />
            Loading model info...
          </div>
        ) : currentModel ? (
          <div className="model-card">
            <div className="model-header">
              <div className="model-badge">
                <Icon name="CheckCircle2" size={16} />
                Active
              </div>
              <h3>{currentModel.name}</h3>
            </div>
            <div className="model-stats">
              <div className="model-stat">
                <Icon name="Layers" size={16} />
                <span className="stat-label">Dimensions:</span>
                <span className="stat-value">{formatNumber(currentModel.dimensions)}</span>
              </div>
              <div className="model-stat">
                <Icon name="FileText" size={16} />
                <span className="stat-label">Max Length:</span>
                <span className="stat-value">{formatNumber(currentModel.max_length)} tokens</span>
              </div>
              <div className="model-stat">
                <Icon name="HardDrive" size={16} />
                <span className="stat-label">Size:</span>
                <span className="stat-value">{currentModel.size_mb.toFixed(0)} MB</span>
              </div>
            </div>
            {currentModel.description && (
              <p className="model-description">{currentModel.description}</p>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <Icon name="AlertCircle" size={48} />
            <p>No model loaded</p>
          </div>
        )}
      </section>

      {/* Similarity Calculator */}
      <section className="similarity-section">
        <SimilarityCalculator />
      </section>

      {/* Nearest Neighbor Search */}
      <section className="nearest-search-section">
        <div className="section-header">
          <h2>
            <Icon name="Search" size={20} />
            Nearest Neighbor Search
          </h2>
          <p className="section-description">
            Find semantically similar vectors in the database
          </p>
        </div>

        <div className="search-controls">
          <div className="search-input-wrapper">
            <Icon name="Search" size={18} className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Enter query text to find similar vectors..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
          </div>

          <div className="search-options">
            <label className="option-label">
              Results:
              <select
                className="option-select"
                value={searchLimit}
                onChange={e => setSearchLimit(Number(e.target.value))}
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </label>

            <button
              className="button-primary"
              onClick={handleSearch}
              disabled={searching || !searchQuery.trim()}
            >
              {searching ? (
                <>
                  <Icon name="Loader" size={16} className="spinner" />
                  Searching...
                </>
              ) : (
                <>
                  <Icon name="Search" size={16} />
                  Search
                </>
              )}
            </button>
          </div>
        </div>

        {searchResults && (
          <div className="search-results">
            <div className="results-header">
              <span className="results-count">
                {searchResults.total} result{searchResults.total !== 1 ? 's' : ''}
              </span>
              <span className="results-meta">
                Query: {searchResults.query_dimensions}D vector
              </span>
            </div>

            {searchResults.neighbors.length === 0 ? (
              <div className="empty-state">
                <Icon name="SearchX" size={48} />
                <p>No similar vectors found</p>
              </div>
            ) : (
              <div className="results-list">
                {searchResults.neighbors.map((neighbor, idx) => (
                  <div key={neighbor.id} className="result-card">
                    <div className="result-rank">#{idx + 1}</div>
                    <div className="result-content">
                      <div className="result-header">
                        <span className="result-id">{neighbor.id}</span>
                        <span
                          className="result-score"
                          style={{
                            color: neighbor.score >= 0.8 ? '#22c55e' : neighbor.score >= 0.6 ? '#3b82f6' : '#f59e0b',
                          }}
                        >
                          {Math.round(neighbor.score * 100)}% similar
                        </span>
                      </div>
                      {neighbor.payload && Object.keys(neighbor.payload).length > 0 && (
                        <div className="result-payload">
                          {Object.entries(neighbor.payload).slice(0, 3).map(([key, value]) => (
                            <span key={key} className="payload-item">
                              <strong>{key}:</strong> {String(value).substring(0, 50)}
                              {String(value).length > 50 ? '...' : ''}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Document Embedding Queue */}
      <section className="document-embed-section">
        <div className="section-header">
          <h2>
            <Icon name="FileCode" size={20} />
            Embed Document
          </h2>
          <p className="section-description">
            Queue a document for asynchronous embedding
          </p>
        </div>

        <div className="embed-controls">
          <input
            type="text"
            className="doc-id-input"
            placeholder="Enter document ID..."
            value={docIdInput}
            onChange={e => setDocIdInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleEmbedDocument()}
          />
          <button
            className="button-primary"
            onClick={handleEmbedDocument}
            disabled={embeddingDoc || !docIdInput.trim()}
          >
            {embeddingDoc ? (
              <>
                <Icon name="Loader" size={16} className="spinner" />
                Queueing...
              </>
            ) : (
              <>
                <Icon name="Play" size={16} />
                Queue Embedding
              </>
            )}
          </button>
        </div>
      </section>

      {/* Cache Statistics */}
      <section className="cache-stats-section">
        <div className="section-header">
          <h2>
            <Icon name="Database" size={20} />
            Cache Statistics
          </h2>
          <button
            className="button-secondary"
            onClick={handleClearCache}
            disabled={clearingCache}
          >
            {clearingCache ? (
              <>
                <Icon name="Loader" size={14} className="spinner" />
                Clearing...
              </>
            ) : (
              <>
                <Icon name="Trash2" size={14} />
                Clear Cache
              </>
            )}
          </button>
        </div>

        {loadingCache ? (
          <div className="loading-state">
            <Icon name="Loader" size={24} className="spinner" />
            Loading cache stats...
          </div>
        ) : cacheStats ? (
          <div className="stats-grid">
            <div className="stat-card">
              <Icon name="TrendingUp" size={24} className="stat-icon" style={{ color: '#22c55e' }} />
              <div className="stat-content">
                <div className="stat-value">{formatNumber(cacheStats.hits)}</div>
                <div className="stat-label">Hits</div>
              </div>
            </div>

            <div className="stat-card">
              <Icon name="TrendingDown" size={24} className="stat-icon" style={{ color: '#ef4444' }} />
              <div className="stat-content">
                <div className="stat-value">{formatNumber(cacheStats.misses)}</div>
                <div className="stat-label">Misses</div>
              </div>
            </div>

            <div className="stat-card">
              <Icon name="Percent" size={24} className="stat-icon" style={{ color: '#3b82f6' }} />
              <div className="stat-content">
                <div className="stat-value">{(cacheStats.hit_rate * 100).toFixed(1)}%</div>
                <div className="stat-label">Hit Rate</div>
              </div>
            </div>

            <div className="stat-card">
              <Icon name="HardDrive" size={24} className="stat-icon" style={{ color: '#f59e0b' }} />
              <div className="stat-content">
                <div className="stat-value">
                  {cacheStats.size}/{cacheStats.max_size}
                </div>
                <div className="stat-label">Cache Size</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <Icon name="AlertCircle" size={48} />
            <p>No cache statistics available</p>
          </div>
        )}
      </section>

      <style>{`
        .embed-page {
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

        section {
          margin-bottom: 2rem;
        }

        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 1rem;
        }

        .section-header h2 {
          margin: 0;
          font-size: 1.25rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .section-description {
          margin: 0.25rem 0 0 0;
          color: #9ca3af;
          font-size: 0.875rem;
        }

        .model-card {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.75rem;
          padding: 1.5rem;
        }

        .model-header {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 1rem;
        }

        .model-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.25rem 0.75rem;
          background: #22c55e;
          color: white;
          border-radius: 9999px;
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .model-header h3 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #f9fafb;
        }

        .model-stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem;
          margin-bottom: 1rem;
        }

        .model-stat {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: #d1d5db;
          font-size: 0.875rem;
        }

        .stat-label {
          color: #9ca3af;
        }

        .stat-value {
          font-weight: 600;
          color: #f9fafb;
        }

        .model-description {
          margin: 0;
          color: #9ca3af;
          font-size: 0.875rem;
          line-height: 1.5;
        }

        .similarity-section {
          margin-bottom: 2rem;
        }

        .search-controls {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          margin-bottom: 1.5rem;
        }

        .search-input-wrapper {
          position: relative;
          display: flex;
          align-items: center;
        }

        .search-icon {
          position: absolute;
          left: 1rem;
          color: #9ca3af;
          pointer-events: none;
        }

        .search-input {
          width: 100%;
          padding: 0.75rem 1rem 0.75rem 3rem;
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          color: #f9fafb;
          font-size: 0.875rem;
          transition: border-color 0.15s;
        }

        .search-input:focus {
          outline: none;
          border-color: #6366f1;
        }

        .search-input::placeholder {
          color: #6b7280;
        }

        .search-options {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 1rem;
        }

        .option-label {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: #d1d5db;
          font-size: 0.875rem;
        }

        .option-select {
          padding: 0.5rem;
          background: #374151;
          border: 1px solid #4b5563;
          border-radius: 0.375rem;
          color: #f9fafb;
          font-size: 0.875rem;
          cursor: pointer;
        }

        .search-results {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.75rem;
          padding: 1.5rem;
        }

        .results-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
          padding-bottom: 0.75rem;
          border-bottom: 1px solid #374151;
        }

        .results-count {
          font-weight: 600;
          color: #f9fafb;
        }

        .results-meta {
          font-size: 0.875rem;
          color: #9ca3af;
        }

        .results-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .result-card {
          display: flex;
          gap: 1rem;
          padding: 1rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.5rem;
        }

        .result-rank {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 2.5rem;
          height: 2.5rem;
          background: #374151;
          border-radius: 0.375rem;
          font-weight: 700;
          color: #9ca3af;
          font-size: 0.875rem;
        }

        .result-content {
          flex: 1;
        }

        .result-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.5rem;
        }

        .result-id {
          font-weight: 500;
          color: #f9fafb;
          font-size: 0.875rem;
        }

        .result-score {
          font-weight: 600;
          font-size: 0.875rem;
        }

        .result-payload {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
          font-size: 0.75rem;
          color: #9ca3af;
        }

        .payload-item {
          display: block;
        }

        .payload-item strong {
          color: #d1d5db;
        }

        .embed-controls {
          display: flex;
          gap: 0.75rem;
        }

        .doc-id-input {
          flex: 1;
          padding: 0.75rem 1rem;
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          color: #f9fafb;
          font-size: 0.875rem;
          transition: border-color 0.15s;
        }

        .doc-id-input:focus {
          outline: none;
          border-color: #6366f1;
        }

        .doc-id-input::placeholder {
          color: #6b7280;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem;
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

        .stat-content .stat-value {
          font-size: 1.875rem;
          font-weight: 600;
          color: #f9fafb;
          line-height: 1;
        }

        .stat-content .stat-label {
          font-size: 0.875rem;
          color: #9ca3af;
          margin-top: 0.25rem;
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
        .button-secondary {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.625rem 1.25rem;
          border-radius: 0.375rem;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s;
          border: 1px solid transparent;
          white-space: nowrap;
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

        .button-secondary:hover:not(:disabled) {
          background: #4b5563;
        }

        .button-secondary:disabled {
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
