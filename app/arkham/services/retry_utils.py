import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from redis import Redis
from rq import Queue

from config.settings import DATABASE_URL, REDIS_URL, PAGES_DIR

from app.arkham.services.db.models import Document, PageOCR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
redis_conn = Redis.from_url(REDIS_URL)
q = Queue(connection=redis_conn)

# Now using DataSilo paths from central config
RAW_PAGES_DIR = str(PAGES_DIR)  # Convert Path to string for os.path.join compatibility


def retry_missing_pages(doc_id, ocr_mode="paddle"):
    """
    Identifies missing or failed pages for a document and re-enqueues them.
    """
    session = Session()
    try:
        doc = session.query(Document).get(doc_id)
        if not doc:
            return "Document not found."

        if doc.num_pages == 0:
            return "Document has 0 pages (split might have failed)."

        # Find existing pages
        existing_pages = (
            session.query(PageOCR).filter(PageOCR.document_id == doc_id).all()
        )
        existing_page_nums = {p.page_num for p in existing_pages}

        # Identify failed pages (those with error text)
        failed_page_nums = {
            p.page_num for p in existing_pages if "[OCR FAILED]" in (p.text or "")
        }

        missing_count = 0
        failed_count = 0

        for page_num in range(1, doc.num_pages + 1):
            should_retry = False

            # Case 1: Missing completely
            if page_num not in existing_page_nums:
                should_retry = True
                missing_count += 1

            # Case 2: Explicit failure record
            elif page_num in failed_page_nums:
                should_retry = True
                failed_count += 1

            if should_retry:
                # Reconstruct image path
                # Pattern from splitter_worker: os.path.join(pages_dir, f"page_{page_num + 1:04d}.png")
                # Note: splitter uses 1-based indexing for filename too.
                image_path = os.path.join(
                    RAW_PAGES_DIR, doc.file_hash, f"page_{page_num:04d}.png"
                )

                if os.path.exists(image_path):
                    logger.info(f"Retrying Doc {doc_id} Page {page_num}...")
                    q.enqueue(
                        "app.arkham.services.workers.ocr_worker.process_page_job",
                        doc_id=doc.id,
                        doc_hash=doc.file_hash,
                        page_num=page_num,
                        image_path=image_path,
                        ocr_mode=ocr_mode,
                    )
                else:
                    logger.warning(
                        f"Image file missing for Doc {doc_id} Page {page_num}: {image_path}"
                    )

        return f"Enqueued {missing_count} missing and {failed_count} failed pages."

    except Exception as e:
        logger.error(f"Retry failed: {e}")
        return f"Error: {e}"
    finally:
        session.close()
