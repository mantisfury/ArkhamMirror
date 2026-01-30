"""File type detection and classification."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import FileCategory, FileInfo

logger = logging.getLogger(__name__)

# Magika optional
MAGIKA_AVAILABLE = False
_magika_worker = None
try:
    from magika import Magika
    MAGIKA_AVAILABLE = True
except ImportError:
    Magika = None  # type: ignore[misc, assignment]


def _init_magika_worker() -> Any:
    """Initialize Magika worker (singleton). Returns Magika instance or None."""
    global _magika_worker
    if not MAGIKA_AVAILABLE:
        return None
    if _magika_worker is None:
        try:
            _magika_worker = Magika()
            logger.info("Magika worker initialized for file type detection")
        except Exception as e:
            logger.warning(f"Magika init failed: {e}")
            return None
    return _magika_worker


# MIME type -> (category, pipeline steps). Category is FileCategory.value; pipeline used for get_route.
# spreadsheet/text/email map to document category but have distinct pipelines.
MIME_TYPE_ROUTES: dict[str, tuple[str, list[str]]] = {
    "application/pdf": ("document", ["cpu-extract", "IMAGES->ocr_route"]),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ("document", ["cpu-extract", "IMAGES->ocr_route"]),
    "application/msword": ("document", ["cpu-extract", "IMAGES->ocr_route"]),
    "application/vnd.oasis.opendocument.text": ("document", ["cpu-extract", "IMAGES->ocr_route"]),
    "application/rtf": ("document", ["cpu-extract", "IMAGES->ocr_route"]),
    "image/png": ("image", ["cpu-light:classify", "ROUTE_BY_QUALITY"]),
    "image/jpeg": ("image", ["cpu-light:classify", "ROUTE_BY_QUALITY"]),
    "image/tiff": ("image", ["cpu-light:classify", "ROUTE_BY_QUALITY"]),
    "image/bmp": ("image", ["cpu-light:classify", "ROUTE_BY_QUALITY"]),
    "image/webp": ("image", ["cpu-light:classify", "ROUTE_BY_QUALITY"]),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ("document", ["cpu-extract"]),
    "application/vnd.ms-excel": ("document", ["cpu-extract"]),
    "text/csv": ("document", ["cpu-extract"]),
    "text/tab-separated-values": ("document", ["cpu-extract"]),
    "application/vnd.oasis.opendocument.spreadsheet": ("document", ["cpu-extract"]),
    "text/plain": ("document", ["cpu-light"]),
    "text/markdown": ("document", ["cpu-light"]),
    "application/json": ("document", ["cpu-light"]),
    "application/xml": ("document", ["cpu-light"]),
    "text/xml": ("document", ["cpu-light"]),
    "text/html": ("document", ["cpu-light"]),
    "message/rfc822": ("document", ["cpu-extract", "RECURSE_ATTACHMENTS"]),
    "application/vnd.ms-outlook": ("document", ["cpu-extract", "RECURSE_ATTACHMENTS"]),
    "application/zip": ("archive", ["cpu-archive", "RECURSE"]),
    "application/x-tar": ("archive", ["cpu-archive", "RECURSE"]),
    "application/gzip": ("archive", ["cpu-archive", "RECURSE"]),
    "application/x-bzip2": ("archive", ["cpu-archive", "RECURSE"]),
    "application/x-7z-compressed": ("archive", ["cpu-archive", "RECURSE"]),
    "application/vnd.rar": ("archive", ["cpu-archive", "RECURSE"]),
    "application/x-rar-compressed": ("archive", ["cpu-archive", "RECURSE"]),
    "audio/mpeg": ("audio", ["gpu-whisper"]),
    "audio/wav": ("audio", ["gpu-whisper"]),
    "audio/x-wav": ("audio", ["gpu-whisper"]),
    "audio/mp4": ("audio", ["gpu-whisper"]),
    "audio/ogg": ("audio", ["gpu-whisper"]),
    "audio/flac": ("audio", ["gpu-whisper"]),
}

# Extension -> mime_type for fallback when magic/Magika unavailable
EXTENSION_MIME_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".rtf": "application/rtf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".xml": "application/xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".eml": "message/rfc822",
    ".emlx": "message/rfc822",
    ".msg": "application/vnd.ms-outlook",
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".tgz": "application/gzip",
    ".bz2": "application/x-bzip2",
    ".7z": "application/x-7z-compressed",
    ".rar": "application/vnd.rar",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}

# Typical archives eligible for extraction (zip, tar, gz, bz2, 7z, rar). Only these run cpu-archive extract.
TYPICAL_ARCHIVE_MIMES: frozenset[str] = frozenset({
    "application/zip",
    "application/x-tar",
    "application/gzip",
    "application/x-bzip2",
    "application/x-7z-compressed",
    "application/vnd.rar",
    "application/x-rar-compressed",
})

# Container formats that are logically archives but handled by other pipelines (document/spreadsheet).
# Only set is_archive=True; do not run through extract-archive.
CONTAINER_ARCHIVE_MIMES: frozenset[str] = frozenset({
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "application/java-archive",
})
CONTAINER_ARCHIVE_EXTENSIONS: frozenset[str] = frozenset({
    ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".jar",
})


class FileTypeClassifier:
    """
    Classifies files by type and determines processing route.
    Uses mime_type (from Magika or python-magic) for routing; unknown types get no auto-route.
    """

    def __init__(self, use_magika: bool = True):
        """
        Args:
            use_magika: If True and Magika is available, use it for content-based MIME detection.
        """
        self._use_magika = use_magika and MAGIKA_AVAILABLE
        self._magic = None
        if not self._use_magika:
            try:
                import magic
                self._magic = magic
            except ImportError:
                logger.warning("python-magic not available, using extension-only detection")

    def classify(self, path: Path) -> FileInfo:
        """
        Classify a file and return FileInfo.
        Unknown types (e.g. application/octet-stream) get category UNKNOWN and no auto-route.
        """
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        stat = path.stat()
        extension = path.suffix.lower() if path.suffix else ""

        # MIME detection: Magika -> python-magic -> extension
        mime_type, confidence, method = self._detect_mime(path, extension)
        if not mime_type:
            mime_type = EXTENSION_MIME_MAP.get(extension, "application/octet-stream")
            method = "extension"
            confidence = 0.5

        # Extension fidelity: does extension match expected for this mime?
        expected_ext = self._mime_to_extension(mime_type)
        extension_fidelity = bool(
            extension and expected_ext and
            extension.lstrip(".").lower() == expected_ext.lstrip(".").lower()
        )

        # Category from mime_type (primary); unknown if octet-stream or low confidence
        category = self._get_category_from_mime(mime_type, extension, confidence)

        # Stat times
        access_time = datetime.fromtimestamp(stat.st_atime) if hasattr(stat, "st_atime") else None
        modification_time = datetime.fromtimestamp(stat.st_mtime) if hasattr(stat, "st_mtime") else None
        if hasattr(stat, "st_birthtime"):
            creation_time = datetime.fromtimestamp(stat.st_birthtime)
        else:
            creation_time = datetime.fromtimestamp(stat.st_ctime) if hasattr(stat, "st_ctime") else None

        # is_archive: typical archives (zip, tar, etc.) or container formats (docx, xlsx, jar)
        is_archive = (
            category == FileCategory.ARCHIVE or
            mime_type in CONTAINER_ARCHIVE_MIMES or
            extension in CONTAINER_ARCHIVE_EXTENSIONS
        )

        file_info = FileInfo(
            path=path,
            original_name=path.name,
            size_bytes=stat.st_size,
            mime_type=mime_type,
            category=category,
            extension=extension,
            extension_fidelity=extension_fidelity,
            access_time=access_time,
            modification_time=modification_time,
            creation_time=creation_time,
            is_archive=is_archive,
        )

        if category == FileCategory.IMAGE:
            self._add_image_info(file_info)
        if mime_type == "application/pdf" or extension == ".pdf":
            self._add_pdf_info(file_info)

        return file_info

    def _detect_mime(self, path: Path, extension: str) -> tuple[str | None, float, str]:
        """
        Detect MIME type. Returns (mime_type, confidence, method).
        method is 'magika', 'magic', or 'extension'.
        """
        if self._use_magika:
            worker = _init_magika_worker()
            if worker:
                try:
                    res = worker.identify_path(str(path))
                    if res and getattr(res, "ok", False) and getattr(res, "output", None):
                        out = res.output
                        mime = getattr(out, "mime_type", None) or getattr(out, "mime", None)
                        score = float(getattr(res, "score", getattr(out, "score", 0.0)))
                        if mime:
                            return (mime, score, "magika")
                except Exception as e:
                    logger.debug(f"Magika identify failed: {e}")

        if self._magic:
            try:
                mime = self._magic.from_file(str(path), mime=True)
                if mime and mime != "application/octet-stream":
                    return (mime, 0.8, "magic")
            except Exception as e:
                logger.warning(f"Magic MIME detection failed: {e}")

        mime = EXTENSION_MIME_MAP.get(extension)
        return (mime, 0.5, "extension") if mime else (None, 0.0, "extension")

    def _mime_to_extension(self, mime_type: str) -> str | None:
        """Return typical extension for a mime type (for fidelity check)."""
        for ext, mime in EXTENSION_MIME_MAP.items():
            if mime == mime_type:
                return ext
        return None

    def _get_category_from_mime(self, mime_type: str, extension: str, confidence: float) -> FileCategory:
        """Determine category from mime_type. UNKNOWN if octet-stream or low confidence."""
        if mime_type == "application/octet-stream" or confidence < 0.3:
            return FileCategory.UNKNOWN

        if mime_type in MIME_TYPE_ROUTES:
            cat, _ = MIME_TYPE_ROUTES[mime_type]
            if cat in [e.value for e in FileCategory]:
                return FileCategory(cat)

        # Generic mime prefixes
        if mime_type.startswith("image/"):
            return FileCategory.IMAGE
        if mime_type.startswith("audio/"):
            return FileCategory.AUDIO
        if mime_type.startswith("text/"):
            return FileCategory.DOCUMENT
        if "pdf" in mime_type:
            return FileCategory.DOCUMENT
        if "zip" in mime_type or "tar" in mime_type or "compressed" in mime_type or "gzip" in mime_type or "rar" in mime_type:
            return FileCategory.ARCHIVE

        # Extension fallback for known types
        ext_mime = EXTENSION_MIME_MAP.get(extension)
        if ext_mime and ext_mime in MIME_TYPE_ROUTES:
            cat, _ = MIME_TYPE_ROUTES[ext_mime]
            if cat in [e.value for e in FileCategory]:
                return FileCategory(cat)

        return FileCategory.UNKNOWN

    def _add_image_info(self, file_info: FileInfo) -> None:
        """Add image dimensions and DPI."""
        try:
            from PIL import Image
            with Image.open(file_info.path) as img:
                file_info.width, file_info.height = img.size
                dpi = img.info.get("dpi")
                if dpi:
                    file_info.dpi = int(dpi[0]) if isinstance(dpi, tuple) else int(dpi)
        except Exception as e:
            logger.warning(f"Could not read image info: {e}")

    def _add_pdf_info(self, file_info: FileInfo) -> None:
        """Add PDF page count."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_info.path)
            file_info.page_count = len(reader.pages)
        except Exception as e:
            logger.warning(f"Could not read PDF info: {e}")

    def get_route(self, file_info: FileInfo) -> list[str]:
        """
        Get the worker route for a file. Based on mime_type.
        Returns empty list for UNKNOWN category (no auto-route; requires manual override).
        """
        if file_info.category == FileCategory.UNKNOWN:
            return []

        mime_type = file_info.mime_type
        if mime_type in MIME_TYPE_ROUTES:
            _, pipeline = MIME_TYPE_ROUTES[mime_type]
            return [
                step for step in pipeline
                if not step.startswith("ROUTE") and not step.startswith("RECURSE") and not step.startswith("IMAGES")
            ]

        # Generic by category (mime not in map)
        if file_info.category == FileCategory.IMAGE:
            return ["cpu-light:classify", "ROUTE_BY_QUALITY"]
        if file_info.category == FileCategory.ARCHIVE:
            return ["cpu-archive"]
        if file_info.category == FileCategory.DOCUMENT:
            return ["cpu-extract", "IMAGES->ocr_route"]
        if file_info.category == FileCategory.AUDIO:
            return ["gpu-whisper"]

        return []
