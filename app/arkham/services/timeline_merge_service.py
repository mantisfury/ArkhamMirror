"""
Multi-Document Timeline Merging Service

Combined chronological view across documents:
- Merge timelines from multiple sources
- Resolve date conflicts and ambiguities
- Identify corroborating vs. contradicting events
"""

import json
import logging
import re
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    CanonicalEntity,
    Document,
    Chunk,
    EntityMention,
)
from app.arkham.services.llm_service import chat_with_llm, TIMELINE_EVENTS_SCHEMA

load_dotenv()
logger = logging.getLogger(__name__)


class TimelineMergeService:
    """Service for multi-document timeline analysis and merging."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        # Cache: entity_id -> analysis result (0 = corpus-wide)
        self._cache: Dict[int, Dict[str, Any]] = {}

    def extract_temporal_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Extract events with temporal references from the corpus."""
        session = self.Session()
        try:
            # Get chunks that likely contain temporal information
            chunks = (
                session.query(Chunk).order_by(desc(Chunk.id)).limit(limit * 2).all()
            )

            # Find temporal patterns
            date_patterns = [
                r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",  # MM/DD/YYYY
                r"\b\d{4}-\d{2}-\d{2}\b",  # YYYY-MM-DD
                r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
                r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
                r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
            ]

            temporal_chunks = []
            for chunk in chunks:
                for pattern in date_patterns:
                    if re.search(pattern, chunk.text, re.IGNORECASE):
                        doc = session.query(Document).filter_by(id=chunk.doc_id).first()
                        temporal_chunks.append(
                            {
                                "chunk_id": chunk.id,
                                "document_id": chunk.doc_id,
                                "document_name": doc.title if doc else "Unknown",
                                "text": chunk.text[:500],
                            }
                        )
                        break

                if len(temporal_chunks) >= limit:
                    break

            return temporal_chunks

        finally:
            session.close()

    def extract_events_with_llm(
        self, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use LLM to extract structured events from temporal chunks."""
        if not chunks:
            return []

        # Limit to 8 chunks with truncated text for simpler responses
        chunks_text = "\n\n---\n\n".join(
            [f"[{c['document_name']}]: {c['text'][:300]}" for c in chunks[:8]]
        )

        prompt = f"""Extract up to 10 key events with dates from these excerpts.
For each event provide: date, event (brief), source, confidence (High/Medium/Low).

{chunks_text}

Return ONLY valid JSON:
{{"events": [{{"date": "YYYY-MM-DD", "event": "...", "source": "...", "confidence": "..."}}]}}"""

        response = chat_with_llm(
            prompt, max_tokens=1500, json_schema=TIMELINE_EVENTS_SCHEMA
        )

        try:
            # Clean up common LLM JSON issues
            cleaned = response
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                parts = cleaned.split("```")
                if len(parts) > 1:
                    cleaned = parts[1]

            # Find JSON object
            json_start = cleaned.find("{")
            json_end = cleaned.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned[json_start:json_end]

                # Fix common JSON issues
                json_str = re.sub(r",\s*]", "]", json_str)
                json_str = re.sub(r",\s*}", "}", json_str)

                result = json.loads(json_str)
                events = result.get("events", [])
                logger.info(f"Extracted {len(events)} events from LLM")
                return events

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse events JSON: {e}")
            # Fallback: try to extract individual events with regex
            try:
                events = []
                # Match simple event objects
                event_pattern = r'\{[^{}]*?"date"[^{}]*?"event"[^{}]*?\}'
                matches = re.findall(event_pattern, response, re.DOTALL)
                for match in matches[:10]:
                    try:
                        clean_match = re.sub(r",\s*}", "}", match)
                        event = json.loads(clean_match)
                        if "date" in event:
                            events.append(event)
                    except json.JSONDecodeError:
                        continue
                if events:
                    logger.warning(f"Fallback extracted {len(events)} events")
                    return events
            except Exception as fallback_error:
                logger.error(f"Fallback extraction failed: {fallback_error}")

        return []

    def merge_timelines(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge events into a unified timeline, detecting conflicts."""
        if not events:
            return {"timeline": [], "conflicts": [], "gaps": []}

        # Sort events by date
        def parse_date(event):
            date_str = event.get("date", "")
            try:
                if len(date_str) == 10 and "-" in date_str:
                    return datetime.strptime(date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                pass
            return datetime.max

        sorted_events = sorted(events, key=parse_date)

        # Detect conflicts (same date, different descriptions from different sources)
        conflicts = []
        date_groups = {}
        for event in sorted_events:
            date = event.get("date", "unknown")
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(event)

        for date, group in date_groups.items():
            if len(group) > 1:
                sources = set(e.get("source", "") for e in group)
                if len(sources) > 1:
                    conflicts.append(
                        {
                            "date": date,
                            "events": group,
                            "type": "multiple_sources",
                            "description": f"Multiple sources report different events on {date}",
                        }
                    )

        # Detect gaps (large time jumps)
        gaps = []
        for i in range(1, len(sorted_events)):
            prev_date = parse_date(sorted_events[i - 1])
            curr_date = parse_date(sorted_events[i])
            if prev_date != datetime.max and curr_date != datetime.max:
                gap_days = (curr_date - prev_date).days
                if gap_days > 90:  # More than 3 months
                    gaps.append(
                        {
                            "from_date": sorted_events[i - 1].get("date"),
                            "to_date": sorted_events[i].get("date"),
                            "gap_days": gap_days,
                            "description": f"No events found for {gap_days} days",
                        }
                    )

        return {
            "timeline": sorted_events,
            "conflicts": conflicts,
            "gaps": gaps,
            "total_events": len(sorted_events),
            "sources_count": len(set(e.get("source", "") for e in sorted_events)),
        }

    def analyze_timeline(
        self, entity_id: int = None, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Full timeline analysis, optionally focused on an entity."""
        cache_key = entity_id or 0  # 0 = corpus-wide

        # Return cached result if available
        if not force_refresh and cache_key in self._cache:
            logger.info(f"Returning cached timeline for entity_id={cache_key}")
            return self._cache[cache_key]

        session = self.Session()
        try:
            # Get temporal chunks
            if entity_id:
                # Get documents mentioning this entity (chunk_id is often NULL, use doc_id)
                doc_ids = (
                    session.query(EntityMention.doc_id)
                    .filter(EntityMention.canonical_entity_id == entity_id)
                    .distinct()
                    .limit(10)
                    .all()
                )
                doc_ids = [d[0] for d in doc_ids if d[0] is not None]

                # Get chunks from those documents
                chunks = (
                    session.query(Chunk)
                    .filter(Chunk.doc_id.in_(doc_ids))
                    .limit(30)
                    .all()
                )

                entity = session.query(CanonicalEntity).filter_by(id=entity_id).first()
                entity_name = entity.canonical_name if entity else "Unknown"

                # Convert to temporal format
                temporal_chunks = []
                for chunk in chunks:
                    doc = session.query(Document).filter_by(id=chunk.doc_id).first()
                    temporal_chunks.append(
                        {
                            "chunk_id": chunk.id,
                            "document_id": chunk.doc_id,
                            "document_name": doc.title if doc else "Unknown",
                            "text": chunk.text[:500],
                        }
                    )
            else:
                temporal_chunks = self.extract_temporal_events(50)
                entity_name = None

            if not temporal_chunks:
                return {
                    "error": "No temporal events found",
                    "entity_name": entity_name,
                    "timeline": [],
                    "conflicts": [],
                    "gaps": [],
                }

            # Extract events with LLM
            events = self.extract_events_with_llm(temporal_chunks)

            # Merge into unified timeline
            merged = self.merge_timelines(events)
            merged["entity_focus"] = entity_name
            merged["analyzed_at"] = datetime.now().isoformat()

            # Cache the result
            self._cache[cache_key] = merged
            logger.info(f"Cached timeline for entity_id={cache_key}")

            return merged

        finally:
            session.close()

    def clear_cache(self, entity_id: int = None):
        """Clear cached analysis results."""
        if entity_id is not None:
            cache_key = entity_id or 0
            self._cache.pop(cache_key, None)
        else:
            self._cache.clear()
        logger.info(f"Cache cleared for entity_id={entity_id}")

    def generate_timeline_narrative(
        self, timeline_data: Dict[str, Any], entity_name: str = None
    ) -> str:
        """Generate a narrative description of the timeline."""
        events = timeline_data.get("timeline", [])
        conflicts = timeline_data.get("conflicts", [])
        gaps = timeline_data.get("gaps", [])

        if not events:
            return "No events to narrate."

        events_text = "\n".join(
            [
                f"- {e.get('date', 'Unknown')}: {e.get('event', '')} (Source: {e.get('source', 'Unknown')})"
                for e in events[:30]  # Increased context slightly
            ]
        )

        focus_instruction = (
            f" focusing on {entity_name}"
            if entity_name
            else " summarizing the key sequence"
        )

        prompt = f"""Based on this timeline of events, write a coherent narrative summary{focus_instruction}:

EVENTS:
{events_text}

{f"CONFLICTS DETECTED: {len(conflicts)}" if conflicts else ""}
{f"GAPS DETECTED: {len(gaps)}" if gaps else ""}

Write a compelling 2-3 paragraph investigative narrative that:
1. Reconstructs the story chronologically{f", highlighting {entity_name}'s role" if entity_name else ""}
2. Connects isolated events into a larger picture
3. Points out inconsistencies or gaps in intelligence

Style: Professional investigative journalism or intelligence briefing.
"""

        return chat_with_llm(prompt, max_tokens=1000)

    def get_timeline_entities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get entities that appear frequently in temporal contexts."""
        session = self.Session()
        try:
            entities = (
                session.query(CanonicalEntity)
                .filter(CanonicalEntity.total_mentions > 0)
                .order_by(desc(CanonicalEntity.total_mentions))
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": e.id,
                    "name": e.canonical_name,
                    "type": e.label,
                    "mentions": e.total_mentions or 0,
                }
                for e in entities
            ]
        finally:
            session.close()


# Singleton
_service_instance = None


def get_timeline_merge_service() -> TimelineMergeService:
    global _service_instance
    if _service_instance is None:
        _service_instance = TimelineMergeService()
    return _service_instance
