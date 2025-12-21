import { useState } from 'react';
import { useACHStore } from '../../store/useACHStore';
import { Button, Dialog, Input, TextArea, Select } from '../ui';
import {
  Plus, Edit2, Trash2, FileJson, FileText, FileDown,
  Clock, CheckCircle, XCircle, Camera, History, Sparkles, Loader2, AlertCircle
} from 'lucide-react';
import { suggestMilestones } from '../../services/llmService';
import { GuidancePanel } from '../GuidancePanel';

export function StepReport() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const addMilestone = useACHStore((state) => state.addMilestone);
  const updateMilestone = useACHStore((state) => state.updateMilestone);
  const deleteMilestone = useACHStore((state) => state.deleteMilestone);
  const createSnapshot = useACHStore((state) => state.createSnapshot);
  const exportToJSON = useACHStore((state) => state.exportToJSON);
  const exportToMarkdown = useACHStore((state) => state.exportToMarkdown);
  const exportToPDF = useACHStore((state) => state.exportToPDF);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const markStepComplete = useACHStore((state) => state.markStepComplete);
  const llmConfig = useACHStore((state) => state.llmConfig);

  const [showAddMilestone, setShowAddMilestone] = useState(false);
  const [showEditMilestone, setShowEditMilestone] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [showSnapshotDialog, setShowSnapshotDialog] = useState(false);

  const [milestoneDesc, setMilestoneDesc] = useState('');
  const [milestoneHypothesis, setMilestoneHypothesis] = useState('');
  const [milestoneExpectedBy, setMilestoneExpectedBy] = useState('');
  const [milestoneObserved, setMilestoneObserved] = useState<0 | 1 | -1>(0);
  const [milestoneNotes, setMilestoneNotes] = useState('');

  const [snapshotLabel, setSnapshotLabel] = useState('');
  const [snapshotDesc, setSnapshotDesc] = useState('');

  // AI suggestion state
  const [isLoadingAI, setIsLoadingAI] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<Array<{ hypothesisId: string; description: string }>>([]);
  const [showAISuggestions, setShowAISuggestions] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  if (!analysis) return null;

  // Mark step complete when viewed
  if (!analysis.stepsCompleted.includes(8)) {
    markStepComplete(8);
  }

  const resetMilestoneForm = () => {
    setMilestoneDesc('');
    setMilestoneHypothesis('');
    setMilestoneExpectedBy('');
    setMilestoneObserved(0);
    setMilestoneNotes('');
  };

  const handleAddMilestone = () => {
    if (milestoneDesc.trim() && milestoneHypothesis) {
      addMilestone(milestoneHypothesis, milestoneDesc.trim(), milestoneExpectedBy || undefined);
      resetMilestoneForm();
      setShowAddMilestone(false);
    }
  };

  const handleEditMilestone = (id: string) => {
    updateMilestone(id, {
      description: milestoneDesc.trim(),
      expectedBy: milestoneExpectedBy || undefined,
      observed: milestoneObserved,
      observationNotes: milestoneNotes || undefined,
    });
    resetMilestoneForm();
    setShowEditMilestone(null);
  };

  const openEditMilestone = (id: string) => {
    const milestone = analysis.milestones.find((m) => m.id === id);
    if (milestone) {
      setMilestoneDesc(milestone.description);
      setMilestoneExpectedBy(milestone.expectedBy || '');
      setMilestoneObserved(milestone.observed);
      setMilestoneNotes(milestone.observationNotes || '');
      setShowEditMilestone(id);
    }
  };

  const handleDeleteMilestone = (id: string) => {
    deleteMilestone(id);
    setShowDeleteConfirm(null);
  };

  const handleCreateSnapshot = () => {
    if (snapshotLabel.trim()) {
      createSnapshot(snapshotLabel.trim(), snapshotDesc.trim() || undefined);
      setSnapshotLabel('');
      setSnapshotDesc('');
      setShowSnapshotDialog(false);
    }
  };

  const handleAISuggest = async () => {
    if (!llmConfig.enabled) return;

    setIsLoadingAI(true);
    setAiError(null);
    setAiSuggestions([]);

    const result = await suggestMilestones(llmConfig, analysis);

    setIsLoadingAI(false);

    if (result.success) {
      // Parse milestones - format is "H1: milestone description" or "[H1] milestone description"
      const parsed: Array<{ hypothesisId: string; description: string }> = [];
      const lines = result.content.split('\n')
        .map(line => line.replace(/^\d+[\.\)]\s*/, '').trim())
        .filter(line => line.length > 0);

      for (const line of lines) {
        // Try to match hypothesis reference at start
        const match = line.match(/^(?:\[?(H\d+)\]?:?\s*)/i);
        if (match) {
          const hLabel = match[1].toUpperCase();
          const hypothesis = analysis.hypotheses.find(h => h.label === hLabel);
          if (hypothesis) {
            parsed.push({
              hypothesisId: hypothesis.id,
              description: line.replace(match[0], '').trim(),
            });
            continue;
          }
        }
        // If no match, try to find any H reference in the line
        const anyMatch = line.match(/\b(H\d+)\b/i);
        if (anyMatch) {
          const hLabel = anyMatch[1].toUpperCase();
          const hypothesis = analysis.hypotheses.find(h => h.label === hLabel);
          if (hypothesis) {
            parsed.push({
              hypothesisId: hypothesis.id,
              description: line.replace(/\b(H\d+)\b:?\s*/i, '').trim(),
            });
            continue;
          }
        }
        // Default to first hypothesis if no match found
        if (analysis.hypotheses.length > 0) {
          parsed.push({
            hypothesisId: analysis.hypotheses[0].id,
            description: line,
          });
        }
      }

      setAiSuggestions(parsed);
      setShowAISuggestions(true);
    } else {
      setAiError(result.error || 'Failed to get suggestions');
    }
  };

  const addSuggestedMilestone = (suggestion: { hypothesisId: string; description: string }) => {
    addMilestone(suggestion.hypothesisId, suggestion.description);
  };

  const handleExportJSON = () => {
    const json = exportToJSON();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ach-${analysis.title.toLowerCase().replace(/\s+/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportMarkdown = () => {
    const md = exportToMarkdown();
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ach-${analysis.title.toLowerCase().replace(/\s+/g, '-')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const hypothesisOptions = analysis.hypotheses.map((h) => ({
    value: h.id,
    label: `${h.label}: ${h.description.slice(0, 30)}${h.description.length > 30 ? '...' : ''}`,
  }));

  const observedOptions = [
    { value: '0', label: 'Pending' },
    { value: '1', label: 'Observed' },
    { value: '-1', label: 'Contradicted' },
  ];

  const getObservedIcon = (observed: 0 | 1 | -1) => {
    switch (observed) {
      case 1:
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case -1:
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Clock className="w-5 h-5 text-yellow-400" />;
    }
  };

  return (
    <div className="space-y-8">
      {/* Guidance */}
      {showStepGuidance && <GuidancePanel step={8} />}

      {/* Milestones Section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-white">Future Milestones</h3>
          <div className="flex gap-2">
            {llmConfig.enabled && (
              <Button
                onClick={handleAISuggest}
                variant="secondary"
                icon={isLoadingAI ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                size="sm"
                disabled={isLoadingAI || analysis.hypotheses.length < 2}
              >
                {isLoadingAI ? 'Thinking...' : 'AI Suggest'}
              </Button>
            )}
            <Button onClick={() => setShowAddMilestone(true)} icon={<Plus className="w-4 h-4" />} size="sm">
              Add Milestone
            </Button>
          </div>
        </div>

        {/* AI Error */}
        {aiError && (
          <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <p className="text-red-300 text-sm">{aiError}</p>
          </div>
        )}

        {analysis.milestones.length === 0 ? (
          <div className="text-center py-8 bg-gray-800 rounded-lg border border-gray-700">
            <Clock className="w-12 h-12 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400">No milestones yet</p>
            <p className="text-gray-500 text-sm mt-1">
              Add indicators to track that could confirm or refute hypotheses
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {analysis.milestones.map((milestone) => {
              const hypothesis = analysis.hypotheses.find((h) => h.id === milestone.hypothesisId);

              return (
                <div
                  key={milestone.id}
                  className={`bg-gray-800 rounded-lg border p-4 ${
                    milestone.observed === 1
                      ? 'border-green-800'
                      : milestone.observed === -1
                        ? 'border-red-800'
                        : 'border-gray-700'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {getObservedIcon(milestone.observed)}

                    <div className="flex-1">
                      <p className="text-white">{milestone.description}</p>
                      <div className="flex items-center gap-4 mt-2 text-sm text-gray-400">
                        {hypothesis && (
                          <span className="flex items-center gap-1">
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: hypothesis.color }}
                            />
                            {hypothesis.label}
                          </span>
                        )}
                        {milestone.expectedBy && (
                          <span>Expected by: {milestone.expectedBy}</span>
                        )}
                      </div>
                      {milestone.observationNotes && (
                        <p className="text-sm text-gray-500 mt-2 italic">
                          Note: {milestone.observationNotes}
                        </p>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={() => openEditMilestone(milestone.id)}
                        className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setShowDeleteConfirm(milestone.id)}
                        className="p-2 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Version History Section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-white">Version History</h3>
          <Button onClick={() => setShowSnapshotDialog(true)} icon={<Camera className="w-4 h-4" />} size="sm" variant="secondary">
            Create Snapshot
          </Button>
        </div>

        {analysis.snapshots.length === 0 ? (
          <div className="text-center py-6 bg-gray-800 rounded-lg border border-gray-700">
            <History className="w-10 h-10 text-gray-600 mx-auto mb-2" />
            <p className="text-gray-400 text-sm">No snapshots yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {analysis.snapshots.map((snapshot) => (
              <div
                key={snapshot.id}
                className="flex items-center gap-4 p-3 bg-gray-800 rounded-lg border border-gray-700"
              >
                <Camera className="w-5 h-5 text-gray-500" />
                <div className="flex-1">
                  <p className="text-white font-medium">{snapshot.label}</p>
                  {snapshot.description && (
                    <p className="text-sm text-gray-400">{snapshot.description}</p>
                  )}
                </div>
                <span className="text-sm text-gray-500">
                  {new Date(snapshot.createdAt).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Export Section */}
      <section className="space-y-4">
        <h3 className="text-lg font-medium text-white">Export Analysis</h3>

        <div className="grid grid-cols-3 gap-4">
          <button
            onClick={exportToPDF}
            className="flex items-center gap-4 p-4 bg-gray-800 rounded-lg border border-gray-700 hover:border-red-500 transition-colors text-left"
          >
            <FileDown className="w-10 h-10 text-red-400" />
            <div>
              <p className="text-white font-medium">Export PDF</p>
              <p className="text-sm text-gray-400">Printable report</p>
            </div>
          </button>

          <button
            onClick={handleExportJSON}
            className="flex items-center gap-4 p-4 bg-gray-800 rounded-lg border border-gray-700 hover:border-blue-500 transition-colors text-left"
          >
            <FileJson className="w-10 h-10 text-blue-400" />
            <div>
              <p className="text-white font-medium">Export JSON</p>
              <p className="text-sm text-gray-400">Full data, re-importable</p>
            </div>
          </button>

          <button
            onClick={handleExportMarkdown}
            className="flex items-center gap-4 p-4 bg-gray-800 rounded-lg border border-gray-700 hover:border-green-500 transition-colors text-left"
          >
            <FileText className="w-10 h-10 text-green-400" />
            <div>
              <p className="text-white font-medium">Export Markdown</p>
              <p className="text-sm text-gray-400">Human-readable report</p>
            </div>
          </button>
        </div>
      </section>

      {/* Add Milestone Dialog */}
      <Dialog
        open={showAddMilestone}
        onClose={() => {
          setShowAddMilestone(false);
          resetMilestoneForm();
        }}
        title="Add Milestone"
        size="lg"
      >
        <div className="space-y-4">
          <Select
            label="Hypothesis"
            value={milestoneHypothesis}
            onChange={(e) => setMilestoneHypothesis(e.target.value)}
            options={[{ value: '', label: 'Select a hypothesis...' }, ...hypothesisOptions]}
          />
          <TextArea
            label="Description"
            value={milestoneDesc}
            onChange={(e) => setMilestoneDesc(e.target.value)}
            placeholder="What indicator should we watch for?"
            rows={3}
          />
          <Input
            label="Expected By (optional)"
            value={milestoneExpectedBy}
            onChange={(e) => setMilestoneExpectedBy(e.target.value)}
            placeholder="e.g., Q1 2025, March, 30 days"
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => {
              setShowAddMilestone(false);
              resetMilestoneForm();
            }}>
              Cancel
            </Button>
            <Button onClick={handleAddMilestone} disabled={!milestoneDesc.trim() || !milestoneHypothesis}>
              Add
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Edit Milestone Dialog */}
      <Dialog
        open={showEditMilestone !== null}
        onClose={() => {
          setShowEditMilestone(null);
          resetMilestoneForm();
        }}
        title="Edit Milestone"
        size="lg"
      >
        <div className="space-y-4">
          <TextArea
            label="Description"
            value={milestoneDesc}
            onChange={(e) => setMilestoneDesc(e.target.value)}
            rows={3}
          />
          <Input
            label="Expected By"
            value={milestoneExpectedBy}
            onChange={(e) => setMilestoneExpectedBy(e.target.value)}
          />
          <Select
            label="Status"
            value={String(milestoneObserved)}
            onChange={(e) => setMilestoneObserved(Number(e.target.value) as 0 | 1 | -1)}
            options={observedOptions}
          />
          <TextArea
            label="Observation Notes"
            value={milestoneNotes}
            onChange={(e) => setMilestoneNotes(e.target.value)}
            placeholder="Notes about what was observed..."
            rows={2}
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => {
              setShowEditMilestone(null);
              resetMilestoneForm();
            }}>
              Cancel
            </Button>
            <Button onClick={() => showEditMilestone && handleEditMilestone(showEditMilestone)}>
              Save
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Create Snapshot Dialog */}
      <Dialog
        open={showSnapshotDialog}
        onClose={() => {
          setShowSnapshotDialog(false);
          setSnapshotLabel('');
          setSnapshotDesc('');
        }}
        title="Create Snapshot"
      >
        <div className="space-y-4">
          <Input
            label="Label"
            value={snapshotLabel}
            onChange={(e) => setSnapshotLabel(e.target.value)}
            placeholder="e.g., Before new evidence"
          />
          <TextArea
            label="Description (optional)"
            value={snapshotDesc}
            onChange={(e) => setSnapshotDesc(e.target.value)}
            placeholder="What's notable about this version?"
            rows={2}
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => {
              setShowSnapshotDialog(false);
              setSnapshotLabel('');
              setSnapshotDesc('');
            }}>
              Cancel
            </Button>
            <Button onClick={handleCreateSnapshot} disabled={!snapshotLabel.trim()}>
              Create
            </Button>
          </div>
        </div>
      </Dialog>

      {/* AI Suggestions Dialog */}
      <Dialog
        open={showAISuggestions}
        onClose={() => setShowAISuggestions(false)}
        title="AI Suggested Milestones"
        size="lg"
      >
        <div className="space-y-4">
          <p className="text-gray-400 text-sm">
            Click on a suggestion to add it as a milestone. Each milestone is linked to a hypothesis.
          </p>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {aiSuggestions.map((suggestion, index) => {
              const hypothesis = analysis.hypotheses.find(h => h.id === suggestion.hypothesisId);
              return (
                <button
                  key={index}
                  onClick={() => {
                    addSuggestedMilestone(suggestion);
                  }}
                  className="w-full text-left p-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-blue-500 rounded-lg transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <Sparkles className="w-4 h-4 text-purple-400 mt-1 flex-shrink-0" />
                    <div className="flex-1">
                      <span className="text-gray-200">{suggestion.description}</span>
                      {hypothesis && (
                        <div className="flex items-center gap-2 mt-2 text-sm">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: hypothesis.color }}
                          />
                          <span className="text-gray-400">{hypothesis.label}: {hypothesis.description.slice(0, 40)}{hypothesis.description.length > 40 ? '...' : ''}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button variant="secondary" onClick={() => setShowAISuggestions(false)}>
              Close
            </Button>
            <Button
              onClick={handleAISuggest}
              icon={isLoadingAI ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              disabled={isLoadingAI}
            >
              Regenerate
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog
        open={showDeleteConfirm !== null}
        onClose={() => setShowDeleteConfirm(null)}
        title="Delete Milestone"
      >
        <p className="text-gray-300 mb-6">
          Are you sure you want to delete this milestone?
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setShowDeleteConfirm(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => showDeleteConfirm && handleDeleteMilestone(showDeleteConfirm)}
          >
            Delete
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
