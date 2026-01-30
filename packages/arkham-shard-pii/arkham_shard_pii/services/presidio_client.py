"""
Presidio Analyzer HTTP client.

Calls a running Presidio Analyzer service (e.g. Docker). Used when configured;
otherwise the shard uses the fallback detector.
"""

import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class PresidioClient:
    """Client for Microsoft Presidio Analyzer HTTP API."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def health(self) -> bool:
        """Return True if Presidio service is reachable."""
        try:
            r = self._session.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except requests.RequestException as e:
            logger.debug("Presidio health check failed: %s", e)
            return False

    def analyze(
        self,
        text: str,
        language: str = "en",
        score_threshold: float = 0.3,
        entities: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze text for PII. Returns list of entities: [{entity_type, start, end, score}, ...].
        """
        if not text or not text.strip():
            return []

        payload: Dict[str, Any] = {
            "text": text,
            "language": language,
            "score_threshold": score_threshold,
        }
        if entities:
            payload["entities"] = entities

        try:
            r = self._session.post(
                f"{self.base_url}/analyze",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            if r.status_code != 200:
                logger.warning("Presidio analyze returned %s: %s", r.status_code, r.text[:200])
                return []

            data = r.json()
            # Presidio returns list of {entity_type, start, end, score}
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return []
        except requests.RequestException as e:
            logger.warning("Presidio analyze failed: %s", e)
            return []

    def supported_entities(self, language: str = "en") -> List[str]:
        """Return list of supported entity types (if endpoint exists)."""
        try:
            r = self._session.get(
                f"{self.base_url}/supportedentities",
                params={"language": language},
                timeout=5,
            )
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        return [
            "PERSON",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "CREDIT_CARD",
            "US_SSN",
            "US_DRIVER_LICENSE",
            "US_PASSPORT",
            "IBAN_CODE",
            "IP_ADDRESS",
            "DATE_TIME",
            "LOCATION",
            "ORGANIZATION",
            "URL",
            "AGE",
            "TITLE",
            "NRP",  # Nationalities, religious or political groups
            "MEDICAL_LICENSE",
            "US_BANK_NUMBER",
            "US_ITIN",
            "CRYPTO"
        ]
