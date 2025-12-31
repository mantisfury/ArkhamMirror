"""ACH Shard API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ach", tags=["ach"])

# These get set by the shard on initialization
_matrix_manager = None
_scorer = None
_evidence_analyzer = None
_exporter = None
_event_bus = None
_llm_service = None
_llm_integration = None
_corpus_service = None


def init_api(
    matrix_manager,
    scorer,
    evidence_analyzer,
    exporter,
    event_bus,
    llm_service,
    corpus_service=None,
):
    """Initialize API with shard dependencies."""
    global _matrix_manager, _scorer, _evidence_analyzer, _exporter, _event_bus, _llm_service, _llm_integration, _corpus_service
    _matrix_manager = matrix_manager
    _scorer = scorer
    _evidence_analyzer = evidence_analyzer
    _exporter = exporter
    _event_bus = event_bus
    _llm_service = llm_service
    _corpus_service = corpus_service

    # Initialize LLM integration if service available
    if llm_service:
        from .llm import ACHLLMIntegration
        _llm_integration = ACHLLMIntegration(llm_service)
        logger.info("ACH LLM integration initialized")

    if corpus_service:
        logger.info("ACH Corpus search service initialized")




async def _get_corpus_context_for_matrix(matrix, limit: int = 10) -> list[dict]:
    """Get relevant corpus chunks for matrix hypotheses."""
    if not _corpus_service or not matrix.linked_document_ids:
        return []

    all_chunks = []

    for hypothesis in matrix.hypotheses[:5]:  # Limit hypotheses
        search_text = f"{hypothesis.title} {hypothesis.description}"
        try:
            results = await _corpus_service.vectors.search_text(
                collection="arkham_chunks",
                text=search_text,
                limit=3,
                filter={"document_id": {"in": matrix.linked_document_ids}},
                score_threshold=0.6,
            )
            for r in results:
                all_chunks.append({
                    "text": r.get("payload", {}).get("text", "")[:500],
                    "document_name": r.get("payload", {}).get("filename", "Unknown"),
                    "page_number": r.get("payload", {}).get("page_number"),
                    "similarity_score": r.get("score", 0),
                })
        except Exception as e:
            logger.warning(f"Corpus context fetch failed: {e}")

    # Dedupe and limit
    seen = set()
    unique = []
    for c in sorted(all_chunks, key=lambda x: x["similarity_score"], reverse=True):
        key = c["text"][:100]
        if key not in seen:
            seen.add(key)
            unique.append(c)
            if len(unique) >= limit:
                break

    return unique

# --- Request/Response Models ---


class CreateMatrixRequest(BaseModel):
    title: str
    description: str = ""
    project_id: str | None = None
    created_by: str | None = None


class UpdateMatrixRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    notes: str | None = None


class AddHypothesisRequest(BaseModel):
    matrix_id: str
    title: str
    description: str = ""
    author: str | None = None


class AddEvidenceRequest(BaseModel):
    matrix_id: str
    description: str
    source: str = ""
    evidence_type: str = "fact"
    credibility: float = 1.0
    relevance: float = 1.0
    author: str | None = None
    document_ids: list[str] | None = None


class UpdateRatingRequest(BaseModel):
    matrix_id: str
    evidence_id: str
    hypothesis_id: str
    rating: str
    reasoning: str = ""
    confidence: float = 1.0
    author: str | None = None


class DevilsAdvocateRequest(BaseModel):
    matrix_id: str
    hypothesis_id: str | None = None


# --- LLM Request Models ---


class SuggestHypothesesRequest(BaseModel):
    """Request to suggest hypotheses."""
    focus_question: str
    matrix_id: str | None = None  # If provided, uses existing matrix context
    context: str = ""


class SuggestEvidenceRequest(BaseModel):
    """Request to suggest evidence."""
    matrix_id: str
    focus_question: str = ""
    use_corpus: bool = False


class SuggestRatingsRequest(BaseModel):
    """Request to suggest ratings for a specific evidence item."""
    matrix_id: str
    evidence_id: str


class AnalysisInsightsRequest(BaseModel):
    """Request for analysis insights."""
    matrix_id: str


class SuggestMilestonesRequest(BaseModel):
    """Request to suggest milestones."""
    matrix_id: str


class ExtractEvidenceRequest(BaseModel):
    """Request to extract evidence from document text."""
    matrix_id: str
    text: str
    document_id: str | None = None
    max_items: int = 5


class CorpusSearchRequest(BaseModel):
    """Request to search corpus for evidence."""
    matrix_id: str
    hypothesis_id: str
    chunk_limit: int = 30
    min_similarity: float = 0.5
    scope: dict | None = None


class AcceptCorpusEvidenceRequest(BaseModel):
    """Request to accept corpus-extracted evidence into matrix."""
    matrix_id: str
    evidence: list[dict]
    auto_rate: bool = False



class LinkDocumentsRequest(BaseModel):
    """Request to link documents to a matrix."""
    document_ids: list[str]


# --- Endpoints ---


@router.post("/matrix")
async def create_matrix(request: CreateMatrixRequest):
    """Create a new ACH matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.create_matrix(
        title=request.title,
        description=request.description,
        created_by=request.created_by,
        project_id=request.project_id,
    )

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.matrix.created",
            {
                "matrix_id": matrix.id,
                "title": matrix.title,
                "created_by": matrix.created_by,
            },
            source="ach-shard",
        )

    return {
        "matrix_id": matrix.id,
        "title": matrix.title,
        "status": matrix.status.value,
        "created_at": matrix.created_at.isoformat(),
    }


