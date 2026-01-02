/**
 * Types for Deception Detection (MOM/POP/MOSES/EVE)
 */

export type DeceptionChecklistType = 'mom' | 'pop' | 'moses' | 'eve';
export type DeceptionRisk = 'minimal' | 'low' | 'moderate' | 'high' | 'critical';
export type IndicatorStrength = 'none' | 'weak' | 'moderate' | 'strong' | 'conclusive';

export interface DeceptionIndicator {
  id: string;
  checklist: DeceptionChecklistType;
  question: string;
  answer: string | null;
  strength: IndicatorStrength;
  confidence: number;
  evidence_ids: string[];
  notes: string | null;
}

export interface DeceptionChecklist {
  checklist_type: DeceptionChecklistType;
  indicators: DeceptionIndicator[];
  overall_score: number;
  risk_level: string;
  summary: string | null;
  completed_at: string | null;
}

export interface DeceptionAssessment {
  id: string;
  source_type: string;
  source_id: string;
  mom_checklist: DeceptionChecklist | null;
  pop_checklist: DeceptionChecklist | null;
  moses_checklist: DeceptionChecklist | null;
  eve_checklist: DeceptionChecklist | null;
  overall_score: number;
  risk_level: DeceptionRisk;
  conclusion: string | null;
  recommendations: string[];
  affects_credibility: boolean;
  credibility_weight: number;
  assessed_by: string;
  assessor_id: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface StandardIndicator {
  id: string;
  checklist_type: DeceptionChecklistType;
  question: string;
  description: string;
  weight: number;
}

export const CHECKLIST_INFO: Record<DeceptionChecklistType, {
  name: string;
  fullName: string;
  description: string;
  icon: string;
  color: string;
}> = {
  mom: {
    name: 'MOM',
    fullName: 'Motive, Opportunity, Means',
    description: 'Evaluates whether an adversary has motive, opportunity, and means to deceive',
    icon: 'Target',
    color: '#f97316', // orange
  },
  pop: {
    name: 'POP',
    fullName: 'Past Opposition Practices',
    description: 'Examines historical patterns of deception by the adversary',
    icon: 'History',
    color: '#8b5cf6', // purple
  },
  moses: {
    name: 'MOSES',
    fullName: 'Manipulability of Sources',
    description: 'Assesses how easily sources could be manipulated or fed false information',
    icon: 'Users',
    color: '#06b6d4', // cyan
  },
  eve: {
    name: 'EVE',
    fullName: 'Evaluation of Evidence',
    description: 'Evaluates the consistency and reliability of evidence itself',
    icon: 'FileSearch',
    color: '#22c55e', // green
  },
};

export const RISK_COLORS: Record<DeceptionRisk, string> = {
  minimal: '#10b981', // emerald
  low: '#22c55e',     // green
  moderate: '#eab308', // yellow
  high: '#f97316',    // orange
  critical: '#ef4444', // red
};

export const STRENGTH_COLORS: Record<IndicatorStrength, string> = {
  none: '#6b7280',      // gray
  weak: '#22c55e',      // green (weak deception indicator = good)
  moderate: '#eab308',   // yellow
  strong: '#f97316',     // orange
  conclusive: '#ef4444', // red (strong deception indicator = bad)
};
