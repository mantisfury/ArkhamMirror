/**
 * DeceptionChecklist - Renders a single MOM/POP/MOSES/EVE checklist
 *
 * Shows indicators with strength ratings and allows editing.
 */

import { useState } from 'react';
import { Icon } from '../../../components/common/Icon';
import type {
  DeceptionChecklist as ChecklistType,
  DeceptionChecklistType,
  DeceptionIndicator,
  IndicatorStrength,
} from './DeceptionTypes';
import { CHECKLIST_INFO, STRENGTH_COLORS } from './DeceptionTypes';

interface DeceptionChecklistProps {
  checklist: ChecklistType | null;
  checklistType: DeceptionChecklistType;
  standardIndicators: { id: string; question: string; description: string }[];
  onUpdateIndicator?: (indicator: DeceptionIndicator) => void;
  onAnalyzeWithLLM?: () => void;
  isAnalyzing?: boolean;
  readOnly?: boolean;
}

const STRENGTH_OPTIONS: { value: IndicatorStrength; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'weak', label: 'Weak' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'strong', label: 'Strong' },
  { value: 'conclusive', label: 'Conclusive' },
];

export function DeceptionChecklist({
  checklist,
  checklistType,
  standardIndicators,
  onUpdateIndicator,
  onAnalyzeWithLLM,
  isAnalyzing = false,
  readOnly = false,
}: DeceptionChecklistProps) {
  const [expandedIndicator, setExpandedIndicator] = useState<string | null>(null);
  const info = CHECKLIST_INFO[checklistType];

  // Use checklist indicators if available, otherwise create from standards
  const indicators: DeceptionIndicator[] = checklist?.indicators || standardIndicators.map(std => ({
    id: std.id,
    checklist: checklistType,
    question: std.question,
    answer: null,
    strength: 'none' as IndicatorStrength,
    confidence: 0,
    evidence_ids: [],
    notes: null,
  }));

  const completedCount = indicators.filter(i => i.strength !== 'none').length;
  const totalCount = indicators.length;
  const progressPercent = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  const handleStrengthChange = (indicator: DeceptionIndicator, strength: IndicatorStrength) => {
    if (onUpdateIndicator && !readOnly) {
      onUpdateIndicator({ ...indicator, strength });
    }
  };

  const handleNotesChange = (indicator: DeceptionIndicator, notes: string) => {
    if (onUpdateIndicator && !readOnly) {
      onUpdateIndicator({ ...indicator, notes: notes || null });
    }
  };

  const getRiskScoreClass = (score: number): string => {
    if (score <= 20) return 'risk-minimal';
    if (score <= 40) return 'risk-low';
    if (score <= 60) return 'risk-moderate';
    if (score <= 80) return 'risk-high';
    return 'risk-critical';
  };

  return (
    <div className="deception-checklist">
      {/* Checklist Header */}
      <div className="checklist-header" style={{ borderLeftColor: info.color }}>
        <div className="checklist-title">
          <Icon name={info.icon} size={20} style={{ color: info.color }} />
          <div>
            <h4>{info.name}</h4>
            <span className="checklist-fullname">{info.fullName}</span>
          </div>
        </div>
        <div className="checklist-meta">
          <span className="checklist-progress">
            {completedCount}/{totalCount} assessed
          </span>
          {checklist && (
            <span className={`checklist-score ${getRiskScoreClass(checklist.overall_score)}`}>
              Score: {checklist.overall_score}
            </span>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="checklist-progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${progressPercent}%`, backgroundColor: info.color }}
        />
      </div>

      {/* LLM Analysis Button */}
      {onAnalyzeWithLLM && !readOnly && (
        <button
          className="btn btn-secondary btn-sm analyze-btn"
          onClick={onAnalyzeWithLLM}
          disabled={isAnalyzing}
        >
          {isAnalyzing ? (
            <>
              <Icon name="Loader2" size={14} className="spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Icon name="Brain" size={14} />
              Analyze with AI
            </>
          )}
        </button>
      )}

      {/* Indicators List */}
      <div className="indicators-list">
        {indicators.map((indicator, idx) => {
          const isExpanded = expandedIndicator === indicator.id;
          const stdIndicator = standardIndicators.find(s => s.id === indicator.id);

          return (
            <div
              key={indicator.id}
              className={`indicator-item ${isExpanded ? 'expanded' : ''}`}
            >
              <div
                className="indicator-header"
                onClick={() => setExpandedIndicator(isExpanded ? null : indicator.id)}
              >
                <div className="indicator-number">{idx + 1}</div>
                <div className="indicator-question">
                  {indicator.question}
                </div>
                <div
                  className="indicator-strength"
                  style={{ backgroundColor: STRENGTH_COLORS[indicator.strength] }}
                >
                  {indicator.strength}
                </div>
                <Icon
                  name={isExpanded ? 'ChevronUp' : 'ChevronDown'}
                  size={16}
                  className="expand-icon"
                />
              </div>

              {isExpanded && (
                <div className="indicator-details">
                  {stdIndicator?.description && (
                    <p className="indicator-description">{stdIndicator.description}</p>
                  )}

                  {/* LLM Answer */}
                  {indicator.answer && (
                    <div className="indicator-answer">
                      <strong>Assessment:</strong> {indicator.answer}
                    </div>
                  )}

                  {!readOnly && (
                    <div className="indicator-controls">
                      <label className="control-label">Deception Indicator Strength:</label>
                      <div className="strength-buttons">
                        {STRENGTH_OPTIONS.map(opt => (
                          <button
                            key={opt.value}
                            className={`strength-btn ${indicator.strength === opt.value ? 'active' : ''}`}
                            style={{
                              borderColor: indicator.strength === opt.value ? STRENGTH_COLORS[opt.value] : undefined,
                              backgroundColor: indicator.strength === opt.value ? `${STRENGTH_COLORS[opt.value]}20` : undefined,
                            }}
                            onClick={() => handleStrengthChange(indicator, opt.value)}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>

                      <label className="control-label">Notes:</label>
                      <textarea
                        className="indicator-notes"
                        placeholder="Add notes or evidence references..."
                        value={indicator.notes || ''}
                        onChange={(e) => handleNotesChange(indicator, e.target.value)}
                        rows={2}
                      />
                    </div>
                  )}

                  {readOnly && indicator.notes && (
                    <div className="indicator-notes-readonly">
                      <strong>Notes:</strong> {indicator.notes}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary */}
      {checklist?.summary && (
        <div className="checklist-summary">
          <Icon name="FileText" size={14} />
          <p>{checklist.summary}</p>
        </div>
      )}
    </div>
  );
}
