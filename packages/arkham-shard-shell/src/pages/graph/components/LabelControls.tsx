/**
 * LabelControls - Controls for label visibility in the graph
 */

import { Icon } from '../../../components/common/Icon';
import type { LabelSettings } from '../hooks/useGraphSettings';

interface LabelControlsProps {
  settings: LabelSettings;
  onChange: (updates: Partial<LabelSettings>) => void;
}

const LABEL_MODES = [
  { value: 'top', label: 'Top entities only', description: 'Show labels for most connected nodes' },
  { value: 'zoom', label: 'Zoom-based', description: 'Show more labels when zoomed in' },
  { value: 'selected', label: 'Selected + neighbors', description: 'Only selected node and connections' },
  { value: 'all', label: 'All labels', description: 'Show all node labels (slower)' },
] as const;

export function LabelControls({ settings, onChange }: LabelControlsProps) {
  return (
    <div className="control-section">
      <div className="control-header">
        <Icon name="Tag" size={16} />
        <h4>Label Visibility</h4>
      </div>

      <div className="control-group">
        <label>Display Mode</label>
        <select
          value={settings.mode}
          onChange={e => onChange({ mode: e.target.value as LabelSettings['mode'] })}
          className="control-select"
        >
          {LABEL_MODES.map(mode => (
            <option key={mode.value} value={mode.value}>
              {mode.label}
            </option>
          ))}
        </select>
        <span className="control-hint">
          {LABEL_MODES.find(m => m.value === settings.mode)?.description}
        </span>
      </div>

      {settings.mode === 'top' && (
        <div className="control-group">
          <label>
            Top Entities: {settings.topPercent}%
          </label>
          <input
            type="range"
            min="1"
            max="100"
            value={settings.topPercent}
            onChange={e => onChange({ topPercent: Number(e.target.value) })}
            className="control-slider"
          />
          <div className="slider-labels">
            <span>1%</span>
            <span>50%</span>
            <span>100%</span>
          </div>
        </div>
      )}

      {settings.mode === 'zoom' && (
        <div className="control-group">
          <label>
            Zoom Threshold: {settings.zoomThreshold.toFixed(1)}x
          </label>
          <input
            type="range"
            min="0.1"
            max="2"
            step="0.1"
            value={settings.zoomThreshold}
            onChange={e => onChange({ zoomThreshold: Number(e.target.value) })}
            className="control-slider"
          />
          <div className="slider-labels">
            <span>0.1x</span>
            <span>1x</span>
            <span>2x</span>
          </div>
        </div>
      )}

      <div className="control-group">
        <label>
          Font Size: {settings.fontSize}px
        </label>
        <input
          type="range"
          min="8"
          max="20"
          value={settings.fontSize}
          onChange={e => onChange({ fontSize: Number(e.target.value) })}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>8px</span>
          <span>14px</span>
          <span>20px</span>
        </div>
      </div>
    </div>
  );
}