@router.get("/matrix/{matrix_id}")
async def get_matrix(matrix_id: str):
    """Get an ACH matrix by ID."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix_data = _matrix_manager.get_matrix_data(matrix_id)
    if not matrix_data:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    return matrix_data


@router.put("/matrix/{matrix_id}")
async def update_matrix(matrix_id: str, request: UpdateMatrixRequest):
    """Update an ACH matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    from .models import MatrixStatus

    # Parse status if provided
    status = None
    if request.status:
        try:
            status = MatrixStatus[request.status.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    matrix = _matrix_manager.update_matrix(
        matrix_id=matrix_id,
        title=request.title,
        description=request.description,
        status=status,
        notes=request.notes,
    )

    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.matrix.updated",
            {
                "matrix_id": matrix.id,
                "title": matrix.title,
            },
            source="ach-shard",
        )

    return {
        "matrix_id": matrix.id,
        "title": matrix.title,
        "status": matrix.status.value,
        "updated_at": matrix.updated_at.isoformat(),
    }


@router.delete("/matrix/{matrix_id}")
async def delete_matrix(matrix_id: str):
    """Delete an ACH matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    success = _matrix_manager.delete_matrix(matrix_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.matrix.deleted",
            {"matrix_id": matrix_id},
            source="ach-shard",
        )

    return {"status": "deleted", "matrix_id": matrix_id}



# --- Linked Documents Endpoints ---


@router.get("/matrix/{matrix_id}/documents")
async def get_linked_documents(matrix_id: str):
    """Get documents linked to a matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    return {
        "matrix_id": matrix_id,
        "document_ids": matrix.linked_document_ids,
        "count": len(matrix.linked_document_ids),
    }


@router.post("/matrix/{matrix_id}/documents")
async def link_documents(matrix_id: str, request: LinkDocumentsRequest):
    """Link documents to a matrix for corpus search scope."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    # Add new document IDs (avoid duplicates)
    added = []
    for doc_id in request.document_ids:
        if doc_id not in matrix.linked_document_ids:
            matrix.linked_document_ids.append(doc_id)
            added.append(doc_id)

    # Emit event
    if _event_bus and added:
        await _event_bus.emit(
            "ach.documents.linked",
            {
                "matrix_id": matrix_id,
                "document_ids": added,
            },
            source="ach-shard",
        )

    return {
        "matrix_id": matrix_id,
        "linked": added,
        "total_linked": len(matrix.linked_document_ids),
    }


@router.delete("/matrix/{matrix_id}/documents/{document_id}")
async def unlink_document(matrix_id: str, document_id: str):
    """Unlink a document from a matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    if document_id not in matrix.linked_document_ids:
        raise HTTPException(status_code=404, detail=f"Document not linked: {document_id}")

    matrix.linked_document_ids.remove(document_id)

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.documents.unlinked",
            {
                "matrix_id": matrix_id,
                "document_id": document_id,
            },
            source="ach-shard",
        )

    return {
        "matrix_id": matrix_id,
        "unlinked": document_id,
        "total_linked": len(matrix.linked_document_ids),
    }


