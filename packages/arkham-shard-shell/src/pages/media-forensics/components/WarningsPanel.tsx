/**
 * WarningsPanel - Display metadata warnings and forensic findings
 */

import { Icon } from '../../../components/common/Icon';
import type { MediaAnalysis, ForensicFinding, FindingSeverity } from '../types';
import { SEVERITY_LABELS, SEVERITY_COLORS } from '../types';

interface WarningsPanelProps {
  analysis: MediaAnalysis;
}

export function WarningsPanel({ analysis }: WarningsPanelProps) {
  const { findings } = analysis;

  if (!findings || findings.length === 0) {
    return (
      <div className="panel-empty">
        <Icon name="CheckCircle" size={48} />
        <p>No warnings or findings detected</p>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
          The analysis did not identify any suspicious indicators in this image
        </p>
      </div>
    );
  }

  // Group findings by category
  const groupedFindings = findings.reduce(
    (acc, finding) => {
      if (!acc[finding.category]) {
        acc[finding.category] = [];
      }
      acc[finding.category].push(finding);
      return acc;
    },
    {} as Record<string, ForensicFinding[]>
  );

  // Sort findings by severity within each category
  const severityOrder: FindingSeverity[] = ['critical', 'high', 'medium', 'low', 'info'];
  Object.keys(groupedFindings).forEach((category) => {
    groupedFindings[category].sort(
      (a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity)
    );
  });

  const getCategoryIcon = (category: string): string => {
    switch (category) {
      case 'exif':
        return 'Camera';
      case 'c2pa':
        return 'ShieldCheck';
      case 'ela':
        return 'Layers';
      case 'sun_position':
        return 'Sun';
      case 'similar_images':
        return 'Images';
      default:
        return 'AlertTriangle';
    }
  };

  const getCategoryLabel = (category: string): string => {
    switch (category) {
      case 'exif':
        return 'EXIF Metadata';
      case 'c2pa':
        return 'Content Credentials';
      case 'ela':
        return 'Error Level Analysis';
      case 'sun_position':
        return 'Sun Position';
      case 'similar_images':
        return 'Similar Images';
      default:
        return 'General';
    }
  };

  const getSeverityIcon = (severity: FindingSeverity): string => {
    switch (severity) {
      case 'critical':
        return 'XCircle';
      case 'high':
        return 'AlertTriangle';
      case 'medium':
        return 'AlertCircle';
      case 'low':
        return 'Info';
      default:
        return 'HelpCircle';
    }
  };

  const formatDate = (dateStr: string): string => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  // Count by severity
  const severityCounts = findings.reduce(
    (acc, f) => {
      acc[f.severity] = (acc[f.severity] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="warnings-panel">
      {/* Summary */}
      <div className="warnings-summary">
        <div className="summary-total">
          <Icon name="AlertTriangle" size={20} />
          <span>
            {findings.length} finding{findings.length !== 1 ? 's' : ''} detected
          </span>
        </div>
        <div className="summary-breakdown">
          {severityOrder.map(
            (severity) =>
              severityCounts[severity] > 0 && (
                <span
                  key={severity}
                  className="severity-count"
                  style={{ color: SEVERITY_COLORS[severity] }}
                >
                  {severityCounts[severity]} {SEVERITY_LABELS[severity]}
                </span>
              )
          )}
        </div>
      </div>

      {/* Grouped Findings */}
      {Object.entries(groupedFindings).map(([category, categoryFindings]) => (
        <div key={category} className="panel-section">
          <div className="panel-section-header">
            <Icon name={getCategoryIcon(category) as any} size={16} />
            <h4>
              {getCategoryLabel(category)} ({categoryFindings.length})
            </h4>
          </div>
          <div className="findings-list">
            {categoryFindings.map((finding) => (
              <div
                key={finding.id}
                className={`finding-card severity-${finding.severity}`}
              >
                <div className="finding-header">
                  <div className="finding-title-row">
                    <Icon name={getSeverityIcon(finding.severity) as any} size={16} />
                    <span className="finding-title">{finding.title}</span>
                  </div>
                  <span className={`finding-severity severity-${finding.severity}`}>
                    {SEVERITY_LABELS[finding.severity]}
                  </span>
                </div>
                <p className="finding-description">{finding.description}</p>

                {/* Recommendation */}
                {finding.recommendation && (
                  <div className="finding-recommendation">
                    <Icon name="Lightbulb" size={14} />
                    <span>{finding.recommendation}</span>
                  </div>
                )}

                {/* Evidence */}
                {finding.evidence && Object.keys(finding.evidence).length > 0 && (
                  <div className="finding-evidence">
                    <details>
                      <summary>
                        <Icon name="Code" size={12} />
                        Evidence Details
                      </summary>
                      <pre>{JSON.stringify(finding.evidence, null, 2)}</pre>
                    </details>
                  </div>
                )}

                <div className="finding-meta">
                  <span className="finding-confidence">
                    <Icon name="Target" size={12} />
                    {(finding.confidence * 100).toFixed(0)}% confidence
                  </span>
                  <span className="finding-detection">
                    {finding.auto_detected ? (
                      <>
                        <Icon name="Cpu" size={12} />
                        Auto-detected
                      </>
                    ) : (
                      <>
                        <Icon name="User" size={12} />
                        Manual
                      </>
                    )}
                  </span>
                  <span className="finding-time">
                    <Icon name="Clock" size={12} />
                    {formatDate(finding.detected_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Legend */}
      <div className="severity-legend">
        <h5>Severity Legend</h5>
        <div className="legend-items">
          {severityOrder.map((severity) => (
            <div key={severity} className="legend-item">
              <div
                className="legend-color"
                style={{ backgroundColor: SEVERITY_COLORS[severity] }}
              />
              <span className="legend-label">{SEVERITY_LABELS[severity]}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default WarningsPanel;
