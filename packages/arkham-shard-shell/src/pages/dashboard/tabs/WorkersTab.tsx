/**
 * WorkersTab - Worker and queue management with full controls
 */

import { useState } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useQueues, useWorkers, usePools, useHealth, workerActions, queueActions } from '../api';
import type { WorkerInfo, PoolInfo, QueueStats } from '../api';

// Pool type icons and colors
const POOL_TYPE_CONFIG: Record<string, { icon: string; color: string }> = {
  io: { icon: 'HardDrive', color: 'var(--color-info)' },
  cpu: { icon: 'Cpu', color: 'var(--color-warning)' },
  gpu: { icon: 'Zap', color: 'var(--color-success)' },
  llm: { icon: 'Brain', color: 'var(--color-accent)' },
  custom: { icon: 'Box', color: 'var(--text-secondary)' },
};

const QUEUE_DESCRIPTIONS: Record<string, string> = {
  'io-file': 'File I/O operations',
  'io-db': 'Database operations',
  'cpu-light': 'Light CPU tasks',
  'cpu-heavy': 'Heavy CPU processing',
  'cpu-ner': 'Named entity recognition',
  'cpu-extract': 'Content extraction',
  'cpu-image': 'Image processing',
  'cpu-archive': 'Archive handling',
  'gpu-paddle': 'PaddleOCR processing',
  'gpu-qwen': 'Qwen-VL vision tasks',
  'gpu-whisper': 'Whisper transcription',
  'gpu-embed': 'Embedding generation',
  'llm-enrich': 'LLM enrichment tasks',
  'llm-analysis': 'LLM analysis tasks',
  default: 'General purpose queue',
  ingest: 'Document ingestion',
  ocr: 'OCR processing',
  parse: 'Document parsing',
  embed: 'Embedding generation',
};

interface PoolCardProps {
  pool: PoolInfo;
  queueStats?: QueueStats;
  workers: WorkerInfo[];
  onStartWorker: () => void;
  onStopAll: () => void;
  onScale: (count: number) => void;
  onClearPending: () => void;
  onRetryFailed: () => void;
}

