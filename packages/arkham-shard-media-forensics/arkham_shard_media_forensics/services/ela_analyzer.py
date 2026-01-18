"""
Error Level Analysis (ELA) service.
Highlights regions with different compression levels.

IMPORTANT: ELA has high false positive rates and should be used
as a visualization tool, NOT as definitive evidence of manipulation.
"""

from typing import Dict, Any
from pathlib import Path
import io
import base64
import uuid

from PIL import Image
import numpy as np

import structlog

logger = structlog.get_logger()


class ELAAnalyzer:
    """
    Perform Error Level Analysis on images.

    ELA works by re-saving an image at a known quality level and
    comparing the result to the original. Regions that have been
    modified may show different error levels.

    CAVEAT: ELA is unreliable for:
    - Images saved multiple times
    - AI-generated images (often uniform ELA)
    - High-quality original images
    - Certain types of edits
    """

    def __init__(self, frame):
        self.frame = frame
        self.storage = frame.get_service("storage") if frame else None

    async def analyze(
        self,
        file_path: Path,
        quality: int = 95,
        scale: int = 15,
    ) -> Dict[str, Any]:
        """
        Perform ELA analysis on an image.

        Args:
            file_path: Path to image file
            quality: JPEG quality for resave (90-95 recommended)
            scale: Multiplier for error visualization (10-20 recommended)

        Returns:
            Dict with ELA image, interpretation, and caveats
        """
        try:
            # Load original image
            with Image.open(file_path) as original:
                # Convert to RGB if necessary
                if original.mode != "RGB":
                    original = original.convert("RGB")

                original_array = np.array(original)

                # Resave at specified quality
                buffer = io.BytesIO()
                original.save(buffer, format="JPEG", quality=quality)
                buffer.seek(0)

                with Image.open(buffer) as resaved:
                    resaved_array = np.array(resaved)

                # Compute absolute difference
                diff = np.abs(original_array.astype(np.int16) - resaved_array.astype(np.int16))

                # Scale for visibility
                ela = np.clip(diff * scale, 0, 255).astype(np.uint8)

                # Create ELA image
                ela_image = Image.fromarray(ela)

                # Convert to base64 for response
                ela_buffer = io.BytesIO()
                ela_image.save(ela_buffer, format="PNG")
                ela_base64 = base64.b64encode(ela_buffer.getvalue()).decode()

                # Analyze the ELA result
                interpretation = self._interpret_ela(ela)

                return {
                    "success": True,
                    "ela_image_base64": ela_base64,
                    "quality_used": quality,
                    "scale_used": scale,
                    "interpretation": interpretation,
                    "caveats": [
                        "ELA has high false positive rates",
                        "Uniform ELA may indicate AI generation OR multiple saves",
                        "Different error levels don't definitively prove manipulation",
                        "Use as one signal among many, not as proof",
                    ],
                }

        except Exception as e:
            logger.error("ELA analysis failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    def _interpret_ela(self, ela_array: np.ndarray) -> Dict[str, Any]:
        """
        Analyze ELA result for patterns.

        Returns interpretation with appropriate caveats.
        """
        # Calculate statistics
        mean_error = np.mean(ela_array)
        std_error = np.std(ela_array)
        max_error = np.max(ela_array)

        # Check uniformity
        # Split into blocks and check variance
        block_size = 64
        h, w = ela_array.shape[:2]

        block_means = []
        for y in range(0, h - block_size, block_size):
            for x in range(0, w - block_size, block_size):
                block = ela_array[y:y + block_size, x:x + block_size]
                block_means.append(np.mean(block))

        block_std = np.std(block_means) if block_means else 0

        interpretation = {
            "mean_error": float(mean_error),
            "std_error": float(std_error),
            "max_error": float(max_error),
            "uniformity_score": float(1.0 - min(block_std / 50, 1.0)),  # 0-1, higher = more uniform
            "assessment": "",
            "details": [],
        }

        # Interpret results (with heavy caveats)
        if block_std < 5:
            interpretation["assessment"] = "Highly uniform error levels"
            interpretation["details"].append(
                "The error levels are unusually uniform across the image. "
                "This MAY indicate: (1) AI-generated content, (2) multiple JPEG saves, "
                "or (3) heavy post-processing. This is NOT definitive."
            )
        elif block_std > 20:
            interpretation["assessment"] = "Variable error levels detected"
            interpretation["details"].append(
                "Different regions show different error levels. "
                "This MAY indicate editing, or may simply reflect different content "
                "(e.g., sky vs. detailed areas naturally compress differently)."
            )
        else:
            interpretation["assessment"] = "Error levels appear typical"
            interpretation["details"].append(
                "No obvious anomalies in error level distribution. "
                "This does NOT prove the image is authentic."
            )

        return interpretation

    async def save_ela_image(
        self,
        analysis_id: str,
        ela_base64: str,
    ) -> str:
        """Save ELA image to storage and return path."""
        # Generate filename
        filename = f"ela_{analysis_id}_{uuid.uuid4().hex[:8]}.png"

        # Decode and save
        ela_bytes = base64.b64decode(ela_base64)

        if self.storage:
            path = await self.storage.save(
                ela_bytes,
                filename=filename,
                category="media_forensics",
            )
            return path

        return filename
