"""
PII Shard - Single source for PII discovery and analysis.

When Presidio Analyzer is configured and reachable, uses it; otherwise uses
an improved regex/heuristic fallback. Ingest and other shards call this shard
for new data, or read PII results from document_metadata for existing documents.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from arkham_frame import ArkhamShard

from .models import PiiEntity
from .services import FallbackPiiDetector, PresidioClient

logger = logging.getLogger(__name__)


def _normalize_presidio_entities(
    raw: List[Dict[str, Any]], text: str
) -> List[Dict[str, Any]]:
    """Convert Presidio API result to our entity shape (type, value, start, end, score)."""
    out = []
    for r in raw:
        start = r.get("start", 0)
        end = r.get("end", 0)
        entity_type = r.get("entity_type") or r.get("type") or "PII"
        score = r.get("score", 0.5)
        value = text[start:end] if 0 <= start < end <= len(text) else ""
        if len(value) > 100:
            value = value[:97] + "..."
        out.append({
            "type": entity_type,
            "value": value,
            "start": start,
            "end": end,
            "score": score,
        })
    return out


class PiiShard(ArkhamShard):
    """
    PII Shard - Detect and analyze PII in text and metadata.

    - Prefer Microsoft Presidio Analyzer when configured (env PII_PRESIDIO_URL or config).
    - Fallback to improved regex/heuristic detector when Presidio is unavailable.
    - Ingest calls analyze_metadata() during document registration; results are stored
      in document_metadata (pii_detected, pii_types, pii_entities, pii_count).
    - Other services should read PII from document metadata when available,
      or call this shard for new analysis.
    """

    name = "pii"
    version = "0.1.0"
    description = "PII detection and analysis (Presidio preferred, regex fallback)"

    def __init__(self):
        super().__init__()
        self._frame = None
        self._presidio: Optional[PresidioClient] = None
        self._fallback = FallbackPiiDetector()
        self._presidio_available = False

    async def initialize(self, frame) -> None:
        """Initialize shard and Presidio client if configured."""
        self._frame = frame
        base_url = os.environ.get("PII_PRESIDIO_URL") or ""
        if not base_url and hasattr(frame, "config") and frame.config:
            base_url = (frame.config.get("pii") or {}).get("presidio_url") or ""
        if base_url:
            self._presidio = PresidioClient(base_url.strip(), timeout=30)
            self._presidio_available = self._presidio.health()
            if self._presidio_available:
                logger.info("PII shard: Presidio Analyzer available at %s", base_url)
            else:
                logger.warning(
                    "PII shard: Presidio URL configured (%s) but not reachable; using fallback",
                    base_url,
                )
        else:
            logger.info("PII shard: No Presidio URL configured; using fallback only")
        logger.debug("PII shard initialized: presidio_available=%s, fallback detector ready", self._presidio_available)

    def get_routes(self):
        """Return FastAPI router."""
        from .api import router
        return router

    def is_presidio_available(self) -> bool:
        """Return True if Presidio Analyzer is configured and healthy."""
        if not self._presidio:
            return False
        self._presidio_available = self._presidio.health()
        return self._presidio_available

    def analyze_text(
        self,
        text: str,
        language: str = "en",
        score_threshold: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Analyze text for PII. Prefer Presidio; fallback to regex.
        Returns dict: pii_detected, pii_types, pii_entities, pii_count, backend.
        """
        if not text or not text.strip():
            logger.debug("analyze_text: empty text, skipping")
            return {
                "pii_detected": False,
                "pii_types": [],
                "pii_entities": [],
                "pii_count": 0,
                "backend": "fallback",
            }

        text_len = len(text)
        logger.debug("analyze_text: text len=%s, language=%s", text_len, language)
        if self._presidio and self._presidio.health():
            raw = self._presidio.analyze(
                text, language=language, score_threshold=score_threshold
            )
            entities = _normalize_presidio_entities(raw, text)
            types_seen = {e.get("type") for e in entities if e.get("type")}
            pii_count = len(entities)
            logger.info(
                "analyze_text: presidio backend, pii_detected=%s, pii_count=%s",
                pii_count > 0,
                pii_count,
            )
            return {
                "pii_detected": pii_count > 0,
                "pii_types": sorted(types_seen),
                "pii_entities": entities,
                "pii_count": pii_count,
                "backend": "presidio",
            }

        out = self._fallback.analyze_text(text)
        out["backend"] = "fallback"
        logger.info(
            "analyze_text: fallback backend, pii_detected=%s, pii_count=%s",
            out.get("pii_detected", False),
            out.get("pii_count", 0),
        )
        return out

    def analyze_metadata(
        self, metadata: Dict[str, Any], language: str = "en"
    ) -> Dict[str, Any]:
        """
        Analyze all string values in metadata for PII. Used by ingest during
        document registration. Prefer Presidio per string; fallback to regex.
        language: ISO code (e.g. from detected_language) to guide Presidio.
        Returns dict: pii_detected, pii_types, pii_entities, pii_count, backend.
        """
        strings: List[tuple] = []  # (value, key_path)

        def collect(obj: Any, path: str = "") -> None:
            if isinstance(obj, str) and obj.strip():
                strings.append((obj, path))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    collect(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    collect(v, f"{path}[{i}]" if path else f"[{i}]")

        collect(metadata)
        num_strings = len(strings)
        logger.debug("analyze_metadata: collected %s string values from metadata", num_strings)

        all_entities: List[Dict[str, Any]] = []
        types_seen: set = set()
        max_entities = 200

        if self._presidio and self._presidio.health():
            for value, key_path in strings:
                if len(value) > 100_000:
                    continue
                raw = self._presidio.analyze(value, language=language, score_threshold=0.3)
                entities = _normalize_presidio_entities(raw, value)
                for e in entities:
                    e["source_field"] = key_path or None
                    if len(all_entities) < max_entities:
                        all_entities.append(e)
                    types_seen.add(e.get("type", ""))
            pii_count = len(all_entities)
            logger.info(
                "analyze_metadata: presidio backend, pii_detected=%s, pii_count=%s",
                pii_count > 0,
                pii_count,
            )
            return {
                "pii_detected": pii_count > 0,
                "pii_types": sorted(types_seen),
                "pii_entities": all_entities,
                "pii_count": pii_count,
                "backend": "presidio",
            }

        result = self._fallback.analyze_metadata(metadata)
        result["backend"] = "fallback"
        logger.info(
            "analyze_metadata: fallback backend, pii_detected=%s, pii_count=%s",
            result.get("pii_detected", False),
            result.get("pii_count", 0),
        )
        return result

    async def analyze_metadata_async(
        self, metadata: Dict[str, Any], language: str = "en"
    ) -> Dict[str, Any]:
        """Async wrapper for analyze_metadata (for ingest calling from async context)."""
        logger.debug("analyze_metadata_async: language=%s", language)
        return self.analyze_metadata(metadata, language=language)
