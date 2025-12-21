import { useACHStore } from '../../store/useACHStore';
import { RATING_COLORS, RATING_LABELS, Rating } from '../../types';
import { AlertCircle, TrendingUp } from 'lucide-react';
import { GuidancePanel } from '../GuidancePanel';

const RATING_OPTIONS: Rating[] = ['CC', 'C', 'N', 'I', 'II'];

export function StepRefine() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const setRating = useACHStore((state) => state.setRating);
  const getRating = useACHStore((state) => state.getRating);
  const calculateDiagnosticity = useACHStore((state) => state.calculateDiagnosticity);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const markStepComplete = useACHStore((state) => state.markStepComplete);
  const sortEvidenceBy = useACHStore((state) => state.sortEvidenceBy);
  const setSortEvidenceBy = useACHStore((state) => state.setSortEvidenceBy);
  const evidenceFilter = useACHStore((state) => state.evidenceFilter);
  const setEvidenceFilter = useACHStore((state) => state.setEvidenceFilter);

  if (!analysis) return null;

  const { hypotheses, evidence } = analysis;
  const diagnosticity = calculateDiagnosticity();

  // Get evidence with diagnosticity info
  const evidenceWithDiag = evidence.map((e) => {
    const diag = diagnosticity.find((d) => d.evidenceId === e.id);
    return { ...e, diagnosticity: diag };
  });

  // Sort evidence
  let sortedEvidence = [...evidenceWithDiag];
  if (sortEvidenceBy === 'diagnosticity') {
    sortedEvidence.sort((a, b) =>
      (b.diagnosticity?.diagnosticityScore || 0) - (a.diagnosticity?.diagnosticityScore || 0)
    );
  }

  // Filter evidence
  if (evidenceFilter === 'unrated') {
    sortedEvidence = sortedEvidence.filter((e) => {
      const hasUnrated = hypotheses.some((h) => !getRating(e.id, h.id));
      return hasUnrated;
    });
  } else if (evidenceFilter === 'high_diagnostic') {
    sortedEvidence = sortedEvidence.filter((e) => e.diagnosticity?.isHighDiagnostic);
  }

  // Mark step complete when viewed
  if (analysis.ratings.length > 0 && !analysis.stepsCompleted.includes(5)) {
    markStepComplete(5);
  }

  const unratedCount = evidence.filter((e) =>
    hypotheses.some((h) => !getRating(e.id, h.id))
  ).length;

  return (
    <div className="space-y-6">
      {/* Guidance */}
      {showStepGuidance && <GuidancePanel step={5} />}

      {/* Filters and Sorting */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">Sort by:</span>
          <select
            value={sortEvidenceBy}
            onChange={(e) => setSortEvidenceBy(e.target.value as 'order' | 'diagnosticity')}
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-white"
          >
            <option value="order">Original Order</option>
            <option value="diagnosticity">Diagnosticity (High First)</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">Filter:</span>
          <select
            value={evidenceFilter}
            onChange={(e) => setEvidenceFilter(e.target.value as 'all' | 'unrated' | 'high_diagnostic')}
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-white"
          >
            <option value="all">All Evidence ({evidence.length})</option>
            <option value="unrated">Unrated ({unratedCount})</option>
            <option value="high_diagnostic">High Diagnostic ({diagnosticity.filter(d => d.isHighDiagnostic).length})</option>
          </select>
        </div>
      </div>

      {/* Unrated Warning */}
      {unratedCount > 0 && (
        <div className="bg-yellow-900/30 border border-yellow-800 rounded-lg p-4">
          <div className="flex gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-yellow-200">
                {unratedCount} evidence item{unratedCount > 1 ? 's have' : ' has'} unrated cells
              </p>
              <p className="text-yellow-300/70 text-sm mt-1">
                Use the filter above to focus on unrated items.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Evidence Cards with Inline Rating */}
      {sortedEvidence.length === 0 ? (
        <div className="text-center py-8 bg-gray-800 rounded-lg border border-gray-700">
          <p className="text-gray-400">No evidence matches the current filter.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {sortedEvidence.map((e) => (
            <div
              key={e.id}
              className={`bg-gray-800 rounded-lg border p-4 ${
                e.diagnosticity?.isHighDiagnostic ? 'border-green-800' : 'border-gray-700'
              }`}
            >
              {/* Evidence Header */}
              <div className="flex items-start gap-3 mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold text-white">{e.label}</span>
                  {e.diagnosticity?.isHighDiagnostic && (
                    <TrendingUp className="w-4 h-4 text-green-400" />
                  )}
                </div>
                <p className="flex-1 text-gray-300">{e.description}</p>
                {e.diagnosticity && (
                  <span className="text-sm text-gray-500">
                    Diag: {e.diagnosticity.diagnosticityScore.toFixed(2)}
                  </span>
                )}
              </div>

              {/* Ratings Row */}
              <div className="flex flex-wrap gap-3">
                {hypotheses.map((h) => {
                  const rating = getRating(e.id, h.id);

                  return (
                    <div key={h.id} className="flex items-center gap-2">
                      {/* Hypothesis label */}
                      <div className="flex items-center gap-1 min-w-[60px]">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: h.color }}
                        />
                        <span className="text-sm text-gray-400">{h.label}</span>
                      </div>

                      {/* Rating buttons */}
                      <div className="flex gap-1">
                        {RATING_OPTIONS.map((r) => (
                          <button
                            key={r}
                            onClick={() => setRating(e.id, h.id, r)}
                            className={`
                              w-8 h-8 rounded text-xs font-bold transition-all
                              ${rating === r
                                ? `${RATING_COLORS[r]} text-white ring-2 ring-offset-1 ring-offset-gray-800 ring-white/50`
                                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                              }
                            `}
                            title={RATING_LABELS[r]}
                          >
                            {r}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
