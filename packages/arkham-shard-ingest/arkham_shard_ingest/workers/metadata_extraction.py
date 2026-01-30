"""
Shared metadata extraction for the ingest pipeline (single source of truth).

- EXIFTool: preferred when available (subprocess exiftool -m -u -P -j). https://exiftool.org
- Normalizes output to document_metadata schema (author, title, dates, gps_data, etc.).
- Filesystem times from path.stat().
- Language detection on extracted text (langdetect; fallback "en" if unavailable or detection fails).
- PII in metadata/text is handled by the PII shard in ingest _register_document.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# EXIFTool tag names (with group prefix like "XMP:Author" or "Author") -> our metadata key
EXIFTOOL_TO_META = {
    "Author": "author",
    "Creator": "creator",
    "Producer": "producer",
    "Title": "title",
    "Subject": "subject",
    "Keywords": "keywords",
    "CreateDate": "creation_date",
    "CreationDate": "creation_date",
    "ModifyDate": "modification_date",
    "ModificationDate": "modification_date",
    "DateCreated": "creation_date",
    "DateModified": "modification_date",
    "LastModifiedBy": "last_modified_by",
    "NumberOfPages": "num_pages",
    "PageCount": "num_pages",
    "Pages": "num_pages",
    "Encrypted": "is_encrypted",
    "Software": "software",
    "Application": "creator",
}


def _get_nested_field(raw: Dict[str, Any], field_path: str) -> Any:
    """Get a field value from exiftool raw (Group:Tag or nested Group.Tag)."""
    if not raw:
        return None
    # Try direct key (exiftool uses Group:Tag)
    if field_path in raw:
        return raw[field_path]
    # Try match by suffix (e.g. any key ending with :Author)
    tag = field_path.split(":")[-1] if ":" in field_path else field_path
    for k, v in raw.items():
        if k == "SourceFile":
            continue
        if k.endswith(":" + tag) or k == tag:
            return v
    # Nested: Group.Tag
    parts = field_path.replace(":", ".").split(".")
    current = raw
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _parse_date(value: Any) -> Optional[str]:
    """Parse date value to ISO string. Handles PDF D: format and common formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    s = str(value).strip()
    if not s:
        return None
    # PDF date format D:YYYYMMDDHHmmSS
    if s.startswith("D:"):
        s = s[2:]
        try:
            if len(s) >= 14:
                return f"{s[0:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}:{s[12:14]}"
            if len(s) >= 8:
                return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        except (ValueError, IndexError):
            pass
        return s
    # Common formats
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.isoformat()
        except ValueError:
            continue
    return s


