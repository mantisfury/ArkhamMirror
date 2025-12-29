"""OCR Shard implementation."""

import asyncio
import hashlib
import logging
import time
from pathlib import Path
from arkham_frame.shard_interface import ArkhamShard
from .api import router, init_api

logger = logging.getLogger(__name__)


class OCRShard(ArkhamShard):
    """
    OCR shard for ArkhamFrame.

    Handles:
    - PaddleOCR for standard document OCR
    - Qwen-VL for complex/handwritten OCR
    - Page-level and document-level processing
    - Bounding box extraction
    """

    name = "ocr"
    version = "0.1.0"
    description = "Optical character recognition for document images"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self._frame = None
        self._config = None
        self._default_engine = "paddle"
        self._parallel_pages = 4  # Default concurrent page OCR limit
        self._confidence_threshold = 0.8  # Escalate to Qwen below this
        self._enable_escalation = True  # Enable confidence-based escalation
        self._enable_cache = True  # Enable result caching
        self._cache_ttl_days = 7  # Cache TTL in days
        self._cache: dict[str, tuple[float, dict]] = {}  # checksum -> (timestamp, result)

    async def initialize(self, frame) -> None:
        """Initialize the shard with Frame services."""
        self._frame = frame
        self._config = frame.config

        logger.info("Initializing OCR Shard...")

        # Get OCR settings from config
        self._default_engine = self._config.get("ocr_default_engine", "paddle")
        self._parallel_pages = self._config.get("ocr_parallel_pages", 4)
        self._confidence_threshold = self._config.get("ocr_confidence_threshold", 0.8)
        self._enable_escalation = self._config.get("ocr_enable_escalation", True)
        self._enable_cache = self._config.get("ocr_enable_cache", True)
        self._cache_ttl_days = self._config.get("ocr_cache_ttl_days", 7)

        # Register workers with Frame
        worker_service = frame.get_service("workers")
        if worker_service:
            from .workers import PaddleWorker, QwenWorker
            worker_service.register_worker(PaddleWorker)
            worker_service.register_worker(QwenWorker)
            logger.info("Registered OCR workers (paddle, qwen)")

        # Subscribe to events
        event_bus = frame.get_service("events")
        if event_bus:
            await event_bus.subscribe("ingest.job.completed", self._on_document_ingested)

        # Initialize API with shard reference
        init_api(self)

        logger.info("OCR Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down OCR Shard...")

        # Unregister workers
        if self._frame:
            worker_service = self._frame.get_service("workers")
            if worker_service:
                from .workers import PaddleWorker, QwenWorker
                worker_service.unregister_worker(PaddleWorker)
                worker_service.unregister_worker(QwenWorker)

            # Unsubscribe from events
            event_bus = self._frame.get_service("events")
            if event_bus:
                await event_bus.unsubscribe("ingest.job.completed", self._on_document_ingested)

        logger.info("OCR Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    # --- Cache Methods ---

    def _get_file_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file for cache key."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _cache_get(self, checksum: str, engine: str) -> dict | None:
        """
        Get cached OCR result if available and not expired.

        Args:
            checksum: File checksum
            engine: OCR engine used

        Returns:
            Cached result or None if not found/expired
        """
        if not self._enable_cache:
            return None

        cache_key = f"{checksum}:{engine}"
        entry = self._cache.get(cache_key)

        if entry is None:
            return None

        timestamp, result = entry
        ttl_seconds = self._cache_ttl_days * 24 * 60 * 60

        if time.time() - timestamp > ttl_seconds:
            # Expired, remove from cache
            del self._cache[cache_key]
            return None

        return result

    def _cache_set(self, checksum: str, engine: str, result: dict) -> None:
        """
        Store OCR result in cache.

        Args:
            checksum: File checksum
            engine: OCR engine used
            result: OCR result to cache
        """
        if not self._enable_cache:
            return

        cache_key = f"{checksum}:{engine}"
        self._cache[cache_key] = (time.time(), result)

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        now = time.time()
        ttl_seconds = self._cache_ttl_days * 24 * 60 * 60

        valid_entries = 0
        expired_entries = 0

        for key, (timestamp, _) in list(self._cache.items()):
            if now - timestamp > ttl_seconds:
                expired_entries += 1
            else:
                valid_entries += 1

        return {
            "enabled": self._enable_cache,
            "ttl_days": self._cache_ttl_days,
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
        }

    def clear_cache(self) -> int:
        """Clear all cached results. Returns number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {count} cached OCR results")
        return count

    async def _on_document_ingested(self, event: dict) -> None:
        """Handle document ingestion - trigger OCR if needed."""
        doc_id = event.get("document_id")
        doc_type = event.get("document_type", "")

        # Only OCR image-based documents
        if doc_type not in ("image", "scanned_pdf"):
            return

        logger.info(f"Auto-triggering OCR for document {doc_id}")
        await self.ocr_document(doc_id)

    # --- Public API ---

    async def ocr_page(
        self,
        image_path: str,
        engine: str | None = None,
        language: str = "en",
        allow_escalation: bool = True,
        use_cache: bool = True,
    ) -> dict:
        """
        OCR a single page image.

        Args:
            image_path: Path to the image file
            engine: OCR engine ("paddle" or "qwen"), defaults to config
            language: Language code
            allow_escalation: If True, low-confidence Paddle results escalate to Qwen
            use_cache: If True, check/store results in cache

        Returns:
            OCR result with text, bounding boxes, and confidence
        """
        selected_engine = engine or self._default_engine
        pool = f"gpu-{selected_engine}" if selected_engine == "qwen" else "gpu-paddle"

        # Check cache first
        checksum = None
        if use_cache and self._enable_cache and Path(image_path).exists():
            checksum = self._get_file_checksum(image_path)
            cached = self._cache_get(checksum, selected_engine)
            if cached:
                logger.debug(f"Cache hit for {image_path} (engine={selected_engine})")
                cached["from_cache"] = True
                return cached

        worker_service = self._frame.get_service("workers")
        if not worker_service:
            raise RuntimeError("Worker service not available")

        result = await worker_service.enqueue_and_wait(
            pool=pool,
            payload={
                "image_path": image_path,
                "lang": language,
                "job_type": "ocr_page",
            },
        )

        # Confidence-based escalation: if Paddle returns low confidence, try Qwen
        if (
            allow_escalation
            and self._enable_escalation
            and selected_engine == "paddle"
            and result.get("confidence", 1.0) < self._confidence_threshold
        ):
            original_confidence = result.get("confidence", 0)
            logger.info(
                f"Escalating OCR for {image_path}: Paddle confidence {original_confidence:.2f} "
                f"< threshold {self._confidence_threshold}"
            )

            # Emit escalation event
            event_bus = self._frame.get_service("events")
            if event_bus:
                await event_bus.emit(
                    "ocr.escalation",
                    {
                        "image_path": image_path,
                        "original_engine": "paddle",
                        "original_confidence": original_confidence,
                        "threshold": self._confidence_threshold,
                        "escalated_to": "qwen",
                    },
                    source="ocr-shard",
                )

            # Re-OCR with Qwen (no further escalation)
            qwen_result = await worker_service.enqueue_and_wait(
                pool="gpu-qwen",
                payload={
                    "image_path": image_path,
                    "lang": language,
                    "job_type": "ocr_page",
                },
            )
            qwen_result["escalated"] = True
            qwen_result["original_engine"] = "paddle"
            qwen_result["original_confidence"] = original_confidence

            # Cache the escalated result under qwen engine
            if use_cache and checksum:
                self._cache_set(checksum, "qwen", qwen_result)

            qwen_result["from_cache"] = False
            return qwen_result

        result["escalated"] = False
        result["from_cache"] = False

        # Cache the result
        if use_cache and checksum:
            self._cache_set(checksum, selected_engine, result)

        return result

    async def _ocr_document_from_file(
        self,
        document_id: str,
        doc_service,
        engine: str | None = None,
        language: str = "en",
        event_bus=None,
    ) -> dict:
        """
        OCR a document directly from its source file.

        Used when no page images are available (e.g., PDFs that were text-extracted
        but not rendered to images).

        Args:
            document_id: Document ID
            doc_service: DocumentService instance
            engine: OCR engine to use
            language: Language code
            event_bus: EventBus for emitting events

        Returns:
            OCR results dict
        """
        selected_engine = engine or self._default_engine

        # Get the document record to find storage_id
        doc = await doc_service.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        if not doc.storage_id:
            return {
                "document_id": document_id,
                "engine": selected_engine,
                "pages_processed": 0,
                "total_text": "",
                "page_results": [],
                "status": "failed",
                "error": "Document has no associated file",
            }

        # Get file info from storage service
        storage_service = self._frame.get_service("storage")
        if not storage_service:
            raise RuntimeError("Storage service not available")

        file_info = await storage_service.get_file_info(doc.storage_id)
        if not file_info:
            return {
                "document_id": document_id,
                "engine": selected_engine,
                "pages_processed": 0,
                "total_text": "",
                "page_results": [],
                "status": "failed",
                "error": f"File not found in storage: {doc.storage_id}",
            }

        # Get full file path
        base_path = storage_service.get_base_path()
        file_path = base_path / file_info.path

        if not file_path.exists():
            return {
                "document_id": document_id,
                "engine": selected_engine,
                "pages_processed": 0,
                "total_text": "",
                "page_results": [],
                "status": "failed",
                "error": f"File not found on disk: {file_path}",
            }

        # Check file type and process accordingly
        mime_type = (file_info.mime_type or "").lower()
        is_pdf = mime_type == "application/pdf" or str(file_path).lower().endswith(".pdf")
        is_image = mime_type.startswith("image/") or any(
            str(file_path).lower().endswith(ext)
            for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"]
        )

        if is_image:
            # Single image - OCR directly
            logger.info(f"OCR'ing image file: {file_path}")
            page_result = await self.ocr_page(
                image_path=str(file_path),
                engine=selected_engine,
                language=language,
            )

            result = {
                "document_id": document_id,
                "engine": selected_engine,
                "pages_processed": 1,
                "total_pages": 1,
                "total_text": page_result.get("text", ""),
                "page_results": [
                    {
                        "page": 1,
                        "path": str(file_path),
                        "text": page_result.get("text", ""),
                        "boxes": page_result.get("boxes", []),
                        "confidence": page_result.get("confidence"),
                    }
                ],
                "status": "completed",
            }

        elif is_pdf:
            # PDF - convert to images and OCR each page
            logger.info(f"Converting PDF to images for OCR: {file_path}")
            result = await self._ocr_pdf_file(
                pdf_path=str(file_path),
                document_id=document_id,
                engine=selected_engine,
                language=language,
            )

        else:
            return {
                "document_id": document_id,
                "engine": selected_engine,
                "pages_processed": 0,
                "total_text": "",
                "page_results": [],
                "status": "failed",
                "error": f"Unsupported file type for OCR: {mime_type}",
            }

        # Emit completion event
        if event_bus:
            await event_bus.emit(
                "ocr.document.completed",
                result,
                source="ocr-shard",
            )

        return result

    async def _ocr_pdf_file(
        self,
        pdf_path: str,
        document_id: str,
        engine: str,
        language: str,
    ) -> dict:
        """
        Convert a PDF to images and OCR each page.

        Args:
            pdf_path: Path to the PDF file
            document_id: Document ID
            engine: OCR engine
            language: Language code

        Returns:
            OCR results dict
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            logger.error("pdf2image not installed - cannot OCR PDFs without page images")
            return {
                "document_id": document_id,
                "engine": engine,
                "pages_processed": 0,
                "total_text": "",
                "page_results": [],
                "status": "failed",
                "error": "pdf2image not installed. Install with: pip install pdf2image",
            }

        # Get storage service for temp files
        storage_service = self._frame.get_service("storage")
        temp_dir = None

        try:
            # Create temp directory for page images
            if storage_service:
                temp_dir = await storage_service.create_temp(prefix="ocr_pdf_")
                temp_dir = Path(temp_dir).parent / f"ocr_pdf_{document_id}"
                temp_dir.mkdir(parents=True, exist_ok=True)
            else:
                import tempfile
                temp_dir = Path(tempfile.mkdtemp(prefix="ocr_pdf_"))

            logger.info(f"Converting PDF {pdf_path} to images in {temp_dir}")

            # Convert PDF to images
            try:
                images = await asyncio.to_thread(
                    convert_from_path,
                    pdf_path,
                    dpi=200,  # Good balance of quality and speed
                    fmt="png",
                )
            except Exception as e:
                logger.error(f"Failed to convert PDF to images: {e}")
                return {
                    "document_id": document_id,
                    "engine": engine,
                    "pages_processed": 0,
                    "total_text": "",
                    "page_results": [],
                    "status": "failed",
                    "error": f"Failed to convert PDF: {str(e)}",
                }

            if not images:
                return {
                    "document_id": document_id,
                    "engine": engine,
                    "pages_processed": 0,
                    "total_text": "",
                    "page_results": [],
                    "status": "completed",
                }

            # Save images to temp directory and OCR
            page_results = []
            semaphore = asyncio.Semaphore(self._parallel_pages)

            async def ocr_page_image(page_num: int, image):
                async with semaphore:
                    # Save image to temp file
                    img_path = temp_dir / f"page_{page_num:04d}.png"
                    await asyncio.to_thread(image.save, str(img_path), "PNG")

                    try:
                        result = await self.ocr_page(
                            image_path=str(img_path),
                            engine=engine,
                            language=language,
                            use_cache=False,  # Don't cache temp files
                        )
                        return {
                            "page": page_num,
                            "path": str(img_path),
                            "text": result.get("text", ""),
                            "boxes": result.get("boxes", []),
                            "confidence": result.get("confidence"),
                        }
                    except Exception as e:
                        logger.error(f"OCR failed for page {page_num}: {e}")
                        return {
                            "page": page_num,
                            "path": str(img_path),
                            "error": str(e),
                        }

            # OCR all pages in parallel
            tasks = [
                ocr_page_image(i + 1, img)
                for i, img in enumerate(images)
            ]
            page_results = await asyncio.gather(*tasks)

            # Sort by page number
            page_results = sorted(page_results, key=lambda p: p["page"])

            # Combine results
            all_text = [p["text"] for p in page_results if p.get("text")]
            successful_pages = len([p for p in page_results if "error" not in p])

            return {
                "document_id": document_id,
                "engine": engine,
                "pages_processed": successful_pages,
                "total_pages": len(images),
                "total_text": "\n\n".join(all_text),
                "page_results": page_results,
                "status": "completed",
            }

        finally:
            # Cleanup temp directory
            if temp_dir and temp_dir.exists():
                try:
                    import shutil
                    await asyncio.to_thread(shutil.rmtree, str(temp_dir))
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")

    async def ocr_document(
        self,
        document_id: str,
        engine: str | None = None,
        language: str = "en",
    ) -> dict:
        """
        OCR all pages of a document.

        Args:
            document_id: Document ID to process
            engine: OCR engine to use
            language: Language code

        Returns:
            Combined OCR results for all pages
        """
        # Emit start event
        event_bus = self._frame.get_service("events")
        if event_bus:
            await event_bus.emit(
                "ocr.document.started",
                {"document_id": document_id, "engine": engine or self._default_engine},
                source="ocr-shard",
            )

        # Get document pages from documents service
        doc_service = self._frame.get_service("documents")
        if not doc_service:
            raise RuntimeError("Documents service not available")

        # Get pages for document (returns Page objects with image_path)
        pages = await doc_service.get_document_pages(document_id)

        # Filter to pages that have image paths
        pages_with_images = [p for p in pages if p.image_path]

        if not pages_with_images:
            # No page images - fall back to OCR'ing the original file
            logger.info(f"No page images for document {document_id}, falling back to original file OCR")
            return await self._ocr_document_from_file(
                document_id=document_id,
                doc_service=doc_service,
                engine=engine,
                language=language,
                event_bus=event_bus,
            )

        # OCR pages in parallel with concurrency limit
        selected_engine = engine or self._default_engine
        semaphore = asyncio.Semaphore(self._parallel_pages)

        async def ocr_page_with_limit(index: int, page):
            """OCR a page with concurrency limiting."""
            async with semaphore:
                try:
                    page_result = await self.ocr_page(
                        image_path=str(page.image_path),
                        engine=selected_engine,
                        language=language,
                    )
                    return {
                        "page": page.page_number,
                        "path": str(page.image_path),
                        "text": page_result.get("text", ""),
                        "boxes": page_result.get("boxes", []),
                        "confidence": page_result.get("confidence"),
                    }
                except Exception as e:
                    logger.error(f"OCR failed for page {page.page_number} of document {document_id}: {e}")
                    return {
                        "page": page.page_number,
                        "path": str(page.image_path),
                        "error": str(e),
                    }

        # Create tasks for all pages with images
        tasks = [ocr_page_with_limit(i, page) for i, page in enumerate(pages_with_images)]

        # Run in parallel with gather
        page_results = await asyncio.gather(*tasks)

        # Sort by page number (gather preserves order, but explicit is clearer)
        page_results = sorted(page_results, key=lambda p: p["page"])

        # Extract text from successful pages
        all_text = [p["text"] for p in page_results if p.get("text")]

        result = {
            "document_id": document_id,
            "engine": selected_engine,
            "pages_processed": len([p for p in page_results if "error" not in p]),
            "total_pages": len(pages_with_images),
            "total_text": "\n\n".join(all_text),
            "page_results": page_results,
            "status": "completed",
        }

        # Emit completion event
        if event_bus:
            await event_bus.emit(
                "ocr.document.completed",
                result,
                source="ocr-shard",
            )

        return result
