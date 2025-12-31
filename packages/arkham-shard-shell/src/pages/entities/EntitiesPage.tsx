/**
 * EntitiesPage - Entity browser and management
 *
 * Provides UI for viewing, searching, and managing extracted entities.
 * Supports filtering by type, searching, viewing entity details, and merging duplicates.
 */

import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import { MergeDuplicates } from './MergeDuplicates';
import { Relationships } from './Relationships';
import './EntitiesPage.css';

// Types
interface Entity {
  id: string;
  name: string;
  entity_type: string;
  canonical_id: string | null;
  aliases: string[];
  metadata: Record<string, unknown>;
  mention_count: number;
  created_at: string;
  updated_at: string;
}

interface Mention {
  id: string;
  entity_id: string;
  document_id: string;
  mention_text: string;
  confidence: number;
  start_offset: number;
  end_offset: number;
  created_at: string;
}

type TabId = 'browse' | 'merge' | 'relationships';

const ENTITY_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'PERSON', label: 'Person', icon: 'User' },
  { value: 'ORGANIZATION', label: 'Organization', icon: 'Building' },
  { value: 'LOCATION', label: 'Location', icon: 'MapPin' },
  { value: 'DATE', label: 'Date', icon: 'Calendar' },
  { value: 'MONEY', label: 'Money', icon: 'DollarSign' },
  { value: 'EVENT', label: 'Event', icon: 'Sparkles' },
  { value: 'PRODUCT', label: 'Product', icon: 'Package' },
  { value: 'DOCUMENT', label: 'Document', icon: 'FileText' },
  { value: 'CONCEPT', label: 'Concept', icon: 'Lightbulb' },
  { value: 'OTHER', label: 'Other', icon: 'Tag' },
];

const TABS: { id: TabId; label: string; icon: string; route: string }[] = [
  { id: 'browse', label: 'Browse', icon: 'Users', route: '/entities' },
  { id: 'relationships', label: 'Relationships', icon: 'Link', route: '/entities/relationships' },
  { id: 'merge', label: 'Merge Duplicates', icon: 'Merge', route: '/entities/merge' },
];

