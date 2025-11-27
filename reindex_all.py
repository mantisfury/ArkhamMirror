import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from backend.db.models import Chunk
from backend.workers.embed_worker import embed_chunk_job, ensure_collection

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reindex_all():
    # Ensure collection exists
    ensure_collection()

    engine = create_engine(os.getenv("DATABASE_URL"))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        chunks = session.query(Chunk).all()
        logger.info(f"Found {len(chunks)} chunks to re-index.")

        for i, chunk in enumerate(chunks):
            try:
                embed_chunk_job(chunk.id)
                if i % 10 == 0:
                    print(f"Processed {i}/{len(chunks)} chunks...")
            except Exception as e:
                logger.error(f"Failed to re-index chunk {chunk.id}: {e}")

        print("Re-indexing complete!")

    finally:
        session.close()


if __name__ == "__main__":
    reindex_all()
