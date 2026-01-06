/**
 * FilterControls - Filtering options for graph visualization
 */

import { useState, useMemo } from 'react';
import { Icon } from '../../../components/common/Icon';
import type { FilterSettings } from '../hooks/useGraphSettings';
import {
  getRelationshipStyle,
  RELATIONSHIP_CATEGORIES,
  CATEGORY_ORDER,
  type RelationshipCategory
} from '../constants/relationshipStyles';

interface FilterControlsProps {
  settings: FilterSettings;
  onChange: (updates: Partial<FilterSettings>) => void;
  availableEntityTypes: string[];
  availableRelationshipTypes?: string[];
  availableDocumentSources?: { id: string; name: string }[];
}

export function FilterControls({
  settings,
  onChange,
  availableEntityTypes,
  availableRelationshipTypes = [],
  availableDocumentSources = []
}: FilterControlsProps) {
  const [searchInput, setSearchInput] = useState(settings.searchQuery);
  const [showRelTypes, setShowRelTypes] = useState(false);

  // Debounced search update
  const handleSearchChange = (value: string) => {
    setSearchInput(value);
    // Simple debounce
    const timeoutId = setTimeout(() => {
      onChange({ searchQuery: value });
    }, 300);
    return () => clearTimeout(timeoutId);
  };

  const toggleEntityType = (type: string) => {
    const current = new Set(settings.entityTypes);
    if (current.has(type)) {
      current.delete(type);
    } else {
      current.add(type);
    }
    onChange({ entityTypes: Array.from(current) });
  };

  const selectAllTypes = () => {
    onChange({ entityTypes: [] }); // Empty means all
  };

  const clearAllTypes = () => {
    onChange({ entityTypes: ['__none__'] }); // Special value to show none
  };

  // Group available relationship types by category
  const relationshipTypesByCategory = useMemo(() => {
    const grouped = new Map<RelationshipCategory, string[]>();

    for (const type of availableRelationshipTypes) {
      const style = getRelationshipStyle(type);
      const category = style.category as RelationshipCategory;
      if (!grouped.has(category)) {
        grouped.set(category, []);
      }
      grouped.get(category)!.push(type);
    }

    // Sort by category order
    return CATEGORY_ORDER
      .filter(cat => grouped.has(cat))
      .map(cat => ({
        category: cat,
        types: grouped.get(cat)!
      }));
  }, [availableRelationshipTypes]);

  const toggleRelationshipType = (type: string) => {
    const current = new Set(settings.relationshipTypes);
    if (current.has(type)) {
      current.delete(type);
    } else {
      current.add(type);
    }
    onChange({ relationshipTypes: Array.from(current) });
  };

  const selectAllRelTypes = () => {
    onChange({ relationshipTypes: [] }); // Empty means all
  };

  const clearAllRelTypes = () => {
    onChange({ relationshipTypes: ['__none__'] }); // Special value to show none
  };

  const toggleRelCategory = (category: RelationshipCategory) => {
    const categoryTypes = relationshipTypesByCategory.find(g => g.category === category)?.types || [];
    const current = new Set(settings.relationshipTypes);

    // Check if all types in this category are currently selected
    const allSelected = settings.relationshipTypes.length === 0 ||
      categoryTypes.every(t => current.has(t));

    if (allSelected && settings.relationshipTypes.length > 0) {
      // Deselect all in category
      categoryTypes.forEach(t => current.delete(t));
    } else {
      // Select all in category
      categoryTypes.forEach(t => current.add(t));
    }

    onChange({ relationshipTypes: Array.from(current) });
  };

  return (
    <div className="control-section">
      <div className="control-header">
        <Icon name="Filter" size={16} />
        <h4>Filters</h4>
      </div>

      {/* Search */}
      <div className="control-group">
        <label>Search Entities</label>
        <div className="search-input-wrapper">
          <Icon name="Search" size={14} />
          <input
            type="text"
            value={searchInput}
            onChange={e => handleSearchChange(e.target.value)}
            placeholder="Filter by name..."
            className="control-input"
          />
          {searchInput && (
            <button
              className="search-clear"
              onClick={() => handleSearchChange('')}
            >
              <Icon name="X" size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Entity Types */}
      <div className="control-group">
        <div className="control-group-header">
          <label>Entity Types</label>
          <div className="control-group-actions">
            <button className="mini-btn" onClick={selectAllTypes}>All</button>
            <button className="mini-btn" onClick={clearAllTypes}>None</button>
          </div>
        </div>
        <div className="checkbox-grid">
          {availableEntityTypes.map(type => (
            <label key={type} className="checkbox-item">
              <input
                type="checkbox"
                checked={settings.entityTypes.length === 0 || settings.entityTypes.includes(type)}
                onChange={() => toggleEntityType(type)}
              />
              <span className="checkbox-label">{type}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Relationship Types */}
      {availableRelationshipTypes.length > 0 && (
        <div className="control-group">
          <div className="control-group-header">
            <label>
              Relationship Types
              {settings.relationshipTypes.length > 0 && settings.relationshipTypes[0] !== '__none__' && (
                <span className="filter-count">({settings.relationshipTypes.length})</span>
              )}
            </label>
            <div className="control-group-actions">
              <button className="mini-btn" onClick={selectAllRelTypes}>All</button>
              <button className="mini-btn" onClick={clearAllRelTypes}>None</button>
              <button
                className="mini-btn"
                onClick={() => setShowRelTypes(!showRelTypes)}
                title={showRelTypes ? 'Collapse' : 'Expand'}
              >
                <Icon name={showRelTypes ? 'ChevronUp' : 'ChevronDown'} size={12} />
              </button>
            </div>
          </div>

          {/* Compact category chips */}
          {!showRelTypes && (
            <div className="rel-type-chips">
              {relationshipTypesByCategory.map(({ category, types }) => {
                const catMeta = RELATIONSHIP_CATEGORIES[category];
                const activeCount = settings.relationshipTypes.length === 0
                  ? types.length
                  : types.filter(t => settings.relationshipTypes.includes(t)).length;
                const isActive = activeCount > 0;

                return (
                  <button
                    key={category}
                    className={`rel-category-chip ${isActive ? 'active' : ''}`}
                    onClick={() => toggleRelCategory(category)}
                    style={{
                      '--cat-color': catMeta.color,
                      borderColor: isActive ? catMeta.color : undefined,
                      backgroundColor: isActive ? `${catMeta.color}20` : undefined
                    } as React.CSSProperties}
                    title={`${catMeta.label}: ${activeCount}/${types.length} types`}
                  >
                    <span
                      className="chip-dot"
                      style={{ backgroundColor: catMeta.color }}
                    />
                    {catMeta.label}
                    <span className="chip-count">{activeCount}/{types.length}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Expanded view with all types */}
          {showRelTypes && (
            <div className="rel-type-categories">
              {relationshipTypesByCategory.map(({ category, types }) => {
                const catMeta = RELATIONSHIP_CATEGORIES[category];
                return (
                  <div key={category} className="rel-type-category">
                    <button
                      className="rel-category-header"
                      onClick={() => toggleRelCategory(category)}
                    >
                      <span
                        className="category-indicator"
                        style={{ backgroundColor: catMeta.color }}
                      />
                      <span className="category-label">{catMeta.label}</span>
                    </button>
                    <div className="rel-type-list">
                      {types.map(type => {
                        const style = getRelationshipStyle(type);
                        const isChecked = settings.relationshipTypes.length === 0 ||
                          settings.relationshipTypes.includes(type);
                        return (
                          <label key={type} className="rel-type-item">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => toggleRelationshipType(type)}
                            />
                            <span
                              className="rel-type-color"
                              style={{ backgroundColor: style.color }}
                            />
                            <span className="rel-type-label">{style.label}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <span className="control-hint">Filter edges by relationship type</span>
        </div>
      )}

      {/* Degree Range */}
      <div className="control-group">
        <label>
          Degree Range: {settings.minDegree} - {settings.maxDegree === 1000 ? '∞' : settings.maxDegree}
        </label>
        <div className="dual-slider-row">
          <span className="slider-label-inline">Min:</span>
          <input
            type="range"
            min="0"
            max="50"
            value={settings.minDegree}
            onChange={e => onChange({ minDegree: Number(e.target.value) })}
            className="control-slider"
          />
          <span className="slider-value">{settings.minDegree}</span>
        </div>
        <div className="dual-slider-row">
          <span className="slider-label-inline">Max:</span>
          <input
            type="range"
            min="1"
            max="1000"
            value={settings.maxDegree}
            onChange={e => onChange({ maxDegree: Number(e.target.value) })}
            className="control-slider"
          />
          <span className="slider-value">{settings.maxDegree === 1000 ? '∞' : settings.maxDegree}</span>
        </div>
        <span className="control-hint">Filter nodes by connection count</span>
      </div>

      {/* Edge Weight Threshold */}
      <div className="control-group">
        <label>
          Min Edge Weight: {settings.minEdgeWeight.toFixed(2)}
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={settings.minEdgeWeight}
          onChange={e => onChange({ minEdgeWeight: Number(e.target.value) })}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>0</span>
          <span>0.5</span>
          <span>1</span>
        </div>
        <span className="control-hint">Hide weak connections</span>
      </div>

      {/* Document Sources */}
      {availableDocumentSources.length > 0 && (
        <div className="control-group">
          <label>Document Sources</label>
          <select
            multiple
            value={settings.documentSources}
            onChange={e => {
              const selected = Array.from(e.target.selectedOptions, option => option.value);
              onChange({ documentSources: selected });
            }}
            className="control-select multi-select"
          >
            {availableDocumentSources.map(doc => (
              <option key={doc.id} value={doc.id}>
                {doc.name}
              </option>
            ))}
          </select>
          <span className="control-hint">Hold Ctrl/Cmd to select multiple</span>
        </div>
      )}

      {/* Max Nodes Limit */}
      <div className="control-group">
        <label>
          Max Nodes: {settings.maxNodes === 0 ? 'Unlimited' : settings.maxNodes}
        </label>
        <input
          type="range"
          min="0"
          max="500"
          step="10"
          value={settings.maxNodes}
          onChange={e => onChange({ maxNodes: Number(e.target.value) })}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>Unlimited</span>
          <span>250</span>
          <span>500</span>
        </div>
        <span className="control-hint">Limit to top N nodes by importance (0 = show all)</span>
      </div>

      {/* Giant Component Toggle */}
      <div className="control-group">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={settings.showGiantComponentOnly}
            onChange={e => onChange({ showGiantComponentOnly: e.target.checked })}
          />
          <span>Show Giant Component Only</span>
        </label>
        <span className="control-hint">Hide disconnected clusters</span>
      </div>
    </div>
  );
}
