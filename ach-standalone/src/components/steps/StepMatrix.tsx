import { useState, useCallback } from 'react';
import { useACHStore } from '../../store/useACHStore';
import { RATING_LABELS, RATING_COLORS, Rating, Evidence } from '../../types';
import { Info, Sparkles, Loader2, AlertCircle, Check } from 'lucide-react';
import { GuidancePanel } from '../GuidancePanel';
import { Button, Dialog } from '../ui';
import { suggestRatings, RatingSuggestion } from '../../services/llmService';

const RATING_OPTIONS: Rating[] = ['CC', 'C', 'N', 'I', 'II'];

export function StepMatrix() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const setRating = useACHStore((state) => state.setRating);
  const getRating = useACHStore((state) => state.getRating);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const getMatrixCompletion = useACHStore((state) => state.getMatrixCompletion);
  const markStepComplete = useACHStore((state) => state.markStepComplete);
  const llmConfig = useACHStore((state) => state.llmConfig);

  const [focusedCell, setFocusedCell] = useState<{ eId: string; hId: string } | null>(null);

  // AI rating suggestion state
  const [isLoadingAI, setIsLoadingAI] = useState(false);
  const [loadingEvidenceId, setLoadingEvidenceId] = useState<string | null>(null);
  const [aiSuggestions, setAiSuggestions] = useState<RatingSuggestion[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [showAISuggestions, setShowAISuggestions] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  if (!analysis) return null;

  const { hypotheses, evidence } = analysis;
  const completion = getMatrixCompletion();

  // Handle keyboard shortcuts for rating
  const handleKeyDown = useCallback((e: React.KeyboardEvent, evidenceId: string, hypothesisId: string) => {
    const keyMap: Record<string, Rating> = {
      '1': 'CC',
      '2': 'C',
      '3': 'N',
      '4': 'I',
      '5': 'II',
    };

    if (keyMap[e.key]) {
      e.preventDefault();
      setRating(evidenceId, hypothesisId, keyMap[e.key]);
    }
  }, [setRating]);

  // Handle AI rating suggestions for a row
  const handleAISuggest = async (evidenceItem: Evidence) => {
    if (!llmConfig.enabled) return;

    setIsLoadingAI(true);
    setLoadingEvidenceId(evidenceItem.id);
    setAiError(null);
    setAiSuggestions([]);
    setSelectedEvidence(evidenceItem);

    const result = await suggestRatings(
      llmConfig,
      analysis.focusQuestion,
      evidenceItem,
      hypotheses
    );

    setIsLoadingAI(false);
    setLoadingEvidenceId(null);

    if (result.success && result.suggestions.length > 0) {
      setAiSuggestions(result.suggestions);
      setShowAISuggestions(true);
    } else {
      setAiError(result.error || 'No suggestions received. Try again.');
    }
  };

  // Accept a single AI suggestion
  const acceptSuggestion = (suggestion: RatingSuggestion) => {
    if (selectedEvidence) {
      setRating(selectedEvidence.id, suggestion.hypothesisId, suggestion.rating as Rating);
    }
  };

  // Accept all AI suggestions
  const acceptAllSuggestions = () => {
    if (selectedEvidence) {
      for (const suggestion of aiSuggestions) {
        setRating(selectedEvidence.id, suggestion.hypothesisId, suggestion.rating as Rating);
      }
      setShowAISuggestions(false);
    }
  };

  // Mark step complete when ratings exist
  if (analysis.ratings.length > 0 && !analysis.stepsCompleted.includes(3)) {
    markStepComplete(3);
  }

  if (hypotheses.length === 0 || evidence.length === 0) {
    return (
      <div className="text-center py-12 bg-gray-800 rounded-lg border border-gray-700">
        <Info className="w-12 h-12 text-gray-500 mx-auto mb-4" />
        <p className="text-gray-400">
          You need at least 2 hypotheses and 1 piece of evidence to create the matrix.
        </p>
        <p className="text-gray-500 text-sm mt-2">
          Go back to Steps 1 and 2 to add them.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Guidance */}
      {showStepGuidance && <GuidancePanel step={3} />}

      {/* Keyboard Shortcut Hint */}
      <div className="text-sm text-gray-500 bg-gray-800/50 rounded-lg px-3 py-2 border border-gray-700">
        Tip: Press 1-5 to quickly rate. 1=CC (Very Consistent), 5=II (Very Inconsistent)
      </div>

      {/* Completion Progress */}
      <div className="flex items-center gap-4">
        <div className="flex-1 bg-gray-700 rounded-full h-2">
          <div
            className="bg-blue-500 rounded-full h-2 transition-all"
            style={{ width: `${completion.percentage}%` }}
          />
        </div>
        <span className="text-sm text-gray-400">
          {completion.rated}/{completion.total} rated ({completion.percentage}%)
        </span>
      </div>

      {/* Rating Legend */}
      <div className="flex flex-wrap gap-3 text-sm">
        {RATING_OPTIONS.map((rating) => (
          <div key={rating} className="flex items-center gap-2">
            <div className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold text-white ${RATING_COLORS[rating]}`}>
              {rating}
            </div>
            <span className="text-gray-400">{RATING_LABELS[rating]}</span>
          </div>
        ))}
      </div>

      {/* Matrix Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-gray-900 text-left p-3 border-b border-gray-700 min-w-[200px]">
                <span className="text-gray-400 text-sm font-normal">Evidence</span>
              </th>
              {hypotheses.map((h) => (
                <th
                  key={h.id}
                  className="p-3 border-b border-gray-700 text-center min-w-[100px]"
                >
                  <div className="flex flex-col items-center gap-1">
                    <div
                      className="w-6 h-6 rounded-full"
                      style={{ backgroundColor: h.color }}
                    />
                    <span className="text-white font-bold">{h.label}</span>
                    <span className="text-gray-500 text-xs font-normal truncate max-w-[120px]" title={h.description}>
                      {h.description.slice(0, 20)}{h.description.length > 20 ? '...' : ''}
                    </span>
                  </div>
                </th>
              ))}
              {llmConfig.enabled && (
                <th className="p-3 border-b border-gray-700 text-center min-w-[60px]">
                  <span className="text-gray-400 text-sm font-normal">AI</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {evidence.map((e) => (
              <tr key={e.id} className="hover:bg-gray-800/50">
                <td className="sticky left-0 z-10 bg-gray-900 p-3 border-b border-gray-700">
                  <div className="flex items-start gap-2">
                    <span className="text-white font-bold">{e.label}</span>
                    <span className="text-gray-400 text-sm line-clamp-2" title={e.description}>
                      {e.description}
                    </span>
                  </div>
                </td>
                {hypotheses.map((h) => {
                  const rating = getRating(e.id, h.id);
                  const isFocused = focusedCell?.eId === e.id && focusedCell?.hId === h.id;

                  return (
                    <td key={h.id} className="p-2 border-b border-gray-700 text-center">
                      <div
                        className={`
                          matrix-cell inline-flex items-center justify-center
                          w-12 h-12 rounded-lg cursor-pointer
                          ${rating ? RATING_COLORS[rating] : 'bg-gray-700'}
                          ${isFocused ? 'ring-2 ring-blue-500 ring-offset-2 ring-offset-gray-900' : ''}
                          hover:ring-2 hover:ring-gray-500
                        `}
                        tabIndex={0}
                        onClick={() => {
                          // Cycle through ratings on click
                          const currentIndex = rating ? RATING_OPTIONS.indexOf(rating) : -1;
                          const nextIndex = (currentIndex + 1) % RATING_OPTIONS.length;
                          setRating(e.id, h.id, RATING_OPTIONS[nextIndex]);
                        }}
                        onFocus={() => setFocusedCell({ eId: e.id, hId: h.id })}
                        onBlur={() => setFocusedCell(null)}
                        onKeyDown={(ev) => handleKeyDown(ev, e.id, h.id)}
                        title={`${e.label} vs ${h.label}: ${rating ? RATING_LABELS[rating] : 'Unrated'}`}
                      >
                        <span className="text-white font-bold">
                          {rating || '-'}
                        </span>
                      </div>
                    </td>
                  );
                })}
                {llmConfig.enabled && (
                  <td className="p-2 border-b border-gray-700 text-center">
                    <button
                      onClick={() => handleAISuggest(e)}
                      disabled={isLoadingAI}
                      className={`
                        p-2 rounded-lg transition-colors
                        ${loadingEvidenceId === e.id
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-700 text-gray-400 hover:bg-purple-600 hover:text-white'
                        }
                        disabled:opacity-50 disabled:cursor-not-allowed
                      `}
                      title="AI suggest ratings for this evidence"
                    >
                      {loadingEvidenceId === e.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Sparkles className="w-4 h-4" />
                      )}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Keyboard shortcut reminder */}
      <div className="text-center text-sm text-gray-500">
        Click a cell to cycle ratings, or focus and press 1-5 to rate quickly
      </div>

      {/* AI Error */}
      {aiError && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <p className="text-red-300 text-sm">{aiError}</p>
          <button
            onClick={() => setAiError(null)}
            className="ml-auto text-red-400 hover:text-red-300"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* AI Suggestions Dialog */}
      <Dialog
        open={showAISuggestions}
        onClose={() => setShowAISuggestions(false)}
        title={`AI Rating Suggestions for ${selectedEvidence?.label || 'Evidence'}`}
        size="lg"
      >
        <div className="space-y-4">
          {selectedEvidence && (
            <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <p className="text-sm text-gray-400">Evidence:</p>
              <p className="text-white">{selectedEvidence.description}</p>
            </div>
          )}

          <p className="text-gray-400 text-sm">
            Click on a suggestion to apply that rating, or accept all at once.
          </p>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {aiSuggestions.map((suggestion) => {
              const hypothesis = hypotheses.find(h => h.id === suggestion.hypothesisId);
              const currentRating = selectedEvidence ? getRating(selectedEvidence.id, suggestion.hypothesisId) : null;
              const isApplied = currentRating === suggestion.rating;

              return (
                <div
                  key={suggestion.hypothesisId}
                  className={`p-3 rounded-lg border transition-colors ${
                    isApplied
                      ? 'bg-green-900/30 border-green-700'
                      : 'bg-gray-800 border-gray-700 hover:border-purple-500'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {hypothesis && (
                      <div
                        className="w-4 h-4 rounded-full mt-1 flex-shrink-0"
                        style={{ backgroundColor: hypothesis.color }}
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{suggestion.hypothesisLabel}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold text-white ${RATING_COLORS[suggestion.rating as Rating]}`}>
                          {suggestion.rating}
                        </span>
                        {isApplied && (
                          <span className="text-green-400 text-xs flex items-center gap-1">
                            <Check className="w-3 h-3" /> Applied
                          </span>
                        )}
                      </div>
                      <p className="text-gray-400 text-sm mt-1">{suggestion.explanation}</p>
                    </div>
                    {!isApplied && (
                      <button
                        onClick={() => acceptSuggestion(suggestion)}
                        className="px-3 py-1 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded transition-colors flex-shrink-0"
                      >
                        Apply
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button variant="secondary" onClick={() => setShowAISuggestions(false)}>
              Close
            </Button>
            <Button
              onClick={acceptAllSuggestions}
              icon={<Check className="w-4 h-4" />}
            >
              Accept All
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
