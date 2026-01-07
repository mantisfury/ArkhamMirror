/**
 * TimelinePage - Temporal event visualization
 *
 * Displays events in chronological order with date filtering,
 * statistics, and extraction capabilities.
 */

import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './TimelinePage.css';

// Types
interface TimelineEvent {
  id: string;
  document_id: string;
  text: string;
  date_start: string;
  date_end: string | null;
  precision: string;
  confidence: number;
  entities: string[];
  event_type: string;
  span: [number, number] | null;
  metadata: Record<string, unknown>;
}

interface EventsResponse {
  events: TimelineEvent[];
  count: number;
  limit: number;
  offset: number;
}

interface StatsResponse {
  total_events: number;
  total_documents: number;
  date_range: { earliest: string; latest: string } | null;
  by_precision: Record<string, number>;
  by_type: Record<string, number>;
  avg_confidence: number;
  conflicts_detected: number;
}

interface Document {
  id: string;
  filename: string;
  title: string | null;
  created_at: string | null;
  event_count: number;
}

interface EntityWithEvents {
  entity_id: string;
  name: string;
  entity_type: string;
  event_count: number;
}

interface EntitiesResponse {
  entities: EntityWithEvents[];
  count: number;
}

interface EventNote {
  id: string;
  event_id: string;
  note: string;
  author: string | null;
  created_at: string;
}

interface EditingEvent {
  id: string;
  text: string;
  date_start: string;
  date_end: string;
  event_type: string;
  precision: string;
  entities: string[];
}

interface TimelineGap {
  start_date: string;
  end_date: string;
  gap_days: number;
  before_event_id: string;
  after_event_id: string;
  severity: string;
}

interface GapsResponse {
  gaps: TimelineGap[];
  count: number;
  total_gap_days: number;
  median_gap_days: number;
  coverage_percent: number;
}

interface ConflictDetail {
  id: string;
  type: string;
  severity: string;
  event_ids: string[];
  description: string;
  documents: string[];
  suggested_resolution: string | null;
}

interface ConflictsResponse {
  conflicts: ConflictDetail[];
  count: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
}

type TabId = 'timeline' | 'stats' | 'extract';

