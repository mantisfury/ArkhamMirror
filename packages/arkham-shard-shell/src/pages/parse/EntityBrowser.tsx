/**
 * EntityBrowser - Entity browser component
 *
 * Features:
 * - Entity type filter tabs
 * - Entity list with type badges and icons
 * - Source document links
 * - Occurrence counts
 * - Click to expand showing all occurrences
 */

import { useState, useMemo } from 'react';
import { Icon } from '../../components/common/Icon';
import type { EntityMention, DateMention, EntityType } from './types';

interface EntityBrowserProps {
  entities: EntityMention[];
  dates?: DateMention[];
  onEntityClick?: (entity: EntityMention | DateMention) => void;
}

export function EntityBrowser({ entities, dates = [], onEntityClick }: EntityBrowserProps) {
  const [selectedType, setSelectedType] = useState<EntityType | 'ALL' | 'DATE'>('ALL');
  const [expandedEntity, setExpandedEntity] = useState<string | null>(null);

  // Combine entities and dates
  const allEntities = useMemo(() => {
    const combined: Array<EntityMention | DateMention> = [...entities];
    if (dates.length > 0) {
      combined.push(...dates);
    }
    return combined;
  }, [entities, dates]);

  // Group entities by type
  const entityCounts = useMemo(() => {
    const counts: Record<string, number> = {
      ALL: allEntities.length,
    };

    entities.forEach(entity => {
      const type = entity.entity_type;
      counts[type] = (counts[type] || 0) + 1;
    });

    if (dates.length > 0) {
      counts['DATE'] = dates.length;
    }

    return counts;
  }, [entities, dates, allEntities.length]);

  // Get entity type configuration
  const getEntityTypeConfig = (type: EntityType | 'DATE') => {
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

  // Filter entities by selected type
  const filteredEntities = useMemo(() => {
    if (selectedType === 'ALL') {
      return allEntities;
    }
    if (selectedType === 'DATE') {
      return dates;
    }
    return entities.filter(e => e.entity_type === selectedType);
  }, [selectedType, entities, dates, allEntities]);

  // Group entities by text for occurrence counting
  const entityOccurrences = useMemo(() => {
    const occurrences = new Map<string, Array<EntityMention | DateMention>>();

    filteredEntities.forEach(entity => {
      const key = entity.text.toLowerCase();
      if (!occurrences.has(key)) {
        occurrences.set(key, []);
      }
      occurrences.get(key)!.push(entity);
    });

    return Array.from(occurrences.entries()).map(([, entities]) => ({
      text: entities[0].text, // Use original casing from first occurrence
      entities,
      count: entities.length,
      type: 'entity_type' in entities[0] ? entities[0].entity_type : 'DATE',
    }));
  }, [filteredEntities]);

  // Available entity types
  const entityTypes: Array<EntityType | 'ALL' | 'DATE'> = [
    'ALL',
    'PERSON',
    'ORG',
    'LOCATION',
    'DATE',
    'MONEY',
  ];

  const handleEntityClick = (occurrence: typeof entityOccurrences[0]) => {
    const key = occurrence.text.toLowerCase();
    if (expandedEntity === key) {
      setExpandedEntity(null);
    } else {
      setExpandedEntity(key);
    }
  };

  return (
    <div className="entity-browser">
      {/* Type Filter Tabs */}
      <div className="filter-tabs">
        {entityTypes.map(type => {
          const count = entityCounts[type] || 0;
          if (count === 0 && type !== 'ALL') return null;

          const config = type === 'ALL'
            ? { icon: 'List' as const, color: '#6b7280', label: 'All' }
            : getEntityTypeConfig(type as EntityType | 'DATE');

          return (
            <button
              key={type}
              className={`filter-tab ${selectedType === type ? 'active' : ''}`}
              onClick={() => setSelectedType(type)}
              style={{
                borderColor: selectedType === type ? config.color : 'transparent',
              }}
            >
              <Icon name={config.icon} size={16} style={{ color: config.color }} />
              <span>{config.label}</span>
              <span className="tab-count">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Entity List */}
      <div className="entity-browser-list">
        {entityOccurrences.length === 0 ? (
          <div className="empty-state">
            <Icon name="SearchX" size={48} />
            <p>No entities of this type</p>
          </div>
        ) : (
          entityOccurrences.map((occurrence, idx) => {
            const config = getEntityTypeConfig(occurrence.type as EntityType | 'DATE');
            const isExpanded = expandedEntity === occurrence.text.toLowerCase();

            return (
              <div key={idx} className="entity-occurrence">
                <button
                  className="entity-occurrence-header"
                  onClick={() => handleEntityClick(occurrence)}
                >
                  <Icon name={config.icon} size={18} style={{ color: config.color }} />
                  <div className="entity-occurrence-info">
                    <div className="entity-occurrence-text">{occurrence.text}</div>
                    <div className="entity-occurrence-meta">
                      <span className="entity-type-label" style={{ color: config.color }}>
                        {config.label}
                      </span>
                      {occurrence.count > 1 && (
                        <>
                          <span className="separator">•</span>
                          <span>{occurrence.count} occurrences</span>
                        </>
                      )}
                    </div>
                  </div>
                  <Icon
                    name={isExpanded ? 'ChevronUp' : 'ChevronDown'}
                    size={20}
                    className="expand-icon"
                  />
                </button>

                {isExpanded && (
                  <div className="entity-occurrences-list">
                    {occurrence.entities.map((entity, entityIdx) => (
                      <div
                        key={entityIdx}
                        className="entity-occurrence-item"
                        onClick={() => onEntityClick?.(entity)}
                      >
                        <div className="occurrence-details">
                          <div className="occurrence-position">
                            Position: {entity.start_char} - {entity.end_char}
                          </div>
                          <div className="occurrence-confidence">
                            Confidence: {(entity.confidence * 100).toFixed(0)}%
                          </div>
                          {entity.doc_id && (
                            <div className="occurrence-doc">
                              <Icon name="FileText" size={12} />
                              Doc: {entity.doc_id.substring(0, 8)}...
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <style>{`
        .entity-browser {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          overflow: hidden;
        }

        .filter-tabs {
          display: flex;
          gap: 0.5rem;
          padding: 1rem;
          border-bottom: 1px solid #374151;
          overflow-x: auto;
        }

        .filter-tab {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 1rem;
          background: #111827;
          border: 2px solid transparent;
          border-radius: 0.375rem;
          color: #f9fafb;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s;
          white-space: nowrap;
        }

        .filter-tab:hover {
          background: #1f2937;
        }

        .filter-tab.active {
          background: #1f2937;
        }

        .tab-count {
          background: #374151;
          color: #9ca3af;
          padding: 0.125rem 0.5rem;
          border-radius: 1rem;
          font-size: 0.75rem;
          margin-left: 0.25rem;
        }

        .entity-browser-list {
          padding: 1rem;
          max-height: 600px;
          overflow-y: auto;
        }

        .entity-occurrence {
          margin-bottom: 0.75rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          overflow: hidden;
        }

        .entity-occurrence-header {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem;
          width: 100%;
          background: transparent;
          border: none;
          cursor: pointer;
          color: #f9fafb;
          transition: background 0.15s;
        }

        .entity-occurrence-header:hover {
          background: #1f2937;
        }

        .entity-occurrence-info {
          flex: 1;
          text-align: left;
        }

        .entity-occurrence-text {
          font-size: 0.875rem;
          font-weight: 500;
          color: #f9fafb;
        }

        .entity-occurrence-meta {
          font-size: 0.75rem;
          color: #9ca3af;
          margin-top: 0.25rem;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .entity-type-label {
          font-weight: 500;
        }

        .separator {
          color: #4b5563;
        }

        .expand-icon {
          color: #9ca3af;
          transition: transform 0.15s;
        }

        .entity-occurrences-list {
          border-top: 1px solid #374151;
          padding: 0.5rem;
        }

        .entity-occurrence-item {
          padding: 0.5rem;
          margin: 0.25rem 0;
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.25rem;
          cursor: pointer;
          transition: all 0.15s;
        }

        .entity-occurrence-item:hover {
          background: #374151;
          border-color: #4b5563;
        }

        .occurrence-details {
          display: flex;
          gap: 1rem;
          flex-wrap: wrap;
          font-size: 0.75rem;
          color: #9ca3af;
        }

        .occurrence-doc {
          display: flex;
          align-items: center;
          gap: 0.25rem;
        }

        .empty-state {
          padding: 3rem;
          text-align: center;
          color: #9ca3af;
        }

        .empty-state p {
          margin: 0.5rem 0 0 0;
        }
      `}</style>
    </div>
  );
}
