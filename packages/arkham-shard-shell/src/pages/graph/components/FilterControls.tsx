/**
 * FilterControls - Filtering options for graph visualization
 */

import { useState } from 'react';
import { Icon } from '../../../components/common/Icon';
import type { FilterSettings } from '../hooks/useGraphSettings';

interface FilterControlsProps {
  settings: FilterSettings;
  onChange: (updates: Partial<FilterSettings>) => void;
  availableEntityTypes: string[];
  availableDocumentSources?: { id: string; name: string }[];
}

export function FilterControls({
  settings,
  onChange,
  availableEntityTypes,
  availableDocumentSources = []
}: FilterControlsProps) {
  const [searchInput, setSearchInput] = useState(settings.searchQuery);

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
