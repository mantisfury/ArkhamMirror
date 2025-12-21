import { useState } from 'react';
import { useACHStore } from '../../store/useACHStore';
import { Button } from '../ui';
import { Trophy, AlertTriangle, TrendingDown, Sparkles, Loader2 } from 'lucide-react';
import { getAnalysisInsights } from '../../services/llmService';
import { GuidancePanel } from '../GuidancePanel';

export function StepConclusions() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const calculateScores = useACHStore((state) => state.calculateScores);
  const getMatrixCompletion = useACHStore((state) => state.getMatrixCompletion);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const markStepComplete = useACHStore((state) => state.markStepComplete);
  const llmConfig = useACHStore((state) => state.llmConfig);

  const [isLoadingAI, setIsLoadingAI] = useState(false);
  const [aiInsights, setAiInsights] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  if (!analysis) return null;

  const handleGetInsights = async () => {
    if (!llmConfig.enabled) return;

    setIsLoadingAI(true);
    setAiError(null);

    const result = await getAnalysisInsights(llmConfig, analysis);

    setIsLoadingAI(false);

    if (result.success) {
      setAiInsights(result.content);
    } else {
      setAiError(result.error || 'Failed to get insights');
    }
  };

  const scores = calculateScores();
  const completion = getMatrixCompletion();

  // Mark step complete when viewed with scores
  if (scores.length > 0 && !analysis.stepsCompleted.includes(6)) {
    markStepComplete(6);
  }

  // Find the winner (lowest inconsistency)
  const winner = scores.length > 0 ? scores[0] : null;

  // Check for close race
  const isCloseRace = scores.length >= 2 &&
    Math.abs(scores[0].inconsistencyScore - scores[1].inconsistencyScore) <= 1;

  // Max score for percentage calculation
  const maxScore = Math.max(...scores.map((s) => s.inconsistencyScore), 1);

  return (
    <div className="space-y-6">
      {/* Guidance */}
      {showStepGuidance && <GuidancePanel step={6} />}

      {/* Completion Status */}
      {completion.percentage < 100 && (
        <div className="bg-yellow-900/30 border border-yellow-800 rounded-lg p-4">
          <div className="flex gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-yellow-200">Matrix is {completion.percentage}% complete</p>
              <p className="text-yellow-300/70 text-sm mt-1">
                Consider rating all evidence before drawing final conclusions.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Winner Announcement */}
      {winner && (
        <div className="bg-gradient-to-r from-green-900/50 to-emerald-900/50 border border-green-700 rounded-xl p-6">
          <div className="flex items-center gap-4">
            <div className="bg-green-600 rounded-full p-3">
              <Trophy className="w-8 h-8 text-white" />
            </div>
            <div>
              <p className="text-green-300 text-sm uppercase tracking-wide">Leading Hypothesis</p>
              <div className="flex items-center gap-3 mt-1">
                <div
                  className="w-5 h-5 rounded-full"
                  style={{ backgroundColor: winner.color }}
                />
                <h3 className="text-2xl font-bold text-white">{winner.label}</h3>
              </div>
              <p className="text-green-200/70 text-sm mt-2">
                Inconsistency Score: {winner.inconsistencyScore} (lowest of all hypotheses)
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Close Race Warning */}
      {isCloseRace && scores.length >= 2 && (
        <div className="bg-yellow-900/30 border border-yellow-800 rounded-lg p-4">
          <div className="flex gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-yellow-200 font-medium">Close Race Detected</p>
              <p className="text-yellow-300/70 text-sm mt-1">
                {scores[0].label} and {scores[1].label} are very close in score.
                Consider gathering more diagnostic evidence to distinguish between them.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* All Scores */}
      <div className="space-y-4">
        <h3 className="text-lg font-medium text-white">Hypothesis Rankings</h3>

        {scores.length === 0 ? (
          <div className="text-center py-8 bg-gray-800 rounded-lg border border-gray-700">
            <p className="text-gray-400">No scores to display. Rate evidence in the matrix first.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {scores.map((score, index) => {
              const hypothesis = analysis.hypotheses.find((h) => h.id === score.hypothesisId);

              return (
                <div
                  key={score.hypothesisId}
                  className={`rounded-lg border p-4 ${
                    index === 0
                      ? 'bg-green-900/20 border-green-800'
                      : 'bg-gray-800 border-gray-700'
                  }`}
                >
                  <div className="flex items-center gap-4">
                    {/* Rank */}
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg ${
                      index === 0 ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-300'
                    }`}>
                      #{score.rank}
                    </div>

                    {/* Hypothesis info */}
                    <div className="flex items-center gap-2 min-w-[100px]">
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: score.color }}
                      />
                      <span className="font-bold text-white">{score.label}</span>
                    </div>

                    {/* Score Bar */}
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <div className="flex-1 bg-gray-700 rounded-full h-3">
                          <div
                            className={`h-3 rounded-full transition-all ${
                              index === 0 ? 'bg-green-500' : 'bg-red-500'
                            }`}
                            style={{
                              width: `${(score.inconsistencyScore / maxScore) * 100}%`,
                            }}
                          />
                        </div>
                        <div className="w-24 text-right">
                          <span className={`font-mono ${index === 0 ? 'text-green-400' : 'text-gray-300'}`}>
                            {score.inconsistencyScore}
                          </span>
                          <span className="text-gray-500 text-sm ml-1">pts</span>
                        </div>
                      </div>
                      {hypothesis && (
                        <p className="text-sm text-gray-400 mt-2 truncate" title={hypothesis.description}>
                          {hypothesis.description}
                        </p>
                      )}
                    </div>

                    {/* Status indicator */}
                    {index === 0 && (
                      <Trophy className="w-5 h-5 text-green-400" />
                    )}
                    {index === scores.length - 1 && scores.length > 1 && (
                      <TrendingDown className="w-5 h-5 text-red-400" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Interpretation Guide */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h4 className="text-white font-medium mb-2">Understanding the Scores</h4>
        <ul className="text-sm text-gray-400 space-y-1">
          <li><span className="text-green-400">Lower score = better</span>: Fewer inconsistencies with the evidence</li>
          <li>Each "Inconsistent" (I) rating adds 1 point</li>
          <li>Each "Very Inconsistent" (II) rating adds 2 points</li>
          <li>The hypothesis with the lowest score is hardest to disprove</li>
        </ul>
      </div>

      {/* AI Insights Section */}
      {llmConfig.enabled && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-white">AI Analysis</h3>
            <Button
              onClick={handleGetInsights}
              variant="secondary"
              icon={isLoadingAI ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              disabled={isLoadingAI || scores.length === 0}
            >
              {isLoadingAI ? 'Analyzing...' : aiInsights ? 'Refresh Insights' : 'Get AI Insights'}
            </Button>
          </div>

          {aiError && (
            <div className="bg-red-900/30 border border-red-800 rounded-lg p-3">
              <p className="text-red-300 text-sm">{aiError}</p>
            </div>
          )}

          {aiInsights && (
            <div className="bg-purple-900/20 border border-purple-800 rounded-lg p-4">
              <div className="flex gap-3">
                <Sparkles className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                <div className="prose prose-invert prose-sm max-w-none">
                  <div className="text-gray-200 whitespace-pre-wrap">{aiInsights}</div>
                </div>
              </div>
            </div>
          )}

          {!aiInsights && !aiError && (
            <div className="text-center py-6 bg-gray-800/50 rounded-lg border border-gray-700 border-dashed">
              <Sparkles className="w-8 h-8 text-gray-600 mx-auto mb-2" />
              <p className="text-gray-500 text-sm">
                Click "Get AI Insights" for an AI-powered analysis of your hypotheses and evidence.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
