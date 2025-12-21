import { Skull, Save, X, AlertTriangle, Lightbulb, FileQuestion } from 'lucide-react';
import { useACHStore } from '../store/useACHStore';
import { Dialog } from './ui/Dialog';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';

interface ChallengeCardProps {
  hypothesisLabel: string;
  counterArgument: string;
  disproofEvidence: string;
  alternativeAngle: string;
}

function ChallengeCard({
  hypothesisLabel,
  counterArgument,
  disproofEvidence,
  alternativeAngle,
}: ChallengeCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Badge variant="info">{hypothesisLabel}</Badge>
        <span className="text-gray-400 text-sm">Challenge</span>
      </div>

      <div className="space-y-3">
        <div className="flex gap-2">
          <AlertTriangle className="w-4 h-4 text-orange-400 mt-1 flex-shrink-0" />
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Counter-Argument</div>
            <p className="text-sm text-gray-200">{counterArgument}</p>
          </div>
        </div>

        <div className="flex gap-2">
          <FileQuestion className="w-4 h-4 text-red-400 mt-1 flex-shrink-0" />
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">What Would Disprove This</div>
            <p className="text-sm text-gray-200">{disproofEvidence}</p>
          </div>
        </div>

        <div className="flex gap-2">
          <Lightbulb className="w-4 h-4 text-yellow-400 mt-1 flex-shrink-0" />
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Alternative Angle</div>
            <p className="text-sm text-gray-200">{alternativeAngle}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function DevilsAdvocateDialog() {
  const {
    challenges,
    showChallengesDialog,
    saveChallengesAsNotes,
    closeChallengesDialog,
  } = useACHStore();

  if (!showChallengesDialog) return null;

  return (
    <Dialog
      isOpen={showChallengesDialog}
      onClose={closeChallengesDialog}
      title={
        <div className="flex items-center gap-2">
          <Skull className="w-5 h-5 text-red-400" />
          <span>Devil's Advocate Challenges</span>
        </div>
      }
      maxWidth="2xl"
    >
      <div className="space-y-4">
        <p className="text-gray-400 text-sm">
          The AI has generated challenges to your hypotheses. Review these counter-arguments
          and consider if they reveal weaknesses in your analysis.
        </p>

        <div className="space-y-3 max-h-96 overflow-y-auto">
          {challenges.map((challenge, index) => (
            <ChallengeCard
              key={index}
              hypothesisLabel={challenge.hypothesisLabel}
              counterArgument={challenge.counterArgument}
              disproofEvidence={challenge.disproofEvidence}
              alternativeAngle={challenge.alternativeAngle}
            />
          ))}
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
          <Button
            variant="primary"
            onClick={saveChallengesAsNotes}
            icon={<Save className="w-4 h-4" />}
          >
            Save to Notes
          </Button>
          <Button
            variant="secondary"
            onClick={closeChallengesDialog}
            icon={<X className="w-4 h-4" />}
          >
            Dismiss
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
