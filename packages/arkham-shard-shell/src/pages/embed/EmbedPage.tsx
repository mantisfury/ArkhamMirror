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
import {
  useModels,
  useCacheStats,
  useNearest,
  useEmbedDocument,
  useClearCache,
  useAvailableModels,
  useVectorCollections,
  useCheckModelSwitch,
  useSwitchModel,
} from './api';
import type { AvailableModel, ModelSwitchCheckResult } from './types';

export function EmbedPage() {
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLimit, setSearchLimit] = useState(10);
  const [docIdInput, setDocIdInput] = useState('');

  // Model management state
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [showWipeConfirm, setShowWipeConfirm] = useState(false);
  const [switchCheckResult, setSwitchCheckResult] = useState<ModelSwitchCheckResult | null>(null);

  const { data: models, loading: loadingModels } = useModels();
  const { data: availableModels, loading: loadingAvailable, refetch: refetchAvailable } = useAvailableModels();
  const { data: collections, refetch: refetchCollections } = useVectorCollections();
  const { data: cacheStats, loading: loadingCache, refetch: refetchCache } = useCacheStats();
  const { search, data: searchResults, loading: searching } = useNearest();
  const { embed: embedDoc, loading: embeddingDoc } = useEmbedDocument();
  const { clear: clearCacheAPI, loading: clearingCache } = useClearCache();
  const { check: checkSwitch, loading: checkingSwitch } = useCheckModelSwitch();
  const { switchTo: switchModelAPI, loading: switchingModel } = useSwitchModel();

  // Auto-refresh cache stats
  useEffect(() => {
    const interval = setInterval(() => {
      refetchCache();
    }, 10000); // Refresh every 10 seconds

    return () => clearInterval(interval);
  }, [refetchCache]);

  const currentModel = models?.find(m => m.loaded) || availableModels?.find(m => m.is_current);

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

  const handleModelSelect = async (model: AvailableModel) => {
    if (model.is_current) {
      toast.info('This model is already active');
      return;
    }

    setSelectedModel(model.name);

    try {
      const result = await checkSwitch(model.name);
      setSwitchCheckResult(result);

      if (result.requires_wipe) {
        setShowWipeConfirm(true);
      } else {
        // No wipe needed, switch directly
        await performModelSwitch(model.name, false);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to check model switch');
      setSelectedModel(null);
    }
  };

  const performModelSwitch = async (modelName: string, confirmWipe: boolean) => {
    try {
      const result = await switchModelAPI(modelName, confirmWipe);

      if (result.success) {
        toast.success(result.message);
        // Refresh all model-related data
        refetchAvailable();
        refetchCollections();
        refetchCache();
      } else if (result.requires_wipe) {
        // Need confirmation
        setSwitchCheckResult({
          success: false,
          requires_wipe: true,
          message: result.message,
          current_model: result.previous_model || '',
          current_dimensions: result.previous_dimensions || 0,
          new_model: modelName,
          new_dimensions: result.new_dimensions,
          affected_collections: result.affected_collections,
        });
        setShowWipeConfirm(true);
      } else {
        toast.error(result.message);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Model switch failed');
    } finally {
      if (!showWipeConfirm) {
        setSelectedModel(null);
        setSwitchCheckResult(null);
      }
    }
  };

  const handleConfirmWipe = async () => {
    if (!selectedModel) return;

    setShowWipeConfirm(false);
    await performModelSwitch(selectedModel, true);
    setSelectedModel(null);
    setSwitchCheckResult(null);
  };

  const handleCancelWipe = () => {
    setShowWipeConfirm(false);
    setSelectedModel(null);
    setSwitchCheckResult(null);
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

      {/* Model Selection Section */}
      <section className="model-selection-section">
        <div className="section-header">
          <h2>
            <Icon name="RefreshCw" size={20} />
            Switch Embedding Model
          </h2>
          <p className="section-description">
            Select a different embedding model. Different dimensions require wiping the vector database.
          </p>
        </div>

        {loadingAvailable ? (
          <div className="loading-state">
            <Icon name="Loader" size={24} className="spinner" />
            Loading available models...
          </div>
        ) : availableModels && availableModels.length > 0 ? (
          <div className="model-grid">
            {availableModels.map((model) => (
              <div
                key={model.name}
                className={`model-option ${model.is_current ? 'active' : ''} ${selectedModel === model.name && (checkingSwitch || switchingModel) ? 'loading' : ''}`}
                onClick={() => handleModelSelect(model)}
              >
                <div className="model-option-header">
                  <h4>{model.name}</h4>
                  {model.is_current && (
                    <span className="current-badge">
                      <Icon name="CheckCircle2" size={14} />
                      Current
                    </span>
                  )}
                  {selectedModel === model.name && (checkingSwitch || switchingModel) && (
                    <Icon name="Loader" size={16} className="spinner" />
                  )}
                </div>
                <div className="model-option-stats">
                  <span className="model-dim">
                    <Icon name="Layers" size={12} />
                    {model.dimensions}D
                  </span>
                  <span className="model-size">
                    <Icon name="HardDrive" size={12} />
                    {model.size_mb}MB
                  </span>
                </div>
                <p className="model-option-desc">{model.description}</p>
                {currentModel && model.dimensions !== currentModel.dimensions && !model.is_current && (
                  <div className="dimension-warning">
                    <Icon name="AlertTriangle" size={14} />
                    Requires database wipe ({currentModel.dimensions}D → {model.dimensions}D)
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <Icon name="AlertCircle" size={48} />
            <p>No models available</p>
          </div>
        )}

        {/* Vector Collections Info */}
        {collections && collections.length > 0 && (
          <div className="collections-info">
            <h4>
              <Icon name="Database" size={16} />
              Vector Collections
            </h4>
            <div className="collections-grid">
              {collections.map((coll) => (
                <div key={coll.name} className="collection-item">
                  <span className="collection-name">{coll.name}</span>
                  <span className="collection-stats">
                    {formatNumber(coll.points_count)} vectors ({coll.vector_size}D)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Wipe Confirmation Modal */}
      {showWipeConfirm && switchCheckResult && (
        <div className="modal-overlay" onClick={handleCancelWipe}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <Icon name="AlertTriangle" size={24} className="warning-icon" />
              <h3>Vector Database Wipe Required</h3>
            </div>
            <div className="modal-body">
              <p className="warning-text">
                Switching from <strong>{switchCheckResult.current_model}</strong> ({switchCheckResult.current_dimensions}D)
                to <strong>{switchCheckResult.new_model}</strong> ({switchCheckResult.new_dimensions}D)
                requires wiping all vector embeddings.
              </p>
              {switchCheckResult.affected_collections.length > 0 && (
                <div className="affected-collections">
                  <p>The following collections will be wiped:</p>
                  <ul>
                    {switchCheckResult.affected_collections.map(name => (
                      <li key={name}>{name}</li>
                    ))}
                  </ul>
                  {switchCheckResult.total_vectors_affected !== undefined && (
                    <p className="vectors-count">
                      <Icon name="AlertCircle" size={14} />
                      {formatNumber(switchCheckResult.total_vectors_affected)} vectors will be deleted
                    </p>
                  )}
                </div>
              )}
              <p className="warning-note">
                After switching, you will need to re-embed all documents with the new model.
              </p>
            </div>
            <div className="modal-actions">
              <button className="button-secondary" onClick={handleCancelWipe}>
                Cancel
              </button>
              <button className="button-danger" onClick={handleConfirmWipe} disabled={switchingModel}>
                {switchingModel ? (
                  <>
                    <Icon name="Loader" size={16} className="spinner" />
                    Switching...
                  </>
                ) : (
                  <>
                    <Icon name="Trash2" size={16} />
                    Wipe & Switch Model
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

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

        /* Model Selection Styles */
        .model-selection-section {
          margin-bottom: 2rem;
        }

        .model-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 1rem;
        }

        .model-option {
          background: #1f2937;
          border: 2px solid #374151;
          border-radius: 0.75rem;
          padding: 1.25rem;
          cursor: pointer;
          transition: all 0.15s;
        }

        .model-option:hover:not(.active):not(.loading) {
          border-color: #6366f1;
          background: #1e293b;
        }

        .model-option.active {
          border-color: #22c55e;
          background: rgba(34, 197, 94, 0.1);
        }

        .model-option.loading {
          opacity: 0.7;
          cursor: wait;
        }

        .model-option-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.5rem;
          margin-bottom: 0.75rem;
        }

        .model-option-header h4 {
          margin: 0;
          font-size: 0.875rem;
          font-weight: 600;
          color: #f9fafb;
          word-break: break-all;
        }

        .current-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.25rem;
          padding: 0.125rem 0.5rem;
          background: #22c55e;
          color: white;
          border-radius: 9999px;
          font-size: 0.625rem;
          font-weight: 600;
          text-transform: uppercase;
          white-space: nowrap;
        }

        .model-option-stats {
          display: flex;
          gap: 1rem;
          margin-bottom: 0.75rem;
        }

        .model-dim,
        .model-size {
          display: inline-flex;
          align-items: center;
          gap: 0.25rem;
          padding: 0.25rem 0.5rem;
          background: #374151;
          border-radius: 0.25rem;
          font-size: 0.75rem;
          color: #d1d5db;
        }

        .model-option-desc {
          margin: 0;
          font-size: 0.75rem;
          color: #9ca3af;
          line-height: 1.4;
        }

        .dimension-warning {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          margin-top: 0.75rem;
          padding: 0.5rem;
          background: rgba(245, 158, 11, 0.1);
          border: 1px solid rgba(245, 158, 11, 0.3);
          border-radius: 0.375rem;
          color: #f59e0b;
          font-size: 0.75rem;
        }

        .collections-info {
          margin-top: 1.5rem;
          padding: 1rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.5rem;
        }

        .collections-info h4 {
          margin: 0 0 0.75rem 0;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.875rem;
          font-weight: 500;
          color: #d1d5db;
        }

        .collections-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
        }

        .collection-item {
          display: flex;
          flex-direction: column;
          gap: 0.125rem;
          padding: 0.5rem 0.75rem;
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.375rem;
        }

        .collection-name {
          font-size: 0.75rem;
          font-weight: 600;
          color: #f9fafb;
        }

        .collection-stats {
          font-size: 0.625rem;
          color: #9ca3af;
        }

        /* Modal Styles */
        .modal-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.75);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 1rem;
        }

        .modal-content {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.75rem;
          max-width: 500px;
          width: 100%;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }

        .modal-header {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 1.25rem;
          border-bottom: 1px solid #374151;
        }

        .modal-header .warning-icon {
          color: #f59e0b;
        }

        .modal-header h3 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #f9fafb;
        }

        .modal-body {
          padding: 1.25rem;
        }

        .warning-text {
          margin: 0 0 1rem 0;
          color: #d1d5db;
          line-height: 1.5;
        }

        .warning-text strong {
          color: #f9fafb;
        }

        .affected-collections {
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1rem;
          margin-bottom: 1rem;
        }

        .affected-collections p {
          margin: 0 0 0.5rem 0;
          color: #9ca3af;
          font-size: 0.875rem;
        }

        .affected-collections ul {
          margin: 0;
          padding-left: 1.25rem;
          color: #d1d5db;
          font-size: 0.875rem;
        }

        .affected-collections li {
          margin-bottom: 0.25rem;
        }

        .vectors-count {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          margin-top: 0.75rem !important;
          padding-top: 0.75rem;
          border-top: 1px solid #374151;
          color: #ef4444;
          font-size: 0.875rem;
          font-weight: 500;
        }

        .warning-note {
          margin: 0;
          color: #9ca3af;
          font-size: 0.875rem;
          font-style: italic;
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 0.75rem;
          padding: 1rem 1.25rem;
          border-top: 1px solid #374151;
          background: #111827;
          border-radius: 0 0 0.75rem 0.75rem;
        }

        .button-danger {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.625rem 1.25rem;
          background: #dc2626;
          color: white;
          border: none;
          border-radius: 0.375rem;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.15s;
        }

        .button-danger:hover:not(:disabled) {
          background: #b91c1c;
        }

        .button-danger:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}
