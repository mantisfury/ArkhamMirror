/**
 * WorkersTab - Worker and queue management
 */

import { Icon } from '../../../components/common/Icon';
import { useQueues, useHealth } from '../api';

const QUEUE_DESCRIPTIONS: Record<string, string> = {
  default: 'General purpose queue for miscellaneous tasks',
  ingest: 'Document ingestion and file processing',
  ocr: 'Optical character recognition (PaddleOCR/Qwen-VL)',
  parse: 'Entity extraction and NER processing',
  embed: 'Embedding generation for semantic search',
};

export function WorkersTab() {
  const { queues, loading, error } = useQueues();
  const { health } = useHealth();

  const redisAvailable = health?.workers.available ?? false;

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

  return (
    <div className="workers-tab">
      <section className="status-section">
        <h3>
          <Icon name="Server" size={18} />
          Redis Connection
        </h3>
        <div className="config-card">
          <div className="config-header">
            <span className={`status-badge ${redisAvailable ? 'success' : 'error'}`}>
              {redisAvailable ? 'Connected' : 'Disconnected'}
            </span>
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
        <>
          <section className="queues-section">
            <h3>
              <Icon name="ListOrdered" size={18} />
              Queue Status
              <span className="refresh-hint">Auto-refreshes every 3s</span>
            </h3>
            {queues.length === 0 ? (
              <div className="empty-state">
                <Icon name="Inbox" size={32} />
                <p>No queues available</p>
              </div>
            ) : (
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
                        <td className={q.pending > 0 ? 'text-warning' : ''}>{q.pending}</td>
                        <td className={q.active > 0 ? 'text-info' : ''}>{q.active}</td>
                        <td className="text-success">{q.completed}</td>
                        <td className={q.failed > 0 ? 'text-error' : ''}>{q.failed}</td>
                        <td>
                          <span className={`status-badge ${q.active > 0 ? 'warning' : 'success'}`}>
                            {q.active > 0 ? 'Processing' : 'Idle'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="info-section">
            <h3>
              <Icon name="Info" size={18} />
              Queue Information
            </h3>
            <div className="info-card">
              <dl className="queue-descriptions">
                {Object.entries(QUEUE_DESCRIPTIONS).map(([name, description]) => (
                  <div key={name} className="queue-item">
                    <dt><code>{name}</code></dt>
                    <dd>{description}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
