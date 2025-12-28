/**
 * EventsTab - System event log viewer with filtering
 */

import { useState, useMemo } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useEvents, useEventTypes, useEventSources, eventActions } from '../api';
import type { SystemEvent, EventFilters } from '../api';

// Event type categories for styling
const EVENT_CATEGORIES: Record<string, { icon: string; color: string }> = {
  error: { icon: 'AlertCircle', color: 'var(--danger-color, #ef4444)' },
  fail: { icon: 'XCircle', color: 'var(--danger-color, #ef4444)' },
  warning: { icon: 'AlertTriangle', color: 'var(--warning-color, #f59e0b)' },
  success: { icon: 'CheckCircle', color: 'var(--success-color, #22c55e)' },
  complete: { icon: 'CheckCircle', color: 'var(--success-color, #22c55e)' },
  start: { icon: 'Play', color: 'var(--info-color, #3b82f6)' },
  stop: { icon: 'Square', color: 'var(--text-secondary)' },
  create: { icon: 'Plus', color: 'var(--accent-color, #8b5cf6)' },
  update: { icon: 'Edit', color: 'var(--info-color, #3b82f6)' },
  delete: { icon: 'Trash2', color: 'var(--danger-color, #ef4444)' },
  worker: { icon: 'Users', color: 'var(--info-color, #3b82f6)' },
  queue: { icon: 'List', color: 'var(--warning-color, #f59e0b)' },
  job: { icon: 'Briefcase', color: 'var(--accent-color, #8b5cf6)' },
  document: { icon: 'FileText', color: 'var(--text-primary)' },
  ingest: { icon: 'Download', color: 'var(--success-color, #22c55e)' },
  parse: { icon: 'Code', color: 'var(--info-color, #3b82f6)' },
  embed: { icon: 'Cpu', color: 'var(--warning-color, #f59e0b)' },
  search: { icon: 'Search', color: 'var(--accent-color, #8b5cf6)' },
};

function getEventCategory(eventType: string): { icon: string; color: string } {
  const lower = eventType.toLowerCase();
  for (const [key, value] of Object.entries(EVENT_CATEGORIES)) {
    if (lower.includes(key)) {
      return value;
    }
  }
  return { icon: 'Activity', color: 'var(--text-secondary)' };
}

interface EventRowProps {
  event: SystemEvent;
  onShowPayload: (event: SystemEvent) => void;
}

function EventRow({ event, onShowPayload }: EventRowProps) {
  const category = getEventCategory(event.event_type);
  const isError = event.event_type.toLowerCase().includes('error') ||
                  event.event_type.toLowerCase().includes('fail');

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      return 'Today';
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <tr className={isError ? 'event-row error' : 'event-row'}>
      <td className="time-cell">
        <span className="event-date">{formatDate(event.timestamp)}</span>
        <span className="event-time">{formatTime(event.timestamp)}</span>
      </td>
      <td className="type-cell">
        <span className="event-type-badge" style={{ borderColor: category.color }}>
          <Icon name={category.icon} size={12} style={{ color: category.color }} />
          {event.event_type}
        </span>
      </td>
      <td className="source-cell">
        <code>{event.source}</code>
      </td>
      <td className="payload-cell">
        <button
          className="btn-icon btn-view-payload"
          onClick={() => onShowPayload(event)}
          title="View payload"
        >
          <Icon name="Eye" size={14} />
        </button>
        <span className="payload-preview">
          {Object.keys(event.payload).length > 0
            ? `${Object.keys(event.payload).length} field${Object.keys(event.payload).length !== 1 ? 's' : ''}`
            : 'Empty'}
        </span>
      </td>
    </tr>
  );
}

interface PayloadModalProps {
  event: SystemEvent | null;
  onClose: () => void;
}

