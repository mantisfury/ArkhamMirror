import os
import sys
import html
import re
import logging
from pathlib import Path

# Add project root for central config
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config import DATA_SILO_PATH

logger = logging.getLogger(__name__)

# ALLOWED_DATA_DIR now uses centralized DataSilo path
ALLOWED_DATA_DIR = str(DATA_SILO_PATH)


def sanitize_filename(filename: str) -> str:
    """
    Remove path traversal attempts and dangerous characters from filenames.

    Args:
        filename: The original filename.

    Returns:
        A sanitized filename safe for storage.
    """
    # Get just the filename, stripping any path components
    safe_name = os.path.basename(filename)

    # Remove null bytes and other dangerous characters
    # We allow alphanumeric, dots, dashes, underscores, and spaces
    # But for strict safety, let's just strip known bad chars for path traversal
    safe_name = safe_name.replace("\x00", "").replace("/", "").replace("\\", "")

    # Ensure it's not empty or just dots
    if not safe_name or safe_name in (".", ".."):
        safe_name = "unnamed_file"

    return safe_name


def sanitize_for_llm(user_input: str, max_length: int = 10000) -> str:
    """
    Basic sanitization for LLM inputs to prevent prompt injection and excessive token usage.

    Args:
        user_input: The raw input string from the user.
        max_length: Maximum allowed length for the input.

    Returns:
        Sanitized string.
    """
    if not user_input:
        return ""

    # Remove potential injection patterns like triple backticks which might break formatting
    sanitized = user_input.replace("```", "'''")

    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "...[truncated]"

    return sanitized


def safe_delete_file(file_path: str) -> bool:
    """
    Safely delete a file only if it's within the allowed data directory.

    Args:
        file_path: The path to the file to delete.

    Returns:
        True if deleted, False if blocked or failed.
    """
    try:
        abs_path = os.path.abspath(file_path)

        # Check if the path is within the allowed data directory
        # commonpath throws ValueError if paths are on different drives (Windows)
        try:
            if os.path.commonpath([abs_path, ALLOWED_DATA_DIR]) != ALLOWED_DATA_DIR:
                logger.warning(
                    f"Attempted to delete file outside allowed directory: {abs_path}"
                )
                return False
        except ValueError:
            logger.warning(
                f"Attempted to delete file on different drive/path: {abs_path}"
            )
            return False

        if os.path.exists(abs_path):
            os.remove(abs_path)
            logger.info(f"Deleted file: {abs_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting file {file_path}: {e}")
        return False


def escape_html(text: str) -> str:
    """
    Escape HTML characters in text to prevent XSS.

    Args:
        text: Raw text.

    Returns:
        Escaped text safe for rendering.
    """
    return html.escape(text)


def get_display_filename(doc) -> str:
    """
    Get a user-friendly display filename for a document.

    Ingested files are stored with hash prefixes (e.g., "abc123_filename.pdf")
    for deduplication. This function returns the clean filename for UI display.

    Priority:
    1. Use doc.title if it exists (original filename without hash)
    2. Strip hash prefix from path if present
    3. Fall back to full path basename

    Args:
        doc: A Document ORM object with `path` and optional `title` attributes.
             Can also be a dict with 'path' and 'title' keys.

    Returns:
        Clean filename suitable for display in dropdowns and UI elements.
    """
    # Handle both ORM objects and dicts
    if hasattr(doc, "title"):
        title = doc.title
        path = doc.path
    elif isinstance(doc, dict):
        title = doc.get("title")
        path = doc.get("path", "")
    else:
        return "Unknown"

    # Prefer title if it exists and is not empty
    if title and title.strip():
        return title.strip()

    # Fall back to path, stripping hash prefix if present
    if path:
        basename = os.path.basename(path)

        # Hash prefix pattern: 16+ hex chars followed by underscore
        # e.g., "0aa57a887e996abc_Email_thread.eml"
        hash_pattern = re.compile(r"^[a-f0-9]{16,}_")
        match = hash_pattern.match(basename)
        if match:
            # Remove the hash prefix (including underscore)
            return basename[match.end() :]

        return basename

    return "Unknown"
