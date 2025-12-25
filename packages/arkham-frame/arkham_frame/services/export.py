"""
Export Service - Multi-format document and report export.

Provides export capabilities for documents, reports, and data
in various formats: PDF, HTML, Markdown, JSON, CSV.
"""

import json
import csv
import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ============================================
# Exceptions
# ============================================

class ExportError(Exception):
    """Base exception for export errors."""
    pass


class ExportFormatError(ExportError):
    """Invalid or unsupported export format."""
    pass


class ExportRenderError(ExportError):
    """Error during export rendering."""
    pass


class TemplateNotFoundError(ExportError):
    """Export template not found."""
    pass


# ============================================
# Enums and Types
# ============================================

class ExportFormat(str, Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"


@dataclass
class ExportOptions:
    """Options for export operation."""
    format: ExportFormat = ExportFormat.JSON
    template: Optional[str] = None
    include_metadata: bool = True
    include_timestamps: bool = True
    pretty_print: bool = True
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[datetime] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)
    page_size: str = "letter"  # For PDF: letter, a4, legal
    orientation: str = "portrait"  # portrait, landscape


@dataclass
class ExportResult:
    """Result of an export operation."""
    format: ExportFormat
    content: Union[str, bytes]
    filename: str
    content_type: str
    size_bytes: int
    exported_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================
# Format Exporters
# ============================================

