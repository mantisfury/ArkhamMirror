"""
Phase 5.4: Content Extraction Utilities

Regex-based extraction for dates, monetary amounts, and quoted text.
These run without LLM and provide baseline extraction in all modes.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


# Date patterns (comprehensive for multiple formats)
DATE_PATTERNS = [
    # Full dates: January 15, 2023 or 15 January 2023
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
    # Short month: Jan 15, 2023
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b",
    # Numeric: 01/15/2023, 2023-01-15, 15.01.2023
    r"\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b",
    r"\b\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}\b",
    # Month Year: January 2023
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
    # Year only in context: "in 2023", "during 2022"
    r"\b(?:in|during|circa|year)\s+\d{4}\b",
]

# Monetary patterns (USD, EUR, GBP, generic amounts)
MONEY_PATTERNS = [
    # USD: $1,234.56 or $1234
    r"\$\s*[\d,]+(?:\.\d{2})?\b",
    # EUR: €1,234.56 or 1,234.56€
    r"€\s*[\d,]+(?:\.\d{2})?\b",
    r"[\d,]+(?:\.\d{2})?\s*€",
    # GBP: £1,234.56
    r"£\s*[\d,]+(?:\.\d{2})?\b",
    # Written amounts: 1.5 million, 500 thousand
    r"\b[\d,]+(?:\.\d+)?\s*(?:million|billion|trillion|thousand|hundred)\b",
    # USD/EUR/GBP written: USD 1,234
    r"\b(?:USD|EUR|GBP|CAD|AUD)\s*[\d,]+(?:\.\d{2})?\b",
]

# Quote patterns
QUOTE_PATTERNS = [
    # Double quotes
    r'"[^"]{10,500}"',
    # Smart quotes
    r'"[^"]{10,500}"',
    # Single quotes for speech
    r"'[^']{10,500}'",
]


def extract_dates(text: str) -> List[Dict[str, Any]]:
    """
    Extract date mentions from text.

    Args:
        text: Input text to scan

    Returns:
        List of dicts with date_text, parsed_date, position
    """
    results = []
    seen_positions = set()

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = match.start()
            # Avoid duplicates at same position
            if start in seen_positions:
                continue
            seen_positions.add(start)

            date_text = match.group().strip()
            parsed_date = None

            try:
                # Attempt to parse the date
                parsed_date = date_parser.parse(date_text, fuzzy=True)
            except (ValueError, OverflowError):
                pass

            results.append(
                {
                    "date_text": date_text,
                    "parsed_date": parsed_date.isoformat() if parsed_date else None,
                    "start_pos": start,
                    "end_pos": match.end(),
                    "context_before": text[max(0, start - 30) : start].strip(),
                    "context_after": text[match.end() : match.end() + 30].strip(),
                }
            )

    return sorted(results, key=lambda x: x["start_pos"])


def extract_money(text: str) -> List[Dict[str, Any]]:
    """
    Extract monetary amounts from text.

    Args:
        text: Input text to scan

    Returns:
        List of dicts with amount_text, normalized_value, currency
    """
    results = []
    seen_positions = set()

    for pattern in MONEY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = match.start()
            if start in seen_positions:
                continue
            seen_positions.add(start)

            amount_text = match.group().strip()
            normalized = _normalize_amount(amount_text)
            currency = _detect_currency(amount_text)

            results.append(
                {
                    "amount_text": amount_text,
                    "normalized_value": normalized,
                    "currency": currency,
                    "start_pos": start,
                    "end_pos": match.end(),
                    "context_before": text[max(0, start - 30) : start].strip(),
                    "context_after": text[match.end() : match.end() + 30].strip(),
                }
            )

    return sorted(results, key=lambda x: x["start_pos"])


def _normalize_amount(text: str) -> Optional[float]:
    """Convert amount text to numeric value."""
    try:
        # Remove currency symbols and whitespace
        cleaned = re.sub(r"[$€£]|\s", "", text)
        # Remove commas
        cleaned = cleaned.replace(",", "")

        # Handle written multipliers
        multipliers = {
            "thousand": 1_000,
            "million": 1_000_000,
            "billion": 1_000_000_000,
            "trillion": 1_000_000_000_000,
        }

        for word, mult in multipliers.items():
            if word in cleaned.lower():
                num = re.search(r"[\d.]+", cleaned)
                if num:
                    return float(num.group()) * mult

        # Direct numeric conversion
        num_match = re.search(r"[\d.]+", cleaned)
        if num_match:
            return float(num_match.group())

        return None
    except (ValueError, AttributeError):
        return None


def _detect_currency(text: str) -> str:
    """Detect currency from amount text."""
    text_upper = text.upper()
    if "$" in text or "USD" in text_upper:
        return "USD"
    elif "€" in text or "EUR" in text_upper:
        return "EUR"
    elif "£" in text or "GBP" in text_upper:
        return "GBP"
    elif "CAD" in text_upper:
        return "CAD"
    elif "AUD" in text_upper:
        return "AUD"
    else:
        return "UNKNOWN"


def extract_quotes(text: str) -> List[Dict[str, Any]]:
    """
    Extract quoted text passages.

    Args:
        text: Input text to scan

    Returns:
        List of dicts with quote_text, speaker (if detected), position
    """
    results = []
    seen_positions = set()

    for pattern in QUOTE_PATTERNS:
        for match in re.finditer(pattern, text):
            start = match.start()
            if start in seen_positions:
                continue
            seen_positions.add(start)

            quote_text = match.group()
            # Remove outer quotes
            inner_text = quote_text[1:-1].strip()

            # Try to detect speaker from context before
            context_before = text[max(0, start - 100) : start]
            speaker = _detect_speaker(context_before)

            results.append(
                {
                    "quote_text": inner_text,
                    "full_match": quote_text,
                    "speaker": speaker,
                    "start_pos": start,
                    "end_pos": match.end(),
                    "context_before": context_before[-50:].strip(),
                }
            )

    return sorted(results, key=lambda x: x["start_pos"])


def _detect_speaker(context: str) -> Optional[str]:
    """Try to detect speaker from context before a quote."""
    # Look for patterns like "John said", "according to Jane"
    patterns = [
        r"([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:said|stated|noted|remarked|added|explained)[\s,]*$",
        r"(?:according to|per)\s+([A-Z][a-z]+ [A-Z][a-z]+)[\s,]*$",
        r"([A-Z][a-z]+)\s+(?:said|stated|noted)[\s,]*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, context)
        if match:
            return match.group(1)

    return None


def detect_language(text: str) -> str:
    """
    Detect the language of text.

    Args:
        text: Input text (at least 50 characters recommended)

    Returns:
        ISO language code (en, es, fr, de, etc.)
    """
    try:
        from langdetect import detect

        return detect(text)
    except Exception:
        # Fallback to English if detection fails
        return "en"


def extract_all(text: str) -> Dict[str, Any]:
    """
    Run all extractions on text.

    Args:
        text: Input text to process

    Returns:
        Dict with dates, money, quotes, and language
    """
    return {
        "dates": extract_dates(text),
        "money": extract_money(text),
        "quotes": extract_quotes(text),
        "language": detect_language(text) if len(text) > 50 else "en",
    }
