/**
 * C2PAPanel - Display Content Credentials (C2PA) information
 */

import { Icon } from '../../../components/common/Icon';
import type { MediaAnalysis, C2PAManifest, C2PAAction } from '../types';
import { C2PA_VALIDATION_LABELS, C2PA_VALIDATION_COLORS } from '../types';

interface C2PAPanelProps {
  analysis: MediaAnalysis;
}

export function C2PAPanel({ analysis }: C2PAPanelProps) {
  const { c2pa_data } = analysis;

  if (!c2pa_data || !c2pa_data.has_manifest) {
    return (
      <div className="panel-empty">
        <Icon name="ShieldOff" size={48} />
        <p>No C2PA Content Credentials found</p>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
          This image does not contain Content Authenticity Initiative (CAI) credentials
        </p>
      </div>
    );
  }

  const activeManifest =
    c2pa_data.active_manifest_index !== null
      ? c2pa_data.manifests[c2pa_data.active_manifest_index]
      : c2pa_data.manifests[0];

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const getActionIcon = (action: string): string => {
    const actionLower = action.toLowerCase();
    if (actionLower.includes('create') || actionLower.includes('captured')) return 'Camera';
    if (actionLower.includes('edit') || actionLower.includes('modified')) return 'Edit3';
    if (actionLower.includes('crop') || actionLower.includes('resize')) return 'Crop';
    if (actionLower.includes('filter') || actionLower.includes('adjust')) return 'Sliders';
    if (actionLower.includes('publish') || actionLower.includes('export')) return 'Upload';
    if (actionLower.includes('sign')) return 'Key';
    return 'Activity';
  };

  const renderManifest = (manifest: C2PAManifest, index: number) => (
    <div key={index} className="c2pa-manifest">
      {/* Signer Information */}
      {manifest.signer && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="User" size={16} />
            <h4>Signed By</h4>
          </div>
          <div
            className={`c2pa-signer-card ${
              manifest.signer.validation_status !== 'valid' ? 'invalid' : ''
            }`}
          >
            <div
              className={`c2pa-signer-badge ${
                manifest.signer.validation_status !== 'valid' ? 'invalid' : ''
              }`}
            >
              <Icon
                name={manifest.signer.is_trusted ? 'ShieldCheck' : 'ShieldAlert'}
                size={24}
              />
            </div>
            <div className="c2pa-signer-info">
              <div className="c2pa-signer-name">{manifest.signer.name}</div>
              {manifest.signer.organization && (
                <div className="c2pa-signer-org">{manifest.signer.organization}</div>
              )}
              {manifest.signer.issued_date && (
                <div className="c2pa-signer-date">
                  Issued: {formatDate(manifest.signer.issued_date)}
                </div>
              )}
            </div>
            <div
              className="c2pa-validation-status"
              style={{
                backgroundColor: C2PA_VALIDATION_COLORS[manifest.signer.validation_status],
              }}
            >
              {C2PA_VALIDATION_LABELS[manifest.signer.validation_status]}
            </div>
          </div>

          {/* Trust Chain */}
          {manifest.signer.trust_chain && manifest.signer.trust_chain.length > 0 && (
            <div className="c2pa-trust-chain">
              <span className="trust-chain-label">Trust Chain:</span>
              {manifest.signer.trust_chain.map((cert, idx) => (
                <span key={idx} className="trust-chain-item">
                  {cert}
                  {idx < manifest.signer!.trust_chain.length - 1 && (
                    <Icon name="ChevronRight" size={12} />
                  )}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Manifest Info */}
      <div className="panel-section">
        <div className="panel-section-header">
          <Icon name="FileText" size={16} />
          <h4>Manifest Details</h4>
        </div>
        <div className="metadata-grid">
          {manifest.title && (
            <div className="metadata-item">
              <span className="metadata-label">Title</span>
              <span className="metadata-value">{manifest.title}</span>
            </div>
          )}
          {manifest.format && (
            <div className="metadata-item">
              <span className="metadata-label">Format</span>
              <span className="metadata-value">{manifest.format}</span>
            </div>
          )}
          {manifest.claim_generator && (
            <div className="metadata-item full-width">
              <span className="metadata-label">Generated By</span>
              <span className="metadata-value">{manifest.claim_generator}</span>
            </div>
          )}
          {manifest.signature_date && (
            <div className="metadata-item">
              <span className="metadata-label">Signed</span>
              <span className="metadata-value">{formatDate(manifest.signature_date)}</span>
            </div>
          )}
          {manifest.instance_id && (
            <div className="metadata-item full-width">
              <span className="metadata-label">Instance ID</span>
              <span className="metadata-value monospace" style={{ fontSize: '0.7rem' }}>
                {manifest.instance_id}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Actions History */}
      {manifest.actions && manifest.actions.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Activity" size={16} />
            <h4>Edit History ({manifest.actions.length} actions)</h4>
          </div>
          <div className="c2pa-actions-list">
            {manifest.actions.map((action: C2PAAction, idx: number) => (
              <div key={idx} className="c2pa-action-item">
                <div className="c2pa-action-icon">
                  <Icon name={getActionIcon(action.action) as any} size={14} />
                </div>
                <div className="c2pa-action-details">
                  <div className="c2pa-action-name">{action.action}</div>
                  <div className="c2pa-action-meta">
                    {action.software_agent && <span>{action.software_agent}</span>}
                    {action.when && <span> - {formatDate(action.when)}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ingredients (Parent Assets) */}
      {manifest.ingredients && manifest.ingredients.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Layers" size={16} />
            <h4>Source Assets ({manifest.ingredients.length})</h4>
          </div>
          <div className="c2pa-ingredients-list">
            {manifest.ingredients.map((ingredient, idx) => (
              <div key={idx} className="c2pa-ingredient-item">
                {ingredient.thumbnail && (
                  <img
                    src={ingredient.thumbnail}
                    alt={ingredient.title}
                    className="ingredient-thumb"
                  />
                )}
                <div className="ingredient-details">
                  <div className="ingredient-title">{ingredient.title}</div>
                  <div className="ingredient-meta">
                    <span>{ingredient.format}</span>
                    <span className="ingredient-relationship">{ingredient.relationship}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Assertions */}
      {manifest.assertions && manifest.assertions.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="CheckSquare" size={16} />
            <h4>Assertions ({manifest.assertions.length})</h4>
          </div>
          <div className="c2pa-assertions-list">
            {manifest.assertions.map((assertion, idx) => (
              <div key={idx} className="c2pa-assertion-item">
                <div className="assertion-label">{assertion.label}</div>
                {assertion.instance !== undefined && (
                  <span className="assertion-instance">#{assertion.instance}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="c2pa-panel">
      {/* Validation Status Banner */}
      <div
        className="c2pa-status-banner"
        style={{
          backgroundColor: C2PA_VALIDATION_COLORS[c2pa_data.validation_status],
        }}
      >
        <Icon
          name={c2pa_data.validation_status === 'valid' ? 'ShieldCheck' : 'ShieldAlert'}
          size={20}
        />
        <span>
          Content Credentials: {C2PA_VALIDATION_LABELS[c2pa_data.validation_status]}
        </span>
      </div>

      {/* Validation Errors */}
      {c2pa_data.validation_errors && c2pa_data.validation_errors.length > 0 && (
        <div className="c2pa-errors">
          {c2pa_data.validation_errors.map((error, idx) => (
            <div key={idx} className="c2pa-error-item">
              <Icon name="AlertCircle" size={14} />
              <span>{error}</span>
            </div>
          ))}
        </div>
      )}

      {/* Provenance Chain */}
      {c2pa_data.provenance_chain && c2pa_data.provenance_chain.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="GitBranch" size={16} />
            <h4>Provenance Chain</h4>
          </div>
          <div className="c2pa-provenance-chain">
            {c2pa_data.provenance_chain.map((step, idx) => (
              <div key={idx} className="provenance-step">
                <div className="provenance-marker">
                  <div className="provenance-dot" />
                  {idx < c2pa_data.provenance_chain.length - 1 && (
                    <div className="provenance-line" />
                  )}
                </div>
                <div className="provenance-content">{step}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Manifests */}
      {activeManifest && renderManifest(activeManifest, 0)}

      {/* Multiple Manifests Notice */}
      {c2pa_data.manifests.length > 1 && (
        <div className="c2pa-multiple-notice">
          <Icon name="Info" size={14} />
          <span>
            This image contains {c2pa_data.manifests.length} manifests. Showing active manifest.
          </span>
        </div>
      )}
    </div>
  );
}

export default C2PAPanel;
