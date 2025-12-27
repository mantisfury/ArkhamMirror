/**
 * SearchPage - Main search interface
 *
 * Provides search input, filters, mode selection, and results display.
 */

import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { SearchResultCard } from './SearchResultCard';
import { useSearch } from './api';
import type { SearchMode, SearchFilters } from './types';

export function SearchPage() {
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Search state from URL
  const queryFromUrl = searchParams.get('q') || '';
  const modeFromUrl = (searchParams.get('mode') || 'hybrid') as SearchMode;

  // Local state
  const [query, setQuery] = useState(queryFromUrl);
  const [searchMode, setSearchMode] = useState<SearchMode>(modeFromUrl);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<SearchFilters>({});

  // Execute search when URL changes
  const { data, loading, error } = useSearch({
    query: queryFromUrl,
    request: {
      mode: searchMode,
      filters,
      limit: 20,
    },
    enabled: !!queryFromUrl,
  });

  // Update URL when search is executed
  const executeSearch = () => {
    if (!query.trim()) {
      toast.warning('Please enter a search query');
      return;
    }

    const params = new URLSearchParams();
    params.set('q', query);
    params.set('mode', searchMode);
    setSearchParams(params);
  };

  // Handle enter key in search input
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      executeSearch();
    }
  };

  // Update filter state
  const updateFilter = (key: keyof SearchFilters, value: unknown) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  // Clear all filters
  const clearFilters = () => {
    setFilters({});
  };

  // Handle view document
  const handleViewDocument = (docId: string) => {
    toast.info(`View document: ${docId}`);
    // TODO: Navigate to document viewer when available
  };

  // Handle find similar
  const handleFindSimilar = (docId: string) => {
    // Execute similarity search
    const params = new URLSearchParams();
    params.set('similar', docId);
    setSearchParams(params);
    toast.info('Finding similar documents...');
  };

  // Show error toast if search fails
  useEffect(() => {
    if (error) {
      toast.error(`Search failed: ${error.message}`);
    }
  }, [error, toast]);

  return (
    <div className="search-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Search" size={28} />
          <div>
            <h1>Search</h1>
            <p className="page-description">
              Hybrid semantic and keyword search across documents
            </p>
          </div>
        </div>
      </header>

      {/* Search Input Section */}
      <section className="search-input-section">
        <div className="search-input-wrapper">
          <Icon name="Search" size={20} className="search-input-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search documents, entities, and content..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          {query && (
            <button
              className="clear-search-button"
              onClick={() => setQuery('')}
              title="Clear search"
            >
              <Icon name="X" size={16} />
            </button>
          )}
          <button className="search-submit-button" onClick={executeSearch}>
            <Icon name="ArrowRight" size={18} />
            Search
          </button>
        </div>

        {/* Search Mode Toggle */}
        <div className="search-mode-toggle">
          <button
            className={`mode-button ${searchMode === 'hybrid' ? 'active' : ''}`}
            onClick={() => setSearchMode('hybrid')}
          >
            <Icon name="Sparkles" size={16} />
            Hybrid
          </button>
          <button
            className={`mode-button ${searchMode === 'semantic' ? 'active' : ''}`}
            onClick={() => setSearchMode('semantic')}
          >
            <Icon name="Brain" size={16} />
            Semantic
          </button>
          <button
            className={`mode-button ${searchMode === 'keyword' ? 'active' : ''}`}
            onClick={() => setSearchMode('keyword')}
          >
            <Icon name="Type" size={16} />
            Keyword
          </button>
        </div>

        {/* Filters Toggle */}
        <button
          className="filters-toggle-button"
          onClick={() => setShowFilters(!showFilters)}
        >
          <Icon name="Filter" size={16} />
          Filters
          {Object.keys(filters).length > 0 && (
            <span className="filter-count-badge">{Object.keys(filters).length}</span>
          )}
        </button>
      </section>

      {/* Filters Section */}
      {showFilters && (
        <section className="filters-section">
          <div className="filters-header">
            <h3>
              <Icon name="SlidersHorizontal" size={18} />
              Filter Results
            </h3>
            <button className="clear-filters-button" onClick={clearFilters}>
              <Icon name="X" size={14} />
              Clear All
            </button>
          </div>

          <div className="filters-grid">
            {/* Date Range */}
            <div className="filter-group">
              <label className="filter-label">
                <Icon name="Calendar" size={14} />
                Date Range
              </label>
              <div className="date-range-inputs">
                <input
                  type="date"
                  className="filter-input"
                  placeholder="From"
                  value={filters.date_from || ''}
                  onChange={e => updateFilter('date_from', e.target.value)}
                />
                <span>to</span>
                <input
                  type="date"
                  className="filter-input"
                  placeholder="To"
                  value={filters.date_to || ''}
                  onChange={e => updateFilter('date_to', e.target.value)}
                />
              </div>
            </div>

            {/* File Types */}
            <div className="filter-group">
              <label className="filter-label">
                <Icon name="FileType" size={14} />
                File Types
              </label>
              <div className="filter-checkboxes">
                {['PDF', 'TXT', 'JSON', 'CSV', 'DOCX'].map(type => (
                  <label key={type} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={filters.file_types?.includes(type) || false}
                      onChange={e => {
                        const current = filters.file_types || [];
                        updateFilter(
                          'file_types',
                          e.target.checked
                            ? [...current, type]
                            : current.filter(t => t !== type)
                        );
                      }}
                    />
                    {type}
                  </label>
                ))}
              </div>
            </div>

            {/* Entity Types */}
            <div className="filter-group">
              <label className="filter-label">
                <Icon name="Tag" size={14} />
                Entity Types
              </label>
              <div className="filter-checkboxes">
                {['PERSON', 'ORG', 'LOCATION', 'DATE', 'MONEY'].map(type => (
                  <label key={type} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={filters.entity_types?.includes(type) || false}
                      onChange={e => {
                        const current = filters.entity_types || [];
                        updateFilter(
                          'entity_types',
                          e.target.checked
                            ? [...current, type]
                            : current.filter(t => t !== type)
                        );
                      }}
                    />
                    {type}
                  </label>
                ))}
              </div>
            </div>

            {/* Project Filter */}
            <div className="filter-group">
              <label className="filter-label">
                <Icon name="Folder" size={14} />
                Project
              </label>
              <input
                type="text"
                className="filter-input"
                placeholder="Project ID or name"
                value={filters.project_id || ''}
                onChange={e => updateFilter('project_id', e.target.value)}
              />
            </div>
          </div>
        </section>
      )}

      {/* Results Section */}
      {queryFromUrl && (
        <section className="results-section">
          {loading && (
            <div className="results-loading">
              <Icon name="Loader2" size={32} className="spinner" />
              <p>Searching...</p>
            </div>
          )}

          {error && (
            <div className="results-error">
              <Icon name="AlertCircle" size={32} />
              <p>Search failed: {error.message}</p>
            </div>
          )}

          {data && !loading && (
            <>
              <div className="results-header">
                <div className="results-info">
                  <h2>
                    {data.total.toLocaleString()} results for "{data.query}"
                  </h2>
                  <p className="results-meta">
                    {data.mode.charAt(0).toUpperCase() + data.mode.slice(1)} search
                    <span className="separator">•</span>
                    {data.duration_ms.toFixed(0)}ms
                  </p>
                </div>
              </div>

              {data.items.length === 0 && (
                <div className="results-empty">
                  <Icon name="SearchX" size={48} />
                  <h3>No results found</h3>
                  <p>Try adjusting your search query or filters</p>
                </div>
              )}

              <div className="results-list">
                {data.items.map(result => (
                  <SearchResultCard
                    key={`${result.doc_id}-${result.chunk_id || 'doc'}`}
                    result={result}
                    onView={handleViewDocument}
                    onFindSimilar={handleFindSimilar}
                  />
                ))}
              </div>

              {data.has_more && (
                <div className="results-pagination">
                  <button className="load-more-button">
                    <Icon name="ChevronDown" size={16} />
                    Load More
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {/* Empty State */}
      {!queryFromUrl && !loading && (
        <section className="search-empty-state">
          <Icon name="Search" size={64} className="empty-state-icon" />
          <h2>Start searching</h2>
          <p>Enter a query to search across all documents, entities, and content</p>
          <div className="search-tips">
            <h3>Search tips:</h3>
            <ul>
              <li>
                <Icon name="Sparkles" size={14} />
                <strong>Hybrid:</strong> Best of semantic and keyword search
              </li>
              <li>
                <Icon name="Brain" size={14} />
                <strong>Semantic:</strong> Find conceptually related content
              </li>
              <li>
                <Icon name="Type" size={14} />
                <strong>Keyword:</strong> Exact text matching
              </li>
            </ul>
          </div>
        </section>
      )}
    </div>
  );
}
