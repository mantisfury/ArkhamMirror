/**
 * Sensitivity Analysis Section (Step 7)
 *
 * Analyze how vulnerable conclusions are to changes in evidence.
 */

import { useState } from 'react';
import { Icon } from '../../../../components/common/Icon';

interface SensitivityResult {
  evidence_id: string;
  evidence_label: string;
  impact: 'critical' | 'moderate' | 'minor';
  description: string;
}

interface SensitivitySectionProps {
  results: SensitivityResult[] | null;
  notes: string;
  isLoading: boolean;
  onRunAnalysis: () => void;
  onNotesChange: (notes: string) => void;
  onSaveNotes: () => void;
}

export function SensitivitySection({
  results,
  notes,
  isLoading,
  onRunAnalysis,
  onNotesChange,
  onSaveNotes,
}: SensitivitySectionProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="ShieldQuestion" size={18} className="icon-orange" />
          <h3>Sensitivity Analysis</h3>
        </div>
        <button
          className="btn btn-sm btn-soft btn-orange"
          onClick={onRunAnalysis}
          disabled={isLoading}
        >
          {isLoading ? (
            <>
              <Icon name="Loader2" size={14} className="spin" />
              Running...
            </>
          ) : (
            <>
              <Icon name="Zap" size={14} />
              Run Analysis
            </>
          )}
        </button>
      </div>

      <p className="section-description">
        Identify which evidence is most critical to your conclusion.
      </p>

      {/* Critical evidence warnings */}
      {results === null ? (
        <div className="callout callout-info">
          <Icon name="Info" size={14} />
          <div>
            Click <strong>Run Analysis</strong> to identify which evidence items are
            most critical to your conclusions.
          </div>
        </div>
      ) : results.length > 0 ? (
        <div className="sensitivity-results">
          {results.map((result) => (
            <div
              key={result.evidence_id}
              className={`callout callout-${
                result.impact === 'critical' ? 'danger' :
                result.impact === 'moderate' ? 'warning' : 'info'
              }`}
            >
              <Icon
                name={result.impact === 'critical' ? 'AlertTriangle' : 'Info'}
                size={14}
              />
              <div>
                <strong>{result.evidence_label}</strong>: {result.description}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="callout callout-success">
          <Icon name="CheckCircle" size={14} />
          <div>
            <strong>Analysis complete</strong>: Your conclusions appear robust.
            Removing uncertain evidence would not change the hypothesis rankings.
            Click "Run Analysis" to check again after making changes.
          </div>
        </div>
      )}

      <div className="divider" />

      <div className="notes-header">
        <h4>Key Assumptions & Notes</h4>
        <button
          className="btn btn-icon btn-sm"
          onClick={() => setExpanded(!expanded)}
          title={expanded ? 'Collapse notes' : 'Expand notes'}
        >
          <Icon name={expanded ? 'Minimize2' : 'Maximize2'} size={14} />
        </button>
      </div>

      <textarea
        className="sensitivity-notes"
        value={notes}
        onChange={(e) => onNotesChange(e.target.value)}
        onBlur={onSaveNotes}
        placeholder="What are your key assumptions? What evidence, if wrong, would change your conclusion?"
        style={{ minHeight: expanded ? '400px' : '120px' }}
      />
    </div>
  );
}
