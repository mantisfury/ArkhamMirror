"""OCR Shard API routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

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


class OCRResponse(BaseModel):
    """Response from OCR processing."""
    success: bool
    text: str = ""
    pages_processed: int = 0
    engine: str = ""
    error: Optional[str] = None


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "shard": "ocr"}


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
        return OCRResponse(
            success=True,
            text=result.get("text", ""),
            pages_processed=1,
            engine=result.get("engine", "paddle"),
        )
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
        return OCRResponse(
            success=True,
            text=result.get("total_text", ""),
            pages_processed=result.get("pages_processed", 0),
            engine=result.get("engine", "paddle"),
        )
    except Exception as e:
        logger.error(f"OCR document failed: {e}")
        return OCRResponse(success=False, error=str(e))


@router.post("/upload")
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
        return OCRResponse(
            success=True,
            text=result.get("text", ""),
            pages_processed=1,
            engine=result.get("engine", "paddle"),
        )
    except Exception as e:
        logger.error(f"OCR upload failed: {e}")
        return OCRResponse(success=False, error=str(e))
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass
