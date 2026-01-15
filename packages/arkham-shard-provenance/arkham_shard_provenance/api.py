"""Provenance Shard API endpoints."""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from .shard import ProvenanceShard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/provenance", tags=["provenance"])

# Shard instance set on initialization
_shard: Optional["ProvenanceShard"] = None
_event_bus = None
_storage = None
_forensic_analyzer = None


def init_api(
    shard: "ProvenanceShard",
    event_bus,
    storage,
    forensic_analyzer=None,
):
    """Initialize API with shard instance."""
    global _shard, _event_bus, _storage, _forensic_analyzer
    _shard = shard
    _event_bus = event_bus
    _storage = storage
    _forensic_analyzer = forensic_analyzer
    logger.info("Provenance API initialized")


def get_shard(request: Request) -> "ProvenanceShard":
    """Get the provenance shard instance from app state."""
    shard = getattr(request.app.state, "provenance_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Provenance shard not available")
    return shard


# --- Request/Response Models ---


class ProvenanceRecordResponse(BaseModel):
    """Provenance record response."""
    id: str
    entity_type: str
    entity_id: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    imported_at: Optional[str] = None
    imported_by: Optional[str] = None
    metadata: dict = {}
    created_at: Optional[str] = None


class TransformationResponse(BaseModel):
    """Transformation response."""
    id: str
    record_id: str
    transformation_type: str
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    transformed_at: Optional[str] = None
    transformer: Optional[str] = None
    parameters: dict = {}
    metadata: dict = {}


class AuditRecordResponse(BaseModel):
    """Audit record response."""
    id: str
    record_id: str
    action: str
    actor: Optional[str] = None
    details: dict = {}
    occurred_at: Optional[str] = None


class CreateChainRequest(BaseModel):
    """Request to create a new evidence chain."""
    title: str
    description: str = ""
    project_id: Optional[str] = None
    created_by: Optional[str] = None


