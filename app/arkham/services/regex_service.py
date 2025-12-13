import logging

logger = logging.getLogger(__name__)

from config.settings import DATABASE_URL
import re
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.arkham.services.db.models import Document, Chunk, SensitiveDataMatch
from app.arkham.services.utils.pattern_detector import get_detector, PatternMatch
import os

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_pattern_descriptions() -> Dict[str, str]:
    """Return dictionary of pattern types and their descriptions."""
    detector = get_detector()
    return detector.get_pattern_descriptions()


def search_patterns_in_chunks(
    pattern_types: List[str],
    custom_regex: Optional[str] = None,
    confidence_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Search for patterns across all documents.

    Args:
        pattern_types: List of built-in pattern types to search for.
        custom_regex: Optional custom regex string.
        confidence_threshold: Minimum confidence score.

    Returns:
        List of match dictionaries.
    """
    session = SessionLocal()
    try:
        chunks = session.query(Chunk).all()
        if not chunks:
            return []

        detector = get_detector()
        results = []

        # Compile custom regex if provided
        custom_pattern = None
        if custom_regex:
            try:
                custom_pattern = re.compile(custom_regex)
            except re.error:
                logger.warning(f"Invalid custom regex: {custom_regex}")

        # Batch fetch all document titles upfront to avoid N+1 queries
        doc_ids = list(set(chunk.doc_id for chunk in chunks))
        docs = session.query(Document).filter(Document.id.in_(doc_ids)).all()
        doc_title_map = {doc.id: doc.title for doc in docs}

        for chunk in chunks:
            # 1. Search built-in patterns
            if pattern_types:
                matches = detector.detect_patterns(
                    chunk.text, pattern_types=pattern_types
                )
                for match in matches:
                    if match.confidence >= confidence_threshold:
                        results.append(_format_match(match, chunk, doc_title_map))

            # 2. Search custom regex
            if custom_pattern:
                for match in custom_pattern.finditer(chunk.text):
                    match_text = match.group()
                    start = match.start()
                    end = match.end()
                    context_before = chunk.text[max(0, start - 30) : start].strip()
                    context_after = chunk.text[
                        end : min(len(chunk.text), end + 30)
                    ].strip()

                    results.append(
                        {
                            "doc_id": chunk.doc_id,
                            "chunk_id": chunk.id,
                            "pattern_type": "custom",
                            "match_text": match_text,
                            "confidence": 1.0,  # Custom regex is always 100% match to itself
                            "context": f"...{context_before} **{match_text}** {context_after}...",
                            "document_title": doc_title_map.get(
                                chunk.doc_id, f"Document #{chunk.doc_id}"
                            ),
                        }
                    )

        return results
    finally:
        session.close()


def get_detected_sensitive_data() -> Dict[str, Any]:
    """
    Retrieve previously detected sensitive data with statistics.

    Returns:
        Dictionary with 'matches' and 'stats' keys.
    """
    session = SessionLocal()
    try:
        matches_query = session.query(SensitiveDataMatch).all()

        if not matches_query:
            return {"matches": [], "stats": {}}

        # Batch fetch all document titles upfront
        doc_ids = list(set(match.doc_id for match in matches_query))
        docs = session.query(Document).filter(Document.id.in_(doc_ids)).all()
        doc_title_map = {doc.id: doc.title for doc in docs}

        # Format matches
        matches = []
        pattern_counts = {}

        for match in matches_query:
            context = f"...{match.context_before} **{match.match_text}** {match.context_after}..."

            matches.append(
                {
                    "doc_id": match.doc_id,
                    "chunk_id": match.chunk_id,
                    "pattern_type": match.pattern_type,
                    "match_text": match.match_text,
                    "confidence": match.confidence,
                    "context": context,
                    "document": doc_title_map.get(
                        match.doc_id, f"Document #{match.doc_id}"
                    ),
                }
            )

            # Count patterns
            pattern_counts[match.pattern_type] = (
                pattern_counts.get(match.pattern_type, 0) + 1
            )

        return {"matches": matches, "stats": pattern_counts}

    finally:
        session.close()


def get_detected_matches(
    pattern_filter: Optional[List[str]] = None, min_confidence: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Retrieve previously detected matches from the database (legacy function).
    """
    session = SessionLocal()
    try:
        query = session.query(SensitiveDataMatch)

        if pattern_filter:
            query = query.filter(SensitiveDataMatch.pattern_type.in_(pattern_filter))

        if min_confidence > 0:
            query = query.filter(SensitiveDataMatch.confidence >= min_confidence)

        matches = query.all()

        if not matches:
            return []

        # Batch fetch all document titles upfront to avoid N+1 queries
        doc_ids = list(set(match.doc_id for match in matches))
        docs = session.query(Document).filter(Document.id.in_(doc_ids)).all()
        doc_title_map = {doc.id: doc.title for doc in docs}

        results = []

        for match in matches:
            # Construct context string if not stored fully
            context = f"...{match.context_before} **{match.match_text}** {match.context_after}..."

            results.append(
                {
                    "doc_id": match.doc_id,
                    "chunk_id": match.chunk_id,
                    "pattern_type": match.pattern_type,
                    "match_text": match.match_text,
                    "confidence": match.confidence,
                    "context": context,
                    "document_title": doc_title_map.get(
                        match.doc_id, f"Document #{match.doc_id}"
                    ),
                }
            )

        return results
    finally:
        session.close()


def _format_match(
    match: PatternMatch, chunk: Chunk, doc_title_map: Dict[int, str]
) -> Dict[str, Any]:
    """Helper to format a PatternMatch object into a dictionary."""
    return {
        "doc_id": chunk.doc_id,
        "chunk_id": chunk.id,
        "pattern_type": match.pattern_type,
        "match_text": match.match_text,
        "confidence": match.confidence,
        "context": f"...{match.context_before} **{match.match_text}** {match.context_after}...",
        "document_title": doc_title_map.get(chunk.doc_id, f"Document #{chunk.doc_id}"),
    }
