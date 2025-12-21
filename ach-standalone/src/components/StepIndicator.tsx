import { Check } from 'lucide-react';
import { STEP_NAMES } from '../types';

interface StepIndicatorProps {
  currentStep: number;
  stepsCompleted: number[];
  onStepClick: (step: number) => void;
}

export function StepIndicator({ currentStep, stepsCompleted, onStepClick }: StepIndicatorProps) {
  const steps = [1, 2, 3, 4, 5, 6, 7, 8];

  return (
    <div className="flex items-center justify-between">
      {steps.map((step, index) => {
        const isCompleted = stepsCompleted.includes(step);
        const isCurrent = step === currentStep;
        const isPast = step < currentStep;

        return (
          <div key={step} className="flex items-center flex-1">
            {/* Step Circle */}
            <button
              onClick={() => onStepClick(step)}
              className={`
                relative flex items-center justify-center w-10 h-10 rounded-full
                font-medium text-sm transition-all step-indicator
                ${isCurrent
                  ? 'bg-blue-600 text-white ring-4 ring-blue-600/30'
                  : isCompleted
                    ? 'bg-green-600 text-white'
                    : isPast
                      ? 'bg-gray-600 text-gray-300'
                      : 'bg-gray-700 text-gray-400'
                }
                hover:scale-110
              `}
              title={STEP_NAMES[step]}
            >
              {isCompleted && !isCurrent ? (
                <Check className="w-5 h-5" />
              ) : (
                step
              )}
            </button>

            {/* Connector Line */}
            {index < steps.length - 1 && (
              <div className="flex-1 mx-2">
                <div
                  className={`h-1 rounded-full transition-colors ${
                    step < currentStep || isCompleted
                      ? 'bg-green-600'
                      : 'bg-gray-700'
                  }`}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
