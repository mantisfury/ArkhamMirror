import { useACHStore } from '../../store/useACHStore';
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { GuidancePanel } from '../GuidancePanel';

export function StepDiagnosticity() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const calculateDiagnosticity = useACHStore((state) => state.calculateDiagnosticity);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const markStepComplete = useACHStore((state) => state.markStepComplete);

  if (!analysis) return null;

  const diagnosticity = calculateDiagnosticity();

  // Sort by diagnosticity score (high to low)
  const sortedDiagnosticity = [...diagnosticity].sort(
    (a, b) => b.diagnosticityScore - a.diagnosticityScore
  );

  const highDiagnostic = sortedDiagnosticity.filter((d) => d.isHighDiagnostic);
  const lowDiagnostic = sortedDiagnosticity.filter((d) => d.isLowDiagnostic);

  // Mark step complete when viewed with ratings
  if (analysis.ratings.length > 0 && !analysis.stepsCompleted.includes(4)) {
    markStepComplete(4);
  }

  return (
    <div className="space-y-6">
      {/* Guidance */}
      {showStepGuidance && <GuidancePanel step={4} />}

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 text-center">
          <div className="text-3xl font-bold text-white">{diagnosticity.length}</div>
          <div className="text-sm text-gray-400">Total Evidence</div>
        </div>
        <div className="bg-green-900/30 rounded-lg border border-green-800 p-4 text-center">
          <div className="text-3xl font-bold text-green-400">{highDiagnostic.length}</div>
          <div className="text-sm text-green-300/70">High Diagnostic</div>
        </div>
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 text-center">
          <div className="text-3xl font-bold text-gray-400">{lowDiagnostic.length}</div>
          <div className="text-sm text-gray-500">Low Diagnostic</div>
        </div>
      </div>

      {/* High Diagnostic Alert */}
      {highDiagnostic.length === 0 && diagnosticity.length > 0 && (
        <div className="bg-yellow-900/30 border border-yellow-800 rounded-lg p-4">
          <div className="flex gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-yellow-200 font-medium">No highly diagnostic evidence found</p>
              <p className="text-yellow-300/70 text-sm mt-1">
                All your evidence rates similarly across hypotheses. Look for evidence that clearly distinguishes between them.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Evidence List by Diagnosticity */}
      <div className="space-y-4">
        <h3 className="text-lg font-medium text-white">Evidence by Diagnosticity</h3>

        {sortedDiagnosticity.length === 0 ? (
          <div className="text-center py-8 bg-gray-800 rounded-lg border border-gray-700">
            <p className="text-gray-400">No evidence to analyze. Add evidence and rate it in the matrix.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {sortedDiagnosticity.map((item) => {
              const evidence = analysis.evidence.find((e) => e.id === item.evidenceId);
              if (!evidence) return null;

              return (
                <div
                  key={item.evidenceId}
                  className={`flex items-center gap-4 p-4 rounded-lg border ${
                    item.isHighDiagnostic
                      ? 'bg-green-900/20 border-green-800'
                      : item.isLowDiagnostic
                        ? 'bg-gray-800/50 border-gray-700'
                        : 'bg-gray-800 border-gray-700'
                  }`}
                >
                  {/* Diagnostic Icon */}
                  <div className="flex-shrink-0">
                    {item.isHighDiagnostic ? (
                      <TrendingUp className="w-5 h-5 text-green-400" />
                    ) : item.isLowDiagnostic ? (
                      <TrendingDown className="w-5 h-5 text-gray-500" />
                    ) : (
                      <Minus className="w-5 h-5 text-gray-400" />
                    )}
                  </div>

                  {/* Label */}
                  <div className="w-12 text-center">
                    <span className="font-bold text-white">{evidence.label}</span>
                  </div>

                  {/* Score Bar */}
                  <div className="w-24 flex-shrink-0">
                    <div className="bg-gray-700 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${
                          item.isHighDiagnostic ? 'bg-green-500' : item.isLowDiagnostic ? 'bg-gray-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${Math.min(item.diagnosticityScore * 50, 100)}%` }}
                      />
                    </div>
                    <div className="text-xs text-gray-500 mt-1 text-center">
                      {item.diagnosticityScore.toFixed(2)}
                    </div>
                  </div>

                  {/* Description */}
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm truncate ${item.isLowDiagnostic ? 'text-gray-500' : 'text-gray-300'}`}>
                      {evidence.description}
                    </p>
                  </div>

                  {/* Badge */}
                  {item.isHighDiagnostic && (
                    <span className="px-2 py-1 bg-green-900 text-green-300 text-xs rounded-full">
                      HIGH
                    </span>
                  )}
                  {item.isLowDiagnostic && (
                    <span className="px-2 py-1 bg-gray-700 text-gray-400 text-xs rounded-full">
                      LOW
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Interpretation Guide */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h4 className="text-white font-medium mb-2">Interpreting Diagnosticity</h4>
        <ul className="text-sm text-gray-400 space-y-1">
          <li><span className="text-green-400">High diagnostic</span>: Different ratings across hypotheses - helps distinguish</li>
          <li><span className="text-gray-400">Low diagnostic</span>: Similar ratings across hypotheses - doesn't help decide</li>
          <li>Consider removing or re-evaluating low diagnostic evidence</li>
        </ul>
      </div>
    </div>
  );
}
