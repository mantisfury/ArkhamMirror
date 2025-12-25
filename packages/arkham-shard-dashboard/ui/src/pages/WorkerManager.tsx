import { useQueues, useHealth } from '../hooks/useApi'

export default function WorkerManager() {
  const { queues, loading } = useQueues()
  const { health } = useHealth()

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading worker info...
      </div>
    )
  }

  const redisAvailable = health?.workers.available ?? false

  return (
    <>
      <div className="page-header">
        <h2>Worker Management</h2>
        <p>Monitor and control background processing workers</p>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <span className="card-title">Redis Connection</span>
          <span className={`status-badge ${redisAvailable ? 'available' : 'unavailable'}`}>
            {redisAvailable ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        {!redisAvailable && (
          <p className="card-content" style={{ color: 'var(--error)' }}>
            Redis is not available. Make sure the Docker container is running.
          </p>
        )}
      </div>

      {redisAvailable && (
        <>
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
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {queues.map((q) => (
                    <tr key={q.name}>
                      <td><strong>{q.name}</strong></td>
                      <td>{q.pending}</td>
                      <td style={{ color: q.active > 0 ? 'var(--info)' : 'inherit' }}>
                        {q.active}
                      </td>
                      <td style={{ color: 'var(--success)' }}>{q.completed}</td>
                      <td style={{ color: q.failed > 0 ? 'var(--error)' : 'inherit' }}>
                        {q.failed}
                      </td>
                      <td>
                        <span
                          className={`status-badge ${q.active > 0 ? 'warning' : 'available'}`}
                        >
                          {q.active > 0 ? 'Processing' : 'Idle'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h3 className="panel-title">Queue Information</h3>
            <dl className="card-content">
              <dt>default</dt>
              <dd>General purpose queue for miscellaneous tasks</dd>
              <dt>ingest</dt>
              <dd>Document ingestion and file processing</dd>
              <dt>ocr</dt>
              <dd>Optical character recognition (PaddleOCR/Qwen-VL)</dd>
              <dt>parse</dt>
              <dd>Entity extraction and NER processing</dd>
              <dt>embed</dt>
              <dd>Embedding generation for semantic search</dd>
            </dl>
          </div>
        </>
      )}
    </>
  )
}
