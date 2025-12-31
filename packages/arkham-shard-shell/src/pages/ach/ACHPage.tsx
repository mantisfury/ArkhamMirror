/**
 * ACHPage - Analysis of Competing Hypotheses shard
 *
 * Implements Heuer's 8-step ACH methodology:
 * 1. Identify Hypotheses
 * 2. List Evidence
 * 3. Rate the Matrix
 * 4. Analyze Diagnosticity
 * 5. Refine the Matrix
 * 6. Draw Conclusions
 * 7. Sensitivity Analysis
 * 8. Report & Milestones
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useToast } from '../../context/ToastContext';
import { useConfirm } from '../../context/ConfirmContext';
import { Icon } from '../../components/common/Icon';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

import * as api from './api';
import type {
  ACHMatrix,
  MatrixListItem,
  ConsistencyRating,
  EvidenceType,
  HypothesisSuggestion,
  EvidenceSuggestion,
  RatingSuggestion,
  MilestoneSuggestion,
  Challenge,
  SensitivityResult,
  ConsistencyCheck,
  DiagnosticityReport,
} from './types';
import { RATING_COLORS, RATING_LABELS, RATING_OPTIONS, EVIDENCE_TYPE_OPTIONS } from './types';

// Import ACH-specific components
import {
  StepIndicator,
  GuidancePanel,
  AIHypothesesDialog,
  AIEvidenceDialog,
  AIRatingsDialog,
  DevilsAdvocateDialog,
  AIMilestonesDialog,
  ScoresSection,
  ConsistencyChecksSection,
  SensitivitySection,
  MilestonesSection,
  LinkedDocumentsSection,
} from './components';

// ============================================
// Main Page Component
// ============================================

export function ACHPage() {
  const [searchParams, _setSearchParams] = useSearchParams();
  void _setSearchParams;
  const matrixId = searchParams.get('matrixId');
  const view = searchParams.get('view') || 'list';

  // Show matrix detail if matrixId is set, otherwise show list
  if (matrixId) {
    return <MatrixDetailView matrixId={matrixId} />;
  }

  if (view === 'new') {
    return <CreateMatrixView />;
  }

  return <MatrixListView />;
}

// ============================================
// Matrix List View
// ============================================

function MatrixListView() {
  const [_searchParams, setSearchParams] = useSearchParams();
  void _searchParams;
  const { toast } = useToast();
  const confirm = useConfirm();

  const [matrices, setMatrices] = useState<MatrixListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMatrices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listMatrices();
      setMatrices(data.matrices);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load matrices');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMatrices();
  }, [fetchMatrices]);

  const handleDelete = async (matrix: MatrixListItem) => {
    const confirmed = await confirm({
      title: 'Delete Matrix',
      message: `Are you sure you want to delete "${matrix.title}"? This action cannot be undone.`,
      confirmLabel: 'Delete',
      variant: 'danger',
    });

    if (confirmed) {
      try {
        await api.deleteMatrix(matrix.id);
        toast.success(`Matrix "${matrix.title}" deleted`);
        fetchMatrices();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to delete matrix');
      }
    }
  };

  const handleOpenMatrix = (matrixId: string) => {
    setSearchParams({ matrixId });
  };

  const handleNewMatrix = () => {
    setSearchParams({ view: 'new' });
  };

  if (loading) {
    return (
      <div className="ach-page">
        <LoadingSkeleton type="list" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="ach-page">
        <div className="ach-error">
          <Icon name="AlertCircle" size={48} />
          <h2>Failed to load matrices</h2>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={fetchMatrices}>
            <Icon name="RefreshCw" size={16} />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ach-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Scale" size={28} />
          <div>
            <h1>ACH Analysis</h1>
            <p className="page-description">Analysis of Competing Hypotheses - Heuer's 8-Step Method</p>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-primary" onClick={handleNewMatrix}>
            <Icon name="Plus" size={16} />
            New Analysis
          </button>
        </div>
      </header>

      {matrices.length === 0 ? (
        <div className="ach-empty">
          <Icon name="Scale" size={64} />
          <h2>No ACH Analyses</h2>
          <p>Create your first Analysis of Competing Hypotheses to get started.</p>
          <button className="btn btn-primary" onClick={handleNewMatrix}>
            <Icon name="Plus" size={16} />
            Create Analysis
          </button>
        </div>
      ) : (
        <div className="ach-matrix-list">
          {matrices.map(matrix => (
            <div key={matrix.id} className="matrix-card" onClick={() => handleOpenMatrix(matrix.id)}>
              <div className="matrix-card-header">
                <h3>{matrix.title}</h3>
                <span className={`status-badge status-${matrix.status}`}>{matrix.status}</span>
              </div>
              {matrix.description && (
                <p className="matrix-card-description">{matrix.description}</p>
              )}
              <div className="matrix-card-stats">
                <span><Icon name="GitBranch" size={14} /> {matrix.hypothesis_count} hypotheses</span>
                <span><Icon name="FileText" size={14} /> {matrix.evidence_count} evidence</span>
              </div>
              <div className="matrix-card-footer">
                <span className="matrix-date">
                  Updated {new Date(matrix.updated_at).toLocaleDateString()}
                </span>
                <button
                  className="btn btn-icon btn-sm btn-danger"
                  onClick={(e) => { e.stopPropagation(); handleDelete(matrix); }}
                  title="Delete matrix"
                >
                  <Icon name="Trash2" size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// Create Matrix View
// ============================================

function CreateMatrixView() {
  const [_searchParams, setSearchParams] = useSearchParams();
  void _searchParams;
  const { toast } = useToast();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      toast.error('Title is required');
      return;
    }

    setSubmitting(true);
    try {
      const result = await api.createMatrix({ title: title.trim(), description: description.trim() });
      toast.success(`Analysis "${title}" created`);
      setSearchParams({ matrixId: result.matrix_id });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create analysis');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    setSearchParams({});
  };

  return (
    <div className="ach-page">
      <header className="page-header">
        <div className="page-title">
          <button className="btn btn-icon" onClick={handleCancel} title="Back to list">
            <Icon name="ArrowLeft" size={20} />
          </button>
          <div>
            <h1>New ACH Analysis</h1>
            <p className="page-description">Define your focus question - the central question you want to analyze</p>
          </div>
        </div>
      </header>

      <form className="ach-create-form" onSubmit={handleSubmit}>
        <div className="form-field">
          <label htmlFor="title">Title <span className="required">*</span></label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Short title for this analysis"
            disabled={submitting}
            autoFocus
          />
        </div>

        <div className="form-field">
          <label htmlFor="description">Focus Question</label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What question are you trying to answer? Be specific about the analytical problem."
            rows={4}
            disabled={submitting}
          />
          <p className="form-hint">
            Example: "Who is responsible for the security breach on December 15th?"
          </p>
        </div>

        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={handleCancel} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Creating...
              </>
            ) : (
              <>
                <Icon name="Plus" size={16} />
                Create Analysis
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

// ============================================
// Matrix Detail View - 8-Step Methodology
// ============================================

function MatrixDetailView({ matrixId }: { matrixId: string }) {
  const [_searchParams, setSearchParams] = useSearchParams();
  void _searchParams;
  const { toast } = useToast();
  const _confirm = useConfirm();
  void _confirm;

  // State
  const [matrix, setMatrix] = useState<ACHMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  // Step management (persisted in URL)
  const stepFromUrl = parseInt(_searchParams.get('step') || '1', 10);
  const [currentStep, setCurrentStepState] = useState(
    stepFromUrl >= 1 && stepFromUrl <= 8 ? stepFromUrl : 1
  );
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);

  // Sync step with URL
  const setCurrentStep = useCallback((step: number) => {
    setCurrentStepState(step);
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      newParams.set('step', step.toString());
      return newParams;
    });
  }, [setSearchParams]);

  // Dialog state
  const [showAddHypothesis, setShowAddHypothesis] = useState(false);
  const [showAddEvidence, setShowAddEvidence] = useState(false);
  const [editingRating, setEditingRating] = useState<{ evidenceId: string; hypothesisId: string } | null>(null);

  // AI state
  const [aiAvailable, setAiAvailable] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [showAIHypotheses, setShowAIHypotheses] = useState(false);
  const [showAIEvidence, setShowAIEvidence] = useState(false);
  const [showAIRatings, setShowAIRatings] = useState(false);
  const [showDevilsAdvocate, setShowDevilsAdvocate] = useState(false);
  const [showAIMilestones, setShowAIMilestones] = useState(false);

  // AI suggestions
  const [hypothesisSuggestions, setHypothesisSuggestions] = useState<HypothesisSuggestion[]>([]);
  const [evidenceSuggestions, setEvidenceSuggestions] = useState<EvidenceSuggestion[]>([]);
  const [ratingSuggestions, setRatingSuggestions] = useState<RatingSuggestion[]>([]);
  const [ratingEvidenceId, setRatingEvidenceId] = useState('');
  const [ratingEvidenceLabel, setRatingEvidenceLabel] = useState('');
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [milestoneSuggestions, setMilestoneSuggestions] = useState<MilestoneSuggestion[]>([]);

  // Sensitivity
  const [sensitivityResults, setSensitivityResults] = useState<SensitivityResult[] | null>(null);
  const [sensitivityNotes, setSensitivityNotes] = useState('');
  const [sensitivityLoading, setSensitivityLoading] = useState(false);

  // Consistency checks
  const [consistencyChecks, setConsistencyChecks] = useState<ConsistencyCheck[]>([]);

  // Diagnosticity
  const _diagnosticityReport = useState<DiagnosticityReport | null>(null)[0];
  void _diagnosticityReport;

  // Milestones
  const [milestones, setMilestones] = useState<any[]>([]);
  const [selectedMilestoneHypothesis, setSelectedMilestoneHypothesis] = useState('all');
  const milestonesLoadedRef = useRef(false);

  // Fetch matrix data
  const fetchMatrix = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMatrix(matrixId);
      setMatrix(data);

      // Check AI status
      try {
        const aiStatus = await api.getAIStatus();
        setAiAvailable(aiStatus.available);
      } catch {
        setAiAvailable(false);
      }

      // Calculate completed steps based on matrix state
      const completed: number[] = [];
      if (data.hypotheses.length >= 2) completed.push(1);
      if (data.evidence.length >= 1) completed.push(2);
      if (data.ratings.length >= data.hypotheses.length * data.evidence.length * 0.5) completed.push(3);
      setCompletedSteps(completed);

      // Run consistency checks
      runConsistencyChecks(data);

      // Load milestones from localStorage
      try {
        const savedMilestones = localStorage.getItem(`ach-milestones-${matrixId}`);
        if (savedMilestones) {
          setMilestones(JSON.parse(savedMilestones));
        }
        milestonesLoadedRef.current = true;
      } catch (e) {
        console.error('Failed to load milestones from localStorage:', e);
        milestonesLoadedRef.current = true;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load matrix');
    } finally {
      setLoading(false);
    }
  }, [matrixId]);

  useEffect(() => {
    fetchMatrix();
  }, [fetchMatrix]);

  // Save milestones to localStorage whenever they change
  useEffect(() => {
    // Only save after initial load to avoid clearing saved data
    if (!milestonesLoadedRef.current || !matrixId) return;

    try {
      if (milestones.length > 0) {
        localStorage.setItem(`ach-milestones-${matrixId}`, JSON.stringify(milestones));
      } else {
        // Clear localStorage when all milestones are deleted
        localStorage.removeItem(`ach-milestones-${matrixId}`);
      }
    } catch (e) {
      console.error('Failed to save milestones to localStorage:', e);
    }
  }, [matrixId, milestones]);

  // Run consistency checks
  const runConsistencyChecks = (m: ACHMatrix) => {
    const checks: ConsistencyCheck[] = [];

    // Check for minimum hypotheses
    checks.push({
      passed: m.hypotheses.length >= 2,
      message: m.hypotheses.length >= 2
        ? `${m.hypotheses.length} hypotheses defined`
        : 'Need at least 2 hypotheses',
    });

    // Check for evidence
    checks.push({
      passed: m.evidence.length >= 1,
      message: m.evidence.length >= 1
        ? `${m.evidence.length} evidence items`
        : 'No evidence added yet',
    });

    // Check matrix completion
    const totalCells = m.hypotheses.length * m.evidence.length;
    const ratedCells = m.ratings.length;
    const completionPct = totalCells > 0 ? (ratedCells / totalCells * 100).toFixed(0) : 0;
    checks.push({
      passed: Number(completionPct) >= 80,
      message: `Matrix ${completionPct}% complete (${ratedCells}/${totalCells} cells rated)`,
    });

    // Check for unrated cells
    if (totalCells > 0 && ratedCells < totalCells) {
      checks.push({
        passed: false,
        message: `${totalCells - ratedCells} cells still need ratings`,
      });
    }

    setConsistencyChecks(checks);
  };

  // Navigation handlers
  const handleBack = () => {
    setSearchParams({});
  };

  const handleStepClick = (step: number) => {
    setCurrentStep(step);
  };

  const handlePrevStep = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  const handleNextStep = () => {
    if (currentStep < 8) setCurrentStep(currentStep + 1);
  };

  // Rating handlers
  const getRating = (evidenceId: string, hypothesisId: string): ConsistencyRating | null => {
    if (!matrix) return null;
    const rating = matrix.ratings.find(
      r => r.evidence_id === evidenceId && r.hypothesis_id === hypothesisId
    );
    return rating?.rating || null;
  };

  const handleRatingClick = (evidenceId: string, hypothesisId: string) => {
    setEditingRating({ evidenceId, hypothesisId });
  };

  const handleRatingUpdate = async (rating: ConsistencyRating, reasoning: string) => {
    if (!editingRating || !matrix) return;

    try {
      await api.updateRating({
        matrix_id: matrixId,
        evidence_id: editingRating.evidenceId,
        hypothesis_id: editingRating.hypothesisId,
        rating,
        reasoning,
      });
      toast.success('Rating updated');
      setEditingRating(null);
      await fetchMatrix();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update rating');
      setEditingRating(null);
    }
  };

  // Hypothesis handlers
  const handleAddHypothesis = async (title: string, description: string) => {
    try {
      await api.addHypothesis({ matrix_id: matrixId, title, description });
      toast.success('Hypothesis added');
      setShowAddHypothesis(false);
      await fetchMatrix();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add hypothesis');
      setShowAddHypothesis(false);
    }
  };

  const handleRemoveHypothesis = async (hypothesisId: string, title: string) => {
    // Use window.confirm as fallback if useConfirm doesn't work
    const confirmed = window.confirm(`Remove "${title}" from the matrix? All ratings for this hypothesis will be deleted.`);

    if (confirmed) {
      try {
        await api.removeHypothesis(matrixId, hypothesisId);
        toast.success('Hypothesis removed');
        await fetchMatrix();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to remove hypothesis');
      }
    }
  };

  // Evidence handlers
  const handleAddEvidence = async (description: string, source: string, evidenceType: EvidenceType, credibility: number) => {
    try {
      await api.addEvidence({
        matrix_id: matrixId,
        description,
        source,
        evidence_type: evidenceType,
        credibility,
      });
      toast.success('Evidence added');
      setShowAddEvidence(false);
      await fetchMatrix();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add evidence');
      setShowAddEvidence(false);
    }
  };

  const handleRemoveEvidence = async (evidenceId: string, description: string) => {
    const confirmed = window.confirm(`Remove "${description.substring(0, 50)}..." from the matrix?`);

    if (confirmed) {
      try {
        await api.removeEvidence(matrixId, evidenceId);
        toast.success('Evidence removed');
        await fetchMatrix();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to remove evidence');
      }
    }
  };

  // Score handlers
  const handleRecalculateScores = async () => {
    try {
      await api.calculateScores(matrixId);
      toast.success('Scores recalculated');
      await fetchMatrix();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to calculate scores');
    }
  };

  // AI handlers
  const handleRequestHypothesisSuggestions = async () => {
    if (!matrix) return;
    setAiLoading(true);
    try {
      const result = await api.suggestHypotheses({
        focus_question: matrix.description || matrix.title,
        matrix_id: matrixId,
      });
      setHypothesisSuggestions(result.suggestions.map(s => ({
        title: s.title,
        description: s.description,
      })));
      setShowAIHypotheses(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to get suggestions');
    } finally {
      setAiLoading(false);
    }
  };

  const handleAcceptHypothesisSuggestion = async (index: number) => {
    const suggestion = hypothesisSuggestions[index];
    if (!suggestion) return;
    try {
      await api.addHypothesis({
        matrix_id: matrixId,
        title: suggestion.title,
        description: suggestion.description,
      });
      toast.success('Hypothesis added');
      const remaining = hypothesisSuggestions.filter((_, i) => i !== index);
      setHypothesisSuggestions(remaining);
      if (remaining.length === 0) {
        setShowAIHypotheses(false);
      }
      await fetchMatrix();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add hypothesis');
    }
  };

  const handleAcceptAllHypothesisSuggestions = async () => {
    for (const suggestion of hypothesisSuggestions) {
      try {
        await api.addHypothesis({
          matrix_id: matrixId,
          title: suggestion.title,
          description: suggestion.description,
        });
      } catch {
        // Continue with others
      }
    }
    toast.success('All hypotheses added');
    setShowAIHypotheses(false);
    setHypothesisSuggestions([]);
    await fetchMatrix();
  };

  const handleRequestEvidenceSuggestions = async () => {
    if (!matrix) return;
    setAiLoading(true);
    try {
      const result = await api.suggestEvidence({
        matrix_id: matrixId,
        focus_question: matrix.description || matrix.title,
      });
      setEvidenceSuggestions(result.suggestions.map(s => ({
        description: s.description,
        evidence_type: s.evidence_type as EvidenceType,
        source: s.source,
      })));
      setShowAIEvidence(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to get suggestions');
    } finally {
      setAiLoading(false);
    }
  };

  const handleAcceptEvidenceSuggestion = async (index: number) => {
    const suggestion = evidenceSuggestions[index];
    if (!suggestion) return;
    try {
      await api.addEvidence({
        matrix_id: matrixId,
        description: suggestion.description,
        evidence_type: suggestion.evidence_type,
        source: suggestion.source,
      });
      toast.success('Evidence added');
      const remaining = evidenceSuggestions.filter((_, i) => i !== index);
      setEvidenceSuggestions(remaining);
      if (remaining.length === 0) {
        setShowAIEvidence(false);
      }
      await fetchMatrix();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add evidence');
    }
  };

  const handleRequestRatingSuggestions = async (evidenceId: string) => {
    if (!matrix) return;
    const evidence = matrix.evidence.find(e => e.id === evidenceId);
    if (!evidence) return;

    setAiLoading(true);
    try {
      const result = await api.suggestRatings({
        matrix_id: matrixId,
        evidence_id: evidenceId,
      });
      setRatingSuggestions(result.suggestions);
      setRatingEvidenceId(evidenceId);
      setRatingEvidenceLabel(evidence.description.substring(0, 50));
      setShowAIRatings(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to get suggestions');
    } finally {
      setAiLoading(false);
    }
  };

  const handleAcceptRatingSuggestion = async (hypothesisId: string, rating: ConsistencyRating) => {
    const suggestion = ratingSuggestions.find(s => s.hypothesis_id === hypothesisId);
    if (!suggestion || !ratingEvidenceId) return;
    try {
      await api.updateRating({
        matrix_id: matrixId,
        evidence_id: ratingEvidenceId,
        hypothesis_id: hypothesisId,
        rating,
        reasoning: suggestion.explanation,
      });
      toast.success('Rating updated');
      setRatingSuggestions(prev => prev.filter(s => s.hypothesis_id !== hypothesisId));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update rating');
    }
  };

  const handleDevilsAdvocate = async () => {
    setAiLoading(true);
    try {
      const result = await api.runDevilsAdvocate({ matrix_id: matrixId });
      setChallenges([{
        hypothesis_id: result.hypothesis_id,
        hypothesis_label: result.hypothesis_title,
        counter_argument: result.challenge_text,
        disproof_evidence: result.evidence_gaps.join(', '),
        alternative_angle: result.alternative_interpretation,
        weaknesses: result.weaknesses,
      }]);
      setShowDevilsAdvocate(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to run analysis');
    } finally {
      setAiLoading(false);
    }
  };

  const handleSaveChallengesToNotes = () => {
    const notesText = challenges.map(c =>
      `[${c.hypothesis_label}]\nCounter-argument: ${c.counter_argument}\nDisproof: ${c.disproof_evidence}\nAlternative: ${c.alternative_angle}`
    ).join('\n\n');
    setSensitivityNotes(prev => prev + '\n\n--- AI Challenges ---\n' + notesText);
    toast.success('Challenges saved to notes');
    setShowDevilsAdvocate(false);
  };

  // Sensitivity handlers
  const handleRunSensitivity = async () => {
    setSensitivityLoading(true);
    try {
      const result = await api.getSensitivity(matrixId) as {
        sensitivity: string;
        uncertain_evidence_count: number;
        rank_changes: Array<{
          hypothesis_id: string;
          hypothesis_title: string;
          original_rank: number;
          new_rank: number;
          change: number;
        }>;
      };

      // Transform backend response to frontend format
      const results: SensitivityResult[] = result.rank_changes.map(change => ({
        evidence_id: change.hypothesis_id,
        evidence_label: change.hypothesis_title,
        impact: Math.abs(change.change) >= 2 ? 'critical' as const :
                Math.abs(change.change) === 1 ? 'moderate' as const : 'minor' as const,
        description: `Rank changed from ${change.original_rank} to ${change.new_rank} (${change.change > 0 ? '+' : ''}${change.change})`,
        affected_rankings: [change.hypothesis_title],
      }));

      setSensitivityResults(results);

      if (results.length === 0) {
        toast.info(`Sensitivity: ${result.sensitivity} - ${result.uncertain_evidence_count} uncertain evidence items`);
      } else {
        toast.success('Sensitivity analysis complete');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to run analysis');
    } finally {
      setSensitivityLoading(false);
    }
  };

  // Export handlers
  const handleExportMarkdown = async () => {
    try {
      const result = await api.exportMatrix(matrixId, 'markdown');
      // Trigger download
      const blob = new Blob([result.content as string], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${matrix?.title || 'ach-analysis'}.md`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Exported to Markdown');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export');
    }
  };

  const handleExportJSON = async () => {
    try {
      const result = await api.exportMatrix(matrixId, 'json');
      const blob = new Blob([JSON.stringify(result.content, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${matrix?.title || 'ach-analysis'}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Exported to JSON');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export');
    }
  };

  const handleExportPDF = async () => {
    try {
      const result = await api.exportMatrix(matrixId, 'html');
      // Open HTML in new window for printing to PDF
      const win = window.open('', '_blank');
      if (win) {
        win.document.write(result.content as string);
        win.document.close();
        toast.info('PDF preview opened - use Print to save as PDF');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export');
    }
  };

  // Loading/Error states
  if (loading) {
    return (
      <div className="ach-page">
        <LoadingSkeleton type="list" />
      </div>
    );
  }

  if (error || !matrix) {
    return (
      <div className="ach-page">
        <div className="ach-error">
          <Icon name="AlertCircle" size={48} />
          <h2>Failed to load analysis</h2>
          <p>{error || 'Analysis not found'}</p>
          <div className="error-actions">
            <button className="btn btn-secondary" onClick={handleBack}>
              <Icon name="ArrowLeft" size={16} />
              Back to List
            </button>
            <button className="btn btn-primary" onClick={fetchMatrix}>
              <Icon name="RefreshCw" size={16} />
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Calculate diagnosticity for evidence
  const getEvidenceDiagnosticity = (evidenceId: string): 'high' | 'low' | 'normal' => {
    if (!matrix || matrix.hypotheses.length < 2) return 'normal';
    const ratings = matrix.ratings.filter(r => r.evidence_id === evidenceId);
    if (ratings.length < 2) return 'normal';

    const uniqueRatings = new Set(ratings.map(r => r.rating));
    if (uniqueRatings.size >= matrix.hypotheses.length * 0.7) return 'high';
    if (uniqueRatings.size === 1) return 'low';
    return 'normal';
  };

  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return <HypothesesSection
          matrix={matrix}
          aiAvailable={aiAvailable}
          aiLoading={aiLoading}
          onAddHypothesis={() => setShowAddHypothesis(true)}
          onRemoveHypothesis={handleRemoveHypothesis}
          onAISuggest={handleRequestHypothesisSuggestions}
          onDevilsAdvocate={handleDevilsAdvocate}
        />;
      case 2:
        return <EvidenceSection
          matrix={matrix}
          aiAvailable={aiAvailable}
          aiLoading={aiLoading}
          onAddEvidence={() => setShowAddEvidence(true)}
          onRemoveEvidence={handleRemoveEvidence}
          onAISuggest={handleRequestEvidenceSuggestions}
        />;
      case 3:
        return <MatrixSection
          matrix={matrix}
          zoom={zoom}
          onZoomIn={() => setZoom(Math.min(2, zoom + 0.1))}
          onZoomOut={() => setZoom(Math.max(0.5, zoom - 0.1))}
          onRatingClick={handleRatingClick}
          onAISuggestRatings={handleRequestRatingSuggestions}
          onRecalculate={handleRecalculateScores}
          getRating={getRating}
          getEvidenceDiagnosticity={getEvidenceDiagnosticity}
        />;
      case 4:
        return <DiagnosticitySection
          matrix={matrix}
          getEvidenceDiagnosticity={getEvidenceDiagnosticity}
          onRemoveEvidence={handleRemoveEvidence}
        />;
      case 5:
        return (
          <div className="step-5-content">
            <HypothesesSection
              matrix={matrix}
              aiAvailable={aiAvailable}
              aiLoading={aiLoading}
              onAddHypothesis={() => setShowAddHypothesis(true)}
              onRemoveHypothesis={handleRemoveHypothesis}
              onAISuggest={handleRequestHypothesisSuggestions}
              onDevilsAdvocate={handleDevilsAdvocate}
            />
            <EvidenceSection
              matrix={matrix}
              aiAvailable={aiAvailable}
              aiLoading={aiLoading}
              onAddEvidence={() => setShowAddEvidence(true)}
              onRemoveEvidence={handleRemoveEvidence}
              onAISuggest={handleRequestEvidenceSuggestions}
            />
            <MatrixSection
              matrix={matrix}
              zoom={zoom}
              onZoomIn={() => setZoom(Math.min(2, zoom + 0.1))}
              onZoomOut={() => setZoom(Math.max(0.5, zoom - 0.1))}
              onRatingClick={handleRatingClick}
              onAISuggestRatings={handleRequestRatingSuggestions}
              onRecalculate={handleRecalculateScores}
              getRating={getRating}
              getEvidenceDiagnosticity={getEvidenceDiagnosticity}
            />
          </div>
        );
      case 6:
        return (
          <div className="step-6-content">
            <ScoresSection
              scores={matrix.scores}
              onRecalculate={handleRecalculateScores}
            />
            <ConsistencyChecksSection checks={consistencyChecks} />
          </div>
        );
      case 7:
        return <SensitivitySection
          results={sensitivityResults}
          notes={sensitivityNotes}
          isLoading={sensitivityLoading}
          onRunAnalysis={handleRunSensitivity}
          onNotesChange={setSensitivityNotes}
          onSaveNotes={() => toast.success('Notes saved')}
        />;
      case 8:
        return <MilestonesSection
          milestones={milestones}
          hypotheses={matrix.hypotheses.map(h => ({ id: h.id, title: h.title }))}
          aiAvailable={aiAvailable}
          isAILoading={aiLoading}
          selectedHypothesis={selectedMilestoneHypothesis}
          onHypothesisSelect={setSelectedMilestoneHypothesis}
          onAISuggest={async () => {
            setAiLoading(true);
            try {
              const result = await api.suggestMilestones(matrixId);
              setMilestoneSuggestions(result.suggestions);
              setShowAIMilestones(true);
            } catch (err) {
              toast.error(err instanceof Error ? err.message : 'Failed to get suggestions');
            } finally {
              setAiLoading(false);
            }
          }}
          onAddMilestone={() => {
            // Simple add milestone with prompt
            const description = window.prompt('Enter milestone description:');
            if (description) {
              const hypId = selectedMilestoneHypothesis !== 'all'
                ? selectedMilestoneHypothesis
                : matrix.hypotheses[0]?.id || '';
              const hypTitle = matrix.hypotheses.find(h => h.id === hypId)?.title || 'General';
              const newMilestone = {
                id: `milestone-${Date.now()}`,
                description,
                hypothesis_id: hypId,
                hypothesis_label: hypTitle,
                expected_by: null,
                observed: 0 as const,
                observation_notes: '',
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              };
              setMilestones(prev => [...prev, newMilestone]);
              toast.success('Milestone added');
            }
          }}
          onEditMilestone={(id) => {
            const milestone = milestones.find(m => m.id === id);
            if (milestone) {
              const newDesc = window.prompt('Edit milestone description:', milestone.description);
              if (newDesc && newDesc !== milestone.description) {
                setMilestones(prev => prev.map(m =>
                  m.id === id ? { ...m, description: newDesc, updated_at: new Date().toISOString() } : m
                ));
                toast.success('Milestone updated');
              }
            }
          }}
          onDeleteMilestone={(id) => {
            if (window.confirm('Delete this milestone?')) {
              setMilestones(prev => prev.filter(m => m.id !== id));
              toast.success('Milestone deleted');
            }
          }}
          onExportMarkdown={handleExportMarkdown}
          onExportJSON={handleExportJSON}
          onExportPDF={handleExportPDF}
        />;
      default:
        return null;
    }
  };

  return (
    <div className="ach-page ach-detail">
      {/* Header */}
      <header className="page-header">
        <div className="page-title">
          <button className="btn btn-icon" onClick={handleBack} title="Back to list">
            <Icon name="ArrowLeft" size={20} />
          </button>
          <div>
            <h1>{matrix.title}</h1>
            <p className="page-description">{matrix.description || 'Analysis of Competing Hypotheses'}</p>
          </div>
          <span className={`status-badge status-${matrix.status}`}>{matrix.status}</span>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={() => setShowAddHypothesis(true)}>
            <Icon name="Plus" size={16} />
            Add Hypothesis
          </button>
          <button className="btn btn-secondary" onClick={() => setShowAddEvidence(true)}>
            <Icon name="Plus" size={16} />
            Add Evidence
          </button>
          {aiAvailable && (
            <button
              className="btn btn-primary"
              onClick={handleDevilsAdvocate}
              disabled={aiLoading}
            >
              {aiLoading ? (
                <Icon name="Loader2" size={16} className="spin" />
              ) : (
                <Icon name="Bot" size={16} />
              )}
              Devil's Advocate
            </button>
          )}
        </div>
      </header>

      {/* Step Indicator */}
      <StepIndicator
        currentStep={currentStep}
        completedSteps={completedSteps}
        onStepClick={handleStepClick}
        onPrevStep={handlePrevStep}
        onNextStep={handleNextStep}
      />

      {/* Guidance Panel */}
      <GuidancePanel currentStep={currentStep} />

      {/* Step Content */}
      <div className="step-content">
        {renderStepContent()}
      </div>

      {/* Quick View Accordions (after step 3) */}
      {currentStep >= 3 && currentStep < 6 && (
        <div className="quick-views">
          <details className="quick-view-accordion">
            <summary>Quick View: Scores</summary>
            <ScoresSection scores={matrix.scores} onRecalculate={handleRecalculateScores} />
          </details>
          <details className="quick-view-accordion">
            <summary>Quick View: Consistency Checks</summary>
            <ConsistencyChecksSection checks={consistencyChecks} />
          </details>
        </div>
      )}

      {/* Linked Documents Section */}
      <LinkedDocumentsSection
        matrixId={matrixId}
        linkedDocumentIds={matrix.linked_document_ids || []}
        onDocumentsChanged={fetchMatrix}
      />

      {/* Dialogs */}
      {showAddHypothesis && (
        <AddHypothesisDialog
          onSubmit={handleAddHypothesis}
          onCancel={() => setShowAddHypothesis(false)}
        />
      )}

      {showAddEvidence && (
        <AddEvidenceDialog
          onSubmit={handleAddEvidence}
          onCancel={() => setShowAddEvidence(false)}
        />
      )}

      {editingRating && (
        <RatingDialog
          currentRating={getRating(editingRating.evidenceId, editingRating.hypothesisId)}
          onSubmit={handleRatingUpdate}
          onCancel={() => setEditingRating(null)}
        />
      )}

      {/* AI Dialogs */}
      {showAIHypotheses && (
        <AIHypothesesDialog
          suggestions={hypothesisSuggestions}
          onAccept={handleAcceptHypothesisSuggestion}
          onAcceptAll={handleAcceptAllHypothesisSuggestions}
          onClose={() => setShowAIHypotheses(false)}
        />
      )}

      {showAIEvidence && (
        <AIEvidenceDialog
          suggestions={evidenceSuggestions}
          onAccept={handleAcceptEvidenceSuggestion}
          onClose={() => setShowAIEvidence(false)}
        />
      )}

      {showAIRatings && (
        <AIRatingsDialog
          evidenceLabel={ratingEvidenceLabel}
          suggestions={ratingSuggestions}
          onAccept={async (hypothesisId, rating) => {
            await handleAcceptRatingSuggestion(hypothesisId, rating);
            const remaining = ratingSuggestions.filter(s => s.hypothesis_id !== hypothesisId);
            if (remaining.length === 0) {
              setShowAIRatings(false);
            }
            await fetchMatrix();
          }}
          onAcceptAll={async () => {
            if (!ratingEvidenceId) return;
            const suggestionsToApply = [...ratingSuggestions];
            for (const suggestion of suggestionsToApply) {
              try {
                await api.updateRating({
                  matrix_id: matrixId,
                  evidence_id: ratingEvidenceId,
                  hypothesis_id: suggestion.hypothesis_id,
                  rating: suggestion.rating,
                  reasoning: suggestion.explanation,
                });
              } catch (err) {
                toast.error(err instanceof Error ? err.message : 'Failed to update rating');
              }
            }
            toast.success('All ratings applied');
            setRatingSuggestions([]);
            setShowAIRatings(false);
            await fetchMatrix();
          }}
          onClose={() => setShowAIRatings(false)}
        />
      )}

      {showDevilsAdvocate && (
        <DevilsAdvocateDialog
          challenges={challenges}
          onSaveToNotes={handleSaveChallengesToNotes}
          onClose={() => setShowDevilsAdvocate(false)}
        />
      )}

      {showAIMilestones && (
        <AIMilestonesDialog
          suggestions={milestoneSuggestions}
          onAccept={(s) => {
            // Add milestone to state
            const newMilestone = {
              id: `milestone-${Date.now()}`,
              description: s.description,
              hypothesis_id: s.hypothesis_id,
              hypothesis_label: s.hypothesis_label,
              expected_by: null,
              observed: 0 as const,
              observation_notes: '',
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            };
            setMilestones(prev => [...prev, newMilestone]);
            toast.success(`Milestone for ${s.hypothesis_label} added`);
            const remaining = milestoneSuggestions.filter(m => m.hypothesis_id !== s.hypothesis_id);
            setMilestoneSuggestions(remaining);
            if (remaining.length === 0) {
              setShowAIMilestones(false);
            }
          }}
          onAcceptAll={() => {
            // Add all milestones to state
            const newMilestones = milestoneSuggestions.map((s, i) => ({
              id: `milestone-${Date.now()}-${i}`,
              description: s.description,
              hypothesis_id: s.hypothesis_id,
              hypothesis_label: s.hypothesis_label,
              expected_by: null,
              observed: 0 as const,
              observation_notes: '',
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }));
            setMilestones(prev => [...prev, ...newMilestones]);
            setMilestoneSuggestions([]);
            toast.success('All milestones added');
            setShowAIMilestones(false);
          }}
          onClose={() => setShowAIMilestones(false)}
        />
      )}
    </div>
  );
}

