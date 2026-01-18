"""
EXIF/XMP metadata extraction service.
Uses multiple extraction methods for comprehensive coverage.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import re

from PIL import Image
from PIL.ExifTags import TAGS

try:
    import exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False

import structlog

logger = structlog.get_logger()


def _make_serializable(value):
    """Convert EXIF value to JSON-serializable type."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return f"<bytes:{len(value)}>"
    if isinstance(value, (list, tuple)):
        return [_make_serializable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _make_serializable(v) for k, v in value.items()}
    # Handle IFDRational, Fraction, and other numeric types
    try:
        # Try to convert to float first (handles Rational types)
        return float(value)
    except (TypeError, ValueError):
        pass
    # Fall back to string representation
    return str(value)


class ExifExtractor:
    """Extract metadata from image files using multiple methods."""

    def __init__(self, frame):
        self.frame = frame
        self.storage = frame.get_service("storage") if frame else None

    async def extract_all(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract all available metadata from an image file.

        Returns a unified metadata structure regardless of source format.
        """
        result = {
            "basic": {},
            "exif": {},
            "gps": {},
            "camera": {},
            "timestamps": {},
            "warnings": [],
            "extraction_methods": [],
        }

        # Method 1: Pillow (fast, basic EXIF)
        pillow_data = await self._extract_pillow(file_path)
        if pillow_data:
            result["exif"].update(pillow_data.get("exif", {}))
            result["basic"] = pillow_data.get("basic", {})
            result["extraction_methods"].append("pillow")

        # Method 2: ExifRead (comprehensive, pure Python)
        if EXIFREAD_AVAILABLE:
            exifread_data = await self._extract_exifread(file_path)
            if exifread_data:
                # Merge, preferring exifread for detailed data
                for key, value in exifread_data.items():
                    if key not in result["exif"] or not result["exif"][key]:
                        result["exif"][key] = value
                result["extraction_methods"].append("exifread")

        # Extract structured data from raw EXIF
        result["gps"] = self._parse_gps(result["exif"])
        result["camera"] = self._parse_camera(result["exif"])
        result["timestamps"] = self._parse_timestamps(result["exif"])

        # Check for suspicious patterns
        result["warnings"] = self._analyze_metadata_anomalies(result)

        return result

    async def _extract_pillow(self, file_path: Path) -> Optional[Dict]:
        """Extract EXIF using Pillow."""
        try:
            with Image.open(file_path) as img:
                basic = {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                }

                exif_data = img.getexif()
                if not exif_data:
                    return {"basic": basic, "exif": {}}

                exif = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    # Convert to JSON-serializable type
                    exif[tag_name] = _make_serializable(value)

                return {"basic": basic, "exif": exif}

        except Exception as e:
            logger.warning("Pillow extraction failed", error=str(e))
            return None

    async def _extract_exifread(self, file_path: Path) -> Optional[Dict]:
        """Extract EXIF using ExifRead (more comprehensive)."""
        try:
            with open(file_path, "rb") as f:
                tags = exifread.process_file(f, details=True)

                result = {}
                for tag, value in tags.items():
                    # Skip thumbnail data
                    if tag in ("JPEGThumbnail", "TIFFThumbnail", "Filename", "EXIF MakerNote"):
                        continue
                    result[tag] = str(value)

                return result

        except Exception as e:
            logger.warning("ExifRead extraction failed", error=str(e))
            return None

    def _parse_gps(self, exif: Dict) -> Dict[str, Any]:
        """Parse GPS data from EXIF into decimal coordinates."""
        gps = {}

        # Look for GPS tags (different naming in different extractors)
        lat_tag = exif.get("GPS GPSLatitude") or exif.get("GPSLatitude")
        lat_ref = exif.get("GPS GPSLatitudeRef") or exif.get("GPSLatitudeRef")
        lon_tag = exif.get("GPS GPSLongitude") or exif.get("GPSLongitude")
        lon_ref = exif.get("GPS GPSLongitudeRef") or exif.get("GPSLongitudeRef")

        if lat_tag and lon_tag:
            try:
                gps["latitude"] = self._gps_to_decimal(lat_tag, lat_ref)
                gps["longitude"] = self._gps_to_decimal(lon_tag, lon_ref)
                gps["raw_latitude"] = str(lat_tag)
                gps["raw_longitude"] = str(lon_tag)
            except Exception as e:
                gps["parse_error"] = str(e)

        # Altitude
        alt_tag = exif.get("GPS GPSAltitude") or exif.get("GPSAltitude")
        if alt_tag:
            gps["altitude"] = str(alt_tag)

        return gps

    def _gps_to_decimal(self, coord_str: str, ref: str) -> float:
        """Convert GPS coordinates from DMS to decimal degrees."""
        # Parse formats like "[40, 26, 46.302]" or "40/1, 26/1, 46302/1000"
        numbers = re.findall(r"[\d.]+(?:/[\d.]+)?", str(coord_str))

        if len(numbers) >= 3:
            def parse_rational(s):
                if "/" in s:
                    num, den = s.split("/")
                    return float(num) / float(den)
                return float(s)

            d = parse_rational(numbers[0])
            m = parse_rational(numbers[1])
            s = parse_rational(numbers[2])

            decimal = d + (m / 60.0) + (s / 3600.0)

            if ref and str(ref).upper() in ["S", "W"]:
                decimal = -decimal

            return round(decimal, 6)

        raise ValueError(f"Could not parse GPS coordinate: {coord_str}")

    def _parse_camera(self, exif: Dict) -> Dict[str, Any]:
        """Extract camera/device information."""
        return {
            "make": exif.get("Image Make") or exif.get("Make"),
            "model": exif.get("Image Model") or exif.get("Model"),
            "software": exif.get("Image Software") or exif.get("Software"),
            "lens_model": exif.get("EXIF LensModel") or exif.get("LensModel"),
            "focal_length": exif.get("EXIF FocalLength") or exif.get("FocalLength"),
            "aperture": exif.get("EXIF FNumber") or exif.get("FNumber"),
            "iso": exif.get("EXIF ISOSpeedRatings") or exif.get("ISOSpeedRatings"),
            "exposure_time": exif.get("EXIF ExposureTime") or exif.get("ExposureTime"),
            "flash": exif.get("EXIF Flash") or exif.get("Flash"),
            "orientation": exif.get("Image Orientation") or exif.get("Orientation"),
        }

    def _parse_timestamps(self, exif: Dict) -> Dict[str, Any]:
        """Extract all timestamp-related fields."""
        return {
            "datetime_original": exif.get("EXIF DateTimeOriginal") or exif.get("DateTimeOriginal"),
            "datetime_digitized": exif.get("EXIF DateTimeDigitized") or exif.get("DateTimeDigitized"),
            "datetime_modified": exif.get("Image DateTime") or exif.get("DateTime"),
            "gps_timestamp": exif.get("GPS GPSTimeStamp"),
            "gps_datestamp": exif.get("GPS GPSDateStamp"),
        }

    def _analyze_metadata_anomalies(self, metadata: Dict) -> List[str]:
        """Check for suspicious patterns in metadata."""
        warnings = []

        # Warning: No EXIF at all
        if not metadata.get("exif"):
            warnings.append(
                "NO_EXIF: Image has no EXIF metadata - may indicate AI generation or metadata stripping"
            )

        # Warning: Missing camera info but has other EXIF
        if metadata.get("exif") and not metadata.get("camera", {}).get("make"):
            warnings.append(
                "NO_CAMERA: Has EXIF but missing camera make/model - may indicate editing software origin"
            )

        # Warning: Software field indicates editing
        software = metadata.get("camera", {}).get("software", "") or ""
        editing_keywords = ["photoshop", "gimp", "lightroom", "canva", "snapseed", "pixlr", "firefly"]
        if any(kw in software.lower() for kw in editing_keywords):
            warnings.append(f"EDITING_SOFTWARE: Software field indicates editing: {software}")

        # Warning: Timestamp inconsistencies
        timestamps = metadata.get("timestamps", {})
        original = timestamps.get("datetime_original")
        digitized = timestamps.get("datetime_digitized")
        modified = timestamps.get("datetime_modified")

        if original and modified and original != modified:
            warnings.append("TIMESTAMP_MISMATCH: Original and modified timestamps differ")

        if digitized and original and digitized != original:
            warnings.append("DIGITIZED_MISMATCH: Digitized timestamp differs from original")

        # Warning: GPS present but no camera info
        if metadata.get("gps") and not metadata.get("camera", {}).get("make"):
            warnings.append(
                "GPS_NO_CAMERA: Has GPS data but no camera info - may indicate metadata injection"
            )

        return warnings
