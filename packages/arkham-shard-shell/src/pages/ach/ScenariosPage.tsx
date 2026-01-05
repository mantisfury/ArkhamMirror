/**
 * Scenarios Page - Cone of Plausibility
 *
 * A separate page for scenario planning and future mapping.
 * Allows users to create branching scenario trees.
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useToast } from '../../context/ToastContext';
import { Icon } from '../../components/common/Icon';
import {
  getMatrix,
  getScenarioTrees,
  getScenarioTree,
  generateScenarioTree,
  deleteScenarioTree,
  addScenarioBranch,
  updateScenarioNode,
  convertScenarioToHypothesis,
  getAIStatus,
} from './api';
import type {
  ACHMatrix,
  ScenarioTree,
  ScenarioTreeListItem,
  ScenarioNode,
  ScenarioStatus,
} from './types';

const STATUS_COLORS: Record<ScenarioStatus, { bg: string; border: string; text: string }> = {
  active: { bg: 'rgba(99, 102, 241, 0.15)', border: '#6366f1', text: '#a5b4fc' },
  occurred: { bg: 'rgba(34, 197, 94, 0.15)', border: '#22c55e', text: '#86efac' },
  ruled_out: { bg: 'rgba(107, 114, 128, 0.15)', border: '#6b7280', text: '#9ca3af' },
  converted: { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6', text: '#93c5fd' },
};

export function ScenariosPage() {
  const { matrixId } = useParams<{ matrixId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [matrix, setMatrix] = useState<ACHMatrix | null>(null);
  const [trees, setTrees] = useState<ScenarioTreeListItem[]>([]);
  const [selectedTree, setSelectedTree] = useState<ScenarioTree | null>(null);
  const [aiAvailable, setAiAvailable] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showNewTreeDialog, setShowNewTreeDialog] = useState(false);
  const [newTreeTitle, setNewTreeTitle] = useState('');
  const [newTreeSummary, setNewTreeSummary] = useState('');

  // Load initial data
  useEffect(() => {
    if (!matrixId) return;

    async function loadData() {
      try {
        const id = matrixId as string;
        const [matrixData, treesData, aiStatus] = await Promise.all([
          getMatrix(id),
          getScenarioTrees(id),
          getAIStatus(),
        ]);
        setMatrix(matrixData);
        setTrees(treesData.trees);
        setAiAvailable(aiStatus.available);
      } catch (error) {
        console.error('Failed to load data:', error);
        toast.error('Failed to load data');
      }
    }

    loadData();
  }, [matrixId]);

  // Load a specific tree
  const loadTree = useCallback(async (treeId: string) => {
    try {
      const tree = await getScenarioTree(treeId);
      setSelectedTree(tree);
    } catch (error) {
      console.error('Failed to load tree:', error);
      toast.error('Failed to load scenario tree');
    }
  }, []);

  // Generate new tree
  const handleGenerateTree = async () => {
    if (!matrixId || !newTreeTitle.trim() || !newTreeSummary.trim()) return;

    setIsLoading(true);
    try {
      const tree = await generateScenarioTree({
        matrix_id: matrixId,
        title: newTreeTitle,
        situation_summary: newTreeSummary,
        max_depth: 2,
      });
      setTrees((prev) => [
        {
          id: tree.id,
          title: tree.title,
          description: tree.description,
          total_scenarios: tree.total_scenarios,
          active_scenarios: tree.nodes.filter((n) => n.status === 'active').length,
          created_at: tree.created_at,
          updated_at: tree.updated_at,
        },
        ...prev,
      ]);
      setSelectedTree(tree);
      setShowNewTreeDialog(false);
      setNewTreeTitle('');
      setNewTreeSummary('');
      toast.success('Scenario tree generated');
    } catch (error) {
      console.error('Failed to generate tree:', error);
      toast.error('Failed to generate scenario tree');
    } finally {
      setIsLoading(false);
    }
  };

  // Delete tree
  const handleDeleteTree = async (treeId: string) => {
    if (!confirm('Delete this scenario tree?')) return;

    try {
      await deleteScenarioTree(treeId);
      setTrees((prev) => prev.filter((t) => t.id !== treeId));
      if (selectedTree?.id === treeId) {
        setSelectedTree(null);
      }
      toast.success('Scenario tree deleted');
    } catch (error) {
      console.error('Failed to delete tree:', error);
      toast.error('Failed to delete scenario tree');
    }
  };

  // Add branch to a node
  const handleAddBranch = async (nodeId: string) => {
    if (!selectedTree) return;

    setIsLoading(true);
    try {
      const result = await addScenarioBranch({
        tree_id: selectedTree.id,
        parent_node_id: nodeId,
      });

      // Reload tree to get updated nodes
      await loadTree(selectedTree.id);
      toast.success(`Added ${result.count} new scenarios`);
    } catch (error) {
      console.error('Failed to add branch:', error);
      toast.error('Failed to add scenarios');
    } finally {
      setIsLoading(false);
    }
  };

  // Update node status
  const handleUpdateStatus = async (nodeId: string, status: ScenarioStatus) => {
    if (!selectedTree) return;

    try {
      await updateScenarioNode(selectedTree.id, nodeId, { status });
      setSelectedTree((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          nodes: prev.nodes.map((n) =>
            n.id === nodeId ? { ...n, status } : n
          ),
        };
      });
    } catch (error) {
      console.error('Failed to update status:', error);
      toast.error('Failed to update status');
    }
  };

  // Convert scenario to hypothesis
  const handleConvertToHypothesis = async (nodeId: string) => {
    if (!selectedTree) return;

    try {
      const result = await convertScenarioToHypothesis({
        tree_id: selectedTree.id,
        node_id: nodeId,
      });
      toast.success(`Created hypothesis: ${result.hypothesis_title}`);
      await loadTree(selectedTree.id);
    } catch (error) {
      console.error('Failed to convert:', error);
      toast.error('Failed to convert to hypothesis');
    }
  };

  // Build tree structure for display
  const buildTreeDisplay = (nodes: ScenarioNode[]): React.ReactNode => {
    const root = nodes.find((n) => n.parent_id === null);
    if (!root) return null;

    const renderNode = (node: ScenarioNode, depth: number): React.ReactNode => {
      const children = nodes
        .filter((n) => n.parent_id === node.id)
        .sort((a, b) => a.branch_order - b.branch_order);
      const statusColor = STATUS_COLORS[node.status];
      const probabilityPercent = Math.round(node.probability * 100);

      return (
        <div key={node.id} className="scenario-node-container">
          <div
            className={`scenario-node depth-${depth}`}
            style={{
              borderColor: statusColor.border,
              backgroundColor: statusColor.bg,
            }}
          >
            <div className="node-header">
              <span className="node-title">{node.title}</span>
              {depth > 0 && (
                <span
                  className="node-probability"
                  style={{
                    backgroundColor: `rgba(99, 102, 241, ${node.probability})`,
                  }}
                >
                  {probabilityPercent}%
                </span>
              )}
            </div>
            <p className="node-description">{node.description}</p>

            {node.timeframe && (
              <div className="node-meta">
                <Icon name="Clock" size={12} />
                {node.timeframe}
              </div>
            )}

            {node.key_drivers.length > 0 && (
              <div className="node-drivers">
                {node.key_drivers.map((driver, i) => (
                  <span key={i} className="driver-tag">
                    {driver}
                  </span>
                ))}
              </div>
            )}

            {node.indicators.length > 0 && (
              <div className="node-indicators">
                <span className="indicators-label">Indicators:</span>
                {node.indicators.map((ind) => (
                  <span
                    key={ind.id}
                    className={`indicator-tag ${ind.is_triggered ? 'triggered' : ''}`}
                  >
                    {ind.description}
                  </span>
                ))}
              </div>
            )}

            <div className="node-actions">
              <select
                className="status-select"
                value={node.status}
                onChange={(e) =>
                  handleUpdateStatus(node.id, e.target.value as ScenarioStatus)
                }
                style={{
                  backgroundColor: statusColor.bg,
                  borderColor: statusColor.border,
                  color: statusColor.text,
                }}
              >
                <option value="active">Active</option>
                <option value="occurred">Occurred</option>
                <option value="ruled_out">Ruled Out</option>
              </select>

              {depth > 0 && node.status === 'active' && !node.converted_hypothesis_id && (
                <>
                  <button
                    className="btn btn-xs btn-soft"
                    onClick={() => handleAddBranch(node.id)}
                    disabled={isLoading}
                    title="Generate sub-scenarios"
                  >
                    <Icon name="GitBranch" size={12} />
                    Branch
                  </button>
                  <button
                    className="btn btn-xs btn-soft btn-primary"
                    onClick={() => handleConvertToHypothesis(node.id)}
                    title="Convert to ACH hypothesis"
                  >
                    <Icon name="Lightbulb" size={12} />
                    To Hypothesis
                  </button>
                </>
              )}

              {node.converted_hypothesis_id && (
                <span className="converted-badge">
                  <Icon name="Check" size={12} />
                  Converted
                </span>
              )}
            </div>
          </div>

          {children.length > 0 && (
            <div className="scenario-children">
              {children.map((child) => renderNode(child, depth + 1))}
            </div>
          )}
        </div>
      );
    };

    return renderNode(root, 0);
  };

  if (!matrixId) {
    return <div>No matrix ID provided</div>;
  }

  return (
    <div className="scenarios-page">
      <div className="page-header">
        <div className="header-left">
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => navigate(`/ach/${matrixId}`)}
          >
            <Icon name="ArrowLeft" size={16} />
            Back to Matrix
          </button>
          <div className="header-title">
            <Icon name="Network" size={24} className="icon-primary" />
            <div>
              <h1>Cone of Plausibility</h1>
              {matrix && <span className="subtitle">{matrix.title}</span>}
            </div>
          </div>
        </div>
        <div className="header-actions">
          {aiAvailable && (
            <button
              className="btn btn-primary"
              onClick={() => setShowNewTreeDialog(true)}
            >
              <Icon name="Plus" size={16} />
              New Scenario Tree
            </button>
          )}
        </div>
      </div>

      <div className="scenarios-content">
        {/* Tree List Sidebar */}
        <div className="trees-sidebar">
          <h3>Scenario Trees</h3>
          {trees.length === 0 ? (
            <div className="empty-state">
              <Icon name="Network" size={32} className="icon-muted" />
              <p>No scenario trees yet</p>
              <button
                className="btn btn-sm btn-primary"
                onClick={() => setShowNewTreeDialog(true)}
                disabled={!aiAvailable}
              >
                Create First Tree
              </button>
            </div>
          ) : (
            <div className="trees-list">
              {trees.map((tree) => (
                <div
                  key={tree.id}
                  className={`tree-item ${selectedTree?.id === tree.id ? 'selected' : ''}`}
                  onClick={() => loadTree(tree.id)}
                >
                  <div className="tree-item-content">
                    <span className="tree-title">{tree.title}</span>
                    <span className="tree-meta">
                      {tree.total_scenarios} scenarios · {tree.active_scenarios} active
                    </span>
                  </div>
                  <button
                    className="btn btn-icon btn-xs btn-danger"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteTree(tree.id);
                    }}
                    title="Delete tree"
                  >
                    <Icon name="Trash2" size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Tree Visualization */}
        <div className="tree-visualization">
          {selectedTree ? (
            <div className="tree-container">
              <div className="tree-header">
                <h2>{selectedTree.title}</h2>
                <p className="tree-description">{selectedTree.description}</p>
                {selectedTree.situation_summary && (
                  <div className="situation-summary">
                    <strong>Current Situation:</strong> {selectedTree.situation_summary}
                  </div>
                )}
              </div>
              <div className="tree-body">
                {buildTreeDisplay(selectedTree.nodes)}
              </div>
            </div>
          ) : (
            <div className="empty-visualization">
              <Icon name="Network" size={48} className="icon-muted" />
              <p>Select a scenario tree to view</p>
            </div>
          )}
        </div>
      </div>

      {/* New Tree Dialog */}
      {showNewTreeDialog && (
        <div className="modal-overlay" onClick={() => setShowNewTreeDialog(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <Icon name="Network" size={20} />
                Create Scenario Tree
              </h3>
              <button
                className="btn btn-icon btn-ghost"
                onClick={() => setShowNewTreeDialog(false)}
              >
                <Icon name="X" size={16} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Title</label>
                <input
                  type="text"
                  className="input"
                  value={newTreeTitle}
                  onChange={(e) => setNewTreeTitle(e.target.value)}
                  placeholder="e.g., Q1 2024 Market Scenarios"
                />
              </div>
              <div className="form-group">
                <label>Current Situation Summary</label>
                <textarea
                  className="textarea"
                  value={newTreeSummary}
                  onChange={(e) => setNewTreeSummary(e.target.value)}
                  placeholder="Describe the current situation and key factors to consider..."
                  rows={4}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-ghost"
                onClick={() => setShowNewTreeDialog(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleGenerateTree}
                disabled={isLoading || !newTreeTitle.trim() || !newTreeSummary.trim()}
              >
                {isLoading ? (
                  <>
                    <Icon name="Loader2" size={14} className="spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Icon name="Sparkles" size={14} />
                    Generate Scenarios
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .scenarios-page {
          height: 100%;
          display: flex;
          flex-direction: column;
          background: var(--arkham-bg);
        }
        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1rem 1.5rem;
          border-bottom: 1px solid var(--arkham-border);
          background: var(--arkham-bg-secondary);
        }
        .header-left {
          display: flex;
          align-items: center;
          gap: 1.5rem;
        }
        .header-title {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        .header-title h1 {
          font-size: 1.25rem;
          font-weight: 600;
          margin: 0;
        }
        .header-title .subtitle {
          font-size: 0.875rem;
          color: var(--arkham-text-muted);
        }
        .scenarios-content {
          flex: 1;
          display: flex;
          overflow: hidden;
        }
        .trees-sidebar {
          width: 280px;
          border-right: 1px solid var(--arkham-border);
          padding: 1rem;
          overflow-y: auto;
          background: var(--arkham-bg-secondary);
        }
        .trees-sidebar h3 {
          font-size: 0.8125rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--arkham-text-muted);
          margin: 0 0 1rem;
        }
        .trees-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .tree-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.75rem;
          background: var(--arkham-bg);
          border: 1px solid var(--arkham-border);
          border-radius: 0.5rem;
          cursor: pointer;
          transition: all 0.15s;
        }
        .tree-item:hover {
          border-color: var(--arkham-primary);
        }
        .tree-item.selected {
          border-color: var(--arkham-primary);
          background: rgba(99, 102, 241, 0.1);
        }
        .tree-item-content {
          min-width: 0;
        }
        .tree-title {
          display: block;
          font-weight: 500;
          color: var(--arkham-text);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .tree-meta {
          font-size: 0.75rem;
          color: var(--arkham-text-muted);
        }
        .tree-visualization {
          flex: 1;
          overflow: auto;
          padding: 1.5rem;
        }
        .tree-container {
          max-width: 1200px;
        }
        .tree-header {
          margin-bottom: 2rem;
        }
        .tree-header h2 {
          font-size: 1.5rem;
          margin: 0 0 0.5rem;
        }
        .tree-description {
          color: var(--arkham-text-muted);
          margin: 0 0 1rem;
        }
        .situation-summary {
          background: rgba(99, 102, 241, 0.1);
          border: 1px solid rgba(99, 102, 241, 0.3);
          border-radius: 0.5rem;
          padding: 1rem;
          font-size: 0.9375rem;
          color: var(--arkham-text-secondary);
        }
        .scenario-node-container {
          position: relative;
          margin-left: 1.5rem;
          padding-left: 1.5rem;
          border-left: 2px solid var(--arkham-border);
        }
        .scenario-node-container:first-child {
          margin-left: 0;
          padding-left: 0;
          border-left: none;
        }
        .scenario-node {
          background: var(--arkham-bg-secondary);
          border: 1px solid var(--arkham-border);
          border-left: 4px solid;
          border-radius: 0.5rem;
          padding: 1rem;
          margin-bottom: 1rem;
        }
        .scenario-node.depth-0 {
          background: rgba(99, 102, 241, 0.1);
          border-color: var(--arkham-primary);
        }
        .node-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 0.5rem;
        }
        .node-title {
          font-weight: 600;
          font-size: 1rem;
          color: var(--arkham-text);
        }
        .node-probability {
          font-size: 0.75rem;
          font-weight: 600;
          padding: 0.125rem 0.5rem;
          border-radius: 0.25rem;
          color: white;
        }
        .node-description {
          color: var(--arkham-text-secondary);
          font-size: 0.875rem;
          margin: 0 0 0.75rem;
          line-height: 1.5;
        }
        .node-meta {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          font-size: 0.75rem;
          color: var(--arkham-text-muted);
          margin-bottom: 0.5rem;
        }
        .node-drivers {
          display: flex;
          flex-wrap: wrap;
          gap: 0.375rem;
          margin-bottom: 0.5rem;
        }
        .driver-tag {
          font-size: 0.6875rem;
          padding: 0.125rem 0.375rem;
          background: rgba(99, 102, 241, 0.1);
          border: 1px solid rgba(99, 102, 241, 0.3);
          border-radius: 0.25rem;
          color: var(--arkham-primary);
        }
        .node-indicators {
          font-size: 0.75rem;
          color: var(--arkham-text-muted);
          margin-bottom: 0.75rem;
        }
        .indicators-label {
          font-weight: 500;
          margin-right: 0.5rem;
        }
        .indicator-tag {
          display: inline-block;
          margin: 0.125rem 0.25rem;
          padding: 0.125rem 0.375rem;
          background: rgba(0,0,0,0.2);
          border-radius: 0.25rem;
        }
        .indicator-tag.triggered {
          background: rgba(34, 197, 94, 0.2);
          color: #86efac;
        }
        .node-actions {
          display: flex;
          gap: 0.5rem;
          margin-top: 0.75rem;
          padding-top: 0.75rem;
          border-top: 1px solid var(--arkham-border);
        }
        .status-select {
          font-size: 0.6875rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.025em;
          padding: 0.25rem 0.5rem;
          border: 1px solid;
          border-radius: 0.25rem;
          cursor: pointer;
        }
        .converted-badge {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          font-size: 0.75rem;
          color: #22c55e;
        }
        .scenario-children {
          margin-top: 0.5rem;
        }
        .empty-visualization {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: var(--arkham-text-muted);
        }
        .empty-state {
          text-align: center;
          padding: 2rem;
          color: var(--arkham-text-muted);
        }
        .empty-state p {
          margin: 0.5rem 0 1rem;
        }
        .icon-muted {
          color: var(--arkham-text-muted);
        }
        .icon-primary {
          color: var(--arkham-primary);
        }

        /* Modal Styles */
        .modal-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 100;
        }
        .modal-content {
          background: var(--arkham-bg-secondary);
          border: 1px solid var(--arkham-border);
          border-radius: 0.75rem;
          width: 100%;
          max-width: 500px;
          max-height: 90vh;
          overflow: auto;
        }
        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1rem 1.5rem;
          border-bottom: 1px solid var(--arkham-border);
        }
        .modal-header h3 {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 1.125rem;
          margin: 0;
        }
        .modal-body {
          padding: 1.5rem;
        }
        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 0.75rem;
          padding: 1rem 1.5rem;
          border-top: 1px solid var(--arkham-border);
        }
        .form-group {
          margin-bottom: 1rem;
        }
        .form-group label {
          display: block;
          font-size: 0.875rem;
          font-weight: 500;
          margin-bottom: 0.375rem;
          color: var(--arkham-text-secondary);
        }
        .input, .textarea {
          width: 100%;
          background: var(--arkham-bg);
          border: 1px solid var(--arkham-border);
          border-radius: 0.375rem;
          padding: 0.625rem 0.75rem;
          color: var(--arkham-text);
          font-size: 0.9375rem;
        }
        .textarea {
          resize: vertical;
          min-height: 100px;
        }
        .input:focus, .textarea:focus {
          outline: none;
          border-color: var(--arkham-primary);
        }
        .btn-xs {
          padding: 0.25rem 0.5rem;
          font-size: 0.75rem;
        }
        .spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