def _flatten_raw_for_search(raw: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested exiftool raw to key -> value for certificate/signature search."""
    out = {}
    if not raw or not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        key = f"{prefix}:{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten_raw_for_search(v, key))
        else:
            out[key] = v
    return out


def _extract_certificate_envelope_metadata(raw: Dict[str, Any], flat: Dict[str, Any]) -> Dict[str, Any]:
    """Extract certificate/envelope related fields from exiftool raw (Sperling-style)."""
    cert_keys = [
        # PDF digital signatures
        "PDF:SignerName", "PDF:SignerContactInfo", "PDF:SigningDate",
        "PDF:Signature", "PDF:SignatureType", "PDF:SignatureVersion",
        "PDF:SignatureCreator", "PDF:SignatureReason", "PDF:SignatureLocation",
        "PDF:SignatureTime", "PDF:SignatureHandler", "PDF:SignatureBuild",
        "PDF:SignatureSubFilter", "PDF:SignatureByteRange",
        # Office document signatures
        "Microsoft:Signer", "Microsoft:SignatureTime", "Microsoft:SignatureType",
        "Microsoft:SignatureCreator", "Microsoft:SignatureReason",
        # XMP signature fields
        "XMP:SignerName", "XMP:SigningDate", "XMP:Signature",
        # General certificate fields
        "Certificate", "CertificateSubject", "CertificateIssuer",
        "CertificateSerialNumber", "CertificateFingerprint",
        "CertificateAuthority", "CertificateVersion", "CertificateAlgorithm",
        "CertificateValidFrom", "CertificateValidTo", "CertificateKeyUsage",
        # Encryption/Envelope fields
        "Encryption", "EncryptionType", "EncryptionAlgorithm", "EncryptionKeyLength",
        "EncryptionMethod", "EncryptionRecipient", "Envelope", "EnvelopeType",
        "EnvelopeRecipient", "EnvelopeSender", "EnvelopeDate",
        # PKCS fields
        "PKCS", "PKCS7", "PKCS12", "PKCS#7", "PKCS#12",
        # X.509 certificate fields
        "X509", "X509Subject", "X509Issuer", "X509SerialNumber",
        "X509Fingerprint", "X509AuthorityKeyIdentifier",
        # Cryptographic fields
        "Crypt", "CryptFilter", "CryptMethod", "CryptAlgorithm",
        "CryptRecipient", "CryptKeyLength",
    ]
    result = {}
    for f in cert_keys:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v is not None:
            result[f] = v
    for key, value in flat.items():
        kl = key.lower()
        if any(term in kl for term in ["sign", "cert", "encrypt", "envelope", "x509", "pkcs", "crypt"]):
            if key not in result:
                result[key] = value
    return result


def _extract_signature_certificate_metadata(raw: Dict[str, Any], flat: Dict[str, Any]) -> Dict[str, Any]:
    """Extract signature-specific certificate metadata (signer, signing date, etc.)."""
    sig_keys = [
        "PDF:SignerName", "PDF:SignerContactInfo", "PDF:SigningDate", "PDF:Signature", "PDF:SignatureType",
        "PDF:SignatureVersion", "PDF:SignatureCreator", "PDF:SignatureReason", "PDF:SignatureLocation",
        "PDF:SignatureTime", "PDF:SignatureHandler", "PDF:SignatureBuild",
        "PDF:SignatureSubFilter", "PDF:SignatureByteRange",
        "Microsoft:Signer", "Microsoft:SignatureTime", "Microsoft:SignatureType",
        "Microsoft:SignatureCreator", "Microsoft:SignatureReason",
        "XMP:SignerName", "XMP:SigningDate", "XMP:Signature",
    ]
    result = {}
    for f in sig_keys:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v is not None:
            result[f] = v
    for key, value in flat.items():
        if "sign" in key.lower() and ("signer" in key.lower() or "signing" in key.lower() or "signature" in key.lower()):
            if key not in result:
                result[key] = value
    return result


def process_exiftool_key_fields(raw_list: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Process key EXIF/metadata fields from exiftool output: authors list, dates arrays,
    last printed, version, application version, key EXIF (pixels, resolution, device, artist),
    certificate_envelope_metadata, signature_certificate_metadata.
    """
    if not raw_list:
        return {}
    raw = raw_list[0]
    flat = _flatten_raw_for_search(raw)
    meta: Dict[str, Any] = {}

    # Title
    for f in ['Title', 'DocumentTitle', 'PDF:Title', 'XMP:Title', 'DC:Title', 'IPTC:ObjectName',
              'Microsoft:Title', 'EXIF:Title', 'ID3:Title']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            meta["title"] = str(v).strip() if not isinstance(v, list) else (str(v[0]).strip() if v else "")
            if meta["title"]:
                break

    # Subject
    for f in ['Subject', 'Description', 'PDF:Subject', 'XMP:Description', 'DC:Description',
              'IPTC:Caption', 'Microsoft:Subject', 'EXIF:ImageDescription', 'ID3:Comment']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            meta["subject"] = str(v).strip() if not isinstance(v, list) else (str(v[0]).strip() if v else "")
            if meta["subject"]:
                break

    # Keywords (may be list; store as comma-separated string for TEXT column)
    keyword_fields = ['Keywords', 'Keyword', 'XPKeywords', 'XMP:Subject', 'PDF:Keywords',
                     'IPTC:Keywords', 'Microsoft:Keywords', 'EXIF:Keywords', 'ID3:Keywords']
    keywords_seen = []
    for f in keyword_fields:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            parts = v if isinstance(v, list) else [v]
            for p in parts:
                s = str(p).strip()
                if s and s not in keywords_seen:
                    keywords_seen.append(s)
    if keywords_seen:
        meta["keywords"] = ", ".join(keywords_seen)

    # Authors: collect all (Author, Creator, Artist, etc.)
    author_fields = ['Author', 'Creator', 'Artist', 'Owner', 'By-line',
                         'OwnerName', 'Microsoft:Author', 'XMP:Creator',
                         'EXIF:Artist', 'ID3:Artist', 'PDF:Author',
                         'LastModifiedBy', 'CreatorTool']
    all_authors = set()
    for f in author_fields:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            for a in (v if isinstance(v, list) else [v]):
                s = str(a).strip()
                if s:
                    all_authors.add(s)
    if all_authors:
        meta["authors"] = sorted(list(all_authors))
        meta["author"] = meta["authors"][0]

    # Creation dates (all sources)
    creation_fields = ['CreateDate', 'DateTimeOriginal', 'CreationDate', 'DateCreated',
                         'Microsoft:CreationDate', 'XMP:CreationDate', 'EXIF:CreationDate',
                         'ID3:CreationDate', 'PDF:CreationDate']
    creation_dates = []
    for f in creation_fields:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            ds = _parse_date(v)
            if ds and ds not in creation_dates:
                creation_dates.append(ds)
    if creation_dates:
        meta["creation_dates"] = creation_dates
        meta["creation_date"] = creation_dates[0]

    # Modification dates
    mod_fields = ['ModifyDate', 'FileModifyDate', 'ModificationDate', 'LastModified',
                         'Microsoft:ModificationDate', 'XMP:ModificationDate', 'EXIF:ModificationDate',
                         'ID3:ModificationDate', 'PDF:ModificationDate']
    mod_dates = []
    for f in mod_fields:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            ds = _parse_date(v)
            if ds and ds not in mod_dates:
                mod_dates.append(ds)
    if mod_dates:
        meta["modification_dates"] = mod_dates
        meta["modification_date"] = mod_dates[-1]

    # Accessed dates
    access_fields = ['AccessDate', 'LastAccessed', 'FileAccessDate',
                         'Microsoft:AccessDate', 'XMP:AccessDate', 'EXIF:AccessDate',
                         'ID3:AccessDate', 'PDF:AccessDate']
    access_dates = []
    for f in access_fields:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            ds = _parse_date(v)
            if ds and ds not in access_dates:
                access_dates.append(ds)
    if access_dates:
        meta["accessed_dates"] = access_dates
        meta["last_accessed_date"] = access_dates[-1]

    # Last printed
    for f in ['LastPrinted', 'PrintDate', 'DocumentPrintDate',
                         'Microsoft:LastPrinted', 'XMP:LastPrinted', 'EXIF:LastPrinted',
                         'ID3:LastPrinted', 'PDF:LastPrinted']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            meta["last_printed_date"] = _parse_date(v)
            break

    # File version
    for f in ['Version', 'PDFVersion', 'FileVersion', 'DocumentVersion',
                         'Microsoft:Version', 'XMP:Version', 'EXIF:Version',
                         'ID3:Version', 'PDF:Version']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            meta["file_version"] = str(v)
            break

    # Application / software version
    for f in ['ApplicationVersion', 'CreatorTool', 'Software', 'Producer', 'Application',
                         'Microsoft:ApplicationVersion', 'XMP:ApplicationVersion', 'EXIF:ApplicationVersion',
                         'ID3:ApplicationVersion', 'SourceProgram', 'PDF:Producer',
                         'XMP:CreatorTool', 'APP14:Adobe', 'PDF:ApplicationVersion', 'Microsoft:Application',
                         'XMP:ApplicationVersion', 'EXIF:ApplicationVersion', 'ID3:ApplicationVersion']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            meta["application_version"] = str(v) if not isinstance(v, list) else str(v[0])
            break

    # Key EXIF: pixels, resolution, device, artist
    for f in ['ImageWidth', 'ExifImageWidth', 'Microsoft:ImageWidth', 'XMP:ImageWidth', 'EXIF:ImageWidth',
                         'ID3:ImageWidth', 'PDF:ImageWidth', 'ImagePixelWidth', 'ExifImagePixelWidth', 'Microsoft:ImagePixelWidth',
                         'XMP:ImagePixelWidth', 'EXIF:ImagePixelWidth', 'ID3:ImagePixelWidth', 'PDF:ImagePixelWidth', 'ImagePixelXDimension', 'ExifImagePixelXDimension', 'Microsoft:ImagePixelXDimension',
                         'XMP:ImagePixelXDimension', 'EXIF:ImagePixelXDimension', 'ID3:ImagePixelXDimension', 'PDF:ImagePixelXDimension']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v is not None:
            try:
                meta["image_width"] = int(float(str(v).split()[0])) if isinstance(v, str) and " " in str(v) else int(float(v))
            except (TypeError, ValueError):
                pass
            break
    for f in ['ImageHeight', 'ExifImageLength', 'Microsoft:ImageHeight', 'XMP:ImageHeight', 'EXIF:ImageHeight',
                         'ID3:ImageHeight', 'PDF:ImageHeight', 'ImageLength', 'ExifImageLength', 'Microsoft:ImageLength',
                         'XMP:ImageLength', 'EXIF:ImageLength', 'ID3:ImageLength', 'PDF:ImageLength', 'ImagePixelLength', 'ExifImagePixelLength', 'Microsoft:ImagePixelLength',
                         'XMP:ImagePixelLength', 'EXIF:ImagePixelLength', 'ID3:ImagePixelLength', 'PDF:ImagePixelLength', 'ImagePixelYDimension', 'ExifImagePixelYDimension', 'Microsoft:ImagePixelYDimension',
                         'XMP:ImagePixelYDimension', 'EXIF:ImagePixelYDimension', 'ID3:ImagePixelYDimension', 'PDF:ImagePixelYDimension']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v is not None:
            try:
                meta["image_height"] = int(float(str(v).split()[0])) if isinstance(v, str) and " " in str(v) else int(float(v))
            except (TypeError, ValueError):
                pass
            break
    for f in ['XResolution', 'ExifXResolution', 'Microsoft:XResolution', 'XMP:XResolution', 'EXIF:XResolution',
                         'ID3:XResolution', 'PDF:XResolution']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v is not None:
            try:
                meta["x_resolution"] = float(str(v).split()[0]) if isinstance(v, str) and " " in str(v) else float(v)
                break
            except (TypeError, ValueError):
                pass
    for f in ['YResolution', 'ExifYResolution', 'Microsoft:YResolution', 'XMP:YResolution', 'EXIF:YResolution',
                         'ID3:YResolution', 'PDF:YResolution']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v is not None:
            try:
                meta["y_resolution"] = float(str(v).split()[0]) if isinstance(v, str) and " " in str(v) else float(v)
                break
            except (TypeError, ValueError):
                pass
    for f in ['Make', 'DeviceMake', 'Microsoft:Make', 'XMP:Make', 'EXIF:Make',
                         'ID3:Make', 'PDF:Make']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            meta["device_make"] = str(v)
            break
    for f in ['Model', 'DeviceModel', 'Microsoft:Model', 'XMP:Model', 'EXIF:Model',
                         'ID3:Model', 'PDF:Model']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v:
            meta["device_model"] = str(v)
            break
    for f in ['Artist', 'Creator', 'Microsoft:Artist', 'XMP:Artist', 'EXIF:Artist',
                         'ID3:Artist', 'PDF:Artist']:
        v = flat.get(f) or _get_nested_field(raw, f)
        if v and not meta.get("artist"):
            meta["artist"] = str(v) if not isinstance(v, list) else str(v[0])
            break

    # Certificate envelope and signature metadata
    cert_envelope = _extract_certificate_envelope_metadata(raw, flat)
    if cert_envelope:
        meta["certificate_envelope_metadata"] = cert_envelope
    sig_cert = _extract_signature_certificate_metadata(raw, flat)
    if sig_cert:
        meta["signature_certificate_metadata"] = sig_cert

    return meta


def run_exiftool(path: Path) -> Optional[List[Dict[str, Any]]]:
    """
    Run EXIFTool on a file. Returns parsed JSON array or None if unavailable/fails.

    Uses: exiftool -m -u -P -j <path>
    -m: Ignore minor errors and warnings.
    -u: Extract unknown tags.
    -P: Preserve file modification date/time.
    -j: Output in JSON format.
    """
    try:
        result = subprocess.run(
            ["exiftool", "-m", "-u", "-P", "-j", str(path)],
            capture_output=True,
            timeout=30,
            text=False,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        data = json.loads(result.stdout.decode("utf-8", errors="replace"))
        if isinstance(data, list) and len(data) > 0:
            return data
        if isinstance(data, dict):
            return [data]
        return None
    except FileNotFoundError:
        logger.debug("exiftool not found in PATH")
        return None
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        logger.debug("exiftool failed: %s", e)
        return None


def _flat_exiftool(raw_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Flatten first element of exiftool JSON (group:tag -> value)."""
    if not raw_list:
        return {}
    d = raw_list[0]
    out = {}
    for k, v in d.items():
        if k == "SourceFile":
            continue
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        # Key can be "Group:Tag" or "Tag"
        key = k.split(":")[-1] if ":" in k else k
        out[key] = v
    return out


def normalize_exiftool_to_metadata(raw_list: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Convert EXIFTool JSON output to document_metadata dict (single source of truth schema).
    Raw exiftool output is stored in the returned dict under key "exiftool_metadata".
    """
    if not raw_list:
        return {}, None
    flat = _flat_exiftool(raw_list)
    meta: Dict[str, Any] = {}
    raw_for_storage = raw_list[0].copy()
    # Remove SourceFile from stored raw to avoid paths
    raw_for_storage.pop("SourceFile", None)

    for tag_name, value in flat.items():
        if value is None:
            continue
        our_key = EXIFTOOL_TO_META.get(tag_name)
        if our_key:
            if our_key == "num_pages":
                try:
                    meta["num_pages"] = int(value)
                except (TypeError, ValueError):
                    pass
            elif our_key == "is_encrypted":
                meta["is_encrypted"] = bool(value and str(value).lower() not in ("false", "no", "0"))
            elif our_key == "software":
                # Append to software_list
                meta.setdefault("software", [])
                if isinstance(meta["software"], list):
                    meta["software"].append(str(value))
                else:
                    meta["software"] = [meta["software"], str(value)]
            else:
                meta[our_key] = value

    # GPS: collect into gps_data
    gps = {}
    for k, v in flat.items():
        if v is None:
            continue
        kk = k.lower()
        if "gps" in kk or "latitude" in kk or "longitude" in kk or "altitude" in kk:
            gps[k] = v
    if gps:
        meta["gps_data"] = gps

    # Normalize software to list
    if "software" in meta and not isinstance(meta["software"], list):
        meta["software"] = [meta["software"]]

    # Process key fields (authors list, dates arrays, last printed, version, EXIF key, cert/signature)
    key_meta = process_exiftool_key_fields(raw_list)
    for k, v in key_meta.items():
        if v is not None and (k not in meta or meta[k] is None or meta[k] == "" or meta[k] == []):
            meta[k] = v

    # Store raw EXIFTool output for downstream
    meta["exiftool_metadata"] = raw_for_storage

    return meta


def add_filesystem_times(path: Path, meta: Dict[str, Any]) -> None:
    """Add filesystem stat times and file size to meta (mutates meta)."""
    try:
        st = path.stat()
        meta["file_size_bytes"] = st.st_size
        # st_ctime on Windows is creation; on Unix may be metadata change
        meta["filesystem_creation_time"] = datetime.fromtimestamp(st.st_ctime).isoformat()
        meta["filesystem_modification_time"] = datetime.fromtimestamp(st.st_mtime).isoformat()
        meta["filesystem_access_time"] = datetime.fromtimestamp(st.st_atime).isoformat()

        # Birth time: true creation time on macOS/FreeBSD and some Linux filesystems
        if hasattr(st, "st_birthtime"):
            meta["filesystem_creation_time"] = datetime.fromtimestamp(st.st_birthtime).isoformat()
    except OSError:
        pass


def detect_language(text: str) -> str:
    """
    Detect the language of text.

    Args:
        text: Input text (at least ~50 characters recommended for reliable detection).

    Returns:
        ISO language code (e.g. en, es, fr, de). Returns "en" if langdetect is not
        installed, if detection fails, or if text is too short.
    """
    if not text or not text.strip() or len(text.strip()) < 50:
        logger.debug("Language detection failed: text too short")
        return "en"
    try:
        from langdetect import detect  # type: ignore[import-untyped]

        return detect(text)
    except Exception as e:
        logger.warning("Language detection failed: %s", e)
        return "en"

