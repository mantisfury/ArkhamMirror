"""
Hidden Content Detection Service

Detects steganography, metadata anomalies, and embedded content:
- Image metadata forensics (EXIF tampering, geo-coordinates)
- Document metadata analysis (author changes, creation vs. modification dates)
- Watermark and embedded content detection
- File signature verification
"""

import os
import logging
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import Document
from app.arkham.services.utils.security_utils import get_display_filename

load_dotenv()
logger = logging.getLogger(__name__)



# File magic signatures for verification
FILE_SIGNATURES = {
    b"\x89PNG\r\n\x1a\n": ("png", "image/png"),
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"GIF87a": ("gif", "image/gif"),
    b"GIF89a": ("gif", "image/gif"),
    b"%PDF": ("pdf", "application/pdf"),
    b"PK\x03\x04": ("zip", "application/zip"),  # Also docx, xlsx, etc.
    b"\xd0\xcf\x11\xe0": ("doc", "application/msword"),  # OLE compound
    b"Rar!\x1a\x07": ("rar", "application/x-rar-compressed"),
}


class HiddenContentService:
    """Service for detecting hidden content and metadata anomalies."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a file for hidden content and anomalies."""
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found", "path": file_path}

        results = {
            "path": file_path,
            "filename": path.name,
            "size": path.stat().st_size,
            "anomalies": [],
            "warnings": [],
            "metadata": {},
        }

        # Check file signature
        sig_result = self._check_file_signature(path)
        results["signature_check"] = sig_result
        if sig_result.get("mismatch"):
            results["anomalies"].append(
                {
                    "type": "signature_mismatch",
                    "severity": "High",
                    "description": f"File extension suggests {sig_result['expected']} but signature indicates {sig_result['actual']}",
                }
            )

        # Analyze based on file type
        ext = path.suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".gif", ".tiff", ".bmp"]:
            image_results = self._analyze_image(path)
            results.update(image_results)
        elif ext == ".pdf":
            pdf_results = self._analyze_pdf(path)
            results.update(pdf_results)
        elif ext in [".docx", ".xlsx", ".pptx"]:
            office_results = self._analyze_office_document(path)
            results.update(office_results)

        # Check for appended data
        append_result = self._check_appended_data(path)
        if append_result.get("has_appended_data"):
            results["anomalies"].append(
                {
                    "type": "appended_data",
                    "severity": "High",
                    "description": f"File contains {append_result['extra_bytes']} bytes of appended data (possible steganography)",
                }
            )
            results["appended_data"] = append_result

        # Score overall risk
        results["risk_score"] = self._calculate_risk_score(results)
        results["analyzed_at"] = datetime.now().isoformat()

        return results

    def _check_file_signature(self, path: Path) -> Dict[str, Any]:
        """Verify file signature matches extension."""
        try:
            with open(path, "rb") as f:
                header = f.read(16)

            detected = None
            for sig, (ext, mime) in FILE_SIGNATURES.items():
                if header.startswith(sig):
                    detected = {"extension": ext, "mime": mime}
                    break

            actual_ext = path.suffix.lower().lstrip(".")

            # Map docx/xlsx/pptx to zip signature
            if (
                actual_ext in ["docx", "xlsx", "pptx"]
                and detected
                and detected["extension"] == "zip"
            ):
                return {"match": True, "detected": detected, "mismatch": False}

            if detected:
                expected_match = actual_ext == detected["extension"]
                return {
                    "match": expected_match,
                    "mismatch": not expected_match,
                    "expected": actual_ext,
                    "actual": detected["extension"],
                    "detected": detected,
                }

            return {"match": True, "detected": None, "mismatch": False}

        except Exception as e:
            logger.error(f"Error checking file signature: {e}")
            return {"error": str(e)}

    def _analyze_image(self, path: Path) -> Dict[str, Any]:
        """Analyze image for EXIF data and anomalies."""
        results = {
            "image_analysis": {},
            "metadata": {},
            "warnings": [],
            "anomalies": [],
        }

        try:
            # Try to import PIL
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            with Image.open(path) as img:
                results["image_analysis"]["format"] = img.format
                results["image_analysis"]["mode"] = img.mode
                results["image_analysis"]["size"] = {
                    "width": img.width,
                    "height": img.height,
                }

                # Extract EXIF data
                exif_data = {}
                exif = img._getexif() if hasattr(img, "_getexif") else None

                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8", errors="ignore")
                            except Exception:
                                value = str(value)[:100]
                        exif_data[tag] = str(value)[:200]

                    results["metadata"]["exif"] = exif_data

                    # Check for GPS data
                    if "GPSInfo" in exif_data or any(
                        "GPS" in str(k) for k in exif_data.keys()
                    ):
                        results["warnings"].append(
                            {
                                "type": "gps_data_present",
                                "severity": "Medium",
                                "description": "Image contains GPS/location data",
                            }
                        )

                    # Check for software editing
                    if "Software" in exif_data:
                        software = exif_data["Software"]
                        if any(
                            x in software.lower()
                            for x in ["photoshop", "gimp", "lightroom"]
                        ):
                            results["warnings"].append(
                                {
                                    "type": "editing_software",
                                    "severity": "Low",
                                    "description": f"Image was edited with: {software}",
                                }
                            )

                    # Check for date anomalies
                    self._check_date_anomalies(exif_data, results)

                else:
                    results["warnings"].append(
                        {
                            "type": "no_exif",
                            "severity": "Low",
                            "description": "Image has no EXIF metadata (possibly stripped)",
                        }
                    )

        except ImportError:
            results["image_analysis"]["note"] = "PIL not available for image analysis"
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            results["image_analysis"]["error"] = str(e)

        return results

    def _check_date_anomalies(self, exif_data: Dict, results: Dict):
        """Check for suspicious date patterns in EXIF data."""
        date_fields = ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]
        dates = {}

        for field in date_fields:
            if field in exif_data:
                dates[field] = exif_data[field]

        if len(dates) >= 2:
            # Check if dates are inconsistent
            date_values = list(dates.values())
            if len(set(date_values)) > 1:
                results["warnings"].append(
                    {
                        "type": "date_inconsistency",
                        "severity": "Medium",
                        "description": f"Multiple different dates found: {dates}",
                    }
                )

    def _analyze_pdf(self, path: Path) -> Dict[str, Any]:
        """Analyze PDF for hidden content and metadata."""
        results = {"pdf_analysis": {}, "metadata": {}, "warnings": [], "anomalies": []}

        try:
            with open(path, "rb") as f:
                content = f.read()

            # Check for encrypted content
            if b"/Encrypt" in content:
                results["warnings"].append(
                    {
                        "type": "encrypted_content",
                        "severity": "Medium",
                        "description": "PDF contains encrypted content",
                    }
                )

            # Check for JavaScript
            if b"/JavaScript" in content or b"/JS" in content:
                results["anomalies"].append(
                    {
                        "type": "javascript_present",
                        "severity": "High",
                        "description": "PDF contains JavaScript (potential security risk)",
                    }
                )

            # Check for embedded files
            if b"/EmbeddedFiles" in content or b"/EmbeddedFile" in content:
                results["warnings"].append(
                    {
                        "type": "embedded_files",
                        "severity": "Medium",
                        "description": "PDF contains embedded files",
                    }
                )

            # Check for external links
            if b"/URI" in content:
                results["warnings"].append(
                    {
                        "type": "external_links",
                        "severity": "Low",
                        "description": "PDF contains external URL links",
                    }
                )

            # Try to extract metadata
            try:
                import re

                # Basic metadata extraction
                producer_match = re.search(rb"/Producer\s*\((.*?)\)", content)
                creator_match = re.search(rb"/Creator\s*\((.*?)\)", content)
                author_match = re.search(rb"/Author\s*\((.*?)\)", content)

                results["metadata"]["pdf"] = {}
                if producer_match:
                    results["metadata"]["pdf"]["producer"] = producer_match.group(
                        1
                    ).decode("utf-8", errors="ignore")
                if creator_match:
                    results["metadata"]["pdf"]["creator"] = creator_match.group(
                        1
                    ).decode("utf-8", errors="ignore")
                if author_match:
                    results["metadata"]["pdf"]["author"] = author_match.group(1).decode(
                        "utf-8", errors="ignore"
                    )

            except Exception as e:
                logger.debug(f"Error extracting PDF metadata: {e}")

        except Exception as e:
            logger.error(f"Error analyzing PDF: {e}")
            results["pdf_analysis"]["error"] = str(e)

        return results

    def _analyze_office_document(self, path: Path) -> Dict[str, Any]:
        """Analyze Office document for metadata and hidden content."""
        results = {
            "office_analysis": {},
            "metadata": {},
            "warnings": [],
            "anomalies": [],
        }

        try:
            import zipfile

            with zipfile.ZipFile(path, "r") as zf:
                file_list = zf.namelist()
                results["office_analysis"]["file_count"] = len(file_list)

                # Check for hidden files or unusual entries
                suspicious = [
                    f for f in file_list if f.startswith(".") or "hidden" in f.lower()
                ]
                if suspicious:
                    results["warnings"].append(
                        {
                            "type": "hidden_files",
                            "severity": "Medium",
                            "description": f"Document contains hidden/unusual files: {suspicious[:5]}",
                        }
                    )

                # Check for macros (VBA)
                macro_files = [
                    f for f in file_list if "vba" in f.lower() or f.endswith(".bin")
                ]
                if macro_files:
                    results["anomalies"].append(
                        {
                            "type": "macros_present",
                            "severity": "High",
                            "description": "Document contains VBA macros (potential security risk)",
                        }
                    )

                # Try to read core.xml for metadata
                if "docProps/core.xml" in file_list:
                    with zf.open("docProps/core.xml") as core_file:
                        core_content = core_file.read().decode("utf-8", errors="ignore")
                        results["metadata"]["office"] = self._parse_office_core_xml(
                            core_content
                        )

        except zipfile.BadZipFile:
            results["office_analysis"]["error"] = "Invalid ZIP/Office format"
        except Exception as e:
            logger.error(f"Error analyzing Office document: {e}")
            results["office_analysis"]["error"] = str(e)

        return results

    def _parse_office_core_xml(self, content: str) -> Dict[str, str]:
        """Parse Office core.xml metadata."""
        import re

        metadata = {}

        fields = [
            ("creator", r"<dc:creator>(.*?)</dc:creator>"),
            ("lastModifiedBy", r"<cp:lastModifiedBy>(.*?)</cp:lastModifiedBy>"),
            ("created", r"<dcterms:created.*?>(.*?)</dcterms:created>"),
            ("modified", r"<dcterms:modified.*?>(.*?)</dcterms:modified>"),
            ("title", r"<dc:title>(.*?)</dc:title>"),
        ]

        for field, pattern in fields:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                metadata[field] = match.group(1).strip()

        return metadata

    def _check_appended_data(self, path: Path) -> Dict[str, Any]:
        """Check if file has data appended after the normal file content."""
        try:
            with open(path, "rb") as f:
                content = f.read()

            ext = path.suffix.lower()
            expected_end = None
            actual_end = len(content)

            # Check for expected file endings
            if ext in [".jpg", ".jpeg"]:
                # JPEG should end with FFD9
                eof_marker = content.rfind(b"\xff\xd9")
                if eof_marker > 0:
                    expected_end = eof_marker + 2

            elif ext == ".png":
                # PNG should end with IEND chunk
                iend_pos = content.rfind(b"IEND")
                if iend_pos > 0:
                    expected_end = iend_pos + 8  # IEND + CRC

            elif ext == ".pdf":
                # PDF should end with %%EOF
                eof_pos = content.rfind(b"%%EOF")
                if eof_pos > 0:
                    expected_end = eof_pos + 5

            if expected_end and expected_end < actual_end:
                extra_bytes = actual_end - expected_end
                if extra_bytes > 10:  # Ignore small padding
                    return {
                        "has_appended_data": True,
                        "expected_end": expected_end,
                        "actual_end": actual_end,
                        "extra_bytes": extra_bytes,
                    }

            return {"has_appended_data": False}

        except Exception as e:
            logger.error(f"Error checking appended data: {e}")
            return {"error": str(e)}

    def _calculate_risk_score(self, results: Dict) -> int:
        """Calculate overall risk score based on findings."""
        score = 0

        for anomaly in results.get("anomalies", []):
            if anomaly["severity"] == "High":
                score += 30
            elif anomaly["severity"] == "Medium":
                score += 15
            else:
                score += 5

        for warning in results.get("warnings", []):
            if warning["severity"] == "High":
                score += 20
            elif warning["severity"] == "Medium":
                score += 10
            else:
                score += 3

        return min(score, 100)

    def scan_document_library(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Scan documents in the library for hidden content."""
        session = self.Session()
        try:
            documents = (
                session.query(Document)
                .filter(Document.path.isnot(None))
                .order_by(desc(Document.created_at))
                .limit(limit)
                .all()
            )

            results = []
            for doc in documents:
                if doc.path and os.path.exists(doc.path):
                    analysis = self.analyze_file(doc.path)
                    analysis["document_id"] = doc.id
                    analysis["document_name"] = get_display_filename(doc)
                    results.append(analysis)

            # Sort by risk score
            results.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
            return results

        finally:
            session.close()

    def get_summary_stats(self, scan_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary statistics from scan results."""
        total = len(scan_results)
        high_risk = len([r for r in scan_results if r.get("risk_score", 0) >= 50])
        medium_risk = len(
            [r for r in scan_results if 20 <= r.get("risk_score", 0) < 50]
        )
        low_risk = len([r for r in scan_results if 0 < r.get("risk_score", 0) < 20])
        clean = len([r for r in scan_results if r.get("risk_score", 0) == 0])

        anomaly_types = {}
        for result in scan_results:
            for anomaly in result.get("anomalies", []):
                atype = anomaly.get("type", "unknown")
                anomaly_types[atype] = anomaly_types.get(atype, 0) + 1

        return {
            "total_scanned": total,
            "high_risk": high_risk,
            "medium_risk": medium_risk,
            "low_risk": low_risk,
            "clean": clean,
            "anomaly_types": anomaly_types,
        }


# Singleton
_service_instance = None


def get_hidden_content_service() -> HiddenContentService:
    global _service_instance
    if _service_instance is None:
        _service_instance = HiddenContentService()
    return _service_instance
