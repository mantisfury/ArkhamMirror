/**
 * ELAViewer - Error Level Analysis side-by-side viewer with controls
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useToast } from '../../../context/ToastContext';
import * as api from '../api';
import type { MediaAnalysis, ELAResult } from '../types';

interface ELAViewerProps {
  analysis: MediaAnalysis;
  onRegenerate?: () => void;
}

export function ELAViewer({ analysis, onRegenerate }: ELAViewerProps) {
  const { toast } = useToast();
  const [elaResult, setElaResult] = useState<ELAResult | null>(analysis.ela_result);
  const [qualityLevel, setQualityLevel] = useState(95);
  const [generating, setGenerating] = useState(false);
  const [viewMode, setViewMode] = useState<'side-by-side' | 'ela-only' | 'overlay'>('side-by-side');

  const handleGenerateELA = useCallback(async () => {
    setGenerating(true);
    try {
      const response = await api.generateELA({
        analysis_id: analysis.id,
        quality_level: qualityLevel,
      });
      setElaResult(response.result);
      toast.success('ELA generated successfully');
      onRegenerate?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to generate ELA');
    } finally {
      setGenerating(false);
    }
  }, [analysis.id, qualityLevel, toast, onRegenerate]);

  const handleRegenerateELA = useCallback(async () => {
    setGenerating(true);
    try {
      const response = await api.regenerateELA(analysis.id, qualityLevel);
      setElaResult(response.result);
      toast.success('ELA regenerated with new quality level');
      onRegenerate?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to regenerate ELA');
    } finally {
      setGenerating(false);
    }
  }, [analysis.id, qualityLevel, toast, onRegenerate]);

  // No ELA yet
  if (!elaResult) {
    return (
      <div className="ela-container">
        <div className="panel-empty">
          <Icon name="Layers" size={48} />
          <p>Error Level Analysis not yet performed</p>
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)', marginBottom: '1rem' }}>
            ELA can help detect edited or manipulated regions in JPEG images
          </p>
        </div>

        <div className="ela-controls">
          <label>Quality Level:</label>
          <input
            type="range"
            min="70"
            max="100"
            value={qualityLevel}
            onChange={(e) => setQualityLevel(Number(e.target.value))}
            disabled={generating}
          />
          <span className="quality-value">{qualityLevel}%</span>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleGenerateELA}
          disabled={generating}
          style={{ alignSelf: 'center' }}
        >
          {generating ? (
            <>
              <Icon name="Loader2" size={16} className="spin" />
              Generating...
            </>
          ) : (
            <>
              <Icon name="Zap" size={16} />
              Generate ELA
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="ela-container">
      {/* Result Summary */}
      <div
        className={`ela-result-banner ${elaResult.is_potentially_edited ? 'warning' : 'clean'}`}
      >
        <Icon name={elaResult.is_potentially_edited ? 'AlertTriangle' : 'CheckCircle'} size={20} />
        <div className="ela-result-text">
          <span className="ela-result-title">
            {elaResult.is_potentially_edited
              ? 'Potential Editing Detected'
              : 'No Obvious Manipulation'}
          </span>
          <span className="ela-result-confidence">
            Confidence: {(elaResult.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* View Mode Toggle */}
      <div className="ela-view-toggle">
        <button
          className={`view-toggle-btn ${viewMode === 'side-by-side' ? 'active' : ''}`}
          onClick={() => setViewMode('side-by-side')}
        >
          <Icon name="Columns" size={14} />
          Side by Side
        </button>
        <button
          className={`view-toggle-btn ${viewMode === 'ela-only' ? 'active' : ''}`}
          onClick={() => setViewMode('ela-only')}
        >
          <Icon name="Square" size={14} />
          ELA Only
        </button>
        <button
          className={`view-toggle-btn ${viewMode === 'overlay' ? 'active' : ''}`}
          onClick={() => setViewMode('overlay')}
          disabled
          title="Coming soon"
        >
          <Icon name="Layers" size={14} />
          Overlay
        </button>
      </div>

      {/* Image Comparison */}
      <div className={`ela-images ${viewMode}`}>
        {viewMode !== 'ela-only' && (
          <div className="ela-image-container">
            <span className="ela-image-label">Original</span>
            {/* Use the image serving endpoint for the original image */}
            <img
              src={elaResult.original_image_url || `/api/media-forensics/image/${analysis.id}`}
              alt="Original"
              onError={(e) => {
                // Hide the image on error and show placeholder
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const placeholder = target.nextElementSibling;
                if (placeholder) (placeholder as HTMLElement).style.display = 'flex';
              }}
            />
            <div className="ela-placeholder" style={{ display: 'none' }}>
              <Icon name="Image" size={32} />
              <span>Original not available</span>
            </div>
          </div>
        )}
        <div className="ela-image-container">
          <span className="ela-image-label">ELA (Q={elaResult.quality_level})</span>
          {elaResult.ela_image_url ? (
            <img src={elaResult.ela_image_url} alt="ELA" />
          ) : elaResult.ela_image_base64 ? (
            <img
              src={`data:image/png;base64,${elaResult.ela_image_base64}`}
              alt="ELA"
            />
          ) : (
            <div className="ela-placeholder">
              <Icon name="Layers" size={32} />
              <span>ELA not available</span>
            </div>
          )}
        </div>
      </div>

      {/* Intensity Metrics */}
      <div className="panel-section">
        <div className="panel-section-header">
          <Icon name="BarChart3" size={16} />
          <h4>Intensity Metrics</h4>
        </div>
        <div className="metadata-grid">
          <div className="metadata-item">
            <span className="metadata-label">Global Average</span>
            <span className="metadata-value">{elaResult.global_avg_intensity.toFixed(2)}</span>
          </div>
          <div className="metadata-item">
            <span className="metadata-label">Global Maximum</span>
            <span className="metadata-value">{elaResult.global_max_intensity.toFixed(2)}</span>
          </div>
          <div className="metadata-item">
            <span className="metadata-label">Quality Level</span>
            <span className="metadata-value">{elaResult.quality_level}%</span>
          </div>
          <div className="metadata-item">
            <span className="metadata-label">Suspicious Regions</span>
            <span className="metadata-value">{elaResult.suspicious_regions.length}</span>
          </div>
        </div>
      </div>

      {/* Suspicious Regions */}
      {elaResult.suspicious_regions.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Target" size={16} />
            <h4>Suspicious Regions ({elaResult.suspicious_regions.length})</h4>
          </div>
          <div className="ela-regions-list">
            {elaResult.suspicious_regions.map((region, idx) => (
              <div
                key={idx}
                className={`ela-region-item ${region.is_suspicious ? 'suspicious' : ''}`}
              >
                <div className="region-info">
                  <span className="region-coords">
                    Region {idx + 1}: ({region.x}, {region.y}) {region.width}x{region.height}
                  </span>
                  <span className="region-description">{region.description}</span>
                </div>
                <div className="region-metrics">
                  <span className="region-avg">Avg: {region.avg_intensity.toFixed(1)}</span>
                  <span className="region-max">Max: {region.max_intensity.toFixed(1)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Regenerate Controls */}
      <div className="ela-controls">
        <label>Quality Level:</label>
        <input
          type="range"
          min="70"
          max="100"
          value={qualityLevel}
          onChange={(e) => setQualityLevel(Number(e.target.value))}
          disabled={generating}
        />
        <span className="quality-value">{qualityLevel}%</span>
        <button
          className="btn btn-secondary btn-sm"
          onClick={handleRegenerateELA}
          disabled={generating}
        >
          {generating ? (
            <>
              <Icon name="Loader2" size={14} className="spin" />
              Regenerating...
            </>
          ) : (
            <>
              <Icon name="RefreshCw" size={14} />
              Regenerate
            </>
          )}
        </button>
      </div>

      {/* ELA Explanation */}
      <div className="ela-explanation">
        <Icon name="Info" size={14} />
        <p>
          <strong>How to read ELA:</strong> Areas with high intensity (bright spots) have been
          saved at a different quality level than the rest of the image, which may indicate
          manipulation. Uniform intensity usually indicates an unedited image.
        </p>
      </div>
    </div>
  );
}

export default ELAViewer;
