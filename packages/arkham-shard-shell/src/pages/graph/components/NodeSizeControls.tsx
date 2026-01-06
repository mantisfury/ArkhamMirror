/**
 * NodeSizeControls - Controls for node sizing in the graph
 */

import { Icon } from '../../../components/common/Icon';
import type { NodeSizeSettings } from '../hooks/useGraphSettings';

interface NodeSizeControlsProps {
  settings: NodeSizeSettings;
  onChange: (updates: Partial<NodeSizeSettings>) => void;
}

const SIZE_BY_OPTIONS = [
  { value: 'uniform', label: 'Uniform', description: 'All nodes same size' },
  { value: 'degree', label: 'Degree', description: 'By number of connections' },
  { value: 'document_count', label: 'Document Count', description: 'By mentions across documents' },
  { value: 'composite', label: 'Composite Score', description: 'Smart weighted score' },
  { value: 'betweenness', label: 'Betweenness', description: 'Bridge node importance' },
  { value: 'pagerank', label: 'PageRank', description: 'Influence propagation' },
] as const;

export function NodeSizeControls({ settings, onChange }: NodeSizeControlsProps) {
  return (
    <div className="control-section">
      <div className="control-header">
        <Icon name="Circle" size={16} />
        <h4>Node Sizing</h4>
      </div>

      <div className="control-group">
        <label>Size By</label>
        <select
          value={settings.sizeBy}
          onChange={e => onChange({ sizeBy: e.target.value as NodeSizeSettings['sizeBy'] })}
          className="control-select"
        >
          {SIZE_BY_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <span className="control-hint">
          {SIZE_BY_OPTIONS.find(o => o.value === settings.sizeBy)?.description}
        </span>
      </div>

      <div className="control-group">
        <label>Size Range</label>
        <div className="dual-slider-container">
          <div className="dual-slider-row">
            <span className="slider-label">Min: {settings.minRadius}px</span>
            <input
              type="range"
              min="2"
              max="12"
              value={settings.minRadius}
              onChange={e => {
                const newMin = Number(e.target.value);
                onChange({
                  minRadius: newMin,
                  maxRadius: Math.max(newMin + 2, settings.maxRadius)
                });
              }}
              className="control-slider"
            />
          </div>
          <div className="dual-slider-row">
            <span className="slider-label">Max: {settings.maxRadius}px</span>
            <input
              type="range"
              min="8"
              max="24"
              value={settings.maxRadius}
              onChange={e => {
                const newMax = Number(e.target.value);
                onChange({
                  maxRadius: newMax,
                  minRadius: Math.min(newMax - 2, settings.minRadius)
                });
              }}
              className="control-slider"
            />
          </div>
        </div>
        <div className="size-preview">
          <div
            className="size-dot size-min"
            style={{ width: settings.minRadius * 2, height: settings.minRadius * 2 }}
          />
          <span className="size-arrow">→</span>
          <div
            className="size-dot size-max"
            style={{ width: settings.maxRadius * 2, height: settings.maxRadius * 2 }}
          />
        </div>
      </div>
    </div>
  );
}
