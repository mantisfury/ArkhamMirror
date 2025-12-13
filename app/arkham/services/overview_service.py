import logging

logger = logging.getLogger(__name__)

from config.settings import DATABASE_URL
import os
from typing import Dict, Any, List
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

from app.arkham.services.db.models import (
    Document,
    Chunk,
    CanonicalEntity,
    Anomaly,
    ExtractedTable,
    TimelineEvent,
)

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_overview_stats() -> Dict[str, Any]:
    """
    Fetch global statistics for the overview dashboard.
    """
    session = SessionLocal()
    try:
        # Document counts
        total_docs = session.query(Document).count()
        docs_by_type = (
            session.query(Document.doc_type, func.count(Document.id))
            .group_by(Document.doc_type)
            .all()
        )

        # Entity counts
        total_entities = session.query(CanonicalEntity).count()
        entities_by_type = (
            session.query(CanonicalEntity.label, func.count(CanonicalEntity.id))
            .group_by(CanonicalEntity.label)
            .order_by(func.count(CanonicalEntity.id).desc())
            .limit(5)
            .all()
        )

        # Other metrics
        total_chunks = session.query(Chunk).count()
        total_anomalies = session.query(Anomaly).count()
        total_tables = session.query(ExtractedTable).count()
        total_events = session.query(TimelineEvent).count()

        # Recent activity (newest documents)
        recent_docs = (
            session.query(Document).order_by(Document.created_at.desc()).limit(5).all()
        )

        return {
            "total_docs": total_docs,
            "docs_by_type": [{"type": t, "count": c} for t, c in docs_by_type],
            "total_entities": total_entities,
            "top_entity_types": [{"type": t, "count": c} for t, c in entities_by_type],
            "total_chunks": total_chunks,
            "total_anomalies": total_anomalies,
            "total_tables": total_tables,
            "total_events": total_events,
            "recent_docs": [
                {
                    "id": d.id,
                    "title": d.title or f"Document {d.id}",
                    "created_at": d.created_at.strftime("%Y-%m-%d %H:%M"),
                    "type": d.doc_type,
                }
                for d in recent_docs
            ],
        }
    except Exception as e:
        logger.error(f"Error fetching overview stats: {e}")
        return {}
    finally:
        session.close()


def get_all_documents(limit: int = 1000) -> List[Dict[str, Any]]:
    """Get all documents for drill-down view."""
    session = SessionLocal()
    try:
        docs = session.query(Document).order_by(Document.created_at.desc()).limit(limit).all()
        return [
            {
                "id": d.id,
                "title": d.title,
                "filename": d.path,
                "media_type": d.doc_type or "",
                "status": d.status or "",
            }
            for d in docs
        ]
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return []
    finally:
        session.close()


def get_all_entities(limit: int = 1000) -> List[Dict[str, Any]]:
    """Get all entities for drill-down view."""
    session = SessionLocal()
    try:
        entities = (
            session.query(CanonicalEntity)
            .order_by(CanonicalEntity.total_mentions.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": e.id,
                "name": e.canonical_name,
                "type": e.label or "",
                "mentions": e.total_mentions or 0,
            }
            for e in entities
        ]
    except Exception as e:
        logger.error(f"Error fetching entities: {e}")
        return []
    finally:
        session.close()


def get_all_anomalies(limit: int = 1000) -> List[Dict[str, Any]]:
    """Get all anomalies for drill-down view."""
    session = SessionLocal()
    try:
        anomalies = session.query(Anomaly).order_by(Anomaly.id.desc()).limit(limit).all()
        return [
            {
                "id": a.id,
                "description": a.reason or a.explanation or "",
                "type": "",
                "severity": f"Score: {a.score:.2f}" if a.score else "",
            }
            for a in anomalies
        ]
    except Exception as e:
        logger.error(f"Error fetching anomalies: {e}")
        return []
    finally:
        session.close()


def get_all_events(limit: int = 1000) -> List[Dict[str, Any]]:
    """Get all timeline events for drill-down view."""
    session = SessionLocal()
    try:
        events = session.query(TimelineEvent).order_by(TimelineEvent.id.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "description": e.description or "",
                "event_type": e.event_type or "",
                "date": str(e.event_date) if e.event_date else "",
            }
            for e in events
        ]
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return []
    finally:
        session.close()


def get_sample_chunks(limit: int = 100) -> List[Dict[str, Any]]:
    """Get sample chunks for drill-down view."""
    session = SessionLocal()
    try:
        chunks = session.query(Chunk).order_by(Chunk.id.desc()).limit(limit).all()
        return [
            {
                "id": c.id,
                "text": c.text or "",
                "doc_id": c.doc_id,
                "sequence": c.chunk_index,
            }
            for c in chunks
        ]
    except Exception as e:
        logger.error(f"Error fetching chunks: {e}")
        return []
    finally:
        session.close()


def get_all_tables(limit: int = 1000) -> List[Dict[str, Any]]:
    """Get all extracted tables for drill-down view."""
    session = SessionLocal()
    try:
        tables = session.query(ExtractedTable).order_by(ExtractedTable.id.desc()).limit(limit).all()
        return [
            {
                "id": t.id,
                "title": f"Page {t.page_num}, Table {t.table_index}",
                "doc_id": t.doc_id,
                "row_count": t.row_count or 0,
            }
            for t in tables
        ]
    except Exception as e:
        logger.error(f"Error fetching tables: {e}")
        return []
    finally:
        session.close()
