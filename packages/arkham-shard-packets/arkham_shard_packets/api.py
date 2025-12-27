"""
Packets Shard - FastAPI Routes

REST API endpoints for packet management.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .models import (
    ContentType,
    PacketStatus,
    PacketVisibility,
    SharePermission,
    ExportFormat,
)

if TYPE_CHECKING:
    from .shard import PacketsShard

router = APIRouter(prefix="/api/packets", tags=["packets"])

# === Pydantic Request/Response Models ===


class PacketCreate(BaseModel):
    """Request model for creating a packet."""
    name: str = Field(..., description="Packet name")
    description: str = Field(default="")
    visibility: PacketVisibility = Field(default=PacketVisibility.PRIVATE)
    metadata: Optional[Dict[str, Any]] = None


class PacketUpdate(BaseModel):
    """Request model for updating a packet."""
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[PacketVisibility] = None
    metadata: Optional[Dict[str, Any]] = None


class PacketResponse(BaseModel):
    """Response model for a packet."""
    id: str
    name: str
    description: str
    status: str
    visibility: str
    created_by: str
    created_at: str
    updated_at: str
    version: int
    contents_count: int
    size_bytes: int
    checksum: Optional[str]
    metadata: Dict[str, Any]


class PacketListResponse(BaseModel):
    """Response model for listing packets."""
    packets: List[PacketResponse]
    total: int
    limit: int
    offset: int


class ContentCreate(BaseModel):
    """Request model for adding content."""
    content_type: ContentType
    content_id: str
    content_title: str
    order: int = Field(default=0, ge=0)


class ContentResponse(BaseModel):
    """Response model for packet content."""
    id: str
    packet_id: str
    content_type: str
    content_id: str
    content_title: str
    added_at: str
    added_by: str
    order: int


class ShareCreate(BaseModel):
    """Request model for creating a share."""
    shared_with: str = Field(..., description="User ID or 'public'")
    permissions: SharePermission = Field(default=SharePermission.VIEW)
    expires_at: Optional[str] = None


class ShareResponse(BaseModel):
    """Response model for a share."""
    id: str
    packet_id: str
    shared_with: str
    permissions: str
    shared_at: str
    expires_at: Optional[str]
    access_token: str


class ExportRequest(BaseModel):
    """Request model for exporting a packet."""
    format: ExportFormat = Field(default=ExportFormat.ZIP)


class ExportResponse(BaseModel):
    """Response model for export results."""
    packet_id: str
    export_format: str
    file_path: str
    file_size_bytes: int
    exported_at: str
    contents_exported: int
    errors: List[str]


class ImportRequest(BaseModel):
    """Request model for importing a packet."""
    file_path: str
    merge_mode: str = Field(default="replace", pattern="^(replace|merge|skip)$")


class ImportResponse(BaseModel):
    """Response model for import results."""
    packet_id: str
    import_source: str
    imported_at: str
    contents_imported: int
    merge_mode: str
    errors: List[str]


class VersionResponse(BaseModel):
    """Response model for a version."""
    id: str
    packet_id: str
    version_number: int
    created_at: str
    changes_summary: str
    snapshot_path: str


class StatisticsResponse(BaseModel):
    """Response model for packet statistics."""
    total_packets: int
    by_status: Dict[str, int]
    by_visibility: Dict[str, int]
    total_contents: int
    by_content_type: Dict[str, int]
    total_shares: int
    active_shares: int
    expired_shares: int
    total_versions: int
    avg_contents_per_packet: float
    avg_size_bytes: float


class CountResponse(BaseModel):
    """Response model for count endpoint."""
    count: int


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    shard: str
    version: str


# === Helper Functions ===


def get_shard(request: Request) -> "PacketsShard":
    """Get the packets shard instance from app state."""
    shard = getattr(request.app.state, "packets_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Packets shard not available")
    return shard


def _packet_to_response(packet) -> PacketResponse:
    """Convert Packet object to response model."""
    return PacketResponse(
        id=packet.id,
        name=packet.name,
        description=packet.description,
        status=packet.status.value,
        visibility=packet.visibility.value,
        created_by=packet.created_by,
        created_at=packet.created_at.isoformat(),
        updated_at=packet.updated_at.isoformat(),
        version=packet.version,
        contents_count=packet.contents_count,
        size_bytes=packet.size_bytes,
        checksum=packet.checksum,
        metadata=packet.metadata,
    )


def _content_to_response(content) -> ContentResponse:
    """Convert PacketContent object to response model."""
    return ContentResponse(
        id=content.id,
        packet_id=content.packet_id,
        content_type=content.content_type.value,
        content_id=content.content_id,
        content_title=content.content_title,
        added_at=content.added_at.isoformat(),
        added_by=content.added_by,
        order=content.order,
    )


def _share_to_response(share) -> ShareResponse:
    """Convert PacketShare object to response model."""
    return ShareResponse(
        id=share.id,
        packet_id=share.packet_id,
        shared_with=share.shared_with,
        permissions=share.permissions.value,
        shared_at=share.shared_at.isoformat(),
        expires_at=share.expires_at.isoformat() if share.expires_at else None,
        access_token=share.access_token,
    )


def _version_to_response(version) -> VersionResponse:
    """Convert PacketVersion object to response model."""
    return VersionResponse(
        id=version.id,
        packet_id=version.packet_id,
        version_number=version.version_number,
        created_at=version.created_at.isoformat(),
        changes_summary=version.changes_summary,
        snapshot_path=version.snapshot_path,
    )


# === Endpoints ===


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint."""
    shard = get_shard(request)
    return HealthResponse(
        status="healthy",
        shard=shard.name,
        version=shard.version,
    )


