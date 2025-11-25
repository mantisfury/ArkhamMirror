import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from backend.db.models import Entity

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()


def prune_entities():
    """
    Removes noisy entities from the database based on heuristics.
    """
    logger.info("Starting entity pruning...")

    # 1. Remove short entities
    from sqlalchemy import func

    deleted_short = (
        session.query(Entity)
        .filter(
            (Entity.text == None) | (Entity.text == "") | (func.length(Entity.text) < 3)
        )
        .delete(synchronize_session=False)
    )
    logger.info(f"Deleted {deleted_short} short entities.")

    # 2. Remove blocklisted terms
    BLOCKLIST = [
        "page",
        "total",
        "date",
        "invoice",
        "subtotal",
        "amount",
        "description",
        "item",
        "qty",
        "price",
        "tel",
        "fax",
        "email",
        "www",
        "http",
        "https",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]

    deleted_blocklist = 0
    for term in BLOCKLIST:
        count = (
            session.query(Entity)
            .filter(Entity.text.ilike(term))
            .delete(synchronize_session=False)
        )
        deleted_blocklist += count

    logger.info(f"Deleted {deleted_blocklist} blocklisted entities.")

    # 3. Remove entities with specific labels that slipped through
    deleted_labels = (
        session.query(Entity)
        .filter(
            Entity.label.in_(
                ["CARDINAL", "ORDINAL", "PERCENT", "QUANTITY", "MONEY", "TIME"]
            )
        )
        .delete(synchronize_session=False)
    )
    logger.info(f"Deleted {deleted_labels} entities with noisy labels.")

    session.commit()
    logger.info("Entity pruning complete.")


if __name__ == "__main__":
    prune_entities()
