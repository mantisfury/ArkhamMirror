import { useState } from 'react';
import { useACHStore } from '../../store/useACHStore';
import { Button, TextArea } from '../ui';
import { AlertTriangle, CheckCircle, Play, Save } from 'lucide-react';
import { GuidancePanel } from '../GuidancePanel';

export function StepSensitivity() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const runSensitivityAnalysis = useACHStore((state) => state.runSensitivityAnalysis);
  const updateAnalysis = useACHStore((state) => state.updateAnalysis);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const markStepComplete = useACHStore((state) => state.markStepComplete);

  const [sensitivityNotes, setSensitivityNotes] = useState(analysis?.sensitivityNotes || '');
  const [hasRun, setHasRun] = useState(false);
  const [results, setResults] = useState<ReturnType<typeof runSensitivityAnalysis>>([]);

  if (!analysis) return null;

  const handleRun = () => {
    const sensitivityResults = runSensitivityAnalysis();
    setResults(sensitivityResults);
    setHasRun(true);

    // Mark step complete
    if (!analysis.stepsCompleted.includes(7)) {
      markStepComplete(7);
    }
  };

  const handleSaveNotes = () => {
    updateAnalysis({ sensitivityNotes });
  };

  const criticalEvidence = results.filter((r) => r.isCritical);

  return (
    <div className="space-y-6">
      {/* Guidance */}
      {showStepGuidance && <GuidancePanel step={7} />}

      {/* Run Button */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-white">Sensitivity Analysis</h3>
          <p className="text-sm text-gray-400">
            Test how robust your conclusion is to changes in evidence
          </p>
        </div>
        <Button onClick={handleRun} icon={<Play className="w-4 h-4" />}>
          {hasRun ? 'Re-run Analysis' : 'Run Analysis'}
        </Button>
      </div>

      {/* Results */}
      {hasRun && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
              <div className="text-3xl font-bold text-white">{results.length}</div>
              <div className="text-sm text-gray-400">Evidence Items Tested</div>
            </div>
            <div className={`rounded-lg border p-4 ${
              criticalEvidence.length > 0
                ? 'bg-red-900/30 border-red-800'
                : 'bg-green-900/30 border-green-800'
            }`}>
              <div className={`text-3xl font-bold ${
                criticalEvidence.length > 0 ? 'text-red-400' : 'text-green-400'
              }`}>
                {criticalEvidence.length}
              </div>
              <div className={`text-sm ${
                criticalEvidence.length > 0 ? 'text-red-300/70' : 'text-green-300/70'
              }`}>
                Critical Evidence Items
              </div>
            </div>
          </div>

          {/* Critical Evidence Alert */}
          {criticalEvidence.length > 0 && (
            <div className="bg-red-900/30 border border-red-800 rounded-lg p-4">
              <div className="flex gap-3">
                <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-red-200 font-medium">Critical Evidence Found</p>
                  <p className="text-red-300/70 text-sm mt-1">
                    {criticalEvidence.length} evidence item{criticalEvidence.length > 1 ? 's' : ''} would
                    change the winning hypothesis if removed. Double-check the reliability of these items.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* No Critical Evidence */}
          {criticalEvidence.length === 0 && results.length > 0 && (
            <div className="bg-green-900/30 border border-green-800 rounded-lg p-4">
              <div className="flex gap-3">
                <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-green-200 font-medium">Robust Conclusion</p>
                  <p className="text-green-300/70 text-sm mt-1">
                    No single piece of evidence would change the winner if removed.
                    Your conclusion appears to be well-supported.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Results List */}
          <div className="space-y-2">
            <h4 className="text-white font-medium">Evidence Impact Analysis</h4>
            {results.map((result) => {
              const evidence = analysis.evidence.find((e) => e.id === result.evidenceId);

              return (
                <div
                  key={result.evidenceId}
                  className={`flex items-center gap-4 p-3 rounded-lg border ${
                    result.isCritical
                      ? 'bg-red-900/20 border-red-800'
                      : 'bg-gray-800 border-gray-700'
                  }`}
                >
                  {/* Status Icon */}
                  {result.isCritical ? (
                    <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
                  ) : (
                    <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                  )}

                  {/* Evidence Label */}
                  <span className="font-bold text-white min-w-[50px]">
                    {result.evidenceLabel}
                  </span>

                  {/* Description */}
                  <span className="flex-1 text-gray-400 text-sm truncate">
                    {evidence?.description}
                  </span>

                  {/* Impact */}
                  {result.isCritical ? (
                    <span className="text-red-400 text-sm">
                      Winner changes: {result.originalWinner} → {result.winnerIfRemoved}
                    </span>
                  ) : (
                    <span className="text-gray-500 text-sm">
                      No change
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Sensitivity Notes */}
      <div className="space-y-3">
        <h4 className="text-white font-medium">Analysis Notes</h4>
        <p className="text-sm text-gray-400">
          Document key assumptions, vulnerabilities, and anything that could change your conclusion.
        </p>
        <TextArea
          value={sensitivityNotes}
          onChange={(e) => setSensitivityNotes(e.target.value)}
          placeholder="What assumptions underlie your analysis? What evidence would change your conclusion? What are the key uncertainties?"
          rows={6}
        />
        <div className="flex justify-end">
          <Button
            onClick={handleSaveNotes}
            variant="secondary"
            icon={<Save className="w-4 h-4" />}
            disabled={sensitivityNotes === analysis.sensitivityNotes}
          >
            Save Notes
          </Button>
        </div>
      </div>
    </div>
  );
}