// ============================================
// Hypotheses Section (Step 1)
// ============================================

interface HypothesesSectionProps {
  matrix: ACHMatrix;
  aiAvailable: boolean;
  aiLoading: boolean;
  onAddHypothesis: () => void;
  onRemoveHypothesis: (id: string, title: string) => void;
  onAISuggest: () => void;
  onDevilsAdvocate: () => void;
}

function HypothesesSection({
  matrix,
  aiAvailable,
  aiLoading,
  onAddHypothesis,
  onRemoveHypothesis,
  onAISuggest,
  onDevilsAdvocate,
}: HypothesesSectionProps) {
  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="Lightbulb" size={18} className="icon-blue" />
          <h3>Hypotheses</h3>
          <span className="badge">{matrix.hypotheses.length}</span>
        </div>
        <div className="section-actions">
          {aiAvailable && (
            <>
              <button
                className="btn btn-sm btn-soft btn-violet"
                onClick={onAISuggest}
                disabled={aiLoading}
              >
                {aiLoading ? <Icon name="Loader2" size={12} className="spin" /> : <Icon name="Sparkles" size={12} />}
                AI Suggest
              </button>
              {matrix.hypotheses.length > 0 && (
                <button
                  className="btn btn-sm btn-soft btn-orange"
                  onClick={onDevilsAdvocate}
                  disabled={aiLoading}
                >
                  <Icon name="Swords" size={12} />
                  Challenge
                </button>
              )}
            </>
          )}
          <button className="btn btn-sm btn-soft" onClick={onAddHypothesis}>
            <Icon name="Plus" size={14} />
            Add Hypothesis
          </button>
        </div>
      </div>

      {matrix.hypotheses.length === 0 ? (
        <div className="empty-state">
          <p>Add at least 2 hypotheses to begin</p>
        </div>
      ) : (
        <div className="hypothesis-list">
          {matrix.hypotheses.map((h, i) => (
            <div key={h.id} className="hypothesis-card">
              <div className="hypothesis-content">
                <div className="hypothesis-header">
                  <span className="hypothesis-label">H{i + 1}</span>
                  <span className="hypothesis-title">{h.title}</span>
                </div>
                <p className="hypothesis-description">{h.description}</p>
              </div>
              <div className="hypothesis-actions">
                <button
                  className="btn btn-icon btn-sm btn-danger"
                  onClick={() => onRemoveHypothesis(h.id, h.title)}
                  title="Remove hypothesis"
                >
                  <Icon name="Trash2" size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// Evidence Section (Step 2)
// ============================================

interface EvidenceSectionProps {
  matrix: ACHMatrix;
  aiAvailable: boolean;
  aiLoading: boolean;
  onAddEvidence: () => void;
  onRemoveEvidence: (id: string, description: string) => void;
  onAISuggest: () => void;
}

function EvidenceSection({
  matrix,
  aiAvailable,
  aiLoading,
  onAddEvidence,
  onRemoveEvidence,
  onAISuggest,
}: EvidenceSectionProps) {
  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="FileText" size={18} className="icon-green" />
          <h3>Evidence</h3>
          <span className="badge">{matrix.evidence.length}</span>
        </div>
        <div className="section-actions">
          {aiAvailable && (
            <button
              className="btn btn-sm btn-soft btn-violet"
              onClick={onAISuggest}
              disabled={aiLoading}
            >
              {aiLoading ? <Icon name="Loader2" size={12} className="spin" /> : <Icon name="Sparkles" size={12} />}
              AI Suggest
            </button>
          )}
          <button className="btn btn-sm btn-soft" onClick={onAddEvidence}>
            <Icon name="Plus" size={14} />
            Add Evidence
          </button>
        </div>
      </div>

      {matrix.evidence.length === 0 ? (
        <div className="empty-state">
          <p>Add evidence to rate against hypotheses</p>
        </div>
      ) : (
        <div className="evidence-list">
          {matrix.evidence.map((e, i) => (
            <div key={e.id} className="evidence-card">
              <div className="evidence-content">
                <div className="evidence-header">
                  <span className="evidence-label">E{i + 1}</span>
                  <span className="badge badge-outline">{e.evidence_type}</span>
                  <span className={`badge badge-${getCredibilityClass(e.credibility)}`}>
                    {getCredibilityLabel(e.credibility)}
                  </span>
                </div>
                <p className="evidence-description">{e.description}</p>
                {e.source && <p className="evidence-source">Source: {e.source}</p>}
              </div>
              <div className="evidence-actions">
                <button
                  className="btn btn-icon btn-sm btn-danger"
                  onClick={() => onRemoveEvidence(e.id, e.description)}
                  title="Remove evidence"
                >
                  <Icon name="Trash2" size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// Matrix Section (Step 3)
// ============================================

interface MatrixSectionProps {
  matrix: ACHMatrix;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onRatingClick: (evidenceId: string, hypothesisId: string) => void;
  onAISuggestRatings: (evidenceId: string) => void;
  onRecalculate: () => void;
  getRating: (evidenceId: string, hypothesisId: string) => ConsistencyRating | null;
  getEvidenceDiagnosticity: (evidenceId: string) => 'high' | 'low' | 'normal';
}

function MatrixSection({
  matrix,
  zoom,
  onZoomIn,
  onZoomOut,
  onRatingClick,
  onAISuggestRatings,
  onRecalculate,
  getRating,
  getEvidenceDiagnosticity,
}: MatrixSectionProps) {
  const totalCells = matrix.hypotheses.length * matrix.evidence.length;
  const ratedCells = matrix.ratings.length;
  const completionPct = totalCells > 0 ? Math.round(ratedCells / totalCells * 100) : 0;

  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="Grid3X3" size={18} className="icon-purple" />
          <h3>Analysis Matrix</h3>
        </div>
        <div className="section-actions">
          <div className="completion-indicator">
            <span>Completion:</span>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${completionPct}%` }} />
            </div>
            <span>{completionPct}%</span>
          </div>
        </div>
      </div>

      {/* Zoom Controls */}
      <div className="zoom-controls">
        <button className="btn btn-icon btn-sm" onClick={onZoomOut} disabled={zoom <= 0.5}>
          <Icon name="ZoomOut" size={16} />
        </button>
        <span className="zoom-level">{Math.round(zoom * 100)}%</span>
        <button className="btn btn-icon btn-sm" onClick={onZoomIn} disabled={zoom >= 2}>
          <Icon name="ZoomIn" size={16} />
        </button>
        <button className="btn btn-sm btn-secondary" onClick={onRecalculate}>
          <Icon name="Calculator" size={14} />
          Recalculate
        </button>
      </div>

      {matrix.hypotheses.length === 0 || matrix.evidence.length === 0 ? (
        <div className="empty-state">
          <Icon name="Grid3X3" size={48} />
          <p>Add hypotheses and evidence to create the matrix</p>
        </div>
      ) : (
        <div className="ach-matrix-container" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
          <table className="ach-matrix">
            <thead>
              <tr>
                <th className="evidence-header">Evidence</th>
                {matrix.hypotheses.map((h, i) => (
                  <th key={h.id} className="hypothesis-header" title={h.description}>
                    H{i + 1}: {h.title}
                  </th>
                ))}
                <th className="ai-header">
                  <Icon name="Sparkles" size={12} />
                </th>
              </tr>
            </thead>
            <tbody>
              {matrix.evidence.map((e, i) => {
                const diagnosticity = getEvidenceDiagnosticity(e.id);
                return (
                  <tr
                    key={e.id}
                    className={`evidence-row diagnosticity-${diagnosticity}`}
                  >
                    <td className="evidence-cell">
                      <div className="evidence-cell-content">
                        <span className="evidence-label">E{i + 1}</span>
                        <span className="evidence-text" title={e.description}>
                          {e.description.substring(0, 40)}...
                        </span>
                        {diagnosticity === 'high' && (
                          <Icon name="Star" size={12} className="icon-amber" title="High diagnostic value" />
                        )}
                      </div>
                    </td>
                    {matrix.hypotheses.map((h) => {
                      const rating = getRating(e.id, h.id);
                      return (
                        <td
                          key={`${e.id}-${h.id}`}
                          className="rating-cell"
                          style={{ backgroundColor: rating ? RATING_COLORS[rating] : 'transparent' }}
                          onClick={() => onRatingClick(e.id, h.id)}
                          title={rating ? RATING_LABELS[rating] : 'Click to rate'}
                        >
                          {rating || '?'}
                        </td>
                      );
                    })}
                    <td className="ai-cell">
                      <button
                        className="btn btn-icon btn-xs"
                        onClick={() => onAISuggestRatings(e.id)}
                        title="AI suggest ratings"
                      >
                        <Icon name="Sparkles" size={10} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <td className="score-label">Inconsistency Score</td>
                {matrix.hypotheses.map((h) => {
                  const score = matrix.scores.find(s => s.hypothesis_id === h.id);
                  return (
                    <td key={h.id} className="score-cell">
                      {score?.inconsistency_count ?? '-'}
                    </td>
                  );
                })}
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="rating-legend">
        <span className="legend-label">Legend:</span>
        {RATING_OPTIONS.map(opt => (
          <div key={opt.value} className="legend-item">
            <span className="legend-color" style={{ backgroundColor: RATING_COLORS[opt.value] }} />
            <span>{opt.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================
// Diagnosticity Section (Step 4)
// ============================================

interface DiagnosticitySectionProps {
  matrix: ACHMatrix;
  getEvidenceDiagnosticity: (evidenceId: string) => 'high' | 'low' | 'normal';
  onRemoveEvidence: (id: string, description: string) => void;
}

function DiagnosticitySection({
  matrix,
  getEvidenceDiagnosticity,
  onRemoveEvidence,
}: DiagnosticitySectionProps) {
  const sortedEvidence = [...matrix.evidence].sort((a, b) => {
    const diagA = getEvidenceDiagnosticity(a.id);
    const diagB = getEvidenceDiagnosticity(b.id);
    const order = { high: 0, normal: 1, low: 2 };
    return order[diagA] - order[diagB];
  });

  return (
    <div className="ach-section">
      <div className="section-header">
        <div className="section-title">
          <Icon name="BarChart2" size={18} className="icon-amber" />
          <h3>Diagnosticity Analysis</h3>
        </div>
      </div>

      <p className="section-description">
        Evidence sorted by diagnostic value. High-diagnostic evidence helps distinguish between hypotheses.
        Consider removing low-diagnostic evidence to simplify your analysis.
      </p>

      <div className="diagnosticity-list">
        {sortedEvidence.map((e, i) => {
          const diagnosticity = getEvidenceDiagnosticity(e.id);
          return (
            <div
              key={e.id}
              className={`diagnosticity-card diagnosticity-${diagnosticity}`}
            >
              <div className="diagnosticity-indicator">
                {diagnosticity === 'high' && <Icon name="Star" size={16} className="icon-amber" />}
                {diagnosticity === 'low' && <Icon name="MinusCircle" size={16} className="icon-muted" />}
                {diagnosticity === 'normal' && <Icon name="Circle" size={16} className="icon-blue" />}
              </div>
              <div className="diagnosticity-content">
                <div className="diagnosticity-header">
                  <span className="evidence-label">E{i + 1}</span>
                  <span className={`badge badge-${diagnosticity}`}>
                    {diagnosticity === 'high' ? 'High' : diagnosticity === 'low' ? 'Low' : 'Normal'} Diagnostic Value
                  </span>
                </div>
                <p className="evidence-description">{e.description}</p>
              </div>
              {diagnosticity === 'low' && (
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => onRemoveEvidence(e.id, e.description)}
                  title="Consider removing low-diagnostic evidence"
                >
                  <Icon name="Trash2" size={12} />
                  Remove
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================
// Dialog Components
// ============================================

function AddHypothesisDialog({
  onSubmit,
  onCancel,
}: {
  onSubmit: (title: string, description: string) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (title.trim()) {
      onSubmit(title.trim(), description.trim());
    }
  };

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={e => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>Add Hypothesis</h2>
          <button className="btn btn-icon" onClick={onCancel}>
            <Icon name="X" size={20} />
          </button>
        </div>
        <p className="dialog-description">Add a plausible explanation for your focus question.</p>
        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label>Title *</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g., Insider threat from IT department"
              autoFocus
            />
          </div>
          <div className="form-field">
            <label>Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Describe this hypothesis in detail..."
              rows={3}
            />
          </div>
          <div className="callout callout-info">
            <Icon name="Info" size={14} />
            <span>Remember: Include unlikely explanations too. Consider a 'null hypothesis' - what if nothing unusual happened?</span>
          </div>
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={!title.trim()}>Add Hypothesis</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AddEvidenceDialog({
  onSubmit,
  onCancel,
}: {
  onSubmit: (description: string, source: string, evidenceType: EvidenceType, credibility: number) => void;
  onCancel: () => void;
}) {
  const [description, setDescription] = useState('');
  const [source, setSource] = useState('');
  const [evidenceType, setEvidenceType] = useState<EvidenceType>('fact');
  const [credibility, setCredibility] = useState(1.0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (description.trim()) {
      onSubmit(description.trim(), source.trim(), evidenceType, credibility);
    }
  };

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={e => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>Add Evidence</h2>
          <button className="btn btn-icon" onClick={onCancel}>
            <Icon name="X" size={20} />
          </button>
        </div>
        <p className="dialog-description">Add a piece of evidence or argument to evaluate.</p>
        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label>Description *</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Describe the evidence..."
              rows={3}
              autoFocus
            />
          </div>
          <div className="form-field">
            <label>Source</label>
            <input
              type="text"
              value={source}
              onChange={e => setSource(e.target.value)}
              placeholder="e.g., Security log from Dec 15, Witness interview"
            />
          </div>
          <div className="form-row">
            <div className="form-field">
              <label>Type</label>
              <select value={evidenceType} onChange={e => setEvidenceType(e.target.value as EvidenceType)}>
                {EVIDENCE_TYPE_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label>Credibility</label>
              <select value={credibility} onChange={e => setCredibility(Number(e.target.value))}>
                <option value={1.0}>High (1.0)</option>
                <option value={0.7}>Medium (0.7)</option>
                <option value={0.4}>Low (0.4)</option>
              </select>
            </div>
          </div>
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={!description.trim()}>Add Evidence</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RatingDialog({
  currentRating,
  onSubmit,
  onCancel,
}: {
  currentRating: ConsistencyRating | null;
  onSubmit: (rating: ConsistencyRating, reasoning: string) => void;
  onCancel: () => void;
}) {
  const [rating, setRating] = useState<ConsistencyRating>(currentRating || 'N');
  const [reasoning, setReasoning] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(rating, reasoning.trim());
  };

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={e => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>Rate Consistency</h2>
          <button className="btn btn-icon" onClick={onCancel}>
            <Icon name="X" size={20} />
          </button>
        </div>
        <p className="dialog-description">
          If this hypothesis is true, how consistent is this evidence?
        </p>
        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label>Rating</label>
            <div className="rating-options">
              {RATING_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  className={`rating-option ${rating === opt.value ? 'selected' : ''}`}
                  style={{ borderColor: RATING_COLORS[opt.value] }}
                  onClick={() => setRating(opt.value)}
                >
                  <span className="rating-value" style={{ color: RATING_COLORS[opt.value] }}>{opt.value}</span>
                  <span className="rating-label">{RATING_LABELS[opt.value]}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="form-field">
            <label>Reasoning (optional)</label>
            <textarea
              value={reasoning}
              onChange={e => setReasoning(e.target.value)}
              placeholder="Explain your rating..."
              rows={2}
            />
          </div>
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save Rating</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================
// Helper Functions
// ============================================

function getCredibilityClass(credibility: number): string {
  if (credibility >= 0.8) return 'success';
  if (credibility >= 0.5) return 'warning';
  return 'danger';
}

function getCredibilityLabel(credibility: number): string {
  if (credibility >= 0.8) return 'HIGH';
  if (credibility >= 0.5) return 'MEDIUM';
  return 'LOW';
}
