/**
 * TimelinePage - Temporal event visualization
 *
 * Displays events in chronological order with date filtering.
 */

import { useState, useCallback } from 'react';
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

export function TimelinePage() {
  const { toast } = useToast();
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [filterApplied, setFilterApplied] = useState(false);

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
  const { data, loading, error, refetch } = useFetch<EventsResponse>(buildQuery());

  const applyFilter = () => {
    if (startDate && endDate && startDate > endDate) {
      toast.error('Start date must be before end date');
      return;
    }
    setFilterApplied(true);
    setTimeout(() => refetch(), 0);
  };

  const clearFilter = () => {
    setStartDate('');
    setEndDate('');
    setFilterApplied(false);
    setTimeout(() => refetch(), 0);
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

  return (
    <div className="timeline-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Calendar" size={28} />
          <div>
            <h1>Timeline</h1>
            <p className="page-description">Chronological event visualization and date filtering</p>
          </div>
        </div>

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
              <button
                className="btn btn-secondary"
                onClick={clearFilter}
              >
                <Icon name="X" size={16} />
                Clear
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="timeline-content">
        {loading ? (
          <div className="timeline-loading">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Loading timeline events...</span>
          </div>
        ) : error ? (
          <div className="timeline-error">
            <Icon name="AlertCircle" size={32} />
            <span>Failed to load timeline events</span>
            <button className="btn btn-secondary" onClick={() => refetch()}>
              Retry
            </button>
          </div>
        ) : data && data.events.length > 0 ? (
          <div className="timeline-list">
            {data.events.map(event => (
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
                      <Icon name="Calendar" size={16} />
                      <span className="event-date">{formatDate(event.date_start)}</span>
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
                        <Icon name={getPrecisionIcon(event.precision)} size={14} />
                        {event.precision}
                      </span>
                      <span className="event-confidence">
                        {Math.round(event.confidence * 100)}% confidence
                      </span>
                    </div>
                  </div>
                  <p className="event-text">{event.text}</p>
                  {event.entities.length > 0 && (
                    <div className="event-entities">
                      <Icon name="Users" size={14} />
                      <span className="entities-label">Entities:</span>
                      <div className="entity-tags">
                        {event.entities.map((entity, idx) => (
                          <span key={idx} className="entity-tag">{entity}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="event-footer">
                    <span className="event-document">
                      <Icon name="FileText" size={14} />
                      {event.document_id}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="timeline-empty">
            <Icon name="Calendar" size={48} />
            <span>No timeline events found</span>
            {filterApplied && (
              <p className="empty-hint">Try adjusting your date filter</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
