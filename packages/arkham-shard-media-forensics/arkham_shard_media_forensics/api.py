"""Media Forensics Shard API endpoints."""

import logging
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .shard import MediaForensicsShard

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None

logger = logging.getLogger(__name__)


def _to_python_native(value: Any) -> Any:
    """Convert numpy types to Python native types for JSON serialization."""
    if value is None:
        return None
    try:
        import numpy as np
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
    except ImportError:
        pass
    return value

router = APIRouter(prefix="/api/media-forensics", tags=["media-forensics"])

# Shard reference set by init_api
_shard: Optional["MediaForensicsShard"] = None


def get_shard(request: Request) -> "MediaForensicsShard":
    """Get the Media Forensics shard instance from app state."""
    shard = getattr(request.app.state, "media_forensics_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Media Forensics shard not available")
    return shard


def init_api(shard: "MediaForensicsShard"):
    """Initialize API with shard reference."""
    global _shard
    _shard = shard
    logger.info("Media Forensics API initialized")


# ===========================================
# Request/Response Models
# ===========================================


class AnalyzeRequest(BaseModel):
    """Request to analyze a document."""
    document_id: str


class BatchAnalyzeRequest(BaseModel):
    """Request to analyze multiple documents."""
    document_ids: list[str]


class ELARequest(BaseModel):
    """Request to generate ELA analysis."""
    analysis_id: str
    quality: int = Field(default=95, ge=70, le=100)
    scale: int = Field(default=15, ge=5, le=30)