export function EntitiesPage() {
  const { toast: _toast } = useToast();
  void _toast;

  const location = useLocation();
  const navigate = useNavigate();

  // Determine active tab from URL
  const getTabFromPath = (pathname: string): TabId => {
    if (pathname === '/entities/relationships') return 'relationships';
    if (pathname === '/entities/merge') return 'merge';
    return 'browse';
  };

  const [activeTab, setActiveTab] = useState<TabId>(() => getTabFromPath(location.pathname));

  // Sync tab with URL changes
  useEffect(() => {
    setActiveTab(getTabFromPath(location.pathname));
  }, [location.pathname]);

  // Handle tab click - navigate to route
  const handleTabClick = (tab: typeof TABS[number]) => {
    navigate(tab.route);
  };
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [viewingMentions, setViewingMentions] = useState(false);

  // Fetch entity count/stats
  const { data: stats, refetch: refetchStats } = useFetch<{ count: number }>(
    '/api/entities/count'
  );

  // Fetch entities with pagination
  const { items: entities, loading, error, refetch } = usePaginatedFetch<Entity>(
    '/api/entities/items',
    {
      params: {
        ...(searchQuery && { q: searchQuery }),
        ...(typeFilter && { filter: typeFilter }),
      },
      syncToUrl: false,
    }
  );

  // Fetch mentions for selected entity
  const { data: mentions, loading: loadingMentions } = useFetch<Mention[]>(
    selectedEntity ? `/api/entities/${selectedEntity.id}/mentions` : null
  );

  const handleEntityClick = (entity: Entity) => {
    setSelectedEntity(entity);
    setViewingMentions(false);
  };

  const handleViewMentions = () => {
    setViewingMentions(true);
  };

  const handleCloseDetail = () => {
    setSelectedEntity(null);
    setViewingMentions(false);
  };

  const handleMergeComplete = () => {
    // Refresh entities list after merge
    refetch();
    refetchStats();
  };

  const getEntityIcon = (entityType: string) => {
    const typeInfo = ENTITY_TYPES.find(t => t.value === entityType);
    return typeInfo?.icon || 'Tag';
  };

  const getEntityTypeLabel = (entityType: string) => {
    const typeInfo = ENTITY_TYPES.find(t => t.value === entityType);
    return typeInfo?.label || entityType;
  };

  return (
    <div className="entities-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Users" size={28} />
          <div>
            <h1>Entities</h1>
            <p className="page-description">
              Browse and manage extracted entities
              {stats && stats.count > 0 && (
                <span className="entity-count-badge"> • {stats.count.toLocaleString()} total</span>
              )}
            </p>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="entities-tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => handleTabClick(tab)}
          >
            <Icon name={tab.icon} size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'relationships' ? (
        <div className="entities-layout">
          <Relationships onRelationshipCreated={() => {
            refetch();
            refetchStats();
          }} />
        </div>
      ) : activeTab === 'browse' ? (
        <div className="entities-layout">
          {/* Filters */}
          <div className="entities-filters">
            <div className="search-box">
              <Icon name="Search" size={16} />
              <input
                type="text"
                placeholder="Search entities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="type-filter"
            >
              {ENTITY_TYPES.map(type => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {/* Main Content */}
          <div className="entities-content">
            {/* Entity List */}
            <div className={`entities-list ${selectedEntity ? 'with-detail' : ''}`}>
              {loading ? (
                <div className="entities-loading">
                  <Icon name="Loader2" size={32} className="spin" />
                  <span>Loading entities...</span>
                </div>
              ) : error ? (
                <div className="entities-error">
                  <Icon name="AlertCircle" size={32} />
                  <span>Failed to load entities</span>
                  <button className="btn btn-secondary" onClick={() => refetch()}>
                    Retry
                  </button>
                </div>
              ) : entities && entities.length > 0 ? (
                <div className="entity-items">
                  {entities.map(entity => (
                    <div
                      key={entity.id}
                      className={`entity-card ${selectedEntity?.id === entity.id ? 'selected' : ''}`}
                      onClick={() => handleEntityClick(entity)}
                    >
                      <div className="entity-header">
                        <Icon name={getEntityIcon(entity.entity_type)} size={20} />
                        <div className="entity-info">
                          <h3 className="entity-name">{entity.name}</h3>
                          <span className={`entity-type type-${entity.entity_type.toLowerCase()}`}>
                            {getEntityTypeLabel(entity.entity_type)}
                          </span>
                        </div>
                      </div>
                      {entity.aliases.length > 0 && (
                        <div className="entity-aliases">
                          <Icon name="Tag" size={12} />
                          <span>{entity.aliases.join(', ')}</span>
                        </div>
                      )}
                      <div className="entity-stats">
                        <span className="mention-count">
                          <Icon name="MessageSquare" size={12} />
                          {entity.mention_count} mentions
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="entities-empty">
                  <Icon name="Users" size={48} />
                  <span>No entities found</span>
                  {(searchQuery || typeFilter) && (
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        setSearchQuery('');
                        setTypeFilter('');
                      }}
                    >
                      Clear filters
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Entity Detail Panel */}
            {selectedEntity && (
              <div className="entity-detail">
                <div className="detail-header">
                  <h2>{selectedEntity.name}</h2>
                  <button className="close-btn" onClick={handleCloseDetail}>
                    <Icon name="X" size={20} />
                  </button>
                </div>

                <div className="detail-content">
                  <div className="detail-section">
                    <h3>Information</h3>
                    <div className="detail-grid">
                      <div className="detail-item">
                        <label>Type</label>
                        <span className={`entity-type type-${selectedEntity.entity_type.toLowerCase()}`}>
                          <Icon name={getEntityIcon(selectedEntity.entity_type)} size={14} />
                          {getEntityTypeLabel(selectedEntity.entity_type)}
                        </span>
                      </div>
                      <div className="detail-item">
                        <label>Mentions</label>
                        <span>{selectedEntity.mention_count}</span>
                      </div>
                      {selectedEntity.aliases.length > 0 && (
                        <div className="detail-item full-width">
                          <label>Aliases</label>
                          <div className="aliases-list">
                            {selectedEntity.aliases.map((alias, idx) => (
                              <span key={idx} className="alias-badge">{alias}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {!viewingMentions ? (
                    <div className="detail-actions">
                      <button
                        className="btn btn-primary"
                        onClick={handleViewMentions}
                      >
                        <Icon name="MessageSquare" size={16} />
                        View Mentions
                      </button>
                    </div>
                  ) : (
                    <div className="detail-section">
                      <h3>Mentions</h3>
                      {loadingMentions ? (
                        <div className="mentions-loading">
                          <Icon name="Loader2" size={24} className="spin" />
                          <span>Loading mentions...</span>
                        </div>
                      ) : mentions && mentions.length > 0 ? (
                        <div className="mentions-list">
                          {mentions.map(mention => (
                            <div key={mention.id} className="mention-card">
                              <div className="mention-header">
                                <Icon name="FileText" size={14} />
                                <span className="document-id">
                                  Document: {mention.document_id.substring(0, 8)}...
                                </span>
                                <span className="confidence">
                                  {Math.round(mention.confidence * 100)}%
                                </span>
                              </div>
                              <p className="mention-text">"{mention.mention_text}"</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="mentions-empty">
                          <Icon name="MessageSquare" size={32} />
                          <span>No mentions found</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="entities-layout merge-layout">
          <MergeDuplicates onMergeComplete={handleMergeComplete} />
        </div>
      )}
    </div>
  );
}
