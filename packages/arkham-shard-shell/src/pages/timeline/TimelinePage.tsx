/**
 * TimelinePage - Temporal event visualization
 *
 * Displays events in chronological order with date filtering,
 * statistics, and extraction capabilities.
 */

import { useState, useCallback, useMemo } from 'react';
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

type TabId = 'timeline' | 'stats' | 'extract';

export function TimelinePage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<TabId>('timeline');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [filterApplied, setFilterApplied] = useState(false);
  const [extracting, setExtracting] = useState<string | null>(null);

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

    const groups = new Map<string, TimelineEvent[]>();
    eventsData.events.forEach(event => {
      if (!event?.date_start) return;
      const dateKey = event.date_start.split('T')[0];
      if (!groups.has(dateKey)) {
        groups.set(dateKey, []);
      }
      groups.get(dateKey)!.push(event);
    });
    return groups;
  }, [eventsData]);

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
                                  {event.entities.slice(0, 5).map((entity, idx) => (
                                    <span key={idx} className="entity-tag">{entity}</span>
                                  ))}
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
    </div>
  );
}
