"""
ExtractWorker - Text extraction from PDF, DOCX, and XLSX files.

Extracts text content from common document formats using CPU-based libraries.
Part of the cpu-extract worker pool for document processing.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from arkham_frame.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class ExtractWorker(BaseWorker):
    """
    Worker for extracting text from documents.

    Supports PDF, DOCX, and XLSX file formats. Handles various edge cases
    including missing files, corrupted documents, password-protected files,
    and missing dependencies.

    Uses the cpu-extract pool for document text extraction tasks.
    """

    pool = "cpu-extract"
    name = "ExtractWorker"

    # Configuration
    poll_interval = 1.0
    heartbeat_interval = 10.0
    idle_timeout = 300.0  # 5 minutes
    job_timeout = 120.0   # 2 minutes for large files
    max_retries = 2

    def __init__(self, *args, **kwargs):
        """Initialize worker and check for required dependencies."""
        super().__init__(*args, **kwargs)
        self._check_dependencies()

    def _check_dependencies(self):
        """Check which extraction libraries are available."""
        self._has_pypdf = False
        self._has_docx = False
        self._has_openpyxl = False

        try:
            import pypdf
            self._has_pypdf = True
        except ImportError:
            logger.warning("pypdf not installed - PDF extraction unavailable")

        try:
            import docx
            self._has_docx = True
        except ImportError:
            logger.warning("python-docx not installed - DOCX extraction unavailable")

        try:
            import openpyxl
            self._has_openpyxl = True
        except ImportError:
            logger.warning("openpyxl not installed - XLSX extraction unavailable")

        if not any([self._has_pypdf, self._has_docx, self._has_openpyxl]):
            logger.error(
                "No extraction libraries available! "
                "Install pypdf, python-docx, and/or openpyxl"
            )

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
        Extract text from a document.

        Payload:
            file_path: Path to the file to extract from (required)
            file_type: File type - "pdf", "docx", or "xlsx" (required)

        Returns:
            dict with:
                success: bool - Whether extraction succeeded
                text: str - Extracted text content
                pages: int - Number of pages/sheets processed
                error: str - Error message if success=False
                file_path: str - Original file path
                file_type: str - File type processed

        Raises:
            ValueError: If required parameters are missing or invalid
            FileNotFoundError: If file doesn't exist
            Exception: For other extraction errors
        """
        # Validate payload
        file_path = payload.get("file_path")
        file_type = payload.get("file_type", "").lower()

        if not file_path:
            raise ValueError("Missing required parameter: file_path")

        # Resolve relative path using DATA_SILO_PATH
        file_path = str(self._resolve_path(file_path))

        # Auto-detect file_type from extension if not provided
        if not file_type:
            path = Path(file_path)
            ext = path.suffix.lower()
            ext_to_type = {
                ".pdf": "pdf",
                ".docx": "docx",
                ".doc": "docx",  # Old Word format (may not work)
                ".xlsx": "xlsx",
                ".xls": "xlsx",  # Old Excel format (may not work)
                ".txt": "txt",
                ".text": "txt",
                ".md": "txt",
                ".log": "txt",
                ".eml": "eml",
                ".emlx": "eml",  # Apple Mail format
            }
            file_type = ext_to_type.get(ext, "")
            if file_type:
                logger.debug(f"Auto-detected file_type: {file_type} from extension {ext}")

        if not file_type:
            raise ValueError(
                f"Could not determine file type. "
                "Provide file_type parameter or use a supported extension: "
                "pdf, docx, xlsx, txt"
            )

        if file_type not in ["pdf", "docx", "xlsx", "txt", "eml"]:
            raise ValueError(
                f"Unsupported file_type: {file_type}. "
                "Supported types: pdf, docx, xlsx, txt, eml"
            )

        # Check file exists
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        logger.info(
            f"ExtractWorker processing {file_type.upper()} file: "
            f"{path.name} (job {job_id})"
        )

        # Dispatch to appropriate extractor
        try:
            if file_type == "pdf":
                result = await self._extract_pdf(path)
            elif file_type == "docx":
                result = await self._extract_docx(path)
            elif file_type == "xlsx":
                result = await self._extract_xlsx(path)
            elif file_type == "txt":
                result = await self._extract_text(path)
            elif file_type == "eml":
                result = await self._extract_eml(path)
            else:
                # Should never reach here due to earlier validation
                raise ValueError(f"Unsupported file type: {file_type}")

            # Add metadata
            result["file_path"] = str(file_path)
            result["file_type"] = file_type
            result["success"] = True

            logger.info(
                f"ExtractWorker completed {file_type.upper()}: "
                f"{result.get('pages', 0)} pages, "
                f"{len(result.get('text', ''))} chars"
            )

            return result

        except Exception as e:
            error_msg = f"Extraction failed for {file_type.upper()}: {str(e)}"
            logger.error(f"ExtractWorker error (job {job_id}): {error_msg}")

            return {
                "success": False,
                "text": "",
                "pages": 0,
                "error": error_msg,
                "file_path": str(file_path),
                "file_type": file_type,
            }

    async def _extract_pdf(self, path: Path) -> Dict[str, Any]:
        """
        Extract text from PDF file.

        Args:
            path: Path to PDF file

        Returns:
            dict with text and page count

        Raises:
            ImportError: If pypdf is not installed
            Exception: For PDF reading errors
        """
        if not self._has_pypdf:
            raise ImportError(
                "pypdf library not installed. "
                "Install with: pip install pypdf"
            )

        from pypdf import PdfReader

        # Run in executor to avoid blocking
        def extract():
            try:
                reader = PdfReader(str(path))

                # Check for encryption
                if reader.is_encrypted:
                    raise ValueError(
                        "PDF is password-protected. "
                        "Encrypted PDFs are not supported."
                    )

                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)

                full_text = "\n\n".join(pages)

                return {
                    "text": full_text,
                    "pages": len(reader.pages),
                }

            except Exception as e:
                # Add context to error
                raise Exception(f"PDF reading error: {str(e)}")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract)

    async def _extract_docx(self, path: Path) -> Dict[str, Any]:
        """
        Extract text from DOCX file.

        Args:
            path: Path to DOCX file

        Returns:
            dict with text and paragraph count

        Raises:
            ImportError: If python-docx is not installed
            Exception: For DOCX reading errors
        """
        if not self._has_docx:
            raise ImportError(
                "python-docx library not installed. "
                "Install with: pip install python-docx"
            )

        from docx import Document

        # Run in executor to avoid blocking
        def extract():
            try:
                doc = Document(str(path))

                # Extract paragraphs
                paragraphs = []
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if text:
                        paragraphs.append(text)

                # Extract table content
                tables = []
                for table in doc.tables:
                    for row in table.rows:
                        cells = [cell.text.strip() for cell in row.cells]
                        if any(cells):  # Skip empty rows
                            tables.append(" | ".join(cells))

                # Combine all text
                all_text = []
                all_text.extend(paragraphs)
                if tables:
                    all_text.append("\n--- Tables ---\n")
                    all_text.extend(tables)

                full_text = "\n".join(all_text)

                return {
                    "text": full_text,
                    "pages": len(paragraphs),  # Use paragraph count as proxy
                }

            except Exception as e:
                raise Exception(f"DOCX reading error: {str(e)}")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract)

    async def _extract_xlsx(self, path: Path) -> Dict[str, Any]:
        """
        Extract text from XLSX file.

        Args:
            path: Path to XLSX file

        Returns:
            dict with text and sheet count

        Raises:
            ImportError: If openpyxl is not installed
            Exception: For XLSX reading errors
        """
        if not self._has_openpyxl:
            raise ImportError(
                "openpyxl library not installed. "
                "Install with: pip install openpyxl"
            )

        from openpyxl import load_workbook

        # Run in executor to avoid blocking
        def extract():
            try:
                # Load workbook (read-only for better performance)
                wb = load_workbook(
                    str(path),
                    read_only=True,
                    data_only=True  # Get computed values, not formulas
                )

                sheets = []

                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]

                    sheet_text = [f"--- Sheet: {sheet_name} ---"]

                    # Extract cell values row by row
                    for row in sheet.iter_rows(values_only=True):
                        # Convert to strings and filter out None
                        cells = [str(cell) for cell in row if cell is not None]
                        if cells:
                            sheet_text.append(" | ".join(cells))

                    sheets.append("\n".join(sheet_text))

                full_text = "\n\n".join(sheets)

                return {
                    "text": full_text,
                    "pages": len(wb.sheetnames),
                }

            except Exception as e:
                raise Exception(f"XLSX reading error: {str(e)}")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract)

    async def _extract_text(self, path: Path) -> Dict[str, Any]:
        """
        Extract text from plain text file.

        Args:
            path: Path to text file

        Returns:
            dict with text and line count
        """
        def extract():
            try:
                # Try different encodings
                encodings = ["utf-8", "utf-16", "latin-1", "cp1252"]
                text = None

                for encoding in encodings:
                    try:
                        with open(path, "r", encoding=encoding) as f:
                            text = f.read()
                        break
                    except UnicodeDecodeError:
                        continue

                if text is None:
                    # Fallback: read as bytes and decode with errors ignored
                    with open(path, "rb") as f:
                        text = f.read().decode("utf-8", errors="replace")

                lines = text.count("\n") + 1

                return {
                    "text": text,
                    "pages": lines,  # Use line count as proxy for pages
                }

            except Exception as e:
                raise Exception(f"Text file reading error: {str(e)}")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract)

    async def _extract_eml(self, path: Path) -> Dict[str, Any]:
        """
        Extract text from EML or EMLX (Apple Mail) email file.

        Args:
            path: Path to email file

        Returns:
            dict with text (headers + body) and part count
        """
        import email
        from email import policy

        def extract():
            try:
                # Read file content
                with open(path, "rb") as f:
                    content = f.read()

                # Handle EMLX format (Apple Mail)
                # EMLX has a preamble with byte count on first line
                if path.suffix.lower() == ".emlx":
                    # Skip the preamble (first line is byte count)
                    lines = content.split(b"\n", 1)
                    if len(lines) > 1:
                        try:
                            # Check if first line is a number (byte count)
                            int(lines[0].strip())
                            content = lines[1]
                        except ValueError:
                            pass  # Not EMLX format, use as-is

                # Parse email
                msg = email.message_from_bytes(content, policy=policy.default)

                parts = []
                part_count = 0

                # Extract headers
                headers = []
                for header in ["From", "To", "Cc", "Subject", "Date"]:
                    value = msg.get(header)
                    if value:
                        headers.append(f"{header}: {value}")

                if headers:
                    parts.append("--- Headers ---")
                    parts.extend(headers)
                    parts.append("")

                # Extract body
                parts.append("--- Body ---")

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            body = part.get_content()
                            if isinstance(body, str):
                                parts.append(body)
                                part_count += 1
                        elif content_type == "text/html":
                            # Basic HTML stripping
                            import re
                            html = part.get_content()
                            if isinstance(html, str):
                                text = re.sub(r"<[^>]+>", "", html)
                                text = re.sub(r"\s+", " ", text).strip()
                                if text and part_count == 0:  # Only if no plain text
                                    parts.append(text)
                                    part_count += 1
                else:
                    body = msg.get_content()
                    if isinstance(body, str):
                        parts.append(body)
                        part_count = 1
                    elif isinstance(body, bytes):
                        parts.append(body.decode("utf-8", errors="replace"))
                        part_count = 1

                return {
                    "text": "\n".join(parts),
                    "pages": max(1, part_count),
                }

            except Exception as e:
                raise Exception(f"Email file reading error: {str(e)}")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract)


if __name__ == "__main__":
    """Run the worker if executed directly."""
    from arkham_frame.workers.base import run_worker

    run_worker(ExtractWorker)
