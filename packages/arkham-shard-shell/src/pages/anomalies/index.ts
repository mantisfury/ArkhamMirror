/**
 * Anomalies shard pages
 *
 * Export all page components for the Anomalies shard.
 */

export { AnomaliesPage } from './AnomaliesPage';
export { AnomalyDetail } from './AnomalyDetail';

// Re-export types for convenience
export type {
  Anomaly,
  AnomalyType,
  AnomalyStatus,
  SeverityLevel,
  AnomalyPattern,
  DetectionConfig,
  DetectRequest,
  DetectResponse,
  AnomalyListResponse,
  StatsResponse,
  PatternRequest,
  PatternsResponse,
} from './types';
