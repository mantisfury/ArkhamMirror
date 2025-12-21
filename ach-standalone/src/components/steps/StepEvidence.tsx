import { useState } from 'react';
import { useACHStore } from '../../store/useACHStore';
import { EVIDENCE_TYPES, RELIABILITY_OPTIONS, EvidenceType, Reliability } from '../../types';
import { Button, Dialog, TextArea, Input, Select } from '../ui';
import { Plus, Edit2, Trash2, FileText, MessageSquare, File, HelpCircle, Scale, Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { suggestEvidence } from '../../services/llmService';
import { GuidancePanel } from '../GuidancePanel';

const EVIDENCE_TYPE_ICONS: Record<EvidenceType, React.ReactNode> = {
  fact: <FileText className="w-4 h-4" />,
  testimony: <MessageSquare className="w-4 h-4" />,
  document: <File className="w-4 h-4" />,
  assumption: <HelpCircle className="w-4 h-4" />,
  argument: <Scale className="w-4 h-4" />,
};

const RELIABILITY_COLORS: Record<Reliability, string> = {
  high: 'text-green-400',
  medium: 'text-yellow-400',
  low: 'text-red-400',
};

// Parse evidence type from AI suggestion
const parseEvidenceType = (text: string): EvidenceType => {
  const lower = text.toLowerCase();
  if (lower.includes('(fact)') || lower.includes('fact:')) return 'fact';
  if (lower.includes('(testimony)') || lower.includes('testimony:')) return 'testimony';
  if (lower.includes('(document)') || lower.includes('document:')) return 'document';
  if (lower.includes('(assumption)') || lower.includes('assumption:')) return 'assumption';
  if (lower.includes('(argument)') || lower.includes('argument:')) return 'argument';
  return 'fact';
};

export function StepEvidence() {
  const analysis = useACHStore((state) => state.getCurrentAnalysis());
  const addEvidence = useACHStore((state) => state.addEvidence);
  const updateEvidence = useACHStore((state) => state.updateEvidence);
  const deleteEvidence = useACHStore((state) => state.deleteEvidence);
  const showStepGuidance = useACHStore((state) => state.showStepGuidance);
  const markStepComplete = useACHStore((state) => state.markStepComplete);
  const llmConfig = useACHStore((state) => state.llmConfig);

  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);

  const [description, setDescription] = useState('');
  const [evidenceType, setEvidenceType] = useState<EvidenceType>('fact');
  const [reliability, setReliability] = useState<Reliability>('medium');
  const [source, setSource] = useState('');

  // AI suggestion state
  const [isLoadingAI, setIsLoadingAI] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<string[]>([]);
  const [showAISuggestions, setShowAISuggestions] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  if (!analysis) return null;

  const resetForm = () => {
    setDescription('');
    setEvidenceType('fact');
    setReliability('medium');
    setSource('');
  };

  const handleAdd = () => {
    if (description.trim()) {
      addEvidence(description.trim(), evidenceType, reliability, source.trim() || undefined);
      resetForm();
      setShowAddDialog(false);
    }
  };

  const handleEdit = (id: string) => {
    if (description.trim()) {
      updateEvidence(id, {
        description: description.trim(),
        evidenceType,
        reliability,
        source: source.trim() || undefined,
      });
      resetForm();
      setShowEditDialog(null);
    }
  };

  const handleDelete = (id: string) => {
    deleteEvidence(id);
    setShowDeleteConfirm(null);
  };

  const openEditDialog = (id: string) => {
    const evidence = analysis.evidence.find((e) => e.id === id);
    if (evidence) {
      setDescription(evidence.description);
      setEvidenceType(evidence.evidenceType);
      setReliability(evidence.reliability);
      setSource(evidence.source || '');
      setShowEditDialog(id);
    }
  };

  const handleAISuggest = async () => {
    if (!llmConfig.enabled) return;

    setIsLoadingAI(true);
    setAiError(null);
    setAiSuggestions([]);

    const result = await suggestEvidence(
      llmConfig,
      analysis.focusQuestion,
      analysis.hypotheses,
      analysis.evidence
    );

    setIsLoadingAI(false);

    if (result.success) {
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
    const evType = parseEvidenceType(suggestion);
    // Clean up the suggestion text
    const cleanDesc = suggestion
      .replace(/\(fact\)|\(testimony\)|\(document\)|\(assumption\)|\(argument\)/gi, '')
      .trim();
    addEvidence(cleanDesc, evType, 'medium');
  };

  // Mark step complete when 1+ evidence exists
  if (analysis.evidence.length >= 1 && !analysis.stepsCompleted.includes(2)) {
    markStepComplete(2);
  }

  return (
    <div className="space-y-6">
      {/* Guidance */}
      {showStepGuidance && <GuidancePanel step={2} />}

      {/* Add Button */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-white">
          Evidence ({analysis.evidence.length})
        </h3>
        <div className="flex gap-2">
          {llmConfig.enabled && (
            <Button
              onClick={handleAISuggest}
              variant="secondary"
              icon={isLoadingAI ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              disabled={isLoadingAI || analysis.hypotheses.length < 2}
            >
              {isLoadingAI ? 'Thinking...' : 'AI Suggest'}
            </Button>
          )}
          <Button onClick={() => setShowAddDialog(true)} icon={<Plus className="w-4 h-4" />}>
            Add Evidence
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

      {/* Evidence List */}
      {analysis.evidence.length === 0 ? (
        <div className="text-center py-12 bg-gray-800 rounded-lg border border-gray-700">
          <p className="text-gray-400 mb-4">No evidence yet. Add at least 1 to continue.</p>
          <Button onClick={() => setShowAddDialog(true)} icon={<Plus className="w-4 h-4" />}>
            Add First Evidence
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {analysis.evidence.map((evidence) => (
            <div
              key={evidence.id}
              className="bg-gray-800 rounded-lg border border-gray-700 p-4"
            >
              <div className="flex items-start gap-4">
                {/* Label and type icon */}
                <div className="flex items-center gap-2 min-w-[80px]">
                  <span className="text-lg font-bold text-white">{evidence.label}</span>
                  <span className="text-gray-500" title={evidence.evidenceType}>
                    {EVIDENCE_TYPE_ICONS[evidence.evidenceType]}
                  </span>
                </div>

                {/* Description and metadata */}
                <div className="flex-1">
                  <p className="text-gray-200">{evidence.description}</p>
                  <div className="flex items-center gap-4 mt-2 text-sm">
                    <span className="text-gray-500 capitalize">{evidence.evidenceType}</span>
                    <span className={`capitalize ${RELIABILITY_COLORS[evidence.reliability]}`}>
                      {evidence.reliability} reliability
                    </span>
                    {evidence.source && (
                      <span className="text-gray-500">Source: {evidence.source}</span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => openEditDialog(evidence.id)}
                    className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                    title="Edit"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(evidence.id)}
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

      {/* Add/Edit Dialog */}
      <Dialog
        open={showAddDialog || showEditDialog !== null}
        onClose={() => {
          setShowAddDialog(false);
          setShowEditDialog(null);
          resetForm();
        }}
        title={showEditDialog ? 'Edit Evidence' : 'Add Evidence'}
        size="lg"
      >
        <div className="space-y-4">
          <TextArea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe this piece of evidence..."
            rows={4}
            autoFocus
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Type"
              value={evidenceType}
              onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
              options={EVIDENCE_TYPES.map((t) => ({ value: t, label: t.charAt(0).toUpperCase() + t.slice(1) }))}
            />
            <Select
              label="Reliability"
              value={reliability}
              onChange={(e) => setReliability(e.target.value as Reliability)}
              options={RELIABILITY_OPTIONS.map((r) => ({ value: r, label: r.charAt(0).toUpperCase() + r.slice(1) }))}
            />
          </div>

          <Input
            label="Source (optional)"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Where does this evidence come from?"
          />

          <div className="flex justify-end gap-3 mt-6">
            <Button variant="secondary" onClick={() => {
              setShowAddDialog(false);
              setShowEditDialog(null);
              resetForm();
            }}>
              Cancel
            </Button>
            <Button
              onClick={() => showEditDialog ? handleEdit(showEditDialog) : handleAdd()}
              disabled={!description.trim()}
            >
              {showEditDialog ? 'Save' : 'Add'}
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog
        open={showDeleteConfirm !== null}
        onClose={() => setShowDeleteConfirm(null)}
        title="Delete Evidence"
      >
        <p className="text-gray-300 mb-6">
          Are you sure you want to delete this evidence? This will also remove all associated ratings.
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
        title="AI Suggested Evidence"
        size="lg"
      >
        <div className="space-y-4">
          <p className="text-gray-400 text-sm">
            Click on a suggestion to add it as evidence. You can modify it after adding.
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