@router.get("/matrices")
async def list_matrices(
    project_id: str | None = None,
    status: str | None = None,
):
    """List ACH matrices with optional filtering."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    from .models import MatrixStatus

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = MatrixStatus[status.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    matrices = _matrix_manager.list_matrices(
        project_id=project_id,
        status=status_filter,
    )

    return {
        "count": len(matrices),
        "matrices": [
            {
                "id": m.id,
                "title": m.title,
                "description": m.description,
                "status": m.status.value,
                "hypothesis_count": len(m.hypotheses),
                "evidence_count": len(m.evidence),
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
            }
            for m in matrices
        ],
    }


@router.get("/matrices/count")
async def get_matrices_count():
    """Get count of active matrices for badge display."""
    if not _matrix_manager:
        return {"count": 0}

    from .models import MatrixStatus

    matrices = _matrix_manager.list_matrices(status=MatrixStatus.ACTIVE)
    return {"count": len(matrices)}


@router.post("/hypothesis")
async def add_hypothesis(request: AddHypothesisRequest):
    """Add a hypothesis to a matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    hypothesis = _matrix_manager.add_hypothesis(
        matrix_id=request.matrix_id,
        title=request.title,
        description=request.description,
        author=request.author,
    )

    if not hypothesis:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.hypothesis.added",
            {
                "matrix_id": request.matrix_id,
                "hypothesis_id": hypothesis.id,
                "title": hypothesis.title,
            },
            source="ach-shard",
        )

    return {
        "hypothesis_id": hypothesis.id,
        "matrix_id": hypothesis.matrix_id,
        "title": hypothesis.title,
        "column_index": hypothesis.column_index,
    }


@router.delete("/hypothesis/{matrix_id}/{hypothesis_id}")
async def remove_hypothesis(matrix_id: str, hypothesis_id: str):
    """Remove a hypothesis from a matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    success = _matrix_manager.remove_hypothesis(matrix_id, hypothesis_id)
    if not success:
        raise HTTPException(status_code=404, detail="Matrix or hypothesis not found")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.hypothesis.removed",
            {
                "matrix_id": matrix_id,
                "hypothesis_id": hypothesis_id,
            },
            source="ach-shard",
        )

    return {"status": "removed", "hypothesis_id": hypothesis_id}


@router.post("/evidence")
async def add_evidence(request: AddEvidenceRequest):
    """Add evidence to a matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    evidence = _matrix_manager.add_evidence(
        matrix_id=request.matrix_id,
        description=request.description,
        source=request.source,
        evidence_type=request.evidence_type,
        credibility=request.credibility,
        relevance=request.relevance,
        author=request.author,
        document_ids=request.document_ids,
    )

    if not evidence:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.evidence.added",
            {
                "matrix_id": request.matrix_id,
                "evidence_id": evidence.id,
                "description": evidence.description,
            },
            source="ach-shard",
        )

    return {
        "evidence_id": evidence.id,
        "matrix_id": evidence.matrix_id,
        "description": evidence.description,
        "row_index": evidence.row_index,
    }


