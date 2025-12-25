import { useState } from 'react'
import { useLLMConfig } from '../hooks/useApi'

export default function LLMConfig() {
  const { config, loading, error, updateConfig, testConnection } = useLLMConfig()
  const [endpoint, setEndpoint] = useState('')
  const [model, setModel] = useState('')
  const [testResult, setTestResult] = useState<{ success: boolean; response?: string; error?: string } | null>(null)
  const [testing, setTesting] = useState(false)

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testConnection()
      setTestResult(result)
    } catch (e) {
      setTestResult({ success: false, error: (e as Error).message })
    } finally {
      setTesting(false)
    }
  }

  const handleUpdate = async () => {
    await updateConfig(
      endpoint || undefined,
      model || undefined
    )
    setEndpoint('')
    setModel('')
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading LLM config...
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <h2>LLM Configuration</h2>
        <p>Configure the connection to your local LLM (LM Studio, Ollama, etc.)</p>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <span className="card-title">Current Configuration</span>
          <span className={`status-badge ${config?.available ? 'available' : 'unavailable'}`}>
            {config?.available ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <dl className="card-content">
          <dt>Endpoint</dt>
          <dd>{config?.endpoint || 'Not configured'}</dd>
          <dt>Model</dt>
          <dd>{config?.model || 'Not configured'}</dd>
        </dl>
      </div>

      <div className="panel">
        <h3 className="panel-title">Update Configuration</h3>
        <div className="form-group">
          <label className="form-label">Endpoint URL</label>
          <input
            type="text"
            className="form-input"
            placeholder={config?.endpoint || 'http://localhost:1234/v1'}
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">Model Name</label>
          <input
            type="text"
            className="form-input"
            placeholder={config?.model || 'local-model'}
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
        </div>
        <div className="btn-group">
          <button className="btn btn-primary" onClick={handleUpdate}>
            Update Config
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleTest}
            disabled={testing}
          >
            {testing ? 'Testing...' : 'Test Connection'}
          </button>
        </div>
      </div>

      {testResult && (
        <div
          className="card"
          style={{ borderColor: testResult.success ? 'var(--success)' : 'var(--error)' }}
        >
          <div className="card-header">
            <span className="card-title">Test Result</span>
            <span className={`status-badge ${testResult.success ? 'available' : 'unavailable'}`}>
              {testResult.success ? 'Success' : 'Failed'}
            </span>
          </div>
          <div className="card-content">
            {testResult.success ? (
              <p>LLM responded: "{testResult.response}"</p>
            ) : (
              <p style={{ color: 'var(--error)' }}>{testResult.error}</p>
            )}
          </div>
        </div>
      )}
    </>
  )
}
