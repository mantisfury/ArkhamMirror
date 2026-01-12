"""ACH Shard API endpoints."""

import logging
from typing import Annotated, Any, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from .shard import ACHShard

logger = logging.getLogger(__name__)


def get_shard(request: Request) -> "ACHShard":
    """Get the ACH shard instance from app state."""
    shard = getattr(request.app.state, "ach_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="ACH shard not available")
    return shard

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
_shard = None


def init_api(
    matrix_manager,
    scorer,
    evidence_analyzer,
    exporter,
    event_bus,
    llm_service,
    corpus_service=None,
    shard=None,
):
    """Initialize API with shard dependencies."""
    global _matrix_manager, _scorer, _evidence_analyzer, _exporter, _event_bus, _llm_service, _llm_integration, _corpus_service, _shard
    _matrix_manager = matrix_manager
    _scorer = scorer
    _evidence_analyzer = evidence_analyzer
    _exporter = exporter
    _event_bus = event_bus
    _llm_service = llm_service
    _corpus_service = corpus_service
    _shard = shard

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


# --- Premortem Request Models ---


class RunPremortemRequest(BaseModel):
    """Request to run premortem analysis on a hypothesis."""
    matrix_id: str
    hypothesis_id: str


class ConvertFailureModeRequest(BaseModel):
    """Request to convert a failure mode to hypothesis/milestone."""
    premortem_id: str
    failure_mode_id: str
    convert_to: str  # "hypothesis" | "milestone"


# --- Scenario/Cone Request Models ---


class GenerateScenarioTreeRequest(BaseModel):
    """Request to generate a scenario tree."""
    matrix_id: str
    title: str
    situation_summary: str
    max_depth: int = 2


class AddScenarioBranchRequest(BaseModel):
    """Request to add branches to an existing scenario node."""
    tree_id: str
    parent_node_id: str
    situation_summary: str | None = None


class UpdateScenarioNodeRequest(BaseModel):
    """Request to update a scenario node."""
    title: str | None = None
    description: str | None = None
    probability: float | None = None
    status: str | None = None  # "active" | "occurred" | "ruled_out"
    notes: str | None = None


class ConvertScenarioRequest(BaseModel):
    """Request to convert a scenario to a hypothesis."""
    tree_id: str
    node_id: str


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

    # Ensure matrix is persisted to database before returning
    await _matrix_manager.save_matrix_async(matrix)

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

    # Ensure matrix is persisted to database
    await _matrix_manager.save_matrix_async(matrix)

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

    matrices = await _matrix_manager.list_matrices_async(
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

    matrices = await _matrix_manager.list_matrices_async(status=MatrixStatus.ACTIVE)
    return {"count": len(matrices)}


@router.get("/evidence")
async def list_all_evidence(
    limit: int = Query(100, ge=1, le=500),
):
    """
    List all evidence items across all matrices.
    Used by graph shard for cross-shard data integration.
    """
    if not _shard or not _shard._db:
        return {"items": [], "total": 0}

    try:
        rows = await _shard._db.fetch_all(
            """
            SELECT e.*, m.title as matrix_title
            FROM arkham_ach.evidence e
            JOIN arkham_ach.matrices m ON e.matrix_id = m.id
            ORDER BY e.created_at DESC
            LIMIT :limit
            """,
            {"limit": limit}
        )

        items = []
        for row in rows:
            items.append({
                "id": row["id"],
                "matrix_id": row["matrix_id"],
                "matrix_title": row["matrix_title"],
                "description": row["description"],
                "source": row["source"],
                "evidence_type": row["evidence_type"],
                "credibility": row["credibility"],
                "relevance": row["relevance"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        # Get total count
        count_row = await _shard._db.fetch_one("SELECT COUNT(*) as cnt FROM arkham_ach.evidence")
        total = count_row["cnt"] if count_row else len(items)

        return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"Failed to list evidence: {e}")
        return {"items": [], "total": 0}


@router.get("/hypotheses")
async def list_all_hypotheses(
    limit: int = Query(100, ge=1, le=500),
):
    """
    List all hypotheses across all matrices.
    Used by graph shard for cross-shard data integration.
    """
    if not _shard or not _shard._db:
        return {"items": [], "total": 0}

    try:
        rows = await _shard._db.fetch_all(
            """
            SELECT h.*, m.title as matrix_title
            FROM arkham_ach.hypotheses h
            JOIN arkham_ach.matrices m ON h.matrix_id = m.id
            ORDER BY h.created_at DESC
            LIMIT :limit
            """,
            {"limit": limit}
        )

        items = []
        for row in rows:
            items.append({
                "id": row["id"],
                "matrix_id": row["matrix_id"],
                "matrix_title": row["matrix_title"],
                "title": row["title"],
                "description": row["description"],
                "is_lead": row["is_lead"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        # Get total count
        count_row = await _shard._db.fetch_one("SELECT COUNT(*) as cnt FROM arkham_ach.hypotheses")
        total = count_row["cnt"] if count_row else len(items)

        return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"Failed to list hypotheses: {e}")
        return {"items": [], "total": 0}


@router.post("/hypothesis")
async def add_hypothesis(request: AddHypothesisRequest):
    """Add a hypothesis to a matrix."""
    if not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    # Preload matrix into cache (async) so sync add_hypothesis works
    matrix = await _matrix_manager.get_matrix_async(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    hypothesis = _matrix_manager.add_hypothesis(
        matrix_id=request.matrix_id,
        title=request.title,
        description=request.description,
        author=request.author,
    )

    if not hypothesis:
        raise HTTPException(status_code=500, detail="Failed to add hypothesis")

    # Ensure hypothesis is persisted to database
    await _matrix_manager.save_hypothesis_async(hypothesis)

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

    # Preload matrix into cache (async) so sync add_evidence works
    matrix = await _matrix_manager.get_matrix_async(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

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
        raise HTTPException(status_code=500, detail="Failed to add evidence")

    # Ensure evidence is persisted to database
    await _matrix_manager.save_evidence_async(evidence)

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

    # Preload matrix into cache (async) so sync set_rating works
    matrix = await _matrix_manager.get_matrix_async(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

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
        raise HTTPException(status_code=404, detail="Evidence or hypothesis not found")

    # Ensure rating is persisted to database
    await _matrix_manager.save_rating_async(rating)

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


# =============================================================================
# Premortem Analysis Endpoints
# =============================================================================


@router.post("/ai/premortem")
async def run_premortem(request: RunPremortemRequest):
    """
    Run premortem analysis on a hypothesis.

    Assumes the hypothesis is WRONG and generates failure modes.
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _matrix_manager or not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    hypothesis = matrix.get_hypothesis(request.hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail=f"Hypothesis not found: {request.hypothesis_id}")

    try:
        premortem = await _llm_integration.run_premortem(
            matrix=matrix,
            hypothesis_id=request.hypothesis_id,
        )

        # Save to database
        await _shard.save_premortem(premortem)

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "ach.premortem.created",
                {
                    "matrix_id": request.matrix_id,
                    "hypothesis_id": request.hypothesis_id,
                    "premortem_id": premortem.id,
                },
                source="ach-shard",
            )

        return {
            "premortem_id": premortem.id,
            "matrix_id": premortem.matrix_id,
            "hypothesis_id": premortem.hypothesis_id,
            "hypothesis_title": premortem.hypothesis_title,
            "scenario_description": premortem.scenario_description,
            "overall_vulnerability": premortem.overall_vulnerability,
            "key_risks": premortem.key_risks,
            "recommendations": premortem.recommendations,
            "failure_modes": [
                {
                    "id": fm.id,
                    "failure_type": fm.failure_type.value,
                    "description": fm.description,
                    "likelihood": fm.likelihood,
                    "early_warning_indicator": fm.early_warning_indicator,
                    "mitigation_action": fm.mitigation_action,
                }
                for fm in premortem.failure_modes
            ],
            "model_used": premortem.model_used,
            "created_at": premortem.created_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Premortem analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Premortem analysis failed: {str(e)}")


@router.get("/matrix/{matrix_id}/premortems")
async def get_premortems(matrix_id: str):
    """Get all premortems for a matrix."""
    if not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    premortems = await _shard.get_premortems(matrix_id)

    return {
        "matrix_id": matrix_id,
        "premortems": [
            {
                "id": pm.id,
                "hypothesis_id": pm.hypothesis_id,
                "hypothesis_title": pm.hypothesis_title,
                "overall_vulnerability": pm.overall_vulnerability,
                "failure_mode_count": len(pm.failure_modes),
                "key_risks": pm.key_risks,
                "recommendations": pm.recommendations,
                "created_at": pm.created_at.isoformat(),
            }
            for pm in premortems
        ],
        "count": len(premortems),
    }


@router.get("/premortem/{premortem_id}")
async def get_premortem(premortem_id: str):
    """Get a single premortem by ID."""
    if not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    premortem = await _shard.get_premortem(premortem_id)
    if not premortem:
        raise HTTPException(status_code=404, detail=f"Premortem not found: {premortem_id}")

    return {
        "id": premortem.id,
        "matrix_id": premortem.matrix_id,
        "hypothesis_id": premortem.hypothesis_id,
        "hypothesis_title": premortem.hypothesis_title,
        "scenario_description": premortem.scenario_description,
        "overall_vulnerability": premortem.overall_vulnerability,
        "key_risks": premortem.key_risks,
        "recommendations": premortem.recommendations,
        "failure_modes": [
            {
                "id": fm.id,
                "failure_type": fm.failure_type.value,
                "description": fm.description,
                "likelihood": fm.likelihood,
                "early_warning_indicator": fm.early_warning_indicator,
                "mitigation_action": fm.mitigation_action,
                "converted_to": fm.converted_to.value if fm.converted_to else None,
                "converted_id": fm.converted_id,
            }
            for fm in premortem.failure_modes
        ],
        "model_used": premortem.model_used,
        "created_at": premortem.created_at.isoformat(),
        "updated_at": premortem.updated_at.isoformat(),
    }


@router.delete("/premortem/{premortem_id}")
async def delete_premortem(premortem_id: str):
    """Delete a premortem."""
    if not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    success = await _shard.delete_premortem(premortem_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Premortem not found: {premortem_id}")

    return {"status": "deleted", "premortem_id": premortem_id}


@router.post("/premortem/convert")
async def convert_failure_mode(request: ConvertFailureModeRequest):
    """
    Convert a failure mode to a hypothesis or milestone.

    The failure mode's alternative explanation can become a new hypothesis,
    or its early warning indicator can become a milestone.
    """
    if not _shard or not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    premortem = await _shard.get_premortem(request.premortem_id)
    if not premortem:
        raise HTTPException(status_code=404, detail=f"Premortem not found: {request.premortem_id}")

    # Find the failure mode
    failure_mode = None
    for fm in premortem.failure_modes:
        if fm.id == request.failure_mode_id:
            failure_mode = fm
            break

    if not failure_mode:
        raise HTTPException(status_code=404, detail=f"Failure mode not found: {request.failure_mode_id}")

    if request.convert_to == "hypothesis":
        # Create a new hypothesis from the failure mode's alternative explanation
        hypothesis = _matrix_manager.add_hypothesis(
            matrix_id=premortem.matrix_id,
            title=f"Alternative: {failure_mode.description[:50]}...",
            description=failure_mode.description,
            author="premortem-conversion",
        )

        if hypothesis:
            # Update the failure mode with conversion info
            from .models import PremortemConversionType
            failure_mode.converted_to = PremortemConversionType.HYPOTHESIS
            failure_mode.converted_id = hypothesis.id
            await _shard.save_premortem(premortem)

            return {
                "status": "converted",
                "convert_to": "hypothesis",
                "hypothesis_id": hypothesis.id,
                "hypothesis_title": hypothesis.title,
            }

    elif request.convert_to == "milestone":
        # Return the milestone info - it would be stored in localStorage on frontend
        # since milestones currently use localStorage
        return {
            "status": "converted",
            "convert_to": "milestone",
            "milestone": {
                "hypothesis_id": premortem.hypothesis_id,
                "description": failure_mode.early_warning_indicator or failure_mode.description,
                "source": "premortem",
                "premortem_id": premortem.id,
                "failure_mode_id": failure_mode.id,
            },
        }

    raise HTTPException(status_code=400, detail=f"Invalid convert_to: {request.convert_to}")


# =============================================================================
# Cone of Plausibility / Scenario Endpoints
# =============================================================================


@router.post("/ai/scenarios")
async def generate_scenario_tree(request: GenerateScenarioTreeRequest):
    """
    Generate a cone of plausibility (scenario tree) for a matrix.

    Creates a tree of branching scenarios from the current situation.
    """
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _matrix_manager or not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    matrix = _matrix_manager.get_matrix(request.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {request.matrix_id}")

    try:
        tree = await _llm_integration.generate_scenario_tree(
            matrix=matrix,
            title=request.title,
            situation_summary=request.situation_summary,
            max_depth=request.max_depth,
        )

        # Save to database
        await _shard.save_scenario_tree(tree)

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "ach.scenarios.created",
                {
                    "matrix_id": request.matrix_id,
                    "tree_id": tree.id,
                    "scenario_count": tree.total_scenarios,
                },
                source="ach-shard",
            )

        return _format_scenario_tree(tree)

    except Exception as e:
        logger.error(f"Scenario generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scenario generation failed: {str(e)}")


@router.get("/matrix/{matrix_id}/scenarios")
async def get_scenario_trees(matrix_id: str):
    """Get all scenario trees for a matrix."""
    if not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    trees = await _shard.get_scenario_trees(matrix_id)

    return {
        "matrix_id": matrix_id,
        "trees": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "total_scenarios": t.total_scenarios,
                "active_scenarios": len(t.active_scenarios),
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in trees
        ],
        "count": len(trees),
    }


@router.get("/scenarios/{tree_id}")
async def get_scenario_tree(tree_id: str):
    """Get a single scenario tree by ID."""
    if not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    tree = await _shard.get_scenario_tree(tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail=f"Scenario tree not found: {tree_id}")

    return _format_scenario_tree(tree)


@router.delete("/scenarios/{tree_id}")
async def delete_scenario_tree(tree_id: str):
    """Delete a scenario tree."""
    if not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    success = await _shard.delete_scenario_tree(tree_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Scenario tree not found: {tree_id}")

    return {"status": "deleted", "tree_id": tree_id}


@router.post("/scenarios/branch")
async def add_scenario_branch(request: AddScenarioBranchRequest):
    """Add new scenario branches to an existing node."""
    if not _llm_integration or not _llm_integration.is_available:
        raise HTTPException(status_code=503, detail="AI features not available")

    if not _shard or not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    tree = await _shard.get_scenario_tree(request.tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail=f"Scenario tree not found: {request.tree_id}")

    parent_node = tree.get_node(request.parent_node_id)
    if not parent_node:
        raise HTTPException(status_code=404, detail=f"Parent node not found: {request.parent_node_id}")

    matrix = _matrix_manager.get_matrix(tree.matrix_id)
    if not matrix:
        raise HTTPException(status_code=404, detail=f"Matrix not found: {tree.matrix_id}")

    try:
        situation = request.situation_summary or f"{tree.situation_summary}\n\nCurrent scenario: {parent_node.title}\n{parent_node.description}"

        new_nodes = await _llm_integration.generate_scenarios(
            matrix=matrix,
            situation_summary=situation,
            parent_node=parent_node,
            depth=parent_node.depth + 1,
        )

        # Update tree_id on new nodes and add to tree
        for node in new_nodes:
            node.tree_id = tree.id
            tree.nodes.append(node)

        # Save updated tree
        await _shard.save_scenario_tree(tree)

        return {
            "tree_id": tree.id,
            "parent_node_id": parent_node.id,
            "new_nodes": [
                {
                    "id": n.id,
                    "title": n.title,
                    "description": n.description,
                    "probability": n.probability,
                    "depth": n.depth,
                }
                for n in new_nodes
            ],
            "count": len(new_nodes),
        }

    except Exception as e:
        logger.error(f"Branch generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Branch generation failed: {str(e)}")


@router.put("/scenarios/{tree_id}/nodes/{node_id}")
async def update_scenario_node(tree_id: str, node_id: str, request: UpdateScenarioNodeRequest):
    """Update a scenario node."""
    if not _shard:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    tree = await _shard.get_scenario_tree(tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail=f"Scenario tree not found: {tree_id}")

    node = tree.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

    # Update fields
    if request.title is not None:
        node.title = request.title
    if request.description is not None:
        node.description = request.description
    if request.probability is not None:
        node.probability = request.probability
    if request.status is not None:
        from .models import ScenarioStatus
        try:
            node.status = ScenarioStatus(request.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")
    if request.notes is not None:
        node.notes = request.notes

    from datetime import datetime
    node.updated_at = datetime.utcnow()

    await _shard.update_scenario_node(node)

    return {
        "tree_id": tree_id,
        "node_id": node_id,
        "updated": True,
    }


@router.post("/scenarios/convert")
async def convert_scenario_to_hypothesis(request: ConvertScenarioRequest):
    """Convert a scenario to an ACH hypothesis."""
    if not _shard or not _matrix_manager:
        raise HTTPException(status_code=503, detail="ACH service not initialized")

    tree = await _shard.get_scenario_tree(request.tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail=f"Scenario tree not found: {request.tree_id}")

    node = tree.get_node(request.node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {request.node_id}")

    # Create hypothesis from scenario
    hypothesis = _matrix_manager.add_hypothesis(
        matrix_id=tree.matrix_id,
        title=node.title,
        description=f"{node.description}\n\nProbability: {node.probability:.0%}\nTimeframe: {node.timeframe}",
        author="scenario-conversion",
    )

    if hypothesis:
        # Update scenario status
        from .models import ScenarioStatus
        node.status = ScenarioStatus.CONVERTED
        node.converted_hypothesis_id = hypothesis.id
        await _shard.update_scenario_node(node)

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "ach.scenario.converted",
                {
                    "tree_id": tree.id,
                    "node_id": node.id,
                    "hypothesis_id": hypothesis.id,
                },
                source="ach-shard",
            )

        return {
            "status": "converted",
            "tree_id": tree.id,
            "node_id": node.id,
            "hypothesis_id": hypothesis.id,
            "hypothesis_title": hypothesis.title,
        }

    raise HTTPException(status_code=500, detail="Failed to create hypothesis")


def _format_scenario_tree(tree) -> dict:
    """Format a scenario tree for API response."""
    return {
        "id": tree.id,
        "matrix_id": tree.matrix_id,
        "title": tree.title,
        "description": tree.description,
        "situation_summary": tree.situation_summary,
        "root_node_id": tree.root_node_id,
        "total_scenarios": tree.total_scenarios,
        "nodes": [
            {
                "id": n.id,
                "parent_id": n.parent_id,
                "title": n.title,
                "description": n.description,
                "probability": n.probability,
                "timeframe": n.timeframe,
                "key_drivers": n.key_drivers,
                "trigger_conditions": n.trigger_conditions,
                "indicators": [
                    {
                        "id": ind.id,
                        "description": ind.description,
                        "is_triggered": ind.is_triggered,
                    }
                    for ind in n.indicators
                ],
                "status": n.status.value,
                "converted_hypothesis_id": n.converted_hypothesis_id,
                "depth": n.depth,
                "branch_order": n.branch_order,
                "notes": n.notes,
            }
            for n in tree.nodes
        ],
        "drivers": [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "current_state": d.current_state,
                "possible_states": d.possible_states,
            }
            for d in tree.drivers
        ],
        "model_used": tree.model_used,
        "created_at": tree.created_at.isoformat(),
        "updated_at": tree.updated_at.isoformat(),
    }


# --- AI Junior Analyst ---


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""
    target_id: str
    context: dict[str, Any] = {}
    depth: str = "quick"
    session_id: str | None = None
    message: str | None = None
    conversation_history: list[dict[str, str]] | None = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for ACH matrix analysis.

    Provides AI-powered interpretation of ACH matrices including:
    - Hypothesis ranking and likelihood assessment
    - Evidence pattern analysis
    - Inconsistency detection
    - Devil's advocate perspectives
    - Cognitive bias warnings
    """
    shard = get_shard(request)
    frame = shard._frame

    if not frame or not getattr(frame, "ai_analyst", None):
        raise HTTPException(
            status_code=503,
            detail="AI Analyst service not available"
        )

    # Build context from request
    from arkham_frame.services import AnalysisRequest, AnalysisDepth, AnalystMessage

    # Parse depth
    try:
        depth = AnalysisDepth(body.depth)
    except ValueError:
        depth = AnalysisDepth.QUICK

    # Build conversation history
    history = None
    if body.conversation_history:
        history = [
            AnalystMessage(role=msg["role"], content=msg["content"])
            for msg in body.conversation_history
        ]

    analysis_request = AnalysisRequest(
        shard="ach",
        target_id=body.target_id,
        context=body.context,
        depth=depth,
        session_id=body.session_id,
        message=body.message,
        conversation_history=history,
    )

    # Stream the response
    return StreamingResponse(
        frame.ai_analyst.stream_analyze(analysis_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
