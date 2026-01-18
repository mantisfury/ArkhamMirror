/**
 * Media Forensics Types
 *
 * Type definitions for the Media Forensics shard.
 */

// ============================================
// Status and Enum Types
// ============================================

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type VerificationStatus = 'verified' | 'flagged' | 'unknown' | 'tampered';

export type FindingSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export type C2PAValidationStatus = 'valid' | 'invalid' | 'expired' | 'revoked' | 'unknown';

// ============================================
// EXIF Data Types
// ============================================

export interface ExifGPSData {
  latitude: number | null;
  longitude: number | null;
  altitude: number | null;
  altitude_ref: string | null;
  gps_timestamp: string | null;
  gps_date: string | null;
  direction: number | null;
  direction_ref: string | null;
}

export interface ExifCameraData {
  make: string | null;
  model: string | null;
  serial_number: string | null;
  lens_make: string | null;
  lens_model: string | null;
  lens_serial: string | null;
}

export interface ExifImageData {
  width: number | null;
  height: number | null;
  orientation: number | null;
  color_space: string | null;
  bits_per_sample: number | null;
  compression: string | null;
}

export interface ExifCaptureSettings {
  exposure_time: string | null;
  f_number: number | null;
  iso: number | null;
  focal_length: number | null;
  focal_length_35mm: number | null;
  exposure_mode: string | null;
  exposure_program: string | null;
  metering_mode: string | null;
  white_balance: string | null;
  flash: string | null;
}

export interface ExifTimestamps {
  datetime_original: string | null;
  datetime_digitized: string | null;
  datetime_modified: string | null;
  timezone_offset: string | null;
}

export interface ExifSoftware {
  software: string | null;
  processing_software: string | null;
  host_computer: string | null;
  firmware: string | null;
}

export interface ExifData {
  camera: ExifCameraData;
  image: ExifImageData;
  gps: ExifGPSData;
  capture: ExifCaptureSettings;
  timestamps: ExifTimestamps;
  software: ExifSoftware;
  raw_data: Record<string, unknown>;
  warnings: string[];
}

// ============================================
// C2PA (Content Credentials) Types
// ============================================

export interface C2PAAssertion {
  label: string;
  data: Record<string, unknown>;
  instance?: number;
}

export interface C2PAAction {
  action: string;
  when: string | null;
  software_agent: string | null;
  parameters: Record<string, unknown>;
}

export interface C2PAIngredient {
  title: string;
  format: string;
  document_id: string | null;
  instance_id: string | null;
  relationship: string;
  thumbnail: string | null;
}

export interface C2PASigner {
  name: string;
  organization: string | null;
  issued_date: string | null;
  expiry_date: string | null;
  is_trusted: boolean;
  trust_chain: string[];
  validation_status: C2PAValidationStatus;
}

export interface C2PAManifest {
  claim_generator: string;
  title: string | null;
  format: string | null;
  instance_id: string | null;
  assertions: C2PAAssertion[];
  actions: C2PAAction[];
  ingredients: C2PAIngredient[];
  signer: C2PASigner | null;
  signature_date: string | null;
}

export interface C2PAData {
  has_manifest: boolean;
  manifests: C2PAManifest[];
  active_manifest_index: number | null;
  validation_status: C2PAValidationStatus;
  validation_errors: string[];
  provenance_chain: string[];
}

// ============================================
// ELA (Error Level Analysis) Types
// ============================================

export interface ELARegion {
  x: number;
  y: number;
  width: number;
  height: number;
  avg_intensity: number;
  max_intensity: number;
  is_suspicious: boolean;
  description: string;
}

export interface ELAResult {
  id: string;
  doc_id: string;
  analysis_id: string;
  quality_level: number;
  original_image_url: string | null;
  ela_image_url: string | null;
  ela_image_base64: string | null;
  global_avg_intensity: number;
  global_max_intensity: number;
  suspicious_regions: ELARegion[];
  is_potentially_edited: boolean;
  confidence: number;
  generated_at: string;
}

// ============================================
// Sun Position Analysis Types
// ============================================

export interface SunPosition {
  azimuth: number;
  altitude: number;
  calculated_time: string;
  location_lat: number;
  location_lon: number;
}

export interface ShadowAnalysis {
  detected_shadows: {
    object_id: string;
    shadow_direction: number;
    shadow_length: number;
    confidence: number;
  }[];
  average_shadow_direction: number | null;
  consistency_score: number;
}

export interface SunPositionResult {
  id: string;
  doc_id: string;
  analysis_id: string;
  claimed_location: { lat: number; lon: number } | null;
  claimed_time: string | null;
  calculated_sun_position: SunPosition | null;
  shadow_analysis: ShadowAnalysis | null;
  is_consistent: boolean;
  inconsistency_details: string[];
  confidence: number;
  generated_at: string;
}

// ============================================
// Similar Images Types
// ============================================

export interface SimilarImage {
  id: string;
  doc_id: string;
  filename: string;
  similarity_score: number;
  similarity_type: 'exact' | 'near_duplicate' | 'visually_similar' | 'content_similar';
  match_details: {
    hash_distance?: number;
    feature_similarity?: number;
    matching_regions?: { x: number; y: number; width: number; height: number }[];
    source_url?: string;
    source_domain?: string;
  };
  thumbnail_url: string | null;
  thumbnail_base64: string | null;
  source: string | null;
  found_at: string;
}

export interface ReverseImageSearchUrl {
  engine: string;
  url: string;
  icon: string;
  description: string;
  type: 'url_search' | 'upload_search';
  instructions?: string;
}

