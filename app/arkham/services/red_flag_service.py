import os
import sys
import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import logging

from config.settings import DATABASE_URL

from sqlalchemy import create_engine, func, and_, or_
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.arkham.services.db.models import (
    Document,
    Chunk,
    Entity,
    CanonicalEntity,
    Anomaly,
    TimelineEvent,
    DateMention,
    ExtractedTable,
)

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection



class RedFlagService:
    """Service for detecting red flags in document corpus."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def detect_all_red_flags(self) -> List[Dict]:
        """
        Run all red flag detectors and return combined results.

        Returns:
            List of red flag dictionaries with all detected issues
        """
        all_flags = []

        logger.info("Running all red flag detectors...")

        # Run each detector
        all_flags.extend(self.detect_financial_flags())
        all_flags.extend(self.detect_timeline_anomalies())
        all_flags.extend(self.detect_content_anomalies())
        all_flags.extend(self.detect_entity_behavior_flags())
        all_flags.extend(self.detect_metadata_forensics())
        all_flags.extend(self.detect_hidden_content())

        logger.info(f"Total red flags detected: {len(all_flags)}")

        return all_flags

    def detect_financial_flags(self) -> List[Dict]:
        """
        Detect financial red flags: round numbers, structuring patterns.

        Detects:
        - Round number transactions (amounts ending in 000)
        - Structuring patterns (multiple transactions just below $10K threshold)

        Returns:
            List of financial red flag dictionaries
        """
        session = self.Session()
        flags = []

        try:
            # Get all chunks to search for currency amounts
            chunks = (
                session.query(Chunk)
                .join(Document)
                .filter(Document.status == "complete")
                .all()
            )

            # Regex patterns for currency detection
            # Matches: $10,000 | $9,999 | 10000 USD | 10.000 EUR | etc.
            currency_pattern = re.compile(
                r"[\$\£\€]\s*[\d,]+(?:\.\d{2})?|\d[\d,]+\s*(?:USD|EUR|GBP|dollars?)",
                re.IGNORECASE,
            )

            # Track all amounts per document for structuring detection
            doc_amounts = defaultdict(list)

            for chunk in chunks:
                matches = currency_pattern.findall(chunk.text)

                for match in matches:
                    # Parse amount (remove currency symbols and commas)
                    amount_str = re.sub(r"[^\d.]", "", match)
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        continue

                    # Store for structuring detection
                    doc_amounts[chunk.doc_id].append(
                        {"amount": amount, "text": match, "chunk_id": chunk.id}
                    )

                    # DETECTOR 1: Round Number Transactions
                    # Check if amount ends in 000 or is exactly divisible by 1000
                    if amount >= 1000 and amount % 1000 == 0:
                        flags.append(
                            {
                                "flag_type": "financial",
                                "flag_category": "round_numbers",
                                "severity": "MEDIUM",
                                "title": "Round Number Transaction Detected",
                                "description": f"Transaction amount {match} is a round number (ends in 000), "
                                f"which may indicate artificial structuring or estimation rather than "
                                f"an actual precise transaction.",
                                "evidence": {
                                    "amount": match,
                                    "numeric_value": amount,
                                    "chunk_text": chunk.text[:200],
                                },
                                "confidence": 0.6,
                                "doc_id": chunk.doc_id,
                                "chunk_id": chunk.id,
                                "entity_id": None,
                                "timeline_event_id": None,
                            }
                        )

            # DETECTOR 2: Structuring Pattern Detection (Smurfing)
            # Look for multiple transactions between $9,000-$9,999 (just below $10K threshold)
            for doc_id, amounts in doc_amounts.items():
                # Filter amounts in structuring range
                structuring_amounts = [
                    a for a in amounts if 9000 <= a["amount"] <= 9999
                ]

                # If 3+ transactions in this range, flag as critical
                if len(structuring_amounts) >= 3:
                    total = sum(a["amount"] for a in structuring_amounts)
                    flags.append(
                        {
                            "flag_type": "financial",
                            "flag_category": "structuring",
                            "severity": "CRITICAL",
                            "title": "Possible Structuring Pattern Detected (Smurfing)",
                            "description": f"Detected {len(structuring_amounts)} transactions between $9,000-$9,999 "
                            f"in a single document, potentially evading the $10,000 reporting threshold. "
                            f"Total amount: ${total:,.2f}",
                            "evidence": {
                                "transaction_count": len(structuring_amounts),
                                "transactions": [
                                    {"amount": a["text"], "value": a["amount"]}
                                    for a in structuring_amounts
                                ],
                                "total_amount": total,
                            },
                            "confidence": 0.85,
                            "doc_id": doc_id,
                            "chunk_id": structuring_amounts[0]["chunk_id"],
                            "entity_id": None,
                            "timeline_event_id": None,
                        }
                    )

        except Exception as e:
            logger.error(f"Financial flag detection failed: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Financial flags detected: {len(flags)}")
        return flags

    def detect_timeline_anomalies(self) -> List[Dict]:
        """
        Detect timeline anomalies: backdated documents, timeline gaps, impossible dates.

        Detects:
        - Backdated documents (creation date after modification date)
        - Timeline gaps (long periods with no activity)
        - Impossible dates (future dates in past-tense documents)

        Returns:
            List of timeline red flag dictionaries
        """
        session = self.Session()
        flags = []

        try:
            # DETECTOR 1: Backdated Documents
            # Check for documents where modification date is before creation date
            backdated_docs = (
                session.query(Document)
                .filter(
                    and_(
                        Document.pdf_creation_date.isnot(None),
                        Document.pdf_modification_date.isnot(None),
                        Document.pdf_modification_date < Document.pdf_creation_date,
                    )
                )
                .all()
            )

            for doc in backdated_docs:
                flags.append(
                    {
                        "flag_type": "timeline",
                        "flag_category": "backdated_document",
                        "severity": "HIGH",
                        "title": "Backdated Document Detected",
                        "description": f"Document '{doc.title}' has a modification date "
                        f"({doc.pdf_modification_date.strftime('%Y-%m-%d')}) that is BEFORE "
                        f"its creation date ({doc.pdf_creation_date.strftime('%Y-%m-%d')}). "
                        f"This is technically impossible and suggests document tampering.",
                        "evidence": {
                            "creation_date": doc.pdf_creation_date.isoformat(),
                            "modification_date": doc.pdf_modification_date.isoformat(),
                            "pdf_producer": doc.pdf_producer,
                            "pdf_creator": doc.pdf_creator,
                        },
                        "confidence": 0.95,
                        "doc_id": doc.id,
                        "chunk_id": None,
                        "entity_id": None,
                        "timeline_event_id": None,
                    }
                )

            # DETECTOR 2: Timeline Gaps
            # Get all timeline events sorted by date
            timeline_events = (
                session.query(TimelineEvent)
                .filter(TimelineEvent.event_date.isnot(None))
                .order_by(TimelineEvent.event_date)
                .all()
            )

            # Check for gaps > 90 days between consecutive events
            for i in range(len(timeline_events) - 1):
                current_event = timeline_events[i]
                next_event = timeline_events[i + 1]

                gap = (next_event.event_date - current_event.event_date).days

                if gap > 90:
                    flags.append(
                        {
                            "flag_type": "timeline",
                            "flag_category": "timeline_gap",
                            "severity": "MEDIUM",
                            "title": "Suspicious Timeline Gap Detected",
                            "description": f"Gap of {gap} days between timeline events. "
                            f"Long periods of inactivity may indicate missing records or "
                            f"deliberate omissions.",
                            "evidence": {
                                "gap_days": gap,
                                "before_event": {
                                    "date": current_event.event_date.isoformat(),
                                    "description": current_event.description[:100],
                                },
                                "after_event": {
                                    "date": next_event.event_date.isoformat(),
                                    "description": next_event.description[:100],
                                },
                            },
                            "confidence": 0.5,
                            "doc_id": next_event.doc_id,
                            "chunk_id": None,
                            "entity_id": None,
                            "timeline_event_id": next_event.id,
                        }
                    )

            # DETECTOR 3: Impossible Dates (Future Dates)
            # Check for events with dates in the future
            future_events = (
                session.query(TimelineEvent)
                .filter(TimelineEvent.event_date > datetime.utcnow())
                .all()
            )

            for event in future_events:
                flags.append(
                    {
                        "flag_type": "timeline",
                        "flag_category": "impossible_date",
                        "severity": "MEDIUM",
                        "title": "Future Date in Historical Document",
                        "description": f"Event dated {event.event_date.strftime('%Y-%m-%d')} is in the future. "
                        f"This may indicate a data extraction error or document forgery.",
                        "evidence": {
                            "event_date": event.event_date.isoformat(),
                            "event_description": event.description[:200],
                            "extraction_method": event.extraction_method,
                        },
                        "confidence": 0.7,
                        "doc_id": event.doc_id,
                        "chunk_id": event.chunk_id,
                        "entity_id": None,
                        "timeline_event_id": event.id,
                    }
                )

        except Exception as e:
            logger.error(f"Timeline anomaly detection failed: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Timeline anomalies detected: {len(flags)}")
        return flags

    def detect_content_anomalies(self) -> List[Dict]:
        """
        Detect content anomalies: high anomaly clustering.

        Detects:
        - Documents with unusually high number of anomalies
        - Entities appearing frequently in anomalous documents

        Returns:
            List of content anomaly red flag dictionaries
        """
        session = self.Session()
        flags = []

        try:
            # DETECTOR 1: High Anomaly Clustering
            # Count anomalies per document
            anomaly_counts = (
                session.query(
                    Chunk.doc_id, func.count(Anomaly.id).label("anomaly_count")
                )
                .join(Anomaly)
                .group_by(Chunk.doc_id)
                .all()
            )

            for doc_id, count in anomaly_counts:
                # Flag documents with 5+ anomalies
                if count >= 5:
                    doc = session.query(Document).filter(Document.id == doc_id).first()

                    # Get sample anomalies for evidence
                    sample_anomalies = (
                        session.query(Anomaly)
                        .join(Chunk)
                        .filter(Chunk.doc_id == doc_id)
                        .limit(3)
                        .all()
                    )

                    flags.append(
                        {
                            "flag_type": "content",
                            "flag_category": "high_anomaly_clustering",
                            "severity": "MEDIUM",
                            "title": "Document with Unusually High Anomaly Count",
                            "description": f"Document '{doc.title}' has {count} detected anomalies, "
                            f"significantly higher than typical. This may indicate unusual "
                            f"or suspicious content requiring manual review.",
                            "evidence": {
                                "anomaly_count": count,
                                "sample_anomalies": [
                                    {
                                        "reason": a.reason,
                                        "score": a.score,
                                        "explanation": a.explanation,
                                    }
                                    for a in sample_anomalies
                                ],
                            },
                            "confidence": 0.65,
                            "doc_id": doc_id,
                            "chunk_id": None,
                            "entity_id": None,
                            "timeline_event_id": None,
                        }
                    )

        except Exception as e:
            logger.error(f"Content anomaly detection failed: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Content anomaly flags detected: {len(flags)}")
        return flags

    def detect_entity_behavior_flags(self) -> List[Dict]:
        """
        Detect entity behavior anomalies: name changes, sudden disappearances.

        Detects:
        - Entities with multiple aliases (potential identity obfuscation)
        - Entities that suddenly stop appearing in documents

        Returns:
            List of entity behavior red flag dictionaries
        """
        session = self.Session()
        flags = []

        try:
            # DETECTOR 1: Entity Name Changes / Multiple Aliases
            # Check for canonical entities with many aliases
            entities_with_aliases = (
                session.query(CanonicalEntity)
                .filter(CanonicalEntity.aliases.isnot(None))
                .all()
            )

            for entity in entities_with_aliases:
                try:
                    aliases = json.loads(entity.aliases) if entity.aliases else []
                except (json.JSONDecodeError, TypeError):
                    aliases = []

                # Flag if entity has 3+ aliases
                if len(aliases) >= 3:
                    flags.append(
                        {
                            "flag_type": "entity_behavior",
                            "flag_category": "name_changes",
                            "severity": "HIGH",
                            "title": "Entity with Multiple Aliases Detected",
                            "description": f"Entity '{entity.canonical_name}' has {len(aliases)} known aliases. "
                            f"Multiple name variations may indicate identity obfuscation, "
                            f"shell companies, or data quality issues requiring investigation.",
                            "evidence": {
                                "canonical_name": entity.canonical_name,
                                "alias_count": len(aliases),
                                "aliases": aliases,
                                "total_mentions": entity.total_mentions,
                                "entity_type": entity.label,
                            },
                            "confidence": 0.7,
                            "doc_id": None,
                            "chunk_id": None,
                            "entity_id": entity.id,
                            "timeline_event_id": None,
                        }
                    )

            # DETECTOR 2: Sudden Disappearance
            # Find entities that were frequently mentioned but then stopped appearing
            # (Entity appears in first 70% of documents but not in last 30%)

            # Get document chronology
            all_docs = (
                session.query(Document)
                .filter(Document.status == "complete")
                .order_by(Document.created_at)
                .all()
            )

            if len(all_docs) >= 5:  # Need at least 5 docs for meaningful analysis
                cutoff_index = int(len(all_docs) * 0.7)
                early_doc_ids = [d.id for d in all_docs[:cutoff_index]]
                late_doc_ids = [d.id for d in all_docs[cutoff_index:]]

                # Find entities mentioned 5+ times in early docs
                active_entities = (
                    session.query(
                        Entity.canonical_entity_id,
                        func.count(Entity.id).label("mention_count"),
                    )
                    .join(CanonicalEntity)
                    .filter(
                        Entity.doc_id.in_(early_doc_ids),
                        Entity.canonical_entity_id.isnot(None),
                    )
                    .group_by(Entity.canonical_entity_id)
                    .having(func.count(Entity.id) >= 5)
                    .all()
                )

                for entity_id, early_mentions in active_entities:
                    # Check if entity appears in late docs
                    late_mentions = (
                        session.query(func.count(Entity.id))
                        .filter(
                            Entity.canonical_entity_id == entity_id,
                            Entity.doc_id.in_(late_doc_ids),
                        )
                        .scalar()
                    )

                    if late_mentions == 0:
                        entity = (
                            session.query(CanonicalEntity)
                            .filter(CanonicalEntity.id == entity_id)
                            .first()
                        )

                        flags.append(
                            {
                                "flag_type": "entity_behavior",
                                "flag_category": "sudden_disappearance",
                                "severity": "MEDIUM",
                                "title": "Entity Sudden Disappearance Detected",
                                "description": f"Entity '{entity.canonical_name}' was mentioned {early_mentions} times "
                                f"in earlier documents but completely disappears in recent documents. "
                                f"This may indicate the entity was removed, replaced, or is no longer active.",
                                "evidence": {
                                    "entity_name": entity.canonical_name,
                                    "early_mentions": early_mentions,
                                    "late_mentions": late_mentions,
                                    "entity_type": entity.label,
                                    "last_seen": entity.last_seen.isoformat()
                                    if entity.last_seen
                                    else None,
                                },
                                "confidence": 0.6,
                                "doc_id": None,
                                "chunk_id": None,
                                "entity_id": entity.id,
                                "timeline_event_id": None,
                            }
                        )

        except Exception as e:
            logger.error(f"Entity behavior flag detection failed: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Entity behavior flags detected: {len(flags)}")
        return flags

    def detect_metadata_forensics(self) -> List[Dict]:
        """
        Detect metadata forensic anomalies: creation date issues, author inconsistencies.

        Detects:
        - Documents modified before created (impossible)
        - Author inconsistencies in document series

        Returns:
            List of metadata forensics red flag dictionaries
        """
        session = self.Session()
        flags = []

        try:
            # DETECTOR 1: Creation Date Anomalies (already covered in timeline)
            # This is a duplicate of backdated_document, so we'll add a different check:
            # Documents with creation date far in the past vs file system date

            docs_with_dates = (
                session.query(Document)
                .filter(
                    and_(
                        Document.pdf_creation_date.isnot(None),
                        Document.created_at.isnot(None),
                    )
                )
                .all()
            )

            for doc in docs_with_dates:
                # Check if PDF claims to be created >10 years before file was uploaded
                # (indicates possible backdating or timestamp manipulation)
                date_diff = (doc.created_at - doc.pdf_creation_date).days

                if date_diff > 3650:  # 10 years
                    flags.append(
                        {
                            "flag_type": "metadata",
                            "flag_category": "creation_date_anomaly",
                            "severity": "MEDIUM",
                            "title": "Suspicious PDF Creation Date",
                            "description": f"Document '{doc.title}' has a PDF creation date "
                            f"({doc.pdf_creation_date.strftime('%Y-%m-%d')}) that is "
                            f"{date_diff // 365} years before the file was uploaded. "
                            f"This may indicate timestamp manipulation or document forgery.",
                            "evidence": {
                                "pdf_creation_date": doc.pdf_creation_date.isoformat(),
                                "file_upload_date": doc.created_at.isoformat(),
                                "days_difference": date_diff,
                                "pdf_producer": doc.pdf_producer,
                                "pdf_creator": doc.pdf_creator,
                            },
                            "confidence": 0.5,
                            "doc_id": doc.id,
                            "chunk_id": None,
                            "entity_id": None,
                            "timeline_event_id": None,
                        }
                    )

            # DETECTOR 2: Author Inconsistencies
            # Group documents by similar titles (document series detection)
            all_docs = (
                session.query(Document)
                .filter(
                    and_(Document.pdf_author.isnot(None), Document.title.isnot(None))
                )
                .all()
            )

            # Simple series detection: group by first 3 words of title
            series_groups = defaultdict(list)
            for doc in all_docs:
                # Extract first 3 words as series identifier
                words = doc.title.split()[:3]
                series_key = " ".join(words).lower()
                series_groups[series_key].append(doc)

            # Check for author inconsistencies within series
            for series_key, docs in series_groups.items():
                if len(docs) >= 2:  # Need at least 2 docs to compare
                    authors = [doc.pdf_author for doc in docs]
                    unique_authors = set(authors)

                    if len(unique_authors) > 1:
                        flags.append(
                            {
                                "flag_type": "metadata",
                                "flag_category": "author_inconsistency",
                                "severity": "LOW",
                                "title": "Author Inconsistency in Document Series",
                                "description": f"Document series starting with '{series_key}' has {len(unique_authors)} "
                                f"different authors: {', '.join(unique_authors)}. "
                                f"This may indicate collaborative authoring, document tampering, "
                                f"or metadata inconsistencies.",
                                "evidence": {
                                    "series_identifier": series_key,
                                    "document_count": len(docs),
                                    "unique_authors": list(unique_authors),
                                    "documents": [
                                        {"title": d.title, "author": d.pdf_author}
                                        for d in docs
                                    ],
                                },
                                "confidence": 0.4,
                                "doc_id": docs[0].id,
                                "chunk_id": None,
                                "entity_id": None,
                                "timeline_event_id": None,
                            }
                        )

        except Exception as e:
            logger.error(f"Metadata forensics detection failed: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        logger.info(f"Metadata forensics flags detected: {len(flags)}")
        return flags

    def save_red_flags(self, flags: List[Dict]) -> int:
        """
        Save detected red flags to database.

        Clears existing 'active' flags before saving to prevent duplicates.
        Each detection run replaces the previous active flags.

        Args:
            flags: List of red flag dictionaries to save

        Returns:
            Number of flags saved
        """
        session = self.Session()
        count = 0

        try:
            from app.arkham.services.db.models import Base
            from sqlalchemy import Table, MetaData, delete

            # Get red_flags table metadata
            metadata = MetaData()
            metadata.reflect(bind=self.engine)

            if "red_flags" not in metadata.tables:
                logger.error("red_flags table does not exist. Run migration first.")
                return 0

            red_flags_table = metadata.tables["red_flags"]

            # Delete all existing 'active' flags before inserting new detection
            # This prevents duplicates from multiple detection runs
            delete_stmt = delete(red_flags_table).where(
                red_flags_table.c.status == "active"
            )
            deleted = session.execute(delete_stmt)
            logger.info(f"Cleared {deleted.rowcount} existing active flags")

            for flag in flags:
                # Convert evidence dict to JSON string
                evidence_json = json.dumps(flag.get("evidence", {}))

                # Insert flag
                insert_stmt = red_flags_table.insert().values(
                    flag_type=flag["flag_type"],
                    flag_category=flag["flag_category"],
                    severity=flag["severity"],
                    title=flag["title"],
                    description=flag["description"],
                    evidence=evidence_json,
                    confidence=flag.get("confidence", 0.5),
                    doc_id=flag.get("doc_id"),
                    entity_id=flag.get("entity_id"),
                    timeline_event_id=flag.get("timeline_event_id"),
                    status="active",
                    detected_at=datetime.utcnow(),
                )

                session.execute(insert_stmt)
                count += 1

            session.commit()
            logger.info(f"Saved {count} red flags to database")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save red flags: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        return count

    def get_red_flags(
        self,
        severity_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        status_filter: str = "active",
        sort_by: str = "severity",
        sort_direction: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Retrieve red flags from database with filtering and pagination.

        Args:
            severity_filter: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)
            category_filter: Filter by flag_category
            status_filter: Filter by status (active, reviewed, dismissed, escalated)
            sort_by: Column to sort by (severity, flag_category, title, detected_at, status)
            sort_direction: Sort direction (asc or desc)
            limit: Maximum number of results
            offset: Number of results to skip (for pagination)

        Returns:
            List of red flag dictionaries
        """
        session = self.Session()
        results = []

        try:
            from sqlalchemy import Table, MetaData, select, asc, desc

            metadata = MetaData()
            metadata.reflect(bind=self.engine)

            if "red_flags" not in metadata.tables:
                logger.warning("red_flags table does not exist")
                return []

            red_flags_table = metadata.tables["red_flags"]

            # Build query with filters
            query = select(red_flags_table)

            if severity_filter:
                query = query.where(red_flags_table.c.severity == severity_filter)

            if category_filter:
                query = query.where(red_flags_table.c.flag_category == category_filter)

            if status_filter:
                query = query.where(red_flags_table.c.status == status_filter)

            # Map sort_by to actual column names
            sort_column_map = {
                "severity": red_flags_table.c.severity,
                "category": red_flags_table.c.flag_category,
                "title": red_flags_table.c.title,
                "detected_at": red_flags_table.c.detected_at,
                "status": red_flags_table.c.status,
            }

            sort_column = sort_column_map.get(sort_by, red_flags_table.c.severity)
            order_func = desc if sort_direction == "desc" else asc

            query = query.order_by(order_func(sort_column)).offset(offset).limit(limit)

            rows = session.execute(query).fetchall()

            for row in rows:
                results.append(
                    {
                        "id": row.id,
                        "flag_type": row.flag_type,
                        "flag_category": row.flag_category,
                        "severity": row.severity,
                        "title": row.title,
                        "description": row.description,
                        "evidence": json.loads(row.evidence) if row.evidence else {},
                        "confidence": row.confidence,
                        "doc_id": row.doc_id,
                        "entity_id": row.entity_id,
                        "timeline_event_id": row.timeline_event_id,
                        "status": row.status,
                        "reviewer_notes": row.reviewer_notes,
                        "reviewed_at": row.reviewed_at.isoformat()
                        if row.reviewed_at
                        else None,
                        "detected_at": row.detected_at.isoformat()
                        if row.detected_at
                        else None,
                    }
                )

        except Exception as e:
            logger.error(f"Failed to retrieve red flags: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        return results

    def update_flag_status(
        self, flag_id: int, status: str, reviewer_notes: Optional[str] = None
    ) -> bool:
        """
        Update the status of a red flag (mark as reviewed, dismissed, escalated).

        Args:
            flag_id: Red flag ID to update
            status: New status (reviewed, dismissed, escalated)
            reviewer_notes: Optional analyst notes

        Returns:
            True if successful, False otherwise
        """
        session = self.Session()

        try:
            from sqlalchemy import Table, MetaData, update

            metadata = MetaData()
            metadata.reflect(bind=self.engine)

            if "red_flags" not in metadata.tables:
                logger.error("red_flags table does not exist")
                return False

            red_flags_table = metadata.tables["red_flags"]

            # Update statement
            update_stmt = (
                update(red_flags_table)
                .where(red_flags_table.c.id == flag_id)
                .values(
                    status=status,
                    reviewer_notes=reviewer_notes,
                    reviewed_at=datetime.utcnow(),
                )
            )

            session.execute(update_stmt)
            session.commit()
            logger.info(f"Updated red flag {flag_id} to status: {status}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update red flag: {e}")
            import traceback

            traceback.print_exc()
            return False

        finally:
            session.close()

    def get_summary_stats(self) -> Dict[str, int]:
        """
        Get summary statistics for red flags dashboard.

        Returns:
            Dictionary with counts by severity
        """
        session = self.Session()
        stats = {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}

        try:
            from sqlalchemy import Table, MetaData, select, func

            metadata = MetaData()
            metadata.reflect(bind=self.engine)

            if "red_flags" not in metadata.tables:
                return stats

            red_flags_table = metadata.tables["red_flags"]

            # Count by severity where status is active
            for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                count = session.execute(
                    select(func.count())
                    .select_from(red_flags_table)
                    .where(
                        and_(
                            red_flags_table.c.severity == severity,
                            red_flags_table.c.status == "active",
                        )
                    )
                ).scalar()

                stats[severity.lower()] = count
                stats["total"] += count

        except Exception as e:
            logger.error(f"Failed to get summary stats: {e}")

        finally:
            session.close()

        return stats

    def detect_hidden_content(self) -> List[Dict]:
        """
        Detect hidden content: steganography, invisible characters, homoglyphs.

        Delegates to HiddenContentDetector for specialized detection algorithms.

        Returns:
            List of hidden content red flag dictionaries
        """
        try:
            from app.arkham.services.hidden_content_detector import (
                get_hidden_content_detector,
            )

            detector = get_hidden_content_detector()
            flags = detector.detect_all_hidden_content()

            logger.info(f"Hidden content flags detected: {len(flags)}")
            return flags

        except Exception as e:
            logger.error(f"Hidden content detection failed: {e}")
            import traceback

            traceback.print_exc()
            return []


# Singleton instance
_service_instance = None


def get_red_flag_service() -> RedFlagService:
    """Get singleton red flag service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RedFlagService()
    return _service_instance
