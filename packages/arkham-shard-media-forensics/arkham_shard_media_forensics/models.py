"""Data models for the Media Forensics Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, List, Dict


class IntegrityStatus(str, Enum):
    """Integrity status of analyzed media."""
    UNKNOWN = "unknown"
    VERIFIED = "verified"
    FLAGGED = "flagged"
    UNVERIFIED = "unverified"


class ELAAssessment(str, Enum):
    """ELA analysis assessment."""
    UNIFORM = "uniform"
    VARIABLE = "variable"
    TYPICAL = "typical"


class SunVerificationStatus(str, Enum):
    """Sun position verification status."""
    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    UNCERTAIN = "uncertain"
    UNAVAILABLE = "unavailable"


class HashType(str, Enum):
    """Types of perceptual hashes."""
    PHASH = "phash"
    DHASH = "dhash"
    AHASH = "ahash"


# ===========================================
# API Request Models (Pydantic)
# ===========================================

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request to analyze a document."""
    document_id: str


class BatchAnalyzeRequest(BaseModel):
    """Request to analyze multiple documents."""
    document_ids: List[str]


class ELARequest(BaseModel):
    """Request to generate ELA analysis."""
    analysis_id: str
    quality: int = Field(default=95, ge=70, le=100)
    scale: int = Field(default=15, ge=5, le=30)


class SunPositionRequest(BaseModel):
    """Request to calculate sun position."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    datetime: str  # ISO format


class SimilarSearchRequest(BaseModel):
    """Request to find similar images."""
    analysis_id: str
    hash_type: str = Field(default="phash", pattern="^(phash|dhash|ahash)$")
    threshold: int = Field(default=10, ge=0, le=64)


# ===========================================
# API Response Models (Pydantic)
# ===========================================

class CountResponse(BaseModel):
    """Response with count."""
    count: int


class AnalysisListResponse(BaseModel):
    """Response with list of analyses."""
    items: List[Dict[str, Any]]
    total: int


class AnalysisResponse(BaseModel):
    """Response for a single analysis."""
    analysis_id: str
    document_id: str
    exif: Dict[str, Any]
    hashes: Dict[str, str]
    c2pa: Optional[Dict[str, Any]]
    c2pa_interpretation: Optional[Dict[str, Any]]
    warnings: List[str]
    integrity_status: str


class BatchAnalyzeResponse(BaseModel):
    """Response for batch analysis."""
    results: List[Dict[str, Any]]


class ELAResponse(BaseModel):
    """Response for ELA analysis."""
    success: bool
    ela_image_base64: Optional[str] = None
    quality_used: Optional[int] = None
    scale_used: Optional[int] = None
    interpretation: Optional[Dict[str, Any]] = None
    caveats: List[str] = []
    error: Optional[str] = None


class SunPositionResponse(BaseModel):
    """Response for sun position calculation."""
    success: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    datetime: Optional[str] = None
    sun_altitude: Optional[float] = None
    sun_azimuth: Optional[float] = None
    expected_shadow_direction: Optional[float] = None
    shadow_length_ratio: Optional[float] = None
    sun_above_horizon: Optional[bool] = None
    interpretation: Optional[str] = None
    error: Optional[str] = None


class SimilarImageResult(BaseModel):
    """Result for a similar image."""
    analysis_id: str
    hash: str
    hamming_distance: int
    similarity_score: float


class SimilarSearchResponse(BaseModel):
    """Response for similar image search."""
    similar_images: List[SimilarImageResult]


class StatsResponse(BaseModel):
    """Response for statistics."""
    stats: Dict[str, Any]


class C2PASupportResponse(BaseModel):
    """Response for C2PA support check."""
    c2pa_available: bool
    signature_verification_available: bool
    pysolar_available: bool


# ===========================================
# Data Classes for Internal Use
# ===========================================

@dataclass
class MediaAnalysis:
    """A media analysis record."""
    id: str
    document_id: str
    tenant_id: Optional[str] = None

    # File info
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None

    # Cryptographic hashes
    sha256: Optional[str] = None
    md5: Optional[str] = None

    # Perceptual hashes
    phash: Optional[str] = None
    dhash: Optional[str] = None
    ahash: Optional[str] = None

    # EXIF data
    exif_data: Dict[str, Any] = field(default_factory=dict)

    # Camera info
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None

    # Timestamps
    datetime_original: Optional[str] = None
    datetime_digitized: Optional[str] = None
    datetime_modified: Optional[str] = None

    # GPS
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None

    # C2PA
    c2pa_data: Dict[str, Any] = field(default_factory=dict)
    has_c2pa: bool = False
    c2pa_signer: Optional[str] = None
    c2pa_timestamp: Optional[str] = None

    # Analysis results
    warnings: List[str] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    integrity_status: str = "unknown"
    confidence_score: float = 0.0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SimilarImage:
    """A similar image match record."""
    id: str
    source_analysis_id: str
    target_analysis_id: str
    hash_type: str
    hamming_distance: int
    similarity_score: float
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ELAResult:
    """An ELA analysis result."""
    id: str
    analysis_id: str
    quality: int = 95
    ela_image_path: Optional[str] = None

    # Analysis results
    uniform_regions: List[Dict[str, Any]] = field(default_factory=list)
    anomalous_regions: List[Dict[str, Any]] = field(default_factory=list)
    interpretation: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SunVerification:
    """A sun position verification record."""
    id: str
    analysis_id: str

    # Input parameters
    claimed_datetime: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Calculated sun position
    sun_altitude: Optional[float] = None
    sun_azimuth: Optional[float] = None
    expected_shadow_direction: Optional[float] = None

    # Verification result
    verification_status: str = "unknown"
    notes: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AnalysisStats:
    """Statistics about media analyses."""
    total_analyses: int = 0
    with_exif: int = 0
    with_gps: int = 0
    with_c2pa: int = 0
    with_warnings: int = 0
    ai_generated_detected: int = 0
    by_integrity_status: Dict[str, int] = field(default_factory=dict)
    by_file_type: Dict[str, int] = field(default_factory=dict)
