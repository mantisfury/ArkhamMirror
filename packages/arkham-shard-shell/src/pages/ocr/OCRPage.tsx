/**
 * OCRPage - Main OCR interface
 *
 * Provides OCR processing with engine selection and status monitoring.
 */

import { useState, useRef } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import { ocrUpload } from './api';
import { OCRResultView } from './OCRResultView';
import type { OCRHealthResponse, OCREngine, OCRResponse } from './types';
import { ENGINE_LABELS, ENGINE_DESCRIPTIONS } from './types';

export function OCRPage() {
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedEngine, setSelectedEngine] = useState<OCREngine>('paddle');
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<OCRResponse | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string>('');

  // Fetch OCR health status
  const { data: health, loading: healthLoading } = useFetch<OCRHealthResponse>('/api/ocr/health');

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/bmp'];
    if (!validTypes.includes(file.type)) {
      toast.error('Please select a valid image file (PNG, JPEG, WebP, or BMP)');
      return;
    }

    // Validate file size (max 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error('File size must be less than 10MB');
      return;
    }

    setIsProcessing(true);
    setUploadedFileName(file.name);
    setResult(null);

    try {
      const ocrResult = await ocrUpload(file, selectedEngine, 'en');
      setResult(ocrResult);

      if (ocrResult.success) {
        toast.success(`OCR completed successfully using ${ENGINE_LABELS[ocrResult.engine]}`);
      } else {
        toast.error(ocrResult.error || 'OCR processing failed');
      }
    } catch (error) {
      toast.error(`OCR failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setResult({
        success: false,
        text: '',
        pages_processed: 0,
        engine: selectedEngine,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setIsProcessing(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const engineAvailable = (engine: OCREngine): boolean => {
    if (!health) return false;
    if (engine === 'paddle') return health.paddle_available !== false;
    if (engine === 'qwen') return health.qwen_available === true;
    return false;
  };

  return (
    <div className="ocr-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="ScanText" size={28} />
          <div>
            <h1>Optical Character Recognition</h1>
            <p className="page-description">Extract text from document images</p>
          </div>
        </div>
      </header>

      {/* Engine Status */}
      <section className="engine-status-section">
        <h2>
          <Icon name="Cpu" size={20} />
          OCR Engines
        </h2>
        {healthLoading ? (
          <div className="loading-state">
            <Icon name="Loader2" size={20} className="spinning" />
            Checking engine status...
          </div>
        ) : (
          <div className="engine-grid">
            {/* PaddleOCR */}
            <div className={`engine-card ${engineAvailable('paddle') ? 'available' : 'unavailable'}`}>
              <div className="engine-header">
                <Icon name="Zap" size={20} />
                <span className="engine-name">PaddleOCR</span>
                <span className={`status-badge ${engineAvailable('paddle') ? 'healthy' : 'offline'}`}>
                  {engineAvailable('paddle') ? 'Available' : 'Unavailable'}
                </span>
              </div>
              <p className="engine-description">{ENGINE_DESCRIPTIONS.paddle}</p>
              <div className="engine-specs">
                <span className="spec-badge speed-fast">
                  <Icon name="Gauge" size={14} />
                  Fast
                </span>
                <span className="spec-badge accuracy-good">
                  <Icon name="Target" size={14} />
                  Good Accuracy
                </span>
              </div>
            </div>

            {/* Qwen-VL */}
            <div className={`engine-card ${engineAvailable('qwen') ? 'available' : 'unavailable'}`}>
              <div className="engine-header">
                <Icon name="Sparkles" size={20} />
                <span className="engine-name">Qwen-VL</span>
                <span className={`status-badge ${engineAvailable('qwen') ? 'healthy' : 'offline'}`}>
                  {engineAvailable('qwen') ? 'Available' : 'Unavailable'}
                </span>
              </div>
              <p className="engine-description">{ENGINE_DESCRIPTIONS.qwen}</p>
              <div className="engine-specs">
                <span className="spec-badge speed-slow">
                  <Icon name="Gauge" size={14} />
                  Slower
                </span>
                <span className="spec-badge accuracy-excellent">
                  <Icon name="Target" size={14} />
                  Excellent Accuracy
                </span>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Upload Section */}
      <section className="upload-section">
        <h2>
          <Icon name="Upload" size={20} />
          Upload & Process
        </h2>

        <div className="upload-container">
          {/* Engine Selection */}
          <div className="engine-selector">
            <label htmlFor="engine-select">Select OCR Engine:</label>
            <select
              id="engine-select"
              value={selectedEngine}
              onChange={(e) => setSelectedEngine(e.target.value as OCREngine)}
              disabled={isProcessing}
            >
              <option value="paddle" disabled={!engineAvailable('paddle')}>
                {ENGINE_LABELS.paddle} {!engineAvailable('paddle') && '(Unavailable)'}
              </option>
              <option value="qwen" disabled={!engineAvailable('qwen')}>
                {ENGINE_LABELS.qwen} {!engineAvailable('qwen') && '(Unavailable)'}
              </option>
            </select>
          </div>

          {/* Upload Button */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          <button
            className="upload-button"
            onClick={handleUploadClick}
            disabled={isProcessing || !engineAvailable(selectedEngine)}
          >
            {isProcessing ? (
              <>
                <Icon name="Loader2" size={20} className="spinning" />
                Processing...
              </>
            ) : (
              <>
                <Icon name="Upload" size={20} />
                Upload Image
              </>
            )}
          </button>

          <p className="upload-hint">
            Supported formats: PNG, JPEG, WebP, BMP (max 10MB)
          </p>
        </div>
      </section>

      {/* Results Section */}
      {result && (
        <section className="results-section">
          <h2>
            <Icon name="FileText" size={20} />
            OCR Result
          </h2>
          <OCRResultView
            result={result}
            fileName={uploadedFileName}
          />
        </section>
      )}

      {/* Info Section */}
      <section className="info-section">
        <h2>
          <Icon name="Info" size={20} />
          About OCR
        </h2>
        <div className="info-grid">
          <div className="info-card">
            <Icon name="FileSearch" size={24} />
            <h3>When to use PaddleOCR</h3>
            <p>Use for clean, well-formatted documents where speed is important. Ideal for batch processing.</p>
          </div>
          <div className="info-card">
            <Icon name="Sparkles" size={24} />
            <h3>When to use Qwen-VL</h3>
            <p>Use for complex layouts, handwriting, or challenging documents where accuracy is critical.</p>
          </div>
          <div className="info-card">
            <Icon name="Languages" size={24} />
            <h3>Language Support</h3>
            <p>Currently supports English text recognition. Additional languages coming soon.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
