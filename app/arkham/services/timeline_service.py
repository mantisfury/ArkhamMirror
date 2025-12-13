"""
Timeline extraction service for ArkhamMirror.

Provides functions to extract temporal information from text:
- Date parsing (explicit dates like "March 15, 2023")
- Event extraction (LLM-based extraction of events with dates)
- Timeline analysis and gap detection
- Retrieval of events from database
"""

# Add project root to path for central config
from pathlib import Path
import sys
import logging

logger = logging.getLogger(__name__)

project_root = Path(__file__).resolve()
while project_root.name != "ArkhamMirror" and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import re
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dateutil import parser as date_parser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .llm_service import chat_with_llm, LLM_EVENTS_ARRAY_SCHEMA
from .db.models import Document, TimelineEvent

# Database setup
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_timeline_events(
    project_id: Optional[int] = None, limit: int = 1000
) -> List[Dict]:
    """
    Retrieve timeline events from the database.

    Args:
        project_id: Optional project ID to filter by (0 or None means all projects)
        limit: Max events to return

    Returns:
        List of event dictionaries
    """
    with Session() as session:
        query = session.query(TimelineEvent).filter(
            TimelineEvent.event_date.isnot(None)
        )

        # Filter by project if specified (0 means "All Projects")
        # Also include unassigned documents (project_id=None) to show legacy data
        if project_id and project_id > 0:
            from sqlalchemy import or_

            query = query.join(Document, TimelineEvent.doc_id == Document.id).filter(
                or_(
                    Document.project_id == project_id,
                    Document.project_id.is_(None),  # Include unassigned documents
                )
            )

        events = query.order_by(TimelineEvent.event_date).limit(limit).all()

        return [
            {
                "id": e.id,
                "date": e.event_date.strftime("%Y-%m-%d"),
                "description": e.description,
                "type": e.event_type,
                "confidence": e.confidence,
                "doc_id": e.doc_id,
            }
            for e in events
        ]


def extract_date_mentions(text: str, context_chars: int = 50) -> List[Dict]:
    """
    Extract all date mentions from text using regex patterns.

    Handles multiple formats:
    - Full dates: "March 15, 2023", "15-03-2023", "2023-03-15"
    - Month/Year: "March 2023", "03/2023"
    - Year only: "2023"
    - Relative dates: "last Tuesday", "two weeks ago"

    Args:
        text: Input text to search for dates
        context_chars: Number of characters before/after to capture for context

    Returns:
        List of dicts with keys: date_text, parsed_date, date_type, context_before, context_after
    """
    mentions = []

    # Pattern 1: Full dates with month names (March 15, 2023 | 15 March 2023)
    pattern1 = r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
    pattern2 = r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b"

    # Pattern 3: Numeric dates (03/15/2023, 15-03-2023, 2023-03-15)
    pattern3 = r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
    pattern4 = r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"

    # Pattern 5: Month and year (March 2023, 03/2023)
    pattern5 = (
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b"
    )
    pattern6 = r"\b\d{1,2}[-/]\d{4}\b"

    # Pattern 7: Year only (1990-2099)
    pattern7 = r"\b(19\d{2}|20\d{2})\b"

    # Pattern 8: Relative dates
    pattern8 = r"\b(today|yesterday|tomorrow|last\s+\w+|next\s+\w+|\d+\s+(?:days?|weeks?|months?|years?)\s+ago)\b"

    all_patterns = [
        (pattern1, "explicit"),
        (pattern2, "explicit"),
        (pattern3, "explicit"),
        (pattern4, "explicit"),
        (pattern5, "explicit"),
        (pattern6, "explicit"),
        (pattern7, "explicit"),
        (pattern8, "relative"),
    ]

    for pattern, date_type in all_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            date_text = match.group()
            start_pos = match.start()
            end_pos = match.end()

            # Extract context
            context_before = text[max(0, start_pos - context_chars) : start_pos].strip()
            context_after = text[
                end_pos : min(len(text), end_pos + context_chars)
            ].strip()

            # Try to parse the date
            parsed_date = None
            try:
                if date_type == "explicit":
                    parsed_date = date_parser.parse(date_text, fuzzy=True)
            except (ValueError, TypeError):
                # If parsing fails, store as None
                pass

            mentions.append(
                {
                    "date_text": date_text,
                    "parsed_date": parsed_date,
                    "date_type": date_type,
                    "context_before": context_before,
                    "context_after": context_after,
                    "position": start_pos,
                }
            )

    # Remove duplicates (same date_text at same position)
    unique_mentions = []
    seen = set()
    for mention in mentions:
        key = (mention["date_text"], mention["position"])
        if key not in seen:
            seen.add(key)
            unique_mentions.append(mention)

    # Sort by position in text
    unique_mentions.sort(key=lambda x: x["position"])

    return unique_mentions


