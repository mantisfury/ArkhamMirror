/**
 * ACH Guidance Panel Component
 *
 * Provides contextual guidance for each step of Heuer's 8-step ACH methodology.
 */

import { useState } from 'react';
import { Icon } from '../../../components/common/Icon';

// Guidance content for each step
const STEP_GUIDANCE: Record<number, {
  title: string;
  icon: string;
  color: string;
  sections: Array<{
    heading: string;
    items?: string[];
    text?: string;
  }>;
}> = {
  1: {
    title: 'STEP 1: IDENTIFY HYPOTHESES',
    icon: 'Lightbulb',
    color: 'blue',
    sections: [
      {
        heading: 'Best Practices',
        items: [
          'List ALL plausible explanations, not just likely ones',
          'Include a \'null hypothesis\' - what if nothing unusual happened?',
          'Consider adversarial perspectives: What would a skeptic argue?',
          'If working with a team, brainstorm together before individual analysis',
        ],
      },
      {
        heading: 'Tip',
        text: 'You can always add more hypotheses later if you discover alternatives you hadn\'t considered.',
      },
    ],
  },
  2: {
    title: 'STEP 2: LIST EVIDENCE',
    icon: 'FileText',
    color: 'green',
    sections: [
      {
        heading: 'What counts as evidence',
        items: [
          'Facts you can verify',
          'Documents and records',
          'Witness statements and testimony',
          'Physical observations',
        ],
      },
      {
        heading: 'Also include',
        items: [
          'Key assumptions you\'re making',
          'Logical arguments or inferences',
          'Absence of expected evidence (significant gaps)',
        ],
      },
      {
        heading: 'Credibility Ratings',
        items: [
          'HIGH: Verified, multiple sources, no reason to doubt',
          'MEDIUM: Single source, plausible, unverified',
          'LOW: Uncertain source, possible deception, hearsay',
        ],
      },
    ],
  },
  3: {
    title: 'STEP 3: RATE THE MATRIX',
    icon: 'Grid3X3',
    color: 'purple',
    sections: [
      {
        heading: 'Key Question',
        text: 'For each cell, ask: \'If this hypothesis is true, how likely is it that I would see this evidence?\'',
      },
      {
        heading: 'Rating Scale',
        items: [
          '++ (Highly Consistent) - Evidence strongly supports',
          '+ (Consistent) - Evidence somewhat supports',
          'N (Neutral) - Evidence neither helps nor hurts',
          '- (Inconsistent) - Evidence somewhat contradicts',
          '-- (Highly Inconsistent) - Evidence strongly contradicts',
        ],
      },
      {
        heading: 'Key Insight',
        text: 'Focus on INCONSISTENCIES. The winning hypothesis isn\'t the one with most support - it\'s the one with LEAST contradiction.',
      },
    ],
  },
  4: {
    title: 'STEP 4: ANALYZE DIAGNOSTICITY',
    icon: 'BarChart2',
    color: 'amber',
    sections: [
      {
        heading: 'What is Diagnosticity?',
        text: '\'Diagnostic\' evidence helps you distinguish between hypotheses.',
      },
      {
        heading: 'HIGH DIAGNOSTIC VALUE (helpful)',
        items: [
          'Evidence rated differently across hypotheses',
          'Example: \'++\' for H1, \'--\' for H2 - this discriminates!',
        ],
      },
      {
        heading: 'LOW DIAGNOSTIC VALUE (less helpful)',
        items: [
          'Evidence rated the same for all hypotheses',
          'Example: \'N\' for H1, H2, H3, H4 - doesn\'t help choose',
        ],
      },
      {
        heading: 'Visual Indicators',
        items: [
          'GOLD highlighting = high diagnostic value',
          'GRAY highlighting = low diagnostic value',
          'Consider removing non-diagnostic evidence to simplify',
        ],
      },
    ],
  },
  5: {
    title: 'STEP 5: REFINE THE MATRIX',
    icon: 'PencilLine',
    color: 'cyan',
    sections: [
      {
        heading: '1. Review Non-Diagnostic Evidence',
        items: [
          'Look at gray-highlighted rows',
          'Does this evidence actually help distinguish?',
          'Should I remove it to simplify the analysis?',
        ],
      },
      {
        heading: '2. Reconsider Hypotheses',
        items: [
          'Are any hypotheses essentially the same? Merge them.',
          'Did you think of new alternatives? Add them.',
          'Is one hypothesis clearly wrong? Consider removing.',
        ],
      },
      {
        heading: '3. Check for Gaps',
        items: [
          'What evidence are you missing?',
          'What would definitively prove/disprove a hypothesis?',
          'Can you obtain that evidence?',
        ],
      },
      {
        heading: 'Note',
        text: 'This step is ITERATIVE. You may return here multiple times.',
      },
    ],
  },
  6: {
    title: 'STEP 6: DRAW TENTATIVE CONCLUSIONS',
    icon: 'Target',
    color: 'red',
    sections: [
      {
        heading: 'Reading the Scores',
        items: [
          'Lower score = fewer inconsistencies = more likely true',
          'The hypothesis with the LOWEST score is the best fit',
        ],
      },
      {
        heading: 'Important Caveats',
        items: [
          'Scores are NOT probabilities',
          'A low score doesn\'t mean \'definitely true\'',
          'A high score doesn\'t mean \'definitely false\'',
          'Scores depend on evidence quality and rating accuracy',
        ],
      },
      {
        heading: 'If Scores Are Close',
        items: [
          'You need more evidence that discriminates between them',
          'Reconsider your rating accuracy',
          'Accept that you may not have a clear answer yet',
        ],
      },
      {
        heading: 'Visual Guide',
        text: 'The bar chart shows relative scores. Green = low score (good). Red = high score (problematic).',
      },
    ],
  },
  7: {
    title: 'STEP 7: SENSITIVITY ANALYSIS',
    icon: 'ShieldQuestion',
    color: 'orange',
    sections: [
      {
        heading: 'Test the Robustness of Your Conclusion',
        text: 'Before finalizing, ask yourself these critical questions:',
      },
      {
        heading: '1. What if my most important evidence is WRONG?',
        items: [
          'Identify the 2-3 pieces of evidence that most influenced your conclusion',
          'For each: What if it\'s inaccurate, deceptive, or misinterpreted?',
          'Would your conclusion change?',
        ],
      },
      {
        heading: '2. What assumptions am I making?',
        items: [
          'List assumptions underlying your ratings',
          'Which are well-supported? Which are guesses?',
          'What if a key assumption is wrong?',
        ],
      },
      {
        heading: '3. Is any evidence from an unreliable source?',
        items: [
          'Review the credibility ratings you assigned',
          'Be especially skeptical of LOW credibility evidence that heavily influenced your conclusion',
        ],
      },
      {
        heading: 'Record Your Notes',
        text: 'Use the Sensitivity Notes field to document your key vulnerabilities and what would change your conclusion.',
      },
    ],
  },
  8: {
    title: 'STEP 8: REPORT & SET MILESTONES',
    icon: 'FileOutput',
    color: 'violet',
    sections: [
      {
        heading: 'Reporting Your Conclusions',
        items: [
          'Export your analysis to share with stakeholders',
          'The report includes your focus question, all hypotheses with rankings, full evidence matrix, consistency warnings, and sensitivity notes',
        ],
      },
      {
        heading: 'Setting Milestones (Critical)',
        text: 'For EACH hypothesis, answer: \'If this hypothesis is true, what would we expect to see in the future?\'',
      },
      {
        heading: 'Examples',
        items: [
          'H1 (Embezzlement): \'Expect to find hidden accounts\'',
          'H2 (Incompetence): \'Expect similar errors in other depts\'',
          'H3 (Deliberate fraud): \'Expect more whistleblowers\'',
        ],
      },
      {
        heading: 'Why Milestones Matter',
        items: [
          'Validate your conclusion over time',
          'Know when to revisit and update your analysis',
          'Demonstrate the scientific rigor of your process',
        ],
      },
    ],
  },
};

