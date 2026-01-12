"""File type detection and classification."""

import logging
from pathlib import Path

from ..models import FileCategory, FileInfo

logger = logging.getLogger(__name__)


# File type routing configuration from WORKER_ARCHITECTURE.md
FILE_TYPE_ROUTES = {
    # Documents - extract text, then OCR images
    "document": {
        "extensions": [".pdf", ".docx", ".doc", ".odt", ".rtf"],
        "pipeline": ["cpu-extract", "IMAGES->ocr_route"],
    },
    # Images - quality check, then appropriate OCR
    "image": {
        "extensions": [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"],
        "pipeline": ["cpu-light:classify", "ROUTE_BY_QUALITY"],
    },
    # Spreadsheets - extract to structured data
    "spreadsheet": {
        "extensions": [".xlsx", ".xls", ".csv", ".tsv", ".ods"],
        "pipeline": ["cpu-extract"],
    },
    # Plain text - direct to parsing
    "text": {
        "extensions": [".txt", ".md", ".json", ".xml", ".html"],
        "pipeline": ["cpu-light"],
    },
    # Email - extract body + attachments
    "email": {
        "extensions": [".eml", ".msg"],
        "pipeline": ["cpu-extract", "RECURSE_ATTACHMENTS"],
    },
    # Archives - extract then route contents
    "archive": {
        "extensions": [".zip", ".tar", ".gz", ".7z", ".rar"],
        "pipeline": ["cpu-archive", "RECURSE"],
    },
    # Audio - transcription (optional shard)
    "audio": {
        "extensions": [".mp3", ".wav", ".m4a", ".ogg", ".flac"],
        "pipeline": ["gpu-whisper"],  # Requires audio shard
    },
}


class FileTypeClassifier:
    """
    Classifies files by type and determines processing route.
    """

    def __init__(self):
        # Build extension -> category lookup
        self._ext_to_category: dict[str, str] = {}
        for category, config in FILE_TYPE_ROUTES.items():
            for ext in config["extensions"]:
                self._ext_to_category[ext.lower()] = category

        # Try to import magic for MIME detection
        self._magic = None
        try:
            import magic
            self._magic = magic
        except ImportError:
            logger.warning("python-magic not available, using extension-only detection")

    def classify(self, path: Path) -> FileInfo:
        """
        Classify a file and return FileInfo.
        """
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Basic info
        stat = path.stat()
        extension = path.suffix.lower()

        # MIME type detection
        mime_type = self._detect_mime(path)

        # Category from extension (fallback to MIME)
        category = self._get_category(extension, mime_type)

        file_info = FileInfo(
            path=path,
            original_name=path.name,
            size_bytes=stat.st_size,
            mime_type=mime_type,
            category=category,
            extension=extension,
        )

        # Add image dimensions if applicable
        if category == FileCategory.IMAGE:
            self._add_image_info(file_info)

        # Add page count for PDFs
        if extension == ".pdf":
            self._add_pdf_info(file_info)

        return file_info

    def _detect_mime(self, path: Path) -> str:
        """Detect MIME type using python-magic or fallback."""
        if self._magic:
            try:
                return self._magic.from_file(str(path), mime=True)
            except Exception as e:
                logger.warning(f"Magic MIME detection failed: {e}")

        # Fallback: guess from extension
        ext = path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".txt": "text/plain",
            ".html": "text/html",
            ".json": "application/json",
            ".xml": "application/xml",
            ".zip": "application/zip",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
        }
        return mime_map.get(ext, "application/octet-stream")

    def _get_category(self, extension: str, mime_type: str) -> FileCategory:
        """Determine file category."""
        # Check extension first
        ext_category = self._ext_to_category.get(extension)
        if ext_category:
            return FileCategory(ext_category) if ext_category in [e.value for e in FileCategory] else FileCategory.DOCUMENT

        # Fallback to MIME type
        if mime_type.startswith("image/"):
            return FileCategory.IMAGE
        elif mime_type.startswith("audio/"):
            return FileCategory.AUDIO
        elif mime_type.startswith("text/"):
            return FileCategory.DOCUMENT
        elif mime_type == "application/pdf":
            return FileCategory.DOCUMENT
        elif "zip" in mime_type or "tar" in mime_type or "compressed" in mime_type:
            return FileCategory.ARCHIVE

        return FileCategory.UNKNOWN

    def _add_image_info(self, file_info: FileInfo) -> None:
        """Add image-specific info (dimensions, DPI)."""
        try:
            from PIL import Image
            with Image.open(file_info.path) as img:
                file_info.width, file_info.height = img.size
                # Try to get DPI from EXIF or image info
                dpi = img.info.get("dpi")
                if dpi:
                    file_info.dpi = int(dpi[0]) if isinstance(dpi, tuple) else int(dpi)
        except Exception as e:
            logger.warning(f"Could not read image info: {e}")

    def _add_pdf_info(self, file_info: FileInfo) -> None:
        """Add PDF-specific info (page count)."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_info.path)
            file_info.page_count = len(reader.pages)
        except Exception as e:
            logger.warning(f"Could not read PDF info: {e}")

    def get_route(self, file_info: FileInfo) -> list[str]:
        """
        Get the worker route for a file.
        Returns list of worker pool names.
        """
        # Find matching route config
        for category, config in FILE_TYPE_ROUTES.items():
            if file_info.extension in config["extensions"]:
                # Filter out meta-instructions like ROUTE_BY_QUALITY
                return [
                    step for step in config["pipeline"]
                    if not step.startswith("ROUTE") and not step.startswith("RECURSE") and not step.startswith("IMAGES")
                ]

        # Default route for unknown files
        return ["cpu-light"]
