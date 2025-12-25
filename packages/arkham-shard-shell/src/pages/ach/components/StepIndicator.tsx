/**
 * ACH Step Indicator Component
 *
 * Shows the 8-step ACH methodology progress with clickable steps.
 * Based on Heuer's Analysis of Competing Hypotheses methodology.
 */

import { Icon } from '../../../components/common/Icon';

// Step metadata
const STEP_ICONS: Record<number, string> = {
  1: 'Lightbulb',      // Identify Hypotheses
  2: 'FileText',       // List Evidence
  3: 'Grid3X3',        // Create Matrix
  4: 'BarChart2',      // Analyze Diagnosticity
  5: 'PencilLine',     // Refine the Matrix
  6: 'Target',         // Draw Conclusions
  7: 'ShieldQuestion', // Sensitivity Analysis
  8: 'FileOutput',     // Report & Milestones
};

const STEP_NAMES: Record<number, string> = {
  1: 'Identify Hypotheses',
  2: 'List Evidence',
  3: 'Rate the Matrix',
  4: 'Analyze Diagnosticity',
  5: 'Refine the Matrix',
  6: 'Draw Conclusions',
  7: 'Sensitivity Analysis',
  8: 'Report & Milestones',
};

interface StepIndicatorProps {
  currentStep: number;
  completedSteps: number[];
  onStepClick: (step: number) => void;
  onPrevStep: () => void;
  onNextStep: () => void;
}

export function StepIndicator({
  currentStep,
  completedSteps,
  onStepClick,
  onPrevStep,
  onNextStep,
}: StepIndicatorProps) {
  return (
    <div className="step-indicator">
      <div className="step-indicator-header">
        <div className="step-indicator-title">
          <Icon name="Compass" size={18} />
          <span>ACH Methodology</span>
        </div>
        <span className="step-indicator-progress">Step {currentStep} of 8</span>
      </div>

      <div className="step-circles">
        {[1, 2, 3, 4, 5, 6, 7, 8].map((step) => (
          <div key={step} className="step-wrapper">
            <button
              className={`step-circle ${
                completedSteps.includes(step)
                  ? 'completed'
                  : currentStep === step
                  ? 'current'
                  : 'future'
              }`}
              onClick={() => onStepClick(step)}
              title={STEP_NAMES[step]}
            >
              {completedSteps.includes(step) ? (
                <Icon name="Check" size={14} />
              ) : (
                step
              )}
            </button>
            {step < 8 && (
              <div
                className={`step-connector ${
                  completedSteps.includes(step) ? 'completed' : ''
                }`}
              />
            )}
          </div>
        ))}
      </div>

      <div className="step-indicator-current">
        <div className="current-step-info">
          <Icon name={STEP_ICONS[currentStep]} size={16} />
          <span className="current-step-name">{STEP_NAMES[currentStep]}</span>
        </div>
        <div className="step-nav-buttons">
          <button
            className="btn btn-icon btn-sm"
            onClick={onPrevStep}
            disabled={currentStep <= 1}
            title="Previous step"
          >
            <Icon name="ChevronLeft" size={14} />
          </button>
          <button
            className="btn btn-icon btn-sm"
            onClick={onNextStep}
            disabled={currentStep >= 8}
            title="Next step"
          >
            <Icon name="ChevronRight" size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

// Compact version for smaller spaces
export function StepIndicatorCompact({
  currentStep,
  onPrevStep,
  onNextStep,
}: Pick<StepIndicatorProps, 'currentStep' | 'onPrevStep' | 'onNextStep'>) {
  return (
    <div className="step-indicator-compact">
      <button
        className="btn btn-icon btn-sm"
        onClick={onPrevStep}
        disabled={currentStep <= 1}
      >
        <Icon name="ChevronLeft" size={14} />
      </button>
      <div className="compact-step-info">
        <Icon name={STEP_ICONS[currentStep]} size={16} />
        <span>Step {currentStep}: {STEP_NAMES[currentStep]}</span>
      </div>
      <button
        className="btn btn-icon btn-sm"
        onClick={onNextStep}
        disabled={currentStep >= 8}
      >
        <Icon name="ChevronRight" size={14} />
      </button>
    </div>
  );
}

export { STEP_ICONS, STEP_NAMES };
