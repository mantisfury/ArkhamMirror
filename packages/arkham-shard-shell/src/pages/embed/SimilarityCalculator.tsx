/**
 * SimilarityCalculator - Component for calculating text similarity
 *
 * Features:
 * - Two text areas for input
 * - Calculate similarity button
 * - Animated similarity score gauge
 * - Copy embedding button
 */

import { useState } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useSimilarity, useEmbedText } from './api';

export function SimilarityCalculator() {
  const { toast } = useToast();
  const [text1, setText1] = useState('');
  const [text2, setText2] = useState('');
  const { calculate, data: similarityData, loading: calculating } = useSimilarity();
  const { embed: embedText1, data: embed1Data } = useEmbedText();
  const { embed: embedText2, data: embed2Data } = useEmbedText();

  const handleCalculate = async () => {
    if (!text1.trim() || !text2.trim()) {
      toast.warning('Please enter text in both fields');
      return;
    }

    try {
      await calculate(text1, text2, 'cosine');
      // Also get embeddings for copy functionality
      embedText1(text1);
      embedText2(text2);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Calculation failed');
    }
  };

  const handleCopyEmbedding = async (embedNum: 1 | 2) => {
    const embedding = embedNum === 1 ? embed1Data?.embedding : embed2Data?.embedding;
    if (!embedding) {
      toast.warning('No embedding available to copy');
      return;
    }

    try {
      await navigator.clipboard.writeText(JSON.stringify(embedding));
      toast.success(`Embedding ${embedNum} copied to clipboard`);
    } catch (error) {
      toast.error('Failed to copy to clipboard');
    }
  };

  const handleClear = () => {
    setText1('');
    setText2('');
  };

  const similarityScore = similarityData?.similarity ?? null;
  const similarityPercent = similarityScore !== null ? Math.round(similarityScore * 100) : null;

  // Calculate color based on similarity score
  const getScoreColor = (score: number): string => {
    if (score >= 0.8) return '#22c55e'; // green
    if (score >= 0.6) return '#3b82f6'; // blue
    if (score >= 0.4) return '#f59e0b'; // amber
    return '#ef4444'; // red
  };

  return (
    <div className="similarity-calculator">
      <div className="calculator-header">
        <h2>
          <Icon name="Scale" size={20} />
          Similarity Calculator
        </h2>
        <p className="calculator-description">
          Compare two texts and calculate their semantic similarity
        </p>
      </div>

      <div className="text-inputs">
        <div className="text-input-group">
          <div className="input-header">
            <label className="input-label">
              <Icon name="FileText" size={16} />
              Text 1
            </label>
            {embed1Data && (
              <button
                className="button-icon-sm"
                onClick={() => handleCopyEmbedding(1)}
                title="Copy embedding"
              >
                <Icon name="Copy" size={14} />
              </button>
            )}
          </div>
          <textarea
            className="similarity-textarea"
            placeholder="Enter first text to compare..."
            value={text1}
            onChange={e => setText1(e.target.value)}
            rows={8}
          />
          <div className="input-meta">
            {text1.length} characters
            {embed1Data && (
              <span className="embedding-info">
                <Icon name="Zap" size={12} />
                {embed1Data.dimensions}D embedding
              </span>
            )}
          </div>
        </div>

        <div className="text-input-group">
          <div className="input-header">
            <label className="input-label">
              <Icon name="FileText" size={16} />
              Text 2
            </label>
            {embed2Data && (
              <button
                className="button-icon-sm"
                onClick={() => handleCopyEmbedding(2)}
                title="Copy embedding"
              >
                <Icon name="Copy" size={14} />
              </button>
            )}
          </div>
          <textarea
            className="similarity-textarea"
            placeholder="Enter second text to compare..."
            value={text2}
            onChange={e => setText2(e.target.value)}
            rows={8}
          />
          <div className="input-meta">
            {text2.length} characters
            {embed2Data && (
              <span className="embedding-info">
                <Icon name="Zap" size={12} />
                {embed2Data.dimensions}D embedding
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="calculator-actions">
        <button
          className="button-secondary"
          onClick={handleClear}
          disabled={!text1 && !text2}
        >
          <Icon name="X" size={16} />
          Clear
        </button>
        <button
          className="button-primary"
          onClick={handleCalculate}
          disabled={calculating || !text1.trim() || !text2.trim()}
        >
          {calculating ? (
            <>
              <Icon name="Loader" size={16} className="spinner" />
              Calculating...
            </>
          ) : (
            <>
              <Icon name="Calculator" size={16} />
              Calculate Similarity
            </>
          )}
        </button>
      </div>

      {similarityData && (
        <div className="similarity-result">
          <div className="result-header">
            <h3>
              <Icon name="TrendingUp" size={18} />
              Similarity Score
            </h3>
            <span className="result-method">Method: {similarityData.method}</span>
          </div>

          <div className="score-display">
            <div
              className="score-gauge"
              style={{
                background: `conic-gradient(
                  ${getScoreColor(similarityScore!)} ${similarityPercent}%,
                  #374151 ${similarityPercent}%
                )`,
              }}
            >
              <div className="score-center">
                <div className="score-value">{similarityPercent}%</div>
                <div className="score-label">Similar</div>
              </div>
            </div>

            <div className="score-interpretation">
              {similarityScore! >= 0.8 && (
                <>
                  <Icon name="CheckCircle2" size={20} style={{ color: '#22c55e' }} />
                  <p>
                    <strong>Highly Similar</strong> - The texts are semantically very close
                  </p>
                </>
              )}
              {similarityScore! >= 0.6 && similarityScore! < 0.8 && (
                <>
                  <Icon name="CheckCircle" size={20} style={{ color: '#3b82f6' }} />
                  <p>
                    <strong>Similar</strong> - The texts share significant semantic overlap
                  </p>
                </>
              )}
              {similarityScore! >= 0.4 && similarityScore! < 0.6 && (
                <>
                  <Icon name="AlertCircle" size={20} style={{ color: '#f59e0b' }} />
                  <p>
                    <strong>Somewhat Similar</strong> - The texts have some related concepts
                  </p>
                </>
              )}
              {similarityScore! < 0.4 && (
                <>
                  <Icon name="XCircle" size={20} style={{ color: '#ef4444' }} />
                  <p>
                    <strong>Not Similar</strong> - The texts are semantically different
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <style>{`
        .similarity-calculator {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.75rem;
          padding: 1.5rem;
        }

        .calculator-header {
          margin-bottom: 1.5rem;
        }

        .calculator-header h2 {
          margin: 0 0 0.5rem 0;
          font-size: 1.25rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .calculator-description {
          margin: 0;
          color: #9ca3af;
          font-size: 0.875rem;
        }

        .text-inputs {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1rem;
          margin-bottom: 1.5rem;
        }

        @media (max-width: 768px) {
          .text-inputs {
            grid-template-columns: 1fr;
          }
        }

        .text-input-group {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .input-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .input-label {
          font-size: 0.875rem;
          font-weight: 500;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .button-icon-sm {
          display: inline-flex;
          align-items: center;
          gap: 0.25rem;
          padding: 0.25rem 0.5rem;
          background: #374151;
          color: #9ca3af;
          border: 1px solid #4b5563;
          border-radius: 0.25rem;
          font-size: 0.75rem;
          cursor: pointer;
          transition: all 0.15s;
        }

        .button-icon-sm:hover {
          background: #4b5563;
          color: #f9fafb;
        }

        .similarity-textarea {
          width: 100%;
          padding: 0.75rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          color: #f9fafb;
          font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
          font-size: 0.875rem;
          line-height: 1.5;
          resize: vertical;
          transition: border-color 0.15s;
        }

        .similarity-textarea:focus {
          outline: none;
          border-color: #6366f1;
        }

        .similarity-textarea::placeholder {
          color: #6b7280;
        }

        .input-meta {
          font-size: 0.75rem;
          color: #6b7280;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .embedding-info {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          color: #9ca3af;
        }

        .calculator-actions {
          display: flex;
          justify-content: flex-end;
          gap: 0.75rem;
          margin-bottom: 1.5rem;
        }

        .button-primary,
        .button-secondary {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.625rem 1.25rem;
          border-radius: 0.375rem;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s;
          border: 1px solid transparent;
        }

        .button-primary {
          background: #6366f1;
          color: white;
          border-color: #6366f1;
        }

        .button-primary:hover:not(:disabled) {
          background: #4f46e5;
        }

        .button-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .button-secondary {
          background: #374151;
          color: #f9fafb;
          border-color: #4b5563;
        }

        .button-secondary:hover:not(:disabled) {
          background: #4b5563;
        }

        .button-secondary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .similarity-result {
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1.5rem;
        }

        .result-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
        }

        .result-header h3 {
          margin: 0;
          font-size: 1rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .result-method {
          font-size: 0.75rem;
          color: #9ca3af;
          text-transform: capitalize;
        }

        .score-display {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 1.5rem;
        }

        .score-gauge {
          width: 200px;
          height: 200px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          transition: all 0.5s ease;
        }

        .score-center {
          width: 160px;
          height: 160px;
          background: #1f2937;
          border-radius: 50%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 0.25rem;
        }

        .score-value {
          font-size: 2.5rem;
          font-weight: 700;
          color: #f9fafb;
          line-height: 1;
        }

        .score-label {
          font-size: 0.875rem;
          color: #9ca3af;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .score-interpretation {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 1rem;
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          max-width: 400px;
        }

        .score-interpretation p {
          margin: 0;
          color: #d1d5db;
          font-size: 0.875rem;
          line-height: 1.5;
        }

        .score-interpretation strong {
          color: #f9fafb;
          display: block;
          margin-bottom: 0.25rem;
        }

        .spinner {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}
