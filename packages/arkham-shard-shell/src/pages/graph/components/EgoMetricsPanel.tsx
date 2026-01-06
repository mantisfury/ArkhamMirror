/**
 * EgoMetricsPanel - Display ego-centric network metrics
 *
 * Shows structural holes analysis, ego network composition,
 * and broker positioning metrics for a focused entity.
 */

import { useState, useEffect, useCallback } from 'react';
import { Icon } from '../../../components/common/Icon';

export interface EgoMetrics {
  ego_entity_id: string;
  ego_entity_name: string;
  network_size: number;
  effective_size: number;
  efficiency: number;
  constraint: number;
  hierarchy: number;
  broker_score: number;
  density: number;
  avg_tie_strength: number;
  alter_composition: {
    by_type: Record<string, number>;
    by_relationship: Record<string, number>;
  };
  bridging_ties: number;
  redundant_ties: number;
}

export interface EgoNetwork {
  ego: {
    id: string;
    name: string;
    type: string;
  };
  alters: Array<{
    id: string;
    name: string;
    type: string;
    distance: number;
    tie_strength: number;
  }>;
  ties: Array<{
    source: string;
    target: string;
    type: string;
    weight: number;
  }>;
  metrics: EgoMetrics;
}

interface EgoMetricsPanelProps {
  entityId: string | null;
  entityName?: string;
  onClose: () => void;
  onAlterClick?: (alterId: string) => void;
  isLoading?: boolean;
}

const API_BASE = '/api/graph';

export function EgoMetricsPanel({
  entityId,
  entityName,
  onClose,
  onAlterClick,
  isLoading: externalLoading = false,
}: EgoMetricsPanelProps) {
  const [egoNetwork, setEgoNetwork] = useState<EgoNetwork | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'metrics' | 'alters' | 'composition'>('metrics');
  const [depth, setDepth] = useState(2);

  // Fetch ego network data
  const fetchEgoNetwork = useCallback(async () => {
    if (!entityId) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE}/ego/${encodeURIComponent(entityId)}?depth=${depth}&include_alter_alter=true`
      );

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setEgoNetwork(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load ego network';
      console.error('Failed to fetch ego network:', err);
      setError(message);
      setEgoNetwork(null);
    } finally {
      setIsLoading(false);
    }
  }, [entityId, depth]);

  useEffect(() => {
    if (entityId) {
      fetchEgoNetwork();
    } else {
      setEgoNetwork(null);
    }
  }, [entityId, fetchEgoNetwork]);

  // Format percentage
  const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;

  // Format number with 2 decimal places
  const formatNumber = (value: number) => value.toFixed(2);

  // Get constraint interpretation
  const getConstraintLevel = (constraint: number): { label: string; color: string } => {
    if (constraint < 0.3) return { label: 'Low (Broker)', color: 'var(--success)' };
    if (constraint < 0.6) return { label: 'Medium', color: 'var(--warning)' };
    return { label: 'High (Embedded)', color: 'var(--danger)' };
  };

  // Get broker score interpretation
  const getBrokerLevel = (score: number): { label: string; color: string } => {
    if (score >= 0.7) return { label: 'Strong Broker', color: 'var(--success)' };
    if (score >= 0.4) return { label: 'Moderate', color: 'var(--warning)' };
    return { label: 'Limited', color: 'var(--text-muted)' };
  };

  if (!entityId) {
    return (
      <div className="ego-panel">
        <div className="ego-panel-header">
          <h3>
            <Icon name="Target" size={16} />
            Ego Network Analysis
          </h3>
          <button className="ego-panel-close" onClick={onClose}>
            <Icon name="X" size={16} />
          </button>
        </div>
        <div className="ego-panel-empty">
          <Icon name="MousePointer" size={32} />
          <p>Select an entity to analyze its ego network</p>
        </div>
      </div>
    );
  }

  const loading = isLoading || externalLoading;

  return (
    <div className="ego-panel">
      {/* Header */}
      <div className="ego-panel-header">
        <h3>
          <Icon name="Target" size={16} />
          {entityName || egoNetwork?.ego?.name || 'Ego Network'}
        </h3>
        <div className="ego-panel-actions">
          <select
            className="depth-select"
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            title="Network depth"
          >
            <option value={1}>Depth: 1</option>
            <option value={2}>Depth: 2</option>
            <option value={3}>Depth: 3</option>
          </select>
          <button
            className="ego-panel-refresh"
            onClick={fetchEgoNetwork}
            disabled={loading}
            title="Refresh"
          >
            <Icon name="RefreshCw" size={14} className={loading ? 'spin' : ''} />
          </button>
          <button className="ego-panel-close" onClick={onClose}>
            <Icon name="X" size={16} />
          </button>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="ego-panel-loading">
          <Icon name="Loader2" size={24} className="spin" />
          <span>Analyzing network...</span>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="ego-panel-error">
          <Icon name="AlertCircle" size={20} />
          <span>{error}</span>
          <button onClick={fetchEgoNetwork}>Retry</button>
        </div>
      )}

      {/* Content */}
      {egoNetwork && !loading && !error && (
        <>
          {/* Tabs */}
          <div className="ego-panel-tabs">
            <button
              className={`ego-tab ${activeTab === 'metrics' ? 'active' : ''}`}
              onClick={() => setActiveTab('metrics')}
            >
              <Icon name="BarChart2" size={14} />
              Metrics
            </button>
            <button
              className={`ego-tab ${activeTab === 'alters' ? 'active' : ''}`}
              onClick={() => setActiveTab('alters')}
            >
              <Icon name="Users" size={14} />
              Alters ({egoNetwork.alters.length})
            </button>
            <button
              className={`ego-tab ${activeTab === 'composition' ? 'active' : ''}`}
              onClick={() => setActiveTab('composition')}
            >
              <Icon name="PieChart" size={14} />
              Composition
            </button>
          </div>

          {/* Metrics Tab */}
          {activeTab === 'metrics' && (
            <div className="ego-panel-content">
              {/* Summary Cards */}
              <div className="ego-summary-cards">
                <div className="ego-summary-card">
                  <span className="card-label">Network Size</span>
                  <span className="card-value">{egoNetwork.metrics.network_size}</span>
                  <span className="card-sub">alters</span>
                </div>
                <div className="ego-summary-card">
                  <span className="card-label">Effective Size</span>
                  <span className="card-value">{formatNumber(egoNetwork.metrics.effective_size)}</span>
                  <span className="card-sub">non-redundant</span>
                </div>
                <div className="ego-summary-card highlight">
                  <span className="card-label">Broker Score</span>
                  <span
                    className="card-value"
                    style={{ color: getBrokerLevel(egoNetwork.metrics.broker_score).color }}
                  >
                    {formatPercent(egoNetwork.metrics.broker_score)}
                  </span>
                  <span className="card-sub">{getBrokerLevel(egoNetwork.metrics.broker_score).label}</span>
                </div>
              </div>

              {/* Structural Holes Section */}
              <div className="ego-section">
                <h4>
                  <Icon name="GitBranch" size={14} />
                  Structural Holes
                </h4>
                <div className="ego-metrics-grid">
                  <div className="ego-metric">
                    <span className="metric-label">Efficiency</span>
                    <div className="metric-bar">
                      <div
                        className="metric-fill efficiency"
                        style={{ width: formatPercent(egoNetwork.metrics.efficiency) }}
                      />
                    </div>
                    <span className="metric-value">{formatPercent(egoNetwork.metrics.efficiency)}</span>
                  </div>

                  <div className="ego-metric">
                    <span className="metric-label">Constraint</span>
                    <div className="metric-bar">
                      <div
                        className="metric-fill constraint"
                        style={{
                          width: formatPercent(Math.min(1, egoNetwork.metrics.constraint)),
                          backgroundColor: getConstraintLevel(egoNetwork.metrics.constraint).color
                        }}
                      />
                    </div>
                    <span className="metric-value">
                      {formatNumber(egoNetwork.metrics.constraint)}
                      <span className="metric-interpretation">
                        {getConstraintLevel(egoNetwork.metrics.constraint).label}
                      </span>
                    </span>
                  </div>

                  <div className="ego-metric">
                    <span className="metric-label">Hierarchy</span>
                    <div className="metric-bar">
                      <div
                        className="metric-fill hierarchy"
                        style={{ width: formatPercent(Math.min(1, egoNetwork.metrics.hierarchy)) }}
                      />
                    </div>
                    <span className="metric-value">{formatNumber(egoNetwork.metrics.hierarchy)}</span>
                  </div>
                </div>
              </div>

              {/* Network Properties */}
              <div className="ego-section">
                <h4>
                  <Icon name="Network" size={14} />
                  Network Properties
                </h4>
                <div className="ego-properties">
                  <div className="ego-property">
                    <span className="property-label">Density</span>
                    <span className="property-value">{formatPercent(egoNetwork.metrics.density)}</span>
                  </div>
                  <div className="ego-property">
                    <span className="property-label">Avg Tie Strength</span>
                    <span className="property-value">{formatNumber(egoNetwork.metrics.avg_tie_strength)}</span>
                  </div>
                  <div className="ego-property">
                    <span className="property-label">Bridging Ties</span>
                    <span className="property-value success">{egoNetwork.metrics.bridging_ties}</span>
                  </div>
                  <div className="ego-property">
                    <span className="property-label">Redundant Ties</span>
                    <span className="property-value muted">{egoNetwork.metrics.redundant_ties}</span>
                  </div>
                </div>
              </div>

              {/* Interpretation */}
              <div className="ego-interpretation">
                <Icon name="Lightbulb" size={14} />
                <p>
                  {egoNetwork.metrics.constraint < 0.3 ? (
                    <>
                      <strong>Strong broker position:</strong> This entity bridges disconnected groups,
                      providing access to diverse information and control over information flow.
                    </>
                  ) : egoNetwork.metrics.constraint > 0.6 ? (
                    <>
                      <strong>Embedded position:</strong> This entity's contacts are well-connected to each other,
                      limiting access to novel information but providing strong social support.
                    </>
                  ) : (
                    <>
                      <strong>Moderate position:</strong> This entity has a balanced mix of bridging and
                      redundant ties, with some brokerage opportunities.
                    </>
                  )}
                </p>
              </div>
            </div>
          )}

          {/* Alters Tab */}
          {activeTab === 'alters' && (
            <div className="ego-panel-content">
              <div className="ego-alters-list">
                {egoNetwork.alters
                  .sort((a, b) => a.distance - b.distance || b.tie_strength - a.tie_strength)
                  .map((alter) => (
                    <div
                      key={alter.id}
                      className={`ego-alter-item distance-${alter.distance}`}
                      onClick={() => onAlterClick?.(alter.id)}
                    >
                      <div className="alter-info">
                        <span className="alter-name">{alter.name}</span>
                        <span className="alter-type">{alter.type}</span>
                      </div>
                      <div className="alter-metrics">
                        <span className="alter-distance" title="Distance from ego">
                          <Icon name="GitCommit" size={12} />
                          {alter.distance}
                        </span>
                        <span className="alter-strength" title="Tie strength">
                          <Icon name="Link" size={12} />
                          {alter.tie_strength.toFixed(1)}
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Composition Tab */}
          {activeTab === 'composition' && (
            <div className="ego-panel-content">
              {/* By Type */}
              <div className="ego-section">
                <h4>
                  <Icon name="Layers" size={14} />
                  By Entity Type
                </h4>
                <div className="composition-list">
                  {Object.entries(egoNetwork.metrics.alter_composition.by_type)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => (
                      <div key={type} className="composition-item">
                        <span className="composition-label">{type}</span>
                        <div className="composition-bar">
                          <div
                            className="composition-fill"
                            style={{
                              width: `${(count / egoNetwork.alters.length) * 100}%`
                            }}
                          />
                        </div>
                        <span className="composition-count">{count}</span>
                      </div>
                    ))}
                </div>
              </div>

              {/* By Relationship */}
              <div className="ego-section">
                <h4>
                  <Icon name="Link2" size={14} />
                  By Relationship Type
                </h4>
                <div className="composition-list">
                  {Object.entries(egoNetwork.metrics.alter_composition.by_relationship)
                    .sort(([, a], [, b]) => b - a)
                    .map(([rel, count]) => (
                      <div key={rel} className="composition-item">
                        <span className="composition-label">{rel}</span>
                        <div className="composition-bar">
                          <div
                            className="composition-fill relationship"
                            style={{
                              width: `${(count / egoNetwork.ties.length) * 100}%`
                            }}
                          />
                        </div>
                        <span className="composition-count">{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
