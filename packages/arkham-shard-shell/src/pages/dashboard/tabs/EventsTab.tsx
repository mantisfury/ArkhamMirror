/**
 * EventsTab - System event log viewer
 */

import { Icon } from '../../../components/common/Icon';
import { useEvents } from '../api';

export function EventsTab() {
  const { events, loading, error, refresh } = useEvents();

  if (loading) {
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
      <section className="events-section">
        <div className="section-header">
          <h3>
            <Icon name="ScrollText" size={18} />
            Event Log
            <span className="refresh-hint">Auto-refreshes every 5s</span>
          </h3>
          <button className="btn btn-secondary btn-sm" onClick={refresh}>
            <Icon name="RefreshCw" size={14} />
            Refresh
          </button>
        </div>

        {events.length === 0 ? (
          <div className="empty-state">
            <Icon name="Inbox" size={48} />
            <h4>No Events</h4>
            <p>
              No events have been recorded yet. Events will appear here as the system
              processes documents and performs operations.
            </p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>Source</th>
                  <th>Payload</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event, idx) => (
                  <tr key={`${event.timestamp}-${idx}`}>
                    <td className="time-cell">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </td>
                    <td>
                      <code className="event-type">{event.event_type}</code>
                    </td>
                    <td className="source-cell">{event.source}</td>
                    <td className="payload-cell">
                      <code className="payload-preview">
                        {JSON.stringify(event.payload)}
                      </code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