class UpdateChainRequest(BaseModel):
    """Request to update chain metadata."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class AddLinkRequest(BaseModel):
    """Request to add a link to a chain."""
    source_artifact_id: str
    target_artifact_id: str
    link_type: str
    confidence: float = 1.0
    metadata: dict = {}


class VerifyLinkRequest(BaseModel):
    """Request to verify a link."""
    verified_by: str
    notes: str = ""


class ChainResponse(BaseModel):
    """Evidence chain response."""
    id: str
    title: str
    description: Optional[str] = None
    chain_type: str = "evidence"
    status: str = "active"
    root_artifact_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    project_id: Optional[str] = None
    link_count: int = 0
    metadata: dict = {}


class LinkResponse(BaseModel):
    """Provenance link response."""
    id: str
    chain_id: str
    source_artifact_id: str
    target_artifact_id: str
    link_type: str
    confidence: float = 1.0
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    created_at: Optional[str] = None
    metadata: dict = {}
    # Enrichment from JOINs
    source_title: Optional[str] = None
    source_type: Optional[str] = None
    target_title: Optional[str] = None
    target_type: Optional[str] = None


class ArtifactResponse(BaseModel):
    """Tracked artifact response."""
    id: str
    artifact_type: str
    entity_id: str
    entity_table: str
    title: Optional[str] = None
    hash: Optional[str] = None
    created_at: Optional[str] = None
    metadata: dict = {}


class CreateArtifactRequest(BaseModel):
    """Request to create a new artifact."""
    artifact_type: str
    entity_id: str
    entity_table: str
    title: Optional[str] = None
    hash: Optional[str] = None
    metadata: dict = {}


class LineageNode(BaseModel):
    """Node in lineage graph."""
    id: str
    title: Optional[str] = None
    type: Optional[str] = None
    is_focus: bool = False
    depth: int = 0


class LineageEdge(BaseModel):
    """Edge in lineage graph."""
    id: str
    source: str
    target: str
    link_type: str
    confidence: float


class LineageGraphResponse(BaseModel):
    """Lineage graph response."""
    nodes: List[LineageNode]
    edges: List[LineageEdge]
    root: Optional[str] = None
    ancestor_count: int = 0
    descendant_count: int = 0


class AuditRecord(BaseModel):
    """Audit log record."""
    id: str
    chain_id: Optional[str] = None
    event_type: str
    event_source: str
    event_data: dict
    timestamp: str
    user_id: Optional[str] = None


class ChainListResponse(BaseModel):
    """Paginated list of chains."""
    items: List[ChainResponse]
    total: int
    page: int
    page_size: int


class AuditListResponse(BaseModel):
    """Paginated list of audit records."""
    items: List[AuditRecord]
    total: int
    page: int
    page_size: int


# --- Endpoints ---


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "shard": "provenance",
        "version": "0.1.0"
    }


@router.get("/count")
async def get_count(request: Request):
    """
    Get total counts for navigation badge.

    Returns:
        dict: Combined count of chains and artifacts
    """
    shard = get_shard(request)
    try:
        chains = await shard.count_chains()
        artifacts = await shard.count_artifacts()
        # Use artifacts count as primary metric, chains as secondary
        return {"count": artifacts, "chains": chains, "artifacts": artifacts}
    except Exception as e:
        logger.error(f"Error getting count: {e}")
        return {"count": 0, "chains": 0, "artifacts": 0}


# --- Evidence Chain Endpoints ---
# NOTE: These must be defined BEFORE the catch-all /{id} routes


@router.get("/chains", response_model=ChainListResponse)
async def list_chains(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[str] = None,
    chain_type: Optional[str] = None,
    status: Optional[str] = None,
):
    """
    List all evidence chains with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        project_id: Filter by project
        chain_type: Filter by chain type
        status: Filter by status

    Returns:
        Paginated list of chains
    """
    shard = get_shard(request)
    try:
        offset = (page - 1) * page_size
        chains = await shard.list_chains(
            project_id=project_id,
            chain_type=chain_type,
            status=status,
            limit=page_size,
            offset=offset,
        )
        total = await shard.count_chains()
        return {
            "items": chains,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(f"Error listing chains: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chains", response_model=ChainResponse)
async def create_chain(request_body: CreateChainRequest, request: Request):
    """
    Create a new evidence chain.

    Args:
        request_body: Chain creation request

    Returns:
        Created chain object
    """
    shard = get_shard(request)
    try:
        chain = await shard.create_chain_impl(
            title=request_body.title,
            description=request_body.description,
            project_id=request_body.project_id,
            created_by=request_body.created_by,
        )
        return chain
    except Exception as e:
        logger.error(f"Error creating chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chains/{chain_id}", response_model=ChainResponse)
async def get_chain(chain_id: str, request: Request):
    """
    Get a single chain by ID.

    Args:
        chain_id: Chain identifier

    Returns:
        Chain object
    """
    shard = get_shard(request)
    try:
        chain = await shard.get_chain_impl(chain_id)
        if not chain:
            raise HTTPException(status_code=404, detail=f"Chain not found: {chain_id}")
        return chain
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/chains/{chain_id}", response_model=ChainResponse)
async def update_chain(chain_id: str, request_body: UpdateChainRequest, request: Request):
    """
    Update chain metadata.

    Args:
        chain_id: Chain identifier
        request_body: Update request

    Returns:
        Updated chain object
    """
    shard = get_shard(request)
    try:
        chain = await shard.update_chain_impl(
            chain_id,
            title=request_body.title,
            description=request_body.description,
            status=request_body.status,
        )
        if not chain:
            raise HTTPException(status_code=404, detail=f"Chain not found: {chain_id}")
        return chain
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chains/{chain_id}")
async def delete_chain(chain_id: str, request: Request):
    """
    Delete a chain.

    Args:
        chain_id: Chain identifier

    Returns:
        Success confirmation
    """
    shard = get_shard(request)
    try:
        deleted = await shard.delete_chain_impl(chain_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Chain not found: {chain_id}")
        return {"deleted": True, "id": chain_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Link Endpoints ---


@router.post("/chains/{chain_id}/links", response_model=LinkResponse)
async def add_link(chain_id: str, request_body: AddLinkRequest, request: Request):
    """
    Add a link to an evidence chain.

    Args:
        chain_id: Chain identifier
        request_body: Link creation request

    Returns:
        Created link object
    """
    shard = get_shard(request)
    try:
        link = await shard.add_link_impl(
            chain_id=chain_id,
            source_artifact_id=request_body.source_artifact_id,
            target_artifact_id=request_body.target_artifact_id,
            link_type=request_body.link_type,
            confidence=request_body.confidence,
            metadata=request_body.metadata,
        )
        return link
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chains/{chain_id}/links", response_model=List[LinkResponse])
async def list_chain_links(chain_id: str, request: Request):
    """
    List all links in a chain.

    Args:
        chain_id: Chain identifier

    Returns:
        List of links
    """
    shard = get_shard(request)
    try:
        links = await shard.get_chain_links(chain_id)
        return links
    except Exception as e:
        logger.error(f"Error listing chain links: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/links/{link_id}")
async def delete_link(link_id: str, request: Request):
    """
    Remove a link from a chain.

    Args:
        link_id: Link identifier

    Returns:
        Success confirmation
    """
    shard = get_shard(request)
    try:
        deleted = await shard.remove_link(link_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Link not found: {link_id}")
        return {"deleted": True, "id": link_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/links/{link_id}/verify", response_model=LinkResponse)
async def verify_link_endpoint(link_id: str, request_body: VerifyLinkRequest, request: Request):
    """
    Verify a link in the chain.

    Args:
        link_id: Link identifier
        request_body: Verification request

    Returns:
        Updated link object with verification status
    """
    shard = get_shard(request)
    try:
        link = await shard.verify_link(
            link_id=link_id,
            verified_by=request_body.verified_by,
            notes=request_body.notes,
        )
        if not link:
            raise HTTPException(status_code=404, detail=f"Link not found: {link_id}")
        return link
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Lineage Endpoints ---


@router.get("/lineage/{artifact_id}", response_model=LineageGraphResponse)
async def get_lineage(
    artifact_id: str,
    request: Request,
    direction: str = Query("both", pattern="^(upstream|downstream|both)$"),
    max_depth: int = Query(5, ge=1, le=20),
):
    """
    Get lineage graph for an artifact.

    Args:
        artifact_id: Artifact identifier
        direction: Trace direction (upstream, downstream, both)
        max_depth: Maximum depth to trace

    Returns:
        Lineage graph with nodes and edges
    """
    shard = get_shard(request)
    try:
        lineage = await shard.get_lineage_impl(artifact_id)
        return lineage
    except Exception as e:
        logger.error(f"Error getting lineage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineage/{artifact_id}/upstream", response_model=List[ArtifactResponse])
async def get_upstream(artifact_id: str, request: Request):
    """
    Get upstream dependencies for an artifact.

    Args:
        artifact_id: Artifact identifier

    Returns:
        List of upstream artifacts
    """
    shard = get_shard(request)
    try:
        lineage = await shard.get_lineage_impl(artifact_id)
        # Filter to only ancestors (negative depth)
        upstream = [n for n in lineage.get("nodes", []) if n.get("depth", 0) < 0]
        # Convert to artifact responses
        artifacts = []
        for node in upstream:
            artifact = await shard.get_artifact(node["id"])
            if artifact:
                artifacts.append(artifact)
        return artifacts
    except Exception as e:
        logger.error(f"Error getting upstream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineage/{artifact_id}/downstream", response_model=List[ArtifactResponse])
async def get_downstream(artifact_id: str, request: Request):
    """
    Get downstream dependents for an artifact.

    Args:
        artifact_id: Artifact identifier

    Returns:
        List of downstream artifacts
    """
    shard = get_shard(request)
    try:
        lineage = await shard.get_lineage_impl(artifact_id)
        # Filter to only descendants (positive depth)
        downstream = [n for n in lineage.get("nodes", []) if n.get("depth", 0) > 0]
        # Convert to artifact responses
        artifacts = []
        for node in downstream:
            artifact = await shard.get_artifact(node["id"])
            if artifact:
                artifacts.append(artifact)
        return artifacts
    except Exception as e:
        logger.error(f"Error getting downstream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Audit Endpoints ---


@router.get("/audit", response_model=AuditListResponse)
async def list_audit_records(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    chain_id: Optional[str] = None,
    event_type: Optional[str] = None,
    event_source: Optional[str] = None,
):
    """
    List audit log records with filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        chain_id: Filter by chain
        event_type: Filter by event type
        event_source: Filter by event source

    Returns:
        Paginated list of audit records
    """
    shard = get_shard(request)
    try:
        offset = (page - 1) * page_size
        items, total = await shard.list_audit_records(
            chain_id=chain_id,
            event_type=event_type,
            event_source=event_source,
            limit=page_size,
            offset=offset,
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(f"Error listing audit records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/{chain_id}", response_model=List[AuditRecord])
async def get_chain_audit(chain_id: str, request: Request):
    """
    Get complete audit trail for a chain.

    Args:
        chain_id: Chain identifier

    Returns:
        List of audit records for the chain
    """
    shard = get_shard(request)
    try:
        records = await shard.get_chain_audit_records(chain_id)
        return records
    except Exception as e:
        logger.error(f"Error getting chain audit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit/export")
async def export_audit(
    request: Request,
    chain_id: Optional[str] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
):
    """
    Export audit trail to file.

    Args:
        chain_id: Optional chain ID to filter (None = all)
        format: Export format (json, csv)

    Returns:
        Export file content as download
    """
    shard = get_shard(request)

    if not _storage:
        raise HTTPException(
            status_code=503,
            detail="Storage service unavailable - export disabled"
        )

    try:
        export_data = await shard.export_audit_records(chain_id=chain_id, export_format=format)

        if format == "json":
            import json
            content = json.dumps(export_data, indent=2)
            media_type = "application/json"
            filename = f"audit_export_{chain_id or 'all'}.json"
        else:  # csv
            import csv
            import io
            output = io.StringIO()
            if export_data["records"]:
                # Collect all possible field names from all records
                all_fields = set()
                for record in export_data["records"]:
                    all_fields.update(record.keys())
                # Sort fields for consistent ordering (base fields first, data_ fields after)
                base_fields = ["id", "chain_id", "event_type", "event_source", "timestamp", "user_id"]
                data_fields = sorted([f for f in all_fields if f.startswith("data_")])
                fieldnames = [f for f in base_fields if f in all_fields] + data_fields

                writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(export_data["records"])
            content = output.getvalue()
            media_type = "text/csv"
            filename = f"audit_export_{chain_id or 'all'}.csv"

        from fastapi.responses import Response
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting audit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Verification Endpoints ---


@router.post("/chains/{chain_id}/verify")
async def verify_chain_endpoint(chain_id: str, request: Request, verified_by: Optional[str] = None):
    """
    Verify integrity of an evidence chain.

    Args:
        chain_id: Chain identifier
        verified_by: User performing verification

    Returns:
        Verification result with status and issues
    """
    shard = get_shard(request)
    try:
        result = await shard.verify_chain_impl(chain_id, verified_by=verified_by)
        return result
    except Exception as e:
        logger.error(f"Error verifying chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Artifact Endpoints ---


@router.get("/artifacts", response_model=List[ArtifactResponse])
async def list_artifacts(
    request: Request,
    artifact_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List tracked artifacts with optional type filter.

    Args:
        artifact_type: Filter by artifact type
        limit: Maximum items to return
        offset: Items to skip

    Returns:
        List of artifacts
    """
    shard = get_shard(request)
    try:
        artifacts = await shard.list_artifacts(
            artifact_type=artifact_type,
            limit=limit,
            offset=offset,
        )
        return artifacts
    except Exception as e:
        logger.error(f"Error listing artifacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/artifacts", response_model=ArtifactResponse)
