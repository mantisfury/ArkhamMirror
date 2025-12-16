"""
Ingest Worker - Entry point for document ingestion pipeline.

This worker handles:
1. Deduplication check via file hash
2. Moving files to permanent storage
3. Converting non-PDF files to PDF
4. Creating document records
5. Enqueuing splitter jobs for processing
"""

import os
import sys # Keep sys for shutil
import shutil
import logging
from datetime import datetime
from pathlib import Path

from rq import Queue
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import DATABASE_URL, REDIS_URL, DOCUMENTS_DIR

from app.arkham.services.db.models import Document
from app.arkham.services.utils.hash_utils import get_file_hash
from app.arkham.services.utils.security_utils import sanitize_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup DB & Redis from central config
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
redis_conn = Redis.from_url(REDIS_URL)
q = Queue(connection=redis_conn)


def process_file(file_path, project_id=None, ocr_mode="paddle"):
    """
    Process a single uploaded file through the ingestion pipeline.

    Args:
        file_path: Path to the uploaded file
        project_id: Optional project ID to associate with the document
        ocr_mode: OCR mode to use - "paddle" (fast) or "qwen" (smart)
    """
    logger.info("=" * 80)
    logger.info("INGEST_WORKER: process_file() called")
    logger.info(f"  file_path: {file_path}")
    logger.info(f"  project_id: {project_id}")
    logger.info(f"  ocr_mode: {ocr_mode}")
    logger.info(f"  File exists: {os.path.exists(file_path)}")
    logger.info("=" * 80)

    session = Session()
    try:
        logger.info(
            f"Processing: {file_path} (Project ID: {project_id}, Mode: {ocr_mode})"
        )

        # 1. Deduplication Check
        logger.info("Step 1: Computing file hash for deduplication...")
        file_hash = get_file_hash(file_path)
        logger.info(f"File hash: {file_hash}")

        existing = session.query(Document).filter_by(file_hash=file_hash).first()
        if existing:
            logger.warning(f"Duplicate file skipped: {os.path.basename(file_path)}")
            # Move to processed anyway so it doesn't get picked up again
            processed_dir = os.path.join(os.path.dirname(file_path), "processed")
            os.makedirs(processed_dir, exist_ok=True)
            shutil.move(
                file_path,
                os.path.join(processed_dir, os.path.basename(file_path)),
            )
            return

        # 2. Move to Permanent Storage (DataSilo/documents/)
        storage_dir = str(DOCUMENTS_DIR)
        os.makedirs(storage_dir, exist_ok=True)

        new_filename = f"{file_hash}_{sanitize_filename(os.path.basename(file_path))}"
        permanent_path = os.path.join(storage_dir, new_filename)

        shutil.move(file_path, permanent_path)
        logger.info(f"Moved file to {permanent_path}")

        # 2.5 Conversion (if needed)
        final_processing_path = permanent_path
        ext = os.path.splitext(permanent_path)[1].lower()

        if ext != ".pdf":
            try:
                from app.arkham.services.converters import convert_to_pdf

                logger.info(f"Converting {ext} to PDF...")
                converted_pdf_path = convert_to_pdf(permanent_path)
                final_processing_path = converted_pdf_path
                logger.info(f"Conversion successful: {final_processing_path}")
            except Exception as conv_err:
                logger.error(f"Conversion failed: {conv_err}")
                raise conv_err

        # 3. Create Document Record
        doc = Document(
            title=os.path.basename(file_path),
            path=permanent_path,
            source_path=os.path.dirname(file_path),
            file_hash=file_hash,
            doc_type=ext,
            project_id=project_id,
            status="uploaded",
            num_pages=0,
        )
        session.add(doc)
        session.commit()

        # 4. Enqueue Splitter Job
        q.enqueue(
            "app.arkham.services.workers.splitter_worker.split_pdf_job",
            doc_id=doc.id,
            file_path=final_processing_path,
            ocr_mode=ocr_mode,
        )

        logger.info(f"Enqueued split job for {final_processing_path}")

    except Exception as e:
        session.rollback()
        logger.error(f"FAILED {file_path}: {e}")
        # Dead Letter Queue
        failed_dir = os.path.join(os.path.dirname(file_path), "failed")
        os.makedirs(failed_dir, exist_ok=True)
        shutil.move(file_path, os.path.join(failed_dir, os.path.basename(file_path)))
        with open(os.path.join(failed_dir, "errors.log"), "a") as log:
            log.write(f"{datetime.now()} - {file_path} - {e}\n")
    finally:
        session.close()
