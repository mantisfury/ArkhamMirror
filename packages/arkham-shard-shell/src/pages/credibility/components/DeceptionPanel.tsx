/**
 * DeceptionPanel - Main deception detection panel
 *
 * Shows MOM/POP/MOSES/EVE checklists with overall risk assessment.
 * Integrates with credibility scoring.
 *
 * Scoring:
 * - Each indicator rated: None (0), Weak (25), Moderate (50), Strong (75), Conclusive (100)
 * - Higher score = MORE deception indicators = HIGHER RISK
 * - Checklist score = weighted average of indicator strengths
 * - Overall score = weighted average of checklist scores (MOM: 35%, EVE: 25%, MOSES: 25%, POP: 15%)
 */

import { useState, useEffect, useCallback } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useToast } from '../../../context/ToastContext';
import { DeceptionChecklist } from './DeceptionChecklist';
import { apiDelete, apiGet, apiPost, apiPut } from '../../../utils/api';
import type {
  DeceptionAssessment,
  DeceptionChecklistType,
  DeceptionIndicator,
  StandardIndicator,
  DeceptionRisk,
} from './DeceptionTypes';
import { CHECKLIST_INFO, RISK_COLORS } from './DeceptionTypes';

interface DeceptionPanelProps {
  sourceType: string;
  sourceId: string;
  credibilityAssessmentId?: string;
  onRiskChange?: (risk: DeceptionRisk) => void;
}

interface SourceInfo {
  name: string;
  type: string;
  detail?: string;
}

const CHECKLIST_TYPES: DeceptionChecklistType[] = ['mom', 'pop', 'moses', 'eve'];

