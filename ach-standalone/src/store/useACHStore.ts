import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type {
  Analysis,
  Hypothesis,
  Evidence,
  MatrixRating,
  Milestone,
  Snapshot,
  Rating,
  EvidenceType,
  Reliability,
  HypothesisScore,
  DiagnosticityResult,
  SensitivityResult,
  LLMConfig,
  LLMProvider,
} from '../types';
import { LLM_PROVIDERS } from '../types';

// Generate unique IDs
const generateId = () => crypto.randomUUID();

// Generate hypothesis labels (H1, H2, etc.)
const generateHypothesisLabel = (hypotheses: Hypothesis[]) => {
  const maxNum = hypotheses.reduce((max, h) => {
    const match = h.label.match(/^H(\d+)$/);
    return match ? Math.max(max, parseInt(match[1])) : max;
  }, 0);
  return `H${maxNum + 1}`;
};

// Generate evidence labels (E1, E2, etc.)
const generateEvidenceLabel = (evidence: Evidence[]) => {
  const maxNum = evidence.reduce((max, e) => {
    const match = e.label.match(/^E(\d+)$/);
    return match ? Math.max(max, parseInt(match[1])) : max;
  }, 0);
  return `E${maxNum + 1}`;
};

// Hypothesis colors palette
const HYPOTHESIS_COLORS = [
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#f97316', // orange
  '#14b8a6', // teal
  '#84cc16', // lime
  '#f59e0b', // amber
  '#06b6d4', // cyan
];

interface ACHState {
  // Analyses list
  analyses: Analysis[];
  currentAnalysisId: string | null;

  // UI state
  currentStep: number;
  isLoading: boolean;
  showStepGuidance: boolean;
  sortEvidenceBy: 'order' | 'diagnosticity';
  evidenceFilter: 'all' | 'unrated' | 'high_diagnostic';

  // LLM config
  llmConfig: LLMConfig;

  // Computed getters
  getCurrentAnalysis: () => Analysis | null;

  // Analysis CRUD
  createAnalysis: (title: string, focusQuestion: string, description?: string) => string;
  loadAnalysis: (id: string) => void;
  updateAnalysis: (updates: Partial<Analysis>) => void;
  deleteAnalysis: (id: string) => void;
  closeAnalysis: () => void;

  // Hypothesis CRUD
  addHypothesis: (description: string) => void;
  updateHypothesis: (id: string, updates: Partial<Hypothesis>) => void;
  deleteHypothesis: (id: string) => void;

  // Evidence CRUD
  addEvidence: (description: string, evidenceType: EvidenceType, reliability: Reliability, source?: string) => void;
  updateEvidence: (id: string, updates: Partial<Evidence>) => void;
  deleteEvidence: (id: string) => void;

  // Matrix ratings
  setRating: (evidenceId: string, hypothesisId: string, rating: Rating) => void;
  getRating: (evidenceId: string, hypothesisId: string) => Rating;

  // Milestones
  addMilestone: (hypothesisId: string, description: string, expectedBy?: string) => void;
  updateMilestone: (id: string, updates: Partial<Milestone>) => void;
  deleteMilestone: (id: string) => void;

  // Snapshots
  createSnapshot: (label: string, description?: string) => void;

  // Step navigation
  goToStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  markStepComplete: (step: number) => void;

  // UI actions
  setShowStepGuidance: (show: boolean) => void;
  setSortEvidenceBy: (sort: 'order' | 'diagnosticity') => void;
  setEvidenceFilter: (filter: 'all' | 'unrated' | 'high_diagnostic') => void;

  // LLM config
  setLLMConfig: (config: Partial<LLMConfig>) => void;
  setLLMProvider: (provider: LLMProvider) => void;
  testLLMConnection: () => Promise<boolean>;

  // Calculations
  calculateScores: () => HypothesisScore[];
  calculateDiagnosticity: () => DiagnosticityResult[];
  runSensitivityAnalysis: () => SensitivityResult[];
  getMatrixCompletion: () => { total: number; rated: number; percentage: number };

  // Export
  exportToJSON: () => string;
  exportToMarkdown: () => string;
  exportToPDF: () => void;
  importFromJSON: (json: string) => boolean;
}