class BaseExporter(ABC):
    """Abstract base class for format exporters."""

    @property
    @abstractmethod
    def format(self) -> ExportFormat:
        """Return the export format."""
        pass

    @property
    @abstractmethod
    def content_type(self) -> str:
        """Return the MIME content type."""
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Return the file extension."""
        pass

    @abstractmethod
    def export(self, data: Any, options: ExportOptions) -> ExportResult:
        """Export data to this format."""
        pass


class JSONExporter(BaseExporter):
    """Export data to JSON format."""

    @property
    def format(self) -> ExportFormat:
        return ExportFormat.JSON

    @property
    def content_type(self) -> str:
        return "application/json"

    @property
    def file_extension(self) -> str:
        return ".json"

    def export(self, data: Any, options: ExportOptions) -> ExportResult:
        """Export data to JSON."""
        # Prepare data with optional metadata
        export_data = data
        if options.include_metadata:
            export_data = {
                "data": data,
                "metadata": {
                    "exported_at": datetime.utcnow().isoformat(),
                    "title": options.title,
                    "author": options.author,
                    **options.custom_headers,
                }
            }

        indent = 2 if options.pretty_print else None
        content = json.dumps(export_data, indent=indent, default=str)

        filename = f"{options.title or 'export'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        return ExportResult(
            format=self.format,
            content=content,
            filename=filename,
            content_type=self.content_type,
            size_bytes=len(content.encode('utf-8')),
        )


class CSVExporter(BaseExporter):
    """Export tabular data to CSV format."""

    @property
    def format(self) -> ExportFormat:
        return ExportFormat.CSV

    @property
    def content_type(self) -> str:
        return "text/csv"

    @property
    def file_extension(self) -> str:
        return ".csv"

    def export(self, data: Any, options: ExportOptions) -> ExportResult:
        """Export data to CSV."""
        output = io.StringIO()

        if isinstance(data, list) and len(data) > 0:
            # Assume list of dicts
            if isinstance(data[0], dict):
                fieldnames = list(data[0].keys())
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            else:
                # List of lists
                writer = csv.writer(output)
                writer.writerows(data)
        elif isinstance(data, dict):
            # Single dict - export as key-value pairs
            writer = csv.writer(output)
            writer.writerow(["key", "value"])
            for key, value in data.items():
                writer.writerow([key, value])

        content = output.getvalue()
        filename = f"{options.title or 'export'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

        return ExportResult(
            format=self.format,
            content=content,
            filename=filename,
            content_type=self.content_type,
            size_bytes=len(content.encode('utf-8')),
        )


class MarkdownExporter(BaseExporter):
    """Export data to Markdown format."""

    @property
    def format(self) -> ExportFormat:
        return ExportFormat.MARKDOWN

    @property
    def content_type(self) -> str:
        return "text/markdown"

    @property
    def file_extension(self) -> str:
        return ".md"

    def export(self, data: Any, options: ExportOptions) -> ExportResult:
        """Export data to Markdown."""
        lines = []

        # Header
        if options.title:
            lines.append(f"# {options.title}")
            lines.append("")

        if options.include_metadata:
            if options.author:
                lines.append(f"**Author:** {options.author}")
            date = options.date or datetime.utcnow()
            lines.append(f"**Date:** {date.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Content
        if isinstance(data, dict):
            lines.extend(self._dict_to_md(data))
        elif isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                lines.extend(self._table_to_md(data))
            else:
                for item in data:
                    lines.append(f"- {item}")
        else:
            lines.append(str(data))

        content = "\n".join(lines)
        filename = f"{options.title or 'export'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"

        return ExportResult(
            format=self.format,
            content=content,
            filename=filename,
            content_type=self.content_type,
            size_bytes=len(content.encode('utf-8')),
        )

    def _dict_to_md(self, data: Dict, level: int = 2) -> List[str]:
        """Convert dict to markdown sections."""
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{'#' * level} {key}")
                lines.append("")
                lines.extend(self._dict_to_md(value, level + 1))
            elif isinstance(value, list):
                lines.append(f"{'#' * level} {key}")
                lines.append("")
                for item in value:
                    lines.append(f"- {item}")
                lines.append("")
            else:
                lines.append(f"**{key}:** {value}")
        lines.append("")
        return lines

    def _table_to_md(self, data: List[Dict]) -> List[str]:
        """Convert list of dicts to markdown table."""
        if not data:
            return []

        headers = list(data[0].keys())
        lines = []

        # Header row
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Data rows
        for row in data:
            values = [str(row.get(h, "")) for h in headers]
            lines.append("| " + " | ".join(values) + " |")

        lines.append("")
        return lines


class HTMLExporter(BaseExporter):
    """Export data to HTML format."""

    @property
    def format(self) -> ExportFormat:
        return ExportFormat.HTML

    @property
    def content_type(self) -> str:
        return "text/html"

    @property
    def file_extension(self) -> str:
        return ".html"

    def export(self, data: Any, options: ExportOptions) -> ExportResult:
        """Export data to HTML."""
        title = options.title or "Export"

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>{title}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 40px; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #4CAF50; color: white; }",
            "tr:nth-child(even) { background-color: #f2f2f2; }",
            ".metadata { color: #666; font-size: 0.9em; margin-bottom: 20px; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{title}</h1>",
        ]

        if options.include_metadata:
            html_parts.append('<div class="metadata">')
            if options.author:
                html_parts.append(f"<p><strong>Author:</strong> {options.author}</p>")
            date = options.date or datetime.utcnow()
            html_parts.append(f"<p><strong>Date:</strong> {date.strftime('%Y-%m-%d %H:%M:%S')}</p>")
            html_parts.append("</div>")

        # Content
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            html_parts.extend(self._table_to_html(data))
        elif isinstance(data, dict):
            html_parts.extend(self._dict_to_html(data))
        else:
            html_parts.append(f"<pre>{data}</pre>")

        html_parts.extend(["</body>", "</html>"])

        content = "\n".join(html_parts)
        filename = f"{options.title or 'export'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"

        return ExportResult(
            format=self.format,
            content=content,
            filename=filename,
            content_type=self.content_type,
            size_bytes=len(content.encode('utf-8')),
        )

    def _table_to_html(self, data: List[Dict]) -> List[str]:
        """Convert list of dicts to HTML table."""
        if not data:
            return []

        headers = list(data[0].keys())
        lines = ["<table>", "<thead><tr>"]

        for h in headers:
            lines.append(f"<th>{h}</th>")

        lines.append("</tr></thead><tbody>")

        for row in data:
            lines.append("<tr>")
            for h in headers:
                lines.append(f"<td>{row.get(h, '')}</td>")
            lines.append("</tr>")

        lines.extend(["</tbody>", "</table>"])
        return lines

    def _dict_to_html(self, data: Dict) -> List[str]:
        """Convert dict to HTML definition list."""
        lines = ["<dl>"]
        for key, value in data.items():
            lines.append(f"<dt><strong>{key}</strong></dt>")
            if isinstance(value, dict):
                lines.append("<dd>")
                lines.extend(self._dict_to_html(value))
                lines.append("</dd>")
            elif isinstance(value, list):
                lines.append("<dd><ul>")
                for item in value:
                    lines.append(f"<li>{item}</li>")
                lines.append("</ul></dd>")
            else:
                lines.append(f"<dd>{value}</dd>")
        lines.append("</dl>")
        return lines


class TextExporter(BaseExporter):
    """Export data to plain text format."""

    @property
    def format(self) -> ExportFormat:
        return ExportFormat.TEXT

    @property
    def content_type(self) -> str:
        return "text/plain"

    @property
    def file_extension(self) -> str:
        return ".txt"

    def export(self, data: Any, options: ExportOptions) -> ExportResult:
        """Export data to plain text."""
        lines = []

        if options.title:
            lines.append(options.title)
            lines.append("=" * len(options.title))
            lines.append("")

        if options.include_metadata:
            if options.author:
                lines.append(f"Author: {options.author}")
            date = options.date or datetime.utcnow()
            lines.append(f"Date: {date.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
            lines.append("-" * 40)
            lines.append("")

        if isinstance(data, dict):
            for key, value in data.items():
                lines.append(f"{key}: {value}")
        elif isinstance(data, list):
            for item in data:
                lines.append(str(item))
        else:
            lines.append(str(data))

        content = "\n".join(lines)
        filename = f"{options.title or 'export'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"

        return ExportResult(
            format=self.format,
            content=content,
            filename=filename,
            content_type=self.content_type,
            size_bytes=len(content.encode('utf-8')),
        )


# ============================================
# Export Service
# ============================================

class ExportService:
    """
    Service for exporting data in various formats.

    Provides:
    - Multi-format export (JSON, CSV, Markdown, HTML, PDF, Text)
    - Template-based export
    - Batch export
    - Export history tracking
    """

    def __init__(self, storage_service=None, template_service=None):
        """
        Initialize the export service.

        Args:
            storage_service: Optional storage service for saving exports
            template_service: Optional template service for templated exports
        """
        self._storage = storage_service
        self._templates = template_service

        # Register default exporters
        self._exporters: Dict[ExportFormat, BaseExporter] = {
            ExportFormat.JSON: JSONExporter(),
            ExportFormat.CSV: CSVExporter(),
            ExportFormat.MARKDOWN: MarkdownExporter(),
            ExportFormat.HTML: HTMLExporter(),
            ExportFormat.TEXT: TextExporter(),
        }

        # Export history (in-memory, could be persisted)
        self._history: List[Dict[str, Any]] = []

        logger.info("ExportService initialized")

    @property
    def supported_formats(self) -> List[ExportFormat]:
        """Return list of supported export formats."""
        return list(self._exporters.keys())

    def register_exporter(self, exporter: BaseExporter) -> None:
        """
        Register a custom exporter.

        Args:
            exporter: Exporter instance to register
        """
        self._exporters[exporter.format] = exporter
        logger.info(f"Registered exporter for format: {exporter.format}")

    def export(
        self,
        data: Any,
        format: Union[ExportFormat, str] = ExportFormat.JSON,
        options: Optional[ExportOptions] = None,
    ) -> ExportResult:
        """
        Export data to the specified format.

        Args:
            data: Data to export
            format: Export format
            options: Export options

        Returns:
            ExportResult with content and metadata

        Raises:
            ExportFormatError: If format is not supported
            ExportRenderError: If export fails
        """
        # Normalize format
        if isinstance(format, str):
            try:
                format = ExportFormat(format.lower())
            except ValueError:
                raise ExportFormatError(f"Unsupported format: {format}")

        if format not in self._exporters:
            raise ExportFormatError(f"No exporter registered for format: {format}")

        options = options or ExportOptions(format=format)
        options.format = format

        try:
            exporter = self._exporters[format]
            result = exporter.export(data, options)

            # Track in history
            self._history.append({
                "format": format.value,
                "filename": result.filename,
                "size_bytes": result.size_bytes,
                "exported_at": result.exported_at.isoformat(),
            })

            logger.info(f"Exported data to {format.value}: {result.filename}")
            return result

        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise ExportRenderError(f"Failed to export to {format}: {e}") from e

    async def export_to_file(
        self,
        data: Any,
        filepath: Union[str, Path],
        format: Optional[Union[ExportFormat, str]] = None,
        options: Optional[ExportOptions] = None,
    ) -> ExportResult:
        """
        Export data directly to a file.

        Args:
            data: Data to export
            filepath: Output file path
            format: Export format (inferred from extension if not provided)
            options: Export options

        Returns:
            ExportResult with file info
        """
        filepath = Path(filepath)

        # Infer format from extension if not provided
        if format is None:
            ext_to_format = {
                ".json": ExportFormat.JSON,
                ".csv": ExportFormat.CSV,
                ".md": ExportFormat.MARKDOWN,
                ".html": ExportFormat.HTML,
                ".htm": ExportFormat.HTML,
                ".txt": ExportFormat.TEXT,
                ".pdf": ExportFormat.PDF,
            }
            format = ext_to_format.get(filepath.suffix.lower(), ExportFormat.JSON)

        result = self.export(data, format, options)

        # Write to file
        mode = "wb" if isinstance(result.content, bytes) else "w"
        encoding = None if isinstance(result.content, bytes) else "utf-8"

        with open(filepath, mode, encoding=encoding) as f:
            f.write(result.content)

        result.filename = str(filepath)
        logger.info(f"Exported to file: {filepath}")

        return result

    def batch_export(
        self,
        data: Any,
        formats: List[Union[ExportFormat, str]],
        options: Optional[ExportOptions] = None,
    ) -> Dict[ExportFormat, ExportResult]:
        """
        Export data to multiple formats at once.

        Args:
            data: Data to export
            formats: List of formats to export to
            options: Export options (applied to all formats)

        Returns:
            Dict mapping format to ExportResult
        """
        results = {}

        for format in formats:
            try:
                results[format] = self.export(data, format, options)
            except ExportError as e:
                logger.warning(f"Batch export failed for {format}: {e}")
                # Continue with other formats

        return results

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get export history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of export history entries
        """
        return self._history[-limit:]

    def clear_history(self) -> None:
        """Clear export history."""
        self._history = []
