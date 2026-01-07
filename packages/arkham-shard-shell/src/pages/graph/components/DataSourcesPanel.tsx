/**
 * DataSourcesPanel - Data source selection for graph building
 *
 * Allows selecting which documents and cross-shard sources to include.
 */

import { useState, useEffect } from 'react';
import { Icon } from '../../../components/common/Icon';
import type { DataSourceSettings } from '../hooks/useGraphSettings';

interface DataSourcesPanelProps {
  settings: DataSourceSettings;
  onChange: (updates: Partial<DataSourceSettings>) => void;
  onRefresh?: () => void;
  isLoading?: boolean;
}

interface SourceStatus {
  available: boolean;
  count: number;
  loading: boolean;
  error?: string;
}

interface DocumentInfo {
  id: string;
  filename: string;
  entity_count: number;
  created_at?: string;
}

interface SourceConfig {
  key: keyof DataSourceSettings;
  label: string;
  description: string;
  icon: string;
  category: 'nodes' | 'edges' | 'weights';
}

// Cross-shard sources only (primary sources handled separately)
const SOURCE_CONFIGS: SourceConfig[] = [
  // Node sources (cross-shard)
  {
    key: 'claims',
    label: 'Claims',
    description: 'Add verified claims as graph nodes',
    icon: 'CheckSquare',
    category: 'nodes',
  },
  {
    key: 'achEvidence',
    label: 'ACH Evidence',
    description: 'Add evidence items from ACH matrices',
    icon: 'FileText',
    category: 'nodes',
  },
  {
    key: 'achHypotheses',
    label: 'ACH Hypotheses',
    description: 'Add hypotheses from ACH analysis',
    icon: 'Lightbulb',
    category: 'nodes',
  },
  {
    key: 'provenanceArtifacts',
    label: 'Provenance Artifacts',
    description: 'Add tracked artifacts and their lineage',
    icon: 'GitBranch',
    category: 'nodes',
  },
  {
    key: 'timelineEvents',
    label: 'Timeline Events',
    description: 'Add temporal events as nodes',
    icon: 'Clock',
    category: 'nodes',
  },
  // Edge sources
  {
    key: 'contradictions',
    label: 'Contradictions',
    description: 'Add contradiction pairs as edges',
    icon: 'XCircle',
    category: 'edges',
  },
  {
    key: 'patterns',
    label: 'Pattern Matches',
    description: 'Add pattern relationships as edges',
    icon: 'Sparkles',
    category: 'edges',
  },
  // Weight modifiers
  {
    key: 'credibilityRatings',
    label: 'Source Credibility',
    description: 'Apply credibility ratings to edge weights',
    icon: 'Shield',
    category: 'weights',
  },
];

