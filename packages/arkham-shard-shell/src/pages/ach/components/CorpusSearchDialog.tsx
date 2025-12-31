/**
 * CorpusSearchDialog - Modal dialog for corpus search results
 */

import { useState } from 'react';
import { Icon } from '../../../components/common/Icon';
import type { ExtractedEvidence } from '../api';

interface CorpusSearchDialogProps {
  results: Record<string, ExtractedEvidence[]>;
  totalResults: number;
  hypotheses: { id: string; title: string }[];
  onAccept: (evidence: ExtractedEvidence[], autoRate: boolean) => void;
  onClose: () => void;
}

export function CorpusSearchDialog({
  results,
  totalResults,
  hypotheses,
  onAccept,
  onClose,
}: CorpusSearchDialogProps) {
  const [selectedEvidence, setSelectedEvidence] = useState<Set<string>>(new Set());
  const [autoRate, setAutoRate] = useState(true);

  const getHypothesisTitle = (hypId: string): string => {
    const hyp = hypotheses.find((h) => h.id === hypId);
    return hyp ? hyp.title : hypId.substring(0, 8);
  };

  const getRelevanceColor = (relevance: string): string => {
    switch (relevance) {
      case 'supports': return '#4ade80';
      case 'contradicts': return '#f87171';
      case 'ambiguous': return '#fbbf24';
      default: return '#9ca3af';
    }
  };

  const getRelevanceBg = (relevance: string): string => {
    switch (relevance) {
      case 'supports': return 'rgba(74, 222, 128, 0.15)';
      case 'contradicts': return 'rgba(248, 113, 113, 0.15)';
      case 'ambiguous': return 'rgba(251, 191, 36, 0.15)';
      default: return 'rgba(156, 163, 175, 0.15)';
    }
  };

  const toggleSelection = (key: string) => {
    setSelectedEvidence((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const selectAll = () => {
    const allKeys: string[] = [];
    Object.entries(results).forEach(([hypId, evidences]) => {
      evidences.forEach((_, idx) => {
        allKeys.push(hypId + '-' + idx);
      });
    });
    setSelectedEvidence(new Set(allKeys));
  };

  const deselectAll = () => {
    setSelectedEvidence(new Set());
  };

  const handleAccept = () => {
    const toAccept: ExtractedEvidence[] = [];
    Object.entries(results).forEach(([hypId, evidences]) => {
      evidences.forEach((ev, idx) => {
        if (selectedEvidence.has(hypId + '-' + idx)) {
          toAccept.push(ev);
        }
      });
    });
    onAccept(toAccept, autoRate);
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="corpus-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-title-with-icon">
            <Icon name="Search" size={20} className="icon-violet" />
            <h2>Corpus Search Results</h2>
            <span className="results-badge">{totalResults} candidates</span>
          </div>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <div className="dialog-toolbar">
          <div className="selection-info">
            <span>{selectedEvidence.size} selected</span>
          </div>
          <div className="toolbar-actions">
            <button className="btn btn-sm btn-link" onClick={selectAll}>
              Select All
            </button>
            <button className="btn btn-sm btn-link" onClick={deselectAll}>
              Deselect All
            </button>
          </div>
        </div>

        <div className="dialog-body">
          {Object.entries(results).map(([hypId, evidences]) => (
            <div key={hypId} className="hypothesis-group">
              <div className="hypothesis-header">
                <Icon name="Lightbulb" size={16} />
                <span className="hypothesis-title">{getHypothesisTitle(hypId)}</span>
                <span className="evidence-count">{evidences.length} results</span>
              </div>

              <div className="evidence-grid">
                {evidences.map((ev, idx) => {
                  const key = hypId + '-' + idx;
                  const isSelected = selectedEvidence.has(key);
                  return (
                    <div
                      key={key}
                      className={`evidence-card ${isSelected ? 'selected' : ''}`}
                      onClick={() => toggleSelection(key)}
                    >
                      <div className="card-checkbox">
                        <Icon name={isSelected ? 'CheckSquare' : 'Square'} size={18} />
                      </div>
                      <div className="card-content">
                        <div className="card-quote">"{ev.quote}"</div>
                        <div className="card-meta">
                          <span className="meta-source">
                            <Icon name="FileText" size={12} />
                            {ev.source_document_name || 'Document'}
                          </span>
                          {ev.page_number && (
                            <span className="meta-page">p. {ev.page_number}</span>
                          )}
                          <span
                            className="meta-relevance"
                            style={{
                              color: getRelevanceColor(ev.relevance),
                              backgroundColor: getRelevanceBg(ev.relevance),
                            }}
                          >
                            {ev.relevance}
                          </span>
                          <span className="meta-score">
                            {(ev.similarity_score * 100).toFixed(0)}% match
                          </span>
                        </div>
                        {ev.explanation && (
                          <div className="card-explanation">{ev.explanation}</div>
                        )}
                        {ev.possible_duplicate && (
                          <div className="card-warning">
                            <Icon name="AlertTriangle" size={12} />
                            May duplicate existing evidence
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="dialog-footer">
          <label className="auto-rate-toggle">
            <input
              type="checkbox"
              checked={autoRate}
              onChange={(e) => setAutoRate(e.target.checked)}
            />
            <span>Auto-rate evidence after adding</span>
          </label>
          <div className="footer-actions">
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              className="btn btn-success"
              onClick={handleAccept}
              disabled={selectedEvidence.size === 0}
            >
              <Icon name="Plus" size={14} />
              Accept Selected ({selectedEvidence.size})
            </button>
          </div>
        </div>

        <style>{`
          .corpus-dialog {
            background: #111827;
            border-radius: 0.75rem;
            width: 90vw;
            max-width: 1200px;
            height: 85vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
          }
          .dialog-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 1.5rem;
            border-bottom: 1px solid #374151;
            flex-shrink: 0;
          }
          .dialog-title-with-icon {
            display: flex;
            align-items: center;
            gap: 0.75rem;
          }
          .dialog-title-with-icon h2 {
            margin: 0;
            font-size: 1.25rem;
            color: #f9fafb;
          }
          .results-badge {
            background: #6366f1;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-size: 0.75rem;
            font-weight: 600;
          }
          .dialog-toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 1.5rem;
            background: #1f2937;
            border-bottom: 1px solid #374151;
            flex-shrink: 0;
          }
          .selection-info {
            color: #9ca3af;
            font-size: 0.875rem;
          }
          .toolbar-actions {
            display: flex;
            gap: 0.5rem;
          }
          .btn-link {
            background: none;
            border: none;
            color: #6366f1;
            cursor: pointer;
            padding: 0.375rem 0.75rem;
            font-size: 0.8125rem;
          }
          .btn-link:hover {
            color: #818cf8;
            text-decoration: underline;
          }
          .dialog-body {
            flex: 1;
            overflow-y: auto;
            padding: 1rem 1.5rem;
            display: block;
          }
          .dialog-body::-webkit-scrollbar { width: 8px; }
          .dialog-body::-webkit-scrollbar-track { background: #1f2937; }
          .dialog-body::-webkit-scrollbar-thumb { background: #4b5563; border-radius: 4px; }
          .corpus-dialog .hypothesis-group {
            display: block;
            width: 100%;
            margin-bottom: 1.5rem;
          }
          .corpus-dialog .hypothesis-header {
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            gap: 0.5rem !important;
            padding: 0.75rem 1rem !important;
            background: #1f2937 !important;
            border-radius: 0.5rem !important;
            margin-bottom: 1rem !important;
            border-left: 3px solid #6366f1 !important;
            width: 100% !important;
            max-width: none !important;
            min-width: 0 !important;
            box-sizing: border-box !important;
          }
          .corpus-dialog .hypothesis-title {
            font-weight: 600 !important;
            color: #f9fafb !important;
            flex: 1 !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
          }
          .corpus-dialog .evidence-count {
            color: #9ca3af !important;
            font-size: 0.8125rem !important;
            flex-shrink: 0 !important;
          }
          .corpus-dialog .evidence-grid {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            width: 100%;
          }
          .corpus-dialog .evidence-card {
            display: flex;
            gap: 1rem;
            padding: 1rem;
            background: #1f2937;
            border: 2px solid #374151;
            border-radius: 0.5rem;
            cursor: pointer;
            transition: all 0.15s;
            width: 100%;
            box-sizing: border-box;
          }
          .corpus-dialog .evidence-card:hover {
            border-color: #4b5563;
            background: #263344;
          }
          .corpus-dialog .evidence-card.selected {
            border-color: #6366f1;
            background: rgba(99, 102, 241, 0.1);
          }
          .corpus-dialog .card-checkbox {
            flex-shrink: 0;
            color: #6b7280;
          }
          .corpus-dialog .evidence-card.selected .card-checkbox {
            color: #6366f1;
          }
          .corpus-dialog .card-content {
            flex: 1;
            min-width: 0;
          }
          .corpus-dialog .card-quote {
            font-size: 0.9375rem;
            line-height: 1.6;
            color: #f9fafb;
            font-style: italic;
            margin-bottom: 0.75rem;
            padding: 0.75rem;
            background: rgba(0,0,0,0.2);
            border-radius: 0.375rem;
            border-left: 3px solid #6366f1;
            word-wrap: break-word;
            overflow-wrap: break-word;
          }
          .corpus-dialog .card-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            align-items: center;
            margin-bottom: 0.5rem;
          }
          .corpus-dialog .card-meta span {
            display: flex;
            align-items: center;
            gap: 0.25rem;
            font-size: 0.75rem;
          }
          .corpus-dialog .meta-source {
            color: #d1d5db;
            max-width: 300px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .corpus-dialog .meta-page {
            color: #9ca3af;
          }
          .corpus-dialog .meta-relevance {
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.6875rem;
          }
          .corpus-dialog .meta-score {
            color: #6366f1;
            font-weight: 500;
          }
          .corpus-dialog .card-explanation {
            font-size: 0.8125rem;
            color: #9ca3af;
            line-height: 1.5;
          }
          .corpus-dialog .card-warning {
            display: flex;
            align-items: center;
            gap: 0.375rem;
            margin-top: 0.5rem;
            padding: 0.375rem 0.5rem;
            background: rgba(251, 191, 36, 0.1);
            border-radius: 0.25rem;
            font-size: 0.75rem;
            color: #fbbf24;
          }
          .dialog-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.5rem;
            border-top: 1px solid #374151;
            background: #1f2937;
            flex-shrink: 0;
            border-radius: 0 0 0.75rem 0.75rem;
          }
          .auto-rate-toggle {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #d1d5db;
            font-size: 0.875rem;
            cursor: pointer;
          }
          .auto-rate-toggle input {
            accent-color: #6366f1;
          }
          .footer-actions {
            display: flex;
            gap: 0.75rem;
          }
          .icon-violet { color: #8b5cf6; }
        `}</style>
      </div>
    </div>
  );
}
