import os
import glob
import logging
import shutil
from datetime import datetime
from dotenv import load_dotenv
from rq import Queue
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Document
from backend.utils.hash_utils import get_file_hash
import argparse
import watchgod

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_conn = Redis.from_url(os.getenv("REDIS_URL"))
q = Queue(connection=redis_conn)
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)


def process_file(file_path, project_id=None, ocr_mode="paddle"):
    session = Session()
    try:
        logger.info(
            f"Processing: {file_path} (Project ID: {project_id}, Mode: {ocr_mode})"
        )

        # 1. Deduplication Check
        file_hash = get_file_hash(file_path)
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

        # 2. Move to Permanent Storage
        storage_dir = os.path.abspath(os.path.join("data", "documents"))
        os.makedirs(storage_dir, exist_ok=True)

        new_filename = f"{file_hash}_{os.path.basename(file_path)}"
        permanent_path = os.path.join(storage_dir, new_filename)

        shutil.move(file_path, permanent_path)
        logger.info(f"Moved file to {permanent_path}")

        # 2.5 Conversion (if needed)
        final_processing_path = permanent_path
        ext = os.path.splitext(permanent_path)[1].lower()

        if ext != ".pdf":
            try:
                from backend.converters import convert_to_pdf

                logger.info(f"Converting {ext} to PDF...")
                converted_pdf_path = convert_to_pdf(permanent_path)
                final_processing_path = converted_pdf_path
                logger.info(f"Conversion successful: {final_processing_path}")
            except Exception as conv_err:
                logger.error(f"Conversion failed: {conv_err}")
                # We can't process it if we can't convert it (for now)
                raise conv_err

        # 3. Create Document Record
        # We store the ORIGINAL file path in 'path', but we might want to store the converted one too?
        # For now, 'path' is the source of truth. The splitter will need to know if it should use a different file.
        # Actually, let's update 'path' to be the PDF if we converted it,
        # OR keep 'path' as original and add a 'processed_path' column?
        # Simpler for v0.1: If converted, treat the PDF as the document to process.

        doc = Document(
            title=os.path.basename(file_path),
            path=permanent_path,  # Original file
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
        # Pass the PDF path (converted or original) to the splitter
        q.enqueue(
            "backend.workers.splitter_worker.split_pdf_job",
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


def watch_folder(folder_path, project_id=None):
    for changes in watchgod.watch(folder_path):
        for change_type, file_path in changes:
            if "processed" in file_path or "failed" in file_path:
                continue
            if change_type == watchgod.Status.added and os.path.isfile(file_path):
                q.enqueue(
                    process_file, file_path, project_id, "paddle"
                )  # Default to paddle for watcher for now


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument(
        "--project_id",
        type=int,
        default=None,
        help="Project ID to associate with ingested files",
    )
    parser.add_argument(
        "--ocr_mode",
        type=str,
        default="paddle",
        choices=["paddle", "qwen"],
        help="OCR Mode: paddle (fast) or qwen (smart)",
    )
    args = parser.parse_args()

    if args.watch:
        watch_folder("./temp", args.project_id)
    else:
        for f in glob.glob("./temp/*.*"):
            process_file(f, args.project_id, args.ocr_mode)