function PoolCard({
  pool,
  queueStats,
  workers,
  onStartWorker,
  onStopAll,
  onScale,
  onClearPending,
  onRetryFailed,
}: PoolCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const typeConfig = POOL_TYPE_CONFIG[pool.type] || POOL_TYPE_CONFIG.custom;
  const description = QUEUE_DESCRIPTIONS[pool.name] || 'Worker pool';

  const pending = queueStats?.pending || 0;
  const active = queueStats?.active || 0;
  const failed = queueStats?.failed || 0;
  const completed = queueStats?.completed || 0;

  return (
    <div className="pool-card">
      <div className="pool-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="pool-title">
          <Icon name={typeConfig.icon} size={18} style={{ color: typeConfig.color }} />
          <span className="pool-name">{pool.name}</span>
          <span className="pool-type-badge" style={{ borderColor: typeConfig.color }}>
            {pool.type.toUpperCase()}
          </span>
        </div>
        <div className="pool-stats">
          <span className="stat">
            <Icon name="Users" size={14} />
            {pool.current_workers}/{pool.max_workers}
          </span>
          {pending > 0 && (
            <span className="stat warning">
              <Icon name="Clock" size={14} />
              {pending}
            </span>
          )}
          {active > 0 && (
            <span className="stat info">
              <Icon name="Activity" size={14} />
              {active}
            </span>
          )}
          {failed > 0 && (
            <span className="stat error">
              <Icon name="AlertTriangle" size={14} />
              {failed}
            </span>
          )}
        </div>
        <Icon name={isExpanded ? 'ChevronUp' : 'ChevronDown'} size={18} />
      </div>

      {isExpanded && (
        <div className="pool-details">
          <p className="pool-description">{description}</p>
          {pool.vram_mb && (
            <p className="pool-vram">VRAM: {pool.vram_mb} MB</p>
          )}

          <div className="pool-controls">
            <div className="control-group">
              <label>Workers:</label>
              <div className="scale-controls">
                <button
                  className="btn-icon"
                  onClick={() => onScale(Math.max(0, pool.current_workers - 1))}
                  disabled={pool.current_workers === 0}
                  title="Decrease workers"
                >
                  <Icon name="Minus" size={16} />
                </button>
                <span className="worker-count">{pool.current_workers}</span>
                <button
                  className="btn-icon"
                  onClick={() => onScale(pool.current_workers + 1)}
                  disabled={pool.current_workers >= pool.max_workers}
                  title="Increase workers"
                >
                  <Icon name="Plus" size={16} />
                </button>
              </div>
            </div>

            <div className="control-buttons">
              <button
                className="btn btn-sm btn-primary"
                onClick={onStartWorker}
                disabled={pool.current_workers >= pool.max_workers}
              >
                <Icon name="Play" size={14} />
                Start
              </button>
              <button
                className="btn btn-sm btn-danger"
                onClick={onStopAll}
                disabled={pool.current_workers === 0}
              >
                <Icon name="Square" size={14} />
                Stop All
              </button>
            </div>
          </div>

          <div className="queue-actions">
            {pending > 0 && (
              <button className="btn btn-sm btn-warning" onClick={onClearPending}>
                <Icon name="Trash2" size={14} />
                Clear Pending ({pending})
              </button>
            )}
            {failed > 0 && (
              <button className="btn btn-sm btn-info" onClick={onRetryFailed}>
                <Icon name="RotateCcw" size={14} />
                Retry Failed ({failed})
              </button>
            )}
          </div>

          {workers.length > 0 && (
            <div className="workers-list">
              <h5>Active Workers</h5>
              <table className="workers-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Status</th>
                    <th>Jobs</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {workers.map((worker) => (
                    <WorkerRow key={worker.id} worker={worker} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {queueStats && (
            <div className="queue-summary">
              <span className="queue-stat">
                <Icon name="CheckCircle" size={14} />
                Completed: {completed}
              </span>
              <span className="queue-stat">
                <Icon name="XCircle" size={14} />
                Failed: {failed}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface WorkerRowProps {
  worker: WorkerInfo;
}

function WorkerRow({ worker }: WorkerRowProps) {
  const [stopping, setStopping] = useState(false);

  const handleStop = async () => {
    setStopping(true);
    await workerActions.stop(worker.id);
    setStopping(false);
  };

  const formatUptime = (seconds?: number) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  return (
    <tr>
      <td className="worker-id">
        <code>{worker.id.split('-').slice(-1)[0]}</code>
      </td>
      <td>
        <span className={`status-badge ${worker.status === 'processing' ? 'warning' : 'success'}`}>
          {worker.status}
        </span>
      </td>
      <td>
        <span className="jobs-stats">
          <span className="success">{worker.jobs_completed}</span>
          {worker.jobs_failed > 0 && (
            <span className="error">/ {worker.jobs_failed}</span>
          )}
        </span>
        <span className="uptime">{formatUptime(worker.uptime_seconds)}</span>
      </td>
      <td>
        <button
          className="btn-icon btn-danger"
          onClick={handleStop}
          disabled={stopping || worker.status === 'stopping'}
          title="Stop worker"
        >
          <Icon name={stopping ? 'Loader2' : 'Square'} size={14} className={stopping ? 'spin' : ''} />
        </button>
      </td>
    </tr>
  );
}

export function WorkersTab() {
  const { queues, refresh: refreshQueues } = useQueues();
  const { workers, refresh: refreshWorkers } = useWorkers();
  const { pools, loading, error, refresh: refreshPools } = usePools();
  const { health } = useHealth();
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const redisAvailable = health?.workers.available ?? false;

  const showMessage = (type: 'success' | 'error', text: string) => {
    setActionMessage({ type, text });
    setTimeout(() => setActionMessage(null), 3000);
  };

  const refreshAll = () => {
    refreshQueues();
    refreshWorkers();
    refreshPools();
  };

  const handleStartWorker = async (pool: string) => {
    const result = await workerActions.start(pool);
    if (result.success) {
      showMessage('success', `Started worker for ${pool}`);
      refreshAll();
    } else {
      showMessage('error', result.error || 'Failed to start worker');
    }
  };

  const handleStopAll = async (pool: string) => {
    const result = await workerActions.stopAll(pool);
    if (result.success) {
      showMessage('success', `Stopped ${result.count} workers in ${pool}`);
      refreshAll();
    } else {
      showMessage('error', result.error || 'Failed to stop workers');
    }
  };

  const handleScale = async (pool: string, count: number) => {
    const result = await workerActions.scale(pool, count);
    if (result.success) {
      showMessage('success', `Scaled ${pool} to ${count} workers`);
      refreshAll();
    } else {
      showMessage('error', result.error || 'Failed to scale workers');
    }
  };

  const handleClearPending = async (pool: string) => {
    const result = await queueActions.clear(pool, 'pending');
    if (result.success) {
      showMessage('success', `Cleared ${result.cleared} pending jobs from ${pool}`);
      refreshAll();
    } else {
      showMessage('error', result.error || 'Failed to clear queue');
    }
  };

  const handleRetryFailed = async (pool: string) => {
    const result = await queueActions.retryFailed(pool);
    if (result.success) {
      showMessage('success', `Retried ${result.count} failed jobs in ${pool}`);
      refreshAll();
    } else {
      showMessage('error', result.error || 'Failed to retry jobs');
    }
  };

  if (loading) {
    return (
      <div className="tab-loading">
        <Icon name="Loader2" size={32} className="spin" />
        <span>Loading worker info...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-error">
        <Icon name="AlertCircle" size={32} />
        <span>Failed to load worker info</span>
        <p className="error-detail">{error}</p>
      </div>
    );
  }

  // Build a map of queue stats by pool name
  const queueStatsMap = new Map(queues.map(q => [q.name, q]));

  // Group workers by pool
  const workersByPool = new Map<string, WorkerInfo[]>();
  workers.forEach(w => {
    const list = workersByPool.get(w.pool) || [];
    list.push(w);
    workersByPool.set(w.pool, list);
  });

  // Separate pools by type for better organization
  const poolsByType = new Map<string, PoolInfo[]>();
  pools.forEach(p => {
    const list = poolsByType.get(p.type) || [];
    list.push(p);
    poolsByType.set(p.type, list);
  });

  const typeOrder = ['io', 'cpu', 'gpu', 'llm', 'custom'];

  return (
    <div className="workers-tab">
      {actionMessage && (
        <div className={`action-message ${actionMessage.type}`}>
          <Icon name={actionMessage.type === 'success' ? 'CheckCircle' : 'AlertCircle'} size={16} />
          {actionMessage.text}
        </div>
      )}

      <section className="status-section">
        <h3>
          <Icon name="Server" size={18} />
          Redis Connection
          <button className="btn-icon btn-refresh" onClick={refreshAll} title="Refresh">
            <Icon name="RefreshCw" size={16} />
          </button>
        </h3>
        <div className="config-card">
          <div className="config-header">
            <span className={`status-badge ${redisAvailable ? 'success' : 'error'}`}>
              {redisAvailable ? 'Connected' : 'Disconnected'}
            </span>
            {redisAvailable && (
              <span className="worker-summary">
                {workers.length} worker{workers.length !== 1 ? 's' : ''} active
              </span>
            )}
          </div>
          {!redisAvailable && (
            <div className="config-details">
              <p className="error-text">
                Redis is not available. Make sure the Docker container is running.
              </p>
            </div>
          )}
        </div>
      </section>

      {redisAvailable && (
        <section className="pools-section">
          <h3>
            <Icon name="Layers" size={18} />
            Worker Pools
            <span className="refresh-hint">Auto-refreshes every 3s</span>
          </h3>

          {typeOrder.map(type => {
            const typePools = poolsByType.get(type);
            if (!typePools || typePools.length === 0) return null;

            const typeConfig = POOL_TYPE_CONFIG[type] || POOL_TYPE_CONFIG.custom;

            return (
              <div key={type} className="pool-type-group">
                <h4 className="pool-type-header" style={{ color: typeConfig.color }}>
                  <Icon name={typeConfig.icon} size={16} />
                  {type.toUpperCase()} Pools
                </h4>
                <div className="pools-grid">
                  {typePools.map(pool => (
                    <PoolCard
                      key={pool.name}
                      pool={pool}
                      queueStats={queueStatsMap.get(pool.name)}
                      workers={workersByPool.get(pool.name) || []}
                      onStartWorker={() => handleStartWorker(pool.name)}
                      onStopAll={() => handleStopAll(pool.name)}
                      onScale={(count) => handleScale(pool.name, count)}
                      onClearPending={() => handleClearPending(pool.name)}
                      onRetryFailed={() => handleRetryFailed(pool.name)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}