async def create_artifact(request_body: CreateArtifactRequest, request: Request):
    """
    Create a new artifact for tracking.

    Args:
        request_body: Artifact creation request

    Returns:
        Created artifact
    """
    shard = get_shard(request)
    try:
        artifact = await shard.create_artifact(
            artifact_type=request_body.artifact_type,
            entity_id=request_body.entity_id,
            entity_table=request_body.entity_table,
            title=request_body.title,
            content_hash=request_body.hash,
            metadata=request_body.metadata,
        )
        return artifact
    except Exception as e:
        logger.error(f"Error creating artifact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(artifact_id: str, request: Request):
    """
    Get artifact by ID.

    Args:
        artifact_id: Artifact identifier

    Returns:
        Artifact object
    """
    shard = get_shard(request)
    try:
        artifact = await shard.get_artifact(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")
        return artifact
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting artifact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts/entity/{entity_id}")
async def get_artifact_by_entity(entity_id: str, entity_table: str, request: Request):
    """
    Get artifact by the entity it tracks.

    Args:
        entity_id: Entity ID
        entity_table: Entity table name

    Returns:
        Artifact object if found
    """
    shard = get_shard(request)
    try:
        artifact = await shard.get_artifact_by_entity(entity_id, entity_table)
        if not artifact:
            raise HTTPException(status_code=404, detail=f"Artifact not found for {entity_table}/{entity_id}")
        return artifact
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting artifact by entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Provenance Record Endpoints ---
# NOTE: These MUST be defined LAST as they contain catch-all {id} routes


@router.get("/", response_model=List[ProvenanceRecordResponse])
async def list_records(
    request: Request,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List provenance records with optional filtering.

    Args:
        entity_type: Filter by entity type
        limit: Maximum records to return
        offset: Number of records to skip

    Returns:
        List of provenance records
    """
    shard = get_shard(request)
    try:
        records = await shard.list_records(entity_type=entity_type, limit=limit, offset=offset)
        return records
    except Exception as e:
        logger.error(f"Error listing records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_type}/{entity_id}", response_model=ProvenanceRecordResponse)
async def get_entity_record(entity_type: str, entity_id: str, request: Request):
    """
    Get provenance record for a specific entity.

    Args:
        entity_type: Type of entity
        entity_id: Entity ID

    Returns:
        Provenance record
    """
    shard = get_shard(request)
    try:
        record = await shard.get_record_for_entity(entity_type, entity_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Record not found for {entity_type}/{entity_id}")
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id}/transformations", response_model=List[TransformationResponse])
async def get_transformations(id: str, request: Request):
    """
    Get transformation history for a record.

    Args:
        id: Record ID

    Returns:
        List of transformations
    """
    shard = get_shard(request)
    try:
        transformations = await shard.get_transformations(id)
        return transformations
    except Exception as e:
        logger.error(f"Error getting transformations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id}/audit", response_model=List[AuditRecordResponse])
async def get_audit_trail(id: str, request: Request):
    """
    Get audit trail for a record.

    Args:
        id: Record ID

    Returns:
        List of audit records
    """
    shard = get_shard(request)
    try:
        audit_records = await shard.get_audit_trail(id)
        return audit_records
    except Exception as e:
        logger.error(f"Error getting audit trail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id}", response_model=ProvenanceRecordResponse)
async def get_record(id: str, request: Request):
    """
    Get a provenance record by ID.

    Args:
        id: Record ID

    Returns:
        Provenance record
    """
    shard = get_shard(request)
    try:
        record = await shard.get_record(id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Record not found: {id}")
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- AI Junior Analyst ---


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
    AI Junior Analyst endpoint for provenance analysis.

    Provides streaming AI analysis of provenance chains and source tracking.
    """
    shard = get_shard(request)
    frame = shard._frame
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
        shard="provenance",
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


# =============================================================================
# Metadata Forensics Endpoints
# =============================================================================


class ForensicScanRequest(BaseModel):
    """Request to perform forensic scan on a document."""
    doc_id: str


class ForensicCompareRequest(BaseModel):
    """Request to compare metadata between documents."""
    source_doc_id: str
    target_doc_id: str


class ForensicScanResponse(BaseModel):
    """Response from forensic scan."""
    scan: dict


class ForensicStatsResponse(BaseModel):
    """Forensic statistics response."""
    stats: dict


@router.post("/forensics/scan", response_model=ForensicScanResponse)
async def scan_forensics(
    request: Request,
    body: ForensicScanRequest,
):
    """
    Perform forensic metadata analysis on a document.

    Extracts and analyzes:
    - EXIF data from images (camera info, GPS, timestamps)
    - PDF metadata (author, creator, dates, XMP)
    - Office document metadata (author, company, revision history)

    Performs integrity analysis:
    - Timestamp consistency checks
    - Metadata stripping detection
    - Editing software detection
    - Timeline reconstruction

    Args:
        body: Request with doc_id

    Returns:
        Complete forensic analysis results
    """
    shard = get_shard(request)

    if not shard.forensic_analyzer:
        raise HTTPException(
            status_code=503,
            detail="Forensic analyzer not available"
        )

    if not shard._db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Get document metadata and file path
    doc_row = await shard._db.fetch_one(
        """SELECT id, filename, storage_id, mime_type, file_size, metadata
           FROM arkham_frame.documents WHERE id = :doc_id""",
        {"doc_id": body.doc_id}
    )

    if not doc_row:
        raise HTTPException(status_code=404, detail=f"Document {body.doc_id} not found")

    # Get storage path from storage_id or metadata
    storage_id = doc_row.get("storage_id")
    metadata = doc_row.get("metadata") or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}

    storage_path = metadata.get("storage_path")
    if not storage_id and not storage_path:
        raise HTTPException(
            status_code=400,
            detail="Document has no associated file storage"
        )

    # Read file content using storage service
    try:
        if _storage and storage_id:
            file_data = (await _storage.retrieve(storage_id))[0]
        elif storage_path:
            from pathlib import Path
            file_data = Path(storage_path).read_bytes()
        else:
            raise ValueError("No storage path available")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read file: {e}"
        )

    mime_type = doc_row.get("mime_type", "")

    # Perform forensic scan (use storage_path for file path reference)
    file_path = storage_path or storage_id
    scan_result = shard.forensic_analyzer.full_scan(
        doc_id=body.doc_id,
        file_path=file_path,
        file_data=file_data,
        mime_type=mime_type,
    )

    # Store the scan result
    await shard._store_forensic_scan(scan_result)

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "provenance.forensics.scanned",
            {
                "doc_id": body.doc_id,
                "scan_id": scan_result.id,
                "integrity_status": scan_result.integrity_status.value,
                "findings_count": len(scan_result.findings),
            },
            source="provenance-shard",
        )

    # Convert to response dict
    scan_dict = {
        "id": scan_result.id,
        "doc_id": scan_result.doc_id,
        "scan_status": scan_result.scan_status.value,
        "file_hash_md5": scan_result.file_hash_md5,
        "file_hash_sha256": scan_result.file_hash_sha256,
        "file_hash_sha512": scan_result.file_hash_sha512,
        "file_size": scan_result.file_size,
        "exif_data": {
            "make": scan_result.exif_data.make,
            "model": scan_result.exif_data.model,
            "serial_number": scan_result.exif_data.serial_number,
            "datetime_original": scan_result.exif_data.datetime_original.isoformat() if scan_result.exif_data.datetime_original else None,
            "datetime_digitized": scan_result.exif_data.datetime_digitized.isoformat() if scan_result.exif_data.datetime_digitized else None,
            "datetime_modified": scan_result.exif_data.datetime_modified.isoformat() if scan_result.exif_data.datetime_modified else None,
            "gps_latitude": scan_result.exif_data.gps_latitude,
            "gps_longitude": scan_result.exif_data.gps_longitude,
            "gps_altitude": scan_result.exif_data.gps_altitude,
            "software": scan_result.exif_data.software,
            "width": scan_result.exif_data.width,
            "height": scan_result.exif_data.height,
        } if scan_result.exif_data else None,
        "pdf_metadata": {
            "title": scan_result.pdf_metadata.title,
            "author": scan_result.pdf_metadata.author,
            "subject": scan_result.pdf_metadata.subject,
            "creator": scan_result.pdf_metadata.creator,
            "producer": scan_result.pdf_metadata.producer,
            "creation_date": scan_result.pdf_metadata.creation_date.isoformat() if scan_result.pdf_metadata.creation_date else None,
            "modification_date": scan_result.pdf_metadata.modification_date.isoformat() if scan_result.pdf_metadata.modification_date else None,
            "keywords": scan_result.pdf_metadata.keywords,
            "page_count": scan_result.pdf_metadata.page_count,
            "pdf_version": scan_result.pdf_metadata.pdf_version,
            "is_encrypted": scan_result.pdf_metadata.is_encrypted,
        } if scan_result.pdf_metadata else None,
        "office_metadata": {
            "title": scan_result.office_metadata.title,
            "author": scan_result.office_metadata.author,
            "subject": scan_result.office_metadata.subject,
            "company": scan_result.office_metadata.company,
            "manager": scan_result.office_metadata.manager,
            "created": scan_result.office_metadata.created.isoformat() if scan_result.office_metadata.created else None,
            "modified": scan_result.office_metadata.modified.isoformat() if scan_result.office_metadata.modified else None,
            "last_modified_by": scan_result.office_metadata.last_modified_by,
            "revision": scan_result.office_metadata.revision,
            "keywords": scan_result.office_metadata.keywords,
            "category": scan_result.office_metadata.category,
        } if scan_result.office_metadata else None,
        "findings": [
            {
                "finding_type": f.finding_type,
                "severity": f.severity,
                "description": f.description,
                "evidence": f.evidence,
                "confidence": f.confidence,
            }
            for f in scan_result.findings
        ],
        "integrity_status": scan_result.integrity_status.value,
        "confidence_score": scan_result.confidence_score,
        "timeline_events": [
            {
                "id": e.id,
                "doc_id": e.doc_id,
                "event_type": e.event_type,
                "event_timestamp": e.event_timestamp.isoformat() if e.event_timestamp else None,
                "event_source": e.event_source,
                "event_actor": e.event_actor,
                "event_details": e.event_details,
                "confidence": e.confidence,
                "is_estimated": e.is_estimated,
            }
            for e in scan_result.timeline_events
        ],
        "scanned_at": scan_result.scanned_at.isoformat() if scan_result.scanned_at else None,
    }

    return ForensicScanResponse(scan=scan_dict)


