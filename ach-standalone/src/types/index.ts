// Rating types for the ACH matrix
export type Rating = 'CC' | 'C' | 'N' | 'I' | 'II' | '';

export const RATING_LABELS: Record<Rating | '-', string> = {
  'CC': 'Very Consistent',
  'C': 'Consistent',
  'N': 'Neutral',
  'I': 'Inconsistent',
  'II': 'Very Inconsistent',
  '': 'Unrated',
  '-': 'Unrated',
};

export const RATING_COLORS: Record<Rating | '-', string> = {
  'CC': 'bg-ach-cc',
  'C': 'bg-ach-c',
  'N': 'bg-ach-n',
  'I': 'bg-ach-i',
  'II': 'bg-ach-ii',
  '': 'bg-gray-700',
  '-': 'bg-gray-700',
};

export const RATING_VALUES: Record<Rating, number> = {
  'CC': 2,
  'C': 1,
  'N': 0,
  'I': -1,
  'II': -2,
  '': 0,
};

// Evidence types
export type EvidenceType = 'fact' | 'testimony' | 'document' | 'assumption' | 'argument';
export type Reliability = 'high' | 'medium' | 'low';

export const EVIDENCE_TYPES: EvidenceType[] = ['fact', 'testimony', 'document', 'assumption', 'argument'];
export const RELIABILITY_OPTIONS: Reliability[] = ['high', 'medium', 'low'];

// Hypothesis model
export interface Hypothesis {
  id: string;
  label: string;
  description: string;
  color: string;
  displayOrder: number;
  futureIndicators?: string;
  createdAt: string;
}

// Evidence model
export interface Evidence {
  id: string;
  label: string;
  description: string;
  evidenceType: EvidenceType;
  reliability: Reliability;
  source?: string;
  displayOrder: number;
  createdAt: string;
}

// Matrix rating entry
export interface MatrixRating {
  evidenceId: string;
  hypothesisId: string;
  rating: Rating;
  notes?: string;
}

// Milestone for future indicators
export interface Milestone {
  id: string;
  hypothesisId: string;
  description: string;
  expectedBy?: string;
  observed: 0 | 1 | -1; // 0=pending, 1=observed, -1=contradicted
  observedDate?: string;
  observationNotes?: string;
  createdAt: string;
}

// Snapshot for version history
export interface Snapshot {
  id: string;
  label: string;
  description?: string;
  createdAt: string;
  data: {
    hypotheses: Hypothesis[];
    evidence: Evidence[];
    ratings: MatrixRating[];
    milestones: Milestone[];
    sensitivityNotes: string;
  };
}

// Analysis session
export interface Analysis {
  id: string;
  title: string;
  focusQuestion: string;
  description?: string;
  status: 'draft' | 'in_progress' | 'complete' | 'archived';
  currentStep: number;
  stepsCompleted: number[];
  sensitivityNotes: string;
  hypotheses: Hypothesis[];
  evidence: Evidence[];
  ratings: MatrixRating[];
  milestones: Milestone[];
  snapshots: Snapshot[];
  createdAt: string;
  updatedAt: string;
}

// Calculated score for a hypothesis
export interface HypothesisScore {
  hypothesisId: string;
  label: string;
  color: string;
  inconsistencyScore: number;
  consistencyScore: number;
  rank: number;
}

// Diagnosticity result for evidence
export interface DiagnosticityResult {
  evidenceId: string;
  label: string;
  diagnosticityScore: number;
  isHighDiagnostic: boolean;
  isLowDiagnostic: boolean;
  ratingVariance: number;
}

// Sensitivity analysis result
export interface SensitivityResult {
  evidenceId: string;
  evidenceLabel: string;
  isCritical: boolean;
  originalWinner: string;
  winnerIfRemoved: string;
  scoreDelta: number;
}

// LLM provider types
export type LLMProvider = 'lmstudio' | 'openai' | 'groq' | 'anthropic' | 'ollama' | 'custom';

export interface LLMProviderConfig {
  name: string;
  endpoint: string;
  apiKey?: string;
  model?: string;
  requiresApiKey: boolean;
  defaultEndpoint: string;
  defaultModel: string;
}

