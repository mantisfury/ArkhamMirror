/**
 * EgoMetricsPanel - Display ego-centric network metrics
 *
 * Shows structural holes analysis, ego network composition,
 * and broker positioning metrics for a focused entity.
 */

import { useState, useEffect, useCallback } from 'react';
import { Icon } from '../../../components/common/Icon';
import { apiGet } from '../../../utils/api';

// API response structure
export interface EgoNetworkResponse {
  project_id: string;
  ego_id: string;
  ego_label: string;
  depth: number;
  graph: {
    nodes: Array<{
      id: string;
      entity_id: string;
      label: string;
      entity_type: string;
      document_count?: number;
      degree?: number;
      properties?: {
        ego_distance?: number;
        is_ego?: boolean;
      };
    }>;
    edges: Array<{
      source: string;
      target: string;
      relationship_type?: string;
      weight?: number;
    }>;
    metadata: {
      ego_id: string;
      ego_label: string;
      depth: number;
      node_count: number;
      edge_count: number;
      nodes_by_depth: Record<string, number>;
    };
  };
  metrics: {
    ego_id: string;
    network_size: number;
    effective_size: number;
    efficiency: number;
    constraint: number;
    hierarchy: number;
    density: number;
    avg_tie_strength: number;
  };
  node_count: number;
  edge_count: number;
  nodes_by_depth: Record<string, number>;
  calculation_time_ms: number;
}

interface EgoMetricsPanelProps {
  entityId: string | null;
  entityName?: string;
  projectId: string;
  onClose: () => void;
  onAlterClick?: (alterId: string) => void;
  isLoading?: boolean;
}

const API_BASE = '/api/graph';

