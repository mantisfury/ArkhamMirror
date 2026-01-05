/**
 * Anomalies Types
 *
 * Type definitions for the Anomalies shard.
 */

// Anomaly types
export type AnomalyType = 'content' | 'metadata' | 'temporal' | 'structural' | 'statistical' | 'red_flag';

// Anomaly status
export type AnomalyStatus = 'detected' | 'confirmed' | 'dismissed' | 'false_positive';

// Severity level
export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low';

// Anomaly record
export interface Anomaly {
  id: string;
  doc_id: string;
  anomaly_type: AnomalyType;
  status: AnomalyStatus;
  score: number;
  severity: SeverityLevel;
  confidence: number;
  explanation: string;
  details: Record<string, any>;
  field_name?: string;
  expected_range?: string;
  actual_value?: string;
  detected_at: string;
  updated_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
  notes: string;
  tags: string[];
}

// Pattern record
export interface AnomalyPattern {
  id: string;
  pattern_type: string;
  description: string;
  anomaly_ids: string[];
  doc_ids: string[];
  frequency: number;
  confidence: number;
  detected_at: string;
  notes: string;
}

// Detection configuration
export interface DetectionConfig {
  z_score_threshold: number;
  min_cluster_distance: number;
  detect_content: boolean;
  detect_metadata: boolean;
  detect_temporal: boolean;
  detect_structural: boolean;
  detect_statistical: boolean;
  detect_red_flags: boolean;
  money_patterns: boolean;
  date_patterns: boolean;
  name_patterns: boolean;
  sensitive_keywords: boolean;
  batch_size: number;
  min_confidence: number;
}

// API Request/Response types
export interface DetectRequest {
  project_id?: string;
  doc_ids?: string[];
  config?: Partial<DetectionConfig>;
}

export interface DetectResponse {
  anomalies_detected: number;
  duration_ms: number;
  job_id?: string;
}

export interface AnomalyListResponse {
  total: number;
  items: Anomaly[];
  offset: number;
  limit: number;
  has_more: boolean;
  facets: {
    by_type?: Record<string, number>;
    by_status?: Record<string, number>;
    by_severity?: Record<string, number>;
  };
}

export interface StatsResponse {
  stats: {
    total_anomalies: number;
    by_type: Record<string, number>;
    by_status: Record<string, number>;
    by_severity: Record<string, number>;
    detected_last_24h: number;
    confirmed_last_24h: number;
    dismissed_last_24h: number;
    false_positive_rate: number;
    avg_confidence: number;
    calculated_at: string;
  };
}

export interface PatternRequest {
  anomaly_ids?: string[];
  min_frequency: number;
  pattern_types?: string[];
}

export interface PatternsResponse {
  patterns_found: number;
  patterns: AnomalyPattern[];
}

export interface BulkStatusResponse {
  success: boolean;
  updated_count: number;
  failed_count: number;
  failed_ids: string[];
}

export interface RelatedAnomaly extends Anomaly {
  relation: 'same_document' | 'same_type';
}

export interface RelatedAnomaliesResponse {
  source_id: string;
  related: RelatedAnomaly[];
  total: number;
}

// Display helpers
export const ANOMALY_TYPE_LABELS: Record<AnomalyType, string> = {
  content: 'Content',
  metadata: 'Metadata',
  temporal: 'Temporal',
  structural: 'Structural',
  statistical: 'Statistical',
  red_flag: 'Red Flag',
};

export const ANOMALY_TYPE_ICONS: Record<AnomalyType, string> = {
  content: 'FileText',
  metadata: 'Info',
  temporal: 'Clock',
  structural: 'Boxes',
  statistical: 'BarChart3',
  red_flag: 'AlertTriangle',
};

export const STATUS_LABELS: Record<AnomalyStatus, string> = {
  detected: 'Detected',
  confirmed: 'Confirmed',
  dismissed: 'Dismissed',
  false_positive: 'False Positive',
};

export const STATUS_COLORS: Record<AnomalyStatus, string> = {
  detected: 'blue',
  confirmed: 'red',
  dismissed: 'gray',
  false_positive: 'yellow',
};

export const SEVERITY_LABELS: Record<SeverityLevel, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

export const SEVERITY_COLORS: Record<SeverityLevel, string> = {
  critical: 'var(--arkham-error)',
  high: 'var(--arkham-warning)',
  medium: 'var(--arkham-info)',
  low: 'var(--arkham-text-muted)',
};

// Filter options
export const ANOMALY_TYPE_OPTIONS: { value: AnomalyType; label: string }[] = [
  { value: 'content', label: 'Content' },
  { value: 'metadata', label: 'Metadata' },
  { value: 'temporal', label: 'Temporal' },
  { value: 'structural', label: 'Structural' },
  { value: 'statistical', label: 'Statistical' },
  { value: 'red_flag', label: 'Red Flag' },
];

export const STATUS_OPTIONS: { value: AnomalyStatus; label: string }[] = [
  { value: 'detected', label: 'Detected' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'dismissed', label: 'Dismissed' },
  { value: 'false_positive', label: 'False Positive' },
];

export const SEVERITY_OPTIONS: { value: SeverityLevel; label: string }[] = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];