export const LLM_PROVIDERS: Record<LLMProvider, LLMProviderConfig> = {
  lmstudio: {
    name: 'LM Studio (Local)',
    endpoint: 'http://localhost:1234/v1',
    requiresApiKey: false,
    defaultEndpoint: 'http://localhost:1234/v1',
    defaultModel: 'local-model',
  },
  ollama: {
    name: 'Ollama (Local)',
    endpoint: 'http://localhost:11434/v1',
    requiresApiKey: false,
    defaultEndpoint: 'http://localhost:11434/v1',
    defaultModel: 'llama3.2',
  },
  openai: {
    name: 'OpenAI',
    endpoint: 'https://api.openai.com/v1',
    requiresApiKey: true,
    defaultEndpoint: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o-mini',
  },
  groq: {
    name: 'Groq',
    endpoint: 'https://api.groq.com/openai/v1',
    requiresApiKey: true,
    defaultEndpoint: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.3-70b-versatile',
  },
  anthropic: {
    name: 'Anthropic',
    endpoint: 'https://api.anthropic.com/v1',
    requiresApiKey: true,
    defaultEndpoint: 'https://api.anthropic.com/v1',
    defaultModel: 'claude-3-5-sonnet-20241022',
  },
  custom: {
    name: 'Custom Endpoint',
    endpoint: '',
    requiresApiKey: false,
    defaultEndpoint: '',
    defaultModel: '',
  },
};

// LLM configuration
export interface LLMConfig {
  enabled: boolean;
  provider: LLMProvider;
  endpoint: string;
  apiKey?: string;
  model: string;
  connectionStatus: 'untested' | 'connected' | 'error';
  lastError?: string;
}

// Step definitions
export const STEP_NAMES: Record<number, string> = {
  1: 'Identify Hypotheses',
  2: 'Gather Evidence',
  3: 'Create Matrix',
  4: 'Analyze Diagnosticity',
  5: 'Refine Matrix',
  6: 'Draw Conclusions',
  7: 'Sensitivity Analysis',
  8: 'Report & Milestones',
};

export const STEP_DESCRIPTIONS: Record<number, string> = {
  1: 'List all possible explanations for the situation, including unlikely ones.',
  2: 'Gather evidence, arguments, and assumptions relevant to each hypothesis.',
  3: 'Rate how consistent each piece of evidence is with each hypothesis.',
  4: 'Identify which evidence items help distinguish between hypotheses.',
  5: 'Review and refine your ratings based on diagnosticity analysis.',
  6: 'Identify the hypothesis with the fewest inconsistencies.',
  7: 'Test how robust your conclusion is to changes in evidence.',
  8: 'Document conclusions, set milestones, and export your analysis.',
};

// Comprehensive guidance for each step (matching ArkhamMirror)
export interface GuidanceSection {
  heading: string;
  items?: string[];
  text?: string;
}

export interface StepGuidance {
  title: string;
  sections: GuidanceSection[];
}