export interface SimilarImagesResult {
  id: string;
  doc_id: string;
  analysis_id: string;
  search_type: 'internal' | 'external' | 'both';
  total_found: number;
  similar_images: SimilarImage[];
  exact_matches: number;
  near_duplicates: number;
  visually_similar: number;
  generated_at: string;
  search_urls?: ReverseImageSearchUrl[];  // URLs for manual reverse image search
}

// ============================================
// Forensic Finding Types
// ============================================

export interface ForensicFinding {
  id: string;
  category: 'exif' | 'c2pa' | 'ela' | 'sun_position' | 'similar_images' | 'general';
  severity: FindingSeverity;
  title: string;
  description: string;
  evidence: Record<string, unknown>;
  recommendation: string | null;
  confidence: number;
  auto_detected: boolean;
  detected_at: string;
}

// ============================================
// Media Analysis Types
// ============================================

export interface PerceptualHashes {
  phash: string | null;
  dhash: string | null;
  ahash: string | null;
}

export interface MediaAnalysis {
  id: string;
  doc_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  file_hash_md5: string | null;
  file_hash_sha256: string | null;
  status: AnalysisStatus;
  verification_status: VerificationStatus;
  integrity_status: string;

  // Analysis components
  exif_data: ExifData | null;
  c2pa_data: C2PAData | null;
  ela_result: ELAResult | null;
  sun_position_result: SunPositionResult | null;
  similar_images_result: SimilarImagesResult | null;
  perceptual_hashes: PerceptualHashes | null;

  // Findings
  findings: ForensicFinding[];
  findings_count: number;
  critical_findings: number;
  high_findings: number;

  // Metadata
  analyzed_at: string;
  updated_at: string;
  analyzed_by: string;
  notes: string | null;
}

// ============================================
// Statistics Types
// ============================================

export interface AnalysisStats {
  total_analyses: number;
  by_status: Record<AnalysisStatus, number>;
  by_verification: Record<VerificationStatus, number>;
  with_c2pa: number;
  with_exif: number;
  with_gps: number;
  with_findings: number;
  critical_findings_total: number;
  high_findings_total: number;
  ela_analyses: number;
  sun_position_analyses: number;
  similar_images_searches: number;
  avg_findings_per_analysis: number;
}

// ============================================
// API Request/Response Types
// ============================================

export interface AnalyzeDocumentRequest {
  doc_id: string;
  run_ela?: boolean;
  run_sun_position?: boolean;
  run_similar_search?: boolean;
  similar_search_type?: 'internal' | 'external' | 'both';
}

export interface AnalyzeDocumentResponse {
  analysis: MediaAnalysis;
  job_id?: string;
}

export interface AnalysisListResponse {
  total: number;
  items: MediaAnalysis[];
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface GenerateELARequest {
  analysis_id: string;
  quality_level?: number;
}

export interface GenerateELAResponse {
  result: ELAResult;
}

export interface SunPositionRequest {
  analysis_id: string;
  override_location?: { lat: number; lon: number };
  override_time?: string;
}

export interface SunPositionResponse {
  result: SunPositionResult;
}

export interface FindSimilarRequest {
  analysis_id: string;
  search_type?: 'internal' | 'external' | 'both';
  limit?: number;
}

export interface FindSimilarResponse {
  result: SimilarImagesResult;
}

export interface StatsResponse {
  stats: AnalysisStats;
}

export interface C2PASupportResponse {
  supported: boolean;
  version: string | null;
  message: string;
}

// ============================================
// Display Helpers
// ============================================

export const STATUS_LABELS: Record<AnalysisStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
};

export const STATUS_COLORS: Record<AnalysisStatus, string> = {
  pending: 'blue',
  processing: 'yellow',
  completed: 'green',
  failed: 'red',
};

export const VERIFICATION_LABELS: Record<VerificationStatus, string> = {
  verified: 'Verified',
  flagged: 'Flagged',
  unknown: 'Unknown',
  tampered: 'Tampered',
};

export const VERIFICATION_COLORS: Record<VerificationStatus, string> = {
  verified: 'var(--arkham-success, #22c55e)',
  flagged: 'var(--arkham-warning, #eab308)',
  unknown: 'var(--arkham-text-muted, #6b7280)',
  tampered: 'var(--arkham-error, #ef4444)',
};

export const SEVERITY_LABELS: Record<FindingSeverity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

export const SEVERITY_COLORS: Record<FindingSeverity, string> = {
  critical: 'var(--arkham-error, #ef4444)',
  high: 'var(--arkham-warning, #f97316)',
  medium: 'var(--arkham-warning, #eab308)',
  low: 'var(--arkham-info, #3b82f6)',
  info: 'var(--arkham-text-muted, #6b7280)',
};

export const C2PA_VALIDATION_LABELS: Record<C2PAValidationStatus, string> = {
  valid: 'Valid',
  invalid: 'Invalid',
  expired: 'Expired',
  revoked: 'Revoked',
  unknown: 'Unknown',
};

export const C2PA_VALIDATION_COLORS: Record<C2PAValidationStatus, string> = {
  valid: 'var(--arkham-success, #22c55e)',
  invalid: 'var(--arkham-error, #ef4444)',
  expired: 'var(--arkham-warning, #f97316)',
  revoked: 'var(--arkham-error, #dc2626)',
  unknown: 'var(--arkham-text-muted, #6b7280)',
};

// Filter options
export const STATUS_OPTIONS: { value: AnalysisStatus; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
];

export const VERIFICATION_OPTIONS: { value: VerificationStatus; label: string }[] = [
  { value: 'verified', label: 'Verified' },
  { value: 'flagged', label: 'Flagged' },
  { value: 'unknown', label: 'Unknown' },
  { value: 'tampered', label: 'Tampered' },
];

export const SEVERITY_OPTIONS: { value: FindingSeverity; label: string }[] = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
  { value: 'info', label: 'Info' },
];