@router.delete("/evidence/{matrix_id}/{evidence_id}")
async def remove_evidence(matrix_id: str, evidence_id: str):
    """Remove evidence from a matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    success = _matrix_manager.remove_evidence(matrix_id, evidence_id)
    if not success:
        raise HTTPException(status_code=404, detail="Matrix or evidence not found")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.evidence.removed",
            {
                "matrix_id": matrix_id,
                "evidence_id": evidence_id,
            },
            source="ach-shard",
        )

    return {"status": "removed", "evidence_id": evidence_id}


@router.put("/rating")
async def update_rating(request: UpdateRatingRequest):
    """Update a rating in the matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    from .models import ConsistencyRating

    # Parse rating
    try:
        rating_enum = ConsistencyRating(request.rating)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid rating: {request.rating}")

    rating = _matrix_manager.set_rating(
        matrix_id=request.matrix_id,
        evidence_id=request.evidence_id,
        hypothesis_id=request.hypothesis_id,
        rating=rating_enum,
        reasoning=request.reasoning,
        confidence=request.confidence,
        author=request.author,
    )

    if not rating:
        raise HTTPException(status_code=404, detail="Matrix, evidence, or hypothesis not found")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.rating.updated",
            {
                "matrix_id": request.matrix_id,
                "evidence_id": request.evidence_id,
                "hypothesis_id": request.hypothesis_id,
                "rating": request.rating,
            },
            source="ach-shard",
        )

    return {
        "matrix_id": rating.matrix_id,
        "evidence_id": rating.evidence_id,
        "hypothesis_id": rating.hypothesis_id,
        "rating": rating.rating.value,
        "confidence": rating.confidence,
    }


@router.post("/score")
async def calculate_scores(matrix_id: str = Query(...)):
    """Calculate or recalculate scores for a matrix."""
    if not _matrix_manager or not _scorer:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    scores = _scorer.calculate_scores(matrix)

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "ach.score.calculated",
            {
                "matrix_id": matrix_id,
                "hypothesis_count": len(scores),
            },
            source="ach-shard",
        )

    return {
        "matrix_id": matrix_id,
        "scores": [
            {
                "hypothesis_id": s.hypothesis_id,
                "hypothesis_title": matrix.get_hypothesis(s.hypothesis_id).title,
                "rank": s.rank,
                "inconsistency_count": s.inconsistency_count,
                "weighted_score": s.weighted_score,
                "normalized_score": s.normalized_score,
                "evidence_count": s.evidence_count,
            }
            for s in scores
        ],
    }


@router.post("/devils-advocate")
async def devils_advocate(request: DevilsAdvocateRequest):
    """
    Challenge the leading hypothesis using devil's advocate mode.

    Requires LLM service to be available.
    """
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    if not _llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    # Determine which hypothesis to challenge
    if request.hypothesis_id:
        hypothesis = matrix.get_hypothesis(request.hypothesis_id)
        if not hypothesis:
            raise HTTPException(status_code=404, detail=f"Hypothesis not found: {request.hypothesis_id}")
    else:
        # Challenge the leading hypothesis
        hypothesis = matrix.leading_hypothesis
        if not hypothesis:
            raise HTTPException(status_code=400, detail="No scored hypothesis to challenge")

    # Build context for LLM
    context_parts = [
        f"Matrix: {matrix.title}",
        f"\nHypothesis to challenge: {hypothesis.title}",
        f"Description: {hypothesis.description}",
        "\nEvidence:",
    ]

    for evidence in matrix.evidence:
        rating = matrix.get_rating(evidence.id, hypothesis.id)
        if rating:
            context_parts.append(
                f"- [{rating.rating.value}] {evidence.description}"
            )

    context = "\n".join(context_parts)

    # Generate devil's advocate challenge
    prompt = f"""You are a devil's advocate analyst. Your job is to challenge the following hypothesis and identify weaknesses.

{context}

Provide:
1. A critical challenge to this hypothesis
2. Alternative interpretations of the evidence
3. Weaknesses in the hypothesis
4. Evidence gaps that should be investigated
5. Recommended investigations

Be critical but fair. Focus on finding flaws and alternative explanations."""

    try:
        response = await _llm_service.generate(prompt)

        from .models import DevilsAdvocateChallenge

        challenge = DevilsAdvocateChallenge(
            matrix_id=matrix.id,
            hypothesis_id=hypothesis.id,
            challenge_text=response.get("text", ""),
            alternative_interpretation="See challenge text",
            model_used=response.get("model", "unknown"),
        )

        return {
            "matrix_id": matrix.id,
            "hypothesis_id": hypothesis.id,
            "hypothesis_title": hypothesis.title,
            "challenge": challenge.challenge_text,
            "model": challenge.model_used,
        }

    except Exception as e:
        logger.error(f"Devil's advocate generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")


