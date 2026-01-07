/**
 * PacketsPage - Investigation packet management
 *
 * Provides UI for creating, managing, and sharing investigation packets.
 * Packets bundle documents, entities, and analyses for archiving and collaboration.
 */

import { useState, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import './PacketsPage.css';

// Types
interface Packet {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'finalized' | 'shared' | 'archived';
  visibility: 'private' | 'team' | 'public';
  created_by: string;
  created_at: string;
  updated_at: string;
  version: number;
  contents_count: number;
  size_bytes: number;
  checksum: string | null;
  metadata: Record<string, unknown>;
}

interface PacketContent {
  id: string;
  packet_id: string;
  content_type: 'document' | 'entity' | 'claim' | 'evidence_chain' | 'matrix' | 'timeline' | 'report';
  content_id: string;
  content_title: string;
  added_at: string;
  added_by: string;
  order: number;
}

const STATUS_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  draft: { label: 'Draft', icon: 'FileEdit', color: 'var(--color-info)' },
  finalized: { label: 'Finalized', icon: 'CheckCircle', color: 'var(--color-success)' },
  shared: { label: 'Shared', icon: 'Share2', color: 'var(--color-accent)' },
  archived: { label: 'Archived', icon: 'Archive', color: 'var(--color-muted)' },
};