def extract_events_with_llm(text: str, max_events: int = 10) -> List[Dict]:
    """
    Use LLM to extract timeline events from text.

    Extracts:
    - Event descriptions
    - Associated dates
    - Event types (meeting, transaction, communication, etc.)
    - Confidence scores

    Args:
        text: Input text to analyze
        max_events: Maximum number of events to extract

    Returns:
        List of dicts with keys: description, event_date, event_type, confidence, context
    """
    prompt = f"""You are a timeline analyst. Extract ALL chronological events from the following text.

For each event, provide:
1. A concise description (1 sentence)
2. The date or time period (exact date if mentioned, otherwise "unknown")
3. Event type (one of: meeting, transaction, communication, deadline, incident, other)
4. Confidence score (0.0-1.0) based on how explicit the event is

Return as JSON:
{{
  "events": [
    {{
      "description": "Event description here",
      "date": "2023-03-15" or "March 2023" or "unknown",
      "event_type": "meeting",
      "confidence": 0.9
    }}
  ]
}}

If no events found, return: {{"events": []}}

Text to analyze:
{text}

JSON output:"""

    try:
        response = chat_with_llm(
            prompt,
            temperature=0.3,
            max_tokens=1500,
            json_schema=LLM_EVENTS_ARRAY_SCHEMA,
        )

        # Clean response - remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            # Remove ```json and ``` markers
            response = re.sub(r"^```(?:json)?\n?", "", response)
            response = re.sub(r"\n?```$", "", response)

        # Parse JSON
        result = json.loads(response)
        events = result.get("events", [])

        # Limit to max_events
        events = events[:max_events]

        # Parse dates in events
        for event in events:
            if "date" in event and event["date"] != "unknown":
                try:
                    parsed = date_parser.parse(event["date"], fuzzy=True)
                    event["parsed_date"] = parsed
                except (ValueError, TypeError):
                    event["parsed_date"] = None
            else:
                event["parsed_date"] = None

            # Ensure required fields exist
            event.setdefault("description", "")
            event.setdefault("event_type", "other")
            event.setdefault("confidence", 0.5)

        return events

    except Exception as e:
        logger.error(f"Error extracting events with LLM: {str(e)}")
        return []


def determine_date_precision(date_text: str) -> str:
    """
    Determine the precision level of a date string.

    Returns: "day", "month", "year", or "approximate"
    """
    # Year only
    if re.match(r"^\d{4}$", date_text.strip()):
        return "year"

    # Month and year
    if re.match(
        r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}$",
        date_text,
        re.IGNORECASE,
    ):
        return "month"

    if re.match(r"^\d{1,2}[-/]\d{4}$", date_text):
        return "month"

    # Relative dates
    if re.search(r"\b(last|next|ago|yesterday|tomorrow)\b", date_text, re.IGNORECASE):
        return "approximate"

    # Full dates (assume day precision)
    return "day"


def extract_timeline_from_chunk(
    chunk_text: str, chunk_id: int, doc_id: int
) -> Tuple[List[Dict], List[Dict]]:
    """
    Extract both date mentions and events from a text chunk.

    Args:
        chunk_text: Text to analyze
        chunk_id: Database ID of the chunk
        doc_id: Database ID of the document

    Returns:
        Tuple of (date_mentions, timeline_events)
        Both are lists of dicts ready to be inserted into the database
    """
    # Extract date mentions
    date_mentions = extract_date_mentions(chunk_text)

    # Prepare for database insertion
    db_date_mentions = []
    for mention in date_mentions:
        db_date_mentions.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "date_text": mention["date_text"],
                "parsed_date": mention["parsed_date"],
                "date_type": mention["date_type"],
                "context_before": mention["context_before"],
                "context_after": mention["context_after"],
            }
        )

    # Extract events using LLM (only if chunk is substantial)
    timeline_events = []
    if len(chunk_text) > 100:  # Only analyze substantial chunks
        llm_events = extract_events_with_llm(chunk_text, max_events=5)

        for event in llm_events:
            # Extract context (first 200 chars of chunk)
            context = chunk_text[:200] + ("..." if len(chunk_text) > 200 else "")

            timeline_events.append(
                {
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "event_date": event.get("parsed_date"),
                    "event_date_text": event.get("date", "unknown"),
                    "date_precision": determine_date_precision(event.get("date", "")),
                    "description": event.get("description", ""),
                    "event_type": event.get("event_type", "other"),
                    "confidence": event.get("confidence", 0.5),
                    "extraction_method": "llm",
                    "context": context,
                }
            )

    return db_date_mentions, timeline_events


def analyze_timeline_gaps(
    events: List[Dict], gap_threshold_days: int = 30
) -> List[Dict]:
    """
    Identify suspicious gaps in timeline coverage.

    Args:
        events: List of timeline events (must have 'event_date' key)
        gap_threshold_days: Minimum gap size to flag

    Returns:
        List of gap descriptions with start/end dates and duration
    """
    # Filter events with valid dates
    dated_events = [e for e in events if e.get("event_date")]

    if len(dated_events) < 2:
        return []

    # Sort by date
    dated_events.sort(key=lambda x: x["event_date"])

    gaps = []
    for i in range(len(dated_events) - 1):
        current = dated_events[i]["event_date"]
        next_event = dated_events[i + 1]["event_date"]

        gap_days = (next_event - current).days

        if gap_days > gap_threshold_days:
            gaps.append(
                {
                    "start_date": current,
                    "end_date": next_event,
                    "duration_days": gap_days,
                    "before_event": dated_events[i].get("description", "Unknown"),
                    "after_event": dated_events[i + 1].get("description", "Unknown"),
                }
            )

    return gaps