export function TimelinePage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>('timeline');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedEntityId, setSelectedEntityId] = useState<string>('');
  const [filterApplied, setFilterApplied] = useState(false);
  const [extracting, setExtracting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ type: 'event' | 'document' | 'all'; id?: string; name?: string } | null>(null);

  // Edit modal state
  const [editingEvent, setEditingEvent] = useState<EditingEvent | null>(null);
  const [saving, setSaving] = useState(false);

  // Notes state
  const [showNotesFor, setShowNotesFor] = useState<string | null>(null);
  const [notes, setNotes] = useState<EventNote[]>([]);
  const [newNote, setNewNote] = useState('');
  const [loadingNotes, setLoadingNotes] = useState(false);

  // Gap and conflict analysis state
  const [gapsData, setGapsData] = useState<GapsResponse | null>(null);
  const [conflictsData, setConflictsData] = useState<ConflictsResponse | null>(null);
  const [analyzingGaps, setAnalyzingGaps] = useState(false);
  const [analyzingConflicts, setAnalyzingConflicts] = useState(false);

  // Build query string
  const buildQuery = useCallback(() => {
    const params = new URLSearchParams();
    params.append('limit', '100');
    params.append('offset', '0');

    if (filterApplied) {
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
    }

    return `/api/timeline/events?${params.toString()}`;
  }, [startDate, endDate, filterApplied]);

  // Fetch events
  const { data: eventsData, loading: eventsLoading, error: eventsError, refetch: refetchEvents } = useFetch<EventsResponse>(buildQuery());

  // Fetch stats
  const { data: statsData, loading: statsLoading, refetch: refetchStats } = useFetch<StatsResponse>('/api/timeline/stats');

  // Fetch documents for extraction
  const { data: docsData, loading: docsLoading, refetch: refetchDocs } = useFetch<{ documents: Document[]; count: number }>('/api/timeline/documents');

  // Fetch entities with timeline events
  const { data: entitiesData } = useFetch<EntitiesResponse>('/api/timeline/entities?limit=100');

  // Create entity lookup map for displaying names
  const entityLookup = useMemo(() => {
    const lookup: Record<string, EntityWithEvents> = {};
    if (entitiesData?.entities) {
      for (const entity of entitiesData.entities) {
        lookup[entity.entity_id] = entity;
      }
    }
    return lookup;
  }, [entitiesData]);

  const applyFilter = () => {
    if (startDate && endDate && startDate > endDate) {
      toast.error('Start date must be before end date');
      return;
    }
    setFilterApplied(true);
    setTimeout(() => refetchEvents(), 0);
  };

  const clearFilter = () => {
    setStartDate('');
    setEndDate('');
    setSelectedEntityId('');
    setFilterApplied(false);
    setTimeout(() => refetchEvents(), 0);
  };

  const extractTimeline = async (documentId: string) => {
    setExtracting(documentId);
    try {
      const response = await fetch(`/api/timeline/extract/${documentId}`, { method: 'POST' });
      if (response.ok) {
        const result = await response.json();
        toast.success(`Extracted ${result.count} events in ${Math.round(result.duration_ms)}ms`);
        refetchEvents();
        refetchStats();
        refetchDocs();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Extraction failed');
      }
    } catch {
      toast.error('Failed to extract timeline');
    } finally {
      setExtracting(null);
    }
  };

  const deleteEvent = async (eventId: string) => {
    setDeleting(eventId);
    try {
      const response = await fetch(`/api/timeline/events/${eventId}`, { method: 'DELETE' });
      if (response.ok) {
        toast.success('Event deleted');
        refetchEvents();
        refetchStats();
        refetchDocs();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to delete event');
      }
    } catch {
      toast.error('Failed to delete event');
    } finally {
      setDeleting(null);
      setConfirmDelete(null);
    }
  };

  const deleteDocumentEvents = async (documentId: string) => {
    setDeleting(documentId);
    try {
      const response = await fetch(`/api/timeline/document/${documentId}/events`, { method: 'DELETE' });
      if (response.ok) {
        const result = await response.json();
        toast.success(`Deleted ${result.deleted} events`);
        refetchEvents();
        refetchStats();
        refetchDocs();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to delete events');
      }
    } catch {
      toast.error('Failed to delete document events');
    } finally {
      setDeleting(null);
      setConfirmDelete(null);
    }
  };

  const deleteAllEvents = async () => {
    setDeleting('all');
    try {
      const response = await fetch('/api/timeline/events?confirm=true', { method: 'DELETE' });
      if (response.ok) {
        const result = await response.json();
        toast.success(`Deleted all ${result.deleted} events`);
        refetchEvents();
        refetchStats();
        refetchDocs();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to delete events');
      }
    } catch {
      toast.error('Failed to delete all events');
    } finally {
      setDeleting(null);
      setConfirmDelete(null);
    }
  };

  const handleConfirmDelete = () => {
    if (!confirmDelete) return;

    if (confirmDelete.type === 'event' && confirmDelete.id) {
      deleteEvent(confirmDelete.id);
    } else if (confirmDelete.type === 'document' && confirmDelete.id) {
      deleteDocumentEvents(confirmDelete.id);
    } else if (confirmDelete.type === 'all') {
      deleteAllEvents();
    }
  };

  // Edit event functions
  const openEditModal = (event: TimelineEvent) => {
    setEditingEvent({
      id: event.id,
      text: event.text,
      date_start: event.date_start.split('T')[0],
      date_end: event.date_end?.split('T')[0] || '',
      event_type: event.event_type,
      precision: event.precision,
      entities: event.entities || [],
    });
  };

  const saveEvent = async () => {
    if (!editingEvent) return;

    setSaving(true);
    try {
      const response = await fetch(`/api/timeline/events/${editingEvent.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: editingEvent.text,
          date_start: editingEvent.date_start,
          date_end: editingEvent.date_end || null,
          event_type: editingEvent.event_type,
          precision: editingEvent.precision,
          entities: editingEvent.entities,
        }),
      });

      if (response.ok) {
        toast.success('Event updated');
        setEditingEvent(null);
        refetchEvents();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to update event');
      }
    } catch {
      toast.error('Failed to update event');
    } finally {
      setSaving(false);
    }
  };

  // Notes functions
  const loadNotes = async (eventId: string) => {
    setLoadingNotes(true);
    setShowNotesFor(eventId);
    try {
      const response = await fetch(`/api/timeline/events/${eventId}/notes`);
      if (response.ok) {
        const data = await response.json();
        setNotes(data.notes || []);
      }
    } catch {
      toast.error('Failed to load notes');
    } finally {
      setLoadingNotes(false);
    }
  };

  const addNote = async () => {
    if (!showNotesFor || !newNote.trim()) return;

    try {
      const response = await fetch(`/api/timeline/events/${showNotesFor}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: newNote.trim() }),
      });

      if (response.ok) {
        const data = await response.json();
        setNotes([data, ...notes]);
        setNewNote('');
        toast.success('Note added');
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to add note');
      }
    } catch {
      toast.error('Failed to add note');
    }
  };

  const deleteNote = async (noteId: string) => {
    if (!showNotesFor) return;

    try {
      const response = await fetch(`/api/timeline/events/${showNotesFor}/notes/${noteId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setNotes(notes.filter(n => n.id !== noteId));
        toast.success('Note deleted');
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to delete note');
      }
    } catch {
      toast.error('Failed to delete note');
    }
  };

  // Gap and conflict analysis functions
  const analyzeGaps = async () => {
    setAnalyzingGaps(true);
    try {
      const response = await fetch('/api/timeline/gaps?min_gap_days=30');
      if (response.ok) {
        const data = await response.json();
        setGapsData(data);
      } else {
        toast.error('Failed to analyze gaps');
      }
    } catch {
      toast.error('Failed to analyze gaps');
    } finally {
      setAnalyzingGaps(false);
    }
  };

  const analyzeConflicts = async () => {
    setAnalyzingConflicts(true);
    try {
      const response = await fetch('/api/timeline/conflicts/analyze');
      if (response.ok) {
        const data = await response.json();
        setConflictsData(data);
      } else {
        toast.error('Failed to analyze conflicts');
      }
    } catch {
      toast.error('Failed to analyze conflicts');
    } finally {
      setAnalyzingConflicts(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'var(--error-color)';
      case 'high': return '#ef4444';
      case 'medium': return '#f59e0b';
      case 'low': return '#22c55e';
      default: return 'var(--text-muted)';
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  const formatDateOnly = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const getPrecisionIcon = (precision: string) => {
    switch (precision) {
      case 'exact': return 'Target';
      case 'day': return 'Calendar';
      case 'month': return 'CalendarDays';
      case 'year': return 'CalendarRange';
      case 'quarter': return 'CalendarDays';
      case 'decade': return 'CalendarRange';
      default: return 'Clock';
    }
  };

  const getEventTypeColor = (eventType: string) => {
    switch (eventType) {
      case 'occurrence': return 'var(--accent-color)';
      case 'reference': return 'var(--info-color)';
      case 'deadline': return 'var(--warning-color)';
      case 'period': return 'var(--success-color)';
      default: return 'var(--text-muted)';
    }
  };

  // Group events by date for visual timeline
  const groupedEvents = useMemo(() => {
    if (!eventsData?.events || !Array.isArray(eventsData.events)) {
      return new Map<string, TimelineEvent[]>();
    }

    // Filter events by selected entity if any
    let filteredEvents = eventsData.events;
    if (selectedEntityId) {
      filteredEvents = eventsData.events.filter(event =>
        event.entities && event.entities.includes(selectedEntityId)
      );
    }

    const groups = new Map<string, TimelineEvent[]>();
    filteredEvents.forEach(event => {
      if (!event?.date_start) return;
      const dateKey = event.date_start.split('T')[0];
      if (!groups.has(dateKey)) {
        groups.set(dateKey, []);
      }
      groups.get(dateKey)!.push(event);
    });
    return groups;
  }, [eventsData, selectedEntityId]);

  return (
    <div className="timeline-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Calendar" size={28} />
          <div>
            <h1>Timeline</h1>
            <p className="page-description">Chronological event visualization and extraction</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="timeline-tabs">
          <button
            className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`}
            onClick={() => setActiveTab('timeline')}
          >
            <Icon name="Calendar" size={16} />
            Timeline
          </button>
          <button
            className={`tab-btn ${activeTab === 'stats' ? 'active' : ''}`}
            onClick={() => setActiveTab('stats')}
          >
            <Icon name="BarChart3" size={16} />
            Statistics
          </button>
          <button
            className={`tab-btn ${activeTab === 'extract' ? 'active' : ''}`}
            onClick={() => setActiveTab('extract')}
          >
            <Icon name="FileSearch" size={16} />
            Extract
          </button>
        </div>
      </header>

      <main className="timeline-content">
        {/* Timeline Tab */}
        {activeTab === 'timeline' && (
          <>
            <div className="timeline-filters">
              <div className="date-inputs">
                <div className="date-input-group">
                  <label htmlFor="start-date">Start Date</label>
                  <input
                    id="start-date"
                    type="date"
                    value={startDate}
                    onChange={e => setStartDate(e.target.value)}
                    className="date-input"
                  />
                </div>
                <div className="date-input-group">
                  <label htmlFor="end-date">End Date</label>
                  <input
                    id="end-date"
                    type="date"
                    value={endDate}
                    onChange={e => setEndDate(e.target.value)}
                    className="date-input"
                  />
                </div>
                <div className="date-input-group">
                  <label htmlFor="entity-filter">Filter by Entity</label>
                  <select
                    id="entity-filter"
                    value={selectedEntityId}
                    onChange={e => setSelectedEntityId(e.target.value)}
                    className="entity-select"
                  >
                    <option value="">All Entities</option>
                    {entitiesData?.entities?.map(entity => (
                      <option key={entity.entity_id} value={entity.entity_id}>
                        {entity.name} ({entity.event_count})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="filter-actions">
                <button
                  className="btn btn-primary"
                  onClick={applyFilter}
                  disabled={!startDate && !endDate}
                >
                  <Icon name="Filter" size={16} />
                  Apply Filter
                </button>
                {filterApplied && (
                  <button className="btn btn-secondary" onClick={clearFilter}>
                    <Icon name="X" size={16} />
                    Clear
                  </button>
                )}
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    // Navigate to graph with timeline events enabled
                    const params = new URLSearchParams();
                    params.set('sources', 'timeline');
                    if (filterApplied && startDate) params.set('start_date', startDate);
                    if (filterApplied && endDate) params.set('end_date', endDate);
                    navigate(`/graph?${params.toString()}`);
                    toast.info('Opening Graph with Timeline Events. Enable "Timeline Events" in Data Sources and click Build Graph.');
                  }}
                  disabled={!eventsData?.events || eventsData.events.length === 0}
                  title="Visualize timeline events in the Graph view"
                >
                  <Icon name="Network" size={16} />
                  Visualize in Graph
                </button>
              </div>
            </div>

            {eventsLoading ? (
              <div className="timeline-loading">
                <Icon name="Loader2" size={32} className="spin" />
                <span>Loading timeline events...</span>
              </div>
            ) : eventsError ? (
              <div className="timeline-error">
                <Icon name="AlertCircle" size={32} />
                <span>Failed to load timeline events</span>
                <button className="btn btn-secondary" onClick={() => refetchEvents()}>
                  Retry
                </button>
              </div>
            ) : eventsData?.events && eventsData.events.length > 0 ? (
              <div className="timeline-visual">
                {/* Visual timeline with date groups */}
                {Array.from(groupedEvents.entries()).map(([dateKey, events]) => (
                  <div key={dateKey} className="timeline-date-group">
                    <div className="date-marker">
                      <div className="date-badge">
                        <Icon name="Calendar" size={14} />
                        {formatDateOnly(dateKey)}
                      </div>
                      <div className="date-count">{events.length} event{events.length !== 1 ? 's' : ''}</div>
                    </div>
                    <div className="timeline-events">
                      {events.map(event => (
                        <div key={event.id} className="timeline-event">
                          <div className="event-timeline-marker">
                            <div
                              className="event-dot"
                              style={{ backgroundColor: getEventTypeColor(event.event_type) }}
                            />
                            <div className="event-line" />
                          </div>
                          <div className="event-content">
                            <div className="event-header">
                              <div className="event-date-time">
                                <Icon name="Clock" size={14} />
                                <span className="event-time">{formatDate(event.date_start).split(',')[1]?.trim() || formatDate(event.date_start)}</span>
                                {event.date_end && (
                                  <>
                                    <Icon name="ArrowRight" size={14} />
                                    <span className="event-date">{formatDateOnly(event.date_end)}</span>
                                  </>
                                )}
                              </div>
                              <div className="event-metadata">
                                <span className="event-type" style={{ color: getEventTypeColor(event.event_type) }}>
                                  {event.event_type}
                                </span>
                                <span className="event-precision">
                                  <Icon name={getPrecisionIcon(event.precision) as any} size={14} />
                                  {event.precision}
                                </span>
                                <span className="event-confidence">
                                  {Math.round(event.confidence * 100)}%
                                </span>
                              </div>
                            </div>
                            <p className="event-text">{event.text}</p>
                            {event.entities && event.entities.length > 0 && (
                              <div className="event-entities">
                                <Icon name="Users" size={14} />
                                <div className="entity-tags">
                                  {event.entities.slice(0, 5).map((entityId, idx) => {
                                    const entity = entityLookup[entityId];
                                    const displayName = entity?.name || entityId.slice(0, 12) + '...';
                                    const isSelected = selectedEntityId === entityId;
                                    return (
                                      <button
                                        key={idx}
                                        className={`entity-tag clickable ${isSelected ? 'selected' : ''}`}
                                        onClick={() => setSelectedEntityId(isSelected ? '' : entityId)}
                                        title={`${entity?.name || entityId} (${entity?.entity_type || 'entity'}) - Click to filter`}
                                      >
                                        {displayName}
                                      </button>
                                    );
                                  })}
                                  {event.entities.length > 5 && (
                                    <span className="entity-tag more">+{event.entities.length - 5}</span>
                                  )}
                                </div>
                              </div>
                            )}
                            <div className="event-footer">
                              <span className="event-document">
                                <Icon name="FileText" size={14} />
                                {event.document_id.slice(0, 8)}...
                              </span>
                              <div className="event-actions">
                                <button
                                  className="btn-icon"
                                  onClick={() => loadNotes(event.id)}
                                  title="View/add notes"
                                >
                                  <Icon name="MessageSquare" size={14} />
                                </button>
                                <button
                                  className="btn-icon"
                                  onClick={() => openEditModal(event)}
                                  title="Edit event"
                                >
                                  <Icon name="Edit2" size={14} />
                                </button>
                                <button
                                  className="btn-icon btn-delete"
                                  onClick={() => setConfirmDelete({ type: 'event', id: event.id })}
                                  title="Delete event"
                                >
                                  <Icon name="Trash2" size={14} />
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="timeline-empty">
                <Icon name="Calendar" size={48} />
                <span>No timeline events found</span>
                {filterApplied ? (
                  <p className="empty-hint">Try adjusting your date filter</p>
                ) : (
                  <p className="empty-hint">Extract events from documents to build a timeline</p>
                )}
                <button className="btn btn-primary" onClick={() => setActiveTab('extract')}>
                  <Icon name="FileSearch" size={16} />
                  Extract Events
                </button>
              </div>
            )}
          </>
        )}

        {/* Stats Tab */}
        {activeTab === 'stats' && (
          <div className="timeline-stats">
            {statsLoading ? (
              <div className="timeline-loading">
                <Icon name="Loader2" size={32} className="spin" />
                <span>Loading statistics...</span>
              </div>
            ) : statsData ? (
              <>
                {/* Summary Cards */}
                <div className="stats-cards">
                  <div className="stat-card">
                    <div className="stat-icon">
                      <Icon name="Calendar" size={24} />
                    </div>
                    <div className="stat-info">
                      <span className="stat-value">{statsData.total_events}</span>
                      <span className="stat-label">Total Events</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon">
                      <Icon name="FileText" size={24} />
                    </div>
                    <div className="stat-info">
                      <span className="stat-value">{statsData.total_documents}</span>
                      <span className="stat-label">Documents</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon">
                      <Icon name="Target" size={24} />
                    </div>
                    <div className="stat-info">
                      <span className="stat-value">{Math.round(statsData.avg_confidence * 100)}%</span>
                      <span className="stat-label">Avg Confidence</span>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon">
                      <Icon name="AlertTriangle" size={24} />
                    </div>
                    <div className="stat-info">
                      <span className="stat-value">{statsData.conflicts_detected}</span>
                      <span className="stat-label">Conflicts</span>
                    </div>
                  </div>
                </div>

                {/* Date Range */}
                {statsData.date_range && (
                  <div className="stats-section">
                    <h3>Date Coverage</h3>
                    <div className="date-range-visual">
                      <div className="range-endpoint">
                        <Icon name="Calendar" size={16} />
                        <span>{formatDateOnly(statsData.date_range.earliest)}</span>
                      </div>
                      <div className="range-line" />
                      <div className="range-endpoint">
                        <Icon name="Calendar" size={16} />
                        <span>{formatDateOnly(statsData.date_range.latest)}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* By Type */}
                {statsData.by_type && Object.keys(statsData.by_type).length > 0 && (
                  <div className="stats-section">
                    <h3>Event Types</h3>
                    <div className="stats-bars">
                      {Object.entries(statsData.by_type).map(([type, count]) => (
                        <div key={type} className="stat-bar-row">
                          <span className="bar-label" style={{ color: getEventTypeColor(type) }}>{type}</span>
                          <div className="bar-container">
                            <div
                              className="bar-fill"
                              style={{
                                width: `${statsData.total_events > 0 ? (count / statsData.total_events) * 100 : 0}%`,
                                backgroundColor: getEventTypeColor(type)
                              }}
                            />
                          </div>
                          <span className="bar-count">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* By Precision */}
                {statsData.by_precision && Object.keys(statsData.by_precision).length > 0 && (
                  <div className="stats-section">
                    <h3>Date Precision</h3>
                    <div className="stats-bars">
                      {Object.entries(statsData.by_precision).map(([precision, count]) => (
                        <div key={precision} className="stat-bar-row">
                          <span className="bar-label">
                            <Icon name={getPrecisionIcon(precision) as any} size={14} />
                            {precision}
                          </span>
                          <div className="bar-container">
                            <div
                              className="bar-fill"
                              style={{ width: `${statsData.total_events > 0 ? (count / statsData.total_events) * 100 : 0}%` }}
                            />
                          </div>
                          <span className="bar-count">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Timeline Gaps Analysis */}
                <div className="stats-section">
                  <div className="section-header">
                    <h3>Timeline Gaps</h3>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={analyzeGaps}
                      disabled={analyzingGaps}
                    >
                      {analyzingGaps ? (
                        <>
                          <Icon name="Loader2" size={14} className="spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Icon name="Search" size={14} />
                          Analyze Gaps
                        </>
                      )}
                    </button>
                  </div>
                  {gapsData ? (
                    <div className="analysis-results">
                      <div className="analysis-summary">
                        <div className="summary-item">
                          <span className="summary-value">{gapsData.count}</span>
                          <span className="summary-label">Gaps Found</span>
                        </div>
                        <div className="summary-item">
                          <span className="summary-value">{gapsData.median_gap_days}d</span>
                          <span className="summary-label">Median Gap</span>
                        </div>
                        <div className="summary-item">
                          <span className="summary-value">{gapsData.coverage_percent}%</span>
                          <span className="summary-label">Coverage</span>
                        </div>
                      </div>
                      {gapsData.gaps.length > 0 && (
                        <div className="gap-list">
                          {gapsData.gaps.slice(0, 5).map((gap, idx) => (
                            <div key={idx} className="gap-item">
                              <div className="gap-severity" style={{ backgroundColor: getSeverityColor(gap.severity) }} />
                              <div className="gap-info">
                                <span className="gap-days">{gap.gap_days} days</span>
                                <span className="gap-dates">
                                  {formatDateOnly(gap.start_date)} → {formatDateOnly(gap.end_date)}
                                </span>
                              </div>
                            </div>
                          ))}
                          {gapsData.gaps.length > 5 && (
                            <div className="gap-more">+{gapsData.gaps.length - 5} more gaps</div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="analysis-hint">Click "Analyze Gaps" to detect timeline gaps (&gt;30 days)</p>
                  )}
                </div>

                {/* Conflicts Analysis */}
                <div className="stats-section">
                  <div className="section-header">
                    <h3>Temporal Conflicts</h3>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={analyzeConflicts}
                      disabled={analyzingConflicts}
                    >
                      {analyzingConflicts ? (
                        <>
                          <Icon name="Loader2" size={14} className="spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Icon name="AlertTriangle" size={14} />
                          Analyze Conflicts
                        </>
                      )}
                    </button>
                  </div>
                  {conflictsData ? (
                    <div className="analysis-results">
                      <div className="analysis-summary">
                        <div className="summary-item">
                          <span className="summary-value">{conflictsData.count}</span>
                          <span className="summary-label">Conflicts</span>
                        </div>
                        {Object.entries(conflictsData.by_severity).map(([severity, count]) => (
                          <div key={severity} className="summary-item">
                            <span className="summary-value" style={{ color: getSeverityColor(severity) }}>{count}</span>
                            <span className="summary-label">{severity}</span>
                          </div>
                        ))}
                      </div>
                      {conflictsData.conflicts.length > 0 && (
                        <div className="conflict-list">
                          {conflictsData.conflicts.slice(0, 5).map((conflict) => (
                            <div key={conflict.id} className="conflict-item">
                              <div className="conflict-severity" style={{ backgroundColor: getSeverityColor(conflict.severity) }} />
                              <div className="conflict-info">
                                <span className="conflict-type">{conflict.type}</span>
                                <span className="conflict-desc">{conflict.description}</span>
                                {conflict.suggested_resolution && (
                                  <span className="conflict-resolution">
                                    <Icon name="Lightbulb" size={12} />
                                    {conflict.suggested_resolution}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                          {conflictsData.conflicts.length > 5 && (
                            <div className="conflict-more">+{conflictsData.conflicts.length - 5} more conflicts</div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="analysis-hint">Click "Analyze Conflicts" to detect temporal inconsistencies</p>
                  )}
                </div>
              </>
            ) : (
              <div className="timeline-empty">
                <Icon name="BarChart3" size={48} />
                <span>No statistics available</span>
              </div>
            )}
          </div>
        )}

        {/* Extract Tab */}
        {activeTab === 'extract' && (
          <div className="timeline-extract">
            <div className="extract-header">
              <h3>Extract Timeline Events</h3>
              <p>Select documents to extract temporal events from their text content.</p>
            </div>

            {docsLoading ? (
              <div className="timeline-loading">
                <Icon name="Loader2" size={32} className="spin" />
                <span>Loading documents...</span>
              </div>
            ) : docsData?.documents && docsData.documents.length > 0 ? (
              <div className="document-list">
                {docsData.documents.map(doc => (
                  <div key={doc.id} className="document-item">
                    <div className="doc-icon">
                      <Icon name="FileText" size={20} />
                    </div>
                    <div className="doc-info">
                      <span className="doc-name">{doc.filename || doc.title || doc.id}</span>
                      {doc.created_at && (
                        <span className="doc-date">{formatDateOnly(doc.created_at)}</span>
                      )}
                    </div>
                    <div className="doc-events">
                      {doc.event_count > 0 ? (
                        <span className="event-badge">{doc.event_count} events</span>
                      ) : (
                        <span className="event-badge empty">No events</span>
                      )}
                    </div>
                    <div className="doc-actions">
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => extractTimeline(doc.id)}
                        disabled={extracting === doc.id}
                      >
                        {extracting === doc.id ? (
                          <>
                            <Icon name="Loader2" size={14} className="spin" />
                            Extracting...
                          </>
                        ) : (
                          <>
                            <Icon name="Play" size={14} />
                            Extract
                          </>
                        )}
                      </button>
                      {doc.event_count > 0 && (
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => setConfirmDelete({ type: 'document', id: doc.id, name: doc.filename || doc.id })}
                          disabled={deleting === doc.id}
                        >
                          {deleting === doc.id ? (
                            <Icon name="Loader2" size={14} className="spin" />
                          ) : (
                            <Icon name="Trash2" size={14} />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="timeline-empty">
                <Icon name="FileText" size={48} />
                <span>No documents available</span>
                <p className="empty-hint">Ingest documents to extract timeline events</p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Confirmation Dialog */}
      {confirmDelete && (
        <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <Icon name="AlertTriangle" size={24} className="text-warning" />
              <h3>Confirm Delete</h3>
            </div>
            <div className="modal-body">
              {confirmDelete.type === 'event' && (
                <p>Are you sure you want to delete this event?</p>
              )}
              {confirmDelete.type === 'document' && (
                <p>Delete all events from <strong>{confirmDelete.name}</strong>?</p>
              )}
              {confirmDelete.type === 'all' && (
                <p>Delete <strong>all</strong> timeline events? This cannot be undone.</p>
              )}
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setConfirmDelete(null)}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={handleConfirmDelete}
                disabled={deleting !== null}
              >
                {deleting !== null ? (
                  <>
                    <Icon name="Loader2" size={14} className="spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Icon name="Trash2" size={14} />
                    Delete
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Event Modal */}
      {editingEvent && (
        <div className="modal-overlay" onClick={() => setEditingEvent(null)}>
          <div className="modal-dialog modal-lg" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <Icon name="Edit2" size={24} />
              <h3>Edit Event</h3>
              <button className="btn-icon" onClick={() => setEditingEvent(null)}>
                <Icon name="X" size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label htmlFor="edit-text">Event Text</label>
                <textarea
                  id="edit-text"
                  className="form-input"
                  rows={4}
                  value={editingEvent.text}
                  onChange={e => setEditingEvent({ ...editingEvent, text: e.target.value })}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="edit-date-start">Start Date</label>
                  <input
                    id="edit-date-start"
                    type="date"
                    className="form-input"
                    value={editingEvent.date_start}
                    onChange={e => setEditingEvent({ ...editingEvent, date_start: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="edit-date-end">End Date</label>
                  <input
                    id="edit-date-end"
                    type="date"
                    className="form-input"
                    value={editingEvent.date_end}
                    onChange={e => setEditingEvent({ ...editingEvent, date_end: e.target.value })}
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="edit-type">Event Type</label>
                  <select
                    id="edit-type"
                    className="form-input"
                    value={editingEvent.event_type}
                    onChange={e => setEditingEvent({ ...editingEvent, event_type: e.target.value })}
                  >
                    <option value="historical">Historical</option>
                    <option value="biographical">Biographical</option>
                    <option value="legal">Legal</option>
                    <option value="financial">Financial</option>
                    <option value="medical">Medical</option>
                    <option value="meeting">Meeting</option>
                    <option value="deadline">Deadline</option>
                    <option value="unknown">Unknown</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="edit-precision">Precision</label>
                  <select
                    id="edit-precision"
                    className="form-input"
                    value={editingEvent.precision}
                    onChange={e => setEditingEvent({ ...editingEvent, precision: e.target.value })}
                  >
                    <option value="day">Day</option>
                    <option value="week">Week</option>
                    <option value="month">Month</option>
                    <option value="year">Year</option>
                    <option value="decade">Decade</option>
                    <option value="approximate">Approximate</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setEditingEvent(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={saveEvent}
                disabled={saving || !editingEvent.text.trim()}
              >
                {saving ? (
                  <>
                    <Icon name="Loader2" size={14} className="spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Icon name="Check" size={14} />
                    Save Changes
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Notes Panel */}
      {showNotesFor && (
        <div className="modal-overlay" onClick={() => { setShowNotesFor(null); setNotes([]); setNewNote(''); }}>
          <div className="modal-dialog modal-md" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <Icon name="MessageSquare" size={24} />
              <h3>Event Notes</h3>
              <button className="btn-icon" onClick={() => { setShowNotesFor(null); setNotes([]); setNewNote(''); }}>
                <Icon name="X" size={20} />
              </button>
            </div>
            <div className="modal-body">
              <div className="notes-input">
                <textarea
                  className="form-input"
                  rows={3}
                  placeholder="Add a note..."
                  value={newNote}
                  onChange={e => setNewNote(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && e.ctrlKey) {
                      addNote();
                    }
                  }}
                />
                <button
                  className="btn btn-primary"
                  onClick={addNote}
                  disabled={!newNote.trim()}
                >
                  <Icon name="Plus" size={14} />
                  Add Note
                </button>
              </div>
              <div className="notes-list">
                {loadingNotes ? (
                  <div className="notes-loading">
                    <Icon name="Loader2" size={20} className="spin" />
                    <span>Loading notes...</span>
                  </div>
                ) : notes.length === 0 ? (
                  <div className="notes-empty">
                    <Icon name="MessageSquare" size={32} />
                    <span>No notes yet</span>
                  </div>
                ) : (
                  notes.map(note => (
                    <div key={note.id} className="note-item">
                      <div className="note-content">{note.note}</div>
                      <div className="note-footer">
                        <span className="note-date">
                          {formatDate(note.created_at)}
                        </span>
                        {note.author && (
                          <span className="note-author">{note.author}</span>
                        )}
                        <button
                          className="btn-icon btn-delete"
                          onClick={() => deleteNote(note.id)}
                          title="Delete note"
                        >
                          <Icon name="Trash2" size={14} />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
