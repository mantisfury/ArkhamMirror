/**
 * AuditPage - Audit log viewer for tenant admins
 *
 * Displays security-relevant events with filtering and export capabilities.
 * Part of Phase 6: Audit Logging Implementation.
 */

import { useState, useCallback, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { apiGet } from '../../utils/api';
import './AuditPage.css';

// Types
interface AuditEvent {
  id: string;
  tenant_id: string | null;
  user_id: string | null;
  user_email: string | null;
  event_type: string;
  target_type: string | null;
  target_id: string | null;
  action: string;
  details: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

interface AuditListResponse {
  events: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

interface AuditStats {
  total_events: number;
  events_today: number;
  events_this_week: number;
  failed_logins_today: number;
  top_event_types: { event_type: string; count: number }[];
  recent_users: { email: string; event_count: number; last_activity: string }[];
}

// Event type labels for display
const EVENT_TYPE_LABELS: Record<string, string> = {
  'auth.login.success': 'Login Success',
  'auth.login.failure': 'Login Failure',
  'auth.logout': 'Logout',
  'user.created': 'User Created',
  'user.updated': 'User Updated',
  'user.deleted': 'User Deleted',
  'user.deactivated': 'User Deactivated',
  'user.reactivated': 'User Reactivated',
  'user.role.changed': 'Role Changed',
  'tenant.created': 'Tenant Created',
  'tenant.updated': 'Tenant Updated',
};

// Action badge colors
const ACTION_COLORS: Record<string, string> = {
  create: 'success',
  update: 'info',
  delete: 'danger',
  authenticate: 'primary',
};

export function AuditPage() {
  const { toast } = useToast();

  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);

  // Pagination
  const [page, setPage] = useState(0);
  const [limit] = useState(50);

  // Filters
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('');
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');

  // Expanded row
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Show stats panel
  const [showStats, setShowStats] = useState(false);

  // Fetch event types for filter dropdown
  const fetchEventTypes = useCallback(async () => {
    try {
      const data = await apiGet<{ event_types: string[] }>('/api/auth/audit/event-types');
      setEventTypes(data.event_types);
    } catch {
      // Ignore - event types are optional
    }
  }, []);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const data = await apiGet<AuditStats>('/api/auth/audit/stats');
      setStats(data);
    } catch {
      // Ignore - stats are optional
    }
  }, []);

  // Fetch events
  const fetchEvents = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      let url = `/api/auth/audit?limit=${limit}&offset=${page * limit}`;

      if (eventTypeFilter) {
        url += `&event_type=${encodeURIComponent(eventTypeFilter)}`;
      }
      if (fromDate) {
        url += `&from_date=${encodeURIComponent(fromDate)}T00:00:00`;
      }
      if (toDate) {
        url += `&to_date=${encodeURIComponent(toDate)}T23:59:59`;
      }

      const data = await apiGet<AuditListResponse>(url);
      setEvents(data.events);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit events');
    } finally {
      setLoading(false);
    }
  }, [page, limit, eventTypeFilter, fromDate, toDate]);

  useEffect(() => {
    fetchEventTypes();
    fetchStats();
  }, [fetchEventTypes, fetchStats]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Export handlers
  const handleExport = async (format: 'csv' | 'json') => {
    try {
      let url = `/api/auth/audit/export?format=${format}`;
      if (fromDate) {
        url += `&from_date=${encodeURIComponent(fromDate)}T00:00:00`;
      }
      if (toDate) {
        url += `&to_date=${encodeURIComponent(toDate)}T23:59:59`;
      }

      // Trigger download
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `audit_events.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);

      toast.success(`Exported audit events as ${format.toUpperCase()}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed');
    }
  };

  // Clear filters
  const clearFilters = () => {
    setEventTypeFilter('');
    setFromDate('');
    setToDate('');
    setPage(0);
  };

  // Format date for display
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  // Format relative time
  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(dateStr);
  };

  // Get event type label
  const getEventTypeLabel = (eventType: string) => {
    return EVENT_TYPE_LABELS[eventType] || eventType;
  };

  // Get icon for event type
  const getEventIcon = (eventType: string) => {
    if (eventType.startsWith('auth.login')) return 'LogIn';
    if (eventType === 'auth.logout') return 'LogOut';
    if (eventType.startsWith('user.')) return 'User';
    if (eventType.startsWith('tenant.')) return 'Building2';
    return 'Activity';
  };

  // Get color class for event type
  const getEventColorClass = (eventType: string) => {
    if (eventType === 'auth.login.failure') return 'event-danger';
    if (eventType === 'auth.login.success') return 'event-success';
    if (eventType.includes('deleted') || eventType.includes('deactivated')) return 'event-warning';
    if (eventType.includes('created')) return 'event-success';
    return 'event-info';
  };

  const totalPages = Math.ceil(total / limit);
  const hasFilters = eventTypeFilter || fromDate || toDate;

  return (
    <div className="audit-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Shield" size={28} />
          <div>
            <h1>Audit Log</h1>
            <p className="page-description">
              Security events and activity history
            </p>
          </div>
        </div>

        <div className="header-actions">
          <button
            className={`btn btn-icon ${showStats ? 'active' : ''}`}
            onClick={() => setShowStats(!showStats)}
            title="Toggle statistics"
          >
            <Icon name="BarChart3" size={16} />
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleExport('csv')}
          >
            <Icon name="Download" size={16} />
            Export CSV
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleExport('json')}
          >
            <Icon name="FileJson" size={16} />
            Export JSON
          </button>
        </div>
      </header>

      {/* Statistics Panel */}
      {showStats && stats && (
        <div className="stats-panel">
          <div className="stat-card">
            <div className="stat-value">{stats.total_events.toLocaleString()}</div>
            <div className="stat-label">Total Events</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.events_today}</div>
            <div className="stat-label">Today</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.events_this_week}</div>
            <div className="stat-label">This Week</div>
          </div>
          <div className="stat-card warning">
            <div className="stat-value">{stats.failed_logins_today}</div>
            <div className="stat-label">Failed Logins Today</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="audit-filters">
        <select
          className="filter-select"
          value={eventTypeFilter}
          onChange={(e) => {
            setEventTypeFilter(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All Event Types</option>
          {eventTypes.map((type) => (
            <option key={type} value={type}>
              {getEventTypeLabel(type)}
            </option>
          ))}
        </select>

        <div className="date-filter">
          <Icon name="Calendar" size={16} />
          <input
            type="date"
            value={fromDate}
            onChange={(e) => {
              setFromDate(e.target.value);
              setPage(0);
            }}
            placeholder="From"
          />
          <span className="date-separator">to</span>
          <input
            type="date"
            value={toDate}
            onChange={(e) => {
              setToDate(e.target.value);
              setPage(0);
            }}
            placeholder="To"
          />
        </div>

        {hasFilters && (
          <button className="btn btn-text" onClick={clearFilters}>
            <Icon name="X" size={14} />
            Clear Filters
          </button>
        )}

        <button className="btn btn-icon" onClick={fetchEvents} title="Refresh">
          <Icon name="RefreshCw" size={16} />
        </button>
      </div>

      {/* Events List */}
      <main className="audit-content">
        {loading ? (
          <div className="audit-loading">
            <Icon name="Loader2" size={32} className="spin" />
            <span>Loading audit events...</span>
          </div>
        ) : error ? (
          <div className="audit-error">
            <Icon name="AlertCircle" size={32} />
            <span>{error}</span>
            <button className="btn btn-secondary" onClick={fetchEvents}>
              Retry
            </button>
          </div>
        ) : events.length > 0 ? (
          <>
            <div className="events-table">
              <div className="events-header">
                <div className="col-time">Time</div>
                <div className="col-event">Event</div>
                <div className="col-user">User</div>
                <div className="col-target">Target</div>
                <div className="col-ip">IP Address</div>
                <div className="col-expand"></div>
              </div>

              {events.map((event) => (
                <div key={event.id} className="event-row-wrapper">
                  <div
                    className={`event-row ${expandedId === event.id ? 'expanded' : ''} ${getEventColorClass(event.event_type)}`}
                    onClick={() => setExpandedId(expandedId === event.id ? null : event.id)}
                  >
                    <div className="col-time">
                      <span className="time-relative">{formatRelativeTime(event.created_at)}</span>
                      <span className="time-full">{formatDate(event.created_at)}</span>
                    </div>

                    <div className="col-event">
                      <Icon name={getEventIcon(event.event_type)} size={16} />
                      <span className="event-type">{getEventTypeLabel(event.event_type)}</span>
                      <span className={`action-badge ${ACTION_COLORS[event.action] || ''}`}>
                        {event.action}
                      </span>
                    </div>

                    <div className="col-user">
                      {event.user_email || (
                        <span className="text-muted">Anonymous</span>
                      )}
                    </div>

                    <div className="col-target">
                      {event.target_type && event.target_id ? (
                        <span className="target">
                          <span className="target-type">{event.target_type}</span>
                          <span className="target-id">{event.target_id.slice(0, 8)}...</span>
                        </span>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </div>

                    <div className="col-ip">
                      {event.ip_address || <span className="text-muted">-</span>}
                    </div>

                    <div className="col-expand">
                      <Icon
                        name={expandedId === event.id ? 'ChevronUp' : 'ChevronDown'}
                        size={16}
                      />
                    </div>
                  </div>

                  {expandedId === event.id && (
                    <div className="event-details">
                      <div className="details-grid">
                        <div className="detail-item">
                          <span className="detail-label">Event ID</span>
                          <span className="detail-value mono">{event.id}</span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">User ID</span>
                          <span className="detail-value mono">
                            {event.user_id || 'N/A'}
                          </span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">User Agent</span>
                          <span className="detail-value">
                            {event.user_agent || 'N/A'}
                          </span>
                        </div>
                        <div className="detail-item full-width">
                          <span className="detail-label">Details</span>
                          <pre className="detail-value mono">
                            {JSON.stringify(event.details, null, 2)}
                          </pre>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="btn btn-icon"
                  disabled={page === 0}
                  onClick={() => setPage(0)}
                >
                  <Icon name="ChevronsLeft" size={16} />
                </button>
                <button
                  className="btn btn-icon"
                  disabled={page === 0}
                  onClick={() => setPage(page - 1)}
                >
                  <Icon name="ChevronLeft" size={16} />
                </button>

                <span className="page-info">
                  Page {page + 1} of {totalPages} ({total} events)
                </span>

                <button
                  className="btn btn-icon"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage(page + 1)}
                >
                  <Icon name="ChevronRight" size={16} />
                </button>
                <button
                  className="btn btn-icon"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage(totalPages - 1)}
                >
                  <Icon name="ChevronsRight" size={16} />
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="audit-empty">
            <Icon name="Shield" size={48} />
            <h3>No audit events found</h3>
            <p>
              {hasFilters
                ? 'Try adjusting your filters'
                : 'Audit events will appear here as users interact with the system'}
            </p>
            {hasFilters && (
              <button className="btn btn-secondary" onClick={clearFilters}>
                Clear Filters
              </button>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
