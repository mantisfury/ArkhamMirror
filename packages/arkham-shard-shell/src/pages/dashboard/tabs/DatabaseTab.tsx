/**
 * DatabaseTab - Database operations and status
 */

import { useState } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useToast } from '../../../context/ToastContext';
import { useConfirm } from '../../../context/ConfirmContext';
import { useDatabase } from '../api';

export function DatabaseTab() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const { info, loading, error, refresh, runMigrations, resetDatabase, vacuumDatabase } = useDatabase();
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [operating, setOperating] = useState<string | null>(null);

  const handleAction = async (
    action: () => Promise<{ success: boolean; message: string }>,
    name: string
  ) => {
    setOperating(name);
    setResult(null);
    try {
      const res = await action();
      setResult({ success: res.success !== false, message: res.message || `${name} completed` });
      if (res.success !== false) {
        toast.success(res.message || `${name} completed`);
        refresh();
      } else {
        toast.error(res.message || `${name} failed`);
      }
    } catch (e) {
      const message = (e as Error).message;
      setResult({ success: false, message });
      toast.error(message);
    } finally {
      setOperating(null);
    }
  };

  const handleReset = async () => {
    const confirmed = await confirm({
      title: 'Reset Database',
      message: 'This will delete ALL data in the database. This action cannot be undone. Are you sure?',
      confirmLabel: 'Yes, Delete Everything',
      cancelLabel: 'Cancel',
      variant: 'danger',
    });

    if (confirmed) {
      await handleAction(() => resetDatabase(true), 'Reset');
    }
  };

  if (loading) {
    return (
      <div className="tab-loading">
        <Icon name="Loader2" size={32} className="spin" />
        <span>Loading database info...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-error">
        <Icon name="AlertCircle" size={32} />
        <span>Failed to load database info</span>
        <p className="error-detail">{error}</p>
      </div>
    );
  }

  return (
    <div className="database-tab">
      <section className="status-section">
        <h3>
          <Icon name="Database" size={18} />
          Database Status
        </h3>
        <div className="config-card">
          <div className="config-header">
            <span className={`status-badge ${info?.available ? 'success' : 'error'}`}>
              {info?.available ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <div className="config-details">
            <div className="config-row">
              <span className="config-label">Connection:</span>
              <code className="config-value">{info?.url || 'Not connected'}</code>
            </div>
            <div className="config-row">
              <span className="config-label">Schemas:</span>
              <span className="config-value">
                {info?.schemas?.length ? info.schemas.join(', ') : 'No arkham schemas found'}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="operations-section">
        <h3>
          <Icon name="Wrench" size={18} />
          Database Operations
        </h3>
        <div className="form-card">
          <div className="operations-grid">
            <div className="operation-item">
              <div className="operation-info">
                <strong>Run Migrations</strong>
                <p>Apply pending database schema migrations</p>
              </div>
              <button
                className="btn btn-primary"
                onClick={() => handleAction(runMigrations, 'Migrations')}
                disabled={operating !== null}
              >
                {operating === 'Migrations' ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Icon name="ArrowUpCircle" size={16} />
                    Run Migrations
                  </>
                )}
              </button>
            </div>

            <div className="operation-item">
              <div className="operation-info">
                <strong>VACUUM ANALYZE</strong>
                <p>Optimize database performance and update statistics</p>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() => handleAction(vacuumDatabase, 'VACUUM')}
                disabled={operating !== null}
              >
                {operating === 'VACUUM' ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Icon name="Sparkles" size={16} />
                    VACUUM ANALYZE
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="danger-section">
        <h3>
          <Icon name="AlertTriangle" size={18} />
          Danger Zone
        </h3>
        <div className="danger-card">
          <div className="danger-content">
            <div className="danger-info">
              <strong>Reset Database</strong>
              <p>Delete all data and recreate tables. This action cannot be undone.</p>
            </div>
            <button
              className="btn btn-danger"
              onClick={handleReset}
              disabled={operating !== null}
            >
              {operating === 'Reset' ? (
                <>
                  <Icon name="Loader2" size={16} className="spin" />
                  Resetting...
                </>
              ) : (
                <>
                  <Icon name="Trash2" size={16} />
                  Reset Database
                </>
              )}
            </button>
          </div>
        </div>
      </section>

      {result && (
        <section className="result-section">
          <div className={`result-card ${result.success ? 'success' : 'error'}`}>
            <div className="result-header">
              <Icon name={result.success ? 'CheckCircle' : 'XCircle'} size={20} />
              <span>Operation Result</span>
              <span className={`status-badge ${result.success ? 'success' : 'error'}`}>
                {result.success ? 'Success' : 'Failed'}
              </span>
            </div>
            <div className="result-content">
              <p>{result.message}</p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
