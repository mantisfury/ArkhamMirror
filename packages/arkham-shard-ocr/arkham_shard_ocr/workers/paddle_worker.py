"""
PaddleOCR Worker - Fast CPU-based OCR using PaddleOCR.

Pool: gpu-paddle (despite name, runs efficiently on CPU too)
Purpose: Extract text from images with bounding box metadata.
"""

import base64
import io
import logging
import os
from typing import Any, Dict

from arkham_frame.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class PaddleWorker(BaseWorker):
    """
    Worker for OCR using PaddleOCR.

    Fast, reliable OCR with bounding box support.
    Best for: printed documents, clear text, high-volume processing.

    Payload formats:
    - Image path: {"image_path": "/path/to/image.png"}
    - Base64: {"image_base64": "...", "filename": "page.png"}
    - Batch: {"images": [{"path": "..."}, {"base64": "..."}], "batch": True}

    Optional params:
    - lang: Language code (default: "en")
    - use_angle_cls: Enable angle classification (default: True)
    - det_only: Only run detection, no recognition (default: False)

    Returns:
    - text: Full extracted text
    - lines: List of {"box": [[x,y]...], "text": "...", "confidence": 0.95}
    - meta: OCR metadata
    """

    pool = "gpu-paddle"
    name = "PaddleWorker"
    job_timeout = 120.0  # OCR can be slow for large images

    # Class-level lazy-loaded OCR engine
    _ocr_engine = None
    _lang = None

    def _resolve_path(self, file_path: str) -> str:
        """
        Resolve file path using DATA_SILO_PATH for Docker/portable deployments.

        Args:
            file_path: Path from payload (may be relative or absolute)

        Returns:
            Resolved absolute path as string
        """
        if not os.path.isabs(file_path):
            data_silo = os.environ.get("DATA_SILO_PATH", ".")
            return os.path.join(data_silo, file_path)
        return file_path

    @classmethod
    def _get_engine(cls, lang: str = "en", use_angle_cls: bool = True):
        """
        Get or initialize the PaddleOCR engine.

        Lazy loads on first use to save memory.

        Args:
            lang: Language code
            use_angle_cls: Enable angle classification

        Returns:
            PaddleOCR engine instance
        """
        if cls._ocr_engine is None or cls._lang != lang:
            try:
                from paddleocr import PaddleOCR
            except ImportError:
                raise ImportError(
                    "paddleocr not installed. "
                    "Install with: pip install paddleocr paddlepaddle"
                )

            logger.info(f"Initializing PaddleOCR (lang={lang}, angle_cls={use_angle_cls})")
            # Suppress PaddleOCR's verbose logging via environment
            os.environ["FLAGS_log_level"] = "3"  # Suppress paddle logging
            cls._ocr_engine = PaddleOCR(
                use_angle_cls=use_angle_cls,
                lang=lang,
            )
            cls._lang = lang
            logger.info("PaddleOCR initialized")

        return cls._ocr_engine

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an OCR job.

        Args:
            job_id: Unique job identifier
            payload: Job data

        Returns:
            Dict with text, lines, and metadata
        """
        # Get configuration
        lang = payload.get("lang", "en")
        use_angle_cls = payload.get("use_angle_cls", True)
        det_only = payload.get("det_only", False)

        # Get engine
        ocr_engine = self._get_engine(lang=lang, use_angle_cls=use_angle_cls)

        # Check if batch mode
        is_batch = payload.get("batch", False)

        if is_batch:
            images = payload.get("images", [])
            if not images:
                raise ValueError("Batch mode requires 'images' field")

            results = []
            for i, img_data in enumerate(images):
                try:
                    result = await self._process_single_image(
                        ocr_engine, img_data, det_only, job_id, i
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to process image {i}: {e}")
                    results.append({"error": str(e), "success": False})

            return {
                "results": results,
                "count": len(results),
                "success": all(r.get("success", False) for r in results),
            }

        else:
            # Single image
            return await self._process_single_image(
                ocr_engine, payload, det_only, job_id
            )

    async def _process_single_image(
        self,
        ocr_engine,
        payload: Dict[str, Any],
        det_only: bool,
        job_id: str,
        index: int = 0,
    ) -> Dict[str, Any]:
        """
        Process a single image through OCR.

        Args:
            ocr_engine: PaddleOCR engine
            payload: Image data (path or base64)
            det_only: Detection only mode
            job_id: Job ID for logging
            index: Image index for batch processing

        Returns:
            OCR result dict
        """
        import numpy as np
        from PIL import Image

        # Load image
        image_path = payload.get("image_path") or payload.get("path")
        image_base64 = payload.get("image_base64") or payload.get("base64")

        if image_path:
            # Resolve relative path using DATA_SILO_PATH
            resolved_path = self._resolve_path(image_path)
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(f"Image not found: {resolved_path}")

            logger.info(f"Job {job_id}: OCR on file {resolved_path}")
            img = Image.open(resolved_path)
            source = resolved_path

        elif image_base64:
            logger.info(f"Job {job_id}: OCR on base64 image (index {index})")
            img_data = base64.b64decode(image_base64)
            img = Image.open(io.BytesIO(img_data))
            source = payload.get("filename", f"base64_image_{index}")

        else:
            raise ValueError("Must provide 'image_path' or 'image_base64'")

        # Convert to numpy array for PaddleOCR
        img_np = np.array(img)

        # Run OCR (new PaddleOCR API doesn't use det/rec params)
        result = ocr_engine.ocr(img_np)

        # Parse results
        text_lines = []
        full_text = ""
        lines = []

        if result and result[0]:
            ocr_res = result[0]

            # Handle PaddleX / New PaddleOCR structure
            if hasattr(ocr_res, "keys") and "rec_texts" in ocr_res:
                # New format with dict keys
                texts = ocr_res["rec_texts"]
                scores = ocr_res["rec_scores"]
                boxes = ocr_res["rec_polys"]

                for box, text, score in zip(boxes, texts, scores):
                    box_list = box.tolist() if hasattr(box, "tolist") else list(box)
                    text_lines.append(text)
                    lines.append({
                        "box": box_list,
                        "text": text,
                        "confidence": float(score),
                    })

            # Handle old list-of-lists structure
            elif isinstance(ocr_res, list):
                for line in ocr_res:
                    if len(line) >= 2:
                        box = line[0]
                        text_conf = line[1]

                        if isinstance(text_conf, tuple) and len(text_conf) == 2:
                            text, conf = text_conf
                        else:
                            text = str(text_conf)
                            conf = 0.0

                        # Convert box to list if numpy
                        if hasattr(box, "tolist"):
                            box = box.tolist()

                        text_lines.append(text)
                        lines.append({
                            "box": box,
                            "text": text,
                            "confidence": float(conf),
                        })

            full_text = "\n".join(text_lines)

        # Calculate average confidence
        avg_confidence = 0.0
        if lines:
            confidences = [line["confidence"] for line in lines if line.get("confidence", 0) > 0]
            if confidences:
                avg_confidence = sum(confidences) / len(confidences)

        return {
            "text": full_text,
            "lines": lines,
            "line_count": len(lines),
            "char_count": len(full_text),
            "confidence": round(avg_confidence, 3),  # Average confidence for escalation
            "source": source,
            "lang": self._lang,
            "det_only": det_only,
            "success": True,
        }


def run_paddle_worker(redis_url: str = None, worker_id: str = None):
    """
    Convenience function to run a PaddleWorker.

    Args:
        redis_url: Redis connection URL
        worker_id: Optional worker ID

    Example:
        python -m arkham_shard_ocr.workers.paddle_worker
    """
    import asyncio
    worker = PaddleWorker(redis_url=redis_url, worker_id=worker_id)
    asyncio.run(worker.run())


if __name__ == "__main__":
    run_paddle_worker()
