/**
 * CredibilityPage - Source credibility assessment and scoring
 *
 * Displays credibility assessments with score visualization,
 * factor breakdown, and history tracking.
 */

import { useState, useCallback, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { AIAnalystButton } from '../../components/AIAnalyst';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { usePaginatedFetch } from '../../hooks';
import { DeceptionPanel, DeceptionRisk, RISK_COLORS } from './components';
import { apiDelete, apiGet, apiPost } from '../../utils/api';
import './CredibilityPage.css';
import './components/DeceptionPanel.css';

// Source item from API
interface SourceItem {
  id: string;
  name: string;
  type?: string;
  description?: string;
}

// Cached source info for display
interface SourceDisplayInfo {
  name: string;
  type: string;
  detail?: string;
}

// Source viewer modal data
interface SourceViewerData {
  id: string;
  type: string;
  name: string;
  content: string;
  metadata?: Record<string, unknown>;
}

// Types
interface CredibilityFactor {
  factor_type: string;
  weight: number;
  score: number;
  notes: string | null;
}

interface Assessment {
  id: string;
  source_type: string;
  source_id: string;
  score: number;
  confidence: number;
  level: string;
  factors: CredibilityFactor[];
  assessed_by: string;
  assessor_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

interface Statistics {
  total_assessments: number;
  by_source_type: Record<string, number>;
  by_level: Record<string, number>;
  by_method: Record<string, number>;
  avg_score: number;
  avg_confidence: number;
  unreliable_count: number;
  low_count: number;
  medium_count: number;
  high_count: number;
  verified_count: number;
  sources_assessed: number;
  avg_assessments_per_source: number;
}

const CREDIBILITY_LEVELS = [
  { id: 'unreliable', label: 'Unreliable', color: '#ef4444', range: '0-20' },
  { id: 'low', label: 'Low', color: '#f97316', range: '21-40' },
  { id: 'medium', label: 'Medium', color: '#eab308', range: '41-60' },
  { id: 'high', label: 'High', color: '#22c55e', range: '61-80' },
  { id: 'verified', label: 'Verified', color: '#10b981', range: '81-100' },
];

type DetailTab = 'factors' | 'deception';

const SOURCE_TYPES = [
  { id: 'document', label: 'Document', api: '/api/documents/items?status=processed&page_size=50', nameKey: 'name', icon: 'FileText' },
  { id: 'entity', label: 'Entity', api: '/api/entities/items?page_size=50', nameKey: 'name', icon: 'User' },
  { id: 'claim', label: 'Claim', api: '/api/claims/?page_size=50', nameKey: 'statement', icon: 'MessageSquare' },
  { id: 'other', label: 'Other (Manual Entry)', api: null, nameKey: null, icon: 'Edit' },
];

export function CredibilityPage() {
  const { toast } = useToast();
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const [selectedAssessment, setSelectedAssessment] = useState<Assessment | null>(null);
  const [showFactors, setShowFactors] = useState(true);
  const [detailTab, setDetailTab] = useState<DetailTab>('factors');
  const [deceptionRisk, setDeceptionRisk] = useState<DeceptionRisk | null>(null);

  // Create assessment modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createSourceType, setCreateSourceType] = useState('document');
  const [createSourceId, setCreateSourceId] = useState('');
  const [_createSourceName, setCreateSourceName] = useState('');
  const [createNotes, setCreateNotes] = useState('');
  const [creating, setCreating] = useState(false);

  // Source browser state
  const [sourceItems, setSourceItems] = useState<SourceItem[]>([]);
  const [loadingSourceItems, setLoadingSourceItems] = useState(false);
  const [sourceSearch, setSourceSearch] = useState('');
  const [selectedSourceItem, setSelectedSourceItem] = useState<SourceItem | null>(null);

  // Source names cache for display (maps source_id to display info)
  const [sourceNamesCache, setSourceNamesCache] = useState<Map<string, SourceDisplayInfo>>(new Map());

  // Source viewer modal state
  const [sourceViewer, setSourceViewer] = useState<SourceViewerData | null>(null);
  const [loadingSourceViewer, setLoadingSourceViewer] = useState(false);

  // Fetch assessments with usePaginatedFetch
  const baseUrl = selectedLevel
    ? `/api/credibility/level/${selectedLevel}`
    : '/api/credibility/';

  const { items: assessments, loading, error, refetch } = usePaginatedFetch<Assessment>(
    baseUrl
  );

  // Fetch statistics
  const { data: stats } = useFetch<Statistics>('/api/credibility/stats');

  // Fetch source names for assessments when they load
  useEffect(() => {
    if (assessments.length === 0) return;

    const fetchSourceNames = async () => {
      const newCache = new Map(sourceNamesCache);
      const idsToFetch: { type: string; id: string }[] = [];

      // Find assessments whose source names we haven't fetched yet
      for (const assessment of assessments) {
        if (!newCache.has(assessment.source_id)) {
          idsToFetch.push({ type: assessment.source_type, id: assessment.source_id });
        }
      }

      if (idsToFetch.length === 0) return;

      // Fetch each source's info
      for (const { type, id } of idsToFetch) {
        try {
          let endpoint: string | null = null;
          let nameKey = 'name';

          if (type === 'document') {
            endpoint = `/api/documents/items/${id}`;
            nameKey = 'title';
          } else if (type === 'entity') {
            endpoint = `/api/entities/${id}`;
            nameKey = 'name';
          } else if (type === 'claim') {
            endpoint = `/api/claims/${id}`;
            nameKey = 'statement';
          }

          if (endpoint) {
            try {
              const data = await apiGet<any>(endpoint);
              const name = data[nameKey] || data.name || data.title || data.filename || id;
              newCache.set(id, {
                name: typeof name === 'string' ? name.substring(0, 80) : String(name),
                type: type.charAt(0).toUpperCase() + type.slice(1),
                detail: data.file_type || data.entity_type || data.source_type || undefined,
              });
            } catch {
              // API returned error, use abbreviated ID
              newCache.set(id, {
                name: id.substring(0, 8) + '...',
                type: type.charAt(0).toUpperCase() + type.slice(1),
              });
            }
          } else {
            // Unknown type, just show ID
            newCache.set(id, {
              name: id.substring(0, 20) + (id.length > 20 ? '...' : ''),
              type: type.charAt(0).toUpperCase() + type.slice(1),
            });
          }
        } catch {
          // On error, use abbreviated ID
          newCache.set(id, {
            name: id.substring(0, 8) + '...',
            type: type.charAt(0).toUpperCase() + type.slice(1),
          });
        }
      }

      setSourceNamesCache(newCache);
    };

    fetchSourceNames();
  }, [assessments]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch source items when source type changes or modal opens
  useEffect(() => {
    if (!showCreateModal) return;

    const sourceType = SOURCE_TYPES.find(t => t.id === createSourceType);
    if (!sourceType?.api) {
      setSourceItems([]);
      return;
    }

    const fetchSourceItems = async () => {
      setLoadingSourceItems(true);
      setSelectedSourceItem(null);
      setCreateSourceId('');
      setCreateSourceName('');

      try {
        const data = await apiGet<any>(sourceType.api);
        // Handle different API response formats
        const items = data.items || data.documents || data.entities || data.claims || data || [];
        const nameKey = sourceType.nameKey || 'name';

        const mapped: SourceItem[] = items.map((item: Record<string, unknown>) => ({
          id: item.id as string,
          name: (item[nameKey] as string) || (item.name as string) || (item.title as string) || String(item.id),
          type: (item.type as string) || (item.entity_type as string) || (item.status as string),
          description: (item.description as string) || (item.content as string)?.substring(0, 100),
        }));

        setSourceItems(mapped);
      } catch (err) {
        console.error('Failed to fetch source items:', err);
        setSourceItems([]);
      } finally {
        setLoadingSourceItems(false);
      }
    };

    fetchSourceItems();
  }, [showCreateModal, createSourceType]);

  const getLevelColor = (level: string): string => {
    const levelConfig = CREDIBILITY_LEVELS.find(l => l.id === level);
    return levelConfig?.color || '#6b7280';
  };

  // Get display info for a source
  const getSourceDisplayInfo = useCallback((sourceId: string, sourceType: string): SourceDisplayInfo => {
    const cached = sourceNamesCache.get(sourceId);
    if (cached) return cached;
    // Return placeholder while loading
    return {
      name: sourceId.substring(0, 8) + '...',
      type: sourceType.charAt(0).toUpperCase() + sourceType.slice(1),
    };
  }, [sourceNamesCache]);

  // Get icon for source type
  const getSourceIcon = (sourceType: string): 'FileText' | 'User' | 'MessageSquare' | 'Edit' => {
    switch (sourceType.toLowerCase()) {
      case 'document': return 'FileText';
      case 'entity': return 'User';
      case 'claim': return 'MessageSquare';
      default: return 'Edit';
    }
  };

  // Open source viewer modal
  const openSourceViewer = useCallback(async (sourceType: string, sourceId: string, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation(); // Prevent card selection when clicking name
    }

    setLoadingSourceViewer(true);
    try {
      let metadataEndpoint: string;
      let contentEndpoint: string | null = null;
      let nameKey: string;

      switch (sourceType.toLowerCase()) {
        case 'document':
          metadataEndpoint = `/api/documents/items/${sourceId}`;
          contentEndpoint = `/api/documents/${sourceId}/content`;
          nameKey = 'title';
          break;
        case 'entity':
          metadataEndpoint = `/api/entities/${sourceId}`;
          nameKey = 'name';
          break;
        case 'claim':
          metadataEndpoint = `/api/claims/${sourceId}`;
          nameKey = 'statement';
          break;
        default:
          toast.error('Unknown source type');
          setLoadingSourceViewer(false);
          return;
      }

      // Fetch metadata
      const data = await apiGet<any>(metadataEndpoint);

      // Get content based on source type
      let content = '';

      if (sourceType.toLowerCase() === 'document') {
        // For documents, fetch content separately
        if (contentEndpoint) {
          try {
            const contentData = await apiGet<any>(contentEndpoint);
            content = contentData.content || '';
          } catch {
            // Content fetch failed, try chunks
          }
        }

        // If no content, try to get from chunks
        if (!content) {
          try {
            const chunksData = await apiGet<any>(`/api/documents/${sourceId}/chunks?page_size=20`);
            const chunks = chunksData.items || chunksData.chunks || [];
            if (Array.isArray(chunks) && chunks.length > 0) {
              content = chunks.map((c: { content?: string; text?: string }) => c.content || c.text || '').join('\n\n---\n\n');
            }
          } catch {
            // Ignore chunk fetch errors
          }
        }
      } else if (sourceType.toLowerCase() === 'entity') {
        content = data.description || data.notes || 'No description available';
      } else if (sourceType.toLowerCase() === 'claim') {
        content = data.statement || 'No statement available';
        if (data.evidence) {
          content += '\n\n--- Evidence ---\n' + data.evidence;
        }
        if (data.source) {
          content += '\n\n--- Source ---\n' + data.source;
        }
      }

      // Build metadata display
      const metadata: Record<string, unknown> = {};
      if (data.file_type) metadata['Type'] = data.file_type;
      if (data.filename) metadata['File'] = data.filename;
      if (data.entity_type) metadata['Entity Type'] = data.entity_type;
      if (data.source_type) metadata['Source Type'] = data.source_type;
      if (data.confidence) metadata['Confidence'] = `${(data.confidence * 100).toFixed(0)}%`;
      if (data.created_at) metadata['Created'] = new Date(data.created_at).toLocaleString();
      if (data.page_count) metadata['Pages'] = data.page_count;
      if (data.chunk_count) metadata['Chunks'] = data.chunk_count;
      if (data.file_size) metadata['Size'] = `${(data.file_size / 1024).toFixed(1)} KB`;
      if (data.source) metadata['Source'] = data.source;
      if (data.aliases?.length) metadata['Aliases'] = data.aliases.join(', ');
      if (data.status) metadata['Status'] = data.status;

      setSourceViewer({
        id: sourceId,
        type: sourceType,
        name: data[nameKey] || data.name || data.title || sourceId,
        content: content || 'No content available',
        metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load source');
    } finally {
      setLoadingSourceViewer(false);
    }
  }, [toast]);

  const getScoreColor = (score: number): string => {
    if (score <= 20) return '#ef4444';
    if (score <= 40) return '#f97316';
    if (score <= 60) return '#eab308';
    if (score <= 80) return '#22c55e';
    return '#10b981';
  };

  const handleAssessmentClick = useCallback((assessment: Assessment) => {
    setSelectedAssessment(assessment);
    setDetailTab('factors');
    setDeceptionRisk(null);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedAssessment(null);
  }, []);

  const handleDeleteAssessment = async (id: string) => {
    if (!confirm('Are you sure you want to delete this assessment?')) {
      return;
    }

    try {
      await apiDelete(`/api/credibility/${id}`);

      toast.success('Assessment deleted');
      refetch();
      if (selectedAssessment?.id === id) {
        setSelectedAssessment(null);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete assessment');
    }
  };

  const handleSelectSourceItem = (item: SourceItem) => {
    setSelectedSourceItem(item);
    setCreateSourceId(item.id);
    setCreateSourceName(item.name);
  };

  // Filter source items by search
  const filteredSourceItems = sourceItems.filter(item =>
    item.name.toLowerCase().includes(sourceSearch.toLowerCase()) ||
    item.id.toLowerCase().includes(sourceSearch.toLowerCase())
  );

  const handleCreateAssessment = async () => {
    const sourceTypeConfig = SOURCE_TYPES.find(t => t.id === createSourceType);
    const sourceId = sourceTypeConfig?.api ? selectedSourceItem?.id : createSourceId.trim();

    if (!sourceId) {
      toast.error('Please select a source');
      return;
    }

    setCreating(true);
    try {
      const newAssessment = await apiPost<Assessment>('/api/credibility/', {
        source_type: createSourceType,
        source_id: sourceId,
        score: 50, // Default neutral score
        confidence: 0.5,
        factors: [],
        assessed_by: 'manual',
        notes: createNotes.trim() || null,
      });
      toast.success('Assessment created');
      setShowCreateModal(false);
      setCreateSourceId('');
      setCreateSourceName('');
      setCreateNotes('');
      setSelectedSourceItem(null);
      setSourceSearch('');
      refetch();
      // Select the new assessment and switch to deception tab
      setSelectedAssessment(newAssessment);
      setDetailTab('deception');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create assessment');
    } finally {
      setCreating(false);
    }
  };

  const renderScoreGauge = (score: number) => {
    const color = getScoreColor(score);
    const percentage = score;

    return (
      <div className="score-gauge">
        <div className="gauge-track">
          <div
            className="gauge-fill"
            style={{
              width: `${percentage}%`,
              backgroundColor: color,
            }}
          />
        </div>
        <div className="gauge-value" style={{ color }}>
          {score}
        </div>
      </div>
    );
  };

  const renderFactorBreakdown = (factors: CredibilityFactor[]) => {
    if (factors.length === 0) {
      return <p className="no-factors">No factors recorded</p>;
    }

    return (
      <div className="factors-list">
        {factors.map((factor, idx) => (
          <div key={idx} className="factor-item">
            <div className="factor-header">
              <span className="factor-type">{factor.factor_type}</span>
              <div className="factor-metrics">
                <span className="factor-weight">Weight: {(factor.weight * 100).toFixed(0)}%</span>
                <span className="factor-score" style={{ color: getScoreColor(factor.score) }}>
                  Score: {factor.score}
                </span>
              </div>
            </div>
            {factor.notes && (
              <p className="factor-notes">{factor.notes}</p>
            )}
            <div className="factor-bar">
              <div
                className="factor-bar-fill"
                style={{
                  width: `${factor.score}%`,
                  backgroundColor: getScoreColor(factor.score),
                }}
              />
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="credibility-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="ShieldCheck" size={28} />
          <div>
            <h1>Credibility</h1>
            <p className="page-description">Source credibility assessment and scoring</p>
          </div>
        </div>
        <div className="page-actions">
          <AIAnalystButton
            shard="credibility"
            targetId={selectedAssessment?.id || 'overview'}
            context={{
              statistics: stats,
              filters: { level: selectedLevel },
              selectedAssessment: selectedAssessment,
            }}
            label="AI Analysis"
            disabled={false}
          />
          <button
            className="btn btn-primary"
            onClick={() => setShowCreateModal(true)}
          >
            <Icon name="Plus" size={16} />
            New Assessment
          </button>
        </div>
      </header>

      <div className="credibility-layout">
        {/* Sidebar - Statistics and Filters */}
        <aside className="credibility-sidebar">
          {/* Statistics */}
          {stats && (
            <div className="stats-panel">
              <h3>Statistics</h3>
              <div className="stat-item">
                <Icon name="FileText" size={16} />
                <span className="stat-label">Total Assessments</span>
                <span className="stat-value">{stats.total_assessments}</span>
              </div>
              <div className="stat-item">
                <Icon name="Database" size={16} />
                <span className="stat-label">Sources Assessed</span>
                <span className="stat-value">{stats.sources_assessed}</span>
              </div>
              <div className="stat-item">
                <Icon name="TrendingUp" size={16} />
                <span className="stat-label">Avg Score</span>
                <span className="stat-value">{stats.avg_score.toFixed(1)}</span>
              </div>
              <div className="stat-item">
                <Icon name="Target" size={16} />
                <span className="stat-label">Avg Certainty</span>
                <span className="stat-value">{(stats.avg_confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          )}

          {/* Level Filter */}
          <div className="filter-panel">
            <h3>Filter by Level</h3>
            <button
              className={`filter-button ${!selectedLevel ? 'active' : ''}`}
              onClick={() => setSelectedLevel(null)}
            >
              <Icon name="List" size={16} />
              <span>All Assessments</span>
              {stats && <span className="filter-count">{stats.total_assessments}</span>}
            </button>
            {CREDIBILITY_LEVELS.map(level => (
              <button
                key={level.id}
                className={`filter-button ${selectedLevel === level.id ? 'active' : ''}`}
                onClick={() => setSelectedLevel(level.id)}
                style={{
                  borderLeftColor: selectedLevel === level.id ? level.color : 'transparent',
                }}
              >
                <div
                  className="level-indicator"
                  style={{ backgroundColor: level.color }}
                />
                <div className="filter-content">
                  <span className="filter-label">{level.label}</span>
                  <span className="filter-range">{level.range}</span>
                </div>
                {stats && (
                  <span className="filter-count">
                    {stats.by_level[level.id] || 0}
                  </span>
                )}
              </button>
            ))}
          </div>
        </aside>

        {/* Main Content */}
        <main className="credibility-content">
          {loading ? (
            <div className="content-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading assessments...</span>
            </div>
          ) : error ? (
            <div className="content-error">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load assessments</span>
              <button className="btn btn-secondary" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : assessments.length === 0 ? (
            <div className="content-empty">
              <Icon name="ShieldAlert" size={48} />
              <span>No credibility assessments found</span>
              <p className="empty-hint">
                Create an assessment to analyze source credibility and detect potential deception
              </p>
              <div className="empty-actions">
                <button
                  className="btn btn-primary"
                  onClick={() => setShowCreateModal(true)}
                >
                  <Icon name="Plus" size={16} />
                  New Assessment
                </button>
                {selectedLevel && (
                  <button
                    className="btn btn-secondary"
                    onClick={() => setSelectedLevel(null)}
                  >
                    Clear Filter
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="assessments-container">
              {/* Assessment List */}
              <div className="assessments-list">
                {assessments.map(assessment => {
                  const sourceInfo = getSourceDisplayInfo(assessment.source_id, assessment.source_type);
                  const isSelected = selectedAssessment?.id === assessment.id;

                  return (
                    <div
                      key={assessment.id}
                      className={`assessment-card ${isSelected ? 'selected' : ''}`}
                      onClick={() => handleAssessmentClick(assessment)}
                    >
                      {/* Selection indicator bar */}
                      {isSelected && <div className="selection-indicator" />}

                      <div className="assessment-header">
                        <div className="assessment-source">
                          <Icon name={getSourceIcon(assessment.source_type)} size={18} />
                          <div className="source-info">
                            <button
                              className="source-name-link"
                              onClick={(e) => openSourceViewer(assessment.source_type, assessment.source_id, e)}
                              title="Click to view source content"
                            >
                              {sourceInfo.name}
                              <Icon name="ExternalLink" size={12} className="link-icon" />
                            </button>
                            <span className="source-type-badge">{sourceInfo.type}</span>
                            {sourceInfo.detail && (
                              <span className="source-detail">{sourceInfo.detail}</span>
                            )}
                          </div>
                        </div>
                        <div
                          className="level-badge"
                          style={{ backgroundColor: getLevelColor(assessment.level) }}
                        >
                          {assessment.level}
                        </div>
                      </div>

                      {renderScoreGauge(assessment.score)}

                      <div className="assessment-meta">
                        <div className="meta-item">
                          <Icon name="Target" size={12} />
                          <span>Certainty: {(assessment.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <div className="meta-item">
                          <Icon name="User" size={12} />
                          <span>{assessment.assessed_by}</span>
                        </div>
                        <div className="meta-item">
                          <Icon name="Clock" size={12} />
                          <span>{new Date(assessment.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>

                      {assessment.notes && (
                        <p className="assessment-notes">{assessment.notes}</p>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Assessment Detail Panel */}
              {selectedAssessment && (() => {
                const detailSourceInfo = getSourceDisplayInfo(selectedAssessment.source_id, selectedAssessment.source_type);
                return (
                <div className="assessment-detail">
                  <div className="detail-header">
                    <h3>Assessment Details</h3>
                    <button
                      className="close-btn"
                      onClick={handleCloseDetail}
                      title="Close"
                    >
                      <Icon name="X" size={16} />
                    </button>
                  </div>

                  {/* Source Banner - prominently shows what's being assessed */}
                  <div className="source-banner">
                    <Icon name={getSourceIcon(selectedAssessment.source_type)} size={24} />
                    <div className="source-banner-info">
                      <button
                        className="source-banner-name-link"
                        onClick={() => openSourceViewer(selectedAssessment.source_type, selectedAssessment.source_id)}
                        title="Click to view source content"
                      >
                        {detailSourceInfo.name}
                        <Icon name="ExternalLink" size={14} className="link-icon" />
                      </button>
                      <div className="source-banner-meta">
                        <span className="source-banner-type">{detailSourceInfo.type}</span>
                        {detailSourceInfo.detail && (
                          <span className="source-banner-detail">{detailSourceInfo.detail}</span>
                        )}
                      </div>
                    </div>
                    <div
                      className="source-banner-level"
                      style={{ backgroundColor: getLevelColor(selectedAssessment.level) }}
                    >
                      {selectedAssessment.level}
                    </div>
                  </div>

                  {/* Detail Tabs */}
                  <div className="detail-tabs">
                    <button
                      className={`detail-tab ${detailTab === 'factors' ? 'active' : ''}`}
                      onClick={() => setDetailTab('factors')}
                    >
                      <Icon name="BarChart3" size={16} />
                      Factors
                    </button>
                    <button
                      className={`detail-tab ${detailTab === 'deception' ? 'active' : ''}`}
                      onClick={() => setDetailTab('deception')}
                    >
                      <Icon name="ShieldAlert" size={16} />
                      Deception
                      {deceptionRisk && deceptionRisk !== 'minimal' && (
                        <span
                          className="deception-risk-dot"
                          style={{ backgroundColor: RISK_COLORS[deceptionRisk] }}
                          title={`Deception risk: ${deceptionRisk}`}
                        />
                      )}
                    </button>
                  </div>

                  <div className="detail-content">
                    {detailTab === 'factors' ? (
                      <>
                        {/* Score Section */}
                        <div className="detail-section">
                          <h4>Credibility Score</h4>
                          {renderScoreGauge(selectedAssessment.score)}
                          <div className="score-info">
                            <div className="info-row">
                              <span>Level:</span>
                              <span
                                className="level-value"
                                style={{ color: getLevelColor(selectedAssessment.level) }}
                              >
                                {selectedAssessment.level.toUpperCase()}
                              </span>
                            </div>
                            <div className="info-row">
                              <span>Certainty:</span>
                              <span>{(selectedAssessment.confidence * 100).toFixed(1)}%</span>
                            </div>
                          </div>
                        </div>

                        {/* Source Section */}
                        <div className="detail-section">
                          <h4>Source Information</h4>
                          <div className="info-row">
                            <span>Name:</span>
                            <span>{detailSourceInfo.name}</span>
                          </div>
                          <div className="info-row">
                            <span>Type:</span>
                            <span>{detailSourceInfo.type}</span>
                          </div>
                          {detailSourceInfo.detail && (
                            <div className="info-row">
                              <span>Format:</span>
                              <span>{detailSourceInfo.detail}</span>
                            </div>
                          )}
                          <div className="info-row">
                            <span>ID:</span>
                            <span className="monospace source-id-small">{selectedAssessment.source_id}</span>
                          </div>
                        </div>

                        {/* Factors Section */}
                        <div className="detail-section">
                          <div className="section-header">
                            <h4>Credibility Factors</h4>
                            <button
                              className="toggle-btn"
                              onClick={() => setShowFactors(!showFactors)}
                            >
                              <Icon name={showFactors ? 'ChevronUp' : 'ChevronDown'} size={16} />
                            </button>
                          </div>
                          {showFactors && renderFactorBreakdown(selectedAssessment.factors)}
                        </div>

                        {/* Assessment Meta */}
                        <div className="detail-section">
                          <h4>Assessment Meta</h4>
                          <div className="info-row">
                            <span>Method:</span>
                            <span>{selectedAssessment.assessed_by}</span>
                          </div>
                          {selectedAssessment.assessor_id && (
                            <div className="info-row">
                              <span>Assessor:</span>
                              <span className="monospace">{selectedAssessment.assessor_id}</span>
                            </div>
                          )}
                          <div className="info-row">
                            <span>Created:</span>
                            <span>{new Date(selectedAssessment.created_at).toLocaleString()}</span>
                          </div>
                          <div className="info-row">
                            <span>Updated:</span>
                            <span>{new Date(selectedAssessment.updated_at).toLocaleString()}</span>
                          </div>
                        </div>

                        {/* Notes Section */}
                        {selectedAssessment.notes && (
                          <div className="detail-section">
                            <h4>Notes</h4>
                            <p className="detail-notes">{selectedAssessment.notes}</p>
                          </div>
                        )}

                        {/* Actions */}
                        <div className="detail-actions">
                          <button
                            className="btn btn-danger"
                            onClick={() => handleDeleteAssessment(selectedAssessment.id)}
                          >
                            <Icon name="Trash2" size={16} />
                            Delete Assessment
                          </button>
                        </div>
                      </>
                    ) : (
                      <DeceptionPanel
                        sourceType={selectedAssessment.source_type}
                        sourceId={selectedAssessment.source_id}
                        credibilityAssessmentId={selectedAssessment.id}
                        onRiskChange={setDeceptionRisk}
                      />
                    )}
                  </div>
                </div>
                );
              })()}
            </div>
          )}
        </main>
      </div>

      {/* Create Assessment Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <Icon name="Plus" size={20} />
                New Credibility Assessment
              </h3>
              <button className="close-btn" onClick={() => setShowCreateModal(false)}>
                <Icon name="X" size={16} />
              </button>
            </div>
            <div className="modal-body">
              {/* Source Type Selector */}
              <div className="source-type-tabs">
                {SOURCE_TYPES.map(type => (
                  <button
                    key={type.id}
                    className={`source-type-tab ${createSourceType === type.id ? 'active' : ''}`}
                    onClick={() => setCreateSourceType(type.id)}
                  >
                    <Icon name={type.icon as 'FileText' | 'User' | 'MessageSquare' | 'Edit'} size={16} />
                    <span>{type.label}</span>
                  </button>
                ))}
              </div>

              {/* Source Browser or Manual Entry */}
              {SOURCE_TYPES.find(t => t.id === createSourceType)?.api ? (
                <div className="source-browser">
                  {/* Search */}
                  <div className="source-search">
                    <Icon name="Search" size={16} />
                    <input
                      type="text"
                      placeholder={`Search ${createSourceType}s...`}
                      value={sourceSearch}
                      onChange={e => setSourceSearch(e.target.value)}
                    />
                  </div>

                  {/* Selected Source Display */}
                  {selectedSourceItem && (
                    <div className="selected-source">
                      <Icon name="CheckCircle" size={16} />
                      <div className="selected-source-info">
                        <span className="selected-source-name">{selectedSourceItem.name}</span>
                        <span className="selected-source-id">{selectedSourceItem.id}</span>
                      </div>
                      <button
                        className="clear-selection"
                        onClick={() => {
                          setSelectedSourceItem(null);
                          setCreateSourceId('');
                          setCreateSourceName('');
                        }}
                      >
                        <Icon name="X" size={14} />
                      </button>
                    </div>
                  )}

                  {/* Source List */}
                  <div className="source-list">
                    {loadingSourceItems ? (
                      <div className="source-list-loading">
                        <Icon name="Loader2" size={20} className="spin" />
                        <span>Loading {createSourceType}s...</span>
                      </div>
                    ) : filteredSourceItems.length === 0 ? (
                      <div className="source-list-empty">
                        <Icon name="Inbox" size={24} />
                        <span>No {createSourceType}s found</span>
                      </div>
                    ) : (
                      filteredSourceItems.map(item => (
                        <button
                          key={item.id}
                          className={`source-item ${selectedSourceItem?.id === item.id ? 'selected' : ''}`}
                          onClick={() => handleSelectSourceItem(item)}
                        >
                          <div className="source-item-info">
                            <span className="source-item-name">{item.name}</span>
                            {item.type && <span className="source-item-type">{item.type}</span>}
                          </div>
                          {item.description && (
                            <span className="source-item-desc">{item.description}</span>
                          )}
                        </button>
                      ))
                    )}
                  </div>
                </div>
              ) : (
                <div className="form-group">
                  <label htmlFor="sourceId">Source Identifier</label>
                  <input
                    type="text"
                    id="sourceId"
                    placeholder="Enter source identifier..."
                    value={createSourceId}
                    onChange={e => setCreateSourceId(e.target.value)}
                  />
                  <span className="form-hint">
                    Enter a unique identifier for this source
                  </span>
                </div>
              )}

              {/* Notes */}
              <div className="form-group">
                <label htmlFor="notes">Notes (optional)</label>
                <textarea
                  id="notes"
                  placeholder="Additional context or notes..."
                  value={createNotes}
                  onChange={e => setCreateNotes(e.target.value)}
                  rows={2}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowCreateModal(false)}
                disabled={creating}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCreateAssessment}
                disabled={creating || (SOURCE_TYPES.find(t => t.id === createSourceType)?.api ? !selectedSourceItem : !createSourceId.trim())}
              >
                {creating ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Icon name="Check" size={16} />
                    Create & Analyze
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Source Viewer Modal */}
      {(sourceViewer || loadingSourceViewer) && (
        <div className="modal-overlay source-viewer-overlay" onClick={() => setSourceViewer(null)}>
          <div className="source-viewer-modal" onClick={e => e.stopPropagation()}>
            <div className="source-viewer-header">
              {loadingSourceViewer ? (
                <>
                  <Icon name="Loader2" size={20} className="spin" />
                  <span>Loading source...</span>
                </>
              ) : sourceViewer && (
                <>
                  <Icon name={getSourceIcon(sourceViewer.type)} size={20} />
                  <div className="source-viewer-title">
                    <h3>{sourceViewer.name}</h3>
                    <span className="source-viewer-type">{sourceViewer.type}</span>
                  </div>
                </>
              )}
              <button className="close-btn" onClick={() => setSourceViewer(null)}>
                <Icon name="X" size={18} />
              </button>
            </div>

            {sourceViewer && (
              <>
                {/* Metadata */}
                {sourceViewer.metadata && Object.keys(sourceViewer.metadata).length > 0 && (
                  <div className="source-viewer-metadata">
                    {Object.entries(sourceViewer.metadata).map(([key, value]) => (
                      <div key={key} className="metadata-item">
                        <span className="metadata-key">{key}:</span>
                        <span className="metadata-value">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Content */}
                <div className="source-viewer-content">
                  <pre>{sourceViewer.content}</pre>
                </div>

                {/* Footer */}
                <div className="source-viewer-footer">
                  <span className="source-id-display">
                    <Icon name="Hash" size={12} />
                    {sourceViewer.id}
                  </span>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      navigator.clipboard.writeText(sourceViewer.content);
                      toast.success('Content copied to clipboard');
                    }}
                  >
                    <Icon name="Copy" size={14} />
                    Copy Content
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
