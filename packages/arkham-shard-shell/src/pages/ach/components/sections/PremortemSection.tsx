/**
 * Premortem Section
 *
 * Display and manage premortem analyses for hypotheses.
 * Premortem assumes a hypothesis is WRONG and generates failure modes.
 */

import { useState } from 'react';
import { Icon } from '../../../../components/common/Icon';
import type {
  PremortemAnalysis,
  PremortemListItem,
  FailureMode,
  FailureModeType,
} from '../../types';

const FAILURE_MODE_LABELS: Record<FailureModeType, string> = {
  misinterpretation: 'Misinterpretation',
  missed_evidence: 'Missed Evidence',
  failed_assumption: 'Failed Assumption',
  deception: 'Deception',
  alternative_explanation: 'Alternative Explanation',
};

const FAILURE_MODE_ICONS: Record<FailureModeType, string> = {
  misinterpretation: 'Eye',
  missed_evidence: 'Search',
  failed_assumption: 'AlertTriangle',
  deception: 'ShieldAlert',
  alternative_explanation: 'GitBranch',
};

const LIKELIHOOD_COLORS: Record<'low' | 'medium' | 'high', { bg: string; border: string; text: string }> = {
  low: { bg: '#166534', border: '#22c55e', text: '#86efac' },
  medium: { bg: '#854d0e', border: '#eab308', text: '#fde047' },
  high: { bg: '#991b1b', border: '#ef4444', text: '#fca5a5' },
};

interface PremortemSectionProps {
  premortems: PremortemListItem[];
  selectedPremortem: PremortemAnalysis | null;
  hypotheses: { id: string; title: string }[];
  aiAvailable: boolean;
  isLoading: boolean;
  onRunPremortem: (hypothesisId: string) => void;
  onSelectPremortem: (premortemId: string) => void;
  onDeletePremortem: (premortemId: string) => void;
  onConvertToHypothesis: (premortemId: string, failureModeId: string) => void;
  onConvertToMilestone: (premortemId: string, failureModeId: string) => void;
}

