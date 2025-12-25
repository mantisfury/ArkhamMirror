/**
 * OCR Types
 *
 * Type definitions matching the backend OCR shard models.
 */

// OCR Engine options
export type OCREngine = 'paddle' | 'qwen';

// Bounding box for detected text
export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
}

// Text block with position
export interface TextBlock {
  text: string;
  bbox: BoundingBox;
  line_number: number;
  block_number: number;
}

// OCR result for a single page
export interface PageOCRResult {
  page_number: number;
  text: string;
  blocks: TextBlock[];
  language: string;
  engine: OCREngine;
  confidence: number;
  processing_time_ms: number;
}

// OCR result for a full document
export interface DocumentOCRResult {
  document_id: string;
  pages: PageOCRResult[];
  total_text: string;
  engine: OCREngine;
  total_processing_time_ms: number;
}

// API Response types
export interface OCRResponse {
  success: boolean;
  text: string;
  pages_processed: number;
  engine: OCREngine;
  error?: string;
}

export interface OCRHealthResponse {
  status: string;
  shard: string;
  paddle_available?: boolean;
  qwen_available?: boolean;
}

export interface OCRRequest {
  document_id?: string;
  image_path?: string;
  engine?: OCREngine;
  language?: string;
}

// Engine status info
export interface EngineStatus {
  name: string;
  available: boolean;
  description: string;
  speed: 'fast' | 'medium' | 'slow';
  accuracy: 'good' | 'excellent';
}

// Recent OCR result summary
export interface OCRResultSummary {
  id: string;
  document_id?: string;
  image_name: string;
  text_preview: string;
  engine: OCREngine;
  pages_processed: number;
  confidence: number;
  timestamp: string;
}

// Engine option labels
export const ENGINE_LABELS: Record<OCREngine, string> = {
  paddle: 'PaddleOCR (Fast)',
  qwen: 'Qwen-VL (Accurate)',
};

export const ENGINE_DESCRIPTIONS: Record<OCREngine, string> = {
  paddle: 'Fast and efficient OCR for clean documents',
  qwen: 'High accuracy OCR using vision-language model',
};
