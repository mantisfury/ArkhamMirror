/**
 * Scores Section (Step 6)
 *
 * Display hypothesis rankings and scores.
 */

import { Icon } from '../../../../components/common/Icon';
import type { HypothesisScore } from '../../types';

interface ScoresSectionProps {
  scores: HypothesisScore[];
  hypotheses?: { id: string; title: string }[];
  closeRaceWarning?: string;
  onRecalculate: () => void;
}

export function ScoresSection({
  scores,
  hypotheses = [],
  closeRaceWarning,
  onRecalculate: _onRecalculate,
}: ScoresSectionProps) {
  void _onRecalculate;
  const sortedScores = [...scores].sort((a, b) => a.rank - b.rank);

  // Helper to get hypothesis title - prefer from score, fallback to hypotheses list
  const getHypothesisTitle = (score: HypothesisScore): string => {
    if (score.hypothesis_title) return score.hypothesis_title;
    const hyp = hypotheses.find(h => h.id === score.hypothesis_id);
    return hyp?.title || `Hypothesis ${score.rank}`;
  };

  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="Target" size={18} className="icon-red" />
          <h3>Hypothesis Scores</h3>
        </div>
        <span className="section-hint">Lower = better fit</span>
      </div>

      {scores.length === 0 ? (
        <div className="empty-state">
          <p>Rate the matrix to see scores</p>
        </div>
      ) : (
        <div className="scores-list">
          {sortedScores.map((score) => {
            // Score bar percentage (capped at 100)
            const pct = Math.min(score.inconsistency_count * 20, 100);
            const colorClass =
              pct < 30 ? 'success' : pct < 60 ? 'warning' : 'danger';

            const title = getHypothesisTitle(score);
            return (
              <div key={score.hypothesis_id} className="score-row">
                <span
                  className={`rank-badge rank-${score.rank}`}
                  title={`#${score.rank}: ${title}`}
                >
                  #{score.rank}
                </span>
                <span className="score-hypothesis" title={title}>
                  {title}
                </span>
                <div className="score-bar-container">
                  <div
                    className={`score-bar score-bar-${colorClass}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="score-value" title={`${score.inconsistency_count} inconsistencies with the evidence`}>
                  {score.inconsistency_count}
                </span>
                <span className="score-description truncate">
                  inconsistencies
                </span>
              </div>
            );
          })}
        </div>
      )}

      {closeRaceWarning && (
        <div className="callout callout-warning">
          <Icon name="AlertTriangle" size={14} />
          {closeRaceWarning}
        </div>
      )}
    </div>
  );
}

// Consistency check result interface
interface ConsistencyCheck {
  passed: boolean;
  message: string;
}

interface ConsistencyChecksSectionProps {
  checks: ConsistencyCheck[];
}

export function ConsistencyChecksSection({ checks }: ConsistencyChecksSectionProps) {
  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="ShieldCheck" size={18} className="icon-cyan" />
          <h3>Consistency Checks</h3>
        </div>
      </div>

      <div className="consistency-checks">
        {checks.map((check, index) => (
          <div key={index} className="consistency-check-row">
            <Icon
              name={check.passed ? 'CheckCircle' : 'AlertCircle'}
              size={14}
              className={check.passed ? 'icon-success' : 'icon-warning'}
            />
            <span>{check.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