export function PremortemSection({
  premortems,
  selectedPremortem,
  hypotheses,
  aiAvailable,
  isLoading,
  onRunPremortem,
  onSelectPremortem,
  onDeletePremortem,
  onConvertToHypothesis,
  onConvertToMilestone,
}: PremortemSectionProps) {
  const [selectedHypothesis, setSelectedHypothesis] = useState<string>('');
  const [expandedPremortem, setExpandedPremortem] = useState<string | null>(null);

  const getVulnerabilityColor = (level: 'low' | 'medium' | 'high') => LIKELIHOOD_COLORS[level];

  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="AlertOctagon" size={18} className="icon-orange" />
          <h3>Premortem Analysis</h3>
        </div>
        <div className="section-actions">
          {hypotheses.length > 0 && aiAvailable && (
            <div className="ai-suggest-group">
              <select
                value={selectedHypothesis}
                onChange={(e) => setSelectedHypothesis(e.target.value)}
                className="select-sm"
              >
                <option value="">Select hypothesis...</option>
                {hypotheses.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.title}
                  </option>
                ))}
              </select>
              <button
                className="btn btn-sm btn-soft btn-orange"
                onClick={() => selectedHypothesis && onRunPremortem(selectedHypothesis)}
                disabled={isLoading || !selectedHypothesis}
              >
                {isLoading ? (
                  <Icon name="Loader2" size={12} className="spin" />
                ) : (
                  <Icon name="Sparkles" size={12} />
                )}
                Run Premortem
              </button>
            </div>
          )}
        </div>
      </div>

      <p className="section-description">
        Assume your hypothesis is WRONG. What would have caused this failure?
        Premortem analysis helps identify blind spots and hidden assumptions.
      </p>

      {/* Premortems List */}
      <div className="premortems-list">
        {premortems.length === 0 ? (
          <div className="empty-state">
            <Icon name="AlertOctagon" size={32} className="icon-muted" />
            <p>No premortem analyses yet.</p>
            <p className="text-sm text-muted">
              Select a hypothesis and run a premortem to identify potential failure modes.
            </p>
          </div>
        ) : (
          premortems.map((premortem) => {
            const isExpanded = expandedPremortem === premortem.id;
            const vulnColor = getVulnerabilityColor(premortem.overall_vulnerability);

            return (
              <div
                key={premortem.id}
                className={`premortem-card ${isExpanded ? 'expanded' : ''}`}
                style={{ borderLeftColor: vulnColor.border }}
              >
                <div
                  className="premortem-header"
                  onClick={() => {
                    setExpandedPremortem(isExpanded ? null : premortem.id);
                    if (!isExpanded) onSelectPremortem(premortem.id);
                  }}
                >
                  <div className="premortem-info">
                    <div className="premortem-title-row">
                      <Icon
                        name={isExpanded ? 'ChevronDown' : 'ChevronRight'}
                        size={16}
                        className="icon-muted"
                      />
                      <span className="premortem-hypothesis">
                        {premortem.hypothesis_title}
                      </span>
                      <span
                        className="vulnerability-badge"
                        style={{
                          backgroundColor: vulnColor.bg,
                          borderColor: vulnColor.border,
                          color: vulnColor.text,
                        }}
                      >
                        {premortem.overall_vulnerability.toUpperCase()} RISK
                      </span>
                    </div>
                    <div className="premortem-meta">
                      <span className="failure-count">
                        <Icon name="AlertTriangle" size={12} />
                        {premortem.failure_mode_count} failure modes
                      </span>
                      <span className="premortem-date">
                        {new Date(premortem.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <div className="premortem-actions">
                    <button
                      className="btn btn-icon btn-sm btn-danger"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeletePremortem(premortem.id);
                      }}
                      title="Delete premortem"
                    >
                      <Icon name="Trash2" size={12} />
                    </button>
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && selectedPremortem && selectedPremortem.id === premortem.id && (
                  <div className="premortem-content">
                    {/* Key Risks */}
                    {selectedPremortem.key_risks.length > 0 && (
                      <div className="premortem-subsection">
                        <h5>
                          <Icon name="AlertCircle" size={14} />
                          Key Risks
                        </h5>
                        <ul className="risk-list">
                          {selectedPremortem.key_risks.map((risk, i) => (
                            <li key={i}>{risk}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Failure Modes */}
                    <div className="premortem-subsection">
                      <h5>
                        <Icon name="GitBranch" size={14} />
                        Failure Modes
                      </h5>
                      <div className="failure-modes-list">
                        {selectedPremortem.failure_modes.map((fm) => (
                          <FailureModeCard
                            key={fm.id}
                            failureMode={fm}
                            premortemId={selectedPremortem.id}
                            onConvertToHypothesis={onConvertToHypothesis}
                            onConvertToMilestone={onConvertToMilestone}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Recommendations */}
                    {selectedPremortem.recommendations.length > 0 && (
                      <div className="premortem-subsection">
                        <h5>
                          <Icon name="Lightbulb" size={14} />
                          Recommendations
                        </h5>
                        <ul className="recommendations-list">
                          {selectedPremortem.recommendations.map((rec, i) => (
                            <li key={i}>{rec}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <style>{`
        .premortems-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }
        .premortem-card {
          background: #1f2937;
          border: 1px solid #374151;
          border-left: 4px solid #6b7280;
          border-radius: 0.5rem;
          overflow: hidden;
        }
        .premortem-card.expanded {
          border-color: #4b5563;
        }
        .premortem-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          padding: 1rem;
          cursor: pointer;
          transition: background 0.15s;
        }
        .premortem-header:hover {
          background: rgba(255,255,255,0.03);
        }
        .premortem-info {
          flex: 1;
          min-width: 0;
        }
        .premortem-title-row {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-bottom: 0.375rem;
        }
        .premortem-hypothesis {
          font-weight: 500;
          color: #f9fafb;
          font-size: 0.9375rem;
        }
        .vulnerability-badge {
          font-size: 0.625rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.025em;
          padding: 0.125rem 0.5rem;
          border: 1px solid;
          border-radius: 0.25rem;
        }
        .premortem-meta {
          display: flex;
          gap: 1rem;
          font-size: 0.75rem;
          color: #9ca3af;
          padding-left: 1.5rem;
        }
        .failure-count {
          display: flex;
          align-items: center;
          gap: 0.25rem;
        }
        .premortem-content {
          padding: 0 1rem 1rem;
          border-top: 1px solid #374151;
        }
        .premortem-subsection {
          margin-top: 1rem;
        }
        .premortem-subsection h5 {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.8125rem;
          font-weight: 600;
          color: #9ca3af;
          margin: 0 0 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.025em;
        }
        .risk-list, .recommendations-list {
          margin: 0;
          padding-left: 1.25rem;
        }
        .risk-list li, .recommendations-list li {
          color: #d1d5db;
          font-size: 0.875rem;
          margin-bottom: 0.375rem;
        }
        .failure-modes-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .btn-orange {
          background: rgba(234, 88, 12, 0.15);
          color: #fb923c;
          border: 1px solid rgba(234, 88, 12, 0.3);
        }
        .btn-orange:hover:not(:disabled) {
          background: rgba(234, 88, 12, 0.25);
        }
        .icon-orange {
          color: #fb923c;
        }
        .empty-state {
          text-align: center;
          padding: 2rem;
          color: #9ca3af;
        }
        .empty-state p {
          margin: 0.5rem 0 0;
        }
        .icon-muted {
          color: #6b7280;
        }
      `}</style>
    </div>
  );
}

// Failure Mode Card Component
interface FailureModeCardProps {
  failureMode: FailureMode;
  premortemId: string;
  onConvertToHypothesis: (premortemId: string, failureModeId: string) => void;
  onConvertToMilestone: (premortemId: string, failureModeId: string) => void;
}

function FailureModeCard({
  failureMode,
  premortemId,
  onConvertToHypothesis,
  onConvertToMilestone,
}: FailureModeCardProps) {
  const likelihoodColor = LIKELIHOOD_COLORS[failureMode.likelihood];
  const iconName = FAILURE_MODE_ICONS[failureMode.failure_type] || 'AlertTriangle';
  const typeLabel = FAILURE_MODE_LABELS[failureMode.failure_type] || failureMode.failure_type;

  return (
    <div className="failure-mode-card">
      <div className="fm-header">
        <div className="fm-type">
          <Icon name={iconName as any} size={14} />
          <span>{typeLabel}</span>
        </div>
        <span
          className="fm-likelihood"
          style={{
            backgroundColor: likelihoodColor.bg,
            borderColor: likelihoodColor.border,
            color: likelihoodColor.text,
          }}
        >
          {failureMode.likelihood}
        </span>
      </div>
      <p className="fm-description">{failureMode.description}</p>

      {failureMode.early_warning_indicator && (
        <div className="fm-indicator">
          <Icon name="Eye" size={12} />
          <span><strong>Watch for:</strong> {failureMode.early_warning_indicator}</span>
        </div>
      )}

      {failureMode.mitigation_action && (
        <div className="fm-mitigation">
          <Icon name="Shield" size={12} />
          <span><strong>Mitigation:</strong> {failureMode.mitigation_action}</span>
        </div>
      )}

      {!failureMode.converted_to && (
        <div className="fm-actions">
          {failureMode.failure_type === 'alternative_explanation' && (
            <button
              className="btn btn-xs btn-soft"
              onClick={() => onConvertToHypothesis(premortemId, failureMode.id)}
              title="Convert to new hypothesis"
            >
              <Icon name="Lightbulb" size={12} />
              New Hypothesis
            </button>
          )}
          {failureMode.early_warning_indicator && (
            <button
              className="btn btn-xs btn-soft"
              onClick={() => onConvertToMilestone(premortemId, failureMode.id)}
              title="Convert to milestone"
            >
              <Icon name="Flag" size={12} />
              Add Milestone
            </button>
          )}
        </div>
      )}

      {failureMode.converted_to && (
        <div className="fm-converted">
          <Icon name="Check" size={12} />
          Converted to {failureMode.converted_to}
        </div>
      )}

      <style>{`
        .failure-mode-card {
          background: rgba(0,0,0,0.2);
          border: 1px solid #374151;
          border-radius: 0.375rem;
          padding: 0.75rem;
        }
        .fm-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.5rem;
        }
        .fm-type {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          font-size: 0.75rem;
          font-weight: 500;
          color: #9ca3af;
        }
        .fm-likelihood {
          font-size: 0.625rem;
          font-weight: 600;
          text-transform: uppercase;
          padding: 0.125rem 0.375rem;
          border: 1px solid;
          border-radius: 0.25rem;
        }
        .fm-description {
          color: #e5e7eb;
          font-size: 0.875rem;
          margin: 0 0 0.5rem;
          line-height: 1.5;
        }
        .fm-indicator, .fm-mitigation {
          display: flex;
          align-items: flex-start;
          gap: 0.375rem;
          font-size: 0.8125rem;
          color: #9ca3af;
          margin-bottom: 0.375rem;
        }
        .fm-indicator strong, .fm-mitigation strong {
          color: #d1d5db;
        }
        .fm-actions {
          display: flex;
          gap: 0.5rem;
          margin-top: 0.75rem;
          padding-top: 0.75rem;
          border-top: 1px solid #374151;
        }
        .fm-converted {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          font-size: 0.75rem;
          color: #22c55e;
          margin-top: 0.5rem;
        }
        .btn-xs {
          padding: 0.25rem 0.5rem;
          font-size: 0.75rem;
        }
      `}</style>
    </div>
  );
}
