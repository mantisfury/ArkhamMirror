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
  onExportMarkdown,
  onExportJSON,
  onExportPDF,
}: MilestonesSectionProps) {
  const getStatusLabel = (observed: number) => {
    switch (observed) {
      case 1:
        return { label: 'OBSERVED', color: 'success' };
      case -1:
        return { label: 'CONTRADICTED', color: 'danger' };
      default:
        return { label: 'PENDING', color: 'muted' };
    }
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
            const status = getStatusLabel(milestone.observed);
            return (
              <div
                key={milestone.id}
                className={`milestone-card milestone-${status.color}`}
              >
                <div className="milestone-content">
                  <div className="milestone-header">
                    <span className={`badge badge-${status.color}`}>
                      {status.label}
                    </span>
                    <span className="milestone-description">
                      {milestone.description}
                    </span>
                  </div>
                  {milestone.expected_by && (
                    <div className="milestone-date">
                      <Icon name="Calendar" size={12} />
                      <span>{milestone.expected_by.split('T')[0]}</span>
                    </div>
                  )}
                  {milestone.observation_notes && (
                    <p className="milestone-notes">
                      Notes: {milestone.observation_notes}
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
    </div>
  );
}
