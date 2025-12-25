/**
 * ACH AI Assistance Dialogs
 *
 * Dialogs for AI-powered suggestions and analysis.
 */

import { Icon } from '../../../components/common/Icon';
import type { ConsistencyRating, EvidenceType } from '../types';
import { RATING_COLORS, RATING_LABELS } from '../types';

// ============================================
// AI Hypothesis Suggestions Dialog
// ============================================

interface HypothesisSuggestion {
  title: string;
  description: string;
  rationale?: string;
  is_null?: boolean;
}

interface AIHypothesesDialogProps {
  suggestions: HypothesisSuggestion[];
  onAccept: (index: number) => void;
  onAcceptAll: () => void;
  onClose: () => void;
}

export function AIHypothesesDialog({
  suggestions,
  onAccept,
  onAcceptAll,
  onClose,
}: AIHypothesesDialogProps) {
  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog dialog-lg" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-title-with-icon">
            <Icon name="Sparkles" size={18} className="icon-violet" />
            <h2>AI Hypothesis Suggestions</h2>
          </div>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <p className="dialog-description">
          The AI has suggested these hypotheses based on your focus question.
          Accept the ones you want to add, or skip them.
        </p>

        <div className="suggestion-list">
          {suggestions.map((suggestion, index) => (
            <div key={index} className="suggestion-card">
              <div className="suggestion-content">
                <div className="suggestion-header">
                  <span className="suggestion-title">{suggestion.title}</span>
                  {suggestion.is_null && (
                    <span className="badge badge-soft">Null Hypothesis</span>
                  )}
                </div>
                <p className="suggestion-description">{suggestion.description}</p>
                {suggestion.rationale && (
                  <p className="suggestion-rationale">{suggestion.rationale}</p>
                )}
              </div>
              <div className="suggestion-actions">
                <button
                  className="btn btn-sm btn-success"
                  onClick={() => onAccept(index)}
                >
                  <Icon name="Check" size={12} />
                  Accept
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
          <button className="btn btn-success" onClick={onAcceptAll}>
            Accept All
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// AI Evidence Suggestions Dialog
// ============================================

interface EvidenceSuggestion {
  description: string;
  evidence_type: EvidenceType;
  source: string;
  importance?: string;
}

interface AIEvidenceDialogProps {
  suggestions: EvidenceSuggestion[];
  onAccept: (index: number) => void;
  onClose: () => void;
}

export function AIEvidenceDialog({
  suggestions,
  onAccept,
  onClose,
}: AIEvidenceDialogProps) {
  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog dialog-lg" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-title-with-icon">
            <Icon name="Sparkles" size={18} className="icon-violet" />
            <h2>AI Evidence Suggestions</h2>
          </div>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <p className="dialog-description">
          The AI suggests considering these evidence items.
          They are designed to help discriminate between your hypotheses.
        </p>

        <div className="suggestion-list scrollable">
          {suggestions.map((suggestion, index) => (
            <div key={index} className="suggestion-card">
              <div className="suggestion-content">
                <div className="suggestion-header">
                  <span className="badge badge-outline">{suggestion.evidence_type}</span>
                  <span className="suggestion-title">{suggestion.description}</span>
                </div>
                {suggestion.importance && (
                  <p className="suggestion-rationale">{suggestion.importance}</p>
                )}
                {suggestion.source && (
                  <p className="suggestion-source">Source: {suggestion.source}</p>
                )}
              </div>
              <div className="suggestion-actions">
                <button
                  className="btn btn-sm btn-success"
                  onClick={() => onAccept(index)}
                >
                  <Icon name="Plus" size={12} />
                  Add
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// AI Rating Suggestions Dialog
// ============================================

interface RatingSuggestion {
  hypothesis_id: string;
  hypothesis_label: string;
  rating: ConsistencyRating;
  explanation: string;
}

interface AIRatingsDialogProps {
  evidenceLabel: string;
  suggestions: RatingSuggestion[];
  onAccept: (hypothesisId: string, rating: ConsistencyRating) => void;
  onAcceptAll: () => void;
  onClose: () => void;
}

export function AIRatingsDialog({
  evidenceLabel,
  suggestions,
  onAccept,
  onAcceptAll,
  onClose,
}: AIRatingsDialogProps) {
  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog dialog-md" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-title-with-icon">
            <Icon name="Sparkles" size={18} className="icon-violet" />
            <h2>AI Rating Suggestions</h2>
          </div>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <p className="dialog-description">
          Suggested ratings for: <strong>{evidenceLabel}</strong>
        </p>

        <div className="rating-suggestion-list">
          {suggestions.map((suggestion) => (
            <div key={suggestion.hypothesis_id} className="rating-suggestion-row">
              <span className="badge badge-primary">{suggestion.hypothesis_label}</span>
              <span
                className="rating-badge"
                style={{ backgroundColor: RATING_COLORS[suggestion.rating] }}
              >
                {suggestion.rating}
              </span>
              <span className="rating-explanation">{suggestion.explanation}</span>
              <button
                className="btn btn-icon btn-sm btn-success"
                onClick={() => onAccept(suggestion.hypothesis_id, suggestion.rating)}
                title="Accept this rating"
              >
                <Icon name="Check" size={12} />
              </button>
            </div>
          ))}
        </div>

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
          <button className="btn btn-success" onClick={onAcceptAll}>
            Accept All
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// Devil's Advocate Challenge Dialog
// ============================================

interface Challenge {
  hypothesis_id: string;
  hypothesis_label: string;
  counter_argument: string;
  disproof_evidence: string;
  alternative_angle: string;
  weaknesses?: string[];
}

interface DevilsAdvocateDialogProps {
  challenges: Challenge[];
  onSaveToNotes: () => void;
  onClose: () => void;
}

export function DevilsAdvocateDialog({
  challenges,
  onSaveToNotes,
  onClose,
}: DevilsAdvocateDialogProps) {
  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog dialog-lg" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-title-with-icon">
            <Icon name="Swords" size={18} className="icon-orange" />
            <h2>Devil's Advocate Challenges</h2>
          </div>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <p className="dialog-description">
          The AI has generated challenges to your hypotheses.
          Consider these counter-arguments to strengthen your analysis.
        </p>

        <div className="challenge-list scrollable">
          {challenges.map((challenge, index) => (
            <div key={index} className="challenge-card">
              <div className="challenge-header">
                <span className="badge badge-primary">{challenge.hypothesis_label}</span>
                <span className="challenge-label">Challenge</span>
              </div>

              <div className="challenge-section">
                <span className="challenge-section-label text-red">Counter-argument:</span>
                <p>{challenge.counter_argument}</p>
              </div>

              <div className="challenge-section">
                <span className="challenge-section-label text-orange">Would be disproved if:</span>
                <p>{challenge.disproof_evidence}</p>
              </div>

              <div className="challenge-section">
                <span className="challenge-section-label text-violet">Alternative angle:</span>
                <p>{challenge.alternative_angle}</p>
              </div>

              {challenge.weaknesses && challenge.weaknesses.length > 0 && (
                <div className="challenge-section">
                  <span className="challenge-section-label">Weaknesses:</span>
                  <ul>
                    {challenge.weaknesses.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="dialog-actions">
          <button className="btn btn-success" onClick={onSaveToNotes}>
            <Icon name="Save" size={14} />
            Save to Notes
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// AI Milestone Suggestions Dialog
// ============================================

interface MilestoneSuggestion {
  hypothesis_id: string;
  hypothesis_label: string;
  description: string;
  expected_timeframe?: string;
  rationale?: string;
}

interface AIMilestonesDialogProps {
  suggestions: MilestoneSuggestion[];
  onAccept: (suggestion: MilestoneSuggestion) => void;
  onAcceptAll: () => void;
  onClose: () => void;
}

export function AIMilestonesDialog({
  suggestions,
  onAccept,
  onAcceptAll,
  onClose,
}: AIMilestonesDialogProps) {
  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog dialog-md" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-title-with-icon">
            <Icon name="Sparkles" size={18} className="icon-purple" />
            <h2>AI Milestone Suggestions</h2>
          </div>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <p className="dialog-description">
          Suggested observable milestones to track your hypotheses over time.
          Click 'Accept' to add any suggestion as a milestone.
        </p>

        <div className="suggestion-list scrollable">
          {suggestions.map((suggestion, index) => (
            <div key={index} className="suggestion-card">
              <div className="suggestion-content">
                <div className="suggestion-header">
                  <span className="badge badge-primary">{suggestion.hypothesis_label}</span>
                  {suggestion.expected_timeframe && (
                    <span className="badge badge-soft">{suggestion.expected_timeframe}</span>
                  )}
                </div>
                <p className="suggestion-description">{suggestion.description}</p>
                {suggestion.rationale && (
                  <p className="suggestion-rationale">{suggestion.rationale}</p>
                )}
              </div>
              <div className="suggestion-actions">
                <button
                  className="btn btn-sm btn-success"
                  onClick={() => onAccept(suggestion)}
                >
                  <Icon name="Plus" size={12} />
                  Accept
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
          <button className="btn btn-success" onClick={onAcceptAll}>
            Accept All
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// Analysis Insights Dialog
// ============================================

interface AnalysisInsights {
  insights: string;
  leading_hypothesis: string;
  key_evidence: string[];
  evidence_gaps: string[];
  cognitive_biases: string[];
  recommendations: string[];
}

interface InsightsDialogProps {
  insights: AnalysisInsights;
  onClose: () => void;
}

export function InsightsDialog({ insights, onClose }: InsightsDialogProps) {
  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog dialog-lg" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-title-with-icon">
            <Icon name="Brain" size={18} className="icon-violet" />
            <h2>AI Analysis Insights</h2>
          </div>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <div className="insights-content scrollable">
          <div className="insights-section">
            <h4>Overall Assessment</h4>
            <p>{insights.insights}</p>
          </div>

          <div className="insights-section highlight">
            <h4>Leading Hypothesis</h4>
            <p className="leading-hypothesis">{insights.leading_hypothesis}</p>
          </div>

          {insights.key_evidence.length > 0 && (
            <div className="insights-section">
              <h4>Key Evidence</h4>
              <ul>
                {insights.key_evidence.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {insights.evidence_gaps.length > 0 && (
            <div className="insights-section warning">
              <h4>Evidence Gaps</h4>
              <ul>
                {insights.evidence_gaps.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {insights.cognitive_biases.length > 0 && (
            <div className="insights-section danger">
              <h4>Potential Cognitive Biases</h4>
              <ul>
                {insights.cognitive_biases.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {insights.recommendations.length > 0 && (
            <div className="insights-section">
              <h4>Recommendations</h4>
              <ul>
                {insights.recommendations.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="dialog-actions">
          <button className="btn btn-primary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
