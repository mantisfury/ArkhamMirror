import logging

logger = logging.getLogger(__name__)

from config.settings import DATABASE_URL
import os
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

from app.arkham.services.db.models import CanonicalEntity
from app.arkham.services.geocoding_service import get_geocoder

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_map_entities(
    entity_types: Optional[List[str]] = None, limit: int = 500
) -> List[Dict[str, Any]]:
    """
    Fetch entities with coordinates for map visualization.
    """
    session = SessionLocal()
    try:
        query = session.query(CanonicalEntity).filter(
            CanonicalEntity.latitude.isnot(None), CanonicalEntity.longitude.isnot(None)
        )

        if entity_types:
            query = query.filter(CanonicalEntity.label.in_(entity_types))
        else:
            # Default to location-related types if no filter
            query = query.filter(CanonicalEntity.label.in_(["GPE", "LOC", "FAC"]))

        entities = query.limit(limit).all()

        results = []
        for entity in entities:
            results.append(
                {
                    "id": entity.id,
                    "name": entity.canonical_name,
                    "type": entity.label,
                    "lat": entity.latitude,
                    "lon": entity.longitude,
                    "address": entity.resolved_address,
                    "mentions": entity.total_mentions or 0,
                }
            )

        return results
    except Exception as e:
        logger.error(f"Error fetching map entities: {e}")
        return []
    finally:
        session.close()


def trigger_geocoding_batch(limit: int = 20) -> int:
    """
    Trigger batch geocoding for entities without coordinates.
    Returns the number of newly geocoded entities.
    """
    session = SessionLocal()
    try:
        geocoder = get_geocoder()

        # Count before
        count_before = (
            session.query(CanonicalEntity)
            .filter(CanonicalEntity.latitude.isnot(None))
            .count()
        )

        geocoder.batch_process_entities(session, limit=limit)

        # Count after
        count_after = (
            session.query(CanonicalEntity)
            .filter(CanonicalEntity.latitude.isnot(None))
            .count()
        )

        return max(0, count_after - count_before)
    except Exception as e:
        logger.error(f"Error in batch geocoding: {e}")
        return 0
    finally:
        session.close()