export function DataSourcesPanel({
  settings,
  onChange,
  onRefresh,
  isLoading = false,
}: DataSourcesPanelProps) {
  const [statuses, setStatuses] = useState<Record<string, SourceStatus>>({});
  const [loadingStatuses, setLoadingStatuses] = useState(false);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Accordion state - docs expanded by default, others collapsed
  const [docsExpanded, setDocsExpanded] = useState(true);
  const [edgesExpanded, setEdgesExpanded] = useState(false);
  const [nodesExpanded, setNodesExpanded] = useState(false);
  const [additionalEdgesExpanded, setAdditionalEdgesExpanded] = useState(false);
  const [weightsExpanded, setWeightsExpanded] = useState(false);

  // Fetch documents with entity counts
  useEffect(() => {
    const fetchDocuments = async () => {
      setLoadingDocs(true);
      try {
        const response = await fetch('/api/documents/items?limit=500');
        if (response.ok) {
          const data = await response.json();
          const docs: DocumentInfo[] = (data.documents || data.items || []).map((d: any) => ({
            id: d.id,
            filename: d.filename || d.name || d.id,
            entity_count: d.entity_count || 0,
            created_at: d.created_at,
          }));
          setDocuments(docs);
        }
      } catch (err) {
        console.error('Failed to fetch documents:', err);
      } finally {
        setLoadingDocs(false);
      }
    };

    fetchDocuments();
  }, []);

  // Fetch cross-shard source availability
  useEffect(() => {
    const fetchStatuses = async () => {
      setLoadingStatuses(true);
      const newStatuses: Record<string, SourceStatus> = {};

      try {
        const response = await fetch('/api/graph/sources/status');
        if (response.ok) {
          const data = await response.json();
          const sources = data.sources || {};

          SOURCE_CONFIGS.forEach((config) => {
            const source = sources[config.key];
            if (source) {
              newStatuses[config.key] = {
                available: source.available,
                count: source.count || 0,
                loading: false,
              };
            } else {
              newStatuses[config.key] = {
                available: false,
                count: 0,
                loading: false,
                error: 'Not configured',
              };
            }
          });
        } else {
          SOURCE_CONFIGS.forEach((config) => {
            newStatuses[config.key] = {
              available: false,
              count: 0,
              loading: false,
              error: 'Status check failed',
            };
          });
        }
      } catch {
        SOURCE_CONFIGS.forEach((config) => {
          newStatuses[config.key] = {
            available: false,
            count: 0,
            loading: false,
            error: 'Connection failed',
          };
        });
      }

      setStatuses(newStatuses);
      setLoadingStatuses(false);
    };

    fetchStatuses();
  }, []);

  // Document selection handlers
  // Convention: null/undefined = all, [] = none, [ids...] = specific
  const selectedDocIds = settings.selectedDocumentIds;
  const allDocsSelected = selectedDocIds === null || selectedDocIds === undefined;
  const noneSelected = Array.isArray(selectedDocIds) && selectedDocIds.length === 0;

  const toggleDocument = (docId: string) => {
    if (allDocsSelected) {
      // Switching from "all" to specific selection - select all except this one
      const allIds = documents.map(d => d.id).filter(id => id !== docId);
      onChange({ selectedDocumentIds: allIds });
    } else if (noneSelected) {
      // Switching from "none" to selecting just this one
      onChange({ selectedDocumentIds: [docId] });
    } else {
      // Toggle individual document
      if (selectedDocIds!.includes(docId)) {
        const newIds = selectedDocIds!.filter(id => id !== docId);
        onChange({ selectedDocumentIds: newIds });
      } else {
        onChange({ selectedDocumentIds: [...selectedDocIds!, docId] });
      }
    }
  };

  const selectAllDocs = () => {
    onChange({ selectedDocumentIds: null }); // null = all
  };

  const selectNoneDocs = () => {
    onChange({ selectedDocumentIds: [], documentEntities: false });
  };

  const isDocSelected = (docId: string) => {
    return allDocsSelected || (Array.isArray(selectedDocIds) && selectedDocIds.includes(docId));
  };

  // Count enabled sources
  const enabledCrossShardCount = SOURCE_CONFIGS.filter(c => settings[c.key]).length;
  const selectedDocCount = allDocsSelected ? documents.length : (noneSelected ? 0 : selectedDocIds!.length);
  const totalEntityCount = documents
    .filter(d => isDocSelected(d.id))
    .reduce((sum, d) => sum + (d.entity_count || 0), 0);

  // Group cross-shard by category
  const nodesSources = SOURCE_CONFIGS.filter(c => c.category === 'nodes');
  const edgesSources = SOURCE_CONFIGS.filter(c => c.category === 'edges');
  const weightsSources = SOURCE_CONFIGS.filter(c => c.category === 'weights');

  const renderSource = (config: SourceConfig) => {
    const status = statuses[config.key];
    const isEnabled = settings[config.key] as boolean;
    const isAvailable = status?.available ?? false;
    const itemCount = status?.count ?? 0;

    return (
      <label
        key={config.key}
        className={`data-source-item ${isEnabled ? 'enabled' : ''} ${!isAvailable ? 'unavailable' : ''}`}
      >
        <div className="source-checkbox">
          <input
            type="checkbox"
            checked={isEnabled}
            disabled={!isAvailable}
            onChange={e => onChange({ [config.key]: e.target.checked })}
          />
        </div>
        <div className="source-icon">
          <Icon name={config.icon as any} size={16} />
        </div>
        <div className="source-info">
          <span className="source-label">{config.label}</span>
          <span className="source-description">{config.description}</span>
        </div>
        <div className="source-status">
          {loadingStatuses ? (
            <Icon name="Loader2" size={14} className="spin" />
          ) : isAvailable ? (
            <span className="source-count">{itemCount}</span>
          ) : (
            <span className="source-unavailable">N/A</span>
          )}
        </div>
      </label>
    );
  };

  return (
    <div className="data-sources-panel">
      {/* Header */}
      <div className="data-sources-header">
        <div className="header-title">
          <Icon name="Database" size={18} />
          <h3>Data Sources</h3>
        </div>
        <div className="header-actions">
          {(selectedDocCount > 0 || enabledCrossShardCount > 0) && (
            <span className="enabled-badge">
              {selectedDocCount} docs, {enabledCrossShardCount} extra
            </span>
          )}
          <button
            className="refresh-btn"
            onClick={onRefresh}
            disabled={isLoading || (selectedDocCount === 0 && enabledCrossShardCount === 0)}
            title="Rebuild graph with selected sources"
          >
            <Icon name={isLoading ? 'Loader2' : 'RefreshCw'} size={14} className={isLoading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* Document Selector */}
      <div className="document-selector">
        <div
          className="document-selector-header"
          onClick={() => setDocsExpanded(!docsExpanded)}
        >
          <Icon name="FileText" size={18} />
          <div className="header-text">
            <span className="header-title">Document Sources</span>
            <span className="header-subtitle">
              {loadingDocs ? 'Loading...' : allDocsSelected
                ? `All ${documents.length} documents (~${totalEntityCount} entities)`
                : `${selectedDocCount} of ${documents.length} selected (~${totalEntityCount} entities)`
              }
            </span>
          </div>
          <Icon
            name="ChevronDown"
            size={16}
            className={`toggle-icon ${docsExpanded ? 'expanded' : ''}`}
          />
        </div>

        {docsExpanded && (
          <>
            <div className="document-selector-actions">
              <button onClick={selectAllDocs} disabled={allDocsSelected}>
                Select All
              </button>
              <button onClick={selectNoneDocs} disabled={selectedDocCount === 0 && !settings.documentEntities}>
                Select None
              </button>
            </div>

            <div className="document-list">
              {loadingDocs ? (
                <div className="document-list-empty">
                  <Icon name="Loader2" size={16} className="spin" /> Loading documents...
                </div>
              ) : documents.length === 0 ? (
                <div className="document-list-empty">
                  No documents found. Ingest documents first.
                </div>
              ) : (
                documents.map(doc => (
                  <label
                    key={doc.id}
                    className={`document-item ${isDocSelected(doc.id) ? 'selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={isDocSelected(doc.id)}
                      onChange={() => toggleDocument(doc.id)}
                    />
                    <div className="document-item-info">
                      <span className="document-item-name" title={doc.filename}>
                        {doc.filename}
                      </span>
                      {doc.created_at && (
                        <span className="document-item-meta">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <span className="document-item-count" title="Entity count">
                      {doc.entity_count}
                    </span>
                  </label>
                ))
              )}
            </div>
          </>
        )}
      </div>

      {/* Co-occurrence Toggle */}
      <div className={`source-category ${edgesExpanded ? 'expanded' : 'collapsed'}`}>
        <div
          className="category-header clickable"
          onClick={() => setEdgesExpanded(!edgesExpanded)}
        >
          <Icon name="Link" size={14} />
          <span>Relationship Edges</span>
          <Icon
            name="ChevronDown"
            size={14}
            className={`category-toggle ${edgesExpanded ? 'expanded' : ''}`}
          />
        </div>
        {edgesExpanded && (
          <label className="data-source-item">
            <div className="source-checkbox">
              <input
                type="checkbox"
                checked={settings.entityCooccurrences}
                onChange={e => onChange({ entityCooccurrences: e.target.checked })}
              />
            </div>
            <div className="source-icon">
              <Icon name="Link" size={16} />
            </div>
            <div className="source-info">
              <span className="source-label">Co-occurrence Edges</span>
              <span className="source-description">
                Create edges between entities that appear together in documents
              </span>
            </div>
          </label>
        )}
      </div>

      {/* Node Sources */}
      <div className={`source-category ${nodesExpanded ? 'expanded' : 'collapsed'}`}>
        <div
          className="category-header clickable"
          onClick={() => setNodesExpanded(!nodesExpanded)}
        >
          <Icon name="Circle" size={14} />
          <span>Additional Nodes</span>
          <span className="category-hint">Cross-shard entities</span>
          <Icon
            name="ChevronDown"
            size={14}
            className={`category-toggle ${nodesExpanded ? 'expanded' : ''}`}
          />
        </div>
        {nodesExpanded && (
          <div className="source-list">
            {nodesSources.map(renderSource)}
          </div>
        )}
      </div>

      {/* Edge Sources */}
      <div className={`source-category ${additionalEdgesExpanded ? 'expanded' : 'collapsed'}`}>
        <div
          className="category-header clickable"
          onClick={() => setAdditionalEdgesExpanded(!additionalEdgesExpanded)}
        >
          <Icon name="Minus" size={14} />
          <span>Additional Edges</span>
          <span className="category-hint">Cross-shard relationships</span>
          <Icon
            name="ChevronDown"
            size={14}
            className={`category-toggle ${additionalEdgesExpanded ? 'expanded' : ''}`}
          />
        </div>
        {additionalEdgesExpanded && (
          <div className="source-list">
            {edgesSources.map(renderSource)}
          </div>
        )}
      </div>

      {/* Weight Modifiers */}
      <div className={`source-category ${weightsExpanded ? 'expanded' : 'collapsed'}`}>
        <div
          className="category-header clickable"
          onClick={() => setWeightsExpanded(!weightsExpanded)}
        >
          <Icon name="Scale" size={14} />
          <span>Weight Modifiers</span>
          <span className="category-hint">Affect importance</span>
          <Icon
            name="ChevronDown"
            size={14}
            className={`category-toggle ${weightsExpanded ? 'expanded' : ''}`}
          />
        </div>
        {weightsExpanded && (
          <div className="source-list">
            {weightsSources.map(renderSource)}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="data-sources-info">
        <Icon name="Info" size={14} />
        <span>
          Select documents to include entities from. Use "Additional" sources to enrich with cross-shard data.
          Click refresh to rebuild the graph.
        </span>
      </div>
    </div>
  );
}