@router.post("/forensics/compare")
async def compare_forensics(
    request: Request,
    body: ForensicCompareRequest,
):
    """
    Compare metadata between two documents.

    Analyzes similarities and differences:
    - Hash matches (exact copies)
    - Camera/device matches
    - Author/creator matches
    - Creation date proximity

    Determines relationship type:
    - Copy: Exact hash match
    - Same source: Same device/serial number
    - Same author: Same author metadata
    - Same camera: Same camera make/model
    - Unrelated: No significant matches

    Args:
        body: Request with source and target doc IDs

    Returns:
        Comparison results with match score and relationship
    """
    shard = get_shard(request)

    if not shard.forensic_analyzer:
        raise HTTPException(
            status_code=503,
            detail="Forensic analyzer not available"
        )

    # Get existing scans for both documents
    source_scans = await shard.get_document_forensic_scans(body.source_doc_id)
    target_scans = await shard.get_document_forensic_scans(body.target_doc_id)

    if not source_scans:
        raise HTTPException(
            status_code=400,
            detail=f"No forensic scan found for source document {body.source_doc_id}. Run /forensics/scan first."
        )

    if not target_scans:
        raise HTTPException(
            status_code=400,
            detail=f"No forensic scan found for target document {body.target_doc_id}. Run /forensics/scan first."
        )

    # Use most recent scans
    source_scan = source_scans[0]
    target_scan = target_scans[0]

    # Build MetadataForensicScan objects from stored data
    from .models import (
        MetadataForensicScan, ForensicScanStatus, IntegrityStatus,
        ExifData, PdfMetadata, OfficeMetadata,
    )
    from datetime import datetime

    def build_scan_from_dict(scan_dict: dict) -> MetadataForensicScan:
        scan = MetadataForensicScan(
            id=scan_dict.get("id", ""),
            doc_id=scan_dict.get("doc_id", ""),
            scan_status=ForensicScanStatus(scan_dict.get("scan_status", "completed")),
            file_hash_md5=scan_dict.get("file_hash_md5"),
            file_hash_sha256=scan_dict.get("file_hash_sha256"),
            file_hash_sha512=scan_dict.get("file_hash_sha512"),
            file_size=scan_dict.get("file_size"),
            integrity_status=IntegrityStatus(scan_dict.get("integrity_status", "unknown")),
            confidence_score=scan_dict.get("confidence_score", 0.0),
        )

        # Build EXIF data if present
        exif = scan_dict.get("exif_data", {})
        if exif and any(exif.values()):
            scan.exif_data = ExifData(
                make=exif.get("make"),
                model=exif.get("model"),
                serial_number=exif.get("serial_number"),
                software=exif.get("software"),
            )

        # Build PDF metadata if present
        pdf = scan_dict.get("pdf_metadata", {})
        if pdf and any(pdf.values()):
            scan.pdf_metadata = PdfMetadata(
                title=pdf.get("title"),
                author=pdf.get("author"),
                creator=pdf.get("creator"),
                producer=pdf.get("producer"),
            )

        # Build Office metadata if present
        office = scan_dict.get("office_metadata", {})
        if office and any(office.values()):
            scan.office_metadata = OfficeMetadata(
                title=office.get("title"),
                author=office.get("author"),
                company=office.get("company"),
            )

        return scan

    source = build_scan_from_dict(source_scan)
    target = build_scan_from_dict(target_scan)

    # Perform comparison
    comparison = shard.forensic_analyzer.compare_documents(source, target)

    # Store comparison result
    if shard._db:
        import json
        tenant_id = shard.get_tenant_id_or_none()
        await shard._db.execute(
            """
            INSERT INTO arkham_provenance.metadata_comparisons (
                id, source_doc_id, target_doc_id, comparison_type,
                match_score, differences, similarities, relationship_type,
                confidence, created_at, metadata, tenant_id
            ) VALUES (
                :id, :source_doc_id, :target_doc_id, :comparison_type,
                :match_score, :differences, :similarities, :relationship_type,
                :confidence, :created_at, :metadata, :tenant_id
            )
            """,
            {
                "id": comparison.id,
                "source_doc_id": comparison.source_doc_id,
                "target_doc_id": comparison.target_doc_id,
                "comparison_type": comparison.comparison_type,
                "match_score": comparison.match_score,
                "differences": json.dumps(comparison.differences),
                "similarities": json.dumps(comparison.similarities),
                "relationship_type": comparison.relationship_type.value if comparison.relationship_type else None,
                "confidence": comparison.confidence,
                "created_at": comparison.created_at.isoformat() if comparison.created_at else datetime.utcnow().isoformat(),
                "metadata": json.dumps(comparison.metadata),
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )

    return {
        "comparison": {
            "id": comparison.id,
            "source_doc_id": comparison.source_doc_id,
            "target_doc_id": comparison.target_doc_id,
            "comparison_type": comparison.comparison_type,
            "match_score": comparison.match_score,
            "differences": comparison.differences,
            "similarities": comparison.similarities,
            "relationship_type": comparison.relationship_type.value if comparison.relationship_type else None,
            "confidence": comparison.confidence,
        }
    }


@router.get("/forensics/stats", response_model=ForensicStatsResponse)
async def get_forensic_stats(request: Request):
    """
    Get forensic analysis statistics.

    Returns aggregated statistics about forensic scans:
    - Total scans performed
    - Scans by status
    - Documents with findings
    - Integrity status counts
    - Average confidence score
    """
    shard = get_shard(request)

    stats = await shard.get_forensic_stats()
    return ForensicStatsResponse(stats=stats)


@router.get("/forensics/document/{doc_id}")
async def get_document_forensic_scans(
    request: Request,
    doc_id: str,
):
    """
    Get all forensic scans for a document.

    Args:
        doc_id: Document ID

    Returns:
        List of scans for the document
    """
    shard = get_shard(request)

    scans = await shard.get_document_forensic_scans(doc_id)
    return {"scans": scans, "total": len(scans)}


@router.get("/forensics/{scan_id}")
async def get_forensic_scan(
    request: Request,
    scan_id: str,
):
    """
    Get a specific forensic scan by ID.

    Args:
        scan_id: Scan ID to retrieve

    Returns:
        Scan details
    """
    shard = get_shard(request)

    scan = await shard.get_forensic_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    return {"scan": scan}
