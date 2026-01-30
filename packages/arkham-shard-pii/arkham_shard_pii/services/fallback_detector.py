"""
Robust regex/heuristic PII detector (fallback when Presidio unavailable).

Uses pre-compiled patterns with optional validators (SSN rules, Luhn for credit
cards, API-key entropy, IBAN structure, international phone). Output shape matches
Presidio-normalized result so ingest and document_metadata stay consistent.

Pattern set inspired by Exhibit Core pattern_detector; extended and aligned
with our entity type naming.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Map internal pattern keys to output entity types (Presidio-aligned)
PATTERN_TYPE_TO_ENTITY: Dict[str, str] = {
    "ssn": "US_SSN",
    "credit_card": "CREDIT_CARD",
    "email": "EMAIL_ADDRESS",
    "phone_us": "PHONE_NUMBER",
    "phone_ua": "PHONE_NUMBER",
    "phone_intl": "PHONE_NUMBER",
    "ip_address": "IP_ADDRESS",
    "api_key_generic": "API_KEY",
    "aws_access_key": "AWS_ACCESS_KEY",
    "github_token": "GITHUB_TOKEN",
    "iban": "IBAN",
    "bitcoin": "BITCOIN_ADDRESS",
    "passport": "PASSPORT_NUMBER",
    "drivers_license": "DRIVERS_LICENSE",
}

class PatternDetector:
    """
    Detects sensitive data patterns using pre-compiled regex and optional
    validators. Produces entities with type, value, start, end, score.
    """

    def __init__(self) -> None:
        self._patterns: Dict[str, Dict[str, Any]] = {}
        self._build_patterns()

    def _build_patterns(self) -> None:
        """Initialize pre-compiled regex and validators."""
        self._patterns = {
            "ssn": {
                "regex": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
                "validator": self._validate_ssn,
            },
            "credit_card": {
                "regex": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
                "validator": self._validate_credit_card,
            },
            "email": {
                "regex": re.compile(
                    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
                ),
                "validator": None,
            },
            "phone_us": {
                "regex": re.compile(
                    r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
                ),
                "validator": None,
            },
            "phone_ua": {
                "regex": re.compile(
                    r"\+380\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b"
                ),
                "validator": self._validate_ukrainian_phone,
            },
            "phone_intl": {
                "regex": re.compile(
                    r"\+\d{1,4}[\s.-]?\d{1,5}[\s.-]?\d{1,5}[\s.-]?\d{1,9}\b"
                ),
                "validator": self._validate_international_phone,
            },
            "ip_address": {
                "regex": re.compile(
                    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
                    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
                ),
                "validator": None,
            },
            "api_key_generic": {
                "regex": re.compile(r"\b[A-Za-z0-9_-]{32,}\b"),
                "validator": self._validate_api_key,
            },
            "aws_access_key": {
                "regex": re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
                "validator": None,
            },
            "github_token": {
                "regex": re.compile(r"\bghp_[A-Za-z0-9_]{36,}\b"),
                "validator": None,
            },
            "iban": {
                "regex": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b"),
                "validator": self._validate_iban,
            },
            "bitcoin": {
                "regex": re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b"),
                "validator": None,
            },
            "passport": {
                "regex": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
                "validator": None,
            },
            "drivers_license": {
                "regex": re.compile(r"\b[A-Z]\d{7,8}\b"),
                "validator": None,
            },
        }

    def _validate_ssn(self, ssn: str) -> Tuple[bool, float]:
        """SSN: reject invalid area/group/serial. Returns (is_valid, confidence)."""
        digits = re.sub(r"[-\s]", "", ssn)
        if len(digits) != 9:
            return False, 0.0
        area, group, serial = digits[:3], digits[3:5], digits[5:]
        if area == "000" or area == "666" or int(area) >= 900:
            return False, 0.0
        if group == "00" or serial == "0000":
            return False, 0.0
        return True, 0.9

    def _validate_credit_card(self, card_num: str) -> Tuple[bool, float]:
        """Luhn check. Returns (is_valid, confidence)."""
        digits = re.sub(r"[-\s]", "", card_num)
        if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
            return False, 0.0
        total = 0
        for i, digit in enumerate(reversed(digits)):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return (total % 10 == 0), 0.95

    def _validate_api_key(self, key: str) -> Tuple[bool, float]:
        """Heuristic: length, entropy, not all digits/alpha. Returns (is_valid, confidence)."""
        if len(key) < 32:
            return False, 0.0
        unique_chars = len(set(key))
        if unique_chars / len(key) < 0.3:
            return False, 0.0
        if key.isdigit() or key.isalpha():
            return False, 0.0
        return True, 0.6

    def _validate_iban(self, iban: str) -> Tuple[bool, float]:
        """Basic IBAN structure. Returns (is_valid, confidence)."""
        iban = iban.replace(" ", "")
        if len(iban) < 15 or len(iban) > 34:
            return False, 0.0
        if not iban[:2].isalpha() or not iban[2:4].isdigit():
            return False, 0.0
        return True, 0.7

    def _validate_ukrainian_phone(self, phone: str) -> Tuple[bool, float]:
        """Ukrainian +380 format. Returns (is_valid, confidence)."""
        digits = re.sub(r"[\s.-]", "", phone)
        if not digits.startswith("+380") or len(digits) != 13:
            return False, 0.0
        mobile_prefixes = {
            "39", "50", "63", "66", "67", "68", "73",
            "91", "92", "93", "94", "95", "96", "97", "98", "99",
        }
        prefix = digits[4:6]
        return True, 0.95 if prefix in mobile_prefixes else 0.7

    def _validate_international_phone(self, phone: str) -> Tuple[bool, float]:
        """Basic international format. Returns (is_valid, confidence)."""
        digits = re.sub(r"[\s.-]", "", phone)
        if not digits.startswith("+"):
            return False, 0.0
        digit_count = len(digits) - 1
        if digit_count < 7 or digit_count > 15:
            return False, 0.0
        return True, 0.6

    def detect(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect sensitive patterns in text. Returns list of entities with
        type, value, start, end, score.
        """
        if not text or len(text) > 100_000:
            return []

        entities: List[Dict[str, Any]] = []
        seen_spans: set = set()

        for pattern_key, config in self._patterns.items():
            regex = config["regex"]
            validator: Optional[Callable[[str], Tuple[bool, float]]] = config.get(
                "validator"
            )
            entity_type = PATTERN_TYPE_TO_ENTITY.get(pattern_key, pattern_key.upper())

            for match in regex.finditer(text):
                start, end = match.start(), match.end()
                if (start, end) in seen_spans:
                    continue
                match_text = match.group()

                confidence = 0.8
                if validator:
                    is_valid, conf = validator(match_text)
                    if not is_valid:
                        continue
                    confidence = conf

                seen_spans.add((start, end))
                value = match_text[:97] + "..." if len(match_text) > 100 else match_text
                entities.append({
                    "type": entity_type,
                    "value": value,
                    "start": start,
                    "end": end,
                    "score": confidence,
                })

        return entities


