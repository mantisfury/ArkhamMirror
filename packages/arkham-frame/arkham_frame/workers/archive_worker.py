"""
ArchiveWorker - Archive extraction and manipulation.

Handles extraction, listing, and creation of various archive formats including
ZIP, TAR, GZIP, BZ2, 7z, and RAR. Part of the cpu-archive worker pool for
file archive operations.
"""

import asyncio
import gzip
import bz2
import logging
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import BaseWorker

logger = logging.getLogger(__name__)


class ArchiveWorker(BaseWorker):
    """
    Worker for archive file operations.

    Supports ZIP, TAR (including compressed variants), GZIP, BZ2, 7z, and RAR
    formats. Provides extraction, listing, creation, and integrity testing.

    Security features:
    - Path traversal prevention
    - Zip bomb detection
    - File size and count limits

    Uses the cpu-archive pool for archive processing tasks.
    """

    pool = "cpu-archive"
    name = "ArchiveWorker"

    # Configuration
    poll_interval = 1.0
    heartbeat_interval = 10.0
    idle_timeout = 300.0  # 5 minutes
    job_timeout = 300.0   # 5 minutes for large archives
    max_retries = 2

    # Security limits
    MAX_FILES = 10000  # Max files in archive
    MAX_UNCOMPRESSED_SIZE = 10 * 1024 * 1024 * 1024  # 10GB total uncompressed
    MAX_COMPRESSION_RATIO = 1000  # Detect zip bombs

    def __init__(self, *args, **kwargs):
        """Initialize worker and check for optional dependencies."""
        super().__init__(*args, **kwargs)
        self._check_dependencies()

    def _check_dependencies(self):
        """Check which archive libraries are available."""
        self._has_py7zr = False
        self._has_rarfile = False

        try:
            import py7zr
            self._has_py7zr = True
            logger.info("py7zr available - 7z format supported")
        except ImportError:
            logger.warning("py7zr not installed - 7z extraction unavailable")

        try:
            import rarfile
            self._has_rarfile = True
            logger.info("rarfile available - RAR format supported")
        except ImportError:
            logger.warning("rarfile not installed - RAR extraction unavailable")

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an archive operation.

        Payload:
            operation: str - Operation type (extract, extract_file, list, info, create, test)
            archive_path: str - Path to archive file (for most operations)
            output_dir: str - Output directory (for extract operations)
            output_path: str - Output file path (for extract_file, create)
            file_name: str - Specific file to extract (for extract_file)
            files: List[str] - Files to archive (for create)
            format: str - Archive format (for create)
            password: str - Archive password (optional)
            flatten: bool - Flatten directory structure on extract (default: False)
            compression: str - Compression method (for create, default: "deflate")

        Returns:
            dict with operation-specific results and success status

        Raises:
            ValueError: If required parameters are missing or invalid
            FileNotFoundError: If file doesn't exist
            Exception: For other processing errors
        """
        operation = payload.get("operation")

        if not operation:
            raise ValueError("Missing required parameter: operation")

        # Dispatch to appropriate handler
        if operation == "extract":
            return await self._extract_archive(payload, job_id)
        elif operation == "extract_file":
            return await self._extract_single_file(payload, job_id)
        elif operation == "list":
            return await self._list_archive(payload, job_id)
        elif operation == "info":
            return await self._get_archive_info(payload, job_id)
        elif operation == "create":
            return await self._create_archive(payload, job_id)
        elif operation == "test":
            return await self._test_archive(payload, job_id)
        else:
            raise ValueError(
                f"Unknown operation: {operation}. "
                "Supported: extract, extract_file, list, info, create, test"
            )

    def _detect_format(self, path: Path) -> str:
        """
        Detect archive format from extension and magic bytes.

        Args:
            path: Path to archive file

        Returns:
            Format string (zip, tar, tar.gz, tar.bz2, tar.xz, gz, bz2, 7z, rar)

        Raises:
            ValueError: If format cannot be detected
        """
        ext = path.suffix.lower()

        # Check double extensions first
        full_ext = "".join(path.suffixes[-2:]).lower() if len(path.suffixes) >= 2 else ""

        ext_map = {
            ".tar.gz": "tar.gz",
            ".tgz": "tar.gz",
            ".tar.bz2": "tar.bz2",
            ".tbz2": "tar.bz2",
            ".tar.xz": "tar.xz",
            ".txz": "tar.xz",
        }

        if full_ext in ext_map:
            return ext_map[full_ext]

        # Single extension
        ext_map_single = {
            ".zip": "zip",
            ".tar": "tar",
            ".gz": "gz",
            ".bz2": "bz2",
            ".7z": "7z",
            ".rar": "rar",
        }

        if ext in ext_map_single:
            return ext_map_single[ext]

        # Try magic bytes
        try:
            with open(path, "rb") as f:
                magic = f.read(8)

                # ZIP magic: PK\x03\x04
                if magic.startswith(b"PK\x03\x04"):
                    return "zip"
                # GZIP magic: \x1f\x8b
                elif magic.startswith(b"\x1f\x8b"):
                    return "gz"
                # BZ2 magic: BZ
                elif magic.startswith(b"BZ"):
                    return "bz2"
                # 7z magic: 7z\xBC\xAF\x27\x1C
                elif magic.startswith(b"7z\xBC\xAF\x27\x1C"):
                    return "7z"
                # RAR magic: Rar!\x1A\x07
                elif magic.startswith(b"Rar!\x1A\x07"):
                    return "rar"
                # TAR (ustar format): check at offset 257
                f.seek(257)
                tar_magic = f.read(5)
                if tar_magic == b"ustar":
                    return "tar"
        except Exception as e:
            logger.warning(f"Could not read magic bytes: {e}")

        raise ValueError(
            f"Could not detect archive format for {path.name}. "
            "Supported extensions: .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tbz2, "
            ".tar.xz, .gz, .bz2, .7z, .rar"
        )

    def _sanitize_path(self, base_dir: Path, archive_path: str) -> Path:
        """
        Sanitize extracted file path to prevent directory traversal.

        Args:
            base_dir: Base directory for extraction
            archive_path: Path from archive member

        Returns:
            Sanitized absolute path

        Raises:
            ValueError: If path attempts directory traversal
        """
        # Remove leading slashes and backslashes
        clean_path = archive_path.lstrip("/\\")

        # Resolve path components
        parts = Path(clean_path).parts

        # Check for directory traversal
        for part in parts:
            if part == "..":
                raise ValueError(
                    f"Path traversal detected in archive member: {archive_path}"
                )

        # Build final path
        final_path = base_dir / clean_path

        # Ensure it's actually within base_dir
        try:
            final_path.resolve().relative_to(base_dir.resolve())
        except ValueError:
            raise ValueError(
                f"Archive member escapes output directory: {archive_path}"
            )

        return final_path

    def _check_zip_bomb(self, archive_path: Path, format_type: str) -> None:
        """
        Check for zip bomb (excessive compression ratio).

        Args:
            archive_path: Path to archive
            format_type: Archive format

        Raises:
            ValueError: If archive appears to be a zip bomb
        """
        compressed_size = archive_path.stat().st_size

        # Get uncompressed size estimate
        uncompressed_size = 0
        file_count = 0

        try:
            if format_type == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for info in zf.infolist():
                        if not info.is_dir():
                            uncompressed_size += info.file_size
                            file_count += 1
            elif format_type.startswith("tar"):
                with tarfile.open(archive_path, "r") as tf:
                    for member in tf.getmembers():
                        if member.isfile():
                            uncompressed_size += member.size
                            file_count += 1
            else:
                # Can't check other formats easily
                return

            # Check file count limit
            if file_count > self.MAX_FILES:
                raise ValueError(
                    f"Archive contains too many files: {file_count} > {self.MAX_FILES}"
                )

            # Check total size limit
            if uncompressed_size > self.MAX_UNCOMPRESSED_SIZE:
                raise ValueError(
                    f"Archive uncompressed size too large: "
                    f"{uncompressed_size / (1024**3):.1f}GB > "
                    f"{self.MAX_UNCOMPRESSED_SIZE / (1024**3):.1f}GB"
                )

            # Check compression ratio (avoid division by zero)
            if compressed_size > 0:
                ratio = uncompressed_size / compressed_size
                if ratio > self.MAX_COMPRESSION_RATIO:
                    raise ValueError(
                        f"Suspicious compression ratio: {ratio:.0f}x "
                        f"(possible zip bomb)"
                    )

        except zipfile.BadZipFile as e:
            raise ValueError(f"Corrupt archive: {e}")
        except tarfile.TarError as e:
            raise ValueError(f"Corrupt archive: {e}")

    async def _extract_archive(self, payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """
        Extract all files from archive.

        Payload:
            archive_path: str - Path to archive
            output_dir: str - Output directory
            password: str - Optional password
            flatten: bool - Flatten directory structure (default: False)

        Returns:
            dict with files list, count, total_size, success
        """
        archive_path = payload.get("archive_path")
        output_dir = payload.get("output_dir")
        password = payload.get("password")
        flatten = payload.get("flatten", False)

        if not archive_path:
            raise ValueError("Missing required parameter: archive_path")
        if not output_dir:
            raise ValueError("Missing required parameter: output_dir")

        archive_path = Path(archive_path)
        output_dir = Path(output_dir)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        # Detect format
        format_type = self._detect_format(archive_path)
        logger.info(f"Extracting {format_type} archive: {archive_path.name} (job {job_id})")

        # Check for zip bomb
        self._check_zip_bomb(archive_path, format_type)

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run extraction in executor
        def extract():
            extracted_files = []
            total_size = 0

            if format_type == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    if password:
                        zf.setpassword(password.encode("utf-8"))

                    for member in zf.namelist():
                        # Skip directories
                        if member.endswith("/"):
                            continue

                        # Determine output path
                        if flatten:
                            out_path = output_dir / Path(member).name
                        else:
                            out_path = self._sanitize_path(output_dir, member)

                        # Create parent directories
                        out_path.parent.mkdir(parents=True, exist_ok=True)

                        # Extract file
                        with zf.open(member) as source, open(out_path, "wb") as target:
                            data = source.read()
                            target.write(data)
                            total_size += len(data)

                        extracted_files.append(str(out_path))

            elif format_type.startswith("tar"):
                mode = "r"
                if format_type == "tar.gz":
                    mode = "r:gz"
                elif format_type == "tar.bz2":
                    mode = "r:bz2"
                elif format_type == "tar.xz":
                    mode = "r:xz"

                with tarfile.open(archive_path, mode) as tf:
                    for member in tf.getmembers():
                        # Skip non-files
                        if not member.isfile():
                            continue

                        # Determine output path
                        if flatten:
                            out_path = output_dir / Path(member.name).name
                        else:
                            out_path = self._sanitize_path(output_dir, member.name)

                        # Create parent directories
                        out_path.parent.mkdir(parents=True, exist_ok=True)

                        # Extract file
                        with tf.extractfile(member) as source, open(out_path, "wb") as target:
                            data = source.read()
                            target.write(data)
                            total_size += len(data)

                        extracted_files.append(str(out_path))

            elif format_type == "gz":
                # Single file GZIP
                out_path = output_dir / archive_path.stem
                with gzip.open(archive_path, "rb") as source, open(out_path, "wb") as target:
                    data = source.read()
                    target.write(data)
                    total_size = len(data)
                extracted_files.append(str(out_path))

            elif format_type == "bz2":
                # Single file BZ2
                out_path = output_dir / archive_path.stem
                with bz2.open(archive_path, "rb") as source, open(out_path, "wb") as target:
                    data = source.read()
                    target.write(data)
                    total_size = len(data)
                extracted_files.append(str(out_path))

            elif format_type == "7z":
                if not self._has_py7zr:
                    raise ImportError("py7zr not installed. Install with: pip install py7zr")

                import py7zr

                with py7zr.SevenZipFile(archive_path, mode="r", password=password) as archive:
                    for name, bio in archive.read().items():
                        # Determine output path
                        if flatten:
                            out_path = output_dir / Path(name).name
                        else:
                            out_path = self._sanitize_path(output_dir, name)

                        # Create parent directories
                        out_path.parent.mkdir(parents=True, exist_ok=True)

                        # Write file
                        data = bio.read()
                        with open(out_path, "wb") as target:
                            target.write(data)
                            total_size += len(data)

                        extracted_files.append(str(out_path))

            elif format_type == "rar":
                if not self._has_rarfile:
                    raise ImportError("rarfile not installed. Install with: pip install rarfile")

                import rarfile

                with rarfile.RarFile(archive_path, "r") as rf:
                    if password:
                        rf.setpassword(password)

                    for member in rf.infolist():
                        # Skip directories
                        if member.isdir():
                            continue

                        # Determine output path
                        if flatten:
                            out_path = output_dir / Path(member.filename).name
                        else:
                            out_path = self._sanitize_path(output_dir, member.filename)

                        # Create parent directories
                        out_path.parent.mkdir(parents=True, exist_ok=True)

                        # Extract file
                        with rf.open(member) as source, open(out_path, "wb") as target:
                            data = source.read()
                            target.write(data)
                            total_size += len(data)

                        extracted_files.append(str(out_path))

            else:
                raise ValueError(f"Unsupported format for extraction: {format_type}")

            return extracted_files, total_size

        loop = asyncio.get_event_loop()
        files, size = await loop.run_in_executor(None, extract)

        logger.info(
            f"Extracted {len(files)} files ({size / (1024**2):.1f}MB) from {archive_path.name}"
        )

        return {
            "files": files,
            "count": len(files),
            "total_size": size,
            "success": True,
        }

    async def _extract_single_file(self, payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """
        Extract a single file from archive.

        Payload:
            archive_path: str - Path to archive
            file_name: str - File to extract
            output_path: str - Output file path
            password: str - Optional password

        Returns:
            dict with path, size, success
        """
        archive_path = payload.get("archive_path")
        file_name = payload.get("file_name")
        output_path = payload.get("output_path")
        password = payload.get("password")

        if not archive_path:
            raise ValueError("Missing required parameter: archive_path")
        if not file_name:
            raise ValueError("Missing required parameter: file_name")
        if not output_path:
            raise ValueError("Missing required parameter: output_path")

        archive_path = Path(archive_path)
        output_path = Path(output_path)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        format_type = self._detect_format(archive_path)
        logger.info(
            f"Extracting '{file_name}' from {format_type} archive: "
            f"{archive_path.name} (job {job_id})"
        )

        # Run extraction in executor
        def extract():
            if format_type == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    if password:
                        zf.setpassword(password.encode("utf-8"))

                    with zf.open(file_name) as source:
                        data = source.read()
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, "wb") as target:
                            target.write(data)
                        return len(data)

            elif format_type.startswith("tar"):
                mode = "r"
                if format_type == "tar.gz":
                    mode = "r:gz"
                elif format_type == "tar.bz2":
                    mode = "r:bz2"
                elif format_type == "tar.xz":
                    mode = "r:xz"

                with tarfile.open(archive_path, mode) as tf:
                    member = tf.getmember(file_name)
                    with tf.extractfile(member) as source:
                        data = source.read()
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, "wb") as target:
                            target.write(data)
                        return len(data)

            elif format_type == "7z":
                if not self._has_py7zr:
                    raise ImportError("py7zr not installed")

                import py7zr

                with py7zr.SevenZipFile(archive_path, mode="r", password=password) as archive:
                    data_dict = archive.read(targets=[file_name])
                    if file_name not in data_dict:
                        raise FileNotFoundError(f"File not found in archive: {file_name}")

                    data = data_dict[file_name].read()
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as target:
                        target.write(data)
                    return len(data)

            elif format_type == "rar":
                if not self._has_rarfile:
                    raise ImportError("rarfile not installed")

                import rarfile

                with rarfile.RarFile(archive_path, "r") as rf:
                    if password:
                        rf.setpassword(password)

                    with rf.open(file_name) as source:
                        data = source.read()
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, "wb") as target:
                            target.write(data)
                        return len(data)

            else:
                raise ValueError(f"Single file extraction not supported for: {format_type}")

        loop = asyncio.get_event_loop()
        size = await loop.run_in_executor(None, extract)

        logger.info(f"Extracted '{file_name}' ({size / 1024:.1f}KB)")

        return {
            "path": str(output_path),
            "size": size,
            "success": True,
        }

    async def _list_archive(self, payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """
        List contents of archive without extracting.

        Payload:
            archive_path: str - Path to archive

        Returns:
            dict with files list (name, size, compressed, is_dir), count
        """
        archive_path = payload.get("archive_path")

        if not archive_path:
            raise ValueError("Missing required parameter: archive_path")

        archive_path = Path(archive_path)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        format_type = self._detect_format(archive_path)
        logger.info(f"Listing {format_type} archive: {archive_path.name} (job {job_id})")

        # Run listing in executor
        def list_files():
            files = []

            if format_type == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for info in zf.infolist():
                        files.append({
                            "name": info.filename,
                            "size": info.file_size,
                            "compressed": info.compress_size,
                            "is_dir": info.is_dir(),
                        })

            elif format_type.startswith("tar"):
                mode = "r"
                if format_type == "tar.gz":
                    mode = "r:gz"
                elif format_type == "tar.bz2":
                    mode = "r:bz2"
                elif format_type == "tar.xz":
                    mode = "r:xz"

                with tarfile.open(archive_path, mode) as tf:
                    for member in tf.getmembers():
                        files.append({
                            "name": member.name,
                            "size": member.size,
                            "compressed": 0,  # TAR doesn't track per-file compression
                            "is_dir": member.isdir(),
                        })

            elif format_type == "gz":
                # Single file
                files.append({
                    "name": archive_path.stem,
                    "size": 0,  # Unknown without decompression
                    "compressed": archive_path.stat().st_size,
                    "is_dir": False,
                })

            elif format_type == "bz2":
                # Single file
                files.append({
                    "name": archive_path.stem,
                    "size": 0,  # Unknown without decompression
                    "compressed": archive_path.stat().st_size,
                    "is_dir": False,
                })

            elif format_type == "7z":
                if not self._has_py7zr:
                    raise ImportError("py7zr not installed")

                import py7zr

                with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                    for name, info in archive.list():
                        files.append({
                            "name": name,
                            "size": info.uncompressed,
                            "compressed": info.compressed,
                            "is_dir": info.is_directory,
                        })

            elif format_type == "rar":
                if not self._has_rarfile:
                    raise ImportError("rarfile not installed")

                import rarfile

                with rarfile.RarFile(archive_path, "r") as rf:
                    for info in rf.infolist():
                        files.append({
                            "name": info.filename,
                            "size": info.file_size,
                            "compressed": info.compress_size,
                            "is_dir": info.isdir(),
                        })

            else:
                raise ValueError(f"Listing not supported for: {format_type}")

            return files

        loop = asyncio.get_event_loop()
        files = await loop.run_in_executor(None, list_files)

        logger.info(f"Archive contains {len(files)} items")

        return {
            "files": files,
            "count": len(files),
        }

    async def _get_archive_info(self, payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """
        Get archive metadata.

        Payload:
            archive_path: str - Path to archive

        Returns:
            dict with format, file_count, total_size, compressed_size, is_encrypted
        """
        archive_path = payload.get("archive_path")

        if not archive_path:
            raise ValueError("Missing required parameter: archive_path")

        archive_path = Path(archive_path)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        format_type = self._detect_format(archive_path)
        logger.info(f"Getting info for {format_type} archive: {archive_path.name} (job {job_id})")

        # Run info gathering in executor
        def get_info():
            file_count = 0
            total_size = 0
            compressed_size = archive_path.stat().st_size
            is_encrypted = False

            if format_type == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for info in zf.infolist():
                        if not info.is_dir():
                            file_count += 1
                            total_size += info.file_size
                        # Check for encryption
                        if info.flag_bits & 0x1:
                            is_encrypted = True

            elif format_type.startswith("tar"):
                mode = "r"
                if format_type == "tar.gz":
                    mode = "r:gz"
                elif format_type == "tar.bz2":
                    mode = "r:bz2"
                elif format_type == "tar.xz":
                    mode = "r:xz"

                with tarfile.open(archive_path, mode) as tf:
                    for member in tf.getmembers():
                        if member.isfile():
                            file_count += 1
                            total_size += member.size

            elif format_type in ["gz", "bz2"]:
                file_count = 1
                # Size unknown without decompression

            elif format_type == "7z":
                if not self._has_py7zr:
                    raise ImportError("py7zr not installed")

                import py7zr

                with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                    for name, info in archive.list():
                        if not info.is_directory:
                            file_count += 1
                            total_size += info.uncompressed
                    # Check for encryption
                    is_encrypted = archive.password_protected

            elif format_type == "rar":
                if not self._has_rarfile:
                    raise ImportError("rarfile not installed")

                import rarfile

                with rarfile.RarFile(archive_path, "r") as rf:
                    for info in rf.infolist():
                        if not info.isdir():
                            file_count += 1
                            total_size += info.file_size
                    # Check if any file is encrypted
                    is_encrypted = any(i.needs_password() for i in rf.infolist())

            else:
                raise ValueError(f"Info not supported for: {format_type}")

            return file_count, total_size, compressed_size, is_encrypted

        loop = asyncio.get_event_loop()
        count, size, comp_size, encrypted = await loop.run_in_executor(None, get_info)

        return {
            "format": format_type,
            "file_count": count,
            "total_size": size,
            "compressed_size": comp_size,
            "is_encrypted": encrypted,
        }

    async def _create_archive(self, payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """
        Create a new archive from files.

        Payload:
            output_path: str - Output archive path
            files: List[str] - Files to include
            format: str - Archive format (zip, tar, tar.gz, tar.bz2, tar.xz)
            compression: str - Compression method (default: "deflate" for ZIP)

        Returns:
            dict with path, size, file_count, success
        """
        output_path = payload.get("output_path")
        files = payload.get("files", [])
        format_type = payload.get("format", "zip").lower()
        compression = payload.get("compression", "deflate")

        if not output_path:
            raise ValueError("Missing required parameter: output_path")
        if not files:
            raise ValueError("Missing required parameter: files (must be non-empty list)")

        output_path = Path(output_path)
        file_paths = [Path(f) for f in files]

        # Validate all files exist
        for fp in file_paths:
            if not fp.exists():
                raise FileNotFoundError(f"File not found: {fp}")

        logger.info(
            f"Creating {format_type} archive with {len(files)} files: "
            f"{output_path.name} (job {job_id})"
        )

        # Create parent directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Run creation in executor
        def create():
            file_count = 0

            if format_type == "zip":
                compress_map = {
                    "deflate": zipfile.ZIP_DEFLATED,
                    "stored": zipfile.ZIP_STORED,
                    "bzip2": zipfile.ZIP_BZIP2,
                    "lzma": zipfile.ZIP_LZMA,
                }
                compress_type = compress_map.get(compression, zipfile.ZIP_DEFLATED)

                with zipfile.ZipFile(output_path, "w", compression=compress_type) as zf:
                    for fp in file_paths:
                        if fp.is_file():
                            zf.write(fp, arcname=fp.name)
                            file_count += 1

            elif format_type.startswith("tar"):
                mode = "w"
                if format_type == "tar.gz":
                    mode = "w:gz"
                elif format_type == "tar.bz2":
                    mode = "w:bz2"
                elif format_type == "tar.xz":
                    mode = "w:xz"

                with tarfile.open(output_path, mode) as tf:
                    for fp in file_paths:
                        if fp.is_file():
                            tf.add(fp, arcname=fp.name)
                            file_count += 1

            elif format_type == "7z":
                if not self._has_py7zr:
                    raise ImportError("py7zr not installed")

                import py7zr

                with py7zr.SevenZipFile(output_path, mode="w") as archive:
                    for fp in file_paths:
                        if fp.is_file():
                            archive.write(fp, arcname=fp.name)
                            file_count += 1

            else:
                raise ValueError(
                    f"Unsupported format for creation: {format_type}. "
                    "Supported: zip, tar, tar.gz, tar.bz2, tar.xz, 7z"
                )

            return file_count

        loop = asyncio.get_event_loop()
        count = await loop.run_in_executor(None, create)

        final_size = output_path.stat().st_size

        logger.info(
            f"Created archive with {count} files ({final_size / (1024**2):.1f}MB)"
        )

        return {
            "path": str(output_path),
            "size": final_size,
            "file_count": count,
            "success": True,
        }

    async def _test_archive(self, payload: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """
        Test archive integrity.

        Payload:
            archive_path: str - Path to archive

        Returns:
            dict with valid (bool), errors (list), success
        """
        archive_path = payload.get("archive_path")

        if not archive_path:
            raise ValueError("Missing required parameter: archive_path")

        archive_path = Path(archive_path)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        format_type = self._detect_format(archive_path)
        logger.info(f"Testing {format_type} archive: {archive_path.name} (job {job_id})")

        # Run test in executor
        def test():
            errors = []
            valid = True

            try:
                if format_type == "zip":
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        bad_file = zf.testzip()
                        if bad_file:
                            errors.append(f"Corrupt file: {bad_file}")
                            valid = False

                elif format_type.startswith("tar"):
                    mode = "r"
                    if format_type == "tar.gz":
                        mode = "r:gz"
                    elif format_type == "tar.bz2":
                        mode = "r:bz2"
                    elif format_type == "tar.xz":
                        mode = "r:xz"

                    with tarfile.open(archive_path, mode) as tf:
                        # Try to read all members
                        for member in tf.getmembers():
                            if member.isfile():
                                try:
                                    tf.extractfile(member).read(1)
                                except Exception as e:
                                    errors.append(f"Corrupt file {member.name}: {e}")
                                    valid = False

                elif format_type == "7z":
                    if not self._has_py7zr:
                        raise ImportError("py7zr not installed")

                    import py7zr

                    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                        if not archive.testzip():
                            errors.append("Archive test failed")
                            valid = False

                elif format_type == "rar":
                    if not self._has_rarfile:
                        raise ImportError("rarfile not installed")

                    import rarfile

                    with rarfile.RarFile(archive_path, "r") as rf:
                        bad_file = rf.testrar()
                        if bad_file:
                            errors.append(f"Test failed: {bad_file}")
                            valid = False

                else:
                    # For GZ/BZ2, just try to open
                    if format_type == "gz":
                        with gzip.open(archive_path, "rb") as f:
                            f.read(1)
                    elif format_type == "bz2":
                        with bz2.open(archive_path, "rb") as f:
                            f.read(1)

            except Exception as e:
                errors.append(str(e))
                valid = False

            return valid, errors

        loop = asyncio.get_event_loop()
        is_valid, error_list = await loop.run_in_executor(None, test)

        logger.info(f"Archive test: {'PASSED' if is_valid else 'FAILED'}")

        return {
            "valid": is_valid,
            "errors": error_list,
            "success": True,
        }


if __name__ == "__main__":
    """Run the worker if executed directly."""
    from .base import run_worker

    run_worker(ArchiveWorker)
