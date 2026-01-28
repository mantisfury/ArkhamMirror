/**
 * Contradictions Types
 *
 * Type definitions matching the backend Contradictions shard models.
 */

// Contradiction status
export type ContradictionStatus = 'detected' | 'confirmed' | 'dismissed' | 'investigating';

// Severity level
export type Severity = 'high' | 'medium' | 'low';

// Contradiction type
export type ContradictionType = 'direct' | 'temporal' | 'numeric' | 'entity' | 'logical' | 'contextual';

// Contradiction details
export interface Contradiction {
  id: string;
  doc_a_id: string;
  doc_b_id: string;
  claim_a: string;
  claim_b: string;
  contradiction_type: ContradictionType;
  severity: Severity;
  status: ContradictionStatus;
  explanation: string;
  confidence_score: number;
  created_at: string;
  analyst_notes: string[];
  chain_id: string | null;
}

// Contradiction list item (summary view)
export interface ContradictionListItem extends Contradiction {}

// API response types
export interface ContradictionListResponse {
  contradictions: ContradictionListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface StatsResponse {
  total_contradictions: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  chains_detected: number;
  recent_count: number;
}

// Display helpers
export const STATUS_LABELS: Record<ContradictionStatus, string> = {
  detected: 'Detected',
  confirmed: 'Confirmed',
  dismissed: 'Dismissed',
  investigating: 'Investigating',
};

export const STATUS_COLORS: Record<ContradictionStatus, string> = {
  detected: 'var(--info)',
  confirmed: 'var(--error)',
  dismissed: 'var(--text-muted)',
  investigating: 'var(--warning)',
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

export const SEVERITY_COLORS: Record<Severity, string> = {
  high: 'var(--error)',
  medium: 'var(--warning)',
  low: 'var(--info)',
};

export const TYPE_LABELS: Record<ContradictionType, string> = {
  direct: 'Direct',
  temporal: 'Temporal',
  numeric: 'Numeric',
  entity: 'Entity',
  logical: 'Logical',
  contextual: 'Contextual',
};

export const TYPE_ICONS: Record<ContradictionType, string> = {
  direct: 'XCircle',
  temporal: 'Clock',
  numeric: 'Hash',
  entity: 'User',
  logical: 'GitBranch',
  contextual: 'FileText',
};

export const STATUS_OPTIONS: { value: ContradictionStatus; label: string }[] = [
  { value: 'detected', label: 'Detected' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'dismissed', label: 'Dismissed' },
  { value: 'investigating', label: 'Investigating' },
];

export const SEVERITY_OPTIONS: { value: Severity; label: string }[] = [
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

export const TYPE_OPTIONS: { value: ContradictionType; label: string }[] = [
  { value: 'direct', label: 'Direct' },
  { value: 'temporal', label: 'Temporal' },
  { value: 'numeric', label: 'Numeric' },
  { value: 'entity', label: 'Entity' },
  { value: 'logical', label: 'Logical' },
  { value: 'contextual', label: 'Contextual' },
];