def _collect_strings(obj: Any) -> List[str]:
    """Recursively collect all string values from dict/list."""
    out: List[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_collect_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_collect_strings(v))
    return out


_detector: Optional[PatternDetector] = None


def _get_detector() -> PatternDetector:
    global _detector
    if _detector is None:
        _detector = PatternDetector()
    return _detector


def detect_in_text(text: str) -> List[Dict[str, Any]]:
    """
    Run pattern-based PII detection on a single string. Returns list of entities
    with type, value, start, end, score.
    """
    return _get_detector().detect(text)


def detect_in_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run PII detection over all string values in metadata. Returns result dict
    compatible with document_metadata: pii_detected, pii_types, pii_entities, pii_count.
    """
    all_entities: List[Dict[str, Any]] = []
    types_seen: set = set()
    max_entities = 200

    def walk(obj: Any, key_path: str = "") -> None:
        if isinstance(obj, str) and obj.strip():
            for e in detect_in_text(obj):
                e["source_field"] = key_path or None
                if len(all_entities) < max_entities:
                    all_entities.append(e)
                types_seen.add(e.get("type", ""))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                path = f"{key_path}.{k}" if key_path else k
                walk(v, path)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                path = f"{key_path}[{i}]" if key_path else f"[{i}]"
                walk(v, path)

    walk(metadata)

    return {
        "pii_detected": len(all_entities) > 0,
        "pii_types": sorted(types_seen),
        "pii_entities": all_entities,
        "pii_count": len(all_entities),
    }


class FallbackPiiDetector:
    """Wrapper for fallback detection (API parity with Presidio path)."""

    def __init__(self) -> None:
        self._detector = PatternDetector()

    def analyze_text(self, text: str) -> Dict[str, Any]:
        logger.debug("fallback analyze_text: text len=%s", len(text) if text else 0)
        entities = self._detector.detect(text)
        types_seen = {e.get("type") for e in entities if e.get("type")}
        result = {
            "pii_detected": len(entities) > 0,
            "pii_types": sorted(types_seen),
            "pii_entities": entities,
            "pii_count": len(entities),
        }
        logger.debug("fallback analyze_text: pii_count=%s", len(entities))
        return result

    def analyze_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        num_keys = len(metadata) if metadata else 0
        logger.debug("fallback analyze_metadata: metadata keys=%s", num_keys)
        result = detect_in_metadata(metadata)
        logger.debug("fallback analyze_metadata: pii_count=%s", result.get("pii_count", 0))
        return result
