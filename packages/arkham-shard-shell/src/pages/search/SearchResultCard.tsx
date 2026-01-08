/**
 * SearchResultCard - Individual search result display
 *
 * Displays a single search result with title, snippet, metadata, and actions.
 */

import { Icon } from '../../components/common/Icon';
import { sanitizeHighlight } from '../../utils/sanitize';
import type { SearchResultItem } from './types';

interface SearchResultCardProps {
  result: SearchResultItem;
  onView?: (docId: string) => void;
  onFindSimilar?: (docId: string) => void;
  onAskAbout?: (result: SearchResultItem) => void;
}

export function SearchResultCard({ result, onView, onFindSimilar, onAskAbout }: SearchResultCardProps) {
  // Format date if available
  const formattedDate = result.created_at
    ? new Date(result.created_at).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : null;

  // Get file type icon
  const getFileIcon = (fileType: string | null) => {
    if (!fileType) return 'FileText';
    const lower = fileType.toLowerCase();
    if (lower.includes('pdf')) return 'FileType';
    if (lower.includes('doc')) return 'FileText';
    if (lower.includes('txt')) return 'FileText';
    if (lower.includes('json')) return 'Braces';
    if (lower.includes('csv')) return 'Table';
    return 'FileText';
  };

  // Render excerpt with highlights
  const renderExcerpt = () => {
    if (result.highlights && result.highlights.length > 0) {
      // Use first highlight
      return (
        <div
          className="search-result-excerpt"
          dangerouslySetInnerHTML={{ __html: sanitizeHighlight(result.highlights[0]) }}
        />
      );
    }
    return <div className="search-result-excerpt">{result.excerpt}</div>;
  };

  return (
    <div className="search-result-card">
      <div className="search-result-header">
        <div className="search-result-title-row">
          <Icon name={getFileIcon(result.file_type)} size={18} className="result-file-icon" />
          <h3 className="search-result-title">{result.title}</h3>
        </div>
        <div className="search-result-score-badge">
          {(result.score * 100).toFixed(0)}%
        </div>
      </div>

      {renderExcerpt()}

      <div className="search-result-metadata">
        <div className="metadata-tags">
          {result.file_type && (
            <span className="metadata-tag">
              <Icon name="FileType" size={12} />
              {result.file_type}
            </span>
          )}
          {formattedDate && (
            <span className="metadata-tag">
              <Icon name="Calendar" size={12} />
              {formattedDate}
            </span>
          )}
          {result.page_number !== null && (
            <span className="metadata-tag">
              <Icon name="BookOpen" size={12} />
              Page {result.page_number}
            </span>
          )}
          {result.chunk_id && (
            <span className="metadata-tag">
              <Icon name="Hash" size={12} />
              Chunk
            </span>
          )}
        </div>

        {result.entities && result.entities.length > 0 && (
          <div className="metadata-entities">
            <Icon name="Tag" size={12} />
            <div className="entity-tags">
              {result.entities.slice(0, 5).map((entity, idx) => (
                <span key={idx} className="entity-tag">
                  {entity}
                </span>
              ))}
              {result.entities.length > 5 && (
                <span className="entity-tag more">+{result.entities.length - 5} more</span>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="search-result-actions">
        {onView && (
          <button
            className="action-button primary"
            onClick={() => onView(result.doc_id)}
            title="View document"
          >
            <Icon name="Eye" size={16} />
            View
          </button>
        )}
        {onAskAbout && (
          <button
            className="action-button ai"
            onClick={() => onAskAbout(result)}
            title="Ask AI about this document"
          >
            <Icon name="MessageSquare" size={16} />
            Ask AI
          </button>
        )}
        {onFindSimilar && (
          <button
            className="action-button secondary"
            onClick={() => onFindSimilar(result.doc_id)}
            title="Find similar documents"
          >
            <Icon name="GitCompare" size={16} />
            Similar
          </button>
        )}
        <button
          className="action-button secondary"
          onClick={() => navigator.clipboard.writeText(result.doc_id)}
          title="Copy document ID"
        >
          <Icon name="Copy" size={16} />
        </button>
      </div>
    </div>
  );
}
