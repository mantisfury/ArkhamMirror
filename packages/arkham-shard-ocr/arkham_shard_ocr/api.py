"""OCR Shard API routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

# Will be set during shard initialization
_shard = None


def init_api(shard):
    """Initialize API with shard instance."""
    global _shard
    _shard = shard


class OCRRequest(BaseModel):
    """Request for OCR processing."""
    document_id: Optional[str] = None
    image_path: Optional[str] = None
    engine: Optional[str] = None
    language: str = "en"


class TextLine(BaseModel):
    """Single line of detected text with bounding box."""
    text: str
    box: Optional[list] = None
    confidence: Optional[float] = None


class OCRResponse(BaseModel):
    """Response from OCR processing."""
    success: bool
    text: str = ""
    pages_processed: int = 0
    engine: str = ""
    error: Optional[str] = None
    confidence: Optional[float] = None
    lines: Optional[list[TextLine]] = None
    from_cache: bool = False
    escalated: bool = False
    char_count: int = 0
    word_count: int = 0


def _build_response(result: dict, pages: int = 1) -> OCRResponse:
    """Build OCRResponse from worker result."""
    text = result.get("text", "")

    # Build lines from worker result
    lines = None
    raw_lines = result.get("lines", [])
    if raw_lines:
        lines = [
            TextLine(
                text=line.get("text", ""),
                box=line.get("box"),
                confidence=line.get("confidence"),
            )
            for line in raw_lines
        ]

    return OCRResponse(
        success=True,
        text=text,
        pages_processed=pages,
        engine=result.get("engine", "paddle"),
        confidence=result.get("confidence"),
        lines=lines,
        from_cache=result.get("from_cache", False),
        escalated=result.get("escalated", False),
        char_count=len(text),
        word_count=len(text.split()) if text else 0,
    )


@router.get("/health")
async def health():
    """Health check endpoint with engine availability."""
    paddle_available = False
    qwen_available = False

    if _shard and _shard._frame:
        worker_service = _shard._frame.get_service("workers")
        if worker_service:
            # Check if workers are registered for each pool
            registered = getattr(worker_service, '_registered_workers', {})
            paddle_available = "gpu-paddle" in registered
            qwen_available = "gpu-qwen" in registered

    return {
        "status": "ok",
        "shard": "ocr",
        "paddle_available": paddle_available,
        "qwen_available": qwen_available,
    }


@router.post("/page", response_model=OCRResponse)
async def ocr_page(request: OCRRequest):
    """OCR a single page image."""
    if not _shard:
        raise HTTPException(status_code=503, detail="OCR shard not initialized")

    if not request.image_path:
        raise HTTPException(status_code=400, detail="image_path required")

    try:
        result = await _shard.ocr_page(
            image_path=request.image_path,
            engine=request.engine,
            language=request.language,
        )
        return _build_response(result, pages=1)
    except Exception as e:
        logger.error(f"OCR page failed: {e}")
        return OCRResponse(success=False, error=str(e))


@router.post("/document", response_model=OCRResponse)
async def ocr_document(request: OCRRequest):
    """OCR all pages of a document."""
    if not _shard:
        raise HTTPException(status_code=503, detail="OCR shard not initialized")

    if not request.document_id:
        raise HTTPException(status_code=400, detail="document_id required")

    try:
        result = await _shard.ocr_document(
            document_id=request.document_id,
            engine=request.engine,
            language=request.language,
        )

        # Check for error status from fallback OCR
        if result.get("status") == "failed":
            return OCRResponse(
                success=False,
                error=result.get("error", "OCR processing failed"),
                engine=result.get("engine", "paddle"),
            )

        # For document OCR, use total_text
        text = result.get("total_text", "")
        pages = result.get("pages_processed", 0)
        return OCRResponse(
            success=True,
            text=text,
            pages_processed=pages,
            engine=result.get("engine", "paddle"),
            char_count=len(text),
            word_count=len(text.split()) if text else 0,
        )
    except Exception as e:
        logger.error(f"OCR document failed: {e}")
        return OCRResponse(success=False, error=str(e))


@router.post("/upload", response_model=OCRResponse)
async def ocr_upload(file: UploadFile = File(...), engine: str = "paddle", language: str = "en"):
    """Upload and OCR an image file."""
    if not _shard:
        raise HTTPException(status_code=503, detail="OCR shard not initialized")

    # Save uploaded file temporarily
    import tempfile
    import os

    suffix = os.path.splitext(file.filename)[1] if file.filename else ".png"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = await _shard.ocr_page(
            image_path=tmp_path,
            engine=engine,
            language=language,
        )
        return _build_response(result, pages=1)
    except Exception as e:
        logger.error(f"OCR upload failed: {e}")
        return OCRResponse(success=False, error=str(e))
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass
