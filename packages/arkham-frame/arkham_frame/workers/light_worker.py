"""
LightWorker - Lightweight text processing for the cpu-light pool.

Handles:
- Text normalization (Unicode, whitespace, encoding)
- Language detection
- Text quality assessment

Fast, efficient tasks suitable for CPU-light processing.
"""

import logging
import re
import unicodedata
from collections import Counter
from typing import Dict, Any, List, Tuple

from .base import BaseWorker

logger = logging.getLogger(__name__)


class LightWorker(BaseWorker):
    """
    Worker for lightweight text processing tasks.

    Supports:
    - normalize: Clean and normalize text
    - detect_language: Identify language
    - quality: Assess text quality
    - process: All-in-one processing (default)
    """

    pool = "cpu-light"
    name = "LightWorker"
    job_timeout = 10.0  # Very fast tasks
    poll_interval = 0.2  # Poll quickly

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._langdetect_available = False

        # Try to import langdetect
        try:
            import langdetect
            self._langdetect_available = True
            logger.info("langdetect available for language detection")
        except ImportError:
            logger.info("langdetect not available, using fallback heuristics")

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a lightweight text task.

        Args:
            job_id: Job identifier
            payload: Job data with 'task' and 'text' fields, OR 'file_path' for ingest jobs

        Returns:
            Result dict based on task type
        """
        task = payload.get("task", "process")
        text = payload.get("text", "")

        # If no text provided but we have a file_path (from ingest), read the file
        if not text and "file_path" in payload:
            file_path = payload["file_path"]
            # Resolve relative path using DATA_SILO_PATH (for Docker/portable deployments)
            import os
            from pathlib import Path
            if not os.path.isabs(file_path):
                data_silo = os.environ.get("DATA_SILO_PATH", ".")
                file_path = str(Path(data_silo) / file_path)
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                logger.info(f"Read {len(text)} chars from {file_path}")
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                return {"error": f"Failed to read file: {e}"}

        if not text:
            return {"error": "No text provided and no file_path specified"}

        if task == "normalize":
            return self._normalize(text)
        elif task == "detect_language":
            return self._detect_language(text)
        elif task == "quality":
            return self._assess_quality(text)
        elif task == "process":
            # All-in-one processing
            normalized = self._normalize(text)
            language = self._detect_language(normalized["text"])
            quality = self._assess_quality(normalized["text"])

            return {
                "text": normalized["text"],  # Include processed text for downstream use
                "normalized_text": normalized["text"],
                "normalization_changes": normalized["changes"],
                "language": language["language"],
                "language_confidence": language["confidence"],
                "quality_score": quality["score"],
                "quality_issues": quality["issues"],
                "word_count": quality["word_count"],
            }
        else:
            return {"error": f"Unknown task: {task}"}

    def _normalize(self, text: str) -> Dict[str, Any]:
        """
        Normalize text: Unicode, encoding, whitespace.

        Args:
            text: Input text

        Returns:
            Dict with 'text' and 'changes' list
        """
        changes = []
        original_len = len(text)

        # Remove control characters (except newline, tab, carriage return)
        cleaned = "".join(
            char for char in text
            if unicodedata.category(char)[0] != "C" or char in "\n\t\r"
        )
        if len(cleaned) != original_len:
            changes.append("removed_control_chars")

        # Normalize Unicode to NFKC (compatibility decomposition + canonical composition)
        # This handles things like full-width characters, ligatures, etc.
        normalized = unicodedata.normalize("NFKC", cleaned)
        if normalized != cleaned:
            changes.append("normalized_unicode")

        # Fix common smart quotes and dashes
        replacements = {
            "\u2018": "'",  # Left single quote
            "\u2019": "'",  # Right single quote
            "\u201c": '"',  # Left double quote
            "\u201d": '"',  # Right double quote
            "\u2013": "-",  # En dash
            "\u2014": "--", # Em dash
            "\u2026": "...", # Ellipsis
        }

        fixed = normalized
        for old, new in replacements.items():
            fixed = fixed.replace(old, new)
        if fixed != normalized:
            changes.append("fixed_smart_punctuation")

        # Normalize whitespace
        # - Replace multiple spaces with single space
        # - Replace multiple newlines with max 2
        # - Strip leading/trailing whitespace from lines
        lines = fixed.split("\n")
        normalized_lines = []
        for line in lines:
            # Collapse multiple spaces
            line = re.sub(r" {2,}", " ", line)
            # Strip leading/trailing whitespace
            line = line.strip()
            normalized_lines.append(line)

        # Collapse multiple blank lines to max 2
        result_lines = []
        blank_count = 0
        for line in normalized_lines:
            if not line:
                blank_count += 1
                if blank_count <= 2:
                    result_lines.append(line)
            else:
                blank_count = 0
                result_lines.append(line)

        final = "\n".join(result_lines).strip()

        if len(final.split()) != len(fixed.split()):
            changes.append("normalized_whitespace")

        if not changes:
            changes.append("no_changes_needed")

        return {
            "text": final,
            "changes": changes,
        }

    def _detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detect text language.

        Args:
            text: Input text

        Returns:
            Dict with 'language' (ISO code) and 'confidence' (0-1)
        """
        if self._langdetect_available:
            return self._detect_language_with_langdetect(text)
        else:
            return self._detect_language_fallback(text)

    def _detect_language_with_langdetect(self, text: str) -> Dict[str, Any]:
        """Detect language using langdetect library."""
        try:
            from langdetect import detect_langs

            # Get all detected languages with probabilities
            langs = detect_langs(text)

            if langs:
                # Return highest probability
                top = langs[0]
                return {
                    "language": top.lang,
                    "confidence": round(top.prob, 2),
                }
            else:
                return {
                    "language": "unknown",
                    "confidence": 0.0,
                }
        except Exception as e:
            logger.warning(f"langdetect failed: {e}, using fallback")
            return self._detect_language_fallback(text)

    def _detect_language_fallback(self, text: str) -> Dict[str, Any]:
        """
        Simple heuristic-based language detection.

        Checks for common character ranges:
        - Latin/English
        - Cyrillic
        - Arabic
        - CJK (Chinese/Japanese/Korean)
        """
        # Count characters in different scripts
        latin = 0
        cyrillic = 0
        arabic = 0
        cjk = 0
        total = 0

        for char in text:
            if char.isalpha():
                total += 1
                code = ord(char)

                # Latin (including extensions)
                if (code >= 0x0041 and code <= 0x007A) or \
                   (code >= 0x00C0 and code <= 0x024F):
                    latin += 1
                # Cyrillic
                elif code >= 0x0400 and code <= 0x04FF:
                    cyrillic += 1
                # Arabic
                elif code >= 0x0600 and code <= 0x06FF:
                    arabic += 1
                # CJK
                elif (code >= 0x4E00 and code <= 0x9FFF) or \
                     (code >= 0x3040 and code <= 0x30FF):
                    cjk += 1

        if total == 0:
            return {
                "language": "unknown",
                "confidence": 0.0,
            }

        # Calculate percentages
        scripts = [
            ("en", latin / total),      # English/Latin
            ("ru", cyrillic / total),   # Russian/Cyrillic
            ("ar", arabic / total),     # Arabic
            ("zh", cjk / total),        # Chinese/CJK
        ]

        # Get dominant script
        scripts.sort(key=lambda x: x[1], reverse=True)
        lang, score = scripts[0]

        # If no clear winner, mark as unknown
        if score < 0.3:
            return {
                "language": "unknown",
                "confidence": round(score, 2),
            }

        return {
            "language": lang,
            "confidence": round(score, 2),
        }

    def _assess_quality(self, text: str) -> Dict[str, Any]:
        """
        Assess text quality.

        Checks:
        - Entropy (repetitiveness)
        - Character distribution
        - Word/sentence structure

        Args:
            text: Input text

        Returns:
            Dict with 'score' (0-1), 'issues' list, and stats
        """
        issues = []
        score = 1.0

        # Basic stats
        char_count = len(text)
        words = text.split()
        word_count = len(words)

        if char_count == 0:
            return {
                "score": 0.0,
                "issues": ["empty_text"],
                "word_count": 0,
                "char_count": 0,
            }

        # Check word count
        if word_count < 3:
            issues.append("very_short")
            score -= 0.3

        # Calculate character entropy
        entropy = self._calculate_entropy(text)

        # Low entropy = repetitive/garbage
        if entropy < 2.0:
            issues.append("very_low_entropy")
            score -= 0.4
        elif entropy < 3.0:
            issues.append("low_entropy")
            score -= 0.2

        # Check character distribution
        letters = sum(1 for c in text if c.isalpha())
        digits = sum(1 for c in text if c.isdigit())
        spaces = sum(1 for c in text if c.isspace())
        punctuation = sum(1 for c in text if not c.isalnum() and not c.isspace())

        # Ratio checks
        if char_count > 0:
            letter_ratio = letters / char_count
            digit_ratio = digits / char_count

            # Mostly numbers
            if digit_ratio > 0.5:
                issues.append("mostly_numbers")
                score -= 0.2

            # Very few letters
            if letter_ratio < 0.3:
                issues.append("low_letter_ratio")
                score -= 0.2

            # Check for reasonable word length
            if word_count > 0:
                avg_word_len = letters / word_count
                if avg_word_len < 2:
                    issues.append("very_short_words")
                    score -= 0.2
                elif avg_word_len > 20:
                    issues.append("very_long_words")
                    score -= 0.1

        # Check for repetitive words
        if word_count > 0:
            word_freq = Counter(words)
            most_common = word_freq.most_common(1)[0]
            if most_common[1] / word_count > 0.3:
                issues.append("repetitive_words")
                score -= 0.2

        # Ensure score stays in [0, 1]
        score = max(0.0, min(1.0, score))

        if not issues:
            issues.append("good_quality")

        return {
            "score": round(score, 2),
            "issues": issues,
            "word_count": word_count,
            "char_count": char_count,
            "entropy": round(entropy, 2),
            "letter_ratio": round(letters / char_count if char_count > 0 else 0, 2),
        }

    def _calculate_entropy(self, text: str) -> float:
        """
        Calculate Shannon entropy of text.

        Higher entropy = more random/diverse
        Lower entropy = more repetitive/predictable

        Args:
            text: Input text

        Returns:
            Entropy value (typically 0-8 for text)
        """
        if not text:
            return 0.0

        # Count character frequencies
        char_counts = Counter(text)
        total = len(text)

        # Calculate Shannon entropy
        import math
        entropy = 0.0
        for count in char_counts.values():
            prob = count / total
            entropy -= prob * math.log2(prob)

        return entropy
