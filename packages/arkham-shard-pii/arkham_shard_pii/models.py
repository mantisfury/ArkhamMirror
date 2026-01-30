"""PII Shard - Request/response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PiiEntity(BaseModel):
    """Single PII entity (type + value, optional position)."""
    type: str = Field(..., description="Entity type (e.g. EMAIL_ADDRESS, US_SSN)")
    value: str = Field(..., description="Redacted or truncated value")
    start: Optional[int] = Field(None, description="Start offset in source text")
    end: Optional[int] = Field(None, description="End offset in source text")
    score: Optional[float] = Field(None, description="Confidence 0-1")
    source_field: Optional[str] = Field(None, description="Metadata key path where found")


class AnalyzeTextRequest(BaseModel):
    """Request to analyze plain text for PII."""
    text: str = Field(..., description="Text to analyze")
    language: str = Field("en", description="Language code")
    score_threshold: float = Field(0.3, ge=0.0, le=1.0, description="Minimum confidence")


class AnalyzeTextResponse(BaseModel):
    """PII analysis result for text."""
    pii_detected: bool = Field(..., description="Whether any PII was found")
    pii_types: List[str] = Field(default_factory=list, description="Unique entity types")
    pii_entities: List[PiiEntity] = Field(default_factory=list, description="Entities found")
    pii_count: int = Field(0, description="Total count")
    backend: str = Field("fallback", description="presidio | fallback")
    error: Optional[str] = Field(None, description="Error message if backend failed")


class AnalyzeMetadataRequest(BaseModel):
    """Request to analyze a metadata dict for PII (all string values)."""
    metadata: Dict[str, Any] = Field(..., description="Metadata to scan")


class AnalyzeMetadataResponse(BaseModel):
    """PII analysis result for metadata."""
    pii_detected: bool = Field(..., description="Whether any PII was found")
    pii_types: List[str] = Field(default_factory=list, description="Unique entity types")
    pii_entities: List[PiiEntity] = Field(default_factory=list, description="Entities found")
    pii_count: int = Field(0, description="Total count")
    backend: str = Field("fallback", description="presidio | fallback")
    error: Optional[str] = Field(None, description="Error message if backend failed")


class HealthResponse(BaseModel):
    """PII service health."""
    status: str = Field(..., description="ok | degraded")
    presidio_available: bool = Field(False, description="Whether Presidio Analyzer is reachable")
    presidio_url: Optional[str] = Field(None, description="Configured Presidio base URL")
