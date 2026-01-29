/**
 * SunPositionPanel - Sun position and shadow verification display
 */

import { useState, useCallback } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useToast } from '../../../context/ToastContext';
import * as api from '../api';
import type { MediaAnalysis, SunPositionResult, SunPositionRequest } from '../types';

interface SunPositionPanelProps {
  analysis: MediaAnalysis;
}

export function SunPositionPanel({ analysis }: SunPositionPanelProps) {
  const { toast } = useToast();
  const [sunResult, setSunResult] = useState<SunPositionResult | null>(
    analysis.sun_position_result
  );
  const [calculating, setCalculating] = useState(false);
  const [overrideLocation, setOverrideLocation] = useState<{ lat: string; lon: string }>({
    lat: '',
    lon: '',
  });
  const [overrideTime, setOverrideTime] = useState('');

  const hasGPS = analysis.exif_data?.gps?.latitude !== null;

  const handleCalculate = useCallback(async () => {
    setCalculating(true);
    try {
      const request: SunPositionRequest = {
        analysis_id: analysis.id,
      };

      // Add overrides if provided
      if (overrideLocation.lat && overrideLocation.lon) {
        request.override_location = {
          lat: parseFloat(overrideLocation.lat),
          lon: parseFloat(overrideLocation.lon),
        };
      }
      if (overrideTime) {
        request.override_time = overrideTime;
      }

      const response = await api.getSunPosition(request);
      setSunResult(response.result);
      toast.success('Sun position calculated');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to calculate sun position');
    } finally {
      setCalculating(false);
    }
  }, [analysis.id, overrideLocation, overrideTime, toast]);

  // No GPS data
  if (!hasGPS && !sunResult) {
    return (
      <div className="sun-position-container">
        <div className="panel-empty">
          <Icon name="Sun" size={48} />
          <p>No GPS data available for sun position verification</p>
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
            Sun position analysis requires GPS coordinates and timestamp from the image metadata
          </p>
        </div>

        {/* Manual Override Form */}
        <div className="sun-override-form">
          <div className="panel-section-header">
            <Icon name="Edit3" size={16} />
            <h4>Manual Coordinates</h4>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', marginBottom: '1rem' }}>
            Enter coordinates manually to verify sun position for a claimed location and time.
          </p>
          <div className="override-inputs">
            <div className="override-input-group">
              <label>Latitude</label>
              <input
                type="number"
                step="0.000001"
                placeholder="e.g., 40.7128"
                value={overrideLocation.lat}
                onChange={(e) =>
                  setOverrideLocation({ ...overrideLocation, lat: e.target.value })
                }
              />
            </div>
            <div className="override-input-group">
              <label>Longitude</label>
              <input
                type="number"
                step="0.000001"
                placeholder="e.g., -74.0060"
                value={overrideLocation.lon}
                onChange={(e) =>
                  setOverrideLocation({ ...overrideLocation, lon: e.target.value })
                }
              />
            </div>
            <div className="override-input-group full-width">
              <label>Date/Time (ISO format)</label>
              <input
                type="datetime-local"
                value={overrideTime}
                onChange={(e) => setOverrideTime(e.target.value)}
              />
            </div>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleCalculate}
            disabled={calculating || !overrideLocation.lat || !overrideLocation.lon}
            style={{ marginTop: '1rem' }}
          >
            {calculating ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Calculating...
              </>
            ) : (
              <>
                <Icon name="Sun" size={16} />
                Calculate Sun Position
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  // No result yet but has GPS
  if (!sunResult) {
    return (
      <div className="sun-position-container">
        <div className="panel-empty">
          <Icon name="Sun" size={48} />
          <p>Sun position verification not yet performed</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleCalculate}
          disabled={calculating}
          style={{ alignSelf: 'center' }}
        >
          {calculating ? (
            <>
              <Icon name="Loader2" size={16} className="spin" />
              Calculating...
            </>
          ) : (
            <>
              <Icon name="Sun" size={16} />
              Verify Sun Position
            </>
          )}
        </button>
      </div>
    );
  }

  const formatAngle = (angle: number): string => {
    return `${angle.toFixed(2)}`;
  };

  return (
    <div className="sun-position-container">
      {/* Consistency Banner */}
      <div
        className={`sun-consistency-banner ${sunResult.is_consistent ? 'consistent' : 'inconsistent'}`}
      >
        <Icon name={sunResult.is_consistent ? 'CheckCircle' : 'AlertTriangle'} size={24} />
        <div>
          <div className="consistency-title">
            {sunResult.is_consistent
              ? 'Sun Position Consistent'
              : 'Sun Position Inconsistent'}
          </div>
          <div className="consistency-confidence">
            Confidence: {(sunResult.confidence * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      {/* Inconsistency Details */}
      {!sunResult.is_consistent && sunResult.inconsistency_details.length > 0 && (
        <div className="sun-inconsistencies">
          {sunResult.inconsistency_details.map((detail, idx) => (
            <div key={idx} className="inconsistency-item">
              <Icon name="AlertCircle" size={14} />
              <span>{detail}</span>
            </div>
          ))}
        </div>
      )}

      {/* Claimed vs Calculated */}
      <div className="sun-data-grid">
        {/* Claimed Data */}
        <div className="sun-data-card">
          <h5>
            <Icon name="MapPin" size={14} />
            Claimed Location
          </h5>
          {sunResult.claimed_location ? (
            <div className="sun-location-data">
              <div className="location-coord">
                <span className="coord-label">Lat:</span>
                <span className="coord-value">{sunResult.claimed_location.lat.toFixed(6)}</span>
              </div>
              <div className="location-coord">
                <span className="coord-label">Lon:</span>
                <span className="coord-value">{sunResult.claimed_location.lon.toFixed(6)}</span>
              </div>
            </div>
          ) : (
            <span className="no-data">Not available</span>
          )}
          {sunResult.claimed_time && (
            <div className="claimed-time">
              <Icon name="Clock" size={12} />
              <span>{new Date(sunResult.claimed_time).toLocaleString()}</span>
            </div>
          )}
        </div>

        {/* Calculated Sun Position */}
        {sunResult.calculated_sun_position && (
          <div className="sun-data-card">
            <h5>
              <Icon name="Sun" size={14} />
              Calculated Sun
            </h5>
            <div className="sun-position-data">
              <div className="sun-metric">
                <span className="metric-label">Azimuth</span>
                <span className="sun-data-value">
                  {formatAngle(sunResult.calculated_sun_position.azimuth)}
                  <span className="sun-data-unit">(deg)</span>
                </span>
              </div>
              <div className="sun-metric">
                <span className="metric-label">Altitude</span>
                <span className="sun-data-value">
                  {formatAngle(sunResult.calculated_sun_position.altitude)}
                  <span className="sun-data-unit">(deg)</span>
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Shadow Analysis */}
      {sunResult.shadow_analysis && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Moon" size={16} />
            <h4>Shadow Analysis</h4>
          </div>

          {/* Consistency Score */}
          <div className="shadow-consistency">
            <span className="consistency-label">Shadow Consistency Score:</span>
            <div className="consistency-bar">
              <div
                className="consistency-fill"
                style={{
                  width: `${sunResult.shadow_analysis.consistency_score * 100}%`,
                  backgroundColor:
                    sunResult.shadow_analysis.consistency_score > 0.7
                      ? 'var(--success)'
                      : sunResult.shadow_analysis.consistency_score > 0.4
                        ? 'var(--warning)'
                        : 'var(--error)',
                }}
              />
            </div>
            <span className="consistency-value">
              {(sunResult.shadow_analysis.consistency_score * 100).toFixed(0)}%
            </span>
          </div>

          {/* Average Shadow Direction */}
          {sunResult.shadow_analysis.average_shadow_direction !== null && (
            <div className="metadata-item" style={{ marginTop: '1rem' }}>
              <span className="metadata-label">Average Shadow Direction</span>
              <span className="metadata-value">
                {sunResult.shadow_analysis.average_shadow_direction.toFixed(1)} (degrees)
              </span>
            </div>
          )}

          {/* Detected Shadows */}
          {sunResult.shadow_analysis.detected_shadows.length > 0 && (
            <div className="detected-shadows">
              <h5>Detected Shadows ({sunResult.shadow_analysis.detected_shadows.length})</h5>
              <div className="shadows-list">
                {sunResult.shadow_analysis.detected_shadows.map((shadow, idx) => (
                  <div key={idx} className="shadow-item">
                    <span className="shadow-id">{shadow.object_id}</span>
                    <span className="shadow-direction">
                      {shadow.shadow_direction.toFixed(1)} (deg)
                    </span>
                    <span className="shadow-confidence">
                      {(shadow.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Recalculate with Overrides */}
      <div className="panel-section">
        <div className="panel-section-header">
          <Icon name="RefreshCw" size={16} />
          <h4>Recalculate with Custom Values</h4>
        </div>
        <div className="override-inputs">
          <div className="override-input-group">
            <label>Override Latitude</label>
            <input
              type="number"
              step="0.000001"
              placeholder="Leave empty to use EXIF"
              value={overrideLocation.lat}
              onChange={(e) =>
                setOverrideLocation({ ...overrideLocation, lat: e.target.value })
              }
            />
          </div>
          <div className="override-input-group">
            <label>Override Longitude</label>
            <input
              type="number"
              step="0.000001"
              placeholder="Leave empty to use EXIF"
              value={overrideLocation.lon}
              onChange={(e) =>
                setOverrideLocation({ ...overrideLocation, lon: e.target.value })
              }
            />
          </div>
          <div className="override-input-group full-width">
            <label>Override Date/Time</label>
            <input
              type="datetime-local"
              value={overrideTime}
              onChange={(e) => setOverrideTime(e.target.value)}
            />
          </div>
        </div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={handleCalculate}
          disabled={calculating}
          style={{ marginTop: '0.75rem' }}
        >
          {calculating ? (
            <>
              <Icon name="Loader2" size={14} className="spin" />
              Recalculating...
            </>
          ) : (
            <>
              <Icon name="RefreshCw" size={14} />
              Recalculate
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default SunPositionPanel;
