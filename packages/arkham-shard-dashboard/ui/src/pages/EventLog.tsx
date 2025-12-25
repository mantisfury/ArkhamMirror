import { useEvents } from '../hooks/useApi'

export default function EventLog() {
  const { events, loading, refresh } = useEvents()

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading events...
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <h2>Event Log</h2>
        <p>View recent system events from the EventBus</p>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <button className="btn btn-secondary" onClick={refresh}>
          Refresh
        </button>
      </div>

      {events.length === 0 ? (
        <div className="card">
          <div className="card-header">
            <span className="card-title">No Events</span>
          </div>
          <p className="card-content">
            No events have been recorded yet. Events will appear here as the system processes documents and performs operations.
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
                <tr key={idx}>
                  <td style={{ whiteSpace: 'nowrap', fontFamily: 'monospace' }}>
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </td>
                  <td>
                    <code style={{
                      background: 'var(--bg-secondary)',
                      padding: '0.25rem 0.5rem',
                      borderRadius: '0.25rem'
                    }}>
                      {event.event_type}
                    </code>
                  </td>
                  <td>{event.source}</td>
                  <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {JSON.stringify(event.payload)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