export function DeceptionPanel({
  sourceType,
  sourceId,
  credibilityAssessmentId,
  onRiskChange,
}: DeceptionPanelProps) {
  const { toast } = useToast();
  const [assessment, setAssessment] = useState<DeceptionAssessment | null>(null);
  const [sourceInfo, setSourceInfo] = useState<SourceInfo | null>(null);
  const [standardIndicators, setStandardIndicators] = useState<Record<DeceptionChecklistType, StandardIndicator[]>>({
    mom: [],
    pop: [],
    moses: [],
    eve: [],
  });
  const [activeChecklist, setActiveChecklist] = useState<DeceptionChecklistType>('mom');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [analyzingChecklist, setAnalyzingChecklist] = useState<DeceptionChecklistType | null>(null);
  const [showScoringHelp, setShowScoringHelp] = useState(false);

  // Fetch source info for display
  const fetchSourceInfo = useCallback(async () => {
    try {
      if (sourceType === 'document') {
        const doc = await apiGet<any>(`/api/documents/${sourceId}`);
        setSourceInfo({
          name: doc.name || 'Unknown Document',
          type: 'Document',
          detail: doc.mime_type || undefined,
        });
      } else if (sourceType === 'entity') {
        const entity = await apiGet<any>(`/api/entities/${sourceId}`);
        setSourceInfo({
          name: entity.name || 'Unknown Entity',
          type: entity.entity_type || 'Entity',
          detail: entity.description?.substring(0, 100) || undefined,
        });
      } else if (sourceType === 'claim') {
        const claim = await apiGet<any>(`/api/claims/${sourceId}`);
        setSourceInfo({
          name: claim.statement?.substring(0, 80) || 'Unknown Claim',
          type: 'Claim',
          detail: claim.source_text?.substring(0, 100) || undefined,
        });
      } else {
        setSourceInfo({
          name: sourceId,
          type: sourceType.charAt(0).toUpperCase() + sourceType.slice(1),
        });
      }
    } catch {
      setSourceInfo({
        name: sourceId,
        type: sourceType.charAt(0).toUpperCase() + sourceType.slice(1),
      });
    }
  }, [sourceType, sourceId]);

  // Fetch existing assessment and standard indicators
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      // Reset assessment state when source changes to avoid showing stale data
      setAssessment(null);
      try {
        // Fetch source info for display
        await fetchSourceInfo();

        // Fetch standard indicators for all checklist types
        const indicatorPromises = CHECKLIST_TYPES.map(type =>
          apiGet<unknown>(`/api/credibility/deception/indicators/${type}`)
        );
        const indicatorResults = await Promise.all(indicatorPromises);
        const indicators: Record<DeceptionChecklistType, StandardIndicator[]> = {
          mom: Array.isArray(indicatorResults[0]) ? indicatorResults[0] : [],
          pop: Array.isArray(indicatorResults[1]) ? indicatorResults[1] : [],
          moses: Array.isArray(indicatorResults[2]) ? indicatorResults[2] : [],
          eve: Array.isArray(indicatorResults[3]) ? indicatorResults[3] : [],
        };
        setStandardIndicators(indicators);

        // Try to fetch existing assessment for this source
        try {
          const data = await apiGet<unknown>(`/api/credibility/deception/source/${sourceType}/${sourceId}`);
          if (Array.isArray(data) && data.length > 0) {
            setAssessment(data[0] as DeceptionAssessment);
            onRiskChange?.((data[0] as DeceptionAssessment).risk_level);
          }
        } catch {
          // No existing assessment (or not accessible) is fine
        }
      } catch (err) {
        console.error('Failed to fetch deception data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [sourceType, sourceId, onRiskChange, fetchSourceInfo]);

  // Create new assessment
  const handleCreateAssessment = async () => {
    setSaving(true);
    try {
      const data = await apiPost<DeceptionAssessment>('/api/credibility/deception', {
        source_type: sourceType,
        source_id: sourceId,
        source_name: sourceInfo?.name,
        linked_assessment_id: credibilityAssessmentId,
        assessed_by: 'manual',
        affects_credibility: true,
        credibility_weight: 0.7, // Higher weight for meaningful impact
      });
      setAssessment(data);
      toast.success('Deception assessment created');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create assessment');
    } finally {
      setSaving(false);
    }
  };

  // Update indicator
  const handleUpdateIndicator = useCallback(async (
    checklistType: DeceptionChecklistType,
    indicator: DeceptionIndicator
  ) => {
    if (!assessment) return;

    const checklistKey = `${checklistType}_checklist` as keyof DeceptionAssessment;
    const currentChecklist = assessment[checklistKey] as DeceptionAssessment['mom_checklist'];
    const indicators = currentChecklist?.indicators || standardIndicators[checklistType].map(std => ({
      id: std.id,
      checklist: checklistType,
      question: std.question,
      answer: null,
      strength: 'none' as const,
      confidence: 0,
      evidence_ids: [],
      notes: null,
    }));

    const updatedIndicators = indicators.map(ind =>
      ind.id === indicator.id ? indicator : ind
    );

    setSaving(true);
    try {
      const data = await apiPut<DeceptionAssessment>(
        `/api/credibility/deception/${assessment.id}/checklist/${checklistType}`,
        { indicators: updatedIndicators }
      );
      setAssessment(data);

      if (onRiskChange && data.risk_level !== assessment.risk_level) {
        onRiskChange(data.risk_level);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update indicator');
    } finally {
      setSaving(false);
    }
  }, [assessment, standardIndicators, onRiskChange, toast]);

  // Fetch comprehensive source context for LLM analysis
  const fetchSourceContext = async (): Promise<string> => {
    const contextParts: string[] = [];
    contextParts.push(`=== SOURCE INFORMATION ===`);
    contextParts.push(`Source Type: ${sourceType}`);
    contextParts.push(`Source ID: ${sourceId}`);
    if (sourceInfo?.name) contextParts.push(`Source Name: ${sourceInfo.name}`);

    try {
      if (sourceType === 'document') {
        // Fetch document metadata
        const doc = await apiGet<any>(`/api/documents/items/${sourceId}`);

        contextParts.push(`\n=== DOCUMENT METADATA ===`);
        if (doc.title) contextParts.push(`Title: ${doc.title}`);
        if (doc.filename) contextParts.push(`Filename: ${doc.filename}`);
        if (doc.file_type) contextParts.push(`File Type: ${doc.file_type}`);
        if (doc.created_at) contextParts.push(`Ingested: ${new Date(doc.created_at).toLocaleString()}`);
        if (doc.page_count) contextParts.push(`Pages: ${doc.page_count}`);
        if (doc.tags?.length) contextParts.push(`Tags: ${doc.tags.join(', ')}`);

        // Extract custom metadata (author, publisher, date, source URL, etc.)
        if (doc.custom_metadata && Object.keys(doc.custom_metadata).length > 0) {
          contextParts.push(`\n=== PROVENANCE & ATTRIBUTION ===`);
          const meta = doc.custom_metadata;
          if (meta.author) contextParts.push(`Author: ${meta.author}`);
          if (meta.publisher) contextParts.push(`Publisher: ${meta.publisher}`);
          if (meta.publication_date) contextParts.push(`Publication Date: ${meta.publication_date}`);
          if (meta.source_url) contextParts.push(`Source URL: ${meta.source_url}`);
          if (meta.organization) contextParts.push(`Organization: ${meta.organization}`);
          if (meta.classification) contextParts.push(`Classification: ${meta.classification}`);
          if (meta.reliability_rating) contextParts.push(`Previous Reliability Rating: ${meta.reliability_rating}`);
          // Include any other custom fields
          for (const [key, value] of Object.entries(meta)) {
            if (!['author', 'publisher', 'publication_date', 'source_url', 'organization', 'classification', 'reliability_rating'].includes(key)) {
              contextParts.push(`${key}: ${value}`);
            }
          }
        }

        // Fetch entities extracted from this document
        try {
          const entitiesData = await apiGet<any>(`/api/documents/${sourceId}/entities`);
          const entities = entitiesData.items || [];
          if (entities.length > 0) {
            contextParts.push(`\n=== ENTITIES MENTIONED IN DOCUMENT ===`);
            const byType: Record<string, string[]> = {};
            for (const e of entities.slice(0, 30)) {
              const type = e.entity_type || 'OTHER';
              if (!byType[type]) byType[type] = [];
              byType[type].push(e.text);
            }
            for (const [type, names] of Object.entries(byType)) {
              contextParts.push(`${type}: ${names.slice(0, 10).join(', ')}${names.length > 10 ? ` (+${names.length - 10} more)` : ''}`);
            }
          }
        } catch { /* ignore entity fetch errors */ }

        // Fetch claims made in this document
        try {
          const claimsData = await apiGet<any>(`/api/claims/by-document/${sourceId}?page_size=10`);
          const claims = claimsData.items || [];
          if (claims.length > 0) {
            contextParts.push(`\n=== CLAIMS MADE IN THIS DOCUMENT ===`);
            for (const claim of claims.slice(0, 8)) {
              const status = claim.verification_status ? ` [${claim.verification_status}]` : '';
              contextParts.push(`- "${claim.statement}"${status}`);
            }
            if (claims.length > 8) {
              contextParts.push(`(+${claims.length - 8} more claims)`);
            }
          }
        } catch { /* ignore claims fetch errors */ }

        // Fetch contradictions involving this document
        try {
          const contradictionsData = await apiGet<any>(`/api/contradictions/by-document/${sourceId}`);
          const contradictions = contradictionsData.contradictions || contradictionsData.items || [];
          if (contradictions.length > 0) {
            contextParts.push(`\n=== KNOWN CONTRADICTIONS ===`);
            contextParts.push(`WARNING: This document contains ${contradictions.length} known contradiction(s) with other sources.`);
            for (const c of contradictions.slice(0, 5)) {
              const severity = c.severity ? ` [${c.severity}]` : '';
              contextParts.push(`- ${c.description || c.claim_1 || 'Contradiction'}${severity}`);
            }
          }
        } catch { /* ignore contradictions fetch errors */ }

        // Fetch document content preview
        try {
          const chunks = await apiGet<any>(`/api/documents/${sourceId}/chunks?page_size=10`);
          const items = chunks.items || [];
          if (items.length > 0) {
            const textPreview = items.slice(0, 5).map((c: { content?: string; text?: string }) => c.content || c.text || '').join('\n\n');
            if (textPreview) {
              contextParts.push(`\n=== DOCUMENT CONTENT PREVIEW ===`);
              contextParts.push(textPreview.substring(0, 3000));
            }
          }
        } catch { /* ignore content fetch errors */ }

      } else if (sourceType === 'entity') {
        const entity = await apiGet<any>(`/api/entities/${sourceId}`);
        contextParts.push(`\n=== ENTITY DETAILS ===`);
        if (entity.name) contextParts.push(`Name: ${entity.name}`);
        if (entity.entity_type) contextParts.push(`Type: ${entity.entity_type}`);
        if (entity.description) contextParts.push(`Description: ${entity.description}`);
        if (entity.aliases?.length) contextParts.push(`Also known as: ${entity.aliases.join(', ')}`);
        if (entity.attributes) {
          for (const [key, value] of Object.entries(entity.attributes)) {
            contextParts.push(`${key}: ${value}`);
          }
        }

        // Fetch related documents
        if (entity.document_ids?.length) {
          contextParts.push(`\n=== APPEARS IN ${entity.document_ids.length} DOCUMENT(S) ===`);
        }
      } else if (sourceType === 'claim') {
        const claim = await apiGet<any>(`/api/claims/${sourceId}`);
        contextParts.push(`\n=== CLAIM DETAILS ===`);
        if (claim.statement) contextParts.push(`Statement: "${claim.statement}"`);
        if (claim.source_text) contextParts.push(`Source Context: ${claim.source_text}`);
        if (claim.source_document_id) contextParts.push(`Source Document ID: ${claim.source_document_id}`);
        if (claim.claim_type) contextParts.push(`Claim Type: ${claim.claim_type}`);
        if (claim.verification_status) contextParts.push(`Verification Status: ${claim.verification_status}`);
        if (claim.confidence) contextParts.push(`Extraction Confidence: ${(claim.confidence * 100).toFixed(0)}%`);

        // Check for contradictions with this claim
        try {
          const data = await apiGet<any>(`/api/contradictions/by-claim/${sourceId}`);
          const contradictions = data.contradictions || data.items || [];
          if (contradictions.length > 0) {
            contextParts.push(`\nWARNING: This claim has ${contradictions.length} known contradiction(s).`);
          }
        } catch { /* ignore */ }
      }
    } catch (err) {
      console.error('Failed to fetch source context:', err);
    }

    contextParts.push(`\n=== ANALYSIS GUIDANCE ===`);
    contextParts.push(`Consider the source's potential motives, access to deception channels, and capability to deceive.`);
    contextParts.push(`Look for internal inconsistencies, unusual patterns, or information that contradicts known facts.`);
    contextParts.push(`Evaluate whether the source could have been manipulated or compromised.`);

    return contextParts.join('\n');
  };

  // Analyze checklist with LLM
  const handleAnalyzeWithLLM = async (checklistType: DeceptionChecklistType) => {
    if (!assessment) return;

    setAnalyzingChecklist(checklistType);
    try {
      const sourceContext = await fetchSourceContext();

      const llmResult = await apiPost<any>(
        `/api/credibility/deception/${assessment.id}/checklist/${checklistType}/llm`,
        { context: sourceContext }
      );

      const updatedAssessment = await apiGet<DeceptionAssessment>(`/api/credibility/deception/${assessment.id}`);
      setAssessment(updatedAssessment);
      toast.success(
        `${CHECKLIST_INFO[checklistType].name} analysis complete (${(llmResult.processing_time_ms / 1000).toFixed(1)}s)`
      );

      if (onRiskChange && updatedAssessment.risk_level !== assessment.risk_level) {
        onRiskChange(updatedAssessment.risk_level);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to analyze with AI');
    } finally {
      setAnalyzingChecklist(null);
    }
  };

  // Recalculate overall score
  const handleRecalculate = async () => {
    if (!assessment) return;

    setSaving(true);
    try {
      const data = await apiPost<DeceptionAssessment>(`/api/credibility/deception/${assessment.id}/recalculate`);
      setAssessment(data);
      toast.success('Scores recalculated');

      if (onRiskChange && data.risk_level !== assessment.risk_level) {
        onRiskChange(data.risk_level);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to recalculate');
    } finally {
      setSaving(false);
    }
  };

  // Delete assessment
  const handleDelete = async () => {
    if (!assessment) return;
    if (!confirm('Delete this deception assessment?')) return;

    setSaving(true);
    try {
      await apiDelete(`/api/credibility/deception/${assessment.id}`);

      setAssessment(null);
      toast.success('Assessment deleted');
      if (onRiskChange) {
        onRiskChange('minimal');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setSaving(false);
    }
  };

  // Helper: get checklist stats
  const getChecklistStats = (type: DeceptionChecklistType) => {
    const checklist = getChecklist(type);
    const totalIndicators = standardIndicators[type].length;

    if (!checklist || !checklist.indicators) {
      return { assessed: 0, total: totalIndicators, score: 0 };
    }

    const assessed = checklist.indicators.filter(i => i.strength !== 'none').length;
    return { assessed, total: totalIndicators, score: checklist.overall_score };
  };

  if (loading) {
    return (
      <div className="deception-panel loading">
        <Icon name="Loader2" size={24} className="spin" />
        <span>Loading deception assessment...</span>
      </div>
    );
  }

  if (!assessment) {
    return (
      <div className="deception-panel empty">
        <div className="empty-state">
          <Icon name="ShieldAlert" size={48} />
          <h3>No Deception Assessment</h3>
          {sourceInfo && (
            <div className="source-info-preview">
              <span className="source-type-badge">{sourceInfo.type}</span>
              <span className="source-name">{sourceInfo.name}</span>
            </div>
          )}
          <p>
            Use the MOM/POP/MOSES/EVE framework to evaluate potential deception
            by this source.
          </p>
          <button
            className="btn btn-primary"
            onClick={handleCreateAssessment}
            disabled={saving}
          >
            {saving ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                Creating...
              </>
            ) : (
              <>
                <Icon name="Plus" size={16} />
                Create Assessment
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  const getChecklist = (type: DeceptionChecklistType) => {
    const key = `${type}_checklist` as keyof DeceptionAssessment;
    return assessment[key] as DeceptionAssessment['mom_checklist'];
  };

  return (
    <div className="deception-panel">
      {/* Source Being Assessed */}
      {sourceInfo && (
        <div className="source-header">
          <div className="source-header-info">
            <Icon name={sourceType === 'document' ? 'FileText' : sourceType === 'entity' ? 'User' : sourceType === 'claim' ? 'MessageSquare' : 'Database'} size={16} />
            <span className="source-type-label">{sourceInfo.type}</span>
            <span className="source-name-label">{sourceInfo.name}</span>
          </div>
          {sourceInfo.detail && (
            <div className="source-detail">{sourceInfo.detail}</div>
          )}
        </div>
      )}

      {/* Overall Risk Summary */}
      <div className="deception-summary">
        <div className="risk-overview">
          <div className="risk-score-display">
            <div
              className="risk-badge"
              style={{ backgroundColor: RISK_COLORS[assessment.risk_level] }}
            >
              <Icon name="AlertTriangle" size={18} />
              <span className="risk-level">{assessment.risk_level.toUpperCase()}</span>
            </div>
            <div className="overall-score">
              <span className="score-value">{assessment.overall_score}</span>
              <span className="score-label">Risk Score</span>
            </div>
          </div>
          <div className="risk-actions">
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setShowScoringHelp(!showScoringHelp)}
              title="Scoring explanation"
            >
              <Icon name="HelpCircle" size={14} />
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleRecalculate}
              disabled={saving}
              title="Recalculate scores"
            >
              <Icon name="RefreshCw" size={14} />
            </button>
            <button
              className="btn btn-danger btn-sm"
              onClick={handleDelete}
              disabled={saving}
              title="Delete assessment"
            >
              <Icon name="Trash2" size={14} />
            </button>
          </div>
        </div>

        {/* Scoring Help */}
        {showScoringHelp && (
          <div className="scoring-help">
            <h4>Scoring Criteria</h4>
            <div className="scoring-legend">
              <div className="legend-item">
                <span className="legend-color" style={{background: '#6b7280'}}></span>
                <span className="legend-label">None (0)</span>
                <span className="legend-desc">No deception indicator present</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{background: '#22c55e'}}></span>
                <span className="legend-label">Weak (25)</span>
                <span className="legend-desc">Minor/circumstantial indicator</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{background: '#eab308'}}></span>
                <span className="legend-label">Moderate (50)</span>
                <span className="legend-desc">Notable deception indicator</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{background: '#f97316'}}></span>
                <span className="legend-label">Strong (75)</span>
                <span className="legend-desc">Clear deception indicator</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{background: '#ef4444'}}></span>
                <span className="legend-label">Conclusive (100)</span>
                <span className="legend-desc">Definitive evidence of deception</span>
              </div>
            </div>
            <p className="scoring-note">
              Higher scores = more deception indicators = higher risk.
              Weights: MOM 35%, EVE 25%, MOSES 25%, POP 15%
            </p>
          </div>
        )}

        {assessment.conclusion && (
          <div className="risk-conclusion">
            <Icon name="FileText" size={14} />
            <p>{assessment.conclusion}</p>
          </div>
        )}
      </div>

      {/* Checklist Tabs - Compact Grid Layout */}
      <div className="checklist-tabs-grid">
        {CHECKLIST_TYPES.map(type => {
          const info = CHECKLIST_INFO[type];
          const stats = getChecklistStats(type);
          const isActive = activeChecklist === type;

          return (
            <button
              key={type}
              className={`checklist-tab-compact ${isActive ? 'active' : ''}`}
              onClick={() => setActiveChecklist(type)}
              style={{
                borderColor: isActive ? info.color : 'transparent',
              }}
            >
              <div className="tab-header">
                <Icon name={info.icon} size={14} style={{ color: info.color }} />
                <span className="tab-name">{info.name}</span>
              </div>
              <div className="tab-stats">
                <span className="tab-progress">{stats.assessed}/{stats.total}</span>
                {stats.score > 0 && (
                  <span className="tab-score" style={{ color: info.color }}>{stats.score}</span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Active Checklist Info */}
      <div className="checklist-info">
        <span className="checklist-fullname">{CHECKLIST_INFO[activeChecklist].fullName}</span>
        <span className="checklist-desc">{CHECKLIST_INFO[activeChecklist].description}</span>
      </div>

      {/* Active Checklist */}
      <div className="checklist-content">
        <DeceptionChecklist
          checklist={getChecklist(activeChecklist)}
          checklistType={activeChecklist}
          standardIndicators={standardIndicators[activeChecklist]}
          onUpdateIndicator={(indicator) => handleUpdateIndicator(activeChecklist, indicator)}
          onAnalyzeWithLLM={() => handleAnalyzeWithLLM(activeChecklist)}
          isAnalyzing={analyzingChecklist === activeChecklist}
        />
      </div>

      {/* Credibility Impact */}
      {assessment.affects_credibility && (
        <div className="credibility-impact">
          <Icon name="Link" size={14} />
          <span>
            This assessment affects credibility scoring
            (weight: {(assessment.credibility_weight * 100).toFixed(0)}%)
          </span>
        </div>
      )}

      {/* Saving Indicator */}
      {saving && (
        <div className="saving-indicator">
          <Icon name="Loader2" size={14} className="spin" />
          <span>Saving...</span>
        </div>
      )}
    </div>
  );
}