export const useACHStore = create<ACHState>()(
  persist(
    (set, get) => ({
      // Initial state
      analyses: [],
      currentAnalysisId: null,
      currentStep: 1,
      isLoading: false,
      showStepGuidance: true,
      sortEvidenceBy: 'order',
      evidenceFilter: 'all',
      llmConfig: {
        enabled: false,
        provider: 'lmstudio' as LLMProvider,
        endpoint: LLM_PROVIDERS.lmstudio.defaultEndpoint,
        model: LLM_PROVIDERS.lmstudio.defaultModel,
        connectionStatus: 'untested' as const,
      },

      // Get current analysis
      getCurrentAnalysis: () => {
        const { analyses, currentAnalysisId } = get();
        return analyses.find(a => a.id === currentAnalysisId) || null;
      },

      // Create new analysis
      createAnalysis: (title, focusQuestion, description) => {
        const id = generateId();
        const now = new Date().toISOString();
        const analysis: Analysis = {
          id,
          title,
          focusQuestion,
          description,
          status: 'draft',
          currentStep: 1,
          stepsCompleted: [],
          sensitivityNotes: '',
          hypotheses: [],
          evidence: [],
          ratings: [],
          milestones: [],
          snapshots: [],
          createdAt: now,
          updatedAt: now,
        };
        set(state => ({
          analyses: [...state.analyses, analysis],
          currentAnalysisId: id,
          currentStep: 1,
        }));
        return id;
      },

      // Load analysis
      loadAnalysis: (id) => {
        const analysis = get().analyses.find(a => a.id === id);
        if (analysis) {
          set({
            currentAnalysisId: id,
            currentStep: analysis.currentStep,
          });
        }
      },

      // Update analysis
      updateAnalysis: (updates) => {
        set(state => ({
          analyses: state.analyses.map(a =>
            a.id === state.currentAnalysisId
              ? { ...a, ...updates, updatedAt: new Date().toISOString() }
              : a
          ),
        }));
      },

      // Delete analysis
      deleteAnalysis: (id) => {
        set(state => ({
          analyses: state.analyses.filter(a => a.id !== id),
          currentAnalysisId: state.currentAnalysisId === id ? null : state.currentAnalysisId,
        }));
      },

      // Close analysis
      closeAnalysis: () => {
        set({ currentAnalysisId: null, currentStep: 1 });
      },

      // Add hypothesis
      addHypothesis: (description) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        const hypothesis: Hypothesis = {
          id: generateId(),
          label: generateHypothesisLabel(analysis.hypotheses),
          description,
          color: HYPOTHESIS_COLORS[analysis.hypotheses.length % HYPOTHESIS_COLORS.length],
          displayOrder: analysis.hypotheses.length,
          createdAt: new Date().toISOString(),
        };

        get().updateAnalysis({
          hypotheses: [...analysis.hypotheses, hypothesis],
        });
      },

      // Update hypothesis
      updateHypothesis: (id, updates) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        get().updateAnalysis({
          hypotheses: analysis.hypotheses.map(h =>
            h.id === id ? { ...h, ...updates } : h
          ),
        });
      },

      // Delete hypothesis
      deleteHypothesis: (id) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        get().updateAnalysis({
          hypotheses: analysis.hypotheses.filter(h => h.id !== id),
          ratings: analysis.ratings.filter(r => r.hypothesisId !== id),
          milestones: analysis.milestones.filter(m => m.hypothesisId !== id),
        });
      },

      // Add evidence
      addEvidence: (description, evidenceType, reliability, source) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        const evidence: Evidence = {
          id: generateId(),
          label: generateEvidenceLabel(analysis.evidence),
          description,
          evidenceType,
          reliability,
          source,
          displayOrder: analysis.evidence.length,
          createdAt: new Date().toISOString(),
        };

        get().updateAnalysis({
          evidence: [...analysis.evidence, evidence],
        });
      },

      // Update evidence
      updateEvidence: (id, updates) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        get().updateAnalysis({
          evidence: analysis.evidence.map(e =>
            e.id === id ? { ...e, ...updates } : e
          ),
        });
      },

      // Delete evidence
      deleteEvidence: (id) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        get().updateAnalysis({
          evidence: analysis.evidence.filter(e => e.id !== id),
          ratings: analysis.ratings.filter(r => r.evidenceId !== id),
        });
      },

      // Set rating
      setRating: (evidenceId, hypothesisId, rating) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        const existingIndex = analysis.ratings.findIndex(
          r => r.evidenceId === evidenceId && r.hypothesisId === hypothesisId
        );

        let newRatings: MatrixRating[];
        if (existingIndex >= 0) {
          newRatings = [...analysis.ratings];
          newRatings[existingIndex] = { ...newRatings[existingIndex], rating };
        } else {
          newRatings = [...analysis.ratings, { evidenceId, hypothesisId, rating }];
        }

        get().updateAnalysis({ ratings: newRatings });
      },

      // Get rating
      getRating: (evidenceId, hypothesisId) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return '';

        const rating = analysis.ratings.find(
          r => r.evidenceId === evidenceId && r.hypothesisId === hypothesisId
        );
        return rating?.rating || '';
      },

      // Add milestone
      addMilestone: (hypothesisId, description, expectedBy) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        const milestone: Milestone = {
          id: generateId(),
          hypothesisId,
          description,
          expectedBy,
          observed: 0,
          createdAt: new Date().toISOString(),
        };

        get().updateAnalysis({
          milestones: [...analysis.milestones, milestone],
        });
      },

      // Update milestone
      updateMilestone: (id, updates) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        get().updateAnalysis({
          milestones: analysis.milestones.map(m =>
            m.id === id ? { ...m, ...updates } : m
          ),
        });
      },

      // Delete milestone
      deleteMilestone: (id) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        get().updateAnalysis({
          milestones: analysis.milestones.filter(m => m.id !== id),
        });
      },

      // Create snapshot
      createSnapshot: (label, description) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        const snapshot: Snapshot = {
          id: generateId(),
          label,
          description,
          createdAt: new Date().toISOString(),
          data: {
            hypotheses: [...analysis.hypotheses],
            evidence: [...analysis.evidence],
            ratings: [...analysis.ratings],
            milestones: [...analysis.milestones],
            sensitivityNotes: analysis.sensitivityNotes,
          },
        };

        get().updateAnalysis({
          snapshots: [...analysis.snapshots, snapshot],
        });
      },

      // Step navigation
      goToStep: (step) => {
        if (step >= 1 && step <= 8) {
          set({ currentStep: step });
          const analysis = get().getCurrentAnalysis();
          if (analysis) {
            get().updateAnalysis({ currentStep: step });
          }
        }
      },

      nextStep: () => {
        const { currentStep } = get();
        if (currentStep < 8) {
          get().goToStep(currentStep + 1);
        }
      },

      prevStep: () => {
        const { currentStep } = get();
        if (currentStep > 1) {
          get().goToStep(currentStep - 1);
        }
      },

      markStepComplete: (step) => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        if (!analysis.stepsCompleted.includes(step)) {
          get().updateAnalysis({
            stepsCompleted: [...analysis.stepsCompleted, step],
          });
        }
      },

      // UI actions
      setShowStepGuidance: (show) => set({ showStepGuidance: show }),
      setSortEvidenceBy: (sort) => set({ sortEvidenceBy: sort }),
      setEvidenceFilter: (filter) => set({ evidenceFilter: filter }),

      // LLM config
      setLLMConfig: (config) => {
        set(state => ({
          llmConfig: { ...state.llmConfig, ...config },
        }));
      },

      setLLMProvider: (provider) => {
        const providerConfig = LLM_PROVIDERS[provider];
        set(state => ({
          llmConfig: {
            ...state.llmConfig,
            provider,
            endpoint: providerConfig.defaultEndpoint,
            model: providerConfig.defaultModel,
            connectionStatus: 'untested',
            lastError: undefined,
            // Keep API key if switching between providers that need it
            apiKey: providerConfig.requiresApiKey ? state.llmConfig.apiKey : undefined,
          },
        }));
      },

      testLLMConnection: async () => {
        const { llmConfig } = get();

        try {
          set(state => ({
            llmConfig: { ...state.llmConfig, connectionStatus: 'untested', lastError: undefined },
          }));

          // For Anthropic, use their specific header format
          const isAnthropic = llmConfig.provider === 'anthropic';

          const headers: Record<string, string> = {
            'Content-Type': 'application/json',
          };

          if (llmConfig.apiKey) {
            if (isAnthropic) {
              headers['x-api-key'] = llmConfig.apiKey;
              headers['anthropic-version'] = '2023-06-01';
            } else {
              headers['Authorization'] = `Bearer ${llmConfig.apiKey}`;
            }
          }

          // Just test models endpoint for non-Anthropic, or do a minimal completion test
          const modelsUrl = `${llmConfig.endpoint}/models`;

          const response = await fetch(modelsUrl, {
            method: 'GET',
            headers,
          });

          if (response.ok) {
            set(state => ({
              llmConfig: { ...state.llmConfig, connectionStatus: 'connected' },
            }));
            return true;
          } else {
            const errorText = await response.text();
            set(state => ({
              llmConfig: {
                ...state.llmConfig,
                connectionStatus: 'error',
                lastError: `HTTP ${response.status}: ${errorText.slice(0, 100)}`,
              },
            }));
            return false;
          }
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Connection failed';
          const isCorsError = errorMessage.includes('Failed to fetch') ||
                              errorMessage.includes('NetworkError') ||
                              errorMessage.includes('CORS');

          set(state => ({
            llmConfig: {
              ...state.llmConfig,
              connectionStatus: 'error',
              lastError: isCorsError
                ? 'CORS error - Enable CORS in LM Studio: Settings > Server > Enable CORS'
                : errorMessage,
            },
          }));
          return false;
        }
      },

      // Calculate hypothesis scores
      calculateScores: () => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return [];

        const RATING_VALUES: Record<Rating, number> = {
          'CC': 0,
          'C': 0,
          'N': 0,
          'I': 1,
          'II': 2,
          '': 0,
        };

        const scores: HypothesisScore[] = analysis.hypotheses.map(h => {
          const hypothesisRatings = analysis.ratings.filter(r => r.hypothesisId === h.id);
          const inconsistencyScore = hypothesisRatings.reduce(
            (sum, r) => sum + RATING_VALUES[r.rating],
            0
          );
          const consistencyScore = hypothesisRatings.reduce((sum, r) => {
            if (r.rating === 'CC') return sum + 2;
            if (r.rating === 'C') return sum + 1;
            return sum;
          }, 0);

          return {
            hypothesisId: h.id,
            label: h.label,
            color: h.color,
            inconsistencyScore,
            consistencyScore,
            rank: 0,
          };
        });

        // Sort by inconsistency (lower is better) and assign ranks
        scores.sort((a, b) => a.inconsistencyScore - b.inconsistencyScore);
        scores.forEach((s, i) => {
          s.rank = i + 1;
        });

        return scores;
      },

      // Calculate diagnosticity
      calculateDiagnosticity: () => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return [];

        const RATING_NUMERIC: Record<Rating, number> = {
          'CC': 2,
          'C': 1,
          'N': 0,
          'I': -1,
          'II': -2,
          '': 0,
        };

        return analysis.evidence.map(e => {
          const evidenceRatings = analysis.ratings.filter(r => r.evidenceId === e.id);
          const values = evidenceRatings.map(r => RATING_NUMERIC[r.rating]);

          if (values.length === 0) {
            return {
              evidenceId: e.id,
              label: e.label,
              diagnosticityScore: 0,
              isHighDiagnostic: false,
              isLowDiagnostic: true,
              ratingVariance: 0,
            };
          }

          const mean = values.reduce((a, b) => a + b, 0) / values.length;
          const variance = values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length;
          const diagnosticityScore = Math.sqrt(variance);

          return {
            evidenceId: e.id,
            label: e.label,
            diagnosticityScore,
            isHighDiagnostic: diagnosticityScore >= 1.0,
            isLowDiagnostic: diagnosticityScore < 0.5,
            ratingVariance: variance,
          };
        });
      },

      // Run sensitivity analysis
      runSensitivityAnalysis: () => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return [];

        const baseScores = get().calculateScores();
        if (baseScores.length === 0) return [];

        const originalWinner = baseScores[0]?.label || '';

        return analysis.evidence.map(e => {
          // Calculate scores without this evidence
          const filteredRatings = analysis.ratings.filter(r => r.evidenceId !== e.id);

          const RATING_VALUES: Record<Rating, number> = {
            'CC': 0, 'C': 0, 'N': 0, 'I': 1, 'II': 2, '': 0,
          };

          const modifiedScores = analysis.hypotheses.map(h => {
            const hypothesisRatings = filteredRatings.filter(r => r.hypothesisId === h.id);
            const inconsistencyScore = hypothesisRatings.reduce(
              (sum, r) => sum + RATING_VALUES[r.rating],
              0
            );
            return { label: h.label, inconsistencyScore };
          });

          modifiedScores.sort((a, b) => a.inconsistencyScore - b.inconsistencyScore);
          const winnerIfRemoved = modifiedScores[0]?.label || '';

          const originalScore = baseScores.find(s => s.label === originalWinner)?.inconsistencyScore || 0;
          const newScore = modifiedScores.find(s => s.label === originalWinner)?.inconsistencyScore || 0;

          return {
            evidenceId: e.id,
            evidenceLabel: e.label,
            isCritical: winnerIfRemoved !== originalWinner,
            originalWinner,
            winnerIfRemoved,
            scoreDelta: newScore - originalScore,
          };
        });
      },

      // Get matrix completion
      getMatrixCompletion: () => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return { total: 0, rated: 0, percentage: 0 };

        const total = analysis.hypotheses.length * analysis.evidence.length;
        const rated = analysis.ratings.filter(r => r.rating !== '').length;
        const percentage = total > 0 ? Math.round((rated / total) * 100) : 0;

        return { total, rated, percentage };
      },

      // Export to JSON
      exportToJSON: () => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return '';
        return JSON.stringify(analysis, null, 2);
      },

      // Export to Markdown
      exportToMarkdown: () => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return '';

        const scores = get().calculateScores();
        const diagnosticity = get().calculateDiagnosticity();
        const completion = get().getMatrixCompletion();

        let md = `# ${analysis.title}\n\n`;
        md += `**Focus Question:** ${analysis.focusQuestion}\n\n`;
        if (analysis.description) {
          md += `${analysis.description}\n\n`;
        }
        md += `---\n\n`;

        // Hypotheses
        md += `## Hypotheses\n\n`;
        analysis.hypotheses.forEach(h => {
          const score = scores.find(s => s.hypothesisId === h.id);
          md += `### ${h.label}: ${h.description}\n`;
          if (score) {
            md += `- **Rank:** #${score.rank}\n`;
            md += `- **Inconsistency Score:** ${score.inconsistencyScore}\n`;
          }
          if (h.futureIndicators) {
            md += `- **Future Indicators:** ${h.futureIndicators}\n`;
          }
          md += `\n`;
        });

        // Evidence
        md += `## Evidence\n\n`;
        analysis.evidence.forEach(e => {
          const diag = diagnosticity.find(d => d.evidenceId === e.id);
          md += `### ${e.label}: ${e.description}\n`;
          md += `- **Type:** ${e.evidenceType}\n`;
          md += `- **Reliability:** ${e.reliability}\n`;
          if (e.source) {
            md += `- **Source:** ${e.source}\n`;
          }
          if (diag) {
            md += `- **Diagnosticity:** ${diag.diagnosticityScore.toFixed(2)} ${diag.isHighDiagnostic ? '(HIGH)' : diag.isLowDiagnostic ? '(LOW)' : ''}\n`;
          }
          md += `\n`;
        });

        // Matrix
        md += `## Matrix\n\n`;
        md += `| Evidence |`;
        analysis.hypotheses.forEach(h => {
          md += ` ${h.label} |`;
        });
        md += `\n|---|`;
        analysis.hypotheses.forEach(() => {
          md += `---|`;
        });
        md += `\n`;

        analysis.evidence.forEach(e => {
          md += `| ${e.label} |`;
          analysis.hypotheses.forEach(h => {
            const rating = analysis.ratings.find(
              r => r.evidenceId === e.id && r.hypothesisId === h.id
            );
            md += ` ${rating?.rating || '-'} |`;
          });
          md += `\n`;
        });
        md += `\n`;

        // Scores
        md += `## Scores\n\n`;
        md += `| Rank | Hypothesis | Inconsistency Score |\n`;
        md += `|------|------------|--------------------|\n`;
        scores.forEach(s => {
          md += `| ${s.rank} | ${s.label} | ${s.inconsistencyScore} |\n`;
        });
        md += `\n`;

        // Milestones
        if (analysis.milestones.length > 0) {
          md += `## Milestones\n\n`;
          analysis.milestones.forEach(m => {
            const h = analysis.hypotheses.find(h => h.id === m.hypothesisId);
            const status = m.observed === 1 ? '[OBSERVED]' : m.observed === -1 ? '[CONTRADICTED]' : '[PENDING]';
            md += `- ${status} ${m.description} (${h?.label || 'Unknown'})\n`;
            if (m.expectedBy) {
              md += `  - Expected by: ${m.expectedBy}\n`;
            }
            if (m.observationNotes) {
              md += `  - Notes: ${m.observationNotes}\n`;
            }
          });
          md += `\n`;
        }

        // Sensitivity notes
        if (analysis.sensitivityNotes) {
          md += `## Sensitivity Notes\n\n`;
          md += `${analysis.sensitivityNotes}\n\n`;
        }

        // Footer
        md += `---\n\n`;
        md += `*Matrix Completion: ${completion.percentage}% (${completion.rated}/${completion.total})*\n`;
        md += `*Generated: ${new Date().toISOString()}*\n`;

        return md;
      },

      // Export to PDF
      exportToPDF: () => {
        const analysis = get().getCurrentAnalysis();
        if (!analysis) return;

        const scores = get().calculateScores();
        const diagnosticity = get().calculateDiagnosticity();
        const completion = get().getMatrixCompletion();

        const doc = new jsPDF();
        let y = 20;

        // Title
        doc.setFontSize(18);
        doc.setFont('helvetica', 'bold');
        doc.text(analysis.title, 14, y);
        y += 10;

        // Focus Question
        doc.setFontSize(11);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100);
        doc.text('Focus Question:', 14, y);
        y += 6;
        doc.setTextColor(0);
        const focusLines = doc.splitTextToSize(analysis.focusQuestion, 180);
        doc.text(focusLines, 14, y);
        y += focusLines.length * 5 + 5;

        // Description if present
        if (analysis.description) {
          doc.setTextColor(100);
          doc.text('Description:', 14, y);
          y += 6;
          doc.setTextColor(0);
          const descLines = doc.splitTextToSize(analysis.description, 180);
          doc.text(descLines, 14, y);
          y += descLines.length * 5 + 5;
        }

        // Scores Table (Rankings)
        y += 5;
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Hypothesis Rankings', 14, y);
        y += 8;

        const scoresData = scores.map(s => [
          `#${s.rank}`,
          s.label,
          analysis.hypotheses.find(h => h.id === s.hypothesisId)?.description.slice(0, 50) + '...' || '',
          s.inconsistencyScore.toString(),
        ]);

        autoTable(doc, {
          startY: y,
          head: [['Rank', 'Label', 'Hypothesis', 'Score']],
          body: scoresData,
          theme: 'striped',
          headStyles: { fillColor: [59, 130, 246] },
          columnStyles: {
            0: { cellWidth: 15 },
            1: { cellWidth: 15 },
            2: { cellWidth: 120 },
            3: { cellWidth: 20 },
          },
        });

        y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10;

        // Matrix Table
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Evidence Matrix', 14, y);
        y += 8;

        const matrixHead = ['Evidence', ...analysis.hypotheses.map(h => h.label)];
        const matrixBody = analysis.evidence.map(e => {
          const row = [e.label];
          analysis.hypotheses.forEach(h => {
            const rating = analysis.ratings.find(
              r => r.evidenceId === e.id && r.hypothesisId === h.id
            );
            row.push(rating?.rating || '-');
          });
          return row;
        });

        autoTable(doc, {
          startY: y,
          head: [matrixHead],
          body: matrixBody,
          theme: 'grid',
          headStyles: { fillColor: [59, 130, 246] },
          styles: { halign: 'center', fontSize: 9 },
          columnStyles: { 0: { halign: 'left' } },
        });

        y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10;

        // Evidence details (new page if needed)
        if (y > 240) {
          doc.addPage();
          y = 20;
        }

        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Evidence Details', 14, y);
        y += 8;

        const evidenceData = analysis.evidence.map(e => {
          const diag = diagnosticity.find(d => d.evidenceId === e.id);
          return [
            e.label,
            e.description.slice(0, 60) + (e.description.length > 60 ? '...' : ''),
            e.evidenceType,
            e.reliability,
            diag ? `${diag.diagnosticityScore.toFixed(1)}${diag.isHighDiagnostic ? ' (H)' : ''}` : '-',
          ];
        });

        autoTable(doc, {
          startY: y,
          head: [['Label', 'Description', 'Type', 'Reliability', 'Diag.']],
          body: evidenceData,
          theme: 'striped',
          headStyles: { fillColor: [59, 130, 246] },
          styles: { fontSize: 8 },
        });

        y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10;

        // Milestones (if any)
        if (analysis.milestones.length > 0) {
          if (y > 240) {
            doc.addPage();
            y = 20;
          }

          doc.setFontSize(14);
          doc.setFont('helvetica', 'bold');
          doc.text('Future Milestones', 14, y);
          y += 8;

          const milestonesData = analysis.milestones.map(m => {
            const h = analysis.hypotheses.find(h => h.id === m.hypothesisId);
            const status = m.observed === 1 ? 'Observed' : m.observed === -1 ? 'Contradicted' : 'Pending';
            return [
              status,
              h?.label || '?',
              m.description.slice(0, 70) + (m.description.length > 70 ? '...' : ''),
              m.expectedBy || '-',
            ];
          });

          autoTable(doc, {
            startY: y,
            head: [['Status', 'Hyp.', 'Milestone', 'Expected By']],
            body: milestonesData,
            theme: 'striped',
            headStyles: { fillColor: [59, 130, 246] },
            styles: { fontSize: 8 },
          });

          y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10;
        }

        // Sensitivity Notes
        if (analysis.sensitivityNotes) {
          if (y > 240) {
            doc.addPage();
            y = 20;
          }

          doc.setFontSize(14);
          doc.setFont('helvetica', 'bold');
          doc.text('Sensitivity Notes', 14, y);
          y += 8;

          doc.setFontSize(10);
          doc.setFont('helvetica', 'normal');
          const noteLines = doc.splitTextToSize(analysis.sensitivityNotes, 180);
          doc.text(noteLines, 14, y);
          y += noteLines.length * 5 + 10;
        }

        // Footer
        if (y > 260) {
          doc.addPage();
          y = 20;
        }

        doc.setFontSize(9);
        doc.setTextColor(100);
        doc.text(`Matrix Completion: ${completion.percentage}% (${completion.rated}/${completion.total})`, 14, y);
        y += 5;
        doc.text(`Generated: ${new Date().toLocaleString()}`, 14, y);
        y += 5;
        doc.text('Analysis of Competing Hypotheses (ACH) - Standalone Tool', 14, y);

        // Save the PDF
        const filename = `ach-${analysis.title.toLowerCase().replace(/\s+/g, '-')}.pdf`;
        doc.save(filename);
      },

      // Import from JSON
      importFromJSON: (json) => {
        try {
          const data = JSON.parse(json) as Analysis;
          if (!data.id || !data.title || !data.focusQuestion) {
            return false;
          }
          // Generate new ID to avoid conflicts
          data.id = generateId();
          data.updatedAt = new Date().toISOString();

          set(state => ({
            analyses: [...state.analyses, data],
            currentAnalysisId: data.id,
            currentStep: data.currentStep,
          }));
          return true;
        } catch {
          return false;
        }
      },
    }),
    {
      name: 'ach-storage',
      version: 1,
    }
  )
);
