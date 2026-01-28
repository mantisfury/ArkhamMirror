/**
 * ACH Types - Analysis of Competing Hypotheses
 *
 * Type definitions matching the backend ACH shard models.
 */

// Consistency ratings for evidence-hypothesis pairs
export type ConsistencyRating = '++' | '+' | 'N' | '-' | '--' | 'N/A';

// Evidence type classification
export type EvidenceType = 'fact' | 'testimony' | 'document' | 'physical' | 'circumstantial' | 'inference';

// Matrix status
export type MatrixStatus = 'draft' | 'active' | 'completed' | 'archived';

// Hypothesis in an ACH matrix
export interface Hypothesis {
  id: string;
  matrix_id: string;
  title: string;
  description: string;
  column_index: number;
  created_at: string;
  updated_at: string;
  author: string | null;
  is_lead: boolean;
  notes: string;
}

// Evidence item in an ACH matrix
export interface Evidence {
  id: string;
  matrix_id: string;
  description: string;
  source: string;
  evidence_type: EvidenceType;
  credibility: number; // 0.0 to 1.0
  relevance: number;   // 0.0 to 1.0
  row_index: number;
  created_at: string;
  updated_at: string;
  author: string | null;
  document_ids: string[];
  notes: string;
}

// Rating for evidence-hypothesis pair
export interface Rating {
  matrix_id: string;
  evidence_id: string;
  hypothesis_id: string;
  rating: ConsistencyRating;
  reasoning: string;
  confidence: number; // 0.0 to 1.0
  created_at: string;
  updated_at: string;
  author: string | null;
}

// Calculated score for a hypothesis
export interface HypothesisScore {
  hypothesis_id: string;
  hypothesis_title: string;
  rank: number;
  inconsistency_count: number;
  weighted_score: number;
  normalized_score: number;
  evidence_count: number;
}

// Full ACH matrix data from API
export interface ACHMatrix {
  id: string;
  title: string;
  description: string;
  status: MatrixStatus;
  hypotheses: Hypothesis[];
  evidence: Evidence[];
  ratings: Rating[];
  scores: HypothesisScore[];
  created_at: string;
  updated_at: string;
  created_by: string | null;
  project_id: string | null;
  tags: string[];
  notes: string;
  linked_document_ids: string[];
}

// Matrix list item (summary view)
export interface MatrixListItem {
  id: string;
  title: string;
  description: string;
  status: MatrixStatus;
  hypothesis_count: number;
  evidence_count: number;
  created_at: string;
  updated_at: string;
}

// API response types
export interface MatricesListResponse {
  count: number;
  matrices: MatrixListItem[];
}

export interface ScoresResponse {
  matrix_id: string;
  scores: HypothesisScore[];
}

export interface DevilsAdvocateResponse {
  matrix_id: string;
  hypothesis_id: string;
  hypothesis_title: string;
  challenge_text: string;
  alternative_interpretation: string;
  weaknesses: string[];
  evidence_gaps: string[];
  recommended_investigations: string[];
  model: string;
}

export interface AIStatusResponse {
  available: boolean;
  llm_service: boolean;
}

// Rating display helpers
export const RATING_LABELS: Record<ConsistencyRating, string> = {
  '++': 'Highly Consistent',
  '+': 'Consistent',
  'N': 'Neutral',
  '-': 'Inconsistent',
  '--': 'Highly Inconsistent',
  'N/A': 'Not Applicable',
};

export const RATING_COLORS: Record<ConsistencyRating, string> = {
  '++': 'var(--success)',
  '+': 'rgba(74, 222, 128, 0.6)',
  'N': 'var(--text-muted)',
  '-': 'rgba(248, 113, 113, 0.6)',
  '--': 'var(--error)',
  'N/A': 'var(--bg-tertiary)',
};

export const RATING_OPTIONS: { value: ConsistencyRating; label: string }[] = [
  { value: '++', label: '++ Highly Consistent' },
  { value: '+', label: '+ Consistent' },
  { value: 'N', label: 'N Neutral' },
  { value: '-', label: '- Inconsistent' },
  { value: '--', label: '-- Highly Inconsistent' },
  { value: 'N/A', label: 'N/A Not Applicable' },
];

export const EVIDENCE_TYPE_OPTIONS: { value: EvidenceType; label: string }[] = [
  { value: 'fact', label: 'Fact' },
  { value: 'testimony', label: 'Testimony' },
  { value: 'document', label: 'Document' },
  { value: 'physical', label: 'Physical' },
  { value: 'circumstantial', label: 'Circumstantial' },
  { value: 'inference', label: 'Inference' },
];

export const STATUS_OPTIONS: { value: MatrixStatus; label: string }[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'archived', label: 'Archived' },
];

// ============================================
// Extended Types for Full ACH Methodology
// ============================================

// Milestone for tracking future indicators
export interface Milestone {
  id: string;
  matrix_id: string;
  description: string;
  hypothesis_id: string;
  hypothesis_label?: string;
  expected_by: string | null;
  observed: -1 | 0 | 1; // -1 = contradicted, 0 = pending, 1 = observed
  observation_notes: string;
  created_at: string;
  updated_at: string;
}

// Sensitivity analysis result
export interface SensitivityResult {
  evidence_id: string;
  evidence_label: string;
  impact: 'critical' | 'moderate' | 'minor';
  description: string;
  affected_rankings?: string[];
}

// Consistency check result
export interface ConsistencyCheck {
  passed: boolean;
  message: string;
  severity?: 'info' | 'warning' | 'error';
}

