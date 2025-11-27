"""
Sensitive Data Pattern Detection for ArkhamMirror.

Detects common sensitive patterns in text:
- Social Security Numbers (SSN)
- Credit Card Numbers
- Email Addresses
- Phone Numbers
- IP Addresses
- API Keys
- IBANs (International Bank Account Numbers)
- Bitcoin Addresses
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class PatternMatch:
    """Represents a detected pattern match."""
    pattern_type: str
    match_text: str
    start_pos: int
    end_pos: int
    confidence: float
    context_before: str
    context_after: str


class PatternDetector:
    """Detects sensitive data patterns using pre-compiled regex."""

    def __init__(self):
        """Initialize with pre-compiled regex patterns for performance."""
        self.patterns = {
            # Social Security Numbers (US)
            "ssn": {
                "regex": re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
                "validator": self._validate_ssn,
                "description": "Social Security Number (US)"
            },

            # Credit Cards (Major brands)
            "credit_card": {
                "regex": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
                "validator": self._validate_credit_card,
                "description": "Credit Card Number"
            },

            # Email Addresses
            "email": {
                "regex": re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'),
                "validator": None,  # Basic regex is sufficient
                "description": "Email Address"
            },

            # Phone Numbers (US/International)
            "phone": {
                "regex": re.compile(r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
                "validator": None,
                "description": "Phone Number"
            },

            # IP Addresses (IPv4)
            "ip_address": {
                "regex": re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
                "validator": None,
                "description": "IP Address (IPv4)"
            },

            # API Keys (Generic patterns)
            "api_key_generic": {
                "regex": re.compile(r'\b[A-Za-z0-9_-]{32,}\b'),
                "validator": self._validate_api_key,
                "description": "Potential API Key (32+ chars)"
            },

            # AWS Access Keys
            "aws_access_key": {
                "regex": re.compile(r'\b(AKIA[0-9A-Z]{16})\b'),
                "validator": None,
                "description": "AWS Access Key"
            },

            # GitHub Personal Access Token
            "github_token": {
                "regex": re.compile(r'\bghp_[A-Za-z0-9_]{36,}\b'),
                "validator": None,
                "description": "GitHub Personal Access Token"
            },

            # IBAN (International Bank Account Number)
            "iban": {
                "regex": re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b'),
                "validator": self._validate_iban,
                "description": "IBAN (Bank Account Number)"
            },

            # Bitcoin Addresses
            "bitcoin": {
                "regex": re.compile(r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b'),
                "validator": None,
                "description": "Bitcoin Address"
            },

            # Passport Numbers (Generic - various formats)
            "passport": {
                "regex": re.compile(r'\b[A-Z]{1,2}\d{6,9}\b'),
                "validator": None,
                "description": "Potential Passport Number"
            },

            # Driver's License (US - simplified)
            "drivers_license": {
                "regex": re.compile(r'\b[A-Z]\d{7,8}\b'),
                "validator": None,
                "description": "Potential Driver's License"
            }
        }

    def detect_patterns(self, text: str, pattern_types: Optional[List[str]] = None,
                       context_chars: int = 30) -> List[PatternMatch]:
        """
        Detect sensitive patterns in text.

        Args:
            text: Text to search for patterns
            pattern_types: List of pattern types to search for (None = all)
            context_chars: Number of characters before/after to include in context

        Returns:
            List of PatternMatch objects
        """
        if pattern_types is None:
            pattern_types = list(self.patterns.keys())

        matches = []

        for pattern_type in pattern_types:
            if pattern_type not in self.patterns:
                continue

            pattern_config = self.patterns[pattern_type]
            regex = pattern_config["regex"]
            validator = pattern_config["validator"]

            for match in regex.finditer(text):
                match_text = match.group()
                start_pos = match.start()
                end_pos = match.end()

                # Apply validator if present
                confidence = 1.0
                if validator:
                    is_valid, conf = validator(match_text)
                    if not is_valid:
                        continue  # Skip invalid matches
                    confidence = conf

                # Extract context
                context_before = text[max(0, start_pos - context_chars):start_pos].strip()
                context_after = text[end_pos:min(len(text), end_pos + context_chars)].strip()

                matches.append(PatternMatch(
                    pattern_type=pattern_type,
                    match_text=match_text,
                    start_pos=start_pos,
                    end_pos=end_pos,
                    confidence=confidence,
                    context_before=context_before,
                    context_after=context_after
                ))

        return matches

    def _validate_ssn(self, ssn: str) -> tuple:
        """
        Validate SSN using basic rules.

        Returns: (is_valid, confidence)
        """
        # Remove separators
        digits = re.sub(r'[-\s]', '', ssn)

        if len(digits) != 9:
            return False, 0.0

        # Invalid SSN patterns
        area = digits[:3]
        group = digits[3:5]
        serial = digits[5:]

        # Area cannot be 000, 666, or 900-999
        if area == "000" or area == "666" or int(area) >= 900:
            return False, 0.0

        # Group and serial cannot be 0000
        if group == "00" or serial == "0000":
            return False, 0.0

        return True, 0.9  # High confidence if passes validation

    def _validate_credit_card(self, card_num: str) -> tuple:
        """
        Validate credit card using Luhn algorithm.

        Returns: (is_valid, confidence)
        """
        # Remove separators
        digits = re.sub(r'[-\s]', '', card_num)

        if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
            return False, 0.0

        # Luhn algorithm
        total = 0
        reverse_digits = digits[::-1]

        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n

        if total % 10 == 0:
            return True, 0.95  # Very high confidence
        else:
            return False, 0.0

    def _validate_api_key(self, key: str) -> tuple:
        """
        Heuristic validation for API keys.

        Returns: (is_valid, confidence)
        """
        # Must be 32+ characters with good entropy
        if len(key) < 32:
            return False, 0.0

        # Check for reasonable character diversity
        unique_chars = len(set(key))
        entropy_ratio = unique_chars / len(key)

        # Low entropy suggests not a real key
        if entropy_ratio < 0.3:
            return False, 0.0

        # Check for patterns that suggest it's not a key
        if key.isdigit() or key.isalpha():
            return False, 0.0

        # Medium confidence for generic API key patterns
        return True, 0.6

    def _validate_iban(self, iban: str) -> tuple:
        """
        Validate IBAN using basic structure check.

        Returns: (is_valid, confidence)
        """
        # Remove spaces
        iban = iban.replace(" ", "")

        # Must start with 2 letters, 2 digits
        if len(iban) < 15 or len(iban) > 34:
            return False, 0.0

        if not iban[:2].isalpha() or not iban[2:4].isdigit():
            return False, 0.0

        # Check digit validation (simplified)
        # Full IBAN validation requires mod-97 check, which is complex
        # We'll accept structurally valid IBANs with medium confidence
        return True, 0.7

    def get_pattern_descriptions(self) -> Dict[str, str]:
        """Return dictionary of pattern types and their descriptions."""
        return {ptype: config["description"]
                for ptype, config in self.patterns.items()}

    def search_by_pattern(self, text: str, pattern_type: str,
                         context_chars: int = 30) -> List[PatternMatch]:
        """
        Search for a specific pattern type only.

        Convenience method for single-pattern searches.
        """
        return self.detect_patterns(text, pattern_types=[pattern_type],
                                   context_chars=context_chars)


# Singleton instance for performance
_detector = None

def get_detector() -> PatternDetector:
    """Get or create singleton PatternDetector instance."""
    global _detector
    if _detector is None:
        _detector = PatternDetector()
    return _detector


def detect_sensitive_data(text: str, pattern_types: Optional[List[str]] = None) -> List[PatternMatch]:
    """
    Convenience function to detect sensitive data patterns.

    Args:
        text: Text to search
        pattern_types: Optional list of pattern types to search for

    Returns:
        List of PatternMatch objects
    """
    detector = get_detector()
    return detector.detect_patterns(text, pattern_types=pattern_types)
