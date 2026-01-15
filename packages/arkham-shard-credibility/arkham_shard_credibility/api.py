"""
Credibility Shard - FastAPI Routes

REST API endpoints for credibility assessment management.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .models import (
    AssessmentMethod,
    CredibilityLevel,
    SourceType,
    DeceptionChecklistType,
    DeceptionRisk,
    IndicatorStrength,
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
    items: List[AssessmentResponse]
    total: int
    page: int
    page_size: int


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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """List credibility assessments with optional filtering."""
    from .models import CredibilityFilter

    shard = _get_shard(request)

    # Convert page/page_size to offset/limit
    offset = (page - 1) * page_size
    limit = page_size

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
        items=[_assessment_to_response(a) for a in assessments],
        total=total,
        page=page,
        page_size=page_size,
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


@router.get("/level/{level}", response_model=AssessmentListResponse)
async def list_by_level(
    level: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """List credibility assessments by level (unreliable, low, medium, high, verified)."""
    from .models import CredibilityFilter

    # Validate and convert level
    try:
        cred_level = CredibilityLevel(level.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level: {level}. Must be one of: unreliable, low, medium, high, verified"
        )

    shard = _get_shard(request)

    # Convert page/page_size to offset/limit
    offset = (page - 1) * page_size
    limit = page_size

    filter = CredibilityFilter(level=cred_level)
    assessments = await shard.list_assessments(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(level=level.lower())

    return AssessmentListResponse(
        items=[_assessment_to_response(a) for a in assessments],
        total=total,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# DECEPTION DETECTION (MOM/POP/MOSES/EVE)
# =============================================================================

# === Deception Pydantic Models ===


class DeceptionIndicatorModel(BaseModel):
    """Request/response model for deception indicator."""
    id: str
    checklist: str
    question: str
    answer: Optional[str] = None
    strength: str = "none"
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    evidence_ids: List[str] = []
    notes: Optional[str] = None


class DeceptionChecklistModel(BaseModel):
    """Request/response model for a single checklist."""
    checklist_type: str
    indicators: List[DeceptionIndicatorModel]
    overall_score: int = Field(0, ge=0, le=100)
    risk_level: str = "minimal"
    summary: Optional[str] = None
    completed_at: Optional[str] = None


class DeceptionAssessmentCreate(BaseModel):
    """Request model for creating a deception assessment."""
    source_type: SourceType
    source_id: str = Field(..., description="ID of the source being assessed")
    source_name: Optional[str] = Field(None, description="Human-readable source name")
    linked_assessment_id: Optional[str] = None
    affects_credibility: bool = True
    credibility_weight: float = Field(0.7, ge=0.0, le=1.0, description="Weight in credibility calc (higher = more impact)")


class DeceptionChecklistUpdate(BaseModel):
    """Request model for updating a single checklist."""
    indicators: List[DeceptionIndicatorModel]
    summary: Optional[str] = None


class DeceptionAssessmentUpdate(BaseModel):
    """Request model for updating a deception assessment."""
    source_name: Optional[str] = None
    summary: Optional[str] = None
    red_flags: Optional[List[str]] = None
    affects_credibility: Optional[bool] = None
    credibility_weight: Optional[float] = Field(None, ge=0.0, le=1.0)


class DeceptionAssessmentResponse(BaseModel):
    """Response model for a deception assessment."""
    id: str
    source_type: str
    source_id: str
    source_name: Optional[str]
    mom_checklist: Optional[DeceptionChecklistModel]
    pop_checklist: Optional[DeceptionChecklistModel]
    moses_checklist: Optional[DeceptionChecklistModel]
    eve_checklist: Optional[DeceptionChecklistModel]
    overall_score: int
    risk_level: str
    confidence: float
    completed_checklists: int
    linked_assessment_id: Optional[str]
    affects_credibility: bool
    credibility_weight: float
    assessed_by: str
    assessor_id: Optional[str]
    summary: Optional[str]
    red_flags: List[str]
    created_at: str
    updated_at: str


class DeceptionAssessmentListResponse(BaseModel):
    """Response model for listing deception assessments."""
    assessments: List[DeceptionAssessmentResponse]
    total: int
    limit: int
    offset: int


class LLMChecklistRequest(BaseModel):
    """Request for LLM-assisted checklist completion."""
    context: Optional[str] = Field(None, description="Additional context for LLM analysis")


class LLMChecklistResponse(BaseModel):
    """Response from LLM checklist analysis."""
    checklist: DeceptionChecklistModel
    reasoning: str
    confidence: float
    processing_time_ms: float


class StandardIndicatorResponse(BaseModel):
    """Response model for standard indicator."""
    id: str
    checklist: str
    question: str
    guidance: str
    category: str


# === Deception Helper Functions ===


def _checklist_to_model(checklist) -> Optional[DeceptionChecklistModel]:
    """Convert DeceptionChecklist to Pydantic model."""
    if not checklist:
        return None

    return DeceptionChecklistModel(
        checklist_type=checklist.checklist_type.value,
        indicators=[
            DeceptionIndicatorModel(
                id=ind.id,
                checklist=ind.checklist.value,
                question=ind.question,
                answer=ind.answer,
                strength=ind.strength.value,
                confidence=ind.confidence,
                evidence_ids=ind.evidence_ids,
                notes=ind.notes,
            )
            for ind in checklist.indicators
        ],
        overall_score=checklist.overall_score,
        risk_level=checklist.risk_level,
        summary=checklist.summary,
        completed_at=checklist.completed_at.isoformat() if checklist.completed_at else None,
    )


def _deception_to_response(assessment) -> DeceptionAssessmentResponse:
    """Convert DeceptionAssessment to response model."""
    return DeceptionAssessmentResponse(
        id=assessment.id,
        source_type=assessment.source_type.value,
        source_id=assessment.source_id,
        source_name=assessment.source_name,
        mom_checklist=_checklist_to_model(assessment.mom_checklist),
        pop_checklist=_checklist_to_model(assessment.pop_checklist),
        moses_checklist=_checklist_to_model(assessment.moses_checklist),
        eve_checklist=_checklist_to_model(assessment.eve_checklist),
        overall_score=assessment.overall_score,
        risk_level=assessment.risk_level.value,
        confidence=assessment.confidence,
        completed_checklists=assessment.completed_checklists,
        linked_assessment_id=assessment.linked_assessment_id,
        affects_credibility=assessment.affects_credibility,
        credibility_weight=assessment.credibility_weight,
        assessed_by=assessment.assessed_by.value,
        assessor_id=assessment.assessor_id,
        summary=assessment.summary,
        red_flags=assessment.red_flags,
        created_at=assessment.created_at.isoformat(),
        updated_at=assessment.updated_at.isoformat(),
    )


# === Deception Endpoints ===


@router.post("/deception", response_model=DeceptionAssessmentResponse, status_code=201)
async def create_deception_assessment(body: DeceptionAssessmentCreate, request: Request):
    """
    Create a new deception detection assessment.

    This creates an empty assessment with all four checklists (MOM, POP, MOSES, EVE)
    ready to be filled out.
    """
    shard = _get_shard(request)

    assessment = await shard.create_deception_assessment(
        source_type=body.source_type,
        source_id=body.source_id,
        source_name=body.source_name,
        linked_assessment_id=body.linked_assessment_id,
        affects_credibility=body.affects_credibility,
        credibility_weight=body.credibility_weight,
    )

    return _deception_to_response(assessment)


@router.get("/deception", response_model=DeceptionAssessmentListResponse)
async def list_deception_assessments(
    request: Request,
    source_type: Optional[SourceType] = Query(None),
    source_id: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    risk_level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List deception assessments with optional filtering."""
    shard = _get_shard(request)

    assessments = await shard.list_deception_assessments(
        source_type=source_type,
        source_id=source_id,
        min_score=min_score,
        risk_level=risk_level,
        limit=limit,
        offset=offset,
    )
    total = await shard.get_deception_count()

    return DeceptionAssessmentListResponse(
        assessments=[_deception_to_response(a) for a in assessments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/deception/high-risk", response_model=DeceptionAssessmentListResponse)
async def list_high_risk_sources(
    request: Request,
    min_score: int = Query(60, ge=0, le=100),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List sources with high deception risk (score >= min_score)."""
    shard = _get_shard(request)

    assessments = await shard.list_deception_assessments(
        min_score=min_score,
        limit=limit,
        offset=offset,
    )
    total = await shard.get_deception_count(min_score=min_score)

    return DeceptionAssessmentListResponse(
        assessments=[_deception_to_response(a) for a in assessments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/deception/count", response_model=CountResponse)
async def get_deception_count(
    request: Request,
    risk_level: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
):
    """Get count of deception assessments."""
    shard = _get_shard(request)
    count = await shard.get_deception_count(risk_level=risk_level, min_score=min_score)
    return CountResponse(count=count)


@router.get("/deception/indicators/{checklist_type}", response_model=List[StandardIndicatorResponse])
async def get_checklist_indicators(checklist_type: str, request: Request):
    """
    Get the standard indicators for a checklist type.

    checklist_type: 'mom', 'pop', 'moses', or 'eve'
    """
    from .models import get_indicators_for_checklist, DeceptionChecklistType

    try:
        ct = DeceptionChecklistType(checklist_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid checklist type: {checklist_type}. Must be one of: mom, pop, moses, eve"
        )

    indicators = get_indicators_for_checklist(ct)

    return [
        StandardIndicatorResponse(
            id=ind.id,
            checklist=ind.checklist.value,
            question=ind.question,
            guidance=ind.guidance,
            category=ind.category,
        )
        for ind in indicators
    ]


@router.get("/deception/{assessment_id}", response_model=DeceptionAssessmentResponse)
async def get_deception_assessment(assessment_id: str, request: Request):
    """Get a deception assessment by ID."""
    shard = _get_shard(request)
    assessment = await shard.get_deception_assessment(assessment_id)

    if not assessment:
        raise HTTPException(status_code=404, detail=f"Deception assessment {assessment_id} not found")

    return _deception_to_response(assessment)


@router.put("/deception/{assessment_id}", response_model=DeceptionAssessmentResponse)
async def update_deception_assessment(
    assessment_id: str,
    body: DeceptionAssessmentUpdate,
    request: Request,
):
    """Update a deception assessment metadata."""
    shard = _get_shard(request)

    assessment = await shard.update_deception_assessment(
        assessment_id=assessment_id,
        source_name=body.source_name,
        summary=body.summary,
        red_flags=body.red_flags,
        affects_credibility=body.affects_credibility,
        credibility_weight=body.credibility_weight,
    )

    if not assessment:
        raise HTTPException(status_code=404, detail=f"Deception assessment {assessment_id} not found")

    return _deception_to_response(assessment)


@router.delete("/deception/{assessment_id}", status_code=204)
async def delete_deception_assessment(assessment_id: str, request: Request):
    """Delete a deception assessment."""
    shard = _get_shard(request)
    success = await shard.delete_deception_assessment(assessment_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Deception assessment {assessment_id} not found")


@router.put("/deception/{assessment_id}/checklist/{checklist_type}", response_model=DeceptionAssessmentResponse)
async def update_checklist(
    assessment_id: str,
    checklist_type: str,
    body: DeceptionChecklistUpdate,
    request: Request,
):
    """
    Update a specific checklist within a deception assessment.

    checklist_type: 'mom', 'pop', 'moses', or 'eve'
    """
    try:
        ct = DeceptionChecklistType(checklist_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid checklist type: {checklist_type}. Must be one of: mom, pop, moses, eve"
        )

    shard = _get_shard(request)

    assessment = await shard.update_deception_checklist(
        assessment_id=assessment_id,
        checklist_type=ct,
        indicators=body.indicators,
        summary=body.summary,
    )

    if not assessment:
        raise HTTPException(status_code=404, detail=f"Deception assessment {assessment_id} not found")

    return _deception_to_response(assessment)


@router.post("/deception/{assessment_id}/recalculate", response_model=DeceptionAssessmentResponse)
async def recalculate_deception_score(assessment_id: str, request: Request):
    """Recalculate overall deception score from completed checklists."""
    shard = _get_shard(request)

    assessment = await shard.recalculate_deception_score(assessment_id)

    if not assessment:
        raise HTTPException(status_code=404, detail=f"Deception assessment {assessment_id} not found")

    return _deception_to_response(assessment)


@router.post("/deception/{assessment_id}/checklist/{checklist_type}/llm", response_model=LLMChecklistResponse)
async def analyze_checklist_with_llm(
    assessment_id: str,
    checklist_type: str,
    body: LLMChecklistRequest,
    request: Request,
):
    """
    Use LLM to analyze and populate a checklist.

    The LLM will assess each indicator based on available information
    about the source.
    """
    try:
        ct = DeceptionChecklistType(checklist_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid checklist type: {checklist_type}. Must be one of: mom, pop, moses, eve"
        )

    shard = _get_shard(request)

    # First check if assessment exists
    assessment = await shard.get_deception_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail=f"Deception assessment {assessment_id} not found")

    # Check if LLM is available
    if not shard._llm or not shard._llm.is_available():
        raise HTTPException(
            status_code=503,
            detail="LLM service is not available. Please configure LLM in Dashboard > LLM Config."
        )

    result = await shard.analyze_checklist_with_llm(
        assessment_id=assessment_id,
        checklist_type=ct,
        context=body.context,
    )

    if not result:
        raise HTTPException(
            status_code=500,
            detail="LLM analysis failed. Check server logs for details."
        )

    return LLMChecklistResponse(
        checklist=_checklist_to_model(result["checklist"]),
        reasoning=result["reasoning"],
        confidence=result["confidence"],
        processing_time_ms=result["processing_time_ms"],
    )


@router.get("/deception/source/{source_type}/{source_id}", response_model=List[DeceptionAssessmentResponse])
async def get_source_deception_history(
    source_type: SourceType,
    source_id: str,
    request: Request,
):
    """Get deception assessment history for a source."""
    shard = _get_shard(request)

    assessments = await shard.list_deception_assessments(
        source_type=source_type,
        source_id=source_id,
        limit=100,
        offset=0,
    )

    return [_deception_to_response(a) for a in assessments]


# === Catch-all Routes (must be last) ===


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


# === AI Junior Analyst ===


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""

    target_id: str
    context: Dict[str, Any] = {}
    depth: str = "quick"
    session_id: Optional[str] = None
    message: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for credibility analysis.

    Provides streaming AI analysis of credibility assessments and source reliability.
    """
    shard = _get_shard(request)
    frame = shard.frame
    if not frame or not getattr(frame, "ai_analyst", None):
        raise HTTPException(status_code=503, detail="AI Analyst service not available")

    from arkham_frame.services import AnalysisRequest, AnalysisDepth, AnalystMessage

    # Map depth string to enum
    depth_map = {
        "quick": AnalysisDepth.QUICK,
        "standard": AnalysisDepth.DETAILED,
        "detailed": AnalysisDepth.DETAILED,
        "deep": AnalysisDepth.DETAILED,
    }
    depth = depth_map.get(body.depth, AnalysisDepth.QUICK)

    # Build conversation history
    history = None
    if body.conversation_history:
        history = [
            AnalystMessage(role=m["role"], content=m["content"])
            for m in body.conversation_history
        ]

    # Create analysis request
    analysis_request = AnalysisRequest(
        shard="credibility",
        target_id=body.target_id,
        context=body.context,
        depth=depth,
        session_id=body.session_id,
        message=body.message,
        conversation_history=history,
    )

    # Return streaming response
    return StreamingResponse(
        frame.ai_analyst.stream_analyze(analysis_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
