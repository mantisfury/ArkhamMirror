"""
StorageService - File and blob storage management.

Provides unified file storage for documents, exports, temp files, and models.
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
import logging
import uuid
import hashlib
import json
import shutil
import asyncio
import os

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class FileNotFoundError(StorageError):
    """File not found in storage."""
    pass


class StorageFullError(StorageError):
    """Storage capacity exceeded."""
    pass


class InvalidPathError(StorageError):
    """Invalid or unsafe path."""
    pass


@dataclass
class FileInfo:
    """Information about a stored file."""
    storage_id: str
    filename: str
    path: str
    size_bytes: int
    mime_type: Optional[str]
    checksum: str
    created_at: datetime
    modified_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StorageStats:
    """Storage statistics."""
    total_bytes: int
    used_bytes: int
    available_bytes: int
    file_count: int
    by_category: Dict[str, int] = field(default_factory=dict)


class StorageService:
    """
    File and blob storage management service.

    Storage locations:
    - {DATA_SILO}/documents/ - Ingested documents
    - {DATA_SILO}/exports/ - Generated exports
    - {DATA_SILO}/temp/ - Temporary processing files
    - {DATA_SILO}/models/ - Cached ML models
    - {DATA_SILO}/projects/{project_id}/ - Project-scoped storage
    """

    # Storage subdirectories
    STORAGE_CATEGORIES = {
        "documents": "documents",
        "exports": "exports",
        "temp": "temp",
        "models": "models",
        "projects": "projects",
    }

    def __init__(self, config=None):
        """
        Initialize StorageService.

        Args:
            config: ConfigService instance for settings
        """
        self.config = config
        self.base_path: Optional[Path] = None
        self.max_file_size_mb: int = 500
        self.cleanup_temp_after_hours: int = 24
        self._initialized = False
        self._metadata_cache: Dict[str, FileInfo] = {}

    async def initialize(self) -> None:
        """Initialize storage service and create directory structure."""
        logger.info("Initializing StorageService...")

        # Get base path from config or use default
        if self.config:
            base_path_str = self.config.get("storage.base_path", "./data_silo")
            self.max_file_size_mb = self.config.get("storage.max_file_size_mb", 500)
            self.cleanup_temp_after_hours = self.config.get("storage.cleanup_temp_after_hours", 24)
        else:
            base_path_str = "./data_silo"

        # Resolve relative path from current working directory
        self.base_path = Path(base_path_str).resolve()

        # Create directory structure
        for category in self.STORAGE_CATEGORIES.values():
            category_path = self.base_path / category
            category_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured storage directory: {category_path}")

        # Load metadata cache
        await self._load_metadata_cache()

        self._initialized = True
        logger.info(f"StorageService initialized at {self.base_path}")

    async def shutdown(self) -> None:
        """Shutdown storage service."""
        logger.info("Shutting down StorageService...")

        # Persist metadata cache
        await self._save_metadata_cache()

        # Cleanup old temp files
        await self.cleanup_temp_files()

        self._initialized = False
        logger.info("StorageService shutdown complete")

    # =========================================================================
    # File Operations
    # =========================================================================

    async def store(
        self,
        path: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        category: str = "documents",
    ) -> str:
        """
        Store content to a file.

        Args:
            path: Relative path within category (e.g., "2024/01/doc.pdf")
            content: File content as bytes
            metadata: Optional metadata to store with file
            category: Storage category (documents, exports, temp, models)

        Returns:
            storage_id: Unique identifier for the stored file

        Raises:
            StorageFullError: If file exceeds max size
            InvalidPathError: If path contains unsafe characters
        """
        self._ensure_initialized()

        # Validate size
        size_mb = len(content) / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            raise StorageFullError(
                f"File size {size_mb:.1f}MB exceeds maximum {self.max_file_size_mb}MB"
            )

        # Validate and sanitize path
        safe_path = self._sanitize_path(path)

        # Generate storage ID
        storage_id = self._generate_storage_id(category, safe_path)

        # Determine full path
        if category not in self.STORAGE_CATEGORIES:
            category = "documents"
        full_path = self.base_path / self.STORAGE_CATEGORIES[category] / safe_path

        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        await asyncio.to_thread(full_path.write_bytes, content)

        # Calculate checksum
        checksum = hashlib.sha256(content).hexdigest()

        # Detect mime type from extension
        mime_type = self._guess_mime_type(safe_path)

        # Create file info
        now = datetime.utcnow()
        file_info = FileInfo(
            storage_id=storage_id,
            filename=Path(safe_path).name,
            path=str(full_path.relative_to(self.base_path)),
            size_bytes=len(content),
            mime_type=mime_type,
            checksum=checksum,
            created_at=now,
            modified_at=now,
            metadata=metadata or {},
        )

        # Cache metadata
        self._metadata_cache[storage_id] = file_info

        logger.debug(f"Stored file: {storage_id} -> {full_path}")
        return storage_id

    async def retrieve(self, storage_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Retrieve file content and metadata.

        Args:
            storage_id: Unique file identifier

        Returns:
            Tuple of (content bytes, metadata dict)

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        self._ensure_initialized()

        file_info = self._metadata_cache.get(storage_id)
        if not file_info:
            raise FileNotFoundError(f"File not found: {storage_id}")

        full_path = self.base_path / file_info.path

        if not full_path.exists():
            # Remove from cache if file is gone
            del self._metadata_cache[storage_id]
            raise FileNotFoundError(f"File not found on disk: {storage_id}")

        content = await asyncio.to_thread(full_path.read_bytes)

        return content, file_info.metadata

    async def delete(self, storage_id: str) -> bool:
        """
        Delete a stored file.

        Args:
            storage_id: Unique file identifier

        Returns:
            True if deleted, False if not found
        """
        self._ensure_initialized()

        file_info = self._metadata_cache.get(storage_id)
        if not file_info:
            return False

        full_path = self.base_path / file_info.path

        try:
            if full_path.exists():
                await asyncio.to_thread(full_path.unlink)

            # Remove from cache
            del self._metadata_cache[storage_id]

            logger.debug(f"Deleted file: {storage_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete {storage_id}: {e}")
            return False

    async def exists(self, storage_id: str) -> bool:
        """Check if a file exists."""
        self._ensure_initialized()

        file_info = self._metadata_cache.get(storage_id)
        if not file_info:
            return False

        full_path = self.base_path / file_info.path
        return full_path.exists()

    async def get_file_info(self, storage_id: str) -> Optional[FileInfo]:
        """Get file information without retrieving content."""
        self._ensure_initialized()
        return self._metadata_cache.get(storage_id)

    # =========================================================================
    # Temp File Operations
    # =========================================================================

    async def create_temp(self, suffix: str = "", prefix: str = "tmp_") -> str:
        """
        Create a temporary file path.

        Args:
            suffix: File suffix (e.g., ".pdf")
            prefix: File prefix

        Returns:
            Full path to temp file (file is NOT created, just path reserved)
        """
        self._ensure_initialized()

        temp_dir = self.base_path / self.STORAGE_CATEGORIES["temp"]

        # Create unique filename
        unique_id = uuid.uuid4().hex[:12]
        filename = f"{prefix}{unique_id}{suffix}"
        temp_path = temp_dir / filename

        logger.debug(f"Created temp path: {temp_path}")
        return str(temp_path)

    async def cleanup_temp(self, path: str) -> None:
        """
        Clean up a specific temp file.

        Args:
            path: Path returned by create_temp
        """
        self._ensure_initialized()

        temp_path = Path(path)

        # Validate it's in temp directory
        temp_dir = self.base_path / self.STORAGE_CATEGORIES["temp"]
        try:
            temp_path.relative_to(temp_dir)
        except ValueError:
            raise InvalidPathError(f"Path is not in temp directory: {path}")

        if temp_path.exists():
            await asyncio.to_thread(temp_path.unlink)
            logger.debug(f"Cleaned up temp file: {temp_path}")

    async def cleanup_temp_files(self, max_age_hours: Optional[int] = None) -> int:
        """
        Clean up old temp files.

        Args:
            max_age_hours: Max age in hours (uses config default if not specified)

        Returns:
            Number of files deleted
        """
        self._ensure_initialized()

        if max_age_hours is None:
            max_age_hours = self.cleanup_temp_after_hours

        temp_dir = self.base_path / self.STORAGE_CATEGORIES["temp"]
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        deleted_count = 0

        for temp_file in temp_dir.iterdir():
            if temp_file.is_file():
                mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        await asyncio.to_thread(temp_file.unlink)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {temp_file}: {e}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old temp files")

        return deleted_count

    # =========================================================================
    # Directory Operations
    # =========================================================================

    async def list_files(
        self,
        prefix: str = "",
        category: str = "documents",
        limit: int = 100,
        offset: int = 0,
    ) -> List[FileInfo]:
        """
        List files matching a prefix.

        Args:
            prefix: Path prefix to filter by
            category: Storage category
            limit: Maximum files to return
            offset: Number of files to skip

        Returns:
            List of FileInfo objects
        """
        self._ensure_initialized()

        results = []
        for storage_id, file_info in self._metadata_cache.items():
            if storage_id.startswith(f"{category}:"):
                if not prefix or file_info.path.startswith(prefix):
                    results.append(file_info)

        # Sort by modified date descending
        results.sort(key=lambda f: f.modified_at, reverse=True)

        return results[offset:offset + limit]

    async def get_storage_stats(self) -> StorageStats:
        """Get storage statistics."""
        self._ensure_initialized()

        by_category: Dict[str, int] = {}
        total_size = 0
        file_count = 0

        for category, subdir in self.STORAGE_CATEGORIES.items():
            category_path = self.base_path / subdir
            category_size = 0

            if category_path.exists():
                for file_path in category_path.rglob("*"):
                    if file_path.is_file():
                        category_size += file_path.stat().st_size
                        file_count += 1

            by_category[category] = category_size
            total_size += category_size

        # Get disk space
        try:
            disk_usage = shutil.disk_usage(self.base_path)
            total_bytes = disk_usage.total
            available_bytes = disk_usage.free
        except Exception:
            total_bytes = 0
            available_bytes = 0

        return StorageStats(
            total_bytes=total_bytes,
            used_bytes=total_size,
            available_bytes=available_bytes,
            file_count=file_count,
            by_category=by_category,
        )

    # =========================================================================
    # Project-scoped Storage
    # =========================================================================

    async def get_project_path(self, project_id: str) -> str:
        """
        Get the storage path for a project.

        Args:
            project_id: Project identifier

        Returns:
            Full path to project storage directory
        """
        self._ensure_initialized()

        # Sanitize project ID
        safe_project_id = self._sanitize_path(project_id).replace("/", "_")
        project_path = self.base_path / self.STORAGE_CATEGORIES["projects"] / safe_project_id

        # Ensure it exists
        project_path.mkdir(parents=True, exist_ok=True)

        return str(project_path)

    async def migrate_to_project(self, storage_id: str, project_id: str) -> str:
        """
        Move a file to project-scoped storage.

        Args:
            storage_id: Current storage ID
            project_id: Target project

        Returns:
            New storage ID
        """
        self._ensure_initialized()

        # Get current file info
        file_info = self._metadata_cache.get(storage_id)
        if not file_info:
            raise FileNotFoundError(f"File not found: {storage_id}")

        # Read content
        content, metadata = await self.retrieve(storage_id)

        # Store in project location
        project_path = await self.get_project_path(project_id)
        relative_path = f"{project_id}/{file_info.filename}"

        new_storage_id = await self.store(
            relative_path,
            content,
            metadata=metadata,
            category="projects",
        )

        # Delete old file
        await self.delete(storage_id)

        return new_storage_id

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _ensure_initialized(self) -> None:
        """Ensure service is initialized."""
        if not self._initialized:
            raise StorageError("StorageService not initialized")

    def _sanitize_path(self, path: str) -> str:
        """
        Sanitize a path to prevent directory traversal.

        Args:
            path: Input path

        Returns:
            Safe path

        Raises:
            InvalidPathError: If path is unsafe
        """
        # Convert to Path and normalize
        normalized = Path(path).as_posix()

        # Remove leading slashes
        normalized = normalized.lstrip("/")

        # Check for directory traversal
        if ".." in normalized or normalized.startswith("/"):
            raise InvalidPathError(f"Unsafe path: {path}")

        # Remove any null bytes or other dangerous characters
        dangerous_chars = ["\x00", "\n", "\r"]
        for char in dangerous_chars:
            if char in normalized:
                raise InvalidPathError(f"Path contains dangerous characters: {path}")

        return normalized

    def _generate_storage_id(self, category: str, path: str) -> str:
        """Generate unique storage ID."""
        unique = uuid.uuid4().hex[:8]
        return f"{category}:{unique}:{path}"

    def _guess_mime_type(self, path: str) -> Optional[str]:
        """Guess MIME type from file extension."""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(path)
        return mime_type

    async def _load_metadata_cache(self) -> None:
        """Load metadata cache from disk."""
        cache_path = self.base_path / ".storage_metadata.json"

        if cache_path.exists():
            try:
                data = await asyncio.to_thread(cache_path.read_text)
                cache_data = json.loads(data)

                for storage_id, info_dict in cache_data.items():
                    # Convert dates back to datetime
                    info_dict["created_at"] = datetime.fromisoformat(info_dict["created_at"])
                    info_dict["modified_at"] = datetime.fromisoformat(info_dict["modified_at"])
                    self._metadata_cache[storage_id] = FileInfo(**info_dict)

                logger.debug(f"Loaded {len(self._metadata_cache)} entries from metadata cache")
            except Exception as e:
                logger.warning(f"Failed to load metadata cache: {e}")

    async def _save_metadata_cache(self) -> None:
        """Save metadata cache to disk."""
        cache_path = self.base_path / ".storage_metadata.json"

        try:
            cache_data = {}
            for storage_id, file_info in self._metadata_cache.items():
                cache_data[storage_id] = {
                    "storage_id": file_info.storage_id,
                    "filename": file_info.filename,
                    "path": file_info.path,
                    "size_bytes": file_info.size_bytes,
                    "mime_type": file_info.mime_type,
                    "checksum": file_info.checksum,
                    "created_at": file_info.created_at.isoformat(),
                    "modified_at": file_info.modified_at.isoformat(),
                    "metadata": file_info.metadata,
                }

            data = json.dumps(cache_data, indent=2)
            await asyncio.to_thread(cache_path.write_text, data)

            logger.debug(f"Saved {len(cache_data)} entries to metadata cache")
        except Exception as e:
            logger.warning(f"Failed to save metadata cache: {e}")

    def get_base_path(self) -> Optional[Path]:
        """Get the base storage path."""
        return self.base_path

    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized
