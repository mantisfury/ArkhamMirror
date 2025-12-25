import { useHealth } from '../hooks/useApi'

function ServiceCard({
  title,
  available,
  info
}: {
  title: string
  available: boolean
  info?: Record<string, any> | null
}) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">{title}</span>
        <span className={`status-badge ${available ? 'available' : 'unavailable'}`}>
          {available ? 'Available' : 'Unavailable'}
        </span>
      </div>
      {info && (
        <dl className="card-content">
          {Object.entries(info).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { health, loading, error } = useHealth()

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading services...
      </div>
    )
  }

  if (error) {
    return (
      <div className="card" style={{ borderColor: 'var(--error)' }}>
        <div className="card-header">
          <span className="card-title">Error</span>
          <span className="status-badge unavailable">Failed</span>
        </div>
        <p className="card-content">{error}</p>
        <p className="card-content" style={{ marginTop: '1rem' }}>
          Make sure the Frame is running on port 8100.
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <h2>Dashboard Overview</h2>
        <p>Monitor the health of all ArkhamFrame services</p>
      </div>

      <div className="card-grid">
        <ServiceCard
          title="Database"
          available={health?.database.available ?? false}
          info={health?.database.info}
        />
        <ServiceCard
          title="Vector Store"
          available={health?.vectors.available ?? false}
          info={health?.vectors.info}
        />
        <ServiceCard
          title="LLM Service"
          available={health?.llm.available ?? false}
          info={health?.llm.info}
        />
        <ServiceCard
          title="Workers (Redis)"
          available={health?.workers.available ?? false}
          info={
            health?.workers.info
              ? { queues: health.workers.info.length }
              : null
          }
        />
        <ServiceCard
          title="Event Bus"
          available={health?.events.available ?? false}
        />
      </div>

      {health?.workers.info && health.workers.info.length > 0 && (
        <div className="section">
          <h3 className="section-title">Queue Status</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Queue</th>
                  <th>Pending</th>
                  <th>Active</th>
                  <th>Completed</th>
                  <th>Failed</th>
                </tr>
              </thead>
              <tbody>
                {health.workers.info.map((q: any) => (
                  <tr key={q.name}>
                    <td><strong>{q.name}</strong></td>
                    <td>{q.pending}</td>
                    <td>{q.active}</td>
                    <td style={{ color: 'var(--success)' }}>{q.completed}</td>
                    <td style={{ color: q.failed > 0 ? 'var(--error)' : 'inherit' }}>
                      {q.failed}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
