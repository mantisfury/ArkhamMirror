/**
 * Relationships - View and manage entity relationships
 *
 * Displays relationships between entities with filtering, creation, and deletion.
 */

import { useState, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './Relationships.css';

interface RelationshipType {
  value: string;
  label: string;
  description: string;
}

interface Relationship {
  id: string;
  source_id: string;
  target_id: string;
  relationship_type: string;
  confidence: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

interface Entity {
  id: string;
  name: string;
  entity_type: string;
}

interface RelationshipsProps {
  onRelationshipCreated?: () => void;
}

export function Relationships({ onRelationshipCreated }: RelationshipsProps) {
  const { toast } = useToast();
  const [typeFilter, setTypeFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedRelationship, setSelectedRelationship] = useState<Relationship | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Entity cache for displaying names
  const [entityCache, setEntityCache] = useState<Record<string, Entity>>({});

  // Fetch relationship types
  const { data: typesData } = useFetch<{ types: RelationshipType[] }>('/api/entities/relationships/types');

  // Fetch relationship stats
  const { data: stats, refetch: refetchStats } = useFetch<{ total: number; by_type: Record<string, number> }>(
    '/api/entities/relationships/stats'
  );

  // Build URL with params
  const relationshipsUrl = `/api/entities/relationships?page_size=100${typeFilter ? `&relationship_type=${typeFilter}` : ''}`;

  // Fetch relationships
  const { data: relationships, loading, error, refetch } = useFetch<Relationship[]>(relationshipsUrl);

  // Fetch entity names for relationships
  useEffect(() => {
    if (!relationships || relationships.length === 0) return;

    const entityIds = new Set<string>();
    relationships.forEach(rel => {
      entityIds.add(rel.source_id);
      entityIds.add(rel.target_id);
    });

    // Fetch any entities not in cache
    entityIds.forEach(async (id) => {
      if (entityCache[id]) return;

      try {
        const response = await fetch(`/api/entities/items/${id}`);
        if (response.ok) {
          const entity = await response.json();
          setEntityCache(prev => ({ ...prev, [id]: entity }));
        }
      } catch {
        // Entity not found - use ID as fallback
      }
    });
  }, [relationships, entityCache]);

  const handleDeleteRelationship = async (relationshipId: string) => {
    setDeleting(relationshipId);

    try {
      const response = await fetch(`/api/entities/relationships/${relationshipId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Delete failed');
      }

      toast.success('Relationship deleted');
      refetch();
      refetchStats();
      setSelectedRelationship(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setDeleting(null);
    }
  };

  const handleCreateSuccess = () => {
    setShowCreateModal(false);
    refetch();
    refetchStats();
    onRelationshipCreated?.();
  };

  const getTypeIcon = (relType: string) => {
    const icons: Record<string, string> = {
      WORKS_FOR: 'Briefcase',
      LOCATED_IN: 'MapPin',
      MEMBER_OF: 'Users',
      OWNS: 'Key',
      RELATED_TO: 'Link',
      MENTIONED_WITH: 'MessageSquare',
      PARENT_OF: 'ArrowUp',
      CHILD_OF: 'ArrowDown',
      SAME_AS: 'Equal',
      PART_OF: 'Puzzle',
      OTHER: 'MoreHorizontal',
    };
    return icons[relType] || 'Link';
  };

  const getTypeLabel = (relType: string) => {
    const type = typesData?.types.find(t => t.value === relType);
    return type?.label || relType;
  };

  const getEntityName = (entityId: string) => {
    const entity = entityCache[entityId];
    return entity?.name || entityId.substring(0, 8) + '...';
  };

  const getEntityType = (entityId: string) => {
    const entity = entityCache[entityId];
    return entity?.entity_type || 'UNKNOWN';
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  };

  return (
    <div className="relationships">
      {/* Header with stats */}
      <div className="relationships-header">
        <div className="header-info">
          <h3>Entity Relationships</h3>
          {stats && (
            <span className="relationships-count">
              {stats.total} total relationships
            </span>
          )}
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowCreateModal(true)}
        >
          <Icon name="Plus" size={16} />
          New Relationship
        </button>
      </div>

      {/* Controls */}
      <div className="relationships-controls">
        <div className="control-group">
          <label>Filter by Type</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="type-select"
          >
            <option value="">All Types</option>
            {typesData?.types.map(type => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <button
          className="btn btn-secondary"
          onClick={() => refetch()}
          disabled={loading}
        >
          <Icon name="RefreshCw" size={16} className={loading ? 'spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stats by type */}
      {stats && Object.keys(stats.by_type).length > 0 && (
        <div className="type-stats">
          {Object.entries(stats.by_type).map(([type, count]) => (
            <button
              key={type}
              className={`type-stat ${typeFilter === type ? 'active' : ''}`}
              onClick={() => setTypeFilter(typeFilter === type ? '' : type)}
            >
              <Icon name={getTypeIcon(type)} size={14} />
              <span className="type-name">{getTypeLabel(type)}</span>
              <span className="type-count">{count}</span>
            </button>
          ))}
        </div>
      )}

      {/* Relationships List */}
      <div className="relationships-content">
        <div className="relationships-list">
          {loading ? (
            <div className="relationships-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading relationships...</span>
            </div>
          ) : error ? (
            <div className="relationships-error">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load relationships</span>
              <button className="btn btn-secondary" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : relationships && relationships.length > 0 ? (
            <div className="relationship-items">
              {relationships.map((rel) => (
                <div
                  key={rel.id}
                  className={`relationship-card ${selectedRelationship?.id === rel.id ? 'selected' : ''}`}
                  onClick={() => setSelectedRelationship(rel)}
                >
                  <div className="relationship-entities">
                    <div className="entity-pill source">
                      <span className="entity-name">{getEntityName(rel.source_id)}</span>
                      <span className="entity-type-small">{getEntityType(rel.source_id)}</span>
                    </div>

                    <div className="relationship-type-badge">
                      <Icon name={getTypeIcon(rel.relationship_type)} size={14} />
                      <span>{getTypeLabel(rel.relationship_type)}</span>
                    </div>

                    <div className="entity-pill target">
                      <span className="entity-name">{getEntityName(rel.target_id)}</span>
                      <span className="entity-type-small">{getEntityType(rel.target_id)}</span>
                    </div>
                  </div>

                  <div className="relationship-meta">
                    <span className="confidence">
                      {Math.round(rel.confidence * 100)}% confidence
                    </span>
                    <span className="date">{formatDate(rel.created_at)}</span>
                  </div>

                  <button
                    className="delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteRelationship(rel.id);
                    }}
                    disabled={deleting === rel.id}
                  >
                    {deleting === rel.id ? (
                      <Icon name="Loader2" size={14} className="spin" />
                    ) : (
                      <Icon name="Trash2" size={14} />
                    )}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="relationships-empty">
              <Icon name="Link" size={48} />
              <span>No relationships found</span>
              <p>Create relationships to connect entities.</p>
              <button
                className="btn btn-primary"
                onClick={() => setShowCreateModal(true)}
              >
                <Icon name="Plus" size={16} />
                Create First Relationship
              </button>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {selectedRelationship && (
          <div className="relationship-detail">
            <div className="detail-header">
              <h3>Relationship Details</h3>
              <button className="close-btn" onClick={() => setSelectedRelationship(null)}>
                <Icon name="X" size={20} />
              </button>
            </div>

            <div className="detail-content">
              <div className="detail-section">
                <h4>Connection</h4>
                <div className="connection-visual">
                  <div className="connection-entity">
                    <Icon name="Circle" size={12} />
                    <div>
                      <span className="name">{getEntityName(selectedRelationship.source_id)}</span>
                      <span className="type">{getEntityType(selectedRelationship.source_id)}</span>
                    </div>
                  </div>

                  <div className="connection-arrow">
                    <div className="arrow-line" />
                    <span className="arrow-label">
                      {getTypeLabel(selectedRelationship.relationship_type)}
                    </span>
                    <Icon name="ArrowRight" size={16} />
                  </div>

                  <div className="connection-entity">
                    <Icon name="Circle" size={12} />
                    <div>
                      <span className="name">{getEntityName(selectedRelationship.target_id)}</span>
                      <span className="type">{getEntityType(selectedRelationship.target_id)}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="detail-section">
                <h4>Properties</h4>
                <div className="detail-grid">
                  <div className="detail-item">
                    <label>Confidence</label>
                    <div className="confidence-bar">
                      <div
                        className="confidence-fill"
                        style={{ width: `${selectedRelationship.confidence * 100}%` }}
                      />
                      <span>{Math.round(selectedRelationship.confidence * 100)}%</span>
                    </div>
                  </div>
                  <div className="detail-item">
                    <label>Created</label>
                    <span>{formatDate(selectedRelationship.created_at)}</span>
                  </div>
                  <div className="detail-item full-width">
                    <label>ID</label>
                    <span className="mono">{selectedRelationship.id}</span>
                  </div>
                </div>
              </div>

              {Object.keys(selectedRelationship.metadata || {}).length > 0 && (
                <div className="detail-section">
                  <h4>Metadata</h4>
                  <pre className="metadata-json">
                    {JSON.stringify(selectedRelationship.metadata, null, 2)}
                  </pre>
                </div>
              )}

              <div className="detail-actions">
                <button
                  className="btn btn-danger"
                  onClick={() => handleDeleteRelationship(selectedRelationship.id)}
                  disabled={deleting === selectedRelationship.id}
                >
                  {deleting === selectedRelationship.id ? (
                    <>
                      <Icon name="Loader2" size={16} className="spin" />
                      Deleting...
                    </>
                  ) : (
                    <>
                      <Icon name="Trash2" size={16} />
                      Delete Relationship
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateRelationshipModal
          relationshipTypes={typesData?.types || []}
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleCreateSuccess}
        />
      )}
    </div>
  );
}

// Create Relationship Modal Component
interface CreateRelationshipModalProps {
  relationshipTypes: RelationshipType[];
  onClose: () => void;
  onSuccess: () => void;
}

function CreateRelationshipModal({ relationshipTypes, onClose, onSuccess }: CreateRelationshipModalProps) {
  const { toast } = useToast();
  const [sourceSearch, setSourceSearch] = useState('');
  const [targetSearch, setTargetSearch] = useState('');
  const [sourceEntity, setSourceEntity] = useState<Entity | null>(null);
  const [targetEntity, setTargetEntity] = useState<Entity | null>(null);
  const [relationshipType, setRelationshipType] = useState('RELATED_TO');
  const [confidence, setConfidence] = useState(1.0);
  const [creating, setCreating] = useState(false);

  // Search for entities
  const { data: sourceResults } = useFetch<{ items: Entity[] }>(
    sourceSearch.length >= 2 ? `/api/entities/items?q=${encodeURIComponent(sourceSearch)}&page_size=5` : null
  );

  const { data: targetResults } = useFetch<{ items: Entity[] }>(
    targetSearch.length >= 2 ? `/api/entities/items?q=${encodeURIComponent(targetSearch)}&page_size=5` : null
  );

  const handleCreate = async () => {
    if (!sourceEntity || !targetEntity) {
      toast.error('Please select both source and target entities');
      return;
    }

    if (sourceEntity.id === targetEntity.id) {
      toast.error('Source and target cannot be the same entity');
      return;
    }

    setCreating(true);

    try {
      const response = await fetch('/api/entities/relationships', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_id: sourceEntity.id,
          target_id: targetEntity.id,
          relationship_type: relationshipType,
          confidence: confidence,
          metadata: {},
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create relationship');
      }

      toast.success('Relationship created');
      onSuccess();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Creation failed');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="create-relationship-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Create Relationship</h3>
          <button className="close-btn" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Source Entity */}
          <div className="form-group">
            <label>Source Entity</label>
            {sourceEntity ? (
              <div className="selected-entity">
                <span className="entity-name">{sourceEntity.name}</span>
                <span className="entity-type">{sourceEntity.entity_type}</span>
                <button onClick={() => setSourceEntity(null)}>
                  <Icon name="X" size={14} />
                </button>
              </div>
            ) : (
              <div className="entity-search">
                <input
                  type="text"
                  placeholder="Search for source entity..."
                  value={sourceSearch}
                  onChange={(e) => setSourceSearch(e.target.value)}
                />
                {sourceResults && sourceResults.items.length > 0 && (
                  <div className="search-results">
                    {sourceResults.items.map(entity => (
                      <button
                        key={entity.id}
                        className="search-result"
                        onClick={() => {
                          setSourceEntity(entity);
                          setSourceSearch('');
                        }}
                      >
                        <span className="name">{entity.name}</span>
                        <span className="type">{entity.entity_type}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Relationship Type */}
          <div className="form-group">
            <label>Relationship Type</label>
            <select
              value={relationshipType}
              onChange={(e) => setRelationshipType(e.target.value)}
            >
              {relationshipTypes.map(type => (
                <option key={type.value} value={type.value}>
                  {type.label} - {type.description}
                </option>
              ))}
            </select>
          </div>

          {/* Target Entity */}
          <div className="form-group">
            <label>Target Entity</label>
            {targetEntity ? (
              <div className="selected-entity">
                <span className="entity-name">{targetEntity.name}</span>
                <span className="entity-type">{targetEntity.entity_type}</span>
                <button onClick={() => setTargetEntity(null)}>
                  <Icon name="X" size={14} />
                </button>
              </div>
            ) : (
              <div className="entity-search">
                <input
                  type="text"
                  placeholder="Search for target entity..."
                  value={targetSearch}
                  onChange={(e) => setTargetSearch(e.target.value)}
                />
                {targetResults && targetResults.items.length > 0 && (
                  <div className="search-results">
                    {targetResults.items.map(entity => (
                      <button
                        key={entity.id}
                        className="search-result"
                        onClick={() => {
                          setTargetEntity(entity);
                          setTargetSearch('');
                        }}
                      >
                        <span className="name">{entity.name}</span>
                        <span className="type">{entity.entity_type}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Confidence */}
          <div className="form-group">
            <label>Confidence: {Math.round(confidence * 100)}%</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={confidence}
              onChange={(e) => setConfidence(parseFloat(e.target.value))}
            />
          </div>

          {/* Visual Preview */}
          {sourceEntity && targetEntity && (
            <div className="relationship-preview">
              <div className="preview-entity">{sourceEntity.name}</div>
              <div className="preview-arrow">
                <Icon name="ArrowRight" size={20} />
                <span>{relationshipTypes.find(t => t.value === relationshipType)?.label || relationshipType}</span>
              </div>
              <div className="preview-entity">{targetEntity.name}</div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleCreate}
            disabled={creating || !sourceEntity || !targetEntity}
          >
            {creating ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Creating...
              </>
            ) : (
              <>
                <Icon name="Plus" size={16} />
                Create Relationship
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