export const STEP_GUIDANCE: Record<number, StepGuidance> = {
  1: {
    title: "STEP 1: IDENTIFY HYPOTHESES",
    sections: [
      {
        heading: "Best Practices",
        items: [
          "List ALL plausible explanations, not just likely ones",
          "Include a 'null hypothesis' - what if nothing unusual happened?",
          "Consider adversarial perspectives: What would a skeptic argue?",
          "If working with a team, brainstorm together before individual analysis",
        ],
      },
      {
        heading: "Tip",
        text: "You can always add more hypotheses later if you discover alternatives you hadn't considered.",
      },
    ],
  },
  2: {
    title: "STEP 2: LIST EVIDENCE",
    sections: [
      {
        heading: "What counts as evidence",
        items: [
          "Facts you can verify",
          "Documents and records",
          "Witness statements and testimony",
          "Physical observations",
        ],
      },
      {
        heading: "Also include",
        items: [
          "Key assumptions you're making",
          "Logical arguments or inferences",
          "Absence of expected evidence (significant gaps)",
        ],
      },
      {
        heading: "Reliability Ratings",
        items: [
          "HIGH: Verified, multiple sources, no reason to doubt",
          "MEDIUM: Single source, plausible, unverified",
          "LOW: Uncertain source, possible deception, hearsay",
        ],
      },
    ],
  },
  3: {
    title: "STEP 3: RATE THE MATRIX",
    sections: [
      {
        heading: "Key Question",
        text: "For each cell, ask: 'If this hypothesis is true, how likely is it that I would see this evidence?'",
      },
      {
        heading: "Rating Scale",
        items: [
          "CC (Very Consistent) - Evidence strongly supports",
          "C (Consistent) - Evidence somewhat supports",
          "N (Neutral) - Evidence neither helps nor hurts",
          "I (Inconsistent) - Evidence somewhat contradicts",
          "II (Very Inconsistent) - Evidence strongly contradicts",
        ],
      },
      {
        heading: "Key Insight",
        text: "Focus on INCONSISTENCIES. The winning hypothesis isn't the one with most support - it's the one with LEAST contradiction.",
      },
    ],
  },
  4: {
    title: "STEP 4: ANALYZE DIAGNOSTICITY",
    sections: [
      {
        heading: "What is Diagnosticity?",
        text: "'Diagnostic' evidence helps you distinguish between hypotheses.",
      },
      {
        heading: "HIGH DIAGNOSTIC VALUE (helpful)",
        items: [
          "Evidence rated differently across hypotheses",
          "Example: 'CC' for H1, 'II' for H2 - this discriminates!",
        ],
      },
      {
        heading: "LOW DIAGNOSTIC VALUE (less helpful)",
        items: [
          "Evidence rated the same for all hypotheses",
          "Example: 'N' for H1, H2, H3, H4 - doesn't help choose",
        ],
      },
      {
        heading: "Visual Indicators",
        items: [
          "GOLD highlighting = high diagnostic value",
          "GRAY highlighting = low diagnostic value",
          "Consider removing non-diagnostic evidence to simplify",
        ],
      },
    ],
  },
  5: {
    title: "STEP 5: REFINE THE MATRIX",
    sections: [
      {
        heading: "1. Review Non-Diagnostic Evidence",
        items: [
          "Look at gray-highlighted rows",
          "Does this evidence actually help distinguish?",
          "Should I remove it to simplify the analysis?",
        ],
      },
      {
        heading: "2. Reconsider Hypotheses",
        items: [
          "Are any hypotheses essentially the same? Merge them.",
          "Did you think of new alternatives? Add them.",
          "Is one hypothesis clearly wrong? Consider removing.",
        ],
      },
      {
        heading: "3. Check for Gaps",
        items: [
          "What evidence are you missing?",
          "What would definitively prove/disprove a hypothesis?",
          "Can you obtain that evidence?",
        ],
      },
      {
        heading: "Note",
        text: "This step is ITERATIVE. You may return here multiple times.",
      },
    ],
  },
  6: {
    title: "STEP 6: DRAW TENTATIVE CONCLUSIONS",
    sections: [
      {
        heading: "Reading the Scores",
        items: [
          "Lower score = fewer inconsistencies = more likely true",
          "The hypothesis with the LOWEST score is the best fit",
        ],
      },
      {
        heading: "Important Caveats",
        items: [
          "Scores are NOT probabilities",
          "A low score doesn't mean 'definitely true'",
          "A high score doesn't mean 'definitely false'",
          "Scores depend on evidence quality and rating accuracy",
        ],
      },
      {
        heading: "If Scores Are Close",
        items: [
          "You need more evidence that discriminates between them",
          "Reconsider your rating accuracy",
          "Accept that you may not have a clear answer yet",
        ],
      },
      {
        heading: "Visual Guide",
        text: "The bar chart shows relative scores. Green = low score (good). Red = high score (problematic).",
      },
    ],
  },
  7: {
    title: "STEP 7: SENSITIVITY ANALYSIS",
    sections: [
      {
        heading: "Test the Robustness of Your Conclusion",
        text: "Before finalizing, ask yourself these critical questions:",
      },
      {
        heading: "1. What if my most important evidence is WRONG?",
        items: [
          "Identify the 2-3 pieces of evidence that most influenced your conclusion",
          "For each: What if it's inaccurate, deceptive, or misinterpreted?",
          "Would your conclusion change?",
        ],
      },
      {
        heading: "2. What assumptions am I making?",
        items: [
          "List assumptions underlying your ratings",
          "Which are well-supported? Which are guesses?",
          "What if a key assumption is wrong?",
        ],
      },
      {
        heading: "3. Is any evidence from an unreliable source?",
        items: [
          "Review the reliability ratings you assigned",
          "Be especially skeptical of LOW reliability evidence that heavily influenced your conclusion",
        ],
      },
      {
        heading: "Record Your Notes",
        text: "Use the Sensitivity Notes field to document your key vulnerabilities and what would change your conclusion.",
      },
    ],
  },
  8: {
    title: "STEP 8: REPORT & SET MILESTONES",
    sections: [
      {
        heading: "Reporting Your Conclusions",
        items: [
          "Export your analysis to share with stakeholders",
          "The report includes your focus question, all hypotheses with rankings, full evidence matrix, consistency warnings, and sensitivity notes",
        ],
      },
      {
        heading: "Setting Milestones (Critical)",
        text: "For EACH hypothesis, answer: 'If this hypothesis is true, what would we expect to see in the future?'",
      },
      {
        heading: "Examples",
        items: [
          "H1 (Embezzlement): 'Expect to find hidden accounts'",
          "H2 (Incompetence): 'Expect similar errors in other depts'",
          "H3 (Deliberate fraud): 'Expect more whistleblowers'",
        ],
      },
      {
        heading: "Why Milestones Matter",
        items: [
          "Validate your conclusion over time",
          "Know when to revisit and update your analysis",
          "Demonstrate the scientific rigor of your process",
        ],
      },
    ],
  },
};
