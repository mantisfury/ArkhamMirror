import { useState } from 'react';
import { useACHStore } from '../../store/useACHStore';
import { Button, Dialog, TextArea } from '../ui';
import { Plus, Edit2, Trash2, Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { suggestHypotheses } from '../../services/llmService';
import { GuidancePanel } from '../GuidancePanel';

export function StepHypotheses() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const addHypothesis = useACHStore((state) => state.addHypothesis);
  const updateHypothesis = useACHStore((state) => state.updateHypothesis);
  const deleteHypothesis = useACHStore((state) => state.deleteHypothesis);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const markStepComplete = useACHStore((state) => state.markStepComplete);
  const llmConfig = useACHStore((state) => state.llmConfig);

  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [description, setDescription] = useState('');

  // AI suggestion state
  const [isLoadingAI, setIsLoadingAI] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<string[]>([]);
  const [showAISuggestions, setShowAISuggestions] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  if (!analysis) return null;

  const handleAdd = () => {
    if (description.trim()) {
      addHypothesis(description.trim());
      setDescription('');
      setShowAddDialog(false);
    }
  };

  const handleEdit = (id: string) => {
    if (description.trim()) {
      updateHypothesis(id, { description: description.trim() });
      setDescription('');
      setShowEditDialog(null);
    }
  };

  const handleDelete = (id: string) => {
    deleteHypothesis(id);
    setShowDeleteConfirm(null);
  };

  const openEditDialog = (id: string) => {
    const hypothesis = analysis.hypotheses.find((h) => h.id === id);
    if (hypothesis) {
      setDescription(hypothesis.description);
      setShowEditDialog(id);
    }
  };

  const handleAISuggest = async () => {
    if (!llmConfig.enabled) return;

    setIsLoadingAI(true);
    setAiError(null);
    setAiSuggestions([]);

    const result = await suggestHypotheses(
      llmConfig,
      analysis.focusQuestion,
      analysis.hypotheses
    );

    setIsLoadingAI(false);

    if (result.success) {
      // Parse the response - expect numbered list
      const lines = result.content.split('\n')
        .map(line => line.replace(/^\d+[\.\)]\s*/, '').trim())
        .filter(line => line.length > 0);
      setAiSuggestions(lines);
      setShowAISuggestions(true);
    } else {
      setAiError(result.error || 'Failed to get suggestions');
    }
  };

  const addSuggestion = (suggestion: string) => {
    addHypothesis(suggestion);
  };

  // Mark step complete when 2+ hypotheses exist
  if (analysis.hypotheses.length >= 2 && !analysis.stepsCompleted.includes(1)) {
    markStepComplete(1);
  }

  return (
    <div className="space-y-6">
      {/* Guidance */}
      {showStepGuidance && <GuidancePanel step={1} />}

      {/* Add Button */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-white">
          Hypotheses ({analysis.hypotheses.length})
        </h3>
        <div className="flex gap-2">
          {llmConfig.enabled && (
            <Button
              onClick={handleAISuggest}
              variant="secondary"
              icon={isLoadingAI ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              disabled={isLoadingAI}
            >
              {isLoadingAI ? 'Thinking...' : 'AI Suggest'}
            </Button>
          )}
          <Button onClick={() => setShowAddDialog(true)} icon={<Plus className="w-4 h-4" />}>
            Add Hypothesis
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

      {/* Hypotheses List */}
      {analysis.hypotheses.length === 0 ? (
        <div className="text-center py-12 bg-gray-800 rounded-lg border border-gray-700">
          <p className="text-gray-400 mb-4">No hypotheses yet. Add at least 2 to continue.</p>
          <Button onClick={() => setShowAddDialog(true)} icon={<Plus className="w-4 h-4" />}>
            Add First Hypothesis
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {analysis.hypotheses.map((hypothesis) => (
            <div
              key={hypothesis.id}
              className="bg-gray-800 rounded-lg border border-gray-700 p-4"
            >
              <div className="flex items-start gap-4">
                {/* Color indicator and label */}
                <div className="flex items-center gap-2">
                  <div
                    className="w-4 h-4 rounded-full"
                    style={{ backgroundColor: hypothesis.color }}
                  />
                  <span className="text-lg font-bold text-white">{hypothesis.label}</span>
                </div>

                {/* Description */}
                <div className="flex-1">
                  <p className="text-gray-200">{hypothesis.description}</p>
                  {hypothesis.futureIndicators && (
                    <p className="text-sm text-gray-400 mt-2">
                      <span className="text-gray-500">Future indicators:</span> {hypothesis.futureIndicators}
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => openEditDialog(hypothesis.id)}
                    className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                    title="Edit"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(hypothesis.id)}
                    className="p-2 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Minimum requirement indicator */}
      {analysis.hypotheses.length < 2 && analysis.hypotheses.length > 0 && (
        <p className="text-yellow-400 text-sm">
          Add at least {2 - analysis.hypotheses.length} more hypothesis to continue.
        </p>
      )}

      {/* Add Dialog */}
      <Dialog
        open={showAddDialog}
        onClose={() => {
          setShowAddDialog(false);
          setDescription('');
        }}
        title="Add Hypothesis"
      >
        <div className="space-y-4">
          <TextArea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe this hypothesis..."
            rows={4}
            autoFocus
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => {
              setShowAddDialog(false);
              setDescription('');
            }}>
              Cancel
            </Button>
            <Button onClick={handleAdd} disabled={!description.trim()}>
              Add
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog
        open={showEditDialog !== null}
        onClose={() => {
          setShowEditDialog(null);
          setDescription('');
        }}
        title="Edit Hypothesis"
      >
        <div className="space-y-4">
          <TextArea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe this hypothesis..."
            rows={4}
            autoFocus
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => {
              setShowEditDialog(null);
              setDescription('');
            }}>
              Cancel
            </Button>
            <Button onClick={() => showEditDialog && handleEdit(showEditDialog)} disabled={!description.trim()}>
              Save
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog
        open={showDeleteConfirm !== null}
        onClose={() => setShowDeleteConfirm(null)}
        title="Delete Hypothesis"
      >
        <p className="text-gray-300 mb-6">
          Are you sure you want to delete this hypothesis? This will also remove all associated ratings.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setShowDeleteConfirm(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => showDeleteConfirm && handleDelete(showDeleteConfirm)}
          >
            Delete
          </Button>
        </div>
      </Dialog>

      {/* AI Suggestions Dialog */}
      <Dialog
        open={showAISuggestions}
        onClose={() => setShowAISuggestions(false)}
        title="AI Suggested Hypotheses"
        size="lg"
      >
        <div className="space-y-4">
          <p className="text-gray-400 text-sm">
            Click on a suggestion to add it as a hypothesis. You can modify it after adding.
          </p>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {aiSuggestions.map((suggestion, index) => (
              <button
                key={index}
                onClick={() => {
                  addSuggestion(suggestion);
                }}
                className="w-full text-left p-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-blue-500 rounded-lg transition-colors"
              >
                <div className="flex items-start gap-3">
                  <Sparkles className="w-4 h-4 text-purple-400 mt-1 flex-shrink-0" />
                  <span className="text-gray-200">{suggestion}</span>
                </div>
              </button>
            ))}
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
    </div>
  );
}
