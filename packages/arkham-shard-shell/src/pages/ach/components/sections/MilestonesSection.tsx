/**
 * Milestones Section (Step 8)
 *
 * Track future indicators and manage analysis export.
 */

import { Icon } from '../../../../components/common/Icon';

interface Milestone {
  id: string;
  description: string;
  hypothesis_id: string;
  hypothesis_label?: string;
  expected_by: string | null;
  observed: -1 | 0 | 1; // -1 = contradicted, 0 = pending, 1 = observed
  observation_notes: string;
  created_at: string;
}

interface MilestonesSectionProps {
  milestones: Milestone[];
  hypotheses: { id: string; title: string }[];
  aiAvailable: boolean;
  isAILoading: boolean;
  selectedHypothesis: string;
  onHypothesisSelect: (id: string) => void;
  onAISuggest: () => void;
  onAddMilestone: () => void;
  onEditMilestone: (id: string) => void;
  onDeleteMilestone: (id: string) => void;
  onUpdateMilestoneStatus: (id: string, status: -1 | 0 | 1) => void;
  onExportMarkdown: () => void;
  onExportJSON: () => void;
  onExportPDF: () => void;
}

export function MilestonesSection({
  milestones,
  hypotheses,
  aiAvailable,
  isAILoading,
  selectedHypothesis,
  onHypothesisSelect,
  onAISuggest,
  onAddMilestone,
  onEditMilestone,
  onDeleteMilestone,
  onUpdateMilestoneStatus,
  onExportMarkdown,
  onExportJSON,
  onExportPDF,
}: MilestonesSectionProps) {
  const getStatusInfo = (observed: number) => {
    switch (observed) {
      case 1:
        return { label: 'OBSERVED', color: 'success', bgColor: '#166534', borderColor: '#22c55e' };
      case -1:
        return { label: 'CONTRADICTED', color: 'danger', bgColor: '#991b1b', borderColor: '#ef4444' };
      default:
        return { label: 'PENDING', color: 'muted', bgColor: '#374151', borderColor: '#6b7280' };
    }
  };

  const getHypothesisLabel = (hypId: string): string => {
    const hyp = hypotheses.find(h => h.id === hypId);
    return hyp ? hyp.title : hypId.substring(0, 8);
  };

  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="Flag" size={18} className="icon-blue" />
          <h3>Future Indicators & Milestones</h3>
        </div>
        <div className="section-actions">
          {hypotheses.length > 0 && aiAvailable && (
            <div className="ai-suggest-group">
              <select
                value={selectedHypothesis}
                onChange={(e) => onHypothesisSelect(e.target.value)}
                className="select-sm"
              >
                <option value="all">All</option>
                {hypotheses.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.title}
                  </option>
                ))}
              </select>
              <button
                className="btn btn-sm btn-soft btn-purple"
                onClick={onAISuggest}
                disabled={isAILoading}
              >
                {isAILoading ? (
                  <Icon name="Loader2" size={12} className="spin" />
                ) : (
                  <Icon name="Sparkles" size={12} />
                )}
                AI Suggest
              </button>
            </div>
          )}
          <button className="btn btn-sm btn-soft" onClick={onAddMilestone}>
            <Icon name="Plus" size={14} />
            Add Milestone
          </button>
        </div>
      </div>

      <p className="section-description">
        Monitor these indicators to validate or disprove your conclusions over time.
      </p>

      {/* Milestones List */}
      <div className="milestones-list">
        {milestones.length === 0 ? (
          <div className="empty-state">
            <p>No milestones defined yet.</p>
          </div>
        ) : (
          milestones.map((milestone) => {
            const status = getStatusInfo(milestone.observed);
            return (
              <div
                key={milestone.id}
                className="milestone-card"
                style={{ borderLeftColor: status.borderColor }}
              >
                <div className="milestone-content">
                  <div className="milestone-header">
                    <div className="milestone-status-group">
                      <select
                        className="status-select"
                        value={milestone.observed}
                        onChange={(e) => onUpdateMilestoneStatus(milestone.id, parseInt(e.target.value) as -1 | 0 | 1)}
                        style={{
                          backgroundColor: status.bgColor,
                          borderColor: status.borderColor,
                        }}
                      >
                        <option value={0}>PENDING</option>
                        <option value={1}>OBSERVED</option>
                        <option value={-1}>CONTRADICTED</option>
                      </select>
                    </div>
                    <div className="milestone-text">
                      <span className="milestone-description">
                        {milestone.description}
                      </span>
                      {milestone.hypothesis_id && (
                        <span className="milestone-hypothesis">
                          <Icon name="Lightbulb" size={12} />
                          {getHypothesisLabel(milestone.hypothesis_id)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="milestone-meta">
                    {milestone.expected_by && (
                      <span className="milestone-date">
                        <Icon name="Calendar" size={12} />
                        Expected: {milestone.expected_by.split('T')[0]}
                      </span>
                    )}
                  </div>
                  {milestone.observation_notes && (
                    <p className="milestone-notes">
                      <Icon name="MessageSquare" size={12} />
                      {milestone.observation_notes}
                    </p>
                  )}
                </div>
                <div className="milestone-actions">
                  <button
                    className="btn btn-icon btn-sm"
                    onClick={() => onEditMilestone(milestone.id)}
                    title="Edit milestone"
                  >
                    <Icon name="Pencil" size={12} />
                  </button>
                  <button
                    className="btn btn-icon btn-sm btn-danger"
                    onClick={() => onDeleteMilestone(milestone.id)}
                    title="Delete milestone"
                  >
                    <Icon name="Trash2" size={12} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="divider" />

      {/* Export Section */}
      <div className="export-section">
        <h4>Final Report</h4>
        <div className="export-buttons">
          <button className="btn btn-outline" onClick={onExportMarkdown}>
            <Icon name="FileText" size={14} />
            Export Markdown
          </button>
          <button className="btn btn-outline" onClick={onExportJSON}>
            <Icon name="Braces" size={14} />
            Export JSON
          </button>
          <button className="btn btn-primary" onClick={onExportPDF}>
            <Icon name="FileType" size={14} />
            Export PDF
          </button>
        </div>
      </div>

      <style>{`
        .milestone-card {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          padding: 1rem;
          background: #1f2937;
          border: 1px solid #374151;
          border-left: 4px solid #6b7280;
          border-radius: 0.5rem;
          margin-bottom: 0.75rem;
        }
        .milestone-content {
          flex: 1;
          min-width: 0;
        }
        .milestone-header {
          display: flex;
          align-items: flex-start;
          gap: 1rem;
          margin-bottom: 0.5rem;
        }
        .milestone-status-group {
          flex-shrink: 0;
        }
        .status-select {
          padding: 0.375rem 0.75rem;
          font-size: 0.6875rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.025em;
          color: white;
          border: 1px solid;
          border-radius: 0.25rem;
          cursor: pointer;
          appearance: none;
          background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%239ca3af' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
          background-position: right 0.25rem center;
          background-repeat: no-repeat;
          background-size: 1.25em 1.25em;
          padding-right: 1.75rem;
        }
        .status-select:hover {
          filter: brightness(1.1);
        }
        .status-select:focus {
          outline: none;
          box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.5);
        }
        .milestone-text {
          flex: 1;
          min-width: 0;
        }
        .milestone-description {
          display: block;
          color: #f9fafb;
          font-size: 0.9375rem;
          line-height: 1.5;
          margin-bottom: 0.25rem;
        }
        .milestone-hypothesis {
          display: inline-flex;
          align-items: center;
          gap: 0.25rem;
          font-size: 0.75rem;
          color: #6366f1;
          background: rgba(99, 102, 241, 0.1);
          padding: 0.125rem 0.5rem;
          border-radius: 0.25rem;
        }
        .milestone-meta {
          display: flex;
          gap: 1rem;
          margin-bottom: 0.5rem;
        }
        .milestone-date {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          font-size: 0.75rem;
          color: #9ca3af;
        }
        .milestone-notes {
          display: flex;
          align-items: flex-start;
          gap: 0.375rem;
          font-size: 0.8125rem;
          color: #9ca3af;
          font-style: italic;
          margin: 0;
          padding: 0.5rem;
          background: rgba(0,0,0,0.2);
          border-radius: 0.25rem;
        }
        .milestone-actions {
          display: flex;
          gap: 0.25rem;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}
