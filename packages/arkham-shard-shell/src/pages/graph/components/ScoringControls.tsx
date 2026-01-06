/**
 * ScoringControls - Composite scoring weight controls
 */

import { Icon } from '../../../components/common/Icon';
import type { ScoringSettings, ScoringWeights } from '../hooks/useGraphSettings';

interface ScoringControlsProps {
  settings: ScoringSettings;
  normalizedWeights: ScoringWeights;
  onChange: (updates: Partial<ScoringSettings>) => void;
  onWeightChange: (updates: Partial<ScoringWeights>) => void;
  onRecalculate?: () => void;
  isLoading?: boolean;
  error?: string | null;
}

const CENTRALITY_OPTIONS = [
  { value: 'pagerank', label: 'PageRank', description: 'Influence propagation' },
  { value: 'betweenness', label: 'Betweenness', description: 'Bridge nodes' },
  { value: 'eigenvector', label: 'Eigenvector', description: 'Quality of connections' },
  { value: 'hits', label: 'HITS', description: 'Hubs and authorities' },
  { value: 'closeness', label: 'Closeness', description: 'Information spread' },
] as const;

const RECENCY_OPTIONS = [
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
  { value: 365, label: '1 year' },
  { value: null, label: 'Disabled' },
] as const;

const WEIGHT_LABELS: Record<keyof ScoringWeights, { label: string; icon: string; hint: string }> = {
  centrality: { label: 'Centrality', icon: 'Network', hint: 'Graph position importance' },
  frequency: { label: 'Frequency (TF-IDF)', icon: 'Hash', hint: 'Rare entities weighted higher' },
  recency: { label: 'Recency', icon: 'Clock', hint: 'Recent mentions weighted higher' },
  credibility: { label: 'Source Credibility', icon: 'Shield', hint: 'From credibility ratings' },
  corroboration: { label: 'Corroboration', icon: 'Users', hint: 'Multiple independent sources' },
};

export function ScoringControls({
  settings,
  normalizedWeights,
  onChange,
  onWeightChange,
  onRecalculate,
  isLoading = false,
  error = null,
}: ScoringControlsProps) {
  const weightKeys = Object.keys(WEIGHT_LABELS) as (keyof ScoringWeights)[];

  return (
    <div className="control-section">
      <div className="control-header">
        <Icon name="BarChart2" size={16} />
        <h4>Smart Weighting</h4>
      </div>

      {/* Enable Toggle */}
      <div className="control-group">
        <label className="toggle-label featured">
          <input
            type="checkbox"
            checked={settings.enabled}
            onChange={e => onChange({ enabled: e.target.checked })}
          />
          <span>Enable Composite Scoring</span>
        </label>
        <span className="control-hint">
          Combine multiple signals for node importance
        </span>
      </div>

      {settings.enabled && (
        <>
          {/* Recalculate Button */}
          <div className="control-group">
            <button
              className="recalculate-btn"
              onClick={onRecalculate}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Icon name="Loader2" size={14} className="spin" />
                  Calculating...
                </>
              ) : (
                <>
                  <Icon name="RefreshCw" size={14} />
                  Recalculate Scores
                </>
              )}
            </button>
            {error && (
              <span className="control-error">{error}</span>
            )}
          </div>
        </>
      )}

      {settings.enabled && (
        <>
          {/* Centrality Type */}
          <div className="control-group">
            <label>Centrality Algorithm</label>
            <select
              value={settings.centralityType}
              onChange={e => onChange({ centralityType: e.target.value as ScoringSettings['centralityType'] })}
              className="control-select"
            >
              {CENTRALITY_OPTIONS.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="control-hint">
              {CENTRALITY_OPTIONS.find(o => o.value === settings.centralityType)?.description}
            </span>
          </div>

          {/* Weight Sliders */}
          <div className="control-group">
            <label>Signal Weights</label>
            <div className="weights-container">
              {weightKeys.map(key => {
                const { label, icon, hint } = WEIGHT_LABELS[key];
                const rawValue = settings.weights[key];
                const normalizedValue = normalizedWeights[key];

                return (
                  <div key={key} className="weight-row">
                    <div className="weight-header">
                      <Icon name={icon as any} size={14} />
                      <span className="weight-label">{label}</span>
                      <span className="weight-value">
                        {(normalizedValue * 100).toFixed(0)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={rawValue}
                      onChange={e => onWeightChange({ [key]: Number(e.target.value) })}
                      className="control-slider weight-slider"
                    />
                    <span className="weight-hint">{hint}</span>
                  </div>
                );
              })}
            </div>

            {/* Weight summary bar */}
            <div className="weight-summary">
              <div className="weight-bar">
                {weightKeys.map(key => (
                  <div
                    key={key}
                    className={`weight-segment weight-${key}`}
                    style={{ flex: normalizedWeights[key] }}
                    title={`${WEIGHT_LABELS[key].label}: ${(normalizedWeights[key] * 100).toFixed(0)}%`}
                  />
                ))}
              </div>
              <div className="weight-legend">
                {weightKeys.map(key => (
                  <span key={key} className={`legend-item weight-${key}`}>
                    {WEIGHT_LABELS[key].label.split(' ')[0]}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Recency Half-Life */}
          <div className="control-group">
            <label>Recency Half-Life</label>
            <select
              value={settings.recencyHalfLifeDays ?? 'null'}
              onChange={e => {
                const val = e.target.value;
                onChange({ recencyHalfLifeDays: val === 'null' ? null : Number(val) });
              }}
              className="control-select"
            >
              {RECENCY_OPTIONS.map(option => (
                <option key={String(option.value)} value={String(option.value)}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="control-hint">
              How quickly old mentions lose weight
            </span>
          </div>
        </>
      )}
    </div>
  );
}