class SunPositionManualRequest(BaseModel):
    """Request to calculate sun position with manual coordinates."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    datetime: str  # ISO format


class SunPositionRequest(BaseModel):
    """Request to verify sun position from an analysis."""
    analysis_id: str
    override_location: Optional[dict] = None  # {"lat": float, "lon": float}
    override_time: Optional[str] = None  # ISO format


class SimilarSearchRequest(BaseModel):
    """Request to find similar images."""
    analysis_id: str
    hash_type: str = Field(default="phash", pattern="^(phash|dhash|ahash)$")
    threshold: int = Field(default=15, ge=0, le=64)  # Default 15 allows more visually similar results
    search_type: str = Field(default="internal", pattern="^(internal|external|both)$")
    limit: int = Field(default=50, ge=1, le=100)


# ===========================================
# Badge/Count Endpoint
# ===========================================


@router.get("/analyses/count")
async def get_analyses_count(request: Request):
    """Get count of analyses for badge display."""
    shard = get_shard(request)
    try:
        count = await shard.get_analysis_count()
        return {"count": count}
    except Exception as e:
        logger.error(f"Failed to get count: {e}")
        return {"count": 0}


# ===========================================
# Analysis Endpoints
# ===========================================


@router.get("/analyses")
async def list_analyses(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[Optional[str], Query()] = None,
    verification_status: Annotated[Optional[str], Query()] = None,
    has_c2pa: Annotated[Optional[bool], Query()] = None,
    has_warnings: Annotated[Optional[bool], Query()] = None,
    has_findings: Annotated[Optional[bool], Query()] = None,
    integrity_status: Annotated[Optional[str], Query()] = None,
    doc_id: Annotated[Optional[str], Query()] = None,
):
    """
    List media analyses with optional filtering.

    - **limit**: Maximum number of results (default 50, max 500)
    - **offset**: Number of results to skip for pagination
    - **status**: Filter by analysis status (pending, processing, completed, failed)
    - **verification_status**: Filter by verification status (verified, flagged, unknown, tampered)
    - **has_c2pa**: Filter by C2PA presence (true/false)
    - **has_warnings**: Filter by warning presence (true/false)
    - **has_findings**: Filter by findings presence (true/false)
    - **integrity_status**: Filter by integrity status (verified, flagged, unverified, unknown)
    - **doc_id**: Filter by document ID
    """
    shard = get_shard(request)

    try:
        items = await shard.list_analyses(
            limit=limit,
            offset=offset,
            status=status,
            verification_status=verification_status,
            has_c2pa=has_c2pa,
            has_warnings=has_warnings,
            has_findings=has_findings,
            integrity_status=integrity_status,
            doc_id=doc_id,
        )

        total = await shard.get_analysis_count()
        has_more = offset + len(items) < total

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    except Exception as e:
        logger.error(f"Failed to list analyses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list analyses: {str(e)}")


@router.get("/analyses/{analysis_id}")
async def get_analysis(request: Request, analysis_id: str):
    """Get a specific analysis by ID."""
    shard = get_shard(request)

    analysis = await shard.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")

    return analysis


@router.get("/document/{document_id}")
async def get_analysis_by_document(request: Request, document_id: str):
    """Get analysis for a specific document."""
    shard = get_shard(request)

    analysis = await shard.get_analysis_by_document(document_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"No analysis found for document: {document_id}")

    return analysis


# ===========================================
# Analysis Actions
# ===========================================


@router.post("/analyze")
async def analyze_document(request: Request, body: AnalyzeRequest):
    """
    Analyze a single document for media forensics.

    Extracts EXIF metadata, computes perceptual hashes, and parses C2PA content credentials.
    Auto-finds similar images using perceptual hashing.

    Returns:
        Full analysis results including:
        - EXIF/XMP metadata
        - Perceptual hashes (pHash, dHash, aHash)
        - C2PA content credentials (if present)
        - Warnings and anomalies detected
        - Integrity status assessment
    """
    with log_operation("media_forensics.analyze", document_id=body.document_id) as event:
        try:
            start_time = time.time()

            if event:
                event.context("shard", "media_forensics")
                event.context("operation", "analyze")
                event.input(document_id=body.document_id)

            shard = get_shard(request)

            result = await shard.analyze_document(body.document_id)

            duration_ms = (time.time() - start_time) * 1000

            if event:
                event.output(
                    analysis_id=result.get("analysis_id"),
                    document_id=body.document_id,
                    integrity_status=result.get("integrity_status"),
                    has_exif=bool(result.get("exif_data")),
                    has_c2pa=bool(result.get("c2pa_data")),
                    warnings_count=len(result.get("warnings", [])),
                    findings_count=len(result.get("findings", [])),
                    duration_ms=duration_ms,
                )

            return result

        except FileNotFoundError as e:
            if event:
                event.error(str(e), exc_info=True)
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            if event:
                event.error(str(e), exc_info=True)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            if event:
                event.error(str(e), exc_info=True)
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/batch")
async def analyze_batch(request: Request, body: BatchAnalyzeRequest):
    """
    Analyze multiple documents in batch.

    Performs full media forensics analysis on each document.

    Returns:
        List of analysis results with status per document.
    """
    shard = get_shard(request)

    results = []
    for doc_id in body.document_ids:
        try:
            result = await shard.analyze_document(doc_id)
            results.append({
                "document_id": doc_id,
                "status": "success",
                "analysis_id": result["analysis_id"],
                "integrity_status": result["integrity_status"],
            })
        except FileNotFoundError as e:
            results.append({
                "document_id": doc_id,
                "status": "error",
                "error": str(e),
            })
        except Exception as e:
            logger.error(f"Batch analysis failed for {doc_id}: {e}")
            results.append({
                "document_id": doc_id,
                "status": "error",
                "error": str(e),
            })

    return {
        "results": results,
        "total": len(results),
        "successful": len([r for r in results if r["status"] == "success"]),
        "failed": len([r for r in results if r["status"] == "error"]),
    }


@router.post("/upload")
async def upload_and_analyze(
    request: Request,
    file: UploadFile = File(...),
    run_ela: bool = Query(default=False, description="Also generate ELA analysis"),
):
    """
    Upload an image file and analyze it directly.

    This endpoint allows direct file upload for media forensics analysis
    without going through the standard document ingest pipeline.

    Accepts: JPEG, PNG, TIFF, WebP, GIF, BMP images.

    **Parameters:**
    - **file**: Image file to analyze
    - **run_ela**: Also generate ELA analysis (default: false)

    **Returns:**
        Full analysis results including:
        - EXIF/XMP metadata
        - Perceptual hashes (pHash, dHash, aHash)
        - C2PA content credentials (if present)
        - Warnings and anomalies detected
        - Integrity status assessment
        - ELA results (if run_ela=true)
    """
    shard = get_shard(request)

    # Validate file type
    allowed_types = {
        "image/jpeg", "image/png", "image/tiff", "image/webp",
        "image/gif", "image/bmp", "image/jpg"
    }
    content_type = file.content_type or ""
    filename = file.filename or "unknown"

    # Check by extension if content_type is generic
    ext = Path(filename).suffix.lower()
    ext_to_mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".tiff": "image/tiff", ".tif": "image/tiff", ".webp": "image/webp",
        ".gif": "image/gif", ".bmp": "image/bmp"
    }

    if content_type not in allowed_types:
        if ext in ext_to_mime:
            content_type = ext_to_mime[ext]
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {content_type}. Supported: JPEG, PNG, TIFF, WebP, GIF, BMP"
            )

    try:
        # Save uploaded file to persistent location (not temp, since ELA needs it later)
        upload_id = str(uuid.uuid4())

        # Get storage path from frame config
        storage_path = "data_silo"
        if hasattr(shard._frame, 'config'):
            config = shard._frame.config
            if hasattr(config, 'get'):
                storage_path = config.get("storage_path", "data_silo")
            elif hasattr(config, 'storage_path'):
                storage_path = config.storage_path or "data_silo"

        # Store in media_forensics subdirectory (persistent for ELA)
        media_dir = Path(storage_path) / "media_forensics"
        media_dir.mkdir(parents=True, exist_ok=True)

        # Preserve original extension with unique ID
        stored_path = media_dir / f"{upload_id}{ext}"

        with open(stored_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        logger.info(f"Saved uploaded file to {stored_path}")

        # Run analysis directly on file (file_path stored for future ELA)
        result = await shard.analyze_file(
            file_path=stored_path,
            filename=filename,
            run_ela=run_ela,
        )

        return result

    except Exception as e:
        logger.error(f"Upload analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/path")
async def analyze_file_path(
    request: Request,
    file_path: str = Query(..., description="Absolute path to image file"),
    run_ela: bool = Query(default=False, description="Also generate ELA analysis"),
):
    """
    Analyze an image file by its file system path.

    This endpoint allows analysis of images already on the server
    without uploading.

    **Parameters:**
    - **file_path**: Absolute path to the image file
    - **run_ela**: Also generate ELA analysis (default: false)

    **Returns:**
        Full analysis results.
    """
    shard = get_shard(request)

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {file_path}")

    # Check extension
    ext = path.suffix.lower()
    allowed_ext = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".gif", ".bmp"}
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(allowed_ext)}"
        )

    try:
        result = await shard.analyze_file(
            file_path=path,
            filename=path.name,
            run_ela=run_ela,
        )
        return result

    except Exception as e:
        logger.error(f"Path analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ===========================================
# ELA (Error Level Analysis) Endpoints
# ===========================================


@router.post("/ela")
async def generate_ela(request: Request, body: ELARequest):
    """
    Generate Error Level Analysis (ELA) for an analyzed image.

    ELA works by re-saving the image at a known quality level and comparing
    the difference. Modified regions may show different error levels.

    **Parameters:**
    - **analysis_id**: ID of the analysis to generate ELA for
    - **quality**: JPEG quality for resave (70-100, default 95)
    - **scale**: Multiplier for error visualization (5-30, default 15)

    **Returns:**
    - Base64-encoded ELA visualization image
    - Interpretation of results
    - List of caveats about ELA reliability

    **Important caveats:**
    - ELA is NOT definitive proof of manipulation
    - Different compression levels in original cause natural variations
    - Works best on JPEG images
    """
    shard = get_shard(request)

    if not shard.ela_analyzer:
        raise HTTPException(
            status_code=503,
            detail="ELA analyzer not available. Pillow library may not be installed."
        )

    try:
        result = await shard.generate_ela(
            analysis_id=body.analysis_id,
            quality=body.quality,
            scale=body.scale,
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "ELA generation failed"))

        # Transform result to match frontend expected format (ELAResult)
        interpretation = result.get("interpretation", {})
        ela_result = {
            "id": str(uuid.uuid4()),
            "doc_id": "",
            "analysis_id": body.analysis_id,
            "quality_level": result.get("quality_used", body.quality),
            "original_image_url": None,
            "ela_image_url": None,
            "ela_image_base64": result.get("ela_image_base64"),
            "global_avg_intensity": interpretation.get("mean_error", 0),
            "global_max_intensity": interpretation.get("max_error", 0),
            "suspicious_regions": [],  # TODO: detect suspicious regions
            "is_potentially_edited": interpretation.get("uniformity_score", 1.0) < 0.5 or interpretation.get("std_error", 0) > 30,
            "confidence": interpretation.get("uniformity_score", 0.5),
            "generated_at": datetime.utcnow().isoformat(),
        }

        return {"result": ela_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ELA generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"ELA generation failed: {str(e)}")


# ===========================================
# Sun Position Verification Endpoints
# ===========================================


@router.post("/sun-position")
async def verify_sun_position(request: Request, body: SunPositionRequest):
    """
    Verify sun position for an analysis using EXIF data or overrides.

    Uses the GPS coordinates and timestamp from EXIF metadata (or provided overrides)
    to calculate the expected sun position at the claimed time and location.

    **Parameters:**
    - **analysis_id**: ID of the analysis to verify
    - **override_location**: Optional override for GPS coordinates {"lat": float, "lon": float}
    - **override_time**: Optional override for timestamp (ISO format)

    **Returns:**
    - Sun position result with consistency assessment
    """
    shard = get_shard(request)

    if not shard.sun_position:
        raise HTTPException(
            status_code=503,
            detail="Sun position service not available. Pysolar library may not be installed."
        )

    try:
        # Get the analysis
        analysis = await shard.get_analysis(body.analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail=f"Analysis not found: {body.analysis_id}")

        exif_data = analysis.get("exif_data", {})
        gps = exif_data.get("gps", {})
        timestamps = exif_data.get("timestamps", {})

        # Use overrides if provided, otherwise use EXIF data
        if body.override_location:
            latitude = body.override_location.get("lat")
            longitude = body.override_location.get("lon")
        else:
            latitude = gps.get("latitude")
            longitude = gps.get("longitude")

        if body.override_time:
            claimed_time = body.override_time
        else:
            claimed_time = (
                timestamps.get("datetime_original")
                or timestamps.get("datetime_digitized")
                or timestamps.get("datetime_modified")
            )

        # Validate we have required data
        if latitude is None or longitude is None:
            return {
                "result": {
                    "id": str(uuid.uuid4()),
                    "doc_id": analysis.get("document_id", ""),
                    "analysis_id": body.analysis_id,
                    "claimed_location": None,
                    "claimed_time": claimed_time,
                    "calculated_sun_position": None,
                    "shadow_analysis": None,
                    "is_consistent": True,  # Can't verify without location
                    "inconsistency_details": ["No GPS coordinates available for verification"],
                    "confidence": 0.0,
                    "generated_at": datetime.utcnow().isoformat(),
                }
            }

        if not claimed_time:
            return {
                "result": {
                    "id": str(uuid.uuid4()),
                    "doc_id": analysis.get("document_id", ""),
                    "analysis_id": body.analysis_id,
                    "claimed_location": {"lat": latitude, "lon": longitude},
                    "claimed_time": None,
                    "calculated_sun_position": None,
                    "shadow_analysis": None,
                    "is_consistent": True,  # Can't verify without time
                    "inconsistency_details": ["No timestamp available for verification"],
                    "confidence": 0.0,
                    "generated_at": datetime.utcnow().isoformat(),
                }
            }

        # Parse datetime
        try:
            # Handle EXIF format (YYYY:MM:DD HH:MM:SS) and ISO format
            if ":" == claimed_time[4:5] and ":" == claimed_time[7:8]:
                # EXIF format - convert colons in date part to dashes
                claimed_time = claimed_time.replace(":", "-", 2)
            dt = datetime.fromisoformat(claimed_time.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Could not parse timestamp: {claimed_time} - {e}")
            dt = datetime.utcnow()

        # Calculate sun position
        sun_result = await shard.calculate_sun_position(
            latitude=latitude,
            longitude=longitude,
            dt=dt,
        )

        if not sun_result.get("success"):
            raise HTTPException(status_code=400, detail=sun_result.get("error", "Calculation failed"))

        # Convert numpy types to Python native for JSON serialization
        sun_above_horizon = bool(sun_result.get("sun_above_horizon", True))
        sun_azimuth = _to_python_native(sun_result.get("sun_azimuth", 0))
        sun_altitude = _to_python_native(sun_result.get("sun_altitude", 0))
        shadow_direction = _to_python_native(sun_result.get("expected_shadow_direction"))

        # Build the response in the format the frontend expects
        return {
            "result": {
                "id": str(uuid.uuid4()),
                "doc_id": analysis.get("document_id", ""),
                "analysis_id": body.analysis_id,
                "claimed_location": {"lat": float(latitude), "lon": float(longitude)},
                "claimed_time": dt.isoformat(),
                "calculated_sun_position": {
                    "azimuth": sun_azimuth,
                    "altitude": sun_altitude,
                    "calculated_time": dt.isoformat(),
                    "location_lat": float(latitude),
                    "location_lon": float(longitude),
                },
                "shadow_analysis": {
                    "detected_shadows": [],
                    "average_shadow_direction": shadow_direction,
                    "consistency_score": 1.0 if sun_above_horizon else 0.5,
                },
                "is_consistent": sun_above_horizon,
                "inconsistency_details": [] if sun_above_horizon else [
                    "Sun was below the horizon at the claimed time"
                ],
                "confidence": 0.85 if sun_above_horizon else 0.3,
                "generated_at": datetime.utcnow().isoformat(),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sun position verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/sun-position/manual")
async def calculate_sun_position_manual(request: Request, body: SunPositionManualRequest):
    """
    Calculate sun position for given coordinates and time (manual input).

    Uses the NOAA solar position algorithm to compute:
    - Sun altitude (elevation above horizon)
    - Sun azimuth (compass direction)
    - Expected shadow direction (opposite of sun)
    - Shadow length ratio (relative to object height)

    **Parameters:**
    - **latitude**: Latitude in decimal degrees (-90 to 90)
    - **longitude**: Longitude in decimal degrees (-180 to 180)
    - **datetime**: ISO format datetime string with timezone

    **Returns:**
    - Sun altitude and azimuth
    - Expected shadow direction
    - Interpretation text
    """
    shard = get_shard(request)

    if not shard.sun_position:
        raise HTTPException(
            status_code=503,
            detail="Sun position service not available. Pysolar library may not be installed."
        )

    try:
        # Parse datetime
        dt = datetime.fromisoformat(body.datetime.replace("Z", "+00:00"))

        result = await shard.calculate_sun_position(
            latitude=body.latitude,
            longitude=body.longitude,
            dt=dt,
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sun position calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


@router.get("/sun-position/{analysis_id}")
async def get_sun_position_from_exif(request: Request, analysis_id: str):
    """
    Calculate sun position from an analyzed image's EXIF data.

    Uses the GPS coordinates and timestamp from EXIF metadata to
    automatically calculate the expected sun position at the time
    and place the photo was supposedly taken.

    **Requirements:**
    - Analysis must have GPS coordinates in EXIF
    - Analysis must have timestamp in EXIF

    **Returns:**
    - Sun position data
    - Interpretation for shadow verification
    """
    shard = get_shard(request)

    if not shard.sun_position:
        raise HTTPException(
            status_code=503,
            detail="Sun position service not available. Pysolar library may not be installed."
        )

    try:
        result = await shard.get_sun_position_from_analysis(analysis_id)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sun position calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


# ===========================================
# Similar Image Search Endpoints
# ===========================================


@router.post("/similar")
async def find_similar_images(request: Request, body: SimilarSearchRequest):
    """
    Find images similar to a given analysis using perceptual hashing.

    Perceptual hashing creates a fingerprint of an image that is
    similar for visually similar images, even after resizing, compression,
    or minor modifications.

    **Parameters:**
    - **analysis_id**: Source analysis to find similar images for
    - **hash_type**: Type of perceptual hash to use (phash, dhash, ahash)
    - **threshold**: Maximum Hamming distance (0-64, lower = more similar)

    **Hash types:**
    - **phash**: Perceptual hash - good general purpose
    - **dhash**: Difference hash - fast, good for detecting crops
    - **ahash**: Average hash - simplest, may have more false positives

    **Returns:**
    - List of similar images with similarity scores
    """
    shard = get_shard(request)

    if not shard.hash_service:
        raise HTTPException(
            status_code=503,
            detail="Hash service not available. ImageHash library may not be installed."
        )

    try:
        # Transform results to match frontend expected format
        transformed_images = []
        exact_matches = 0
        near_duplicates = 0
        visually_similar = 0

        # Internal search: search within local database
        if body.search_type in ("internal", "both"):
            similar = await shard.find_similar_images(
                analysis_id=body.analysis_id,
                hash_type=body.hash_type,
                threshold=body.threshold,
            )

            for img in similar[:body.limit]:
                # Determine similarity type based on hamming distance
                distance = img.get("hamming_distance", 64)
                similarity_score = img.get("similarity_score", 0)

                if distance == 0:
                    similarity_type = "exact"
                    exact_matches += 1
                elif distance <= 5:
                    similarity_type = "near_duplicate"
                    near_duplicates += 1
                else:
                    similarity_type = "visually_similar"
                    visually_similar += 1

                # Fetch the analysis to get filename
                similar_analysis = await shard.get_analysis(img.get("analysis_id"))
                filename = "unknown"
                if similar_analysis:
                    filename = similar_analysis.get("filename", "unknown")

                transformed_images.append({
                    "id": img.get("analysis_id", str(uuid.uuid4())),
                    "doc_id": img.get("document_id", ""),
                    "filename": filename,
                    "similarity_score": similarity_score,
                    "similarity_type": similarity_type,
                    "match_details": {
                        "hash_distance": distance,
                    },
                    "thumbnail_url": None,
                    "thumbnail_base64": None,
                    "source": "internal",
                    "found_at": datetime.utcnow().isoformat(),
                })

        # External search: reverse image search via web APIs or URL generators
        search_urls = []
        if body.search_type in ("external", "both"):
            # Get base URL from request for generating image URLs
            base_url = str(request.base_url).rstrip("/")

            # Call the updated reverse_image_search that returns URLs and API results
            external_data = await shard.reverse_image_search(body.analysis_id, base_url)

            # Add search URLs for manual searching
            search_urls = external_data.get("search_urls", [])

            # Add any API-based results
            for result in external_data.get("api_results", [])[:body.limit - len(transformed_images)]:
                transformed_images.append({
                    "id": str(uuid.uuid4()),
                    "doc_id": "",
                    "filename": result.get("title", "External Result"),
                    "similarity_score": result.get("similarity_score", 0.5),
                    "similarity_type": "content_similar",
                    "match_details": {
                        "source_url": result.get("url"),
                        "source_domain": result.get("domain"),
                    },
                    "thumbnail_url": result.get("thumbnail_url"),
                    "thumbnail_base64": None,
                    "source": result.get("source", "external"),
                    "found_at": datetime.utcnow().isoformat(),
                })

        return {
            "result": {
                "id": str(uuid.uuid4()),
                "doc_id": "",
                "analysis_id": body.analysis_id,
                "search_type": body.search_type,
                "total_found": len(transformed_images),
                "similar_images": transformed_images,
                "exact_matches": exact_matches,
                "near_duplicates": near_duplicates,
                "visually_similar": len(transformed_images) - exact_matches - near_duplicates,
                "generated_at": datetime.utcnow().isoformat(),
                "search_urls": search_urls,  # URLs for manual reverse image search
            }
        }

    except Exception as e:
        logger.error(f"Similar image search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ===========================================
# Image Serving Endpoint (for reverse image search)
# ===========================================


@router.get("/image/{analysis_id}")
async def serve_analysis_image(request: Request, analysis_id: str):
    """
    Serve the original image file for an analysis.

    This endpoint is used to provide a URL for external reverse image
    search engines. The URL can be used with Google Lens, Yandex Images,
    TinEye, and other services.

    **Note:** For URL-based reverse image search to work, this endpoint
    must be accessible from the internet (not just localhost).
    """
    shard = get_shard(request)

    try:
        analysis = await shard.get_analysis(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        file_path = analysis.get("file_path")
        if not file_path:
            raise HTTPException(status_code=404, detail="No file path in analysis")

        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Image file not found")

        # Determine content type from extension
        ext_to_mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        content_type = ext_to_mime.get(path.suffix.lower(), "application/octet-stream")

        # Stream the file
        def iter_file():
            with open(path, "rb") as f:
                while chunk := f.read(65536):  # 64KB chunks
                    yield chunk

        return StreamingResponse(
            iter_file(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{path.name}"',
                "Cache-Control": "public, max-age=3600",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serve image: {str(e)}")


# ===========================================
# Statistics Endpoint
# ===========================================


@router.get("/stats")
async def get_stats(request: Request):
    """
    Get media forensics statistics.

    Returns aggregated statistics including:
    - Total number of analyses
    - Count with EXIF metadata
    - Count with GPS data
    - Count with C2PA content credentials
    - Count with warnings/anomalies
    - AI-generated images detected
    - Breakdown by integrity status
    - Breakdown by file type
    """
    shard = get_shard(request)

    try:
        stats = await shard.get_stats()
        return {"stats": stats}

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


# ===========================================
# C2PA Support Check
# ===========================================


@router.get("/c2pa/supported")
async def check_c2pa_support(request: Request):
    """
    Check which optional features are available.

    Returns availability of:
    - C2PA parsing (requires c2pa-python library)
    - C2PA signature verification
    - Sun position calculations (requires pysolar library)
    """
    shard = get_shard(request)

    return {
        "c2pa_available": shard.c2pa_parser is not None,
        "signature_verification_available": (
            shard.c2pa_parser is not None
            and hasattr(shard.c2pa_parser, "verify_signature")
        ),
        "pysolar_available": shard.sun_position is not None,
        "imagehash_available": shard.hash_service is not None,
        "ela_available": shard.ela_analyzer is not None,
        "exif_available": shard.exif_extractor is not None,
    }


# ===========================================
# Bulk Operations
# ===========================================


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(request: Request, analysis_id: str):
    """Delete an analysis record."""
    shard = get_shard(request)

    if not shard._db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Check if analysis exists
    analysis = await shard.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")

    try:
        # Delete related records first (cascade should handle this, but explicit is safer)
        await shard._db.execute(
            "DELETE FROM arkham_media_ela WHERE analysis_id = :id",
            {"id": analysis_id}
        )
        await shard._db.execute(
            "DELETE FROM arkham_media_sun_verification WHERE analysis_id = :id",
            {"id": analysis_id}
        )
        await shard._db.execute(
            "DELETE FROM arkham_media_similar WHERE source_analysis_id = :id OR target_analysis_id = :id",
            {"id": analysis_id}
        )
        await shard._db.execute(
            "DELETE FROM arkham_media_analyses WHERE id = :id",
            {"id": analysis_id}
        )

        # Emit event
        if shard._event_bus:
            await shard._event_bus.emit(
                "media.analysis.deleted",
                {
                    "analysis_id": analysis_id,
                    "document_id": analysis["document_id"],
                },
                source="media-forensics",
            )

        return {"status": "deleted", "analysis_id": analysis_id}

    except Exception as e:
        logger.error(f"Failed to delete analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.post("/{analysis_id}/reanalyze")
async def reanalyze(request: Request, analysis_id: str):
    """
    Re-run analysis on an existing record.

    Useful when analysis algorithms are updated or to refresh stale data.
    """
    shard = get_shard(request)

    # Get existing analysis
    analysis = await shard.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {analysis_id}")

    try:
        # Re-run analysis on the same document
        result = await shard.analyze_document(analysis["document_id"])

        return {
            "status": "reanalyzed",
            "old_analysis_id": analysis_id,
            "new_analysis_id": result["analysis_id"],
            "changes_detected": result["integrity_status"] != analysis["integrity_status"],
        }

    except Exception as e:
        logger.error(f"Reanalysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reanalysis failed: {str(e)}")


# ===========================================
# AI Junior Analyst Endpoint
# ===========================================


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""
    target_id: str
    context: dict[str, Any] = {}
    depth: str = "quick"
    session_id: Optional[str] = None
    message: Optional[str] = None
    conversation_history: Optional[list[dict[str, str]]] = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for Media Forensics analysis.

    Provides AI-powered interpretation of media analysis including:
    - EXIF metadata significance and anomalies
    - C2PA content credential verification
    - ELA interpretation for manipulation detection
    - Sun position consistency analysis
    - Similar image findings
    - Overall authenticity assessment

    **Parameters:**
    - **target_id**: ID of the analysis to interpret
    - **context**: Additional context data
    - **depth**: Analysis depth (quick, standard, deep)
    - **session_id**: Optional session ID for conversation continuity
    - **message**: Optional follow-up message
    - **conversation_history**: Optional previous conversation messages

    **Returns:**
    - Streaming SSE response with AI analysis
    """
    shard = get_shard(request)
    frame = shard._frame

    if not frame or not getattr(frame, "ai_analyst", None):
        raise HTTPException(
            status_code=503,
            detail="AI Analyst service not available"
        )

    # Build context from request
    try:
        from arkham_frame.services import AnalysisRequest, AnalysisDepth, AnalystMessage
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="AI Analyst service not available (import failed)"
        )

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
        shard="media-forensics",
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
