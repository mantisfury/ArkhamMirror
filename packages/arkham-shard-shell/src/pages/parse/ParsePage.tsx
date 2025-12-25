/**
 * ParsePage - Main parse page with NER testing
 *
 * Features:
 * - Text input area for quick NER testing
 * - Extract entities button
 * - Results display showing entities by type with icons
 * - Entity counts summary
 * - Recent parsed documents list
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useParseText, useParseStats } from './api';
import type { EntityMention, DateMention, EntityType } from './types';

export function ParsePage() {
  const { toast } = useToast();
  const [text, setText] = useState('');
  const [results, setResults] = useState<{
    entities: EntityMention[];
    dates: DateMention[];
    processing_time_ms: number;
  } | null>(null);

  const { parse, loading } = useParseText();
  const { data: stats, loading: loadingStats } = useParseStats();

  const handleExtractEntities = useCallback(async () => {
    if (!text.trim()) {
      toast.warning('Please enter some text to parse');
      return;
    }

    try {
      const result = await parse({
        text,
        extract_entities: true,
        extract_dates: true,
        extract_locations: true,
        extract_relationships: false,
      });

      setResults({
        entities: result.entities,
        dates: result.dates,
        processing_time_ms: result.processing_time_ms,
      });

      toast.success(
        `Extracted ${result.total_entities} entities and ${result.total_dates} dates in ${result.processing_time_ms.toFixed(0)}ms`
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Extraction failed');
    }
  }, [text, parse, toast]);

  const handleClear = useCallback(() => {
    setText('');
    setResults(null);
  }, []);

  // Get entity icon and color by type
  const getEntityTypeConfig = (type: EntityType) => {
    switch (type) {
      case 'PERSON':
        return { icon: 'User' as const, color: '#3b82f6', label: 'People' };
      case 'ORG':
        return { icon: 'Building2' as const, color: '#8b5cf6', label: 'Organizations' };
      case 'LOCATION':
      case 'GPE':
        return { icon: 'MapPin' as const, color: '#10b981', label: 'Locations' };
      case 'DATE':
        return { icon: 'Calendar' as const, color: '#f59e0b', label: 'Dates' };
      case 'MONEY':
        return { icon: 'DollarSign' as const, color: '#22c55e', label: 'Money' };
      case 'EVENT':
        return { icon: 'Zap' as const, color: '#ec4899', label: 'Events' };
      case 'PRODUCT':
        return { icon: 'Package' as const, color: '#06b6d4', label: 'Products' };
      default:
        return { icon: 'Tag' as const, color: '#6b7280', label: type };
    }
  };

  // Group entities by type
  const groupEntitiesByType = (entities: EntityMention[], dates: DateMention[]) => {
    const grouped: Record<string, Array<EntityMention | DateMention>> = {};

    entities.forEach(entity => {
      const type = entity.entity_type;
      if (!grouped[type]) {
        grouped[type] = [];
      }
      grouped[type].push(entity);
    });

    if (dates.length > 0) {
      grouped['DATE'] = dates;
    }

    return grouped;
  };

  const entityGroups = results
    ? groupEntitiesByType(results.entities, results.dates)
    : {};

  return (
    <div className="parse-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Sparkles" size={28} />
          <div>
            <h1>Parse</h1>
            <p className="page-description">Extract entities, dates, and locations from text</p>
          </div>
        </div>
      </header>

      {/* Statistics Cards */}
      <section className="stats-grid">
        <div className="stat-card">
          <Icon name="Tag" size={24} className="stat-icon" style={{ color: '#6366f1' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingStats ? '...' : stats?.total_entities ?? 0}</div>
            <div className="stat-label">Total Entities</div>
          </div>
        </div>
        <div className="stat-card">
          <Icon name="FileText" size={24} className="stat-icon" style={{ color: '#3b82f6' }} />
          <div className="stat-content">
            <div className="stat-value">{loadingStats ? '...' : stats?.total_chunks ?? 0}</div>
            <div className="stat-label">Text Chunks</div>
          </div>
        </div>
        <div className="stat-card">
          <Icon name="File" size={24} className="stat-icon" style={{ color: '#22c55e' }} />
          <div className="stat-content">
            <div className="stat-value">
              {loadingStats ? '...' : stats?.total_documents_parsed ?? 0}
            </div>
            <div className="stat-label">Documents Parsed</div>
          </div>
        </div>
      </section>

      {/* Text Input Section */}
      <section className="parse-input-section">
        <div className="input-header">
          <h2>
            <Icon name="Type" size={20} />
            Extract Entities from Text
          </h2>
          <div className="input-actions">
            {text && (
              <button className="button-secondary" onClick={handleClear}>
                <Icon name="X" size={16} />
                Clear
              </button>
            )}
            <button
              className="button-primary"
              onClick={handleExtractEntities}
              disabled={loading || !text.trim()}
            >
              {loading ? (
                <>
                  <Icon name="Loader" size={18} className="spinner" />
                  Extracting...
                </>
              ) : (
                <>
                  <Icon name="Sparkles" size={18} />
                  Extract Entities
                </>
              )}
            </button>
          </div>
        </div>

        <textarea
          className="text-input"
          placeholder="Enter or paste text to extract entities, people, organizations, locations, dates, and more..."
          value={text}
          onChange={e => setText(e.target.value)}
          rows={10}
        />
      </section>

      {/* Results Section */}
      {results && (
        <section className="results-section">
          <div className="results-header">
            <h2>
              <Icon name="CheckCircle" size={20} />
              Extracted Entities
            </h2>
            <div className="results-meta">
              <span>
                {results.entities.length + results.dates.length} entities
              </span>
              <span className="separator">•</span>
              <span>{results.processing_time_ms.toFixed(0)}ms</span>
            </div>
          </div>

          {Object.keys(entityGroups).length === 0 ? (
            <div className="empty-state">
              <Icon name="SearchX" size={48} />
              <p>No entities found in the text</p>
            </div>
          ) : (
            <div className="entity-groups">
              {Object.entries(entityGroups).map(([type, entities]) => {
                const config = getEntityTypeConfig(type as EntityType);
                return (
                  <div key={type} className="entity-group">
                    <div className="entity-group-header">
                      <div className="entity-type-badge" style={{ color: config.color }}>
                        <Icon name={config.icon} size={16} />
                        {config.label}
                      </div>
                      <div className="entity-count">{entities.length}</div>
                    </div>
                    <div className="entity-list">
                      {entities.map((entity, idx) => (
                        <div key={idx} className="entity-item">
                          <Icon name={config.icon} size={14} style={{ color: config.color }} />
                          <span className="entity-text">{entity.text}</span>
                          <span className="entity-confidence">
                            {(entity.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Empty State */}
      {!results && (
        <section className="empty-state-section">
          <Icon name="Sparkles" size={64} className="empty-state-icon" />
          <h2>Extract Named Entities</h2>
          <p>Enter text above to extract and identify entities using NLP</p>
          <div className="entity-types-preview">
            <div className="entity-type-preview">
              <Icon name="User" size={20} style={{ color: '#3b82f6' }} />
              <span>People</span>
            </div>
            <div className="entity-type-preview">
              <Icon name="Building2" size={20} style={{ color: '#8b5cf6' }} />
              <span>Organizations</span>
            </div>
            <div className="entity-type-preview">
              <Icon name="MapPin" size={20} style={{ color: '#10b981' }} />
              <span>Locations</span>
            </div>
            <div className="entity-type-preview">
              <Icon name="Calendar" size={20} style={{ color: '#f59e0b' }} />
              <span>Dates</span>
            </div>
            <div className="entity-type-preview">
              <Icon name="DollarSign" size={20} style={{ color: '#22c55e' }} />
              <span>Money</span>
            </div>
          </div>
        </section>
      )}

      <style>{`
        .parse-page {
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

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 1rem;
          margin-bottom: 2rem;
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

        .stat-value {
          font-size: 1.875rem;
          font-weight: 600;
          color: #f9fafb;
          line-height: 1;
        }

        .stat-label {
          font-size: 0.875rem;
          color: #9ca3af;
          margin-top: 0.25rem;
        }

        .parse-input-section {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1.5rem;
          margin-bottom: 2rem;
        }

        .input-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }

        .input-header h2 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .input-actions {
          display: flex;
          gap: 0.75rem;
        }

        .text-input {
          width: 100%;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          padding: 0.75rem;
          color: #f9fafb;
          font-family: 'Courier New', monospace;
          font-size: 0.875rem;
          line-height: 1.5;
          resize: vertical;
          min-height: 200px;
        }

        .text-input:focus {
          outline: none;
          border-color: #6366f1;
        }

        .text-input::placeholder {
          color: #6b7280;
        }

        .results-section {
          margin-bottom: 2rem;
        }

        .results-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
        }

        .results-header h2 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .results-meta {
          font-size: 0.875rem;
          color: #9ca3af;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .separator {
          color: #4b5563;
        }

        .entity-groups {
          display: grid;
          gap: 1rem;
        }

        .entity-group {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1rem;
        }

        .entity-group-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.75rem;
        }

        .entity-type-badge {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-weight: 600;
          font-size: 0.875rem;
        }

        .entity-count {
          background: #374151;
          color: #9ca3af;
          padding: 0.25rem 0.75rem;
          border-radius: 1rem;
          font-size: 0.75rem;
          font-weight: 500;
        }

        .entity-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .entity-item {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
        }

        .entity-text {
          flex: 1;
          font-size: 0.875rem;
          color: #f9fafb;
        }

        .entity-confidence {
          font-size: 0.75rem;
          color: #9ca3af;
        }

        .empty-state,
        .empty-state-section {
          padding: 3rem;
          text-align: center;
          color: #9ca3af;
        }

        .empty-state {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
        }

        .empty-state p,
        .empty-state-section p {
          margin: 0.5rem 0 0 0;
        }

        .empty-state-section h2 {
          margin: 1rem 0 0.5rem 0;
          color: #f9fafb;
          font-size: 1.5rem;
        }

        .empty-state-icon {
          opacity: 0.5;
        }

        .entity-types-preview {
          display: flex;
          justify-content: center;
          gap: 2rem;
          margin-top: 2rem;
          flex-wrap: wrap;
        }

        .entity-type-preview {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.875rem;
          color: #f9fafb;
        }

        .button-primary,
        .button-secondary {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 1rem;
          border-radius: 0.375rem;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s;
          border: 1px solid transparent;
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

        .button-secondary:hover {
          background: #4b5563;
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