@router.get("/export/{matrix_id}")
async def export_matrix(
    matrix_id: str,
    format: str = Query("json", description="Export format: json, csv, html, pdf, markdown"),
):
    """Export a matrix in the specified format."""
    from fastapi.responses import Response

    if not _matrix_manager or not _exporter:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    export = _exporter.export(matrix, format=format)

    # For PDF, return binary response directly for download
    if format.lower() == "pdf":
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in matrix.title[:30])
        filename = f"ACH_Report_{safe_title}_{matrix_id[:8]}.pdf"
        return Response(
            content=export.content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    # Determine content type for other formats
    content_types = {
        "json": "application/json",
        "csv": "text/csv",
        "html": "text/html",
        "markdown": "text/markdown",
        "md": "text/markdown",
    }

    content_type = content_types.get(format.lower(), "text/plain")

    return {
        "matrix_id": matrix_id,
        "format": export.format,
        "content_type": content_type,
        "content": export.content,
        "generated_at": export.generated_at.isoformat(),
    }


@router.get("/diagnosticity/{matrix_id}")
async def get_diagnosticity(matrix_id: str):
    """Get diagnosticity report for a matrix."""
    if not _matrix_manager or not _scorer:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    report = _scorer.get_diagnosticity_report(matrix)
    return report


@router.get("/sensitivity/{matrix_id}")
async def get_sensitivity(matrix_id: str):
    """Get sensitivity analysis for a matrix."""
    if not _matrix_manager or not _scorer:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    report = _scorer.get_sensitivity_analysis(matrix)
    return report


@router.get("/evidence-gaps/{matrix_id}")
async def get_evidence_gaps(matrix_id: str):
    """Identify evidence gaps in a matrix."""
    if not _matrix_manager or not _evidence_analyzer:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    gaps = _evidence_analyzer.identify_gaps(matrix)
    return gaps


# =============================================================================
# LLM-Powered Endpoints
# =============================================================================


@router.get("/ai/status")
async def get_ai_status():
    """Check if AI features are available."""
    return {
        "available": _llm_integration is not None and _llm_integration.is_available,
        "llm_service": _llm_service is not None,
    }


@router.post("/ai/hypotheses")
async def suggest_hypotheses(request: SuggestHypothesesRequest):
    """
    Generate hypothesis suggestions using AI.

    Requires LLM service to be available.
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    existing_hypotheses = []
    if request.matrix_id:
        matrix = _matrix_manager.get_matrix(request.matrix_id)
        if matrix:
            existing_hypotheses = matrix.hypotheses

    try:
        suggestions = await _llm_integration.suggest_hypotheses(
            focus_question=request.focus_question,
            existing_hypotheses=existing_hypotheses,
            context=request.context,
        )

        return {
            "suggestions": [
                {
                    "title": s.title,
                    "description": s.description,
                }
                for s in suggestions
            ],
            "count": len(suggestions),
        }

    except Exception as e:
        logger.error(f"Hypothesis suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/ai/evidence")
async def suggest_evidence(request: SuggestEvidenceRequest):
    """
    Generate evidence suggestions using AI.

    Suggests diagnostic evidence that helps distinguish between hypotheses.
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    if len(matrix.hypotheses) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 hypotheses required for evidence suggestion"
        )

    # Use matrix title as focus question if not provided
    focus_question = request.focus_question or matrix.title

    try:
        # Get corpus context if requested and available
        corpus_chunks = None
        if request.use_corpus and _corpus_service and matrix.linked_document_ids:
            corpus_chunks = await _get_corpus_context_for_matrix(matrix, limit=10)

        # Use corpus-aware method if we have chunks, otherwise use standard method
        if corpus_chunks:
            suggestions = await _llm_integration.suggest_evidence_with_corpus(
                focus_question=focus_question,
                hypotheses=matrix.hypotheses,
                existing_evidence=matrix.evidence,
                corpus_chunks=corpus_chunks,
            )
        else:
            suggestions = await _llm_integration.suggest_evidence(
                focus_question=focus_question,
                hypotheses=matrix.hypotheses,
                existing_evidence=matrix.evidence,
            )

        return {
            "matrix_id": request.matrix_id,
            "suggestions": [
                {
                    "description": s.description,
                    "evidence_type": s.evidence_type.value,
                    "source": s.source,
                }
                for s in suggestions
            ],
            "count": len(suggestions),
            "used_corpus": corpus_chunks is not None and len(corpus_chunks) > 0,
        }

    except Exception as e:
        logger.error(f"Evidence suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/ai/ratings")
