import { useState } from 'react';
import { useACHStore } from '../store/useACHStore';
import { STEP_NAMES } from '../types';
import { StepIndicator } from './StepIndicator';
import { StepHypotheses } from './steps/StepHypotheses';
import { StepEvidence } from './steps/StepEvidence';
import { StepMatrix } from './steps/StepMatrix';
import { StepDiagnosticity } from './steps/StepDiagnosticity';
import { StepRefine } from './steps/StepRefine';
import { StepConclusions } from './steps/StepConclusions';
import { StepSensitivity } from './steps/StepSensitivity';
import { StepReport } from './steps/StepReport';
import { LLMSettings } from './LLMSettings';
import { ArrowLeft, ChevronLeft, ChevronRight, HelpCircle, Settings } from 'lucide-react';
import { Button } from './ui/Button';

export function AnalysisView() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const currentStep = useACHStore((state) => state.currentStep);
  const closeAnalysis = useACHStore((state) => state.closeAnalysis);
  const goToStep = useACHStore((state) => state.goToStep);
  const nextStep = useACHStore((state) => state.nextStep);
  const prevStep = useACHStore((state) => state.prevStep);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const setShowStepGuidance = useACHStore((state) => state.setShowStepGuidance);
  const llmConfig = useACHStore((state) => state.llmConfig);

  const [showLLMSettings, setShowLLMSettings] = useState(false);

  if (!analysis) return null;

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return <StepHypotheses />;
      case 2:
        return <StepEvidence />;
      case 3:
        return <StepMatrix />;
      case 4:
        return <StepDiagnosticity />;
      case 5:
        return <StepRefine />;
      case 6:
        return <StepConclusions />;
      case 7:
        return <StepSensitivity />;
      case 8:
        return <StepReport />;
      default:
        return <StepHypotheses />;
    }
  };

  // Determine if navigation should be enabled
  const canGoNext = () => {
    switch (currentStep) {
      case 1:
        return analysis.hypotheses.length >= 2;
      case 2:
        return analysis.evidence.length >= 1;
      case 3:
        return analysis.ratings.length > 0;
      default:
        return currentStep < 8;
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Navigation */}
      <header className="bg-gray-800 border-b border-gray-700 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={closeAnalysis}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span>Back to List</span>
            </button>
            <div className="h-6 w-px bg-gray-700" />
            <div>
              <h1 className="text-lg font-semibold text-white">{analysis.title}</h1>
              <p className="text-sm text-gray-400 truncate max-w-md">{analysis.focusQuestion}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowLLMSettings(true)}
              className={`p-2 rounded-lg transition-colors ${
                llmConfig.enabled
                  ? 'bg-green-600/20 text-green-400 hover:bg-green-600/30'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
              title={llmConfig.enabled ? 'LLM Enabled - Click to configure' : 'LLM Settings'}
            >
              <Settings className="w-5 h-5" />
            </button>
            <button
              onClick={() => setShowStepGuidance(!showStepGuidance)}
              className={`p-2 rounded-lg transition-colors ${
                showStepGuidance ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
              title="Toggle step guidance"
            >
              <HelpCircle className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Step Indicator */}
      <div className="bg-gray-850 border-b border-gray-700 px-4 py-4">
        <div className="max-w-7xl mx-auto">
          <StepIndicator
            currentStep={currentStep}
            stepsCompleted={analysis.stepsCompleted}
            onStepClick={goToStep}
          />
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-6">
          {/* Step Title */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-white">
              Step {currentStep}: {STEP_NAMES[currentStep]}
            </h2>
          </div>

          {/* Step Content */}
          {renderStep()}
        </div>
      </main>

      {/* Bottom Navigation */}
      <footer className="bg-gray-800 border-t border-gray-700 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Button
            variant="secondary"
            onClick={prevStep}
            disabled={currentStep === 1}
            icon={<ChevronLeft className="w-4 h-4" />}
          >
            Previous
          </Button>

          <div className="text-sm text-gray-400">
            Step {currentStep} of 8
          </div>

          <Button
            onClick={nextStep}
            disabled={!canGoNext()}
            className="flex-row-reverse"
          >
            <ChevronRight className="w-4 h-4" />
            {currentStep === 8 ? 'Finish' : 'Next'}
          </Button>
        </div>
      </footer>

      {/* LLM Settings Dialog */}
      <LLMSettings open={showLLMSettings} onClose={() => setShowLLMSettings(false)} />
    </div>
  );
}
