"""
Phase 5.6: OCR Fallback Service

Handles automatic fallback from PaddleOCR to Qwen-VL Vision OCR
when confidence is below threshold or quality indicators are poor.
"""

import logging
import os
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class OCRFallbackService:
    """
    Service for analyzing OCR quality to determine if Vision fallback is needed.
    
    Actual OCR execution (Paddle/Qwen) is handled in `ocr_worker.py`.
    This service provides the decision logic for when to switch methods.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.6,
        auto_fallback: bool = True,
    ):
        self.confidence_threshold = confidence_threshold
        self.auto_fallback = auto_fallback
        self.analyzer = OCRQualityAnalyzer(confidence_threshold)

    def analyze_paddle_output(
        self, text: str, paddle_confidence: float = None
    ) -> Dict[str, Any]:
        """
        Analyze PaddleOCR output to determine if fallback is needed.

        This can be called from the worker after PaddleOCR runs.

        Args:
            text: OCR output text
            paddle_confidence: Confidence from PaddleOCR

        Returns:
            Analysis result with needs_fallback flag
        """
        return self.analyzer.analyze(text, paddle_confidence)


# Singleton instance
_fallback_service: Optional[OCRFallbackService] = None


def get_fallback_service() -> OCRFallbackService:
    """Get the singleton fallback service."""
    global _fallback_service
    if _fallback_service is None:
        _fallback_service = OCRFallbackService()
    return _fallback_service


def analyze_ocr_quality(text: str, confidence: float = None) -> Dict[str, Any]:
    """Convenience function to analyze OCR output quality."""
    return get_fallback_service().analyze_paddle_output(text, confidence)


def should_use_vision_fallback(text: str, confidence: float = None) -> bool:
    """Check if Vision fallback should be used for this OCR output."""
    analysis = analyze_ocr_quality(text, confidence)
    return analysis.get("needs_fallback", False)