export function EgoMetricsPanel({
  entityId,
  entityName,
  projectId,
  onClose,
  onAlterClick,
  isLoading: externalLoading = false,
}: EgoMetricsPanelProps) {
  const [egoNetwork, setEgoNetwork] = useState<EgoNetworkResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'metrics' | 'alters' | 'composition'>('metrics');
  const [depth, setDepth] = useState(2);

  // Fetch ego network data
  const fetchEgoNetwork = useCallback(async () => {
    if (!entityId || !projectId) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await apiGet<EgoNetworkResponse>(
        `${API_BASE}/ego/${encodeURIComponent(entityId)}?project_id=${encodeURIComponent(projectId)}&depth=${depth}&include_alter_alter=true`
      );
      setEgoNetwork(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load ego network';
      console.error('Failed to fetch ego network:', err);
      setError(message);
      setEgoNetwork(null);
    } finally {
      setIsLoading(false);
    }
  }, [entityId, projectId, depth]);

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

  // Derive alters (non-ego nodes) and ties from the graph data
  const alters = egoNetwork?.graph?.nodes?.filter(n => !n.properties?.is_ego) || [];
  const ties = egoNetwork?.graph?.edges || [];
  const egoNode = egoNetwork?.graph?.nodes?.find(n => n.properties?.is_ego);

  // Safely access metrics with defaults
  const metrics = egoNetwork?.metrics || {
    ego_id: '',
    network_size: 0,
    effective_size: 0,
    efficiency: 0,
    constraint: 1,
    hierarchy: 0,
    density: 0,
    avg_tie_strength: 0,
  };

  return (
    <div className="ego-panel">
      {/* Header */}
      <div className="ego-panel-header">
        <h3>
          <Icon name="Target" size={16} />
          {entityName || egoNetwork?.ego_label || egoNode?.label || 'Ego Network'}
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
              Alters ({alters.length})
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
                  <span className="card-value">{metrics.network_size}</span>
                  <span className="card-sub">alters</span>
                </div>
                <div className="ego-summary-card">
                  <span className="card-label">Effective Size</span>
                  <span className="card-value">{formatNumber(metrics.effective_size)}</span>
                  <span className="card-sub">non-redundant</span>
                </div>
                <div className="ego-summary-card highlight">
                  <span className="card-label">Efficiency</span>
                  <span
                    className="card-value"
                    style={{ color: metrics.efficiency > 0.5 ? '#22c55e' : '#f59e0b' }}
                  >
                    {formatPercent(metrics.efficiency)}
                  </span>
                  <span className="card-sub">{metrics.efficiency > 0.5 ? 'efficient' : 'redundant'}</span>
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
                        style={{ width: formatPercent(metrics.efficiency) }}
                      />
                    </div>
                    <span className="metric-value">{formatPercent(metrics.efficiency)}</span>
                  </div>

                  <div className="ego-metric">
                    <span className="metric-label">Constraint</span>
                    <div className="metric-bar">
                      <div
                        className="metric-fill constraint"
                        style={{
                          width: formatPercent(Math.min(1, metrics.constraint)),
                          backgroundColor: getConstraintLevel(metrics.constraint).color
                        }}
                      />
                    </div>
                    <span className="metric-value">
                      {formatNumber(metrics.constraint)}
                      <span className="metric-interpretation">
                        {getConstraintLevel(metrics.constraint).label}
                      </span>
                    </span>
                  </div>

                  <div className="ego-metric">
                    <span className="metric-label">Hierarchy</span>
                    <div className="metric-bar">
                      <div
                        className="metric-fill hierarchy"
                        style={{ width: formatPercent(Math.min(1, metrics.hierarchy)) }}
                      />
                    </div>
                    <span className="metric-value">{formatNumber(metrics.hierarchy)}</span>
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
                    <span className="property-value">{formatPercent(metrics.density)}</span>
                  </div>
                  <div className="ego-property">
                    <span className="property-label">Avg Tie Strength</span>
                    <span className="property-value">{formatNumber(metrics.avg_tie_strength)}</span>
                  </div>
                  <div className="ego-property">
                    <span className="property-label">Total Alters</span>
                    <span className="property-value">{alters.length}</span>
                  </div>
                  <div className="ego-property">
                    <span className="property-label">Total Ties</span>
                    <span className="property-value">{ties.length}</span>
                  </div>
                </div>
              </div>

              {/* Interpretation */}
              <div className="ego-interpretation">
                <Icon name="Lightbulb" size={14} />
                <p>
                  {metrics.constraint < 0.3 ? (
                    <>
                      <strong>Strong broker position:</strong> This entity bridges disconnected groups,
                      providing access to diverse information and control over information flow.
                    </>
                  ) : metrics.constraint > 0.6 ? (
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
                {alters.length === 0 ? (
                  <div className="ego-panel-empty">
                    <Icon name="Users" size={24} />
                    <p>No connected entities found</p>
                  </div>
                ) : (
                  alters
                    .sort((a, b) => (a.properties?.ego_distance || 0) - (b.properties?.ego_distance || 0))
                    .map((alter) => (
                      <div
                        key={alter.id}
                        className={`ego-alter-item distance-${alter.properties?.ego_distance || 1}`}
                        onClick={() => onAlterClick?.(alter.id)}
                      >
                        <div className="alter-info">
                          <span className="alter-name">{alter.label}</span>
                          <span className="alter-type">{alter.entity_type}</span>
                        </div>
                        <div className="alter-metrics">
                          <span className="alter-distance" title="Distance from ego">
                            <Icon name="GitCommit" size={12} />
                            {alter.properties?.ego_distance || 1}
                          </span>
                          {alter.degree !== undefined && (
                            <span className="alter-strength" title="Connections">
                              <Icon name="Link" size={12} />
                              {alter.degree}
                            </span>
                          )}
                        </div>
                      </div>
                    ))
                )}
              </div>
            </div>
          )}

          {/* Composition Tab */}
          {activeTab === 'composition' && (
            <div className="ego-panel-content">
              {/* By Type - computed from alters */}
              <div className="ego-section">
                <h4>
                  <Icon name="Layers" size={14} />
                  By Entity Type
                </h4>
                <div className="composition-list">
                  {alters.length === 0 ? (
                    <div className="ego-panel-empty">
                      <p>No alters to analyze</p>
                    </div>
                  ) : (
                    Object.entries(
                      alters.reduce((acc, alter) => {
                        const type = alter.entity_type || 'Unknown';
                        acc[type] = (acc[type] || 0) + 1;
                        return acc;
                      }, {} as Record<string, number>)
                    )
                      .sort(([, a], [, b]) => b - a)
                      .map(([type, count]) => (
                        <div key={type} className="composition-item">
                          <span className="composition-label">{type}</span>
                          <div className="composition-bar">
                            <div
                              className="composition-fill"
                              style={{
                                width: `${(count / alters.length) * 100}%`
                              }}
                            />
                          </div>
                          <span className="composition-count">{count}</span>
                        </div>
                      ))
                  )}
                </div>
              </div>

              {/* By Relationship - computed from ties */}
              <div className="ego-section">
                <h4>
                  <Icon name="Link2" size={14} />
                  By Relationship Type
                </h4>
                <div className="composition-list">
                  {ties.length === 0 ? (
                    <div className="ego-panel-empty">
                      <p>No relationships found</p>
                    </div>
                  ) : (
                    Object.entries(
                      ties.reduce((acc, tie) => {
                        const rel = tie.relationship_type || 'co_occurrence';
                        acc[rel] = (acc[rel] || 0) + 1;
                        return acc;
                      }, {} as Record<string, number>)
                    )
                      .sort(([, a], [, b]) => b - a)
                      .map(([rel, count]) => (
                        <div key={rel} className="composition-item">
                          <span className="composition-label">{rel}</span>
                          <div className="composition-bar">
                            <div
                              className="composition-fill relationship"
                              style={{
                                width: `${(count / ties.length) * 100}%`
                              }}
                            />
                          </div>
                          <span className="composition-count">{count}</span>
                        </div>
                      ))
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
