/**
 * DatabaseTab - Database operations and statistics
 */

import { useState } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useToast } from '../../../context/ToastContext';
import { useConfirm } from '../../../context/ConfirmContext';
import { useDatabase } from '../api';
import type { SchemaStats, TableInfo } from '../api';

// Format bytes to human readable
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

// Format number with commas
function formatNumber(num: number): string {
  return num.toLocaleString();
}

interface SchemaCardProps {
  schema: SchemaStats;
  onExpand: () => void;
  expanded: boolean;
  tables: TableInfo[];
  loadingTables: boolean;
}

function SchemaCard({ schema, onExpand, expanded, tables, loadingTables }: SchemaCardProps) {
  const shardName = schema.name.replace('arkham_', '');

  return (
    <div className="schema-card">
      <div className="schema-header" onClick={onExpand}>
        <div className="schema-info">
          <Icon name="Database" size={16} />
          <span className="schema-name">{shardName}</span>
          <code className="schema-full-name">{schema.name}</code>
        </div>
        <div className="schema-stats">
          <span className="stat">
            <Icon name="Table" size={14} />
            {schema.tables} tables
          </span>
          <span className="stat">
            <Icon name="Rows3" size={14} />
            {formatNumber(schema.rows)} rows
          </span>
          <span className="stat">
            <Icon name="HardDrive" size={14} />
            {formatBytes(schema.size_bytes)}
          </span>
        </div>
        <Icon name={expanded ? 'ChevronUp' : 'ChevronDown'} size={18} />
      </div>

      {expanded && (
        <div className="schema-details">
          {loadingTables ? (
            <div className="loading-tables">
              <Icon name="Loader2" size={16} className="spin" />
              <span>Loading tables...</span>
            </div>
          ) : tables.length === 0 ? (
            <div className="no-tables">No tables found</div>
          ) : (
            <table className="tables-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Rows</th>
                  <th>Size</th>
                  <th>Last Vacuum</th>
                  <th>Last Analyze</th>
                </tr>
              </thead>
              <tbody>
                {tables.map((table) => (
                  <tr key={table.name}>
                    <td>
                      <code>{table.name}</code>
                    </td>
                    <td>{formatNumber(table.row_count)}</td>
                    <td>{formatBytes(table.size_bytes)}</td>
                    <td className="date-cell">
                      {table.last_vacuum
                        ? new Date(table.last_vacuum).toLocaleDateString()
                        : <span className="never">Never</span>}
                    </td>
                    <td className="date-cell">
                      {table.last_analyze
                        ? new Date(table.last_analyze).toLocaleDateString()
                        : <span className="never">Never</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export function DatabaseTab() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const { info, stats, loading, error, refresh, runMigrations, resetDatabase, vacuumDatabase, getTableInfo } = useDatabase();
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [operating, setOperating] = useState<string | null>(null);
  const [expandedSchema, setExpandedSchema] = useState<string | null>(null);
  const [tableInfo, setTableInfo] = useState<Record<string, TableInfo[]>>({});
  const [loadingTables, setLoadingTables] = useState<string | null>(null);

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

  const handleExpandSchema = async (schemaName: string) => {
    if (expandedSchema === schemaName) {
      setExpandedSchema(null);
      return;
    }

    setExpandedSchema(schemaName);

    // Load table info if not already loaded
    if (!tableInfo[schemaName]) {
      setLoadingTables(schemaName);
      const tables = await getTableInfo(schemaName);
      setTableInfo(prev => ({ ...prev, [schemaName]: tables }));
      setLoadingTables(null);
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
      {/* Status Section */}
      <section className="status-section">
        <h3>
          <Icon name="Database" size={18} />
          Database Status
          <button className="btn-icon btn-refresh" onClick={refresh} title="Refresh">
            <Icon name="RefreshCw" size={16} />
          </button>
        </h3>
        <div className="config-card">
          <div className="config-header">
            <span className={`status-badge ${info?.available ? 'success' : 'error'}`}>
              {info?.available ? 'Connected' : 'Disconnected'}
            </span>
            {stats?.database_size_bytes !== undefined && (
              <span className="db-size">
                <Icon name="HardDrive" size={14} />
                {formatBytes(stats.database_size_bytes)}
              </span>
            )}
          </div>
          <div className="config-details">
            <div className="config-row">
              <span className="config-label">Connection:</span>
              <code className="config-value">{info?.url || 'Not connected'}</code>
            </div>
            {stats && (
              <>
                <div className="config-row">
                  <span className="config-label">Total Tables:</span>
                  <span className="config-value">{stats.total_tables ?? 0}</span>
                </div>
                <div className="config-row">
                  <span className="config-label">Total Rows:</span>
                  <span className="config-value">{formatNumber(stats.total_rows ?? 0)}</span>
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      {/* Schemas Section */}
      {stats?.schemas && stats.schemas.length > 0 && (
        <section className="schemas-section">
          <h3>
            <Icon name="Layers" size={18} />
            Schemas
            <span className="schema-count">{stats.schemas.length} schemas</span>
          </h3>
          <div className="schemas-list">
            {stats.schemas.map((schema) => (
              <SchemaCard
                key={schema.name}
                schema={schema}
                expanded={expandedSchema === schema.name}
                onExpand={() => handleExpandSchema(schema.name)}
                tables={tableInfo[schema.name] || []}
                loadingTables={loadingTables === schema.name}
              />
            ))}
          </div>
        </section>
      )}

      {/* Operations Section */}
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

      {/* Danger Zone */}
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

      {/* Result Section */}
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
