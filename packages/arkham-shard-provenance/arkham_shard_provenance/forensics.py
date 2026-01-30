"""Metadata forensics module.

Extracts and analyzes metadata from:
- Images (EXIF, IPTC, XMP)
- PDFs (Info dict, XMP)
- Office documents (Core properties)

Performs integrity analysis:
- Timestamp consistency checks
- Metadata stripping detection
- Editing software detection
- Timeline reconstruction
"""

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from .models import (
    ExifData,
    ForensicFinding,
    ForensicScanStatus,
    IntegrityStatus,
    MetadataComparison,
    MetadataForensicScan,
    OfficeMetadata,
    PdfMetadata,
    RelationshipType,
    TimelineEvent,
)

logger = logging.getLogger(__name__)


def _parse_optional_date(value: Any) -> Optional[datetime]:
    """Parse date from document_metadata (ISO string or datetime)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def _pdf_metadata_from_document_metadata(d: Dict[str, Any]) -> PdfMetadata:
    """Build PdfMetadata from frame document_metadata dict (avoids re-reading file)."""
    pdf = PdfMetadata()
    if not d:
        return pdf
    pdf.title = d.get("title") and str(d["title"]).strip() or None
    pdf.author = d.get("author") and str(d["author"]).strip() or None
    pdf.subject = d.get("subject") and str(d["subject"]).strip() or None
    pdf.creator = d.get("creator") and str(d["creator"]).strip() or None
    pdf.producer = d.get("producer") and str(d["producer"]).strip() or None
    pdf.creation_date = _parse_optional_date(d.get("creation_date"))
    pdf.modification_date = _parse_optional_date(d.get("modification_date"))
    kw = d.get("keywords")
    if kw is not None:
        pdf.keywords = [k.strip() for k in str(kw).split(",") if k.strip()]
    pdf.page_count = int(d["num_pages"]) if d.get("num_pages") is not None else 0
    pdf.is_encrypted = bool(d.get("is_encrypted"))
    xmp = d.get("exiftool_metadata") or d.get("xmp_data")
    if isinstance(xmp, dict):
        pdf.xmp_data = xmp
    return pdf


def _office_metadata_from_document_metadata(d: Dict[str, Any]) -> OfficeMetadata:
    """Build OfficeMetadata from frame document_metadata dict (avoids re-reading file)."""
    office = OfficeMetadata()
    if not d:
        return office
    office.title = d.get("title") and str(d["title"]).strip() or None
    office.author = d.get("author") and str(d["author"]).strip() or None
    office.subject = d.get("subject") and str(d["subject"]).strip() or None
    office.last_modified_by = d.get("last_modified_by") and str(d["last_modified_by"]).strip() or None
    office.created = _parse_optional_date(d.get("creation_date"))
    office.modified = _parse_optional_date(d.get("modification_date"))
    kw = d.get("keywords")
    if kw is not None:
        office.keywords = [k.strip() for k in str(kw).split(",") if k.strip()]
    rev = d.get("revision")
    if rev is not None:
        try:
            office.revision = int(rev)
        except (TypeError, ValueError):
            pass
    return office


def _exif_data_from_document_metadata(d: Dict[str, Any]) -> ExifData:
    """Build ExifData from frame document_metadata dict (avoids re-reading file for images)."""
    exif = ExifData()
    if not d:
        return exif
    exif.make = d.get("device_make") and str(d["device_make"]).strip() or None
    exif.model = d.get("device_model") and str(d["device_model"]).strip() or None
    exif.software = None
    sw = d.get("software") or d.get("software_list")
    if isinstance(sw, list) and sw:
        exif.software = ", ".join(str(x) for x in sw)
    elif sw:
        exif.software = str(sw)
    exif.width = int(d["image_width"]) if d.get("image_width") is not None else None
    exif.height = int(d["image_height"]) if d.get("image_height") is not None else None
    exif.datetime_original = _parse_optional_date(d.get("creation_date"))
    exif.datetime_modified = _parse_optional_date(d.get("modification_date"))
    gps = d.get("gps_data")
    if isinstance(gps, dict):
        exif.raw_data["gps_data"] = gps
        # Try common exiftool GPS keys for decimal degrees
        lat = gps.get("GPSLatitude") or gps.get("GPS Latitude")
        lon = gps.get("GPSLongitude") or gps.get("GPS Longitude")
        if lat is not None:
            try:
                exif.gps_latitude = float(lat)
            except (TypeError, ValueError):
                pass
        if lon is not None:
            try:
                exif.gps_longitude = float(lon)
            except (TypeError, ValueError):
                pass
    return exif


def _has_meaningful_pdf_metadata(pdf: PdfMetadata) -> bool:
    """True if pdf has at least one meaningful field for integrity/timeline."""
    return bool(
        pdf.title or pdf.author or pdf.subject or pdf.creator or pdf.producer
        or pdf.creation_date or pdf.modification_date or pdf.page_count
    )


def _has_meaningful_office_metadata(office: OfficeMetadata) -> bool:
    """True if office has at least one meaningful field."""
    return bool(
        office.title or office.author or office.subject or office.created
        or office.modified or office.last_modified_by
    )


def _has_meaningful_exif_data(exif: ExifData) -> bool:
    """True if exif has at least one meaningful field."""
    return bool(
        exif.make or exif.model or exif.width or exif.height
        or exif.gps_latitude is not None or exif.gps_longitude is not None
        or exif.datetime_original or exif.datetime_modified or exif.software
    )


class MetadataForensicAnalyzer:
    """
    Comprehensive metadata forensic analyzer.

    Extracts and analyzes metadata from:
    - Images (EXIF, IPTC, XMP via Pillow)
    - PDFs (Info dict, XMP via pypdf)
    - Office documents (Core properties via python-docx/openpyxl)

    Performs forensic analysis:
    - Timestamp consistency validation
    - Metadata integrity checks
    - Editing software detection
    - Timeline reconstruction from available metadata
    """

    def __init__(self):
        self._magic = None

    def _get_magic(self):
        """Lazy load python-magic with fallback."""
        if self._magic is None:
            try:
                import magic
                self._magic = magic.Magic(mime=True)
            except ImportError:
                logger.warning("python-magic not available")
                self._magic = False
            except Exception as e:
                logger.warning(f"libmagic not available: {e}")
                self._magic = False
        return self._magic if self._magic is not False else None

    def calculate_hashes(self, data: bytes) -> dict:
        """
        Calculate multiple hash digests for integrity verification.

        Args:
            data: Raw file bytes

        Returns:
            Dict with md5, sha256, sha512 hashes
        """
        return {
            'md5': hashlib.md5(data).hexdigest(),
            'sha256': hashlib.sha256(data).hexdigest(),
            'sha512': hashlib.sha512(data).hexdigest(),
        }

    def extract_exif(self, file_path: str) -> ExifData:
        """
        Extract EXIF data from image file.

        Extracts:
        - Camera make/model/serial
        - Date/time stamps (original, digitized, modified)
        - GPS coordinates
        - Software used
        - Image dimensions

        Args:
            file_path: Path to image file

        Returns:
            ExifData with extracted fields
        """
        exif = ExifData()

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS, IFD
        except ImportError:
            logger.warning("Pillow not available - EXIF extraction disabled")
            return exif

        try:
            with Image.open(file_path) as img:
                exif.width = img.width
                exif.height = img.height

                exif_data = img.getexif()
                if not exif_data:
                    return exif

                raw_data = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    # Convert bytes to string for JSON serialization
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8', errors='ignore')
                        except Exception:
                            value = str(value)
                    raw_data[tag_name] = value

                exif.raw_data = raw_data
                exif.make = raw_data.get('Make')
                exif.model = raw_data.get('Model')
                exif.software = raw_data.get('Software')

                # Parse DateTime fields
                datetime_fields = [
                    ('DateTimeOriginal', 'datetime_original'),
                    ('DateTimeDigitized', 'datetime_digitized'),
                    ('DateTime', 'datetime_modified'),
                ]
                for exif_field, attr in datetime_fields:
                    if exif_field in raw_data:
                        try:
                            dt = datetime.strptime(
                                raw_data[exif_field],
                                '%Y:%m:%d %H:%M:%S'
                            )
                            setattr(exif, attr, dt)
                        except (ValueError, TypeError):
                            pass

                # Extract GPS data
                try:
                    gps_ifd = exif_data.get_ifd(IFD.GPSInfo)
                    if gps_ifd:
                        # GPS Latitude
                        lat_data = gps_ifd.get(2)  # GPSLatitude
                        lat_ref = gps_ifd.get(1)   # GPSLatitudeRef
                        if lat_data and lat_ref:
                            exif.gps_latitude = self._convert_gps_coords(lat_data, lat_ref)

                        # GPS Longitude
                        lon_data = gps_ifd.get(4)  # GPSLongitude
                        lon_ref = gps_ifd.get(3)   # GPSLongitudeRef
                        if lon_data and lon_ref:
                            exif.gps_longitude = self._convert_gps_coords(lon_data, lon_ref)

                        # GPS Altitude
                        alt_data = gps_ifd.get(6)  # GPSAltitude
                        if alt_data:
                            try:
                                exif.gps_altitude = float(alt_data)
                            except (ValueError, TypeError):
                                pass
                except Exception as e:
                    logger.debug(f"GPS extraction failed: {e}")

        except Exception as e:
            logger.warning(f"EXIF extraction failed for {file_path}: {e}")

        return exif

    def _convert_gps_coords(
        self,
        coords: Optional[Tuple],
        ref: Optional[str]
    ) -> Optional[float]:
        """
        Convert GPS from EXIF format to decimal degrees.

        Args:
            coords: Tuple of (degrees, minutes, seconds) or IFDRational values
            ref: Reference direction (N/S/E/W)

        Returns:
            Decimal degrees or None if conversion fails
        """
        if not coords or not ref:
            return None

        try:
            # Handle IFDRational or plain numbers
            def to_float(val):
                if hasattr(val, 'numerator') and hasattr(val, 'denominator'):
                    return float(val.numerator) / float(val.denominator)
                return float(val)

            degrees = to_float(coords[0])
            minutes = to_float(coords[1])
            seconds = to_float(coords[2])

            decimal = degrees + minutes / 60 + seconds / 3600

            if ref in ['S', 'W']:
                decimal = -decimal

            return decimal
        except (ValueError, IndexError, TypeError, ZeroDivisionError) as e:
            logger.debug(f"GPS conversion failed: {e}")
            return None

    def extract_pdf_metadata(self, file_path: str) -> PdfMetadata:
        """
        Extract metadata from PDF file.

        Extracts:
        - Document info (title, author, subject, keywords)
        - Creator/Producer applications
        - Creation/Modification dates
        - XMP metadata
        - Page count and PDF version
        - Encryption status

        Args:
            file_path: Path to PDF file

        Returns:
            PdfMetadata with extracted fields
        """
        pdf = PdfMetadata()

        try:
            from pypdf import PdfReader
        except ImportError:
            logger.warning("pypdf not available - PDF extraction disabled")
            return pdf

        try:
            reader = PdfReader(file_path)

            # Basic document info
            meta = reader.metadata
            if meta:
                pdf.title = getattr(meta, 'title', None)
                pdf.author = getattr(meta, 'author', None)
                pdf.subject = getattr(meta, 'subject', None)
                pdf.creator = getattr(meta, 'creator', None)
                pdf.producer = getattr(meta, 'producer', None)

                # Parse dates
                creation_date = getattr(meta, 'creation_date', None)
                if creation_date:
                    pdf.creation_date = creation_date

                modification_date = getattr(meta, 'modification_date', None)
                if modification_date:
                    pdf.modification_date = modification_date

            pdf.page_count = len(reader.pages)

            # Get PDF version if available
            try:
                pdf.pdf_version = reader.pdf_header
            except Exception:
                pass

            # XMP metadata
            try:
                xmp = reader.xmp_metadata
                if xmp:
                    xmp_data = {}
                    for attr in ['dc_title', 'dc_creator', 'dc_description',
                                 'xmp_create_date', 'xmp_modify_date',
                                 'pdf_producer', 'pdf_keywords']:
                        val = getattr(xmp, attr, None)
                        if val:
                            xmp_data[attr] = str(val) if not isinstance(val, (list, dict)) else val
                    pdf.xmp_data = xmp_data
            except Exception as e:
                logger.debug(f"XMP extraction failed: {e}")

            pdf.is_encrypted = reader.is_encrypted

        except Exception as e:
            logger.warning(f"PDF metadata extraction failed for {file_path}: {e}")

        return pdf

    def extract_office_metadata(self, file_path: str) -> OfficeMetadata:
        """
        Extract metadata from Office documents (docx, xlsx, pptx).

        Args:
            file_path: Path to Office file

        Returns:
            OfficeMetadata with extracted fields
        """
        office = OfficeMetadata()

        # Try python-docx for Word documents
        if file_path.lower().endswith('.docx'):
            try:
                from docx import Document
                doc = Document(file_path)
                props = doc.core_properties

                office.title = props.title
                office.author = props.author
                office.subject = props.subject
                office.company = getattr(props, 'company', None)
                office.created = props.created
                office.modified = props.modified
                office.last_modified_by = props.last_modified_by
                office.revision = props.revision
                office.category = props.category
                office.comments = props.comments
                if props.keywords:
                    office.keywords = [k.strip() for k in props.keywords.split(',')]

                return office
            except ImportError:
                logger.debug("python-docx not available")
            except Exception as e:
                logger.warning(f"DOCX extraction failed: {e}")

        # Generic ZIP-based Office Open XML extraction
        try:
            import zipfile
            import xml.etree.ElementTree as ET

            with zipfile.ZipFile(file_path, 'r') as zf:
                # Try to read docProps/core.xml
                if 'docProps/core.xml' in zf.namelist():
                    with zf.open('docProps/core.xml') as f:
                        tree = ET.parse(f)
                        root = tree.getroot()

                        # Define namespaces
                        ns = {
                            'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
                            'dc': 'http://purl.org/dc/elements/1.1/',
                            'dcterms': 'http://purl.org/dc/terms/',
                        }

                        # Extract properties
                        title = root.find('.//dc:title', ns)
                        if title is not None and title.text:
                            office.title = title.text

                        creator = root.find('.//dc:creator', ns)
                        if creator is not None and creator.text:
                            office.author = creator.text

                        subject = root.find('.//dc:subject', ns)
                        if subject is not None and subject.text:
                            office.subject = subject.text

                        created = root.find('.//dcterms:created', ns)
                        if created is not None and created.text:
                            try:
                                office.created = datetime.fromisoformat(
                                    created.text.replace('Z', '+00:00')
                                )
                            except ValueError:
                                pass

                        modified = root.find('.//dcterms:modified', ns)
                        if modified is not None and modified.text:
                            try:
                                office.modified = datetime.fromisoformat(
                                    modified.text.replace('Z', '+00:00')
                                )
                            except ValueError:
                                pass

                        last_mod_by = root.find('.//cp:lastModifiedBy', ns)
                        if last_mod_by is not None and last_mod_by.text:
                            office.last_modified_by = last_mod_by.text

                        revision = root.find('.//cp:revision', ns)
                        if revision is not None and revision.text:
                            try:
                                office.revision = int(revision.text)
                            except ValueError:
                                pass

        except Exception as e:
            logger.debug(f"Office metadata extraction failed: {e}")

        return office

    def analyze_integrity(
        self,
        exif: Optional[ExifData] = None,
        pdf: Optional[PdfMetadata] = None,
        office: Optional[OfficeMetadata] = None,
    ) -> Tuple[IntegrityStatus, list[ForensicFinding], float]:
        """
        Analyze metadata for integrity issues.

        Checks:
        - Timestamp consistency (creation vs modification dates)
        - Missing expected metadata (EXIF stripped)
        - Signs of editing software
        - Revision count anomalies

        Args:
            exif: EXIF data from image (optional)
            pdf: PDF metadata (optional)
            office: Office metadata (optional)

        Returns:
            Tuple of (status, findings, confidence)
        """
        findings = []
        suspicious_count = 0

        if exif:
            # Check for stripped EXIF (minimal metadata)
            if not exif.raw_data or len(exif.raw_data) < 5:
                findings.append(ForensicFinding(
                    finding_type="exif_minimal",
                    severity="medium",
                    description="Minimal or missing EXIF data - may have been stripped",
                    confidence=0.7,
                ))
                suspicious_count += 1

            # Check timestamp inconsistencies
            if exif.datetime_original and exif.datetime_digitized:
                diff = abs((exif.datetime_original - exif.datetime_digitized).total_seconds())
                if diff > 60:  # More than 1 minute difference
                    findings.append(ForensicFinding(
                        finding_type="timestamp_inconsistency",
                        severity="medium",
                        description=f"DateTime Original and Digitized differ by {diff:.0f} seconds",
                        evidence={
                            "original": exif.datetime_original.isoformat(),
                            "digitized": exif.datetime_digitized.isoformat(),
                        },
                        confidence=0.8,
                    ))
                    suspicious_count += 1

            # Check for editing software
            if exif.software:
                editing_tools = ['photoshop', 'gimp', 'lightroom', 'snapseed',
                                 'picasa', 'afterlight', 'vsco']
                software_lower = exif.software.lower()
                if any(tool in software_lower for tool in editing_tools):
                    findings.append(ForensicFinding(
                        finding_type="editing_software_detected",
                        severity="low",
                        description=f"Image edited with: {exif.software}",
                        evidence={"software": exif.software},
                        confidence=1.0,
                    ))

        if pdf:
            # Check creation vs modification date
            if pdf.creation_date and pdf.modification_date:
                if pdf.modification_date < pdf.creation_date:
                    findings.append(ForensicFinding(
                        finding_type="timestamp_anomaly",
                        severity="high",
                        description="Modification date is before creation date",
                        evidence={
                            "creation": pdf.creation_date.isoformat() if pdf.creation_date else None,
                            "modification": pdf.modification_date.isoformat() if pdf.modification_date else None,
                        },
                        confidence=0.95,
                    ))
                    suspicious_count += 2

            # Check for PDF manipulation tools
            if pdf.producer:
                manipulation_tools = ['ghostscript', 'pdftk', 'pdf-tools',
                                      'itext', 'fpdf', 'reportlab']
                producer_lower = pdf.producer.lower()
                if any(tool in producer_lower for tool in manipulation_tools):
                    findings.append(ForensicFinding(
                        finding_type="pdf_tool_detected",
                        severity="low",
                        description=f"PDF processed with: {pdf.producer}",
                        evidence={"producer": pdf.producer},
                        confidence=0.9,
                    ))

            # Check if PDF is encrypted
            if pdf.is_encrypted:
                findings.append(ForensicFinding(
                    finding_type="pdf_encrypted",
                    severity="low",
                    description="PDF is encrypted - metadata may be limited",
                    confidence=1.0,
                ))

        if office:
            # Check creation vs modification date
            if office.created and office.modified:
                if office.modified < office.created:
                    findings.append(ForensicFinding(
                        finding_type="timestamp_anomaly",
                        severity="high",
                        description="Modification date is before creation date",
                        evidence={
                            "creation": office.created.isoformat() if office.created else None,
                            "modification": office.modified.isoformat() if office.modified else None,
                        },
                        confidence=0.95,
                    ))
                    suspicious_count += 2

            # Check revision count
            if office.revision is not None:
                if office.revision == 1 and office.modified:
                    # Single revision but has modification date
                    if office.created and office.modified != office.created:
                        findings.append(ForensicFinding(
                            finding_type="revision_anomaly",
                            severity="medium",
                            description="Document shows only 1 revision but has different created/modified dates",
                            evidence={"revision": office.revision},
                            confidence=0.7,
                        ))
                        suspicious_count += 1
                elif office.revision > 100:
                    findings.append(ForensicFinding(
                        finding_type="high_revision_count",
                        severity="low",
                        description=f"Document has {office.revision} revisions - heavily edited",
                        evidence={"revision": office.revision},
                        confidence=0.9,
                    ))

        # Determine status
        if suspicious_count >= 3:
            status = IntegrityStatus.TAMPERED
        elif suspicious_count >= 1:
            status = IntegrityStatus.SUSPICIOUS
        elif findings:
            status = IntegrityStatus.CLEAN  # Has findings but not suspicious
        else:
            status = IntegrityStatus.CLEAN

        # Calculate confidence
        if findings:
            confidence = sum(f.confidence for f in findings) / len(findings)
        else:
            confidence = 1.0  # High confidence in clean status if no findings

        return status, findings, confidence

    def build_timeline(
        self,
        doc_id: str,
        exif: Optional[ExifData] = None,
        pdf: Optional[PdfMetadata] = None,
        office: Optional[OfficeMetadata] = None,
    ) -> list[TimelineEvent]:
        """
        Build document timeline from all available metadata.

        Reconstructs the chronological history of a document based on
        metadata timestamps from various sources.

        Args:
            doc_id: Document identifier
            exif: EXIF data (optional)
            pdf: PDF metadata (optional)
            office: Office metadata (optional)

        Returns:
            List of timeline events, sorted chronologically
        """
        events = []

        if exif:
            if exif.datetime_original:
                events.append(TimelineEvent(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    event_type="captured",
                    event_timestamp=exif.datetime_original,
                    event_source="exif",
                    event_actor=f"{exif.make or ''} {exif.model or ''}".strip() or None,
                    event_details={"field": "DateTimeOriginal"},
                ))

            if exif.datetime_digitized and exif.datetime_digitized != exif.datetime_original:
                events.append(TimelineEvent(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    event_type="digitized",
                    event_timestamp=exif.datetime_digitized,
                    event_source="exif",
                    event_details={"field": "DateTimeDigitized"},
                ))

            if exif.datetime_modified:
                events.append(TimelineEvent(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    event_type="modified",
                    event_timestamp=exif.datetime_modified,
                    event_source="exif",
                    event_actor=exif.software,
                    event_details={"field": "DateTime"},
                ))

        if pdf:
            if pdf.creation_date:
                events.append(TimelineEvent(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    event_type="created",
                    event_timestamp=pdf.creation_date,
                    event_source="pdf",
                    event_actor=pdf.creator,
                    event_details={"creator": pdf.creator, "producer": pdf.producer},
                ))

            if pdf.modification_date and pdf.modification_date != pdf.creation_date:
                events.append(TimelineEvent(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    event_type="modified",
                    event_timestamp=pdf.modification_date,
                    event_source="pdf",
                    event_actor=pdf.producer,
                    event_details={"producer": pdf.producer},
                ))

        if office:
            if office.created:
                events.append(TimelineEvent(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    event_type="created",
                    event_timestamp=office.created,
                    event_source="office",
                    event_actor=office.author,
                    event_details={"author": office.author, "company": office.company},
                ))

            if office.modified and office.modified != office.created:
                events.append(TimelineEvent(
                    id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    event_type="modified",
                    event_timestamp=office.modified,
                    event_source="office",
                    event_actor=office.last_modified_by,
                    event_details={
                        "last_modified_by": office.last_modified_by,
                        "revision": office.revision,
                    },
                ))

        # Sort by timestamp
        events.sort(key=lambda e: e.event_timestamp or datetime.min)
        return events

    def compare_documents(
        self,
        scan1: MetadataForensicScan,
        scan2: MetadataForensicScan,
    ) -> MetadataComparison:
        """
        Compare metadata between two documents.

        Analyzes:
        - Hash matches (exact copies)
        - Camera/device matches
        - Author/creator matches
        - Creation date proximity

        Args:
            scan1: First document's forensic scan
            scan2: Second document's forensic scan

        Returns:
            MetadataComparison with match score and relationship type
        """
        comparison = MetadataComparison(
            id=str(uuid.uuid4()),
            source_doc_id=scan1.doc_id,
            target_doc_id=scan2.doc_id,
            comparison_type="comprehensive",
        )

        similarities = []
        differences = []

        # Hash comparison (exact match)
        if scan1.file_hash_sha256 and scan2.file_hash_sha256:
            if scan1.file_hash_sha256 == scan2.file_hash_sha256:
                similarities.append({
                    "type": "exact_hash_match",
                    "field": "sha256",
                    "confidence": 1.0,
                })
                comparison.relationship_type = RelationshipType.COPY
                comparison.confidence = 1.0
                comparison.match_score = 1.0
            else:
                differences.append({
                    "type": "hash_mismatch",
                    "field": "sha256",
                })

        # EXIF comparison
        if scan1.exif_data and scan2.exif_data:
            exif1, exif2 = scan1.exif_data, scan2.exif_data

            # Camera match
            if (exif1.make and exif2.make and exif1.make == exif2.make and
                exif1.model and exif2.model and exif1.model == exif2.model):
                similarities.append({
                    "type": "same_camera",
                    "value": f"{exif1.make} {exif1.model}",
                    "confidence": 0.9,
                })
                if not comparison.relationship_type:
                    comparison.relationship_type = RelationshipType.SAME_CAMERA
                    comparison.confidence = max(comparison.confidence, 0.7)

            # Serial number match (very strong indicator)
            if exif1.serial_number and exif2.serial_number:
                if exif1.serial_number == exif2.serial_number:
                    similarities.append({
                        "type": "same_device",
                        "value": exif1.serial_number,
                        "confidence": 0.99,
                    })
                    if not comparison.relationship_type:
                        comparison.relationship_type = RelationshipType.SAME_SOURCE
                        comparison.confidence = max(comparison.confidence, 0.95)

        # PDF comparison
        if scan1.pdf_metadata and scan2.pdf_metadata:
            pdf1, pdf2 = scan1.pdf_metadata, scan2.pdf_metadata

            # Author match
            if pdf1.author and pdf2.author and pdf1.author == pdf2.author:
                similarities.append({
                    "type": "same_author",
                    "value": pdf1.author,
                    "confidence": 0.8,
                })
                if not comparison.relationship_type:
                    comparison.relationship_type = RelationshipType.SAME_AUTHOR
                    comparison.confidence = max(comparison.confidence, 0.6)

            # Creator software match
            if pdf1.creator and pdf2.creator and pdf1.creator == pdf2.creator:
                similarities.append({
                    "type": "same_creator_software",
                    "value": pdf1.creator,
                    "confidence": 0.5,
                })

        # Office metadata comparison
        if scan1.office_metadata and scan2.office_metadata:
            off1, off2 = scan1.office_metadata, scan2.office_metadata

            if off1.author and off2.author and off1.author == off2.author:
                similarities.append({
                    "type": "same_author",
                    "value": off1.author,
                    "confidence": 0.8,
                })
                if not comparison.relationship_type:
                    comparison.relationship_type = RelationshipType.SAME_AUTHOR
                    comparison.confidence = max(comparison.confidence, 0.6)

            if off1.company and off2.company and off1.company == off2.company:
                similarities.append({
                    "type": "same_company",
                    "value": off1.company,
                    "confidence": 0.6,
                })

        comparison.similarities = similarities
        comparison.differences = differences

        if similarities and not comparison.match_score:
            comparison.match_score = sum(
                s.get('confidence', 0.5) for s in similarities
            ) / len(similarities)

        if not comparison.relationship_type:
            comparison.relationship_type = RelationshipType.UNRELATED

        return comparison

    def full_scan(
        self,
        doc_id: str,
        file_path: str,
        file_data: bytes,
        mime_type: str,
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> MetadataForensicScan:
        """
        Perform complete forensic scan on a document.

        Extracts all available metadata, calculates file hashes,
        performs integrity analysis, and reconstructs timeline.

        When document_metadata (from frame document_metadata table) is provided,
        uses it for PDF/Office/EXIF-style fields and only falls back to file-based
        extraction when the stored metadata has no meaningful fields for that type.

        Args:
            doc_id: Document identifier
            file_path: Path to file on disk
            file_data: Raw file bytes
            mime_type: MIME type
            document_metadata: Optional dict from frame get_document_metadata(doc_id)

        Returns:
            Complete forensic scan results
        """
        scan = MetadataForensicScan(
            id=str(uuid.uuid4()),
            doc_id=doc_id,
        )

        try:
            # Calculate hashes
            hashes = self.calculate_hashes(file_data)
            scan.file_hash_md5 = hashes['md5']
            scan.file_hash_sha256 = hashes['sha256']
            scan.file_hash_sha512 = hashes['sha512']
            scan.file_size = len(file_data)

            # Extract metadata based on file type; prefer document_metadata when available
            mime_lower = mime_type.lower() if mime_type else ""
            file_path_str = str(file_path) if file_path else ""

            if 'image' in mime_lower:
                if document_metadata:
                    scan.exif_data = _exif_data_from_document_metadata(document_metadata)
                    if not _has_meaningful_exif_data(scan.exif_data):
                        scan.exif_data = self.extract_exif(file_path_str)
                else:
                    scan.exif_data = self.extract_exif(file_path_str)

            if 'pdf' in mime_lower:
                if document_metadata:
                    scan.pdf_metadata = _pdf_metadata_from_document_metadata(document_metadata)
                    if not _has_meaningful_pdf_metadata(scan.pdf_metadata):
                        scan.pdf_metadata = self.extract_pdf_metadata(file_path_str)
                else:
                    scan.pdf_metadata = self.extract_pdf_metadata(file_path_str)

            if any(x in mime_lower for x in ['word', 'document', 'spreadsheet',
                                              'presentation', 'officedocument']):
                if document_metadata:
                    scan.office_metadata = _office_metadata_from_document_metadata(document_metadata)
                    if not _has_meaningful_office_metadata(scan.office_metadata):
                        scan.office_metadata = self.extract_office_metadata(file_path_str)
                else:
                    scan.office_metadata = self.extract_office_metadata(file_path_str)

            # Also try Office extraction for common extensions when we have no author yet
            if file_path_str.lower().endswith(('.docx', '.xlsx', '.pptx')):
                if not scan.office_metadata or not scan.office_metadata.author:
                    scan.office_metadata = self.extract_office_metadata(file_path_str)

            # Analyze integrity
            status, findings, confidence = self.analyze_integrity(
                exif=scan.exif_data,
                pdf=scan.pdf_metadata,
                office=scan.office_metadata,
            )
            scan.integrity_status = status
            scan.findings = findings
            scan.confidence_score = confidence

            # Build timeline
            scan.timeline_events = self.build_timeline(
                doc_id=doc_id,
                exif=scan.exif_data,
                pdf=scan.pdf_metadata,
                office=scan.office_metadata,
            )

            scan.scan_status = ForensicScanStatus.COMPLETED
            scan.scanned_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Forensic scan failed for {doc_id}: {e}", exc_info=True)
            scan.scan_status = ForensicScanStatus.FAILED
            scan.metadata["error"] = str(e)

        return scan