function PayloadModal({ event, onClose }: PayloadModalProps) {
  if (!event) return null;

  const category = getEventCategory(event.event_type);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content payload-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            <Icon name={category.icon} size={18} style={{ color: category.color }} />
            Event Details
          </h3>
          <button className="btn-icon" onClick={onClose}>
            <Icon name="X" size={18} />
          </button>
        </div>
        <div className="modal-body">
          <div className="event-detail-row">
            <label>Type:</label>
            <code className="event-type-badge" style={{ borderColor: category.color }}>
              {event.event_type}
            </code>
          </div>
          <div className="event-detail-row">
            <label>Source:</label>
            <code>{event.source}</code>
          </div>
          <div className="event-detail-row">
            <label>Time:</label>
            <span>{new Date(event.timestamp).toLocaleString()}</span>
          </div>
          <div className="event-detail-row">
            <label>Sequence:</label>
            <span>#{event.sequence}</span>
          </div>
          <div className="event-payload-section">
            <label>Payload:</label>
            <pre className="payload-content">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

export function EventsTab() {
  const [filters, setFilters] = useState<EventFilters>({ limit: 100 });
  const [selectedEvent, setSelectedEvent] = useState<SystemEvent | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const { events, total, loading, error, refresh } = useEvents(filters);
  const { types } = useEventTypes();
  const { sources } = useEventSources();

  const showMessage = (type: 'success' | 'error', text: string) => {
    setActionMessage({ type, text });
    setTimeout(() => setActionMessage(null), 3000);
  };

  const handleClearEvents = async () => {
    if (!confirm('Are you sure you want to clear all events? This cannot be undone.')) {
      return;
    }
    const result = await eventActions.clear();
    if (result.success) {
      showMessage('success', `Cleared ${result.cleared} events`);
      refresh();
    } else {
      showMessage('error', result.error || 'Failed to clear events');
    }
  };

  const handleFilterChange = (key: keyof EventFilters, value: string | undefined) => {
    setFilters(prev => ({
      ...prev,
      [key]: value || undefined,
      offset: 0, // Reset offset when filters change
    }));
  };

  const errorCount = useMemo(() => {
    return events.filter(e =>
      e.event_type.toLowerCase().includes('error') ||
      e.event_type.toLowerCase().includes('fail')
    ).length;
  }, [events]);

  if (loading && events.length === 0) {
    return (
      <div className="tab-loading">
        <Icon name="Loader2" size={32} className="spin" />
        <span>Loading events...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-error">
        <Icon name="AlertCircle" size={32} />
        <span>Failed to load events</span>
        <p className="error-detail">{error}</p>
      </div>
    );
  }

  return (
    <div className="events-tab">
      {actionMessage && (
        <div className={`action-message ${actionMessage.type}`}>
          <Icon name={actionMessage.type === 'success' ? 'CheckCircle' : 'AlertCircle'} size={16} />
          {actionMessage.text}
        </div>
      )}

      <section className="events-section">
        <div className="section-header">
          <h3>
            <Icon name="ScrollText" size={18} />
            Event Log
            <span className="event-count">
              {total} event{total !== 1 ? 's' : ''}
              {errorCount > 0 && (
                <span className="error-badge" title="Error events">
                  <Icon name="AlertCircle" size={12} />
                  {errorCount}
                </span>
              )}
            </span>
          </h3>
          <div className="header-actions">
            <span className="refresh-hint">Auto-refreshes every 5s</span>
            <button className="btn btn-secondary btn-sm" onClick={refresh}>
              <Icon name="RefreshCw" size={14} />
              Refresh
            </button>
            <button
              className="btn btn-danger btn-sm"
              onClick={handleClearEvents}
              disabled={events.length === 0}
            >
              <Icon name="Trash2" size={14} />
              Clear
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="event-filters">
          <div className="filter-group">
            <label>
              <Icon name="Filter" size={14} />
              Type:
            </label>
            <select
              value={filters.event_type || ''}
              onChange={(e) => handleFilterChange('event_type', e.target.value)}
            >
              <option value="">All Types</option>
              {types.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label>Source:</label>
            <select
              value={filters.source || ''}
              onChange={(e) => handleFilterChange('source', e.target.value)}
            >
              <option value="">All Sources</option>
              {sources.map(source => (
                <option key={source} value={source}>{source}</option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label>Limit:</label>
            <select
              value={filters.limit || 50}
              onChange={(e) => handleFilterChange('limit', e.target.value)}
            >
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="200">200</option>
              <option value="500">500</option>
            </select>
          </div>
          {(filters.source || filters.event_type) && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setFilters({ limit: filters.limit })}
            >
              <Icon name="X" size={14} />
              Clear Filters
            </button>
          )}
        </div>

        {events.length === 0 ? (
          <div className="empty-state">
            <Icon name="Inbox" size={48} />
            <h4>No Events</h4>
            <p>
              {filters.source || filters.event_type
                ? 'No events match the current filters.'
                : 'No events have been recorded yet. Events will appear here as the system processes documents and performs operations.'}
            </p>
          </div>
        ) : (
          <div className="table-container events-table-container">
            <table className="events-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>Source</th>
                  <th>Payload</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <EventRow
                    key={`${event.sequence}-${event.timestamp}`}
                    event={event}
                    onShowPayload={setSelectedEvent}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination info */}
        {total > (filters.limit || 50) && (
          <div className="pagination-info">
            Showing {events.length} of {total} events
          </div>
        )}
      </section>

      {/* Payload Modal */}
      <PayloadModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
