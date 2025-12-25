"""
ImageWorker - CPU-based image preprocessing for OCR.

Pool: cpu-image
Purpose: Prepare images for OCR by applying various preprocessing operations.
"""

import asyncio
import base64
import io
import logging
import os
from typing import Any, Dict, List, Tuple

from .base import BaseWorker

logger = logging.getLogger(__name__)


class ImageWorker(BaseWorker):
    """
    Worker for image preprocessing operations.

    Prepares images for OCR by applying various enhancement operations.
    All operations run on CPU using PIL/Pillow and NumPy.

    Supported operations:
    - preprocess: Full OCR preprocessing pipeline
    - resize: Resize images with aspect ratio preservation
    - deskew: Correct rotation/skew in scanned documents
    - denoise: Remove noise from images
    - enhance_contrast: Improve text visibility
    - binarize: Convert to black and white
    - analyze: Analyze image quality without modification

    Payload format:
    {
        "operation": "preprocess|resize|deskew|denoise|enhance_contrast|binarize|analyze",
        "image_path": "/path/to/image.png",  # OR
        "image_base64": "...",
        "output_path": "/path/to/output.png",  # Optional
        ... operation-specific params ...
    }

    Returns:
    {
        "image_base64": "...",  # Processed image (except for analyze)
        "success": True,
        ... operation-specific metadata ...
    }
    """

    pool = "cpu-image"
    name = "ImageWorker"
    job_timeout = 120.0  # Image processing can be slow for large images

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an image preprocessing job.

        Args:
            job_id: Unique job identifier
            payload: Job data

        Returns:
            Dict with processed image and metadata
        """
        operation = payload.get("operation", "preprocess")

        # Validate operation
        valid_operations = [
            "preprocess",
            "resize",
            "deskew",
            "denoise",
            "enhance_contrast",
            "binarize",
            "analyze",
        ]
        if operation not in valid_operations:
            raise ValueError(
                f"Invalid operation '{operation}'. Must be one of: {valid_operations}"
            )

        logger.info(f"Job {job_id}: Running {operation} operation")

        # Load image
        img = await self._load_image(payload)

        # Route to operation handler
        if operation == "preprocess":
            result = await self._preprocess(img, payload, job_id)
        elif operation == "resize":
            result = await self._resize(img, payload)
        elif operation == "deskew":
            result = await self._deskew(img, payload)
        elif operation == "denoise":
            result = await self._denoise(img, payload)
        elif operation == "enhance_contrast":
            result = await self._enhance_contrast(img, payload)
        elif operation == "binarize":
            result = await self._binarize(img, payload)
        elif operation == "analyze":
            result = await self._analyze(img, payload)
        else:
            raise ValueError(f"Unhandled operation: {operation}")

        # Save to output path if specified (and not analyze)
        if operation != "analyze":
            output_path = payload.get("output_path")
            if output_path:
                await self._save_image_from_base64(result["image_base64"], output_path)
                result["output_path"] = output_path

        result["operation"] = operation
        result["success"] = True

        logger.info(f"Job {job_id}: Completed {operation}")
        return result

    async def _load_image(self, payload: Dict[str, Any]):
        """
        Load image from path or base64.

        Args:
            payload: Job payload

        Returns:
            PIL Image
        """
        def _load():
            from PIL import Image

            image_path = payload.get("image_path")
            image_base64 = payload.get("image_base64")

            if image_path:
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"Image not found: {image_path}")
                return Image.open(image_path)

            elif image_base64:
                img_data = base64.b64decode(image_base64)
                return Image.open(io.BytesIO(img_data))

            else:
                raise ValueError("Must provide 'image_path' or 'image_base64'")

        # Run in executor since PIL I/O is blocking
        return await asyncio.to_thread(_load)

    async def _save_image_from_base64(self, img_base64: str, output_path: str):
        """
        Save base64 image to file.

        Args:
            img_base64: Base64-encoded image
            output_path: File path to save to
        """
        def _save():
            from PIL import Image

            img_data = base64.b64decode(img_base64)
            img = Image.open(io.BytesIO(img_data))

            # Create directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path)

        await asyncio.to_thread(_save)

    async def _image_to_base64(self, img, format: str = "PNG") -> str:
        """
        Convert PIL Image to base64 string.

        Args:
            img: PIL Image
            format: Image format (PNG, JPEG, etc.)

        Returns:
            Base64-encoded image string
        """
        def _convert():
            buffer = io.BytesIO()
            img.save(buffer, format=format)
            return base64.b64encode(buffer.getvalue()).decode()

        return await asyncio.to_thread(_convert)

    async def _preprocess(
        self, img, payload: Dict[str, Any], job_id: str
    ) -> Dict[str, Any]:
        """
        Full preprocessing pipeline for OCR.

        Applies: grayscale, contrast enhancement, denoise, deskew, threshold.

        Args:
            img: PIL Image
            payload: Job payload
            job_id: Job ID for logging

        Returns:
            Result dict with processed image
        """
        def _process():
            from PIL import Image, ImageEnhance
            import numpy as np
            import cv2

            logger.info(f"Job {job_id}: Starting preprocessing pipeline")
            operations_applied = []

            # Convert to numpy array
            img_np = np.array(img)

            # 1. Convert to grayscale
            if len(img_np.shape) == 3:
                img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                operations_applied.append("grayscale")
            else:
                img_gray = img_np

            # 2. Denoise
            img_denoised = cv2.fastNlMeansDenoising(img_gray, None, 10, 7, 21)
            operations_applied.append("denoise")

            # 3. Enhance contrast (CLAHE)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img_contrast = clahe.apply(img_denoised)
            operations_applied.append("enhance_contrast")

            # 4. Deskew
            img_deskewed, angle = self._deskew_cv2(img_contrast)
            if abs(angle) > 0.1:
                operations_applied.append(f"deskew({angle:.2f}°)")

            # 5. Binarize (Otsu's method)
            _, img_binary = cv2.threshold(
                img_deskewed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            operations_applied.append("binarize")

            # Convert back to PIL
            result_img = Image.fromarray(img_binary)

            logger.info(
                f"Job {job_id}: Preprocessing complete: {', '.join(operations_applied)}"
            )

            return result_img, operations_applied

        result_img, operations_applied = await asyncio.to_thread(_process)
        img_base64 = await self._image_to_base64(result_img)

        return {
            "image_base64": img_base64,
            "operations_applied": operations_applied,
        }

    async def _resize(self, img, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resize image.

        Args:
            img: PIL Image
            payload: Job payload with width, height, maintain_aspect

        Returns:
            Result dict with resized image
        """
        def _process():
            from PIL import Image

            width = payload.get("width")
            height = payload.get("height")
            maintain_aspect = payload.get("maintain_aspect", True)

            original_size = img.size

            if maintain_aspect:
                img.thumbnail((width or 10000, height or 10000), Image.Resampling.LANCZOS)
                new_size = img.size
            else:
                if not width or not height:
                    raise ValueError("width and height required when maintain_aspect=False")
                img = img.resize((width, height), Image.Resampling.LANCZOS)
                new_size = (width, height)

            return img, original_size, new_size

        result_img, original_size, new_size = await asyncio.to_thread(_process)
        img_base64 = await self._image_to_base64(result_img)

        return {
            "image_base64": img_base64,
            "original_size": list(original_size),
            "new_size": list(new_size),
        }

    async def _deskew(self, img, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Correct image rotation/skew.

        Args:
            img: PIL Image
            payload: Job payload with max_angle

        Returns:
            Result dict with deskewed image
        """
        def _process():
            from PIL import Image
            import numpy as np

            max_angle = payload.get("max_angle", 10)

            # Convert to numpy
            img_np = np.array(img)

            # Convert to grayscale if needed
            if len(img_np.shape) == 3:
                import cv2
                img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                img_gray = img_np

            # Deskew
            img_deskewed, angle = self._deskew_cv2(img_gray)

            # Limit to max_angle
            if abs(angle) > max_angle:
                logger.warning(
                    f"Detected angle {angle:.2f}° exceeds max_angle {max_angle}°, "
                    "skipping deskew"
                )
                return img, 0.0

            # Convert back to PIL
            result_img = Image.fromarray(img_deskewed)

            return result_img, angle

        result_img, angle = await asyncio.to_thread(_process)
        img_base64 = await self._image_to_base64(result_img)

        return {
            "image_base64": img_base64,
            "angle_corrected": round(angle, 2),
        }

    def _deskew_cv2(self, img_gray) -> Tuple[Any, float]:
        """
        Deskew a grayscale image using OpenCV.

        Args:
            img_gray: Grayscale numpy array

        Returns:
            (deskewed_image, angle)
        """
        import cv2
        import numpy as np

        # Threshold
        _, thresh = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Find all white pixels
        coords = np.column_stack(np.where(thresh > 0))

        if len(coords) < 10:
            # Not enough points to determine angle
            return img_gray, 0.0

        # Find minimum area rectangle
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]

        # Correct angle (OpenCV returns angle in [-90, 0])
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90

        # Rotate image
        if abs(angle) > 0.1:  # Only rotate if significant
            (h, w) = img_gray.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                img_gray,
                M,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )
            return rotated, angle

        return img_gray, 0.0

    async def _denoise(self, img, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove noise from image.

        Args:
            img: PIL Image
            payload: Job payload with strength

        Returns:
            Result dict with denoised image
        """
        def _process():
            from PIL import Image
            import numpy as np
            import cv2

            strength = payload.get("strength", "medium")

            # Convert to numpy
            img_np = np.array(img)

            # Convert to grayscale if needed
            if len(img_np.shape) == 3:
                img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                img_gray = img_np

            # Apply denoising based on strength
            if strength == "light":
                h = 5
            elif strength == "heavy":
                h = 15
            else:  # medium
                h = 10

            img_denoised = cv2.fastNlMeansDenoising(img_gray, None, h, 7, 21)

            # Convert back to PIL
            result_img = Image.fromarray(img_denoised)

            return result_img

        result_img = await asyncio.to_thread(_process)
        img_base64 = await self._image_to_base64(result_img)

        return {
            "image_base64": img_base64,
            "method": "bilateral",
        }

    async def _enhance_contrast(self, img, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Improve contrast for text visibility.

        Args:
            img: PIL Image
            payload: Job payload with method

        Returns:
            Result dict with enhanced image
        """
        def _process():
            from PIL import Image, ImageEnhance
            import numpy as np
            import cv2

            method = payload.get("method", "clahe")

            # Convert to numpy
            img_np = np.array(img)

            # Convert to grayscale if needed
            if len(img_np.shape) == 3:
                img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                img_gray = img_np

            if method == "clahe":
                # Adaptive histogram equalization
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                img_enhanced = clahe.apply(img_gray)

            elif method == "histogram":
                # Global histogram equalization
                img_enhanced = cv2.equalizeHist(img_gray)

            elif method == "auto":
                # Automatic contrast adjustment
                pil_img = Image.fromarray(img_gray)
                enhancer = ImageEnhance.Contrast(pil_img)
                img_enhanced = np.array(enhancer.enhance(1.5))

            else:
                raise ValueError(f"Unknown method: {method}")

            # Convert back to PIL
            result_img = Image.fromarray(img_enhanced)

            return result_img, method

        result_img, method_used = await asyncio.to_thread(_process)
        img_base64 = await self._image_to_base64(result_img)

        return {
            "image_base64": img_base64,
            "method": method_used,
        }

    async def _binarize(self, img, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert to black and white (for OCR).

        Args:
            img: PIL Image
            payload: Job payload with method, block_size

        Returns:
            Result dict with binarized image
        """
        def _process():
            from PIL import Image
            import numpy as np
            import cv2

            method = payload.get("method", "otsu")
            block_size = payload.get("block_size", 11)

            # Ensure block_size is odd
            if block_size % 2 == 0:
                block_size += 1

            # Convert to numpy
            img_np = np.array(img)

            # Convert to grayscale if needed
            if len(img_np.shape) == 3:
                img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                img_gray = img_np

            if method == "otsu":
                # Otsu's binarization
                threshold_val, img_binary = cv2.threshold(
                    img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )

            elif method == "adaptive":
                # Adaptive thresholding (Gaussian)
                img_binary = cv2.adaptiveThreshold(
                    img_gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    block_size,
                    2,
                )
                threshold_val = None

            elif method == "sauvola":
                # Sauvola binarization (via local mean/std)
                # Approximation using adaptive threshold
                img_binary = cv2.adaptiveThreshold(
                    img_gray,
                    255,
                    cv2.ADAPTIVE_THRESH_MEAN_C,
                    cv2.THRESH_BINARY,
                    block_size,
                    10,
                )
                threshold_val = None

            else:
                raise ValueError(f"Unknown method: {method}")

            # Convert back to PIL
            result_img = Image.fromarray(img_binary)

            return result_img, threshold_val

        result_img, threshold_val = await asyncio.to_thread(_process)
        img_base64 = await self._image_to_base64(result_img)

        result = {
            "image_base64": img_base64,
        }

        if threshold_val is not None:
            result["threshold"] = int(threshold_val)

        return result

    async def _analyze(self, img, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze image quality (no modification).

        Args:
            img: PIL Image
            payload: Job payload

        Returns:
            Result dict with analysis metrics
        """
        def _process():
            import numpy as np
            import cv2

            # Convert to numpy
            img_np = np.array(img)

            # Convert to grayscale if needed
            is_grayscale = len(img_np.shape) == 2
            if is_grayscale:
                img_gray = img_np
            else:
                img_gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

            # Estimate DPI (if available from EXIF, otherwise estimate)
            dpi = img.info.get("dpi", (None, None))[0]
            if not dpi:
                # Rough estimate based on size (assume A4 document)
                width_inches = img.width / 210 * 8.27  # A4 width in inches
                dpi = int(img.width / width_inches) if width_inches > 0 else 72

            # Calculate contrast (std deviation of pixel values)
            contrast = np.std(img_gray) / 255.0

            # Estimate noise level (using Laplacian variance)
            laplacian = cv2.Laplacian(img_gray, cv2.CV_64F)
            noise_level = laplacian.var() / 10000.0  # Normalize

            # Estimate skew angle
            _, thresh = cv2.threshold(
                img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) > 10:
                rect = cv2.minAreaRect(coords)
                skew_angle = rect[-1]
                if skew_angle < -45:
                    skew_angle = 90 + skew_angle
                elif skew_angle > 45:
                    skew_angle = skew_angle - 90
            else:
                skew_angle = 0.0

            # Recommendation
            if contrast > 0.3 and noise_level < 0.5 and abs(skew_angle) < 2:
                recommendation = "CLEAN"
            elif contrast > 0.15 and noise_level < 2.0 and abs(skew_angle) < 10:
                recommendation = "FIXABLE"
            else:
                recommendation = "MESSY"

            return {
                "dpi": int(dpi),
                "contrast": round(contrast, 3),
                "noise_level": round(noise_level, 3),
                "skew_angle": round(skew_angle, 2),
                "is_grayscale": is_grayscale,
                "recommendation": recommendation,
                "width": img.width,
                "height": img.height,
            }

        return await asyncio.to_thread(_process)


def run_image_worker(redis_url: str = None, worker_id: str = None):
    """
    Convenience function to run an ImageWorker.

    Args:
        redis_url: Redis connection URL
        worker_id: Optional worker ID

    Example:
        python -m arkham_frame.workers.image_worker
    """
    import asyncio
    worker = ImageWorker(redis_url=redis_url, worker_id=worker_id)
    asyncio.run(worker.run())


if __name__ == "__main__":
    run_image_worker()