interface GuidancePanelProps {
  currentStep: number;
  defaultExpanded?: boolean;
}

export function GuidancePanel({ currentStep, defaultExpanded = true }: GuidancePanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const guidance = STEP_GUIDANCE[currentStep];

  if (!guidance) return null;

  const colorVars: Record<string, string> = {
    blue: '--accent-primary',
    green: '--success',
    purple: '--accent-secondary',
    amber: '--warning',
    cyan: '--accent-primary',
    red: '--error',
    orange: '--warning',
    violet: '--accent-secondary',
  };

  const bgColor = `var(${colorVars[guidance.color] || '--accent-primary'})`;

  return (
    <div
      className="guidance-panel"
      style={{
        borderLeft: `4px solid ${bgColor}`,
        backgroundColor: `color-mix(in srgb, ${bgColor} 10%, var(--bg-secondary))`,
      }}
    >
      <div className="guidance-header" onClick={() => setExpanded(!expanded)}>
        <div className="guidance-title">
          <Icon name={guidance.icon} size={18} />
          <span>{guidance.title}</span>
        </div>
        <button className="btn btn-icon btn-sm">
          <Icon name={expanded ? 'ChevronUp' : 'ChevronDown'} size={14} />
        </button>
      </div>

      {expanded && (
        <div className="guidance-content">
          {guidance.sections.map((section, index) => (
            <div key={index} className="guidance-section">
              <h4 className="guidance-section-heading">{section.heading}</h4>
              {section.text && (
                <p className="guidance-section-text">{section.text}</p>
              )}
              {section.items && (
                <ul className="guidance-section-items">
                  {section.items.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export { STEP_GUIDANCE };
