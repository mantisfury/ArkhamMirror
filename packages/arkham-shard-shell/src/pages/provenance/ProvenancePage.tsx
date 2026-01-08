/**
 * ProvenancePage - Data provenance, chains of custody, and lineage tracking
 *
 * Provides UI for viewing artifacts, evidence chains, and data lineage.
 * Supports automatic tracking of entities through the system.
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { AIAnalystButton } from '../../components/AIAnalyst';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './ProvenancePage.css';

// Types
interface Artifact {
  id: string;
  artifact_type: string;
  entity_id: string;
  entity_table: string;
  title?: string;
  hash?: string;
  created_at?: string;
  metadata: Record<string, unknown>;
}

interface Chain {
  id: string;
  title: string;
  description?: string;
  chain_type: string;
  status: string;
  project_id?: string;
  root_artifact_id?: string;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
  link_count: number;
  metadata: Record<string, unknown>;
}

interface Link {
  id: string;
  chain_id: string;
  source_artifact_id: string;
  target_artifact_id: string;
  link_type: string;
  confidence: number;
  verified: boolean;
  verified_by?: string;
  verified_at?: string;
  created_at?: string;
  metadata: Record<string, unknown>;
  source_title?: string;
  source_type?: string;
  target_title?: string;
  target_type?: string;
}

interface LineageNode {
  id: string;
  title?: string;
  type?: string;
  is_focus?: boolean;
  depth: number;
}

interface LineageEdge {
  id: string;
  source: string;
  target: string;
  link_type: string;
  confidence: number;
}

interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
  root?: string;
  ancestor_count: number;
  descendant_count: number;
}

type MainTab = 'artifacts' | 'chains' | 'lineage';

export function ProvenancePage() {
  const { toast } = useToast();
  const [mainTab, setMainTab] = useState<MainTab>('artifacts');
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [selectedChain, setSelectedChain] = useState<Chain | null>(null);
  const [artifactTypeFilter, setArtifactTypeFilter] = useState<string>('');
  const [lineageArtifactId, setLineageArtifactId] = useState<string>('');

  // Create chain form
  const [showCreateChain, setShowCreateChain] = useState(false);
  const [newChainTitle, setNewChainTitle] = useState('');
  const [newChainDescription, setNewChainDescription] = useState('');
  const [creating, setCreating] = useState(false);

  // Fetch artifacts
  const { data: artifacts, loading: artifactsLoading, error: artifactsError, refetch: refetchArtifacts } = useFetch<Artifact[]>(
    `/api/provenance/artifacts${artifactTypeFilter ? `?artifact_type=${artifactTypeFilter}` : ''}`
  );

  // Fetch chains
  const { data: chainsData, loading: chainsLoading, error: chainsError, refetch: refetchChains } = useFetch<{ items: Chain[]; total: number }>(
    '/api/provenance/chains'
  );

  // Fetch links for selected chain
  const { data: chainLinks, loading: linksLoading } = useFetch<Link[]>(
    selectedChain ? `/api/provenance/chains/${selectedChain.id}/links` : null
  );

  // Fetch lineage for selected artifact
  const { data: lineage, loading: lineageLoading, error: lineageError } = useFetch<LineageGraph>(
    lineageArtifactId ? `/api/provenance/lineage/${lineageArtifactId}` : null
  );

  const chains = chainsData?.items || [];

  const handleSelectArtifact = useCallback((artifact: Artifact) => {
    setSelectedArtifact(artifact);
  }, []);

  const handleSelectChain = useCallback((chain: Chain) => {
    setSelectedChain(chain);
  }, []);

  const handleViewLineage = useCallback((artifactId: string) => {
    setLineageArtifactId(artifactId);
    setMainTab('lineage');
  }, []);

  const handleCreateChain = async () => {
    if (!newChainTitle.trim()) {
      toast.error('Please enter a chain title');
      return;
    }

    setCreating(true);
    try {
      const response = await fetch('/api/provenance/chains', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newChainTitle,
          description: newChainDescription,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create chain');
      }

      toast.success('Chain created successfully');
      setShowCreateChain(false);
      setNewChainTitle('');
      setNewChainDescription('');
      refetchChains();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create chain');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteChain = async (chainId: string) => {
    if (!confirm('Are you sure you want to delete this chain?')) return;

    try {
      const response = await fetch(`/api/provenance/chains/${chainId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete chain');
      }

      toast.success('Chain deleted');
      setSelectedChain(null);
      refetchChains();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete chain');
    }
  };

  const handleVerifyChain = async (chainId: string) => {
    try {
      const response = await fetch(`/api/provenance/chains/${chainId}/verify`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to verify chain');
      }

      const result = await response.json();
      if (result.verified) {
        toast.success('Chain verified successfully');
      } else {
        toast.warning(`Chain has ${result.issues?.length || 0} issues`);
      }
      refetchChains();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to verify chain');
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const getArtifactIcon = (type: string) => {
    switch (type) {
      case 'document': return 'FileText';
      case 'entity': return 'User';
      case 'claim': return 'Quote';
      case 'chunk': return 'FileSlice';
      default: return 'Box';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'status-active';
      case 'verified': return 'status-verified';
      case 'disputed': return 'status-disputed';
      default: return '';
    }
  };

  // Render Artifacts Tab
  const renderArtifactsTab = () => (
    <div className="artifacts-tab">
      <div className="tab-toolbar">
        <select
          className="artifact-filter"
          value={artifactTypeFilter}
          onChange={(e) => setArtifactTypeFilter(e.target.value)}
        >
          <option value="">All Types</option>
          <option value="document">Documents</option>
          <option value="entity">Entities</option>
          <option value="claim">Claims</option>
          <option value="chunk">Chunks</option>
        </select>
        <span className="item-count">{artifacts?.length || 0} artifacts</span>
      </div>

      <div className="split-layout">
        <div className="list-panel">
          {artifactsLoading ? (
            <div className="loading-state">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading artifacts...</span>
            </div>
          ) : artifactsError ? (
            <div className="error-state">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load artifacts</span>
              <button className="btn btn-secondary" onClick={() => refetchArtifacts()}>Retry</button>
            </div>
          ) : !artifacts || artifacts.length === 0 ? (
            <div className="empty-state">
              <Icon name="Box" size={48} />
              <span>No artifacts tracked yet</span>
              <p className="empty-hint">Artifacts are automatically created when entities are processed</p>
            </div>
          ) : (
            <div className="items-list">
              {artifacts.map(artifact => (
                <div
                  key={artifact.id}
                  className={`item-card ${selectedArtifact?.id === artifact.id ? 'selected' : ''}`}
                  onClick={() => handleSelectArtifact(artifact)}
                >
                  <Icon name={getArtifactIcon(artifact.artifact_type)} size={20} />
                  <div className="item-info">
                    <h3>{artifact.title || artifact.entity_id}</h3>
                    <p>{artifact.artifact_type} - {artifact.entity_table}</p>
                  </div>
                  <button
                    className="btn-icon-sm"
                    onClick={(e) => { e.stopPropagation(); handleViewLineage(artifact.id); }}
                    title="View Lineage"
                  >
                    <Icon name="GitBranch" size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="detail-panel">
          {selectedArtifact ? (
            <div className="artifact-detail">
              <div className="detail-header">
                <Icon name={getArtifactIcon(selectedArtifact.artifact_type)} size={24} />
                <h2>{selectedArtifact.title || 'Untitled Artifact'}</h2>
                <button className="btn-icon" onClick={() => setSelectedArtifact(null)}>
                  <Icon name="X" size={20} />
                </button>
              </div>

              <div className="detail-content">
                <div className="detail-section">
                  <h3>Artifact Information</h3>
                  <div className="detail-grid">
                    <div className="detail-item">
                      <label>ID</label>
                      <code>{selectedArtifact.id}</code>
                    </div>
                    <div className="detail-item">
                      <label>Type</label>
                      <span>{selectedArtifact.artifact_type}</span>
                    </div>
                    <div className="detail-item">
                      <label>Entity ID</label>
                      <code>{selectedArtifact.entity_id}</code>
                    </div>
                    <div className="detail-item">
                      <label>Entity Table</label>
                      <span>{selectedArtifact.entity_table}</span>
                    </div>
                    {selectedArtifact.hash && (
                      <div className="detail-item">
                        <label>Hash</label>
                        <code>{selectedArtifact.hash.substring(0, 16)}...</code>
                      </div>
                    )}
                    <div className="detail-item">
                      <label>Created</label>
                      <span>{formatDate(selectedArtifact.created_at)}</span>
                    </div>
                  </div>
                </div>

                {Object.keys(selectedArtifact.metadata).length > 0 && (
                  <div className="detail-section">
                    <h3>Metadata</h3>
                    <pre className="metadata-display">{JSON.stringify(selectedArtifact.metadata, null, 2)}</pre>
                  </div>
                )}

                <div className="detail-actions">
                  <button className="btn btn-primary" onClick={() => handleViewLineage(selectedArtifact.id)}>
                    <Icon name="GitBranch" size={16} />
                    View Lineage
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="no-selection">
              <Icon name="Box" size={64} />
              <h2>Select an Artifact</h2>
              <p>Choose an artifact from the list to view its details and lineage</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Render Chains Tab
  const renderChainsTab = () => (
    <div className="chains-tab">
      <div className="tab-toolbar">
        <button className="btn btn-primary" onClick={() => setShowCreateChain(true)}>
          <Icon name="Plus" size={16} />
          New Chain
        </button>
        <span className="item-count">{chains.length} chains</span>
      </div>

      <div className="split-layout">
        <div className="list-panel">
          {chainsLoading ? (
            <div className="loading-state">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading chains...</span>
            </div>
          ) : chainsError ? (
            <div className="error-state">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load chains</span>
              <button className="btn btn-secondary" onClick={() => refetchChains()}>Retry</button>
            </div>
          ) : chains.length === 0 ? (
            <div className="empty-state">
              <Icon name="Link" size={48} />
              <span>No evidence chains yet</span>
              <button className="btn btn-primary" onClick={() => setShowCreateChain(true)}>
                Create your first chain
              </button>
            </div>
          ) : (
            <div className="items-list">
              {chains.map(chain => (
                <div
                  key={chain.id}
                  className={`item-card ${selectedChain?.id === chain.id ? 'selected' : ''}`}
                  onClick={() => handleSelectChain(chain)}
                >
                  <Icon name="Link" size={20} />
                  <div className="item-info">
                    <h3>{chain.title}</h3>
                    <p>{chain.chain_type} - {chain.link_count} links</p>
                  </div>
                  <span className={`status-badge ${getStatusColor(chain.status)}`}>
                    {chain.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="detail-panel">
          {selectedChain ? (
            <div className="chain-detail">
              <div className="detail-header">
                <Icon name="Link" size={24} />
                <h2>{selectedChain.title}</h2>
                <button className="btn-icon" onClick={() => setSelectedChain(null)}>
                  <Icon name="X" size={20} />
                </button>
              </div>

              <div className="detail-content">
                <div className="detail-section">
                  <h3>Chain Information</h3>
                  <div className="detail-grid">
                    <div className="detail-item">
                      <label>Status</label>
                      <span className={`status-badge ${getStatusColor(selectedChain.status)}`}>
                        {selectedChain.status}
                      </span>
                    </div>
                    <div className="detail-item">
                      <label>Type</label>
                      <span>{selectedChain.chain_type}</span>
                    </div>
                    <div className="detail-item">
                      <label>Links</label>
                      <span>{selectedChain.link_count}</span>
                    </div>
                    <div className="detail-item">
                      <label>Created</label>
                      <span>{formatDate(selectedChain.created_at)}</span>
                    </div>
                  </div>
                  {selectedChain.description && (
                    <p className="chain-description">{selectedChain.description}</p>
                  )}
                </div>

                <div className="detail-section">
                  <h3>Links ({chainLinks?.length || 0})</h3>
                  {linksLoading ? (
                    <div className="loading-state small">
                      <Icon name="Loader2" size={20} className="spin" />
                      <span>Loading links...</span>
                    </div>
                  ) : chainLinks && chainLinks.length > 0 ? (
                    <div className="links-list">
                      {chainLinks.map(link => (
                        <div key={link.id} className="link-item">
                          <div className="link-source">
                            <Icon name="Box" size={14} />
                            <span>{link.source_title || link.source_artifact_id.substring(0, 8)}</span>
                          </div>
                          <div className="link-arrow">
                            <Icon name="ArrowRight" size={16} />
                            <span className="link-type">{link.link_type}</span>
                          </div>
                          <div className="link-target">
                            <Icon name="Box" size={14} />
                            <span>{link.target_title || link.target_artifact_id.substring(0, 8)}</span>
                          </div>
                          {link.verified && (
                            <Icon name="CheckCircle" size={14} className="verified-icon" title="Verified" />
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-hint">No links in this chain yet</p>
                  )}
                </div>

                <div className="detail-actions">
                  <button className="btn btn-secondary" onClick={() => handleVerifyChain(selectedChain.id)}>
                    <Icon name="CheckCircle" size={16} />
                    Verify Chain
                  </button>
                  <button className="btn btn-danger" onClick={() => handleDeleteChain(selectedChain.id)}>
                    <Icon name="Trash2" size={16} />
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="no-selection">
              <Icon name="Link" size={64} />
              <h2>Select a Chain</h2>
              <p>Choose an evidence chain from the list to view its links and details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Render Lineage Tab
  const renderLineageTab = () => (
    <div className="lineage-tab">
      <div className="tab-toolbar">
        <div className="lineage-search">
          <Icon name="Search" size={16} />
          <input
            type="text"
            placeholder="Enter artifact ID to view lineage..."
            value={lineageArtifactId}
            onChange={(e) => setLineageArtifactId(e.target.value)}
          />
        </div>
        {artifacts && artifacts.length > 0 && (
          <select
            className="artifact-select"
            value={lineageArtifactId}
            onChange={(e) => setLineageArtifactId(e.target.value)}
          >
            <option value="">Select an artifact...</option>
            {artifacts.map(a => (
              <option key={a.id} value={a.id}>
                {a.title || a.entity_id} ({a.artifact_type})
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="lineage-content">
        {!lineageArtifactId ? (
          <div className="empty-state">
            <Icon name="GitBranch" size={64} />
            <h2>View Data Lineage</h2>
            <p>Enter an artifact ID or select from the list to trace its ancestry and descendants</p>
          </div>
        ) : lineageLoading ? (
          <div className="loading-state">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Loading lineage...</span>
          </div>
        ) : lineageError ? (
          <div className="error-state">
            <Icon name="AlertCircle" size={32} />
            <span>Failed to load lineage</span>
          </div>
        ) : lineage ? (
          <div className="lineage-graph">
            <div className="lineage-stats">
              <div className="stat-item">
                <Icon name="ArrowUp" size={16} />
                <span>{lineage.ancestor_count} ancestors</span>
              </div>
              <div className="stat-item">
                <Icon name="ArrowDown" size={16} />
                <span>{lineage.descendant_count} descendants</span>
              </div>
              <div className="stat-item">
                <Icon name="Box" size={16} />
                <span>{lineage.nodes.length} total nodes</span>
              </div>
            </div>

            {lineage.nodes.length === 0 ? (
              <div className="empty-state">
                <Icon name="GitBranch" size={48} />
                <span>No lineage found for this artifact</span>
              </div>
            ) : (
              <div className="lineage-visualization">
                {/* Group nodes by depth */}
                {[...new Set(lineage.nodes.map(n => n.depth))]
                  .sort((a, b) => a - b)
                  .map(depth => (
                    <div key={depth} className="lineage-level">
                      <span className="level-label">
                        {depth < 0 ? `Ancestor ${Math.abs(depth)}` : depth === 0 ? 'Focus' : `Descendant ${depth}`}
                      </span>
                      <div className="level-nodes">
                        {lineage.nodes
                          .filter(n => n.depth === depth)
                          .map(node => (
                            <div
                              key={node.id}
                              className={`lineage-node ${node.is_focus ? 'focus' : ''}`}
                              title={node.id}
                            >
                              <Icon name={getArtifactIcon(node.type || 'unknown')} size={16} />
                              <span>{node.title || node.id.substring(0, 8)}</span>
                              <span className="node-type">{node.type}</span>
                            </div>
                          ))}
                      </div>
                    </div>
                  ))}

                {lineage.edges.length > 0 && (
                  <div className="lineage-edges">
                    <h4>Connections ({lineage.edges.length})</h4>
                    {lineage.edges.map(edge => (
                      <div key={edge.id} className="edge-item">
                        <code>{edge.source.substring(0, 8)}</code>
                        <Icon name="ArrowRight" size={14} />
                        <span className="edge-type">{edge.link_type}</span>
                        <Icon name="ArrowRight" size={14} />
                        <code>{edge.target.substring(0, 8)}</code>
                        <span className="edge-confidence">{(edge.confidence * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );

  return (
    <div className="provenance-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="GitBranch" size={28} />
          <div>
            <h1>Provenance</h1>
            <p className="page-description">Track data origin, evidence chains, and lineage</p>
          </div>
        </div>
        <div className="page-actions">
          <AIAnalystButton
            shard="provenance"
            targetId={selectedArtifact?.id || selectedChain?.id || 'overview'}
            context={{
              currentTab: mainTab,
              selectedArtifact: selectedArtifact,
              selectedChain: selectedChain,
              artifactCount: artifacts?.length || 0,
              chainCount: chains?.length || 0,
            }}
            label="AI Analysis"
            disabled={false}
          />
        </div>
      </header>

      {/* Main Tabs */}
      <div className="main-tabs">
        <button
          className={`main-tab ${mainTab === 'artifacts' ? 'active' : ''}`}
          onClick={() => setMainTab('artifacts')}
        >
          <Icon name="Box" size={18} />
          Artifacts
          {artifacts && <span className="tab-count">{artifacts.length}</span>}
        </button>
        <button
          className={`main-tab ${mainTab === 'chains' ? 'active' : ''}`}
          onClick={() => setMainTab('chains')}
        >
          <Icon name="Link" size={18} />
          Evidence Chains
          {chains && <span className="tab-count">{chains.length}</span>}
        </button>
        <button
          className={`main-tab ${mainTab === 'lineage' ? 'active' : ''}`}
          onClick={() => setMainTab('lineage')}
        >
          <Icon name="GitBranch" size={18} />
          Lineage
        </button>
      </div>

      {/* Tab Content */}
      <main className="tab-content">
        {mainTab === 'artifacts' && renderArtifactsTab()}
        {mainTab === 'chains' && renderChainsTab()}
        {mainTab === 'lineage' && renderLineageTab()}
      </main>

      {/* Create Chain Dialog */}
      {showCreateChain && (
        <div className="dialog-overlay" onClick={() => setShowCreateChain(false)}>
          <div className="dialog" onClick={e => e.stopPropagation()}>
            <div className="dialog-header">
              <h2>Create Evidence Chain</h2>
              <button className="dialog-close" onClick={() => setShowCreateChain(false)}>
                <Icon name="X" size={20} />
              </button>
            </div>
            <div className="dialog-content">
              <div className="form-group">
                <label htmlFor="chain-title">Title</label>
                <input
                  id="chain-title"
                  type="text"
                  className="form-input"
                  value={newChainTitle}
                  onChange={e => setNewChainTitle(e.target.value)}
                  placeholder="Enter chain title..."
                />
              </div>
              <div className="form-group">
                <label htmlFor="chain-description">Description</label>
                <textarea
                  id="chain-description"
                  className="form-textarea"
                  value={newChainDescription}
                  onChange={e => setNewChainDescription(e.target.value)}
                  placeholder="Describe the evidence chain..."
                  rows={3}
                />
              </div>
            </div>
            <div className="dialog-actions">
              <button className="btn btn-secondary" onClick={() => setShowCreateChain(false)} disabled={creating}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleCreateChain} disabled={creating}>
                {creating ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Icon name="Plus" size={16} />
                    Create Chain
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
