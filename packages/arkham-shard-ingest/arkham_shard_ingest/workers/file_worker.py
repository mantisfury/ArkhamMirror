"""
FileWorker - Async file I/O operations for the io-file pool.

Handles:
- File reading (text and binary)
- File writing (text and binary)
- File/directory operations (copy, move, delete)
- Path queries (exists, stat, list)

All operations are async using aiofiles or asyncio.to_thread.
"""

import asyncio
import base64
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from arkham_frame.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class FileWorker(BaseWorker):
    """
    Worker for async file I/O operations.

    Supports operations:
    - read: Read file contents (text or binary)
    - write: Write content to file
    - copy: Copy file or directory
    - move: Move/rename file or directory
    - delete: Delete file or directory
    - exists: Check if path exists
    - list: List directory contents
    - stat: Get file/directory stats
    """

    pool = "io-file"
    name = "FileWorker"
    job_timeout = 60.0  # File ops shouldn't take more than 60s
    poll_interval = 0.5  # Poll frequently for I/O tasks

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aiofiles_available = False

        # Try to import aiofiles
        try:
            import aiofiles
            self._aiofiles_available = True
            logger.info("aiofiles available for async file I/O")
        except ImportError:
            logger.warning("aiofiles not available, using synchronous I/O in executor")

    def _resolve_path(self, file_path: str) -> Path:
        """
        Resolve file path using DATA_SILO_PATH for Docker/portable deployments.

        Args:
            file_path: Path from payload (may be relative or absolute)

        Returns:
            Resolved absolute Path
        """
        if not os.path.isabs(file_path):
            data_silo = os.environ.get("DATA_SILO_PATH", ".")
            return Path(data_silo) / file_path
        return Path(file_path)

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a file I/O task.

        Args:
            job_id: Job identifier
            payload: Job data with 'operation' field and operation-specific params

        Returns:
            Result dict based on operation type
        """
        operation = payload.get("operation", "")

        if not operation:
            return {"error": "No operation specified", "success": False}

        # Route to appropriate handler
        if operation == "read":
            return await self._read(payload)
        elif operation == "write":
            return await self._write(payload)
        elif operation == "copy":
            return await self._copy(payload)
        elif operation == "move":
            return await self._move(payload)
        elif operation == "delete":
            return await self._delete(payload)
        elif operation == "exists":
            return await self._exists(payload)
        elif operation == "list":
            return await self._list(payload)
        elif operation == "stat":
            return await self._stat(payload)
        else:
            return {"error": f"Unknown operation: {operation}", "success": False}

    async def _read(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read file contents.

        Args:
            payload: {
                "path": str - File path to read
                "binary": bool - Read as binary (default: False)
                "encoding": str - Text encoding (default: "utf-8")
            }

        Returns:
            {
                "content": str or base64 encoded - File contents
                "size": int - File size in bytes
                "success": bool
            }
        """
        path = payload.get("path")
        binary = payload.get("binary", False)
        encoding = payload.get("encoding", "utf-8")

        if not path:
            return {"error": "No path specified", "success": False}

        # Resolve relative path using DATA_SILO_PATH
        path_obj = self._resolve_path(path)

        if not path_obj.exists():
            return {"error": f"Path not found: {path}", "success": False}

        if not path_obj.is_file():
            return {"error": f"Path is not a file: {path}", "success": False}

        try:
            if self._aiofiles_available:
                import aiofiles
                mode = "rb" if binary else "r"
                async with aiofiles.open(path, mode=mode, encoding=None if binary else encoding) as f:
                    content = await f.read()
            else:
                # Fallback to sync I/O in executor
                def sync_read():
                    mode = "rb" if binary else "r"
                    with open(path, mode=mode, encoding=None if binary else encoding) as f:
                        return f.read()
                content = await asyncio.to_thread(sync_read)

            # If binary, base64 encode for JSON transport
            if binary:
                content = base64.b64encode(content).decode("ascii")

            size = path_obj.stat().st_size

            return {
                "content": content,
                "size": size,
                "binary": binary,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return {"error": str(e), "success": False}

    async def _write(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write content to file.

        Args:
            payload: {
                "path": str - File path to write
                "content": str or base64 encoded - Content to write
                "binary": bool - Write as binary (default: False)
                "encoding": str - Text encoding (default: "utf-8")
                "mkdir": bool - Create parent dirs if needed (default: True)
            }

        Returns:
            {
                "path": str - File path written
                "size": int - Bytes written
                "success": bool
            }
        """
        path = payload.get("path")
        content = payload.get("content", "")
        binary = payload.get("binary", False)
        encoding = payload.get("encoding", "utf-8")
        mkdir = payload.get("mkdir", True)

        if not path:
            return {"error": "No path specified", "success": False}

        # Resolve relative path using DATA_SILO_PATH
        path_obj = self._resolve_path(path)

        try:
            # Create parent directories if requested
            if mkdir and not path_obj.parent.exists():
                await asyncio.to_thread(path_obj.parent.mkdir, parents=True, exist_ok=True)

            # If binary, decode from base64
            if binary:
                content = base64.b64decode(content)

            if self._aiofiles_available:
                import aiofiles
                mode = "wb" if binary else "w"
                async with aiofiles.open(path, mode=mode, encoding=None if binary else encoding) as f:
                    await f.write(content)
            else:
                # Fallback to sync I/O in executor
                def sync_write():
                    mode = "wb" if binary else "w"
                    with open(path, mode=mode, encoding=None if binary else encoding) as f:
                        f.write(content)
                await asyncio.to_thread(sync_write)

            size = path_obj.stat().st_size

            return {
                "path": str(path),
                "size": size,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to write {path}: {e}")
            return {"error": str(e), "success": False}

    async def _copy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Copy file or directory.

        Args:
            payload: {
                "src": str - Source path
                "dst": str - Destination path
                "overwrite": bool - Overwrite if exists (default: False)
            }

        Returns:
            {
                "src": str - Source path
                "dst": str - Destination path
                "success": bool
            }
        """
        src = payload.get("src")
        dst = payload.get("dst")
        overwrite = payload.get("overwrite", False)

        if not src or not dst:
            return {"error": "Both src and dst required", "success": False}

        # Resolve relative paths using DATA_SILO_PATH
        src_obj = self._resolve_path(src)
        dst_obj = self._resolve_path(dst)

        if not src_obj.exists():
            return {"error": f"Source not found: {src}", "success": False}

        if dst_obj.exists() and not overwrite:
            return {"error": f"Destination exists: {dst}", "success": False}

        try:
            def sync_copy():
                if src_obj.is_file():
                    shutil.copy2(str(src_obj), str(dst_obj))
                else:
                    shutil.copytree(str(src_obj), str(dst_obj), dirs_exist_ok=overwrite)

            await asyncio.to_thread(sync_copy)

            return {
                "src": str(src),
                "dst": str(dst),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to copy {src} to {dst}: {e}")
            return {"error": str(e), "success": False}

    async def _move(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Move/rename file or directory.

        Args:
            payload: {
                "src": str - Source path
                "dst": str - Destination path
                "overwrite": bool - Overwrite if exists (default: False)
            }

        Returns:
            {
                "src": str - Source path
                "dst": str - Destination path
                "success": bool
            }
        """
        src = payload.get("src")
        dst = payload.get("dst")
        overwrite = payload.get("overwrite", False)

        if not src or not dst:
            return {"error": "Both src and dst required", "success": False}

        # Resolve relative paths using DATA_SILO_PATH
        src_obj = self._resolve_path(src)
        dst_obj = self._resolve_path(dst)

        if not src_obj.exists():
            return {"error": f"Source not found: {src}", "success": False}

        if dst_obj.exists() and not overwrite:
            return {"error": f"Destination exists: {dst}", "success": False}

        try:
            def sync_move():
                if dst_obj.exists() and overwrite:
                    if dst_obj.is_file():
                        dst_obj.unlink()
                    else:
                        shutil.rmtree(str(dst_obj))
                shutil.move(str(src_obj), str(dst_obj))

            await asyncio.to_thread(sync_move)

            return {
                "src": str(src),
                "dst": str(dst),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to move {src} to {dst}: {e}")
            return {"error": str(e), "success": False}

    async def _delete(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete file or directory.

        Args:
            payload: {
                "path": str - Path to delete
                "recursive": bool - Delete directory recursively (default: False)
            }

        Returns:
            {
                "path": str - Path deleted
                "success": bool
            }
        """
        path = payload.get("path")
        recursive = payload.get("recursive", False)

        if not path:
            return {"error": "No path specified", "success": False}

        # Resolve relative path using DATA_SILO_PATH
        path_obj = self._resolve_path(path)

        if not path_obj.exists():
            return {"error": f"Path not found: {path}", "success": False}

        try:
            def sync_delete():
                if path_obj.is_file():
                    path_obj.unlink()
                else:
                    if recursive:
                        shutil.rmtree(str(path_obj))
                    else:
                        path_obj.rmdir()  # Will fail if not empty

            await asyncio.to_thread(sync_delete)

            return {
                "path": str(path),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            return {"error": str(e), "success": False}

    async def _exists(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if path exists.

        Args:
            payload: {
                "path": str - Path to check
            }

        Returns:
            {
                "path": str - Path checked
                "exists": bool - Whether path exists
                "is_file": bool - Whether path is a file (if exists)
                "is_dir": bool - Whether path is a directory (if exists)
            }
        """
        path = payload.get("path")

        if not path:
            return {"error": "No path specified", "success": False}

        # Resolve relative path using DATA_SILO_PATH
        path_obj = self._resolve_path(path)

        try:
            def sync_exists():
                return {
                    "path": str(path_obj),
                    "exists": path_obj.exists(),
                    "is_file": path_obj.is_file() if path_obj.exists() else False,
                    "is_dir": path_obj.is_dir() if path_obj.exists() else False,
                    "success": True,
                }

            return await asyncio.to_thread(sync_exists)

        except Exception as e:
            logger.error(f"Failed to check existence of {path}: {e}")
            return {"error": str(e), "success": False}

    async def _list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        List directory contents.

        Args:
            payload: {
                "path": str - Directory path to list
                "pattern": str - Glob pattern to match (default: "*")
                "recursive": bool - List recursively (default: False)
            }

        Returns:
            {
                "path": str - Directory path listed
                "files": List[str] - List of matching file paths
                "count": int - Number of files found
                "success": bool
            }
        """
        path = payload.get("path")
        pattern = payload.get("pattern", "*")
        recursive = payload.get("recursive", False)

        if not path:
            return {"error": "No path specified", "success": False}

        # Resolve relative path using DATA_SILO_PATH
        path_obj = self._resolve_path(path)

        if not path_obj.exists():
            return {"error": f"Path not found: {path}", "success": False}

        if not path_obj.is_dir():
            return {"error": f"Path is not a directory: {path}", "success": False}

        try:
            def sync_list():
                if recursive:
                    matches = list(path_obj.rglob(pattern))
                else:
                    matches = list(path_obj.glob(pattern))

                # Convert to strings, relative to the base path
                files = [str(p.relative_to(path_obj)) if p != path_obj else "." for p in matches]
                files.sort()

                return files

            files = await asyncio.to_thread(sync_list)

            return {
                "path": str(path_obj),
                "files": files,
                "count": len(files),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Failed to list {path}: {e}")
            return {"error": str(e), "success": False}

    async def _stat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get file/directory stats.

        Args:
            payload: {
                "path": str - Path to stat
            }

        Returns:
            {
                "path": str - Path queried
                "size": int - Size in bytes
                "created": str - Creation time (ISO format)
                "modified": str - Last modified time (ISO format)
                "is_file": bool - Whether path is a file
                "is_dir": bool - Whether path is a directory
                "success": bool
            }
        """
        path = payload.get("path")

        if not path:
            return {"error": "No path specified", "success": False}

        # Resolve relative path using DATA_SILO_PATH
        path_obj = self._resolve_path(path)

        if not path_obj.exists():
            return {"error": f"Path not found: {path}", "success": False}

        try:
            def sync_stat():
                stat = path_obj.stat()
                return {
                    "path": str(path_obj),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "is_file": path_obj.is_file(),
                    "is_dir": path_obj.is_dir(),
                    "success": True,
                }

            return await asyncio.to_thread(sync_stat)

        except Exception as e:
            logger.error(f"Failed to stat {path}: {e}")
            return {"error": str(e), "success": False}