async def suggest_ratings(request: SuggestRatingsRequest):
    """
    Generate rating suggestions for evidence against all hypotheses.

    Suggests consistency ratings (++, +, N, -, --) with explanations.
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    evidence = matrix.get_evidence(request.evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"Evidence not found: {request.evidence_id}")

    if not matrix.hypotheses:
        raise HTTPException(status_code=400, detail="No hypotheses in matrix")

    try:
        suggestions = await _llm_integration.suggest_ratings(
            evidence=evidence,
            hypotheses=matrix.hypotheses,
        )

        return {
            "matrix_id": request.matrix_id,
            "evidence_id": request.evidence_id,
            "suggestions": [
                {
                    "hypothesis_id": s.hypothesis_id,
                    "hypothesis_label": s.hypothesis_label,
                    "rating": s.rating.value,
                    "explanation": s.explanation,
                }
                for s in suggestions
            ],
            "count": len(suggestions),
        }

    except Exception as e:
        logger.error(f"Rating suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/ai/insights")
async def get_analysis_insights(request: AnalysisInsightsRequest):
    """
    Get comprehensive AI-generated analysis insights.

    Provides analysis of the matrix state including:
    - Leading hypothesis assessment
    - Key distinguishing evidence
    - Evidence gaps
    - Cognitive bias warnings
    - Recommendations
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    # Calculate scores first
    if _scorer:
        _scorer.calculate_scores(matrix)

    try:
        insights = await _llm_integration.get_analysis_insights(matrix)

        return {
            "matrix_id": request.matrix_id,
            "insights": insights.full_text,
            "leading_hypothesis": insights.leading_hypothesis,
            "key_evidence": insights.key_evidence,
            "evidence_gaps": insights.evidence_gaps,
            "cognitive_biases": insights.cognitive_biases,
            "recommendations": insights.recommendations,
        }

    except Exception as e:
        logger.error(f"Analysis insights failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/ai/milestones")
async def suggest_milestones(request: SuggestMilestonesRequest):
    """
    Suggest future indicators/milestones for hypotheses.

    Generates observable events that would confirm or refute hypotheses.
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    if len(matrix.hypotheses) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 hypotheses required for milestone suggestion"
        )

    try:
        suggestions = await _llm_integration.suggest_milestones(matrix)

        return {
            "matrix_id": request.matrix_id,
            "suggestions": [
                {
                    "hypothesis_id": s.hypothesis_id,
                    "hypothesis_label": s.hypothesis_label,
                    "description": s.description,
                }
                for s in suggestions
            ],
            "count": len(suggestions),
        }

    except Exception as e:
        logger.error(f"Milestone suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/ai/devils-advocate")
async def devils_advocate_full(request: DevilsAdvocateRequest):
    """
    Generate comprehensive devil's advocate challenges.

    Enhanced version that provides structured challenges including:
    - Counter-arguments
    - Disproof evidence
    - Alternative angles

    For each hypothesis or just the leading/specified hypothesis.
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    try:
        challenge = await _llm_integration.generate_full_challenge(
            matrix=matrix,
            hypothesis_id=request.hypothesis_id,
        )

        if not challenge:
            raise HTTPException(status_code=400, detail="Could not generate challenge")

        hypothesis = matrix.get_hypothesis(challenge.hypothesis_id)

        return {
            "matrix_id": matrix.id,
            "hypothesis_id": challenge.hypothesis_id,
            "hypothesis_title": hypothesis.title if hypothesis else "Unknown",
            "challenge_text": challenge.challenge_text,
            "alternative_interpretation": challenge.alternative_interpretation,
            "weaknesses": challenge.weaknesses_identified,
            "evidence_gaps": challenge.evidence_gaps,
            "recommended_investigations": challenge.recommended_investigations,
            "model": challenge.model_used,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Devil's advocate generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/ai/extract-evidence")
async def extract_evidence_from_document(request: ExtractEvidenceRequest):
    """
    Extract potential evidence from document text using AI.

    Analyzes document text and identifies facts, claims, and other
    evidence relevant to the hypotheses in the matrix.
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    if not matrix.hypotheses:
        raise HTTPException(status_code=400, detail="No hypotheses in matrix")

    try:
        suggestions = await _llm_integration.extract_evidence_from_text(
            text=request.text,
            hypotheses=matrix.hypotheses,
            max_items=request.max_items,
        )

        return {
            "matrix_id": request.matrix_id,
            "document_id": request.document_id,
            "suggestions": [
                {
                    "description": s.description,
                    "evidence_type": s.evidence_type.value,
                    "source": request.document_id or "extracted",
                }
                for s in suggestions
            ],
            "count": len(suggestions),
        }

    except Exception as e:
        logger.error(f"Evidence extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


# =============================================================================
# Corpus Search Endpoints
# =============================================================================


@router.get("/ai/corpus/status")
async def get_corpus_status():
    """Check if corpus search is available."""
    return {
        "available": _corpus_service is not None and _corpus_service.is_available,
        "vectors_service": _corpus_service is not None and _corpus_service.vectors is not None,
        "llm_service": _corpus_service is not None and _corpus_service.llm is not None,
    }


@router.post("/ai/corpus-search")
async def search_corpus_for_evidence(request: CorpusSearchRequest):
    """
    Search document corpus for evidence relevant to a hypothesis.

    Uses vector search to find relevant document chunks, then
    uses LLM to classify and extract evidence quotes.
    """
    if not _corpus_service or not _corpus_service.is_available:
        raise HTTPException(status_code=503, detail="Corpus search not available")

    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    hypothesis = matrix.get_hypothesis(request.hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail=f"Hypothesis not found: {request.hypothesis_id}")

    from .models import SearchScope, CorpusSearchConfig
    scope = None
    if request.scope:
        scope = SearchScope(
            project_id=request.scope.get("project_id"),
            document_ids=request.scope.get("document_ids"),
        )

    config = CorpusSearchConfig(
        chunk_limit=request.chunk_limit,
        min_similarity=request.min_similarity,
    )

    try:
        search_text = f"{hypothesis.title} {hypothesis.description}"
        results = await _corpus_service.search_for_evidence(
            hypothesis_text=search_text,
            hypothesis_id=hypothesis.id,
            scope=scope,
            config=config,
        )

        results = await _corpus_service.check_duplicates(matrix, results)

        return {
            "matrix_id": request.matrix_id,
            "hypothesis_id": request.hypothesis_id,
            "hypothesis_title": hypothesis.title,
            "results": [
                {
                    "quote": r.quote,
                    "source_document_id": r.source_document_id,
                    "source_document_name": r.source_document_name,
                    "source_chunk_id": r.source_chunk_id,
                    "page_number": r.page_number,
                    "relevance": r.relevance.value,
                    "explanation": r.explanation,
                    "similarity_score": r.similarity_score,
                    "verified": r.verified,
                    "possible_duplicate": r.possible_duplicate,
                }
                for r in results
            ],
            "count": len(results),
        }

    except Exception as e:
        logger.error(f"Corpus search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Corpus search failed: {str(e)}")


@router.post("/ai/corpus-search-all")
async def search_corpus_all_hypotheses(
    matrix_id: str = Query(...),
    chunk_limit: int = Query(20, description="Chunks per hypothesis"),
    min_similarity: float = Query(0.5, description="Minimum similarity threshold"),
):
    """Search corpus for evidence relevant to all hypotheses in a matrix."""
    if not _corpus_service or not _corpus_service.is_available:
        raise HTTPException(status_code=503, detail="Corpus search not available")

    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {matrix_id}")

    if not matrix.hypotheses:
        raise HTTPException(status_code=400, detail="No hypotheses in matrix")

    from .models import CorpusSearchConfig
    config = CorpusSearchConfig(chunk_limit=chunk_limit, min_similarity=min_similarity)

    try:
        results = await _corpus_service.search_all_hypotheses(matrix=matrix, config=config)

        formatted = {}
        for hyp_id, evidence_list in results.items():
            hyp = matrix.get_hypothesis(hyp_id)
            formatted[hyp_id] = {
                "hypothesis_title": hyp.title if hyp else "Unknown",
                "results": [
                    {
                        "quote": r.quote,
                        "source_document_id": r.source_document_id,
                        "source_document_name": r.source_document_name,
                        "relevance": r.relevance.value,
                        "explanation": r.explanation,
                        "similarity_score": r.similarity_score,
                        "verified": r.verified,
                    }
                    for r in evidence_list
                ],
                "count": len(evidence_list),
            }

        return {
            "matrix_id": matrix_id,
            "by_hypothesis": formatted,
            "total_results": sum(len(v) for v in results.values()),
        }

    except Exception as e:
        logger.error(f"Corpus search all failed: {e}")
        raise HTTPException(status_code=500, detail=f"Corpus search failed: {str(e)}")


@router.post("/ai/accept-corpus-evidence")
async def accept_corpus_evidence(request: AcceptCorpusEvidenceRequest):
    """Accept extracted corpus evidence into the matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    added_ids = []

    for item in request.evidence:
        evidence = _matrix_manager.add_evidence(
            matrix_id=request.matrix_id,
            description=item.get("quote", ""),
            source=item.get("source_document_name", "corpus"),
            evidence_type="document",
            credibility=1.0,
            relevance=1.0,
            author="corpus-extraction",
            document_ids=[item.get("source_document_id")] if item.get("source_document_id") else None,
        )

        if evidence:
            added_ids.append(evidence.id)

            if request.auto_rate and item.get("hypothesis_id"):
                from .models import ConsistencyRating

                relevance = item.get("relevance", "neutral")
                rating_map = {
                    "supports": ConsistencyRating.CONSISTENT,
                    "contradicts": ConsistencyRating.INCONSISTENT,
                    "neutral": ConsistencyRating.NEUTRAL,
                    "ambiguous": ConsistencyRating.NEUTRAL,
                }
                rating = rating_map.get(relevance, ConsistencyRating.NEUTRAL)

                _matrix_manager.set_rating(
                    matrix_id=request.matrix_id,
                    evidence_id=evidence.id,
                    hypothesis_id=item.get("hypothesis_id"),
                    rating=rating,
                    reasoning=item.get("explanation", "Auto-rated from corpus extraction"),
                    confidence=0.8,
                    author="corpus-extraction",
                )

    if _event_bus and added_ids:
        await _event_bus.emit(
            "ach.corpus.evidence_accepted",
            {
                "matrix_id": request.matrix_id,
                "evidence_ids": added_ids,
                "count": len(added_ids),
            },
            source="ach-shard",
        )

    return {
        "matrix_id": request.matrix_id,
        "added": len(added_ids),
        "evidence_ids": added_ids,
    }