// Diagnosticity report
export interface DiagnosticityReport {
  matrix_id: string;
  evidence_diagnosticity: {
    evidence_id: string;
    evidence_label: string;
    diagnosticity_score: number;
    is_high_diagnostic: boolean;
    is_low_diagnostic: boolean;
    variance: number;
  }[];
  suggestions: string[];
}

// AI Suggestion Types
export interface HypothesisSuggestion {
  title: string;
  description: string;
  rationale?: string;
  is_null?: boolean;
}

export interface EvidenceSuggestion {
  description: string;
  evidence_type: EvidenceType;
  source: string;
  importance?: string;
}

export interface RatingSuggestion {
  hypothesis_id: string;
  hypothesis_label: string;
  rating: ConsistencyRating;
  explanation: string;
}

export interface MilestoneSuggestion {
  hypothesis_id: string;
  hypothesis_label: string;
  description: string;
  expected_timeframe?: string;
  rationale?: string;
}

export interface Challenge {
  hypothesis_id: string;
  hypothesis_label: string;
  counter_argument: string;
  disproof_evidence: string;
  alternative_angle: string;
  weaknesses?: string[];
}

export interface AnalysisInsights {
  matrix_id: string;
  insights: string;
  leading_hypothesis: string;
  key_evidence: string[];
  evidence_gaps: string[];
  cognitive_biases: string[];
  recommendations: string[];
}

// Step completion tracking
export interface StepProgress {
  currentStep: number;
  completedSteps: number[];
  lastUpdated: string;
}

// ============================================
// Premortem Analysis Types
// ============================================

export type FailureModeType =
  | 'misinterpretation'
  | 'missed_evidence'
  | 'failed_assumption'
  | 'deception'
  | 'alternative_explanation';

export type PremortemConversionType = 'hypothesis' | 'milestone' | 'assumption';

export interface FailureMode {
  id: string;
  failure_type: FailureModeType;
  description: string;
  likelihood: 'low' | 'medium' | 'high';
  early_warning_indicator: string;
  mitigation_action: string;
  converted_to?: PremortemConversionType | null;
  converted_id?: string | null;
}

export interface PremortemAnalysis {
  id: string;
  matrix_id: string;
  hypothesis_id: string;
  hypothesis_title: string;
  scenario_description: string;
  overall_vulnerability: 'low' | 'medium' | 'high';
  key_risks: string[];
  recommendations: string[];
  failure_modes: FailureMode[];
  model_used?: string;
  created_at: string;
  updated_at?: string;
}

export interface PremortemListItem {
  id: string;
  hypothesis_id: string;
  hypothesis_title: string;
  overall_vulnerability: 'low' | 'medium' | 'high';
  failure_mode_count: number;
  key_risks: string[];
  recommendations: string[];
  created_at: string;
}

export interface PremortremsListResponse {
  matrix_id: string;
  premortems: PremortemListItem[];
  count: number;
}

// ============================================
// Cone of Plausibility / Scenario Types
// ============================================

export type ScenarioStatus = 'active' | 'occurred' | 'ruled_out' | 'converted';

export interface ScenarioIndicator {
  id: string;
  description: string;
  is_triggered: boolean;
  triggered_at?: string | null;
}

export interface ScenarioNode {
  id: string;
  parent_id: string | null;
  title: string;
  description: string;
  probability: number;
  timeframe: string;
  key_drivers: string[];
  trigger_conditions: string[];
  indicators: ScenarioIndicator[];
  status: ScenarioStatus;
  converted_hypothesis_id?: string | null;
  depth: number;
  branch_order: number;
  notes: string;
}

export interface ScenarioDriver {
  id: string;
  name: string;
  description: string;
  current_state: string;
  possible_states: string[];
}

export interface ScenarioTree {
  id: string;
  matrix_id: string;
  title: string;
  description: string;
  situation_summary: string;
  root_node_id: string | null;
  total_scenarios: number;
  nodes: ScenarioNode[];
  drivers: ScenarioDriver[];
  model_used?: string;
  created_at: string;
  updated_at: string;
}

export interface ScenarioTreeListItem {
  id: string;
  title: string;
  description: string;
  total_scenarios: number;
  active_scenarios: number;
  created_at: string;
  updated_at: string;
}

export interface ScenarioTreesListResponse {
  matrix_id: string;
  trees: ScenarioTreeListItem[];
  count: number;
}

// Premortem display helpers
export const FAILURE_MODE_LABELS: Record<FailureModeType, string> = {
  misinterpretation: 'Misinterpretation',
  missed_evidence: 'Missed Evidence',
  failed_assumption: 'Failed Assumption',
  deception: 'Deception',
  alternative_explanation: 'Alternative Explanation',
};

export const FAILURE_MODE_ICONS: Record<FailureModeType, string> = {
  misinterpretation: 'Eye',
  missed_evidence: 'Search',
  failed_assumption: 'AlertTriangle',
  deception: 'ShieldAlert',
  alternative_explanation: 'GitBranch',
};

export const LIKELIHOOD_COLORS: Record<'low' | 'medium' | 'high', string> = {
  low: 'var(--success)',
  medium: 'var(--warning)',
  high: 'var(--error)',
};

export const SCENARIO_STATUS_LABELS: Record<ScenarioStatus, string> = {
  active: 'Active',
  occurred: 'Occurred',
  ruled_out: 'Ruled Out',
  converted: 'Converted to Hypothesis',
};

export const SCENARIO_STATUS_COLORS: Record<ScenarioStatus, string> = {
  active: 'var(--primary)',
  occurred: 'var(--success)',
  ruled_out: 'var(--text-muted)',
  converted: 'var(--info)',
};