export function PacketsPage() {
  const { toast } = useToast();
  const [selectedPacket, setSelectedPacket] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAddContentModal, setShowAddContentModal] = useState(false);

  // Fetch packets with usePaginatedFetch
  const { items: packets, loading, error, refetch } = usePaginatedFetch<Packet>(
    '/api/packets/'
  );

  const selectedPacketData = packets.find(p => p.id === selectedPacket);

  // Fetch contents for selected packet
  const { data: contents, refetch: refetchContents } = useFetch<PacketContent[]>(
    selectedPacket ? `/api/packets/${selectedPacket}/contents` : null
  );

  const handleCreatePacket = async (name: string, description: string) => {
    try {
      const response = await fetch('/api/packets/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          visibility: 'private',
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create packet');
      }

      const newPacket = await response.json();
      toast.success('Packet created successfully');
      setShowCreateModal(false);
      setSelectedPacket(newPacket.id);
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create packet');
    }
  };

  const handleFinalizePacket = async (packetId: string) => {
    try {
      const response = await fetch(`/api/packets/${packetId}/finalize`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to finalize packet');
      }

      toast.success('Packet finalized successfully');
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to finalize packet');
    }
  };

  const handleDeletePacket = async (packetId: string) => {
    if (!confirm('Archive this packet?')) return;

    try {
      const response = await fetch(`/api/packets/${packetId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete packet');
      }

      toast.success('Packet archived successfully');
      if (selectedPacket === packetId) {
        setSelectedPacket(null);
      }
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete packet');
    }
  };

  const handleRemoveContent = async (packetId: string, contentId: string) => {
    try {
      const response = await fetch(`/api/packets/${packetId}/contents/${contentId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to remove content');
      }

      toast.success('Content removed from packet');
      refetch();
      refetchContents();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove content');
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="packets-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Package" size={28} />
          <div>
            <h1>Investigation Packets</h1>
            <p className="page-description">Bundle and share documents, entities, and analyses</p>
          </div>
        </div>

        <div className="header-actions">
          <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
            <Icon name="Plus" size={16} />
            New Packet
          </button>
        </div>
      </header>

      <div className="packets-layout">
        {/* Packet List */}
        <aside className="packets-sidebar">
          {loading ? (
            <div className="packets-loading">
              <Icon name="Loader2" size={24} className="spin" />
              <span>Loading packets...</span>
            </div>
          ) : error ? (
            <div className="packets-error">
              <Icon name="AlertCircle" size={24} />
              <span>Failed to load packets</span>
            </div>
          ) : packets.length === 0 ? (
            <div className="packets-empty">
              <Icon name="Package" size={48} />
              <p>No packets yet</p>
              <button className="btn btn-secondary" onClick={() => setShowCreateModal(true)}>
                Create your first packet
              </button>
            </div>
          ) : (
            <div className="packets-list">
              {packets.map(packet => (
                <div
                  key={packet.id}
                  className={`packet-item ${selectedPacket === packet.id ? 'active' : ''}`}
                  onClick={() => setSelectedPacket(packet.id)}
                >
                  <div className="packet-item-header">
                    <h3>{packet.name}</h3>
                    <Icon
                      name={STATUS_LABELS[packet.status].icon}
                      size={16}
                      style={{ color: STATUS_LABELS[packet.status].color }}
                    />
                  </div>
                  <p className="packet-item-description">{packet.description || 'No description'}</p>
                  <div className="packet-item-meta">
                    <span>
                      <Icon name="FileText" size={12} />
                      {packet.contents_count} items
                    </span>
                    <span>v{packet.version}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* Packet Detail */}
        <main className="packets-content">
          {!selectedPacketData ? (
            <div className="packets-placeholder">
              <Icon name="Package" size={64} />
              <p>Select a packet to view details</p>
            </div>
          ) : (
            <>
              <div className="packet-header">
                <div className="packet-info">
                  <h2>{selectedPacketData.name}</h2>
                  <div className="packet-badges">
                    <span
                      className="packet-status-badge"
                      style={{ color: STATUS_LABELS[selectedPacketData.status].color }}
                    >
                      <Icon name={STATUS_LABELS[selectedPacketData.status].icon} size={14} />
                      {STATUS_LABELS[selectedPacketData.status].label}
                    </span>
                    <span className="packet-version-badge">Version {selectedPacketData.version}</span>
                  </div>
                  <p className="packet-description">{selectedPacketData.description}</p>
                  <div className="packet-metadata">
                    <span>
                      <Icon name="Calendar" size={14} />
                      Created {formatDate(selectedPacketData.created_at)}
                    </span>
                    <span>
                      <Icon name="FileText" size={14} />
                      {selectedPacketData.contents_count} items
                    </span>
                    <span>
                      <Icon name="HardDrive" size={14} />
                      {formatBytes(selectedPacketData.size_bytes)}
                    </span>
                  </div>
                </div>

                <div className="packet-actions">
                  {selectedPacketData.status === 'draft' && (
                    <>
                      <button
                        className="btn btn-secondary"
                        onClick={() => setShowAddContentModal(true)}
                      >
                        <Icon name="Plus" size={16} />
                        Add Content
                      </button>
                      <button
                        className="btn btn-primary"
                        onClick={() => handleFinalizePacket(selectedPacketData.id)}
                      >
                        <Icon name="Lock" size={16} />
                        Finalize
                      </button>
                    </>
                  )}
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDeletePacket(selectedPacketData.id)}
                  >
                    <Icon name="Archive" size={16} />
                    Archive
                  </button>
                </div>
              </div>

              <div className="packet-contents">
                <h3>Contents ({contents?.length || 0})</h3>
                {!contents || contents.length === 0 ? (
                  <div className="contents-empty">
                    <Icon name="FileText" size={32} />
                    <p>No content in this packet</p>
                    {selectedPacketData.status === 'draft' && (
                      <button
                        className="btn btn-secondary"
                        onClick={() => setShowAddContentModal(true)}
                      >
                        Add Content
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="contents-list">
                    {contents.map(content => (
                      <div key={content.id} className="content-item">
                        <Icon name="FileText" size={20} />
                        <div className="content-info">
                          <h4>{content.content_title}</h4>
                          <span className="content-type">{content.content_type}</span>
                        </div>
                        {selectedPacketData.status === 'draft' && (
                          <button
                            className="btn-icon"
                            onClick={() =>
                              handleRemoveContent(selectedPacketData.id, content.id)
                            }
                            title="Remove from packet"
                          >
                            <Icon name="X" size={16} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      </div>

      {/* Create Packet Modal */}
      {showCreateModal && (
        <CreatePacketModal
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreatePacket}
        />
      )}

      {/* Add Content Modal */}
      {showAddContentModal && selectedPacket && (
        <AddContentModal
          packetId={selectedPacket}
          onClose={() => setShowAddContentModal(false)}
          onAdd={async (contentType, contentId, contentTitle) => {
            try {
              const response = await fetch(`/api/packets/${selectedPacket}/contents`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  content_type: contentType,
                  content_id: contentId,
                  content_title: contentTitle,
                  order: 0,
                }),
              });
              if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to add content');
              }
              toast.success('Content added to packet');
              setShowAddContentModal(false);
              refetchContents();
            } catch (err) {
              toast.error(err instanceof Error ? err.message : 'Failed to add content');
            }
          }}
        />
      )}
    </div>
  );
}

// Create Packet Modal Component
interface CreatePacketModalProps {
  onClose: () => void;
  onCreate: (name: string, description: string) => void;
}

function CreatePacketModal({ onClose, onCreate }: CreatePacketModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onCreate(name, description);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Create New Packet</h3>
          <button className="btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label htmlFor="packet-name">Packet Name</label>
              <input
                id="packet-name"
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g., Q4 Financial Analysis"
                autoFocus
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="packet-description">Description (optional)</label>
              <textarea
                id="packet-description"
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Describe the purpose of this packet"
                rows={3}
              />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={!name.trim()}>
              <Icon name="Plus" size={16} />
              Create Packet
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Add Content Modal Component
interface AddContentModalProps {
  packetId: string;
  onClose: () => void;
  onAdd: (contentType: string, contentId: string, contentTitle: string) => void;
}

type ContentSearchResult = {
  id: string;
  title: string;
  type: string;
  subtitle?: string;
};

const CONTENT_TYPES = [
  { value: 'document', label: 'Document', icon: 'FileText', endpoint: '/api/documents/items' },
  { value: 'entity', label: 'Entity', icon: 'User', endpoint: '/api/entities/items' },
  { value: 'matrix', label: 'ACH Matrix', icon: 'Grid3X3', endpoint: '/api/ach/matrices' },
  { value: 'report', label: 'Report', icon: 'FileBarChart', endpoint: '/api/reports/' },
  { value: 'timeline', label: 'Timeline', icon: 'Clock', endpoint: '/api/timeline/events' },
  { value: 'claim', label: 'Claim', icon: 'Quote', endpoint: '/api/claims/' },
];

function AddContentModal({ onClose, onAdd }: AddContentModalProps) {
  const [contentType, setContentType] = useState('document');
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<ContentSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState<ContentSearchResult | null>(null);

  const currentType = CONTENT_TYPES.find(t => t.value === contentType);

  // Fetch items when content type changes or search query changes
  useEffect(() => {
    const fetchItems = async () => {
      if (!currentType) return;

      setLoading(true);
      try {
        const params = new URLSearchParams({ limit: '20' });
        if (searchQuery) {
          params.append('search', searchQuery);
        }

        const response = await fetch(`${currentType.endpoint}?${params}`);
        if (!response.ok) {
          setResults([]);
          return;
        }

        const data = await response.json();

        // Normalize different response formats
        let items: ContentSearchResult[] = [];
        const rawItems = data.items || data.documents || data.entities ||
                        data.matrices || data.reports || data.events ||
                        data.claims || [];

        items = rawItems.map((item: any) => ({
          id: item.id,
          title: item.title || item.name || item.description?.slice(0, 50) || item.id,
          type: contentType,
          subtitle: item.created_at ? new Date(item.created_at).toLocaleDateString() : undefined,
        }));

        setResults(items);
      } catch (err) {
        console.error('Failed to fetch items:', err);
        setResults([]);
      } finally {
        setLoading(false);
      }
    };

    const debounce = setTimeout(fetchItems, 300);
    return () => clearTimeout(debounce);
  }, [contentType, searchQuery, currentType]);

  const handleAdd = () => {
    if (!selectedItem) return;
    onAdd(contentType, selectedItem.id, selectedItem.title);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Add Content to Packet</h3>
          <button className="btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>
        <div className="modal-body">
          <div className="content-type-selector">
            <label>Content Type</label>
            <div className="content-type-grid">
              {CONTENT_TYPES.map(type => (
                <button
                  key={type.value}
                  className={`content-type-btn ${contentType === type.value ? 'active' : ''}`}
                  onClick={() => {
                    setContentType(type.value);
                    setSelectedItem(null);
                  }}
                >
                  <Icon name={type.icon as any} size={20} />
                  <span>{type.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="content-search">
            <label>Search {currentType?.label}s</label>
            <div className="search-input-wrapper">
              <Icon name="Search" size={16} />
              <input
                type="text"
                placeholder={`Search ${currentType?.label?.toLowerCase()}s...`}
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          <div className="content-results">
            {loading ? (
              <div className="content-loading">
                <Icon name="Loader2" size={24} className="spin" />
                <span>Loading...</span>
              </div>
            ) : results.length > 0 ? (
              <div className="content-list">
                {results.map(item => (
                  <div
                    key={item.id}
                    className={`content-item ${selectedItem?.id === item.id ? 'selected' : ''}`}
                    onClick={() => setSelectedItem(item)}
                  >
                    <Icon name={currentType?.icon as any || 'File'} size={18} />
                    <div className="content-item-info">
                      <div className="content-item-title">{item.title}</div>
                      {item.subtitle && (
                        <div className="content-item-subtitle">{item.subtitle}</div>
                      )}
                    </div>
                    {selectedItem?.id === item.id && (
                      <Icon name="Check" size={18} className="check-icon" />
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="content-empty">
                <Icon name={currentType?.icon as any || 'File'} size={32} />
                <span>No {currentType?.label?.toLowerCase()}s found</span>
              </div>
            )}
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!selectedItem}
            onClick={handleAdd}
          >
            <Icon name="Plus" size={16} />
            Add to Packet
          </button>
        </div>
      </div>
    </div>
  );
}
