/**
 * DashboardPage - Dashboard shard placeholder
 *
 * Phase 1: Placeholder with sample data
 * Phase 2+: Will use GenericShardPage with manifest-driven UI
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';

interface SystemStats {
  documents: number;
  entities: number;
  chunks: number;
  vectors: number;
}

interface ServiceStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'offline';
  latency?: number;
}

export function DashboardPage() {
  const { toast } = useToast();
  const navigate = useNavigate();

  // Placeholder data - in Phase 2, this will come from Frame API
  const [stats] = useState<SystemStats>({
    documents: 1247,
    entities: 8432,
    chunks: 45230,
    vectors: 45230,
  });

  const [services] = useState<ServiceStatus[]>([
    { name: 'PostgreSQL', status: 'healthy', latency: 12 },
    { name: 'Qdrant', status: 'healthy', latency: 8 },
    { name: 'Redis', status: 'healthy', latency: 2 },
    { name: 'LM Studio', status: 'degraded', latency: 245 },
  ]);

  return (
    <div className="dashboard-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="LayoutDashboard" size={28} />
          <div>
            <h1>Dashboard</h1>
            <p className="page-description">System monitoring and status overview</p>
          </div>
        </div>
      </header>

      {/* Stats Grid */}
      <section className="stats-grid">
        <div className="stat-card">
          <Icon name="FileText" size={24} className="stat-icon" />
          <div className="stat-content">
            <div className="stat-value">{stats.documents.toLocaleString()}</div>
            <div className="stat-label">Documents</div>
          </div>
        </div>
        <div className="stat-card">
          <Icon name="Users" size={24} className="stat-icon" />
          <div className="stat-content">
            <div className="stat-value">{stats.entities.toLocaleString()}</div>
            <div className="stat-label">Entities</div>
          </div>
        </div>
        <div className="stat-card">
          <Icon name="Layers" size={24} className="stat-icon" />
          <div className="stat-content">
            <div className="stat-value">{stats.chunks.toLocaleString()}</div>
            <div className="stat-label">Chunks</div>
          </div>
        </div>
        <div className="stat-card">
          <Icon name="Binary" size={24} className="stat-icon" />
          <div className="stat-content">
            <div className="stat-value">{stats.vectors.toLocaleString()}</div>
            <div className="stat-label">Vectors</div>
          </div>
        </div>
      </section>

      {/* Services Status */}
      <section className="services-section">
        <h2>
          <Icon name="Server" size={20} />
          Services
        </h2>
        <div className="services-grid">
          {services.map(service => (
            <div key={service.name} className={`service-card status-${service.status}`}>
              <div className="service-header">
                <span className="service-name">{service.name}</span>
                <span className={`status-badge ${service.status}`}>
                  {service.status}
                </span>
              </div>
              {service.latency && (
                <div className="service-latency">
                  {service.latency}ms
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Quick Actions */}
      <section className="actions-section">
        <h2>
          <Icon name="Zap" size={20} />
          Quick Actions
        </h2>
        <div className="actions-grid">
          <button
            className="action-card"
            onClick={() => toast('Ingest shard coming soon', 'info')}
          >
            <Icon name="Upload" size={24} />
            <span>Ingest Documents</span>
          </button>
          <button
            className="action-card"
            onClick={() => toast('Search shard coming soon', 'info')}
          >
            <Icon name="Search" size={24} />
            <span>Search</span>
          </button>
          <button
            className="action-card"
            onClick={() => navigate('/ach?view=new')}
          >
            <Icon name="Scale" size={24} />
            <span>New ACH Analysis</span>
          </button>
          <button
            className="action-card"
            onClick={() => toast('Export shard coming soon', 'info')}
          >
            <Icon name="Download" size={24} />
            <span>Export Data</span>
          </button>
        </div>
      </section>
    </div>
  );
}
