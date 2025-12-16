"""
Hidden Content Detection Service

Detects steganography, hidden text, whitespace anomalies, and other concealment
techniques in documents. Useful for forensic analysis and investigative journalism.
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging
from collections import Counter
import unicodedata

from config.settings import DATABASE_URL

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.arkham.services.db.models import Document, Chunk, PageOCR

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection



class HiddenContentDetector:
    """Service for detecting hidden or concealed content in documents."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def detect_all_hidden_content(self, doc_id: Optional[int] = None) -> List[Dict]:
        """
        Run all hidden content detectors.

        Args:
            doc_id: Optional document ID to check (if None, checks all documents)

        Returns:
            List of red flag dictionaries for detected hidden content
        """
        all_flags = []

        logger.info(f"Running hidden content detectors{f' for doc {doc_id}' if doc_id else ''}...")

        # Run each detector
        all_flags.extend(self.detect_invisible_characters(doc_id))
        all_flags.extend(self.detect_whitespace_anomalies(doc_id))
        all_flags.extend(self.detect_zero_width_characters(doc_id))
        all_flags.extend(self.detect_homoglyph_substitution(doc_id))
        all_flags.extend(self.detect_hidden_layers(doc_id))

        logger.info(f"Hidden content detection complete: {len(all_flags)} flags found")

        return all_flags

    def detect_invisible_characters(self, doc_id: Optional[int] = None) -> List[Dict]:
        """
        Detect invisible Unicode characters that may hide information.

        Detects:
        - Zero-width space (U+200B)
        - Zero-width joiner (U+200D)
        - Zero-width non-joiner (U+200C)
        - Soft hyphen (U+00AD)
        - Left-to-right/right-to-left marks

        Returns:
            List of red flags for invisible character usage
        """
        session = self.Session()
        flags = []

        try:
            # Invisible characters to detect
            invisible_chars = {
                '\u200B': 'Zero-Width Space',
                '\u200C': 'Zero-Width Non-Joiner',
                '\u200D': 'Zero-Width Joiner',
                '\u00AD': 'Soft Hyphen',
                '\u2060': 'Word Joiner',
                '\u180E': 'Mongolian Vowel Separator',
                '\uFEFF': 'Zero-Width No-Break Space',
                '\u202A': 'Left-to-Right Embedding',
                '\u202B': 'Right-to-Left Embedding',
                '\u202C': 'Pop Directional Formatting',
                '\u202D': 'Left-to-Right Override',
                '\u202E': 'Right-to-Left Override',
            }

            # Query chunks
            query = session.query(Chunk)
            if doc_id:
                query = query.filter(Chunk.doc_id == doc_id)

            chunks = query.all()

            for chunk in chunks:
                text = chunk.text
                if not text:
                    continue

                # Check for invisible characters
                found_chars = {}
                for char, name in invisible_chars.items():
                    count = text.count(char)
                    if count > 0:
                        found_chars[name] = count

                if found_chars:
                    # Calculate severity based on count
                    total_count = sum(found_chars.values())
                    severity = "CRITICAL" if total_count > 50 else "HIGH" if total_count > 10 else "MEDIUM"

                    flags.append({
                        "flag_type": "hidden_content",
                        "flag_category": "invisible_characters",
                        "severity": severity,
                        "title": "Invisible Unicode Characters Detected",
                        "description": f"Found {total_count} invisible Unicode characters in text. "
                                     f"These can be used for steganography or to hide malicious content. "
                                     f"Types detected: {', '.join(found_chars.keys())}",
                        "evidence": {
                            "invisible_chars": found_chars,
                            "total_count": total_count,
                            "chunk_preview": text[:200].replace('\u200B', '[ZWSP]').replace('\u200C', '[ZWNJ]')
                        },
                        "confidence": 0.9,
                        "doc_id": chunk.doc_id,
                        "chunk_id": chunk.id,
                        "entity_id": None,
                        "timeline_event_id": None
                    })

        except Exception as e:
            logger.error(f"Invisible character detection failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Invisible character flags: {len(flags)}")
        return flags

    def detect_whitespace_anomalies(self, doc_id: Optional[int] = None) -> List[Dict]:
        """
        Detect unusual whitespace patterns that may encode hidden information.

        Detects:
        - Excessive consecutive spaces (possible encoding)
        - Unusual space/tab mixing patterns
        - Trailing whitespace (steganography technique)

        Returns:
            List of red flags for whitespace anomalies
        """
        session = self.Session()
        flags = []

        try:
            query = session.query(Chunk)
            if doc_id:
                query = query.filter(Chunk.doc_id == doc_id)

            chunks = query.all()

            for chunk in chunks:
                text = chunk.text
                if not text:
                    continue

                anomalies = []

                # Detect excessive consecutive spaces (5+ spaces in a row)
                excessive_spaces = re.findall(r' {5,}', text)
                if excessive_spaces:
                    anomalies.append(f"{len(excessive_spaces)} instances of 5+ consecutive spaces")

                # Detect space/tab mixing (potential encoding)
                if '\t' in text and ' ' in text:
                    # Check for alternating patterns (suspicious)
                    space_tab_pattern = re.findall(r'[ \t]{10,}', text)
                    if space_tab_pattern:
                        anomalies.append(f"{len(space_tab_pattern)} mixed space/tab sequences")

                # Detect trailing whitespace on lines (steganography technique)
                lines_with_trailing = [line for line in text.split('\n') if line.endswith((' ', '\t'))]
                if len(lines_with_trailing) > 5:
                    anomalies.append(f"{len(lines_with_trailing)} lines with trailing whitespace")

                if anomalies:
                    severity = "HIGH" if len(anomalies) >= 2 else "MEDIUM"

                    flags.append({
                        "flag_type": "hidden_content",
                        "flag_category": "whitespace_anomalies",
                        "severity": severity,
                        "title": "Suspicious Whitespace Patterns Detected",
                        "description": f"Unusual whitespace usage detected. "
                                     f"Whitespace can be used to encode hidden messages. "
                                     f"Anomalies: {'; '.join(anomalies)}",
                        "evidence": {
                            "anomalies": anomalies,
                            "excessive_spaces_count": len(excessive_spaces) if excessive_spaces else 0,
                            "trailing_whitespace_lines": len(lines_with_trailing)
                        },
                        "confidence": 0.7,
                        "doc_id": chunk.doc_id,
                        "chunk_id": chunk.id,
                        "entity_id": None,
                        "timeline_event_id": None
                    })

        except Exception as e:
            logger.error(f"Whitespace anomaly detection failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Whitespace anomaly flags: {len(flags)}")
        return flags

    def detect_zero_width_characters(self, doc_id: Optional[int] = None) -> List[Dict]:
        """
        Detect zero-width characters used for steganography.

        Zero-width characters are invisible but can encode binary data
        (0 = ZWNJ, 1 = ZWJ pattern commonly used for hidden messages).

        Returns:
            List of red flags for zero-width steganography
        """
        session = self.Session()
        flags = []

        try:
            query = session.query(Chunk)
            if doc_id:
                query = query.filter(Chunk.doc_id == doc_id)

            chunks = query.all()

            for chunk in chunks:
                text = chunk.text
                if not text:
                    continue

                # Count zero-width characters commonly used in steganography
                zwj_count = text.count('\u200D')  # Zero-Width Joiner
                zwnj_count = text.count('\u200C')  # Zero-Width Non-Joiner

                # If both are present in significant amounts, likely steganography
                if zwj_count > 0 and zwnj_count > 0:
                    total = zwj_count + zwnj_count

                    # Try to extract potential binary pattern
                    # Replace ZWJ with 1, ZWNJ with 0
                    binary_pattern = text.replace('\u200D', '1').replace('\u200C', '0')
                    binary_sequences = re.findall(r'[01]{8,}', binary_pattern)

                    severity = "CRITICAL" if total > 50 or binary_sequences else "HIGH"

                    flags.append({
                        "flag_type": "hidden_content",
                        "flag_category": "zero_width_steganography",
                        "severity": severity,
                        "title": "Possible Zero-Width Steganography Detected",
                        "description": f"Found {total} zero-width characters (ZWJ: {zwj_count}, ZWNJ: {zwnj_count}). "
                                     f"The combination of these characters is commonly used to encode hidden "
                                     f"binary messages in plain text. "
                                     f"{f'Detected {len(binary_sequences)} potential binary sequences.' if binary_sequences else ''}",
                        "evidence": {
                            "zwj_count": zwj_count,
                            "zwnj_count": zwnj_count,
                            "total_zero_width": total,
                            "potential_binary_sequences": len(binary_sequences),
                            "sample_pattern": binary_sequences[0][:64] if binary_sequences else None
                        },
                        "confidence": 0.95 if binary_sequences else 0.8,
                        "doc_id": chunk.doc_id,
                        "chunk_id": chunk.id,
                        "entity_id": None,
                        "timeline_event_id": None
                    })

        except Exception as e:
            logger.error(f"Zero-width character detection failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Zero-width steganography flags: {len(flags)}")
        return flags

    def detect_homoglyph_substitution(self, doc_id: Optional[int] = None) -> List[Dict]:
        """
        Detect homoglyph substitution (characters that look identical but are different).

        Examples:
        - Latin 'a' vs Cyrillic 'а' (U+0061 vs U+0430)
        - Latin 'o' vs Greek 'ο' (U+006F vs U+03BF)

        This can be used to hide information or evade text searches.

        Returns:
            List of red flags for homoglyph usage
        """
        session = self.Session()
        flags = []

        try:
            # Common homoglyph pairs (Latin lookalike, actual character)
            homoglyphs = {
                'а': 'a',  # Cyrillic vs Latin
                'е': 'e',
                'о': 'o',
                'р': 'p',
                'с': 'c',
                'х': 'x',
                'у': 'y',
                'А': 'A',
                'В': 'B',
                'Е': 'E',
                'К': 'K',
                'М': 'M',
                'Н': 'H',
                'О': 'O',
                'Р': 'P',
                'С': 'C',
                'Т': 'T',
                'Х': 'X',
                'ο': 'o',  # Greek vs Latin
                'ν': 'v',
                'α': 'a',
            }

            query = session.query(Chunk)
            if doc_id:
                query = query.filter(Chunk.doc_id == doc_id)

            chunks = query.all()

            for chunk in chunks:
                text = chunk.text
                if not text:
                    continue

                found_homoglyphs = {}
                total_count = 0

                for homoglyph, lookalike in homoglyphs.items():
                    count = text.count(homoglyph)
                    if count > 0:
                        char_name = unicodedata.name(homoglyph, "UNKNOWN")
                        found_homoglyphs[f"{homoglyph} ({char_name})"] = count
                        total_count += count

                if total_count >= 3:  # Threshold: 3+ homoglyphs
                    severity = "HIGH" if total_count > 10 else "MEDIUM"

                    flags.append({
                        "flag_type": "hidden_content",
                        "flag_category": "homoglyph_substitution",
                        "severity": severity,
                        "title": "Homoglyph Character Substitution Detected",
                        "description": f"Found {total_count} homoglyph characters (visually identical but different Unicode). "
                                     f"This technique can be used to hide information from text searches or "
                                     f"to create misleading document content. "
                                     f"Types: {', '.join(list(found_homoglyphs.keys())[:3])}",
                        "evidence": {
                            "homoglyphs_found": found_homoglyphs,
                            "total_count": total_count,
                            "chunk_preview": text[:200]
                        },
                        "confidence": 0.85,
                        "doc_id": chunk.doc_id,
                        "chunk_id": chunk.id,
                        "entity_id": None,
                        "timeline_event_id": None
                    })

        except Exception as e:
            logger.error(f"Homoglyph detection failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Homoglyph substitution flags: {len(flags)}")
        return flags

    def detect_hidden_layers(self, doc_id: Optional[int] = None) -> List[Dict]:
        """
        Detect suspicious PDF layer usage or page count discrepancies.

        Checks:
        - Documents with unusually high page counts but low text content
        - Potential hidden text layers (white text on white background)

        Returns:
            List of red flags for hidden layer techniques
        """
        session = self.Session()
        flags = []

        try:
            query = session.query(Document).join(Chunk).filter(
                Document.status == "complete",
                Document.num_pages.isnot(None),
                Document.num_pages > 0
            )

            if doc_id:
                query = query.filter(Document.id == doc_id)

            # Group by document and count chunks
            docs = query.all()

            for doc in docs:
                # Get all chunks for this document
                chunks = session.query(Chunk).filter(Chunk.doc_id == doc.id).all()
                total_text_length = sum(len(chunk.text) for chunk in chunks if chunk.text)

                # Calculate average characters per page
                if doc.num_pages > 0:
                    chars_per_page = total_text_length / doc.num_pages

                    # Flag if very low text density (< 100 chars/page) but many pages
                    if chars_per_page < 100 and doc.num_pages > 5:
                        severity = "MEDIUM" if chars_per_page < 50 else "LOW"

                        flags.append({
                            "flag_type": "hidden_content",
                            "flag_category": "hidden_layers",
                            "severity": severity,
                            "title": "Low Text Density - Possible Hidden Layers",
                            "description": f"Document has {doc.num_pages} pages but only {chars_per_page:.0f} "
                                         f"characters per page on average. This may indicate hidden text layers, "
                                         f"white-on-white text, or non-text content (images/scans).",
                            "evidence": {
                                "num_pages": doc.num_pages,
                                "total_text_length": total_text_length,
                                "chars_per_page": round(chars_per_page, 2),
                                "pdf_producer": doc.pdf_producer,
                                "pdf_creator": doc.pdf_creator
                            },
                            "confidence": 0.6,
                            "doc_id": doc.id,
                            "chunk_id": None,
                            "entity_id": None,
                            "timeline_event_id": None
                        })

                # Check for OCR pages with very low confidence (potential hidden text)
                ocr_pages = session.query(PageOCR).filter(
                    PageOCR.document_id == doc.id,
                    PageOCR.text.isnot(None)
                ).all()

                if ocr_pages:
                    # Count pages with very short text (< 50 chars)
                    low_confidence_pages = [
                        p for p in ocr_pages
                        if p.text and len(p.text.strip()) < 50
                    ]

                    if len(low_confidence_pages) > len(ocr_pages) * 0.3:  # 30%+ low-content pages
                        flags.append({
                            "flag_type": "hidden_content",
                            "flag_category": "ocr_anomalies",
                            "severity": "MEDIUM",
                            "title": "OCR Extraction Anomalies Detected",
                            "description": f"{len(low_confidence_pages)} out of {len(ocr_pages)} pages "
                                         f"have very low text extraction (< 50 chars). This may indicate "
                                         f"hidden text, poor scan quality, or intentional obfuscation.",
                            "evidence": {
                                "total_pages": len(ocr_pages),
                                "low_content_pages": len(low_confidence_pages),
                                "percentage": round(len(low_confidence_pages) / len(ocr_pages) * 100, 1)
                            },
                            "confidence": 0.55,
                            "doc_id": doc.id,
                            "chunk_id": None,
                            "entity_id": None,
                            "timeline_event_id": None
                        })

        except Exception as e:
            logger.error(f"Hidden layer detection failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Hidden layer flags: {len(flags)}")
        return flags


# Singleton instance
_detector_instance = None


def get_hidden_content_detector() -> HiddenContentDetector:
    """Get singleton hidden content detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = HiddenContentDetector()
    return _detector_instance
