/**
 * OverviewTab - Dashboard overview with service health and queue status
 */

import { Icon } from '../../../components/common/Icon';
import { useHealth } from '../api';
import type { QueueStats } from '../api';

interface ServiceCardProps {
  title: string;
  icon: string;
  available: boolean;
  info?: Record<string, unknown> | null;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function ServiceCard({ title, icon, available, info }: ServiceCardProps) {
  // Filter out complex nested objects to show only simple values
  const displayInfo = info
    ? Object.fromEntries(
        Object.entries(info).filter(([_key, value]) => {
          // Skip arrays and complex nested objects, keep primitives and simple objects
          if (Array.isArray(value)) return false;
          if (typeof value === 'object' && value !== null) {
            // Only keep objects with string/number/boolean values (like endpoint/model)
            const vals = Object.values(value);
            return vals.every(v => typeof v !== 'object');
          }
          return true;
        })
      )
    : null;

  return (
    <div className={`service-card ${available ? 'available' : 'unavailable'}`}>
      <div className="service-header">
        <Icon name={icon} size={20} />
        <span className="service-name">{title}</span>
        <span className={`status-badge ${available ? 'success' : 'error'}`}>
          {available ? 'Online' : 'Offline'}
        </span>
      </div>
      {displayInfo && Object.keys(displayInfo).length > 0 && (
        <div className="service-info">
          {Object.entries(displayInfo).map(([key, value]) => (
            <div key={key} className="info-row">
              <span className="info-key">{key}:</span>
              <span className="info-value">{formatValue(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface QueueTableProps {
  queues: QueueStats[];
}

function QueueTable({ queues }: QueueTableProps) {
  if (queues.length === 0) {
    return (
      <div className="empty-state">
        <Icon name="Inbox" size={32} />
        <p>No queue data available</p>
      </div>
    );
  }

  return (
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
          {queues.map((q) => (
            <tr key={q.name}>
              <td><strong>{q.name}</strong></td>
              <td>{q.pending}</td>
              <td className={q.active > 0 ? 'text-info' : ''}>{q.active}</td>
              <td className="text-success">{q.completed}</td>
              <td className={q.failed > 0 ? 'text-error' : ''}>{q.failed}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OverviewTab() {
  const { health, loading, error } = useHealth();

  if (loading) {
    return (
      <div className="tab-loading">
        <Icon name="Loader2" size={32} className="spin" />
        <span>Loading service health...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-error">
        <Icon name="AlertCircle" size={32} />
        <span>Failed to load health data</span>
        <p className="error-detail">{error}</p>
        <p className="error-hint">Make sure the Frame is running on port 8100.</p>
      </div>
    );
  }

  return (
    <div className="overview-tab">
      <section className="services-section">
        <h3>
          <Icon name="Server" size={18} />
          Services
        </h3>
        <div className="services-grid">
          <ServiceCard
            title="Database"
            icon="Database"
            available={health?.database.available ?? false}
            info={health?.database.info}
          />
          <ServiceCard
            title="Vector Store"
            icon="Box"
            available={health?.vectors.available ?? false}
            info={health?.vectors.info}
          />
          <ServiceCard
            title="LLM Service"
            icon="Brain"
            available={health?.llm.available ?? false}
            info={health?.llm.info}
          />
          <ServiceCard
            title="Workers (Redis)"
            icon="Cpu"
            available={health?.workers.available ?? false}
            info={health?.workers.info ? { queues: health.workers.info.length } : null}
          />
          <ServiceCard
            title="Event Bus"
            icon="Radio"
            available={health?.events.available ?? false}
          />
        </div>
      </section>

      {health?.workers.info && health.workers.info.length > 0 && (
        <section className="queues-section">
          <h3>
            <Icon name="ListOrdered" size={18} />
            Queue Status
          </h3>
          <QueueTable queues={health.workers.info} />
        </section>
      )}
    </div>
  );
}
