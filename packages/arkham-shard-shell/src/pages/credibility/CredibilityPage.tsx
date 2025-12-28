/**
 * CredibilityPage - Source credibility assessment and scoring
 *
 * Displays credibility assessments with score visualization,
 * factor breakdown, and history tracking.
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import './CredibilityPage.css';

// Types
interface CredibilityFactor {
  factor_type: string;
  weight: number;
  score: number;
  notes: string | null;
}

interface Assessment {
  id: string;
  source_type: string;
  source_id: string;
  score: number;
  confidence: number;
  level: string;
  factors: CredibilityFactor[];
  assessed_by: string;
  assessor_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

interface Statistics {
  total_assessments: number;
  by_source_type: Record<string, number>;
  by_level: Record<string, number>;
  by_method: Record<string, number>;
  avg_score: number;
  avg_confidence: number;
  unreliable_count: number;
  low_count: number;
  medium_count: number;
  high_count: number;
  verified_count: number;
  sources_assessed: number;
  avg_assessments_per_source: number;
}

const CREDIBILITY_LEVELS = [
  { id: 'unreliable', label: 'Unreliable', color: '#ef4444', range: '0-20' },
  { id: 'low', label: 'Low', color: '#f97316', range: '21-40' },
  { id: 'medium', label: 'Medium', color: '#eab308', range: '41-60' },
  { id: 'high', label: 'High', color: '#22c55e', range: '61-80' },
  { id: 'verified', label: 'Verified', color: '#10b981', range: '81-100' },
];

export function CredibilityPage() {
  const { toast } = useToast();
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const [selectedAssessment, setSelectedAssessment] = useState<Assessment | null>(null);
  const [showFactors, setShowFactors] = useState(true);

  // Fetch assessments with usePaginatedFetch
  const baseUrl = selectedLevel
    ? `/api/credibility/level/${selectedLevel}`
    : '/api/credibility/';

  const { items: assessments, loading, error, refetch } = usePaginatedFetch<Assessment>(
    baseUrl
  );

  // Fetch statistics
  const { data: stats } = useFetch<Statistics>('/api/credibility/stats');

  const getLevelColor = (level: string): string => {
    const levelConfig = CREDIBILITY_LEVELS.find(l => l.id === level);
    return levelConfig?.color || '#6b7280';
  };

  const getScoreColor = (score: number): string => {
    if (score <= 20) return '#ef4444';
    if (score <= 40) return '#f97316';
    if (score <= 60) return '#eab308';
    if (score <= 80) return '#22c55e';
    return '#10b981';
  };

  const handleAssessmentClick = useCallback((assessment: Assessment) => {
    setSelectedAssessment(assessment);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedAssessment(null);
  }, []);

  const handleDeleteAssessment = async (id: string) => {
    if (!confirm('Are you sure you want to delete this assessment?')) {
      return;
    }

    try {
      const response = await fetch(`/api/credibility/${id}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete assessment');
      }

      toast.success('Assessment deleted');
      refetch();
      if (selectedAssessment?.id === id) {
        setSelectedAssessment(null);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete assessment');
    }
  };

  const renderScoreGauge = (score: number) => {
    const color = getScoreColor(score);
    const percentage = score;

    return (
      <div className="score-gauge">
        <div className="gauge-track">
          <div
            className="gauge-fill"
            style={{
              width: `${percentage}%`,
              backgroundColor: color,
            }}
          />
        </div>
        <div className="gauge-value" style={{ color }}>
          {score}
        </div>
      </div>
    );
  };

  const renderFactorBreakdown = (factors: CredibilityFactor[]) => {
    if (factors.length === 0) {
      return <p className="no-factors">No factors recorded</p>;
    }

    return (
      <div className="factors-list">
        {factors.map((factor, idx) => (
          <div key={idx} className="factor-item">
            <div className="factor-header">
              <span className="factor-type">{factor.factor_type}</span>
              <div className="factor-metrics">
                <span className="factor-weight">Weight: {(factor.weight * 100).toFixed(0)}%</span>
                <span className="factor-score" style={{ color: getScoreColor(factor.score) }}>
                  Score: {factor.score}
                </span>
              </div>
            </div>
            {factor.notes && (
              <p className="factor-notes">{factor.notes}</p>
            )}
            <div className="factor-bar">
              <div
                className="factor-bar-fill"
                style={{
                  width: `${factor.score}%`,
                  backgroundColor: getScoreColor(factor.score),
                }}
              />
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="credibility-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="ShieldCheck" size={28} />
          <div>
            <h1>Credibility</h1>
            <p className="page-description">Source credibility assessment and scoring</p>
          </div>
        </div>
      </header>

      <div className="credibility-layout">
        {/* Sidebar - Statistics and Filters */}
        <aside className="credibility-sidebar">
          {/* Statistics */}
          {stats && (
            <div className="stats-panel">
              <h3>Statistics</h3>
              <div className="stat-item">
                <Icon name="FileText" size={16} />
                <span className="stat-label">Total Assessments</span>
                <span className="stat-value">{stats.total_assessments}</span>
              </div>
              <div className="stat-item">
                <Icon name="Database" size={16} />
                <span className="stat-label">Sources Assessed</span>
                <span className="stat-value">{stats.sources_assessed}</span>
              </div>
              <div className="stat-item">
                <Icon name="TrendingUp" size={16} />
                <span className="stat-label">Avg Score</span>
                <span className="stat-value">{stats.avg_score.toFixed(1)}</span>
              </div>
              <div className="stat-item">
                <Icon name="Target" size={16} />
                <span className="stat-label">Avg Confidence</span>
                <span className="stat-value">{(stats.avg_confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          )}

          {/* Level Filter */}
          <div className="filter-panel">
            <h3>Filter by Level</h3>
            <button
              className={`filter-button ${!selectedLevel ? 'active' : ''}`}
              onClick={() => setSelectedLevel(null)}
            >
              <Icon name="List" size={16} />
              <span>All Assessments</span>
              {stats && <span className="filter-count">{stats.total_assessments}</span>}
            </button>
            {CREDIBILITY_LEVELS.map(level => (
              <button
                key={level.id}
                className={`filter-button ${selectedLevel === level.id ? 'active' : ''}`}
                onClick={() => setSelectedLevel(level.id)}
                style={{
                  borderLeftColor: selectedLevel === level.id ? level.color : 'transparent',
                }}
              >
                <div
                  className="level-indicator"
                  style={{ backgroundColor: level.color }}
                />
                <div className="filter-content">
                  <span className="filter-label">{level.label}</span>
                  <span className="filter-range">{level.range}</span>
                </div>
                {stats && (
                  <span className="filter-count">
                    {stats.by_level[level.id] || 0}
                  </span>
                )}
              </button>
            ))}
          </div>
        </aside>

        {/* Main Content */}
        <main className="credibility-content">
          {loading ? (
            <div className="content-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading assessments...</span>
            </div>
          ) : error ? (
            <div className="content-error">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load assessments</span>
              <button className="btn btn-secondary" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : assessments.length === 0 ? (
            <div className="content-empty">
              <Icon name="ShieldAlert" size={48} />
              <span>No credibility assessments found</span>
              {selectedLevel && (
                <button
                  className="btn btn-secondary"
                  onClick={() => setSelectedLevel(null)}
                >
                  Clear Filter
                </button>
              )}
            </div>
          ) : (
            <div className="assessments-container">
              {/* Assessment List */}
              <div className="assessments-list">
                {assessments.map(assessment => (
                  <div
                    key={assessment.id}
                    className={`assessment-card ${selectedAssessment?.id === assessment.id ? 'selected' : ''}`}
                    onClick={() => handleAssessmentClick(assessment)}
                  >
                    <div className="assessment-header">
                      <div className="assessment-source">
                        <Icon name="Database" size={16} />
                        <span className="source-type">{assessment.source_type}</span>
                        <span className="source-id">{assessment.source_id}</span>
                      </div>
                      <div
                        className="level-badge"
                        style={{ backgroundColor: getLevelColor(assessment.level) }}
                      >
                        {assessment.level}
                      </div>
                    </div>

                    {renderScoreGauge(assessment.score)}

                    <div className="assessment-meta">
                      <div className="meta-item">
                        <Icon name="Target" size={12} />
                        <span>Confidence: {(assessment.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <div className="meta-item">
                        <Icon name="User" size={12} />
                        <span>{assessment.assessed_by}</span>
                      </div>
                      <div className="meta-item">
                        <Icon name="Clock" size={12} />
                        <span>{new Date(assessment.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>

                    {assessment.notes && (
                      <p className="assessment-notes">{assessment.notes}</p>
                    )}
                  </div>
                ))}
              </div>

              {/* Assessment Detail Panel */}
              {selectedAssessment && (
                <div className="assessment-detail">
                  <div className="detail-header">
                    <h3>Assessment Details</h3>
                    <button
                      className="close-btn"
                      onClick={handleCloseDetail}
                      title="Close"
                    >
                      <Icon name="X" size={16} />
                    </button>
                  </div>

                  <div className="detail-content">
                    {/* Score Section */}
                    <div className="detail-section">
                      <h4>Credibility Score</h4>
                      {renderScoreGauge(selectedAssessment.score)}
                      <div className="score-info">
                        <div className="info-row">
                          <span>Level:</span>
                          <span
                            className="level-value"
                            style={{ color: getLevelColor(selectedAssessment.level) }}
                          >
                            {selectedAssessment.level.toUpperCase()}
                          </span>
                        </div>
                        <div className="info-row">
                          <span>Confidence:</span>
                          <span>{(selectedAssessment.confidence * 100).toFixed(1)}%</span>
                        </div>
                      </div>
                    </div>

                    {/* Source Section */}
                    <div className="detail-section">
                      <h4>Source Information</h4>
                      <div className="info-row">
                        <span>Type:</span>
                        <span>{selectedAssessment.source_type}</span>
                      </div>
                      <div className="info-row">
                        <span>ID:</span>
                        <span className="monospace">{selectedAssessment.source_id}</span>
                      </div>
                    </div>

                    {/* Factors Section */}
                    <div className="detail-section">
                      <div className="section-header">
                        <h4>Credibility Factors</h4>
                        <button
                          className="toggle-btn"
                          onClick={() => setShowFactors(!showFactors)}
                        >
                          <Icon name={showFactors ? 'ChevronUp' : 'ChevronDown'} size={16} />
                        </button>
                      </div>
                      {showFactors && renderFactorBreakdown(selectedAssessment.factors)}
                    </div>

                    {/* Assessment Meta */}
                    <div className="detail-section">
                      <h4>Assessment Meta</h4>
                      <div className="info-row">
                        <span>Method:</span>
                        <span>{selectedAssessment.assessed_by}</span>
                      </div>
                      {selectedAssessment.assessor_id && (
                        <div className="info-row">
                          <span>Assessor:</span>
                          <span className="monospace">{selectedAssessment.assessor_id}</span>
                        </div>
                      )}
                      <div className="info-row">
                        <span>Created:</span>
                        <span>{new Date(selectedAssessment.created_at).toLocaleString()}</span>
                      </div>
                      <div className="info-row">
                        <span>Updated:</span>
                        <span>{new Date(selectedAssessment.updated_at).toLocaleString()}</span>
                      </div>
                    </div>

                    {/* Notes Section */}
                    {selectedAssessment.notes && (
                      <div className="detail-section">
                        <h4>Notes</h4>
                        <p className="detail-notes">{selectedAssessment.notes}</p>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="detail-actions">
                      <button
                        className="btn btn-danger"
                        onClick={() => handleDeleteAssessment(selectedAssessment.id)}
                      >
                        <Icon name="Trash2" size={16} />
                        Delete Assessment
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
