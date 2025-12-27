"""
Credibility Shard - FastAPI Routes

REST API endpoints for credibility assessment management.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .models import (
    AssessmentMethod,
    CredibilityLevel,
    SourceType,
)

router = APIRouter(prefix="/api/credibility", tags=["credibility"])

# === Pydantic Request/Response Models ===


class CredibilityFactorModel(BaseModel):
    """Request/response model for credibility factor."""
    factor_type: str = Field(..., description="Factor type identifier")
    weight: float = Field(..., ge=0.0, le=1.0, description="Factor weight (0-1)")
    score: int = Field(..., ge=0, le=100, description="Factor score (0-100)")
    notes: Optional[str] = None


class AssessmentCreate(BaseModel):
    """Request model for creating an assessment."""
    source_type: SourceType
    source_id: str = Field(..., description="ID of the source being assessed")
    score: int = Field(..., ge=0, le=100, description="Credibility score (0-100)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Assessment confidence (0-1)")
    factors: Optional[List[CredibilityFactorModel]] = None
    assessed_by: AssessmentMethod = Field(default=AssessmentMethod.MANUAL)
    assessor_id: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AssessmentUpdate(BaseModel):
    """Request model for updating an assessment."""
    score: Optional[int] = Field(None, ge=0, le=100)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    factors: Optional[List[CredibilityFactorModel]] = None
    notes: Optional[str] = None


class AssessmentResponse(BaseModel):
    """Response model for an assessment."""
    id: str
    source_type: str
    source_id: str
    score: int
    confidence: float
    level: str
    factors: List[CredibilityFactorModel]
    assessed_by: str
    assessor_id: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


class AssessmentListResponse(BaseModel):
    """Response model for listing assessments."""
    assessments: List[AssessmentResponse]
    total: int
    limit: int
    offset: int


class SourceCredibilityResponse(BaseModel):
    """Response model for source aggregate credibility."""
    source_type: str
    source_id: str
    avg_score: float
    assessment_count: int
    latest_score: int
    latest_confidence: float
    latest_assessment_id: str
    latest_assessed_at: str
    level: str


class CalculateRequest(BaseModel):
    """Request model for calculating credibility."""
    source_type: SourceType
    source_id: str
    use_llm: bool = Field(default=False, description="Use LLM for analysis")


class CalculationResponse(BaseModel):
    """Response model for credibility calculation."""
    source_type: str
    source_id: str
    calculated_score: int
    confidence: float
    factors: List[CredibilityFactorModel]
    method: str
    processing_time_ms: float
    notes: Optional[str]
    errors: List[str]


class StandardFactorResponse(BaseModel):
    """Response model for standard factor."""
    factor_type: str
    default_weight: float
    description: str
    scoring_guidance: str


class StatisticsResponse(BaseModel):
    """Response model for statistics."""
    total_assessments: int
    by_source_type: Dict[str, int]
    by_level: Dict[str, int]
    by_method: Dict[str, int]
    avg_score: float
    avg_confidence: float
    unreliable_count: int
    low_count: int
    medium_count: int
    high_count: int
    verified_count: int
    sources_assessed: int
    avg_assessments_per_source: float


class CountResponse(BaseModel):
    """Response model for count endpoint."""
    count: int


class HistoryResponse(BaseModel):
    """Response model for source history."""
    source_type: str
    source_id: str
    assessments: List[AssessmentResponse]
    score_trend: str
    avg_score: float
    min_score: int
    max_score: int


# === Helper Functions ===


def _get_shard(request):
    """Get the credibility shard instance from app state."""
    shard = getattr(request.app.state, "credibility_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Credibility shard not available")
    return shard


def _assessment_to_response(assessment) -> AssessmentResponse:
    """Convert CredibilityAssessment to response model."""
    from .models import CredibilityFactor

    factors = [
        CredibilityFactorModel(
            factor_type=f.factor_type,
            weight=f.weight,
            score=f.score,
            notes=f.notes,
        )
        for f in assessment.factors
    ]

    return AssessmentResponse(
        id=assessment.id,
        source_type=assessment.source_type.value,
        source_id=assessment.source_id,
        score=assessment.score,
        confidence=assessment.confidence,
        level=assessment.level.value,
        factors=factors,
        assessed_by=assessment.assessed_by.value,
        assessor_id=assessment.assessor_id,
        notes=assessment.notes,
        created_at=assessment.created_at.isoformat(),
        updated_at=assessment.updated_at.isoformat(),
        metadata=assessment.metadata,
    )


def _models_to_factors(models: List[CredibilityFactorModel]):
    """Convert Pydantic factor models to CredibilityFactor objects."""
    from .models import CredibilityFactor

    return [
        CredibilityFactor(
            factor_type=m.factor_type,
            weight=m.weight,
            score=m.score,
            notes=m.notes,
        )
        for m in models
    ]


# === Endpoints ===


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "shard": "credibility"}


@router.get("/count", response_model=CountResponse)
async def get_count(
    request: Request,
    level: Optional[str] = Query(None, description="Filter by credibility level"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
):
    """Get count of assessments (used for badge)."""
    shard = _get_shard(request)
    count = await shard.get_count(level=level, source_type=source_type)
    return CountResponse(count=count)


@router.get("/low/count", response_model=CountResponse)
async def get_low_count(request: Request):
    """Get count of low-credibility assessments (for badge)."""
    shard = _get_shard(request)
    count = await shard.get_count(level="low")
    return CountResponse(count=count)


@router.get("/", response_model=AssessmentListResponse)
async def list_assessments(
    request: Request,
    source_type: Optional[SourceType] = Query(None),
    source_id: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
    level: Optional[CredibilityLevel] = Query(None),
    assessed_by: Optional[AssessmentMethod] = Query(None),
    assessor_id: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List credibility assessments with optional filtering."""
    from .models import CredibilityFilter

    shard = _get_shard(request)

    filter = CredibilityFilter(
        source_type=source_type,
        source_id=source_id,
        min_score=min_score,
        max_score=max_score,
        level=level,
        assessed_by=assessed_by,
        assessor_id=assessor_id,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
    )

    assessments = await shard.list_assessments(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count()

    return AssessmentListResponse(
        assessments=[_assessment_to_response(a) for a in assessments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=AssessmentResponse, status_code=201)
async def create_assessment(body: AssessmentCreate, request: Request):
    """Create a new credibility assessment."""
    shard = _get_shard(request)

    factors = _models_to_factors(body.factors) if body.factors else None

    assessment = await shard.create_assessment(
        source_type=body.source_type,
        source_id=body.source_id,
        score=body.score,
        confidence=body.confidence,
        factors=factors,
        assessed_by=body.assessed_by,
        assessor_id=body.assessor_id,
        notes=body.notes,
        metadata=body.metadata,
    )

    return _assessment_to_response(assessment)


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(assessment_id: str, request: Request):
    """Get a specific assessment by ID."""
    shard = _get_shard(request)
    assessment = await shard.get_assessment(assessment_id)

    if not assessment:
        raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")

    return _assessment_to_response(assessment)


@router.put("/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(assessment_id: str, body: AssessmentUpdate, request: Request):
    """Update an existing assessment."""
    shard = _get_shard(request)

    factors = _models_to_factors(body.factors) if body.factors else None

    assessment = await shard.update_assessment(
        assessment_id=assessment_id,
        score=body.score,
        confidence=body.confidence,
        factors=factors,
        notes=body.notes,
    )

    if not assessment:
        raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")

    return _assessment_to_response(assessment)


@router.delete("/{assessment_id}", status_code=204)
async def delete_assessment(assessment_id: str, request: Request):
    """Delete an assessment."""
    shard = _get_shard(request)
    success = await shard.delete_assessment(assessment_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")


# === Source Endpoints ===


@router.get("/source/{source_type}/{source_id}", response_model=SourceCredibilityResponse)
async def get_source_credibility(source_type: SourceType, source_id: str, request: Request):
    """Get aggregate credibility for a source."""
    shard = _get_shard(request)
    source_cred = await shard.get_source_credibility(source_type, source_id)

    if not source_cred:
        raise HTTPException(
            status_code=404,
            detail=f"No credibility assessments found for {source_type.value}:{source_id}"
        )

    return SourceCredibilityResponse(
        source_type=source_cred.source_type.value,
        source_id=source_cred.source_id,
        avg_score=source_cred.avg_score,
        assessment_count=source_cred.assessment_count,
        latest_score=source_cred.latest_score,
        latest_confidence=source_cred.latest_confidence,
        latest_assessment_id=source_cred.latest_assessment_id,
        latest_assessed_at=source_cred.latest_assessed_at.isoformat(),
        level=source_cred.level.value,
    )


@router.get("/source/{source_type}/{source_id}/history", response_model=HistoryResponse)
async def get_source_history(source_type: SourceType, source_id: str, request: Request):
    """Get credibility history for a source."""
    shard = _get_shard(request)
    history = await shard.get_source_history(source_type, source_id)

    return HistoryResponse(
        source_type=history.source_type.value,
        source_id=history.source_id,
        assessments=[_assessment_to_response(a) for a in history.assessments],
        score_trend=history.score_trend,
        avg_score=history.avg_score,
        min_score=history.min_score,
        max_score=history.max_score,
    )


@router.post("/calculate", response_model=CalculationResponse)
async def calculate_credibility(body: CalculateRequest, request: Request):
    """Calculate credibility score for a source."""
    shard = _get_shard(request)

    calculation = await shard.calculate_credibility(
        source_type=body.source_type,
        source_id=body.source_id,
        use_llm=body.use_llm,
    )

    factors = [
        CredibilityFactorModel(
            factor_type=f.factor_type,
            weight=f.weight,
            score=f.score,
            notes=f.notes,
        )
        for f in calculation.factors
    ]

    return CalculationResponse(
        source_type=calculation.source_type.value,
        source_id=calculation.source_id,
        calculated_score=calculation.calculated_score,
        confidence=calculation.confidence,
        factors=factors,
        method=calculation.method.value,
        processing_time_ms=calculation.processing_time_ms,
        notes=calculation.notes,
        errors=calculation.errors,
    )


# === Factor Endpoints ===


@router.get("/factors", response_model=List[StandardFactorResponse])
async def list_standard_factors(request: Request):
    """Get list of standard credibility factors."""
    shard = _get_shard(request)
    factors = shard.get_standard_factors()

    return [
        StandardFactorResponse(
            factor_type=f["factor_type"],
            default_weight=f["default_weight"],
            description=f["description"],
            scoring_guidance=f["scoring_guidance"],
        )
        for f in factors
    ]


# === Statistics Endpoints ===


@router.get("/stats", response_model=StatisticsResponse)
async def get_statistics(request: Request):
    """Get statistics about credibility assessments."""
    shard = _get_shard(request)
    stats = await shard.get_statistics()

    return StatisticsResponse(
        total_assessments=stats.total_assessments,
        by_source_type=stats.by_source_type,
        by_level=stats.by_level,
        by_method=stats.by_method,
        avg_score=stats.avg_score,
        avg_confidence=stats.avg_confidence,
        unreliable_count=stats.unreliable_count,
        low_count=stats.low_count,
        medium_count=stats.medium_count,
        high_count=stats.high_count,
        verified_count=stats.verified_count,
        sources_assessed=stats.sources_assessed,
        avg_assessments_per_source=stats.avg_assessments_per_source,
    )


@router.get("/stats/by-source-type", response_model=Dict[str, int])
async def get_stats_by_source_type(request: Request):
    """Get assessment counts by source type."""
    shard = _get_shard(request)
    stats = await shard.get_statistics()
    return stats.by_source_type


# === Filtered List Endpoints (for sub-routes) ===


@router.get("/level/high", response_model=AssessmentListResponse)
async def list_high_credibility(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List high-credibility assessments."""
    from .models import CredibilityFilter

    shard = _get_shard(request)
    filter = CredibilityFilter(level=CredibilityLevel.HIGH)
    assessments = await shard.list_assessments(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(level="high")

    return AssessmentListResponse(
        assessments=[_assessment_to_response(a) for a in assessments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/level/low", response_model=AssessmentListResponse)
async def list_low_credibility(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List low-credibility assessments."""
    from .models import CredibilityFilter

    shard = _get_shard(request)
    filter = CredibilityFilter(level=CredibilityLevel.LOW)
    assessments = await shard.list_assessments(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(level="low")

    return AssessmentListResponse(
        assessments=[_assessment_to_response(a) for a in assessments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/level/unreliable", response_model=AssessmentListResponse)
async def list_unreliable(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List unreliable assessments."""
    from .models import CredibilityFilter

    shard = _get_shard(request)
    filter = CredibilityFilter(level=CredibilityLevel.UNRELIABLE)
    assessments = await shard.list_assessments(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(level="unreliable")

    return AssessmentListResponse(
        assessments=[_assessment_to_response(a) for a in assessments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/level/verified", response_model=AssessmentListResponse)
async def list_verified(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List verified/high-credibility assessments."""
    from .models import CredibilityFilter

    shard = _get_shard(request)
    filter = CredibilityFilter(level=CredibilityLevel.VERIFIED)
    assessments = await shard.list_assessments(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(level="verified")

    return AssessmentListResponse(
        assessments=[_assessment_to_response(a) for a in assessments],
        total=total,
        limit=limit,
        offset=offset,
    )
