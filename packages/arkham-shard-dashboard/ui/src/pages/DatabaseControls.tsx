import { useState } from 'react'
import { useDatabase } from '../hooks/useApi'

export default function DatabaseControls() {
  const { info, loading, runMigrations, resetDatabase, vacuumDatabase } = useDatabase()
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)

  const handleAction = async (action: () => Promise<any>, name: string) => {
    setResult(null)
    try {
      const res = await action()
      setResult({ success: res.success !== false, message: res.message || `${name} completed` })
    } catch (e) {
      setResult({ success: false, message: (e as Error).message })
    }
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading database info...
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <h2>Database Controls</h2>
        <p>Manage PostgreSQL database operations</p>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <span className="card-title">Database Status</span>
          <span className={`status-badge ${info?.available ? 'available' : 'unavailable'}`}>
            {info?.available ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <dl className="card-content">
          <dt>Connection</dt>
          <dd>{info?.url || 'Not connected'}</dd>
          <dt>Schemas</dt>
          <dd>{info?.schemas?.length ? info.schemas.join(', ') : 'No arkham schemas found'}</dd>
        </dl>
      </div>

      <div className="panel">
        <h3 className="panel-title">Database Operations</h3>
        <div className="btn-group" style={{ marginBottom: '1rem' }}>
          <button
            className="btn btn-primary"
            onClick={() => handleAction(runMigrations, 'Migrations')}
          >
            Run Migrations
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleAction(vacuumDatabase, 'VACUUM')}
          >
            VACUUM ANALYZE
          </button>
        </div>

        <div style={{
          borderTop: '1px solid var(--border)',
          paddingTop: '1rem',
          marginTop: '1rem'
        }}>
          <h4 style={{ color: 'var(--error)', marginBottom: '0.5rem' }}>Danger Zone</h4>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
            This will delete ALL data in the database. This action cannot be undone.
          </p>
          {!confirmReset ? (
            <button
              className="btn btn-danger"
              onClick={() => setConfirmReset(true)}
            >
              Reset Database...
            </button>
          ) : (
            <div className="btn-group">
              <button
                className="btn btn-danger"
                onClick={() => {
                  handleAction(() => resetDatabase(true), 'Reset')
                  setConfirmReset(false)
                }}
              >
                Yes, Delete Everything
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setConfirmReset(false)}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {result && (
        <div
          className="card"
          style={{ borderColor: result.success ? 'var(--success)' : 'var(--error)' }}
        >
          <div className="card-header">
            <span className="card-title">Result</span>
            <span className={`status-badge ${result.success ? 'available' : 'unavailable'}`}>
              {result.success ? 'Success' : 'Failed'}
            </span>
          </div>
          <p className="card-content">{result.message}</p>
        </div>
      )}
    </>
  )
}