@router.get("/count", response_model=CountResponse)
async def get_packets_count(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get count of packets (used for badge)."""
    shard = get_shard(request)
    count = await shard.get_count(status=status)
    return CountResponse(count=count)


@router.get("/", response_model=PacketListResponse)
async def list_packets(
    request: Request,
    status: Optional[PacketStatus] = Query(None),
    visibility: Optional[PacketVisibility] = Query(None),
    created_by: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search in name/description"),
    has_contents: Optional[bool] = Query(None),
    min_version: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List packets with optional filtering."""
    from .models import PacketFilter

    shard = get_shard(request)

    filter = PacketFilter(
        status=status,
        visibility=visibility,
        created_by=created_by,
        search_text=search,
        has_contents=has_contents,
        min_version=min_version,
    )

    packets = await shard.list_packets(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status=status.value if status else None)

    return PacketListResponse(
        packets=[_packet_to_response(p) for p in packets],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=PacketResponse, status_code=201)
async def create_packet(body: PacketCreate, request: Request):
    """Create a new packet."""
    shard = get_shard(request)

    packet = await shard.create_packet(
        name=body.name,
        description=body.description,
        visibility=body.visibility,
        metadata=body.metadata,
    )

    return _packet_to_response(packet)


@router.get("/{packet_id}", response_model=PacketResponse)
async def get_packet(packet_id: str, request: Request):
    """Get a specific packet by ID."""
    shard = get_shard(request)
    packet = await shard.get_packet(packet_id)

    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")

    return _packet_to_response(packet)


@router.put("/{packet_id}", response_model=PacketResponse)
async def update_packet(packet_id: str, body: PacketUpdate, request: Request):
    """Update packet metadata."""
    shard = get_shard(request)

    packet = await shard.update_packet(
        packet_id=packet_id,
        name=body.name,
        description=body.description,
        visibility=body.visibility,
        metadata=body.metadata,
    )

    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")

    return _packet_to_response(packet)


@router.delete("/{packet_id}", status_code=204)
async def delete_packet(packet_id: str, request: Request):
    """Delete a packet (archives it)."""
    shard = get_shard(request)

    packet = await shard.archive_packet(packet_id)

    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")


# === Status Endpoints ===


@router.post("/{packet_id}/finalize", response_model=PacketResponse)
async def finalize_packet(packet_id: str, request: Request):
    """Finalize a packet (lock for sharing)."""
    shard = get_shard(request)

    packet = await shard.finalize_packet(packet_id)

    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")

    return _packet_to_response(packet)


@router.post("/{packet_id}/archive", response_model=PacketResponse)
async def archive_packet_endpoint(packet_id: str, request: Request):
    """Archive a packet."""
    shard = get_shard(request)

    packet = await shard.archive_packet(packet_id)

    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")

    return _packet_to_response(packet)


# === Content Endpoints ===


@router.get("/{packet_id}/contents", response_model=List[ContentResponse])
async def get_packet_contents(packet_id: str, request: Request):
    """Get all contents for a packet."""
    shard = get_shard(request)

    # Verify packet exists
    packet = await shard.get_packet(packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")

    contents = await shard.get_packet_contents(packet_id)
    return [_content_to_response(c) for c in contents]


@router.post("/{packet_id}/contents", response_model=ContentResponse, status_code=201)
async def add_packet_content(packet_id: str, body: ContentCreate, request: Request):
    """Add content to a packet."""
    shard = get_shard(request)

    try:
        content = await shard.add_content(
            packet_id=packet_id,
            content_type=body.content_type,
            content_id=body.content_id,
            content_title=body.content_title,
            order=body.order,
        )
        return _content_to_response(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{packet_id}/contents/{content_id}", status_code=204)
async def remove_packet_content(packet_id: str, content_id: str, request: Request):
    """Remove content from a packet."""
    shard = get_shard(request)

    success = await shard.remove_content(packet_id, content_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove content (packet not found or not in draft status)"
        )


# === Share Endpoints ===


@router.post("/{packet_id}/share", response_model=ShareResponse, status_code=201)
async def share_packet(packet_id: str, body: ShareCreate, request: Request):
    """Create a share for a packet."""
    shard = get_shard(request)

    from datetime import datetime

    expires_at = None
    if body.expires_at:
        try:
            expires_at = datetime.fromisoformat(body.expires_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid expires_at format")

    try:
        share = await shard.share_packet(
            packet_id=packet_id,
            shared_with=body.shared_with,
            permissions=body.permissions,
            expires_at=expires_at,
        )
        return _share_to_response(share)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{packet_id}/shares", response_model=List[ShareResponse])
async def get_packet_shares(packet_id: str, request: Request):
    """Get all shares for a packet."""
    shard = get_shard(request)

    # Verify packet exists
    packet = await shard.get_packet(packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")

    shares = await shard.get_packet_shares(packet_id)
    return [_share_to_response(s) for s in shares]


@router.delete("/{packet_id}/shares/{share_id}", status_code=204)
async def revoke_share(packet_id: str, share_id: str, request: Request):
    """Revoke a packet share."""
    shard = get_shard(request)

    success = await shard.revoke_share(share_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Share {share_id} not found")


# === Export/Import Endpoints ===


@router.post("/{packet_id}/export", response_model=ExportResponse)
async def export_packet(packet_id: str, body: ExportRequest, request: Request):
    """Export a packet to a file."""
    shard = get_shard(request)

    try:
        result = await shard.export_packet(
            packet_id=packet_id,
            format=body.format,
        )
        return ExportResponse(
            packet_id=result.packet_id,
            export_format=result.export_format.value,
            file_path=result.file_path,
            file_size_bytes=result.file_size_bytes,
            exported_at=result.exported_at.isoformat(),
            contents_exported=result.contents_exported,
            errors=result.errors,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import", response_model=ImportResponse, status_code=201)
async def import_packet(body: ImportRequest, request: Request):
    """Import a packet from a file."""
    shard = get_shard(request)

    result = await shard.import_packet(
        file_path=body.file_path,
        merge_mode=body.merge_mode,
    )

    return ImportResponse(
        packet_id=result.packet_id,
        import_source=result.import_source,
        imported_at=result.imported_at.isoformat(),
        contents_imported=result.contents_imported,
        merge_mode=result.merge_mode,
        errors=result.errors,
    )


# === Version Endpoints ===


@router.get("/{packet_id}/versions", response_model=List[VersionResponse])
async def get_packet_versions(packet_id: str, request: Request):
    """Get version history for a packet."""
    shard = get_shard(request)

    # Verify packet exists
    packet = await shard.get_packet(packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")

    versions = await shard.get_packet_versions(packet_id)
    return [_version_to_response(v) for v in versions]


@router.post("/{packet_id}/versions", response_model=VersionResponse, status_code=201)
async def create_version_snapshot(
    packet_id: str,
    request: Request,
    changes_summary: str = Query(..., description="Summary of changes"),
):
    """Create a version snapshot."""
    shard = get_shard(request)

    try:
        version = await shard._create_version_snapshot(packet_id, changes_summary)
        return _version_to_response(version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# === Statistics Endpoints ===


@router.get("/stats/overview", response_model=StatisticsResponse)
async def get_statistics(request: Request):
    """Get statistics about packets in the system."""
    shard = get_shard(request)
    stats = await shard.get_statistics()

    return StatisticsResponse(
        total_packets=stats.total_packets,
        by_status=stats.by_status,
        by_visibility=stats.by_visibility,
        total_contents=stats.total_contents,
        by_content_type=stats.by_content_type,
        total_shares=stats.total_shares,
        active_shares=stats.active_shares,
        expired_shares=stats.expired_shares,
        total_versions=stats.total_versions,
        avg_contents_per_packet=stats.avg_contents_per_packet,
        avg_size_bytes=stats.avg_size_bytes,
    )


# === Filtered List Endpoints (for sub-routes) ===


@router.get("/status/draft", response_model=PacketListResponse)
async def list_draft_packets(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List draft packets."""
    from .models import PacketFilter

    shard = get_shard(request)
    filter = PacketFilter(status=PacketStatus.DRAFT)
    packets = await shard.list_packets(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="draft")

    return PacketListResponse(
        packets=[_packet_to_response(p) for p in packets],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/status/finalized", response_model=PacketListResponse)
async def list_finalized_packets(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List finalized packets."""
    from .models import PacketFilter

    shard = get_shard(request)
    filter = PacketFilter(status=PacketStatus.FINALIZED)
    packets = await shard.list_packets(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="finalized")

    return PacketListResponse(
        packets=[_packet_to_response(p) for p in packets],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/status/shared", response_model=PacketListResponse)
async def list_shared_packets(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List shared packets."""
    from .models import PacketFilter

    shard = get_shard(request)
    filter = PacketFilter(status=PacketStatus.SHARED)
    packets = await shard.list_packets(filter=filter, limit=limit, offset=offset)
    total = await shard.get_count(status="shared")

    return PacketListResponse(
        packets=[_packet_to_response(p) for p in packets],
        total=total,
        limit=limit,
        offset=offset,
    )
