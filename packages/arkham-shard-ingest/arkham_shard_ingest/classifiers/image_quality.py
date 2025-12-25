"""Image quality classification for OCR routing."""

import logging
import time
from pathlib import Path

from ..models import ImageQuality, ImageQualityScore

logger = logging.getLogger(__name__)


class ImageQualityClassifier:
    """
    Fast image quality assessment for OCR routing.
    Classifies images as CLEAN, FIXABLE, or MESSY.

    This runs in cpu-light pool and should complete in <5ms per image.
    """

    # Thresholds
    MIN_DPI = 150
    MAX_SKEW_DEGREES = 2.0
    MIN_CONTRAST = 0.4
    NOISE_THRESHOLD = 0.15  # Laplacian variance threshold

    def __init__(self):
        self._pil = None
        self._np = None
        try:
            from PIL import Image
            self._pil = Image
        except ImportError:
            logger.warning("PIL not available for image quality assessment")

        try:
            import numpy as np
            self._np = np
        except ImportError:
            logger.warning("NumPy not available, using simplified quality checks")

    def classify(self, path: Path) -> ImageQualityScore:
        """
        Analyze image quality and return classification.
        Designed to be fast (<5ms typical).
        """
        start = time.perf_counter()

        if not self._pil:
            # Fallback: assume needs work
            return ImageQualityScore(
                dpi=72,
                skew_angle=0.0,
                contrast_ratio=0.5,
                is_grayscale=False,
                compression_ratio=1.0,
                has_noise=False,
                layout_complexity="unknown",
                analysis_ms=0.0,
            )

        try:
            with self._pil.open(path) as img:
                # Get basic info
                width, height = img.size
                file_size = path.stat().st_size

                # DPI
                dpi = self._get_dpi(img)

                # Grayscale check
                is_grayscale = img.mode in ("L", "LA", "1")

                # Compression ratio (file size vs raw size)
                raw_size = width * height * (3 if img.mode == "RGB" else 1)
                compression_ratio = file_size / raw_size if raw_size > 0 else 1.0

                # For more detailed analysis, convert to array
                if self._np and width * height < 4_000_000:  # Skip huge images
                    arr = self._np.array(img.convert("L"))
                    contrast_ratio = self._calculate_contrast(arr)
                    skew_angle = self._estimate_skew(arr)
                    has_noise = self._detect_noise(arr)
                    layout_complexity = self._assess_layout(arr)
                else:
                    # Simplified for large images
                    contrast_ratio = 0.6
                    skew_angle = 0.0
                    has_noise = False
                    layout_complexity = "simple"

                elapsed_ms = (time.perf_counter() - start) * 1000

                return ImageQualityScore(
                    dpi=dpi,
                    skew_angle=skew_angle,
                    contrast_ratio=contrast_ratio,
                    is_grayscale=is_grayscale,
                    compression_ratio=compression_ratio,
                    has_noise=has_noise,
                    layout_complexity=layout_complexity,
                    analysis_ms=elapsed_ms,
                )

        except Exception as e:
            logger.warning(f"Image quality analysis failed: {e}")
            elapsed_ms = (time.perf_counter() - start) * 1000
            return ImageQualityScore(
                dpi=72,
                skew_angle=0.0,
                contrast_ratio=0.5,
                is_grayscale=False,
                compression_ratio=1.0,
                has_noise=True,
                layout_complexity="unknown",
                analysis_ms=elapsed_ms,
            )

    def _get_dpi(self, img) -> int:
        """Extract DPI from image metadata."""
        dpi = img.info.get("dpi")
        if dpi:
            return int(dpi[0]) if isinstance(dpi, tuple) else int(dpi)

        # Check EXIF
        exif = img.getexif() if hasattr(img, "getexif") else None
        if exif:
            # EXIF tag 282 = XResolution
            x_res = exif.get(282)
            if x_res:
                return int(x_res)

        # Default assumption for scanned documents
        return 72

    def _calculate_contrast(self, arr) -> float:
        """
        Calculate contrast ratio.
        Uses standard deviation normalized to 0-1 range.
        """
        if self._np is None:
            return 0.5

        std = self._np.std(arr)
        # Normalize: good contrast has std > 50
        return min(1.0, std / 80.0)

    def _estimate_skew(self, arr) -> float:
        """
        Estimate document skew angle.
        Simplified version using edge detection.
        """
        if self._np is None:
            return 0.0

        # Very simplified: check horizontal line consistency
        # Full implementation would use Hough transform
        try:
            # Check variance of row means
            row_means = self._np.mean(arr, axis=1)
            row_diff = self._np.diff(row_means)

            # High variance in diffs suggests skew
            variance = self._np.var(row_diff)
            # Map to approximate angle (heuristic)
            estimated_angle = min(10.0, variance / 100.0)
            return estimated_angle
        except Exception:
            return 0.0

    def _detect_noise(self, arr) -> bool:
        """
        Detect if image has significant noise.
        Uses Laplacian variance method.
        """
        if self._np is None:
            return False

        try:
            # Simple Laplacian approximation
            # Full implementation would use cv2.Laplacian
            laplacian = (
                arr[:-2, 1:-1] + arr[2:, 1:-1] +
                arr[1:-1, :-2] + arr[1:-1, 2:] -
                4 * arr[1:-1, 1:-1]
            )
            variance = self._np.var(laplacian)

            # Low variance = blurry, very high = noisy
            return variance > 500  # Threshold for noise
        except Exception:
            return False

    def _assess_layout(self, arr) -> str:
        """
        Assess document layout complexity.
        Returns: simple, table, mixed, complex
        """
        if self._np is None:
            return "simple"

        try:
            height, width = arr.shape

            # Count horizontal and vertical lines (simplified)
            # Check for regular patterns that suggest tables
            row_means = self._np.mean(arr, axis=1)
            col_means = self._np.mean(arr, axis=0)

            # Detect lines by looking for sudden changes
            row_edges = self._np.sum(self._np.abs(self._np.diff(row_means)) > 30)
            col_edges = self._np.sum(self._np.abs(self._np.diff(col_means)) > 30)

            edge_ratio = (row_edges + col_edges) / (height + width)

            if edge_ratio < 0.05:
                return "simple"
            elif edge_ratio < 0.15:
                return "table"
            elif edge_ratio < 0.3:
                return "mixed"
            else:
                return "complex"

        except Exception:
            return "simple"

    def get_ocr_route(
        self,
        quality: ImageQualityScore,
        ocr_mode: str = "auto"
    ) -> list[str]:
        """
        Determine OCR worker route based on quality.

        Args:
            quality: Quality assessment result
            ocr_mode: auto | paddle_only | qwen_only

        Returns:
            List of worker pool names in order
        """
        # User overrides
        if ocr_mode == "qwen_only":
            return ["cpu-image", "gpu-qwen"]
        if ocr_mode == "paddle_only":
            if quality.classification == ImageQuality.CLEAN:
                return ["gpu-paddle"]
            return ["cpu-image", "gpu-paddle"]

        # Auto routing based on classification
        classification = quality.classification

        if classification == ImageQuality.CLEAN:
            return ["gpu-paddle"]

        elif classification == ImageQuality.FIXABLE:
            return ["cpu-image", "gpu-paddle"]

        else:  # MESSY
            # Complex layouts go to Qwen
            if quality.layout_complexity in ("mixed", "complex"):
                return ["cpu-image", "gpu-qwen"]
            # Try paddle first, will escalate on low confidence
            return ["cpu-image", "gpu-paddle"]
