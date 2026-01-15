"""Hidden content detection module.

Implements steganography and hidden data detection algorithms:
- Shannon entropy analysis
- LSB (Least Significant Bit) pattern analysis
- Chi-square statistical tests
- File type/magic byte mismatch detection
- Histogram anomaly detection
"""

import logging
import math
import uuid
from collections import Counter
from datetime import datetime
from typing import Tuple

import numpy as np
from scipy import stats

from .models import (
    EntropyRegion,
    HiddenContentConfig,
    HiddenContentScan,
    HiddenContentScanStatus,
    HiddenContentScanType,
    LSBAnalysisResult,
    StegoIndicator,
)

logger = logging.getLogger(__name__)


class HiddenContentDetector:
    """
    Detector for hidden content in files.

    Implements multiple detection strategies:
    - Shannon entropy analysis for detecting encrypted/compressed/hidden data
    - LSB (Least Significant Bit) pattern analysis for steganography
    - Chi-square statistical tests for LSB anomalies
    - File type/magic byte mismatch detection
    - Histogram anomaly detection for images
    """

    def __init__(self, config: HiddenContentConfig | None = None):
        self.config = config or HiddenContentConfig()
        self._magic = None

    def _get_magic(self):
        """Lazy load python-magic with fallback for missing libmagic."""
        if self._magic is None:
            try:
                import magic
                self._magic = magic.Magic(mime=True)
            except ImportError:
                logger.warning("python-magic not available - file type detection disabled")
                self._magic = False  # Use False to indicate unavailable
            except Exception as e:
                # libmagic not installed at OS level
                logger.warning(f"libmagic not available: {e} - file type detection disabled")
                self._magic = False
        return self._magic if self._magic is not False else None

    def calculate_entropy(self, data: bytes) -> float:
        """
        Calculate Shannon entropy of byte data.

        Entropy ranges from 0 (no randomness) to 8 (maximum randomness).
        High entropy (>7.5) suggests encrypted or compressed data.

        Args:
            data: Raw byte data to analyze

        Returns:
            Shannon entropy value (0.0 to 8.0)
        """
        if not data:
            return 0.0

        byte_counts = Counter(data)
        total = len(data)

        entropy = 0.0
        for count in byte_counts.values():
            if count > 0:
                probability = count / total
                entropy -= probability * math.log2(probability)

        return entropy

    def analyze_entropy_regions(
        self,
        data: bytes,
        chunk_size: int | None = None
    ) -> list[EntropyRegion]:
        """
        Analyze entropy in chunks to find high-entropy regions.

        High entropy regions may indicate:
        - Encrypted data
        - Compressed data
        - Steganographic payloads
        - Random noise (potentially hiding data)

        Args:
            data: Raw byte data
            chunk_size: Size of each chunk (defaults to config value)

        Returns:
            List of entropy regions with anomaly flags
        """
        chunk_size = chunk_size or self.config.entropy_chunk_size
        regions = []
        threshold = self.config.entropy_threshold_suspicious

        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            if len(chunk) < 64:  # Skip tiny trailing chunks
                continue

            entropy = self.calculate_entropy(chunk)

            is_anomalous = entropy >= threshold
            description = ""
            if entropy >= self.config.entropy_threshold_high:
                description = "Near-random data (possible encryption/steganography)"
            elif entropy >= threshold:
                description = "Elevated entropy (suspicious region)"

            regions.append(EntropyRegion(
                start_offset=i,
                end_offset=min(i + chunk_size, len(data)),
                entropy_value=entropy,
                is_anomalous=is_anomalous,
                description=description,
            ))

        return regions

    def analyze_lsb_image(self, image_path: str) -> LSBAnalysisResult | None:
        """
        Analyze LSB patterns in an image for steganography detection.

        Uses chi-square analysis on LSB distribution.
        Natural images have slight bias in LSB distribution; steganography
        tends to create a perfectly uniform 50/50 distribution.

        Args:
            image_path: Path to image file

        Returns:
            LSB analysis results with suspicion flag, or None if analysis fails
        """
        try:
            from PIL import Image
        except ImportError:
            logger.warning("Pillow not available - LSB analysis disabled")
            return None

        try:
            with Image.open(image_path) as img:
                if img.mode not in ('RGB', 'RGBA', 'L'):
                    img = img.convert('RGB')

                pixels = list(img.getdata())
                sample_size = min(len(pixels), self.config.lsb_sample_size)

                if len(pixels) > sample_size:
                    indices = np.random.choice(len(pixels), sample_size, replace=False)
                    pixels = [pixels[i] for i in indices]

                # Extract LSBs from all color channels
                lsbs = []
                for pixel in pixels:
                    if isinstance(pixel, int):
                        # Grayscale
                        lsbs.append(pixel & 1)
                    else:
                        # RGB or RGBA
                        for channel in pixel[:3]:
                            lsbs.append(channel & 1)

                if not lsbs:
                    return None

                ones = sum(lsbs)
                zeros = len(lsbs) - ones

                # Chi-square test against expected 50/50
                expected = len(lsbs) / 2
                chi_square = ((ones - expected) ** 2 + (zeros - expected) ** 2) / expected
                p_value = 1 - stats.chi2.cdf(chi_square, df=1)

                bit_ratio = ones / len(lsbs)
                # Very close to 50/50 is suspicious for natural images
                # Natural images typically have some bias
                is_suspicious = (
                    p_value > self.config.chi_square_threshold and
                    0.48 <= bit_ratio <= 0.52
                )

                return LSBAnalysisResult(
                    bit_ratio=bit_ratio,
                    chi_square_value=chi_square,
                    chi_square_p_value=p_value,
                    is_suspicious=is_suspicious,
                    confidence=1.0 - abs(0.5 - bit_ratio) * 2,
                    sample_size=len(lsbs),
                )

        except Exception as e:
            logger.warning(f"LSB analysis failed for {image_path}: {e}")
            return None

    def detect_file_type_mismatch(
        self,
        file_path: str,
        claimed_extension: str
    ) -> Tuple[bool, str, str]:
        """
        Check if file content matches its extension.

        Mismatches may indicate:
        - Renamed files to bypass filters
        - Hidden data appended to legitimate files
        - Polyglot files (valid as multiple formats)

        Args:
            file_path: Path to file
            claimed_extension: File extension (e.g., ".jpg")

        Returns:
            Tuple of (is_mismatch, expected_mime, actual_mime)
        """
        magic = self._get_magic()
        if not magic:
            return False, "unknown", "unknown"

        try:
            actual_mime = magic.from_file(file_path)
        except Exception as e:
            logger.warning(f"Magic detection failed for {file_path}: {e}")
            return False, "unknown", "unknown"

        # Mapping of extensions to expected MIME types
        extension_mime_map = {
            '.jpg': ['image/jpeg'],
            '.jpeg': ['image/jpeg'],
            '.png': ['image/png'],
            '.gif': ['image/gif'],
            '.bmp': ['image/bmp', 'image/x-ms-bmp'],
            '.tiff': ['image/tiff'],
            '.tif': ['image/tiff'],
            '.webp': ['image/webp'],
            '.pdf': ['application/pdf'],
            '.doc': ['application/msword'],
            '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            '.xls': ['application/vnd.ms-excel'],
            '.xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
            '.ppt': ['application/vnd.ms-powerpoint'],
            '.pptx': ['application/vnd.openxmlformats-officedocument.presentationml.presentation'],
            '.txt': ['text/plain'],
            '.html': ['text/html'],
            '.htm': ['text/html'],
            '.xml': ['text/xml', 'application/xml'],
            '.json': ['application/json', 'text/json'],
            '.zip': ['application/zip'],
            '.rar': ['application/x-rar-compressed', 'application/vnd.rar'],
            '.7z': ['application/x-7z-compressed'],
            '.tar': ['application/x-tar'],
            '.gz': ['application/gzip', 'application/x-gzip'],
            '.mp3': ['audio/mpeg'],
            '.wav': ['audio/wav', 'audio/x-wav'],
            '.mp4': ['video/mp4'],
            '.avi': ['video/x-msvideo'],
        }

        expected_mimes = extension_mime_map.get(claimed_extension.lower(), [])
        is_mismatch = actual_mime not in expected_mimes if expected_mimes else False

        return is_mismatch, ', '.join(expected_mimes) if expected_mimes else 'unknown', actual_mime

    def calculate_file_hashes(self, data: bytes) -> dict:
        """
        Calculate multiple hash digests for a file.

        Useful for integrity verification and duplicate detection.

        Args:
            data: Raw file bytes

        Returns:
            Dict with md5, sha256, sha512 hashes
        """
        import hashlib
        return {
            'md5': hashlib.md5(data).hexdigest(),
            'sha256': hashlib.sha256(data).hexdigest(),
            'sha512': hashlib.sha512(data).hexdigest(),
        }

    def analyze_histogram(self, image_path: str) -> dict | None:
        """
        Analyze image histogram for anomalies.

        LSB steganography can cause subtle histogram artifacts:
        - Pairs of adjacent bins with similar counts (PoV attacks)
        - Unusual smoothness in what should be natural distribution

        Args:
            image_path: Path to image file

        Returns:
            Dict with histogram analysis results, or None if fails
        """
        try:
            from PIL import Image
        except ImportError:
            return None

        try:
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Get histogram for each channel
                histogram = img.histogram()

                # Analyze R, G, B channels separately
                r_hist = histogram[0:256]
                g_hist = histogram[256:512]
                b_hist = histogram[512:768]

                # Calculate pair differences for PoV detection
                def pair_analysis(hist):
                    pairs_close = 0
                    total_pairs = 0
                    for i in range(0, 256, 2):
                        if hist[i] > 0 or hist[i + 1] > 0:
                            total_pairs += 1
                            if abs(hist[i] - hist[i + 1]) < 10:
                                pairs_close += 1
                    return pairs_close / total_pairs if total_pairs > 0 else 0

                r_poi = pair_analysis(r_hist)
                g_poi = pair_analysis(g_hist)
                b_poi = pair_analysis(b_hist)
                avg_poi = (r_poi + g_poi + b_poi) / 3

                # High PoV (pairs of values) ratio is suspicious
                is_suspicious = avg_poi > 0.7

                return {
                    "r_pair_ratio": r_poi,
                    "g_pair_ratio": g_poi,
                    "b_pair_ratio": b_poi,
                    "average_pair_ratio": avg_poi,
                    "is_suspicious": is_suspicious,
                }

        except Exception as e:
            logger.warning(f"Histogram analysis failed: {e}")
            return None

    def full_scan(
        self,
        doc_id: str,
        file_path: str,
        file_data: bytes,
        file_extension: str,
        mime_type: str,
    ) -> HiddenContentScan:
        """
        Perform complete hidden content scan.

        Runs all applicable detection algorithms based on file type:
        - Entropy analysis (all files)
        - File type mismatch detection (all files)
        - LSB analysis (images only)
        - Histogram analysis (images only)

        Args:
            doc_id: Document identifier
            file_path: Path to file on disk
            file_data: Raw file bytes
            file_extension: File extension
            mime_type: MIME type from metadata

        Returns:
            Complete scan results
        """
        scan = HiddenContentScan(
            id=str(uuid.uuid4()),
            doc_id=doc_id,
            scan_type=HiddenContentScanType.STEGO,
        )

        findings = []
        indicators = []

        try:
            # Check file size limit
            file_size_mb = len(file_data) / (1024 * 1024)
            if file_size_mb > self.config.max_file_size_mb:
                scan.findings = [f"File too large ({file_size_mb:.1f}MB) - skipped"]
                scan.scan_status = HiddenContentScanStatus.COMPLETED
                scan.completed_at = datetime.utcnow()
                return scan

            # 1. Global entropy analysis
            if self.config.detect_entropy:
                scan.entropy_global = self.calculate_entropy(file_data)
                scan.entropy_regions = self.analyze_entropy_regions(file_data)

                high_entropy_regions = [r for r in scan.entropy_regions if r.is_anomalous]
                if high_entropy_regions:
                    findings.append(f"Found {len(high_entropy_regions)} high-entropy regions")
                    indicators.append(StegoIndicator(
                        indicator_type="entropy_spike",
                        confidence=0.7,
                        location=f"{len(high_entropy_regions)} regions",
                        details={"region_count": len(high_entropy_regions)},
                    ))

                # Check global entropy
                if scan.entropy_global and scan.entropy_global >= self.config.entropy_threshold_high:
                    findings.append(f"Very high global entropy: {scan.entropy_global:.3f}")
                    indicators.append(StegoIndicator(
                        indicator_type="high_global_entropy",
                        confidence=0.8,
                        location="global",
                        details={"entropy": scan.entropy_global},
                    ))

            # 2. File type mismatch detection
            if self.config.detect_magic_mismatch:
                is_mismatch, expected, actual = self.detect_file_type_mismatch(
                    file_path, file_extension
                )
                scan.magic_expected = expected
                scan.magic_actual = actual
                scan.file_mismatch = is_mismatch

                if is_mismatch:
                    findings.append(f"File type mismatch: expected {expected}, found {actual}")
                    indicators.append(StegoIndicator(
                        indicator_type="file_type_mismatch",
                        confidence=0.9,
                        location="global",
                        details={"expected": expected, "actual": actual},
                    ))

            # 3. LSB analysis for images
            is_image = mime_type and 'image' in mime_type.lower()
            if self.config.detect_lsb and is_image:
                lsb_result = self.analyze_lsb_image(file_path)
                if lsb_result:
                    scan.lsb_result = lsb_result

                    if lsb_result.is_suspicious:
                        findings.append(
                            f"Suspicious LSB pattern: {lsb_result.bit_ratio:.3f} ratio, "
                            f"p-value={lsb_result.chi_square_p_value:.4f}"
                        )
                        indicators.append(StegoIndicator(
                            indicator_type="lsb_pattern",
                            confidence=lsb_result.confidence,
                            location="pixel_lsbs",
                            details={
                                "bit_ratio": lsb_result.bit_ratio,
                                "chi_square": lsb_result.chi_square_value,
                                "p_value": lsb_result.chi_square_p_value,
                            },
                        ))

            # 4. Histogram analysis for images
            if self.config.detect_histogram and is_image:
                hist_result = self.analyze_histogram(file_path)
                if hist_result and hist_result.get("is_suspicious"):
                    findings.append(
                        f"Suspicious histogram pattern: pair ratio {hist_result['average_pair_ratio']:.3f}"
                    )
                    indicators.append(StegoIndicator(
                        indicator_type="histogram_anomaly",
                        confidence=0.6,
                        location="color_histogram",
                        details=hist_result,
                    ))

            scan.findings = findings
            scan.stego_indicators = indicators
            scan.stego_confidence = max([i.confidence for i in indicators], default=0.0)
            scan.scan_status = HiddenContentScanStatus.COMPLETED
            scan.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Hidden content scan failed for {doc_id}: {e}", exc_info=True)
            scan.scan_status = HiddenContentScanStatus.FAILED
            scan.metadata["error"] = str(e)

        return scan

    def quick_scan(
        self,
        doc_id: str,
        file_data: bytes,
    ) -> dict:
        """
        Perform quick entropy-only scan without file type detection.

        Useful for fast screening of large document sets.

        Args:
            doc_id: Document identifier
            file_data: Raw file bytes

        Returns:
            Dict with quick scan results
        """
        global_entropy = self.calculate_entropy(file_data)
        regions = self.analyze_entropy_regions(file_data)
        high_regions = [r for r in regions if r.is_anomalous]

        return {
            "doc_id": doc_id,
            "global_entropy": global_entropy,
            "is_high_entropy": global_entropy >= self.config.entropy_threshold_high,
            "suspicious_regions": len(high_regions),
            "requires_full_scan": len(high_regions) > 0 or global_entropy >= self.config.entropy_threshold_suspicious,
        }
