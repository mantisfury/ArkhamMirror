/**
 * SimilarImagesPanel - Grid display of similar/duplicate images
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useToast } from '../../../context/ToastContext';
import * as api from '../api';
import type { MediaAnalysis, SimilarImagesResult, SimilarImage } from '../types';

interface SimilarImagesPanelProps {
  analysis: MediaAnalysis;
  onSearch?: () => void;
}

export function SimilarImagesPanel({ analysis, onSearch }: SimilarImagesPanelProps) {
  const { toast } = useToast();
  const [result, setResult] = useState<SimilarImagesResult | null>(
    analysis.similar_images_result
  );
  const [searching, setSearching] = useState(false);
  const [searchType, setSearchType] = useState<'internal' | 'external' | 'both'>('internal');
  const [selectedImage, setSelectedImage] = useState<SimilarImage | null>(null);

  const handleSearch = useCallback(async () => {
    setSearching(true);
    try {
      const response = await api.findSimilar({
        analysis_id: analysis.id,
        search_type: searchType,
        limit: 50,
      });
      setResult(response.result);
      toast.success(
        `Found ${response.result.total_found} similar image${response.result.total_found !== 1 ? 's' : ''}`
      );
      onSearch?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to search for similar images');
    } finally {
      setSearching(false);
    }
  }, [analysis.id, searchType, toast, onSearch]);

  const getSimilarityTypeLabel = (type: SimilarImage['similarity_type']): string => {
    switch (type) {
      case 'exact':
        return 'Exact Match';
      case 'near_duplicate':
        return 'Near Duplicate';
      case 'visually_similar':
        return 'Visually Similar';
      case 'content_similar':
        return 'Content Similar';
      default:
        return type;
    }
  };

  const getSimilarityTypeColor = (type: SimilarImage['similarity_type']): string => {
    switch (type) {
      case 'exact':
        return 'var(--error, #ef4444)';
      case 'near_duplicate':
        return 'var(--warning, #f97316)';
      case 'visually_similar':
        return 'var(--warning, #eab308)';
      case 'content_similar':
        return 'var(--info, #3b82f6)';
      default:
        return 'var(--color-text-muted)';
    }
  };

  // No search performed yet
  if (!result) {
    return (
      <div className="similar-images-container">
        <div className="panel-empty">
          <Icon name="Images" size={48} />
          <p>Similar image search not yet performed</p>
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
            Search for visually similar or duplicate images in the document collection
          </p>
        </div>

        <div className="search-options">
          <div className="panel-section-header">
            <Icon name="Settings" size={16} />
            <h4>Search Options</h4>
          </div>
          <div className="search-type-selector">
            <label>
              <input
                type="radio"
                name="searchType"
                value="internal"
                checked={searchType === 'internal'}
                onChange={() => setSearchType('internal')}
              />
              <span>Internal (document collection only)</span>
            </label>
            <label>
              <input
                type="radio"
                name="searchType"
                value="external"
                checked={searchType === 'external'}
                onChange={() => setSearchType('external')}
              />
              <span>External (reverse image search)</span>
            </label>
            <label>
              <input
                type="radio"
                name="searchType"
                value="both"
                checked={searchType === 'both'}
                onChange={() => setSearchType('both')}
              />
              <span>Both internal and external</span>
            </label>
          </div>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleSearch}
          disabled={searching}
          style={{ alignSelf: 'center' }}
        >
          {searching ? (
            <>
              <Icon name="Loader2" size={16} className="spin" />
              Searching...
            </>
          ) : (
            <>
              <Icon name="Search" size={16} />
              Search Similar Images
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="similar-images-container">
      {/* Summary Stats */}
      <div className="similar-stats">
        <div className="similar-stat">
          <span className="stat-value">{result.total_found}</span>
          <span className="stat-label">Total Found</span>
        </div>
        <div className="similar-stat">
          <span className="stat-value" style={{ color: 'var(--error)' }}>
            {result.exact_matches}
          </span>
          <span className="stat-label">Exact Matches</span>
        </div>
        <div className="similar-stat">
          <span className="stat-value" style={{ color: 'var(--warning)' }}>
            {result.near_duplicates}
          </span>
          <span className="stat-label">Near Duplicates</span>
        </div>
        <div className="similar-stat">
          <span className="stat-value" style={{ color: 'var(--info)' }}>
            {result.visually_similar}
          </span>
          <span className="stat-label">Visually Similar</span>
        </div>
      </div>

      {/* Search URLs for Manual Reverse Image Search */}
      {result.search_urls && result.search_urls.length > 0 && (
        <div className="reverse-search-urls">
          <div className="panel-section-header">
            <Icon name="ExternalLink" size={16} />
            <h4>Reverse Image Search</h4>
            <span className="section-subtitle">Click to search on external engines</span>
          </div>
          <div className="search-urls-grid">
            {result.search_urls.map((searchUrl, idx) => (
              <a
                key={idx}
                href={searchUrl.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`search-url-card ${searchUrl.type}`}
                title={searchUrl.instructions || searchUrl.description}
              >
                <div className="search-url-icon">
                  {searchUrl.engine === 'Google Lens' && <Icon name="Search" size={20} />}
                  {searchUrl.engine === 'Google Images' && <Icon name="Image" size={20} />}
                  {searchUrl.engine === 'TinEye' && <Icon name="Eye" size={20} />}
                  {searchUrl.engine === 'Yandex Images' && <Icon name="Globe" size={20} />}
                  {searchUrl.engine === 'Bing Visual Search' && <Icon name="Search" size={20} />}
                </div>
                <div className="search-url-info">
                  <span className="search-url-engine">{searchUrl.engine}</span>
                  <span className="search-url-type">
                    {searchUrl.type === 'url_search' ? 'Direct Search' : 'Upload Required'}
                  </span>
                </div>
                <Icon name="ExternalLink" size={14} className="external-icon" />
              </a>
            ))}
          </div>
          {result.search_urls.some(u => u.type === 'upload_search') && (
            <p className="search-url-note">
              <Icon name="Info" size={12} />
              For "Upload Required" links, download the image first, then upload it to the search engine.
            </p>
          )}
        </div>
      )}

      {/* No Results */}
      {result.similar_images.length === 0 && !result.search_urls?.length && (
        <div className="panel-empty">
          <Icon name="CheckCircle" size={48} />
          <p>No similar images found</p>
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
            This image appears to be unique in the searched collection
          </p>
        </div>
      )}

      {result.similar_images.length === 0 && (result.search_urls?.length ?? 0) > 0 && (
        <div className="panel-info">
          <Icon name="Info" size={16} />
          <p>No automatic results found. Use the reverse image search links above to search manually.</p>
        </div>
      )}

      {/* Results Grid */}
      {result.similar_images.length > 0 && (
        <div className="similar-images-grid">
          {result.similar_images.map((image) => (
            <div
              key={image.id}
              className={`similar-image-card ${selectedImage?.id === image.id ? 'selected' : ''}`}
              onClick={() => setSelectedImage(selectedImage?.id === image.id ? null : image)}
            >
              {/* Thumbnail */}
              {image.thumbnail_url ? (
                <img
                  src={image.thumbnail_url}
                  alt={image.filename}
                  className="similar-image-thumb"
                />
              ) : image.thumbnail_base64 ? (
                <img
                  src={`data:image/jpeg;base64,${image.thumbnail_base64}`}
                  alt={image.filename}
                  className="similar-image-thumb"
                />
              ) : (
                <div className="similar-image-thumb placeholder">
                  <Icon name="Image" size={24} />
                </div>
              )}

              {/* Similarity Badge */}
              <div
                className="similarity-badge"
                style={{ backgroundColor: getSimilarityTypeColor(image.similarity_type) }}
              >
                {Math.round(image.similarity_score * 100)}%
              </div>

              {/* Info */}
              <div className="similar-image-info">
                <div className="similar-image-score">
                  {getSimilarityTypeLabel(image.similarity_type)}
                </div>
                <div className="similar-image-type">{image.filename}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Selected Image Details */}
      {selectedImage && (
        <div className="selected-image-details">
          <div className="panel-section-header">
            <Icon name="Info" size={16} />
            <h4>Match Details</h4>
            <button
              className="close-btn"
              onClick={() => setSelectedImage(null)}
              style={{ marginLeft: 'auto' }}
            >
              <Icon name="X" size={14} />
            </button>
          </div>
          <div className="metadata-grid">
            <div className="metadata-item">
              <span className="metadata-label">Filename</span>
              <span className="metadata-value">{selectedImage.filename}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Similarity</span>
              <span className="metadata-value">
                {(selectedImage.similarity_score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Type</span>
              <span className="metadata-value">
                {getSimilarityTypeLabel(selectedImage.similarity_type)}
              </span>
            </div>
            {selectedImage.source && (
              <div className="metadata-item">
                <span className="metadata-label">Source</span>
                <span className="metadata-value">{selectedImage.source}</span>
              </div>
            )}
            {selectedImage.match_details.hash_distance !== undefined && (
              <div className="metadata-item">
                <span className="metadata-label">Hash Distance</span>
                <span className="metadata-value">{selectedImage.match_details.hash_distance}</span>
              </div>
            )}
            {selectedImage.match_details.feature_similarity !== undefined && (
              <div className="metadata-item">
                <span className="metadata-label">Feature Similarity</span>
                <span className="metadata-value">
                  {(selectedImage.match_details.feature_similarity * 100).toFixed(1)}%
                </span>
              </div>
            )}
            <div className="metadata-item">
              <span className="metadata-label">Found At</span>
              <span className="metadata-value">
                {new Date(selectedImage.found_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Re-search Controls */}
      <div className="search-controls">
        <div className="search-type-selector inline">
          <select
            value={searchType}
            onChange={(e) => setSearchType(e.target.value as 'internal' | 'external' | 'both')}
            disabled={searching}
          >
            <option value="internal">Internal Only</option>
            <option value="external">External Only</option>
            <option value="both">Both</option>
          </select>
        </div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={handleSearch}
          disabled={searching}
        >
          {searching ? (
            <>
              <Icon name="Loader2" size={14} className="spin" />
              Searching...
            </>
          ) : (
            <>
              <Icon name="RefreshCw" size={14} />
              Search Again
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default SimilarImagesPanel;
