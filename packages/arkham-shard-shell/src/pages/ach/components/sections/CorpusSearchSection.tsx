/**
 * CorpusSearchSection - Search document corpus for evidence
 */

import { useState, useEffect, useCallback } from 'react';
import { Icon } from '../../../../components/common/Icon';
import { useToast } from '../../../../context/ToastContext';
import * as achApi from '../../api';
import type { ExtractedEvidence } from '../../api';
import type { ACHMatrix } from '../../types';
import { CorpusSearchDialog } from '../CorpusSearchDialog';

interface CorpusSearchSectionProps {
  matrix: ACHMatrix;
  onEvidenceAdded: () => void;
}

export function CorpusSearchSection({
  matrix,
  onEvidenceAdded,
}: CorpusSearchSectionProps) {
  const matrixId = matrix.id;
  const hypotheses = matrix.hypotheses;
  const { toast } = useToast();

  const [statusLoading, setStatusLoading] = useState(true);
  const [corpusAvailable, setCorpusAvailable] = useState(false);
  const [vectorsService, setVectorsService] = useState(false);
  const [llmService, setLlmService] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Record<string, ExtractedEvidence[]>>({});
  const [totalResults, setTotalResults] = useState(0);
  const [showDialog, setShowDialog] = useState(false);
  const [chunkLimit, setChunkLimit] = useState(20);
  const [minSimilarity, setMinSimilarity] = useState(0.5);

  const checkStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const status = await achApi.getCorpusStatus();
      setCorpusAvailable(status.available);
      setVectorsService(status.vectors_service);
      setLlmService(status.llm_service);
    } catch (err) {
      console.error('Failed to check corpus status:', err);
      setCorpusAvailable(false);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  const handleSearchAll = async () => {
    if (hypotheses.length === 0) {
      toast.warning('Add hypotheses before searching corpus');
      return;
    }
    setSearching(true);
    setSearchResults({});
    try {
      const result = await achApi.searchCorpusAll(matrixId, chunkLimit, minSimilarity);
      const flatResults: Record<string, ExtractedEvidence[]> = {};
      for (const [hypId, data] of Object.entries(result.by_hypothesis)) {
        flatResults[hypId] = data.results;
      }
      setSearchResults(flatResults);
      setTotalResults(result.total_results);
      if (result.total_results === 0) {
        toast.info('No evidence found in corpus');
      } else {
        toast.success('Found ' + result.total_results + ' evidence candidates');
        setShowDialog(true);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Corpus search failed');
    } finally {
      setSearching(false);
    }
  };

  const handleAcceptEvidence = async (evidence: ExtractedEvidence[], autoRate: boolean) => {
    if (evidence.length === 0) {
      toast.warning('Select evidence to accept');
      return;
    }
    try {
      const result = await achApi.acceptCorpusEvidence({
        matrix_id: matrixId,
        evidence: evidence,
        auto_rate: autoRate,
      });
      toast.success('Added ' + result.count + ' evidence item(s) to matrix');
      setShowDialog(false);
      setSearchResults({});
      setTotalResults(0);
      onEvidenceAdded();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to accept evidence');
    }
  };

  const handleCloseDialog = () => {
    setShowDialog(false);
  };

  return (
    <>
      <div className="corpus-search-section">
        <div className="section-header">
          <h3>
            <Icon name="Search" size={18} />
            Corpus Search
          </h3>
          <div className="status-indicator">
            {statusLoading ? (
              <Icon name="Loader" size={14} className="spin" />
            ) : (
              <span
                className={'status-dot ' + (corpusAvailable ? 'available' : 'unavailable')}
                title={corpusAvailable ? 'Corpus search available' : 'Corpus search unavailable'}
              />
            )}
          </div>
        </div>

        <p className="section-description">
          Search the document corpus for evidence relevant to each hypothesis.
          Requires vectors and LLM services to be available.
        </p>

        <div className="service-status">
          <div className={'service-item ' + (vectorsService ? 'active' : 'inactive')}>
            <Icon name={vectorsService ? 'Check' : 'X'} size={12} />
            <span>Vectors</span>
          </div>
          <div className={'service-item ' + (llmService ? 'active' : 'inactive')}>
            <Icon name={llmService ? 'Check' : 'X'} size={12} />
            <span>LLM</span>
          </div>
        </div>

        <div className="search-controls">
          <div className="search-params">
            <label>
              <span>Chunks:</span>
              <input
                type="number"
                min={5}
                max={100}
                value={chunkLimit}
                onChange={(e) => setChunkLimit(parseInt(e.target.value) || 20)}
                disabled={searching}
              />
            </label>
            <label>
              <span>Min Similarity:</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.1}
                value={minSimilarity}
                onChange={(e) => setMinSimilarity(parseFloat(e.target.value) || 0.5)}
                disabled={searching}
              />
            </label>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleSearchAll}
            disabled={!corpusAvailable || searching || hypotheses.length === 0}
          >
            {searching ? (
              <>
                <Icon name="Loader" size={14} className="spin" />
                Searching...
              </>
            ) : (
              <>
                <Icon name="Search" size={14} />
                Search All Hypotheses
              </>
            )}
          </button>
        </div>

        {totalResults > 0 && !showDialog && (
          <div className="results-summary">
            <span>{totalResults} candidates found</span>
            <button className="btn btn-sm btn-link" onClick={() => setShowDialog(true)}>
              View Results
            </button>
          </div>
        )}

        <style>{`
          .corpus-search-section {
            background: #1f2937;
            border: 1px solid #374151;
            border-radius: 0.5rem;
            padding: 1.25rem;
            margin-top: 1rem;
          }
          .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
          }
          .section-header h3 {
            margin: 0;
            font-size: 1rem;
            font-weight: 600;
            color: #f9fafb;
            display: flex;
            align-items: center;
            gap: 0.5rem;
          }
          .status-indicator { display: flex; align-items: center; }
          .status-dot { width: 10px; height: 10px; border-radius: 50%; }
          .status-dot.available { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
          .status-dot.unavailable { background: #f87171; box-shadow: 0 0 6px #f87171; }
          .section-description { font-size: 0.8125rem; color: #9ca3af; margin: 0 0 1rem 0; line-height: 1.5; }
          .service-status { display: flex; gap: 1rem; margin-bottom: 1rem; }
          .service-item { display: flex; align-items: center; gap: 0.375rem; font-size: 0.75rem; padding: 0.25rem 0.5rem; border-radius: 0.25rem; background: #111827; }
          .service-item.active { color: #4ade80; }
          .service-item.inactive { color: #f87171; }
          .search-controls { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; }
          .search-params { display: flex; gap: 1rem; }
          .search-params label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.75rem; color: #9ca3af; }
          .search-params input { width: 80px; padding: 0.375rem 0.5rem; background: #111827; border: 1px solid #374151; border-radius: 0.25rem; color: #f9fafb; font-size: 0.875rem; }
          .search-params input:focus { outline: none; border-color: #6366f1; }
          .results-summary {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 1rem;
            padding: 0.75rem;
            background: #111827;
            border-radius: 0.375rem;
            border: 1px solid #374151;
          }
          .results-summary span { color: #d1d5db; font-size: 0.875rem; }
          .btn { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.5rem 1rem; font-size: 0.875rem; font-weight: 500; border-radius: 0.375rem; cursor: pointer; transition: all 0.15s; border: 1px solid transparent; }
          .btn-primary { background: #6366f1; color: white; border-color: #6366f1; }
          .btn-primary:hover:not(:disabled) { background: #4f46e5; }
          .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
          .btn-sm { padding: 0.375rem 0.75rem; font-size: 0.8125rem; }
          .btn-link { background: none; border: none; color: #6366f1; cursor: pointer; }
          .btn-link:hover { color: #818cf8; text-decoration: underline; }
          .spin { animation: spin 1s linear infinite; }
          @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        `}</style>
      </div>

      {showDialog && (
        <CorpusSearchDialog
          results={searchResults}
          totalResults={totalResults}
          hypotheses={hypotheses.map(h => ({ id: h.id, title: h.title }))}
          onAccept={handleAcceptEvidence}
          onClose={handleCloseDialog}
        />
      )}
    </>
  );
}
