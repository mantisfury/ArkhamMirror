"""OCR Shard data models."""

from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class OCREngine(str, Enum):
    """Available OCR engines."""
    PADDLE = "paddle"
    QWEN = "qwen"


class BoundingBox(BaseModel):
    """Bounding box for detected text."""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


class TextBlock(BaseModel):
    """A block of detected text with position."""
    text: str
    bbox: BoundingBox
    line_number: int = 0
    block_number: int = 0


class PageOCRResult(BaseModel):
    """OCR result for a single page."""
    page_number: int
    text: str
    blocks: List[TextBlock] = []
    language: str = "en"
    engine: OCREngine = OCREngine.PADDLE
    confidence: float = 0.0
    processing_time_ms: float = 0.0


class DocumentOCRResult(BaseModel):
    """OCR result for a full document."""
    document_id: str
    pages: List[PageOCRResult] = []
    total_text: str = ""
    engine: OCREngine = OCREngine.PADDLE
    total_processing_time_ms: float = 0.0
