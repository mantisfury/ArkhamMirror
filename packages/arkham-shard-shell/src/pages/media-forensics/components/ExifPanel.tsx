/**
 * ExifPanel - Display EXIF metadata in organized grid
 */

import { Icon } from '../../../components/common/Icon';
import type { MediaAnalysis } from '../types';

interface ExifPanelProps {
  analysis: MediaAnalysis;
}

export function ExifPanel({ analysis }: ExifPanelProps) {
  const { exif_data } = analysis;

  if (!exif_data) {
    return (
      <div className="panel-empty">
        <Icon name="Camera" size={48} />
        <p>No EXIF data available for this image</p>
        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
          EXIF data may have been stripped or the image format does not support metadata
        </p>
      </div>
    );
  }

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const formatGPS = (lat: number | null, lon: number | null): string => {
    if (lat === null || lon === null) return 'N/A';
    const latDir = lat >= 0 ? 'N' : 'S';
    const lonDir = lon >= 0 ? 'E' : 'W';
    return `${Math.abs(lat).toFixed(6)}${latDir}, ${Math.abs(lon).toFixed(6)}${lonDir}`;
  };

  const { camera, image, gps, capture, timestamps, software } = exif_data;

  return (
    <div className="exif-panel">
      {/* Warnings */}
      {exif_data.warnings && exif_data.warnings.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="AlertTriangle" size={16} />
            <h4>Warnings</h4>
          </div>
          <div className="exif-warnings">
            {exif_data.warnings.map((warning, idx) => (
              <div key={idx} className="exif-warning-item">
                <Icon name="AlertCircle" size={14} />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Camera Information */}
      {(camera.make || camera.model || camera.serial_number) && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Camera" size={16} />
            <h4>Camera Information</h4>
          </div>
          <div className="metadata-grid">
            {camera.make && (
              <div className="metadata-item">
                <span className="metadata-label">Make</span>
                <span className="metadata-value">{camera.make}</span>
              </div>
            )}
            {camera.model && (
              <div className="metadata-item">
                <span className="metadata-label">Model</span>
                <span className="metadata-value">{camera.model}</span>
              </div>
            )}
            {camera.serial_number && (
              <div className="metadata-item">
                <span className="metadata-label">Serial Number</span>
                <span className="metadata-value monospace">{camera.serial_number}</span>
              </div>
            )}
            {camera.lens_make && (
              <div className="metadata-item">
                <span className="metadata-label">Lens Make</span>
                <span className="metadata-value">{camera.lens_make}</span>
              </div>
            )}
            {camera.lens_model && (
              <div className="metadata-item">
                <span className="metadata-label">Lens Model</span>
                <span className="metadata-value">{camera.lens_model}</span>
              </div>
            )}
            {camera.lens_serial && (
              <div className="metadata-item">
                <span className="metadata-label">Lens Serial</span>
                <span className="metadata-value monospace">{camera.lens_serial}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Image Properties */}
      {(image.width || image.height || image.color_space) && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Image" size={16} />
            <h4>Image Properties</h4>
          </div>
          <div className="metadata-grid">
            {image.width && image.height && (
              <div className="metadata-item">
                <span className="metadata-label">Dimensions</span>
                <span className="metadata-value">
                  {image.width} x {image.height} px
                </span>
              </div>
            )}
            {image.color_space && (
              <div className="metadata-item">
                <span className="metadata-label">Color Space</span>
                <span className="metadata-value">{image.color_space}</span>
              </div>
            )}
            {image.bits_per_sample && (
              <div className="metadata-item">
                <span className="metadata-label">Bit Depth</span>
                <span className="metadata-value">{image.bits_per_sample} bits</span>
              </div>
            )}
            {image.compression && (
              <div className="metadata-item">
                <span className="metadata-label">Compression</span>
                <span className="metadata-value">{image.compression}</span>
              </div>
            )}
            {image.orientation && (
              <div className="metadata-item">
                <span className="metadata-label">Orientation</span>
                <span className="metadata-value">{image.orientation}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* GPS Location */}
      {(gps.latitude !== null || gps.longitude !== null) && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="MapPin" size={16} />
            <h4>GPS Location</h4>
          </div>
          <div className="metadata-grid">
            <div className="metadata-item full-width">
              <span className="metadata-label">Coordinates</span>
              <span className="metadata-value">{formatGPS(gps.latitude, gps.longitude)}</span>
            </div>
            {gps.altitude !== null && (
              <div className="metadata-item">
                <span className="metadata-label">Altitude</span>
                <span className="metadata-value">
                  {gps.altitude.toFixed(1)} m {gps.altitude_ref || ''}
                </span>
              </div>
            )}
            {gps.direction !== null && (
              <div className="metadata-item">
                <span className="metadata-label">Direction</span>
                <span className="metadata-value">
                  {gps.direction.toFixed(1)}{gps.direction_ref || ''}
                </span>
              </div>
            )}
            {gps.gps_timestamp && (
              <div className="metadata-item">
                <span className="metadata-label">GPS Time</span>
                <span className="metadata-value">{formatDate(gps.gps_timestamp)}</span>
              </div>
            )}
            {gps.gps_date && (
              <div className="metadata-item">
                <span className="metadata-label">GPS Date</span>
                <span className="metadata-value">{gps.gps_date}</span>
              </div>
            )}
          </div>
          <div className="gps-map-placeholder">
            <Icon name="Map" size={24} />
            <span style={{ marginLeft: '0.5rem' }}>
              Map view: {gps.latitude?.toFixed(4)}, {gps.longitude?.toFixed(4)}
            </span>
          </div>
        </div>
      )}

      {/* Capture Settings */}
      {(capture.exposure_time || capture.f_number || capture.iso) && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Aperture" size={16} />
            <h4>Capture Settings</h4>
          </div>
          <div className="metadata-grid">
            {capture.exposure_time && (
              <div className="metadata-item">
                <span className="metadata-label">Exposure</span>
                <span className="metadata-value">{capture.exposure_time}</span>
              </div>
            )}
            {capture.f_number !== null && (
              <div className="metadata-item">
                <span className="metadata-label">Aperture</span>
                <span className="metadata-value">f/{capture.f_number}</span>
              </div>
            )}
            {capture.iso !== null && (
              <div className="metadata-item">
                <span className="metadata-label">ISO</span>
                <span className="metadata-value">{capture.iso}</span>
              </div>
            )}
            {capture.focal_length !== null && (
              <div className="metadata-item">
                <span className="metadata-label">Focal Length</span>
                <span className="metadata-value">
                  {capture.focal_length}mm
                  {capture.focal_length_35mm && ` (${capture.focal_length_35mm}mm eq.)`}
                </span>
              </div>
            )}
            {capture.exposure_mode && (
              <div className="metadata-item">
                <span className="metadata-label">Exposure Mode</span>
                <span className="metadata-value">{capture.exposure_mode}</span>
              </div>
            )}
            {capture.exposure_program && (
              <div className="metadata-item">
                <span className="metadata-label">Program</span>
                <span className="metadata-value">{capture.exposure_program}</span>
              </div>
            )}
            {capture.metering_mode && (
              <div className="metadata-item">
                <span className="metadata-label">Metering</span>
                <span className="metadata-value">{capture.metering_mode}</span>
              </div>
            )}
            {capture.white_balance && (
              <div className="metadata-item">
                <span className="metadata-label">White Balance</span>
                <span className="metadata-value">{capture.white_balance}</span>
              </div>
            )}
            {capture.flash && (
              <div className="metadata-item">
                <span className="metadata-label">Flash</span>
                <span className="metadata-value">{capture.flash}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Timestamps */}
      {(timestamps.datetime_original || timestamps.datetime_digitized || timestamps.datetime_modified) && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Clock" size={16} />
            <h4>Timestamps</h4>
          </div>
          <div className="metadata-grid">
            {timestamps.datetime_original && (
              <div className="metadata-item">
                <span className="metadata-label">Original Date</span>
                <span className="metadata-value">{formatDate(timestamps.datetime_original)}</span>
              </div>
            )}
            {timestamps.datetime_digitized && (
              <div className="metadata-item">
                <span className="metadata-label">Digitized</span>
                <span className="metadata-value">{formatDate(timestamps.datetime_digitized)}</span>
              </div>
            )}
            {timestamps.datetime_modified && (
              <div className="metadata-item">
                <span className="metadata-label">Modified</span>
                <span className="metadata-value">{formatDate(timestamps.datetime_modified)}</span>
              </div>
            )}
            {timestamps.timezone_offset && (
              <div className="metadata-item">
                <span className="metadata-label">Timezone</span>
                <span className="metadata-value">{timestamps.timezone_offset}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Software */}
      {(software.software || software.processing_software || software.host_computer) && (
        <div className="panel-section">
          <div className="panel-section-header">
            <Icon name="Code" size={16} />
            <h4>Software</h4>
          </div>
          <div className="metadata-grid">
            {software.software && (
              <div className="metadata-item full-width">
                <span className="metadata-label">Software</span>
                <span className="metadata-value">{software.software}</span>
              </div>
            )}
            {software.processing_software && (
              <div className="metadata-item full-width">
                <span className="metadata-label">Processing Software</span>
                <span className="metadata-value">{software.processing_software}</span>
              </div>
            )}
            {software.host_computer && (
              <div className="metadata-item">
                <span className="metadata-label">Host Computer</span>
                <span className="metadata-value">{software.host_computer}</span>
              </div>
            )}
            {software.firmware && (
              <div className="metadata-item">
                <span className="metadata-label">Firmware</span>
                <span className="metadata-value">{software.firmware}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ExifPanel;
