/**
 * GraphPage - Entity relationship graph visualization
 *
 * Provides interactive visualization of entity relationships and connections.
 * Features graph exploration, filtering, and analysis capabilities.
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './GraphPage.css';

// Types
interface GraphNode {
  id: string;
  label: string;
  type: string;
  degree: number;
  metadata?: Record<string, unknown>;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
  type?: string;
  metadata?: Record<string, unknown>;
}

interface GraphData {
  project_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: Record<string, unknown>;
}

interface GraphStats {
  node_count: number;
  edge_count: number;
  avg_degree: number;
  density: number;
  diameter?: number;
  avg_clustering?: number;
}

export function GraphPage() {
  const { toast } = useToast();
  const [projectId, _setProjectId] = useState<string>('default');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [filterEntityType, setFilterEntityType] = useState<string>('');
  const [minWeight, setMinWeight] = useState<number>(0);
  const [building, setBuilding] = useState(false);

  // Fetch graph data
  const { data: graphData, loading, error, refetch } = useFetch<GraphData>(
    `/api/graph/${projectId}`
  );

  // Fetch statistics
  const { data: stats, loading: _statsLoading, refetch: refetchStats } = useFetch<GraphStats>(
    `/api/graph/stats?project_id=${projectId}`
  );

  const buildGraph = async () => {
    setBuilding(true);
    try {
      const response = await fetch('/api/graph/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          min_co_occurrence: 1,
          include_temporal: false,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to build graph');
      }

      const result = await response.json();
      toast.success(`Graph built: ${result.node_count} nodes, ${result.edge_count} edges`);
      refetch();
      refetchStats();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to build graph');
    } finally {
      setBuilding(false);
    }
  };

  const _findPath = async (sourceId: string, targetId: string) => {
    try {
      const response = await fetch('/api/graph/path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          source_entity_id: sourceId,
          target_entity_id: targetId,
          max_depth: 6,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to find path');
      }

      const result = await response.json();
      if (result.path_found) {
        toast.success(`Path found: ${result.path_length} hops`);
      } else {
        toast.info('No path found between entities');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to find path');
    }
  };
  void _findPath;

  const exportGraph = async (format: string) => {
    try {
      const response = await fetch('/api/graph/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          format: format,
          include_metadata: true,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to export graph');
      }

      const result = await response.json();

      // Create download
      const blob = new Blob([result.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `graph_${projectId}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      toast.success(`Graph exported as ${format.toUpperCase()}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export graph');
    }
  };

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
  };

  const getConnectedNodes = useCallback((nodeId: string): GraphNode[] => {
    if (!graphData) return [];

    const connectedIds = new Set<string>();
    graphData.edges.forEach(edge => {
      if (edge.source === nodeId) connectedIds.add(edge.target);
      if (edge.target === nodeId) connectedIds.add(edge.source);
    });

    return graphData.nodes.filter(node => connectedIds.has(node.id));
  }, [graphData]);

  // Get unique entity types for filter
  const entityTypes = graphData
    ? Array.from(new Set(graphData.nodes.map(n => n.type)))
    : [];

  // Filter nodes and edges
  const filteredData = graphData
    ? {
        nodes: graphData.nodes.filter(
          node => !filterEntityType || node.type === filterEntityType
        ),
        edges: graphData.edges.filter(
          edge => edge.weight >= minWeight
        ),
      }
    : null;

  return (
    <div className="graph-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Network" size={28} />
          <div>
            <h1>Graph</h1>
            <p className="page-description">Visualize entity relationships and connections</p>
          </div>
        </div>

        <div className="graph-actions">
          <button
            className="btn btn-secondary"
            onClick={buildGraph}
            disabled={building}
          >
            {building ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Building...
              </>
            ) : (
              <>
                <Icon name="GitBranch" size={16} />
                Build Graph
              </>
            )}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => exportGraph('json')}
            disabled={!graphData}
          >
            <Icon name="Download" size={16} />
            Export
          </button>
        </div>
      </header>

      {/* Statistics Bar */}
      {stats && (
        <div className="graph-stats">
          <div className="stat-item">
            <Icon name="Circle" size={16} />
            <span className="stat-label">Nodes:</span>
            <span className="stat-value">{stats.node_count}</span>
          </div>
          <div className="stat-item">
            <Icon name="Minus" size={16} />
            <span className="stat-label">Edges:</span>
            <span className="stat-value">{stats.edge_count}</span>
          </div>
          <div className="stat-item">
            <Icon name="GitBranch" size={16} />
            <span className="stat-label">Avg Degree:</span>
            <span className="stat-value">{stats.avg_degree.toFixed(2)}</span>
          </div>
          <div className="stat-item">
            <Icon name="Percent" size={16} />
            <span className="stat-label">Density:</span>
            <span className="stat-value">{(stats.density * 100).toFixed(2)}%</span>
          </div>
        </div>
      )}

      <div className="graph-layout">
        {/* Filters Sidebar */}
        <aside className="graph-sidebar">
          <div className="sidebar-section">
            <h3>Filters</h3>

            <div className="filter-group">
              <label>Entity Type</label>
              <select
                value={filterEntityType}
                onChange={e => setFilterEntityType(e.target.value)}
                className="filter-select"
              >
                <option value="">All Types</option>
                {entityTypes.map(type => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label>Min Edge Weight</label>
              <input
                type="range"
                min="0"
                max="10"
                value={minWeight}
                onChange={e => setMinWeight(Number(e.target.value))}
                className="filter-slider"
              />
              <span className="filter-value">{minWeight}</span>
            </div>
          </div>

          {selectedNode && (
            <div className="sidebar-section">
              <h3>Node Details</h3>
              <div className="node-details">
                <div className="detail-item">
                  <span className="detail-label">ID:</span>
                  <span className="detail-value">{selectedNode.id}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Label:</span>
                  <span className="detail-value">{selectedNode.label}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Type:</span>
                  <span className="detail-value">{selectedNode.type}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Degree:</span>
                  <span className="detail-value">{selectedNode.degree}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Connections:</span>
                  <span className="detail-value">
                    {getConnectedNodes(selectedNode.id).length}
                  </span>
                </div>
              </div>
            </div>
          )}
        </aside>

        {/* Graph Visualization Area */}
        <main className="graph-content">
          {loading ? (
            <div className="graph-loading">
              <Icon name="Loader2" size={48} className="spin" />
              <span>Loading graph...</span>
            </div>
          ) : error ? (
            <div className="graph-error">
              <Icon name="AlertCircle" size={48} />
              <span>Failed to load graph</span>
              <button className="btn btn-secondary" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : filteredData && filteredData.nodes.length > 0 ? (
            <div className="graph-visualization">
              {/* Placeholder for actual graph visualization */}
              <div className="graph-placeholder">
                <Icon name="Network" size={64} />
                <h3>Graph Visualization</h3>
                <p>
                  {filteredData.nodes.length} nodes, {filteredData.edges.length} edges
                </p>
                <p className="graph-note">
                  Interactive graph visualization would render here using a library like D3.js,
                  vis.js, or react-force-graph. Nodes can be dragged, zoomed, and clicked for details.
                </p>
                <div className="graph-sample-nodes">
                  <h4>Sample Nodes:</h4>
                  <div className="node-list">
                    {filteredData.nodes.slice(0, 10).map(node => (
                      <div
                        key={node.id}
                        className={`node-item ${selectedNode?.id === node.id ? 'selected' : ''}`}
                        onClick={() => handleNodeClick(node)}
                      >
                        <div className={`node-icon node-type-${node.type.toLowerCase()}`}>
                          <Icon name="Circle" size={12} />
                        </div>
                        <div className="node-info">
                          <span className="node-label">{node.label}</span>
                          <span className="node-meta">{node.type} • {node.degree} connections</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="graph-empty">
              <Icon name="Network" size={64} />
              <h3>No Graph Data</h3>
              <p>Build a graph to visualize entity relationships</p>
              <button className="btn btn-primary" onClick={buildGraph}>
                <Icon name="GitBranch" size={16} />
                Build Graph
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
