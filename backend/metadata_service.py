"""
PDF Metadata Extraction Service for ArkhamMirror.

Extracts forensic metadata from PDF files:
- Author/Creator information
- Creation and modification dates
- Software used to create the PDF
- Encryption status
- Page count
- File properties
"""

import os
from typing import Dict, Optional
from datetime import datetime
from pypdf import PdfReader


def extract_pdf_metadata(pdf_path: str) -> Dict:
    """
    Extract metadata from a PDF file.

    Args:
        pdf_path: Absolute path to PDF file

    Returns:
        Dictionary with extracted metadata fields
    """
    if not os.path.exists(pdf_path):
        return {"error": "File not found"}

    try:
        reader = PdfReader(pdf_path)

        metadata = {
            # Basic file info
            "num_pages": len(reader.pages),
            "is_encrypted": reader.is_encrypted,
            "file_size_bytes": os.path.getsize(pdf_path),

            # PDF metadata from document info
            "pdf_author": None,
            "pdf_creator": None,
            "pdf_producer": None,
            "pdf_subject": None,
            "pdf_title": None,
            "pdf_keywords": None,
            "pdf_creation_date": None,
            "pdf_modification_date": None,

            # Additional properties
            "pdf_version": reader.pdf_header,
        }

        # Extract document info dictionary
        if reader.metadata:
            info = reader.metadata

            # Author
            if "/Author" in info:
                metadata["pdf_author"] = str(info["/Author"])

            # Creator (application that created the original document)
            if "/Creator" in info:
                metadata["pdf_creator"] = str(info["/Creator"])

            # Producer (PDF generation software)
            if "/Producer" in info:
                metadata["pdf_producer"] = str(info["/Producer"])

            # Subject
            if "/Subject" in info:
                metadata["pdf_subject"] = str(info["/Subject"])

            # Title
            if "/Title" in info:
                metadata["pdf_title"] = str(info["/Title"])

            # Keywords
            if "/Keywords" in info:
                metadata["pdf_keywords"] = str(info["/Keywords"])

            # Creation Date
            if "/CreationDate" in info:
                metadata["pdf_creation_date"] = parse_pdf_date(info["/CreationDate"])

            # Modification Date
            if "/ModDate" in info:
                metadata["pdf_modification_date"] = parse_pdf_date(info["/ModDate"])

        return metadata

    except Exception as e:
        return {"error": str(e)}


def parse_pdf_date(pdf_date_string: str) -> Optional[datetime]:
    """
    Parse PDF date format to Python datetime.

    PDF dates are in format: D:YYYYMMDDHHmmSSOHH'mm'
    Example: D:20230315120000+05'00'

    Args:
        pdf_date_string: PDF date string

    Returns:
        datetime object or None if parsing fails
    """
    if not pdf_date_string:
        return None

    try:
        # Remove D: prefix if present
        date_str = pdf_date_string
        if date_str.startswith("D:"):
            date_str = date_str[2:]

        # Extract basic datetime components (first 14 chars: YYYYMMDDHHmmSS)
        if len(date_str) >= 14:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            hour = int(date_str[8:10])
            minute = int(date_str[10:12])
            second = int(date_str[12:14])

            return datetime(year, month, day, hour, minute, second)

        # If shorter, try year/month/day only
        elif len(date_str) >= 8:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])

            return datetime(year, month, day)

    except (ValueError, IndexError):
        pass

    return None


def extract_metadata_summary(pdf_path: str) -> str:
    """
    Extract metadata and return a human-readable summary.

    Args:
        pdf_path: Path to PDF file

    Returns:
        String summary of metadata
    """
    metadata = extract_pdf_metadata(pdf_path)

    if "error" in metadata:
        return f"Error extracting metadata: {metadata['error']}"

    lines = []

    # Basic info
    lines.append(f"📄 **File Properties**")
    lines.append(f"- Pages: {metadata.get('num_pages', 'Unknown')}")
    lines.append(f"- Size: {format_file_size(metadata.get('file_size_bytes', 0))}")
    lines.append(f"- Encrypted: {'Yes' if metadata.get('is_encrypted') else 'No'}")
    lines.append(f"- PDF Version: {metadata.get('pdf_version', 'Unknown')}")

    # Document info
    if any([metadata.get('pdf_title'), metadata.get('pdf_author'),
            metadata.get('pdf_subject')]):
        lines.append("")
        lines.append(f"📝 **Document Information**")

        if metadata.get('pdf_title'):
            lines.append(f"- Title: {metadata['pdf_title']}")
        if metadata.get('pdf_author'):
            lines.append(f"- Author: {metadata['pdf_author']}")
        if metadata.get('pdf_subject'):
            lines.append(f"- Subject: {metadata['pdf_subject']}")
        if metadata.get('pdf_keywords'):
            lines.append(f"- Keywords: {metadata['pdf_keywords']}")

    # Creation info (forensic value)
    if any([metadata.get('pdf_creator'), metadata.get('pdf_producer')]):
        lines.append("")
        lines.append(f"🔧 **Creation Software** (Forensic)")

        if metadata.get('pdf_creator'):
            lines.append(f"- Creator: {metadata['pdf_creator']}")
        if metadata.get('pdf_producer'):
            lines.append(f"- Producer: {metadata['pdf_producer']}")

    # Dates
    if any([metadata.get('pdf_creation_date'), metadata.get('pdf_modification_date')]):
        lines.append("")
        lines.append(f"📅 **Timestamps** (Forensic)")

        if metadata.get('pdf_creation_date'):
            lines.append(f"- Created: {metadata['pdf_creation_date'].strftime('%Y-%m-%d %H:%M:%S')}")
        if metadata.get('pdf_modification_date'):
            lines.append(f"- Modified: {metadata['pdf_modification_date'].strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(lines)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def is_metadata_suspicious(metadata: Dict) -> tuple:
    """
    Analyze metadata for suspicious patterns.

    Returns: (is_suspicious, list_of_reasons)
    """
    reasons = []

    # Check for missing critical metadata
    if not metadata.get('pdf_author') and not metadata.get('pdf_creator'):
        reasons.append("Missing author/creator information")

    # Check for metadata scrubbing tools
    producer = metadata.get('pdf_producer', '').lower()
    if 'exiftool' in producer or 'metadata' in producer:
        reasons.append("Possible metadata manipulation detected")

    # Check date inconsistencies
    creation = metadata.get('pdf_creation_date')
    modification = metadata.get('pdf_modification_date')

    if creation and modification:
        if modification < creation:
            reasons.append("Modification date is before creation date (tampered)")

    # Check for very recent creation (potential metadata forgery)
    if creation:
        age_days = (datetime.now() - creation).days
        if age_days < 1:
            reasons.append("Document created very recently (verify authenticity)")

    return (len(reasons) > 0, reasons)
