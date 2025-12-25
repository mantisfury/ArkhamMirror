/**
 * OCRResultView - OCR result viewer component
 *
 * Displays extracted text with metadata and actions.
 */

import { useState } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import type { OCRResponse } from './types';
import { ENGINE_LABELS } from './types';

interface OCRResultViewProps {
  result: OCRResponse;
  fileName: string;
}

export function OCRResultView({ result, fileName }: OCRResultViewProps) {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);

  const handleCopyText = async () => {
    if (!result.text) {
      toast.warning('No text to copy');
      return;
    }

    try {
      await navigator.clipboard.writeText(result.text);
      setCopied(true);
      toast.success('Text copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toast.error('Failed to copy text');
    }
  };

  const handleDownloadText = () => {
    if (!result.text) {
      toast.warning('No text to download');
      return;
    }

    const blob = new Blob([result.text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}_ocr.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Text file downloaded');
  };

  if (!result.success) {
    return (
      <div className="result-error">
        <Icon name="AlertCircle" size={24} />
        <h3>OCR Processing Failed</h3>
        <p>{result.error || 'An unknown error occurred'}</p>
      </div>
    );
  }

  const wordCount = result.text.trim() ? result.text.trim().split(/\s+/).length : 0;
  const charCount = result.text.length;

  return (
    <div className="ocr-result-view">
      {/* Metadata Header */}
      <div className="result-header">
        <div className="result-info">
          <div className="info-item">
            <Icon name="FileImage" size={16} />
            <span className="info-label">File:</span>
            <span className="info-value">{fileName}</span>
          </div>
          <div className="info-item">
            <Icon name="Cpu" size={16} />
            <span className="info-label">Engine:</span>
            <span className="info-value">{ENGINE_LABELS[result.engine]}</span>
          </div>
          <div className="info-item">
            <Icon name="FileText" size={16} />
            <span className="info-label">Pages:</span>
            <span className="info-value">{result.pages_processed}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="result-actions">
          <button
            className="action-button"
            onClick={handleCopyText}
            disabled={!result.text}
            title="Copy text to clipboard"
          >
            <Icon name={copied ? 'Check' : 'Copy'} size={16} />
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            className="action-button"
            onClick={handleDownloadText}
            disabled={!result.text}
            title="Download text as file"
          >
            <Icon name="Download" size={16} />
            Download
          </button>
        </div>
      </div>

      {/* Text Stats */}
      <div className="text-stats">
        <div className="stat-item">
          <Icon name="Type" size={14} />
          <span>{charCount.toLocaleString()} characters</span>
        </div>
        <div className="stat-item">
          <Icon name="AlignLeft" size={14} />
          <span>{wordCount.toLocaleString()} words</span>
        </div>
      </div>

      {/* Extracted Text */}
      <div className="text-container">
        <div className="text-header">
          <h3>Extracted Text</h3>
          {!result.text && (
            <span className="empty-badge">
              <Icon name="AlertTriangle" size={14} />
              No text detected
            </span>
          )}
        </div>
        <div className="text-content">
          {result.text ? (
            <pre className="extracted-text">{result.text}</pre>
          ) : (
            <div className="empty-state">
              <Icon name="FileQuestion" size={48} />
              <p>No text was detected in the image</p>
              <p className="hint">Try using a different engine or a clearer image</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
