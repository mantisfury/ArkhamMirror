import os
import logging
import fitz  # PyMuPDF
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from rq import Queue
from redis import Redis
from dotenv import load_dotenv

from backend.db.models import Document, MiniDoc
from backend.metadata_service import extract_pdf_metadata

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup DB & Redis
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
redis_conn = Redis.from_url(os.getenv("REDIS_URL"))
q = Queue(connection=redis_conn)

# Config
RAW_PAGES_DIR = "./data/raw_pdf_pages"
MINIDOC_SIZE = 20
DPI = 200


def split_pdf_job(doc_id, file_path, ocr_mode="paddle"):
    """
    Splits a PDF into page images and creates MiniDoc records.
    """
    session = Session()
    try:
        logger.info(f"Starting split job for Document ID: {doc_id} (Mode: {ocr_mode})")

        doc_record = session.query(Document).get(doc_id)
        if not doc_record:
            logger.error(f"Document {doc_id} not found in DB.")
            return

        doc_record.status = "processing"
        session.commit()

        # Open PDF
        try:
            pdf = fitz.open(file_path)
        except Exception as e:
            logger.error(f"Failed to open PDF {file_path}: {e}")
            doc_record.status = "failed"
            session.commit()
            return

        num_pages = len(pdf)
        doc_record.num_pages = num_pages

        # Extract PDF metadata (forensic information)
        try:
            logger.info(f"Extracting PDF metadata for {file_path}")
            metadata = extract_pdf_metadata(file_path)

            if "error" not in metadata:
                # Update document record with metadata
                doc_record.pdf_author = metadata.get("pdf_author")
                doc_record.pdf_creator = metadata.get("pdf_creator")
                doc_record.pdf_producer = metadata.get("pdf_producer")
                doc_record.pdf_subject = metadata.get("pdf_subject")
                doc_record.pdf_keywords = metadata.get("pdf_keywords")
                doc_record.pdf_creation_date = metadata.get("pdf_creation_date")
                doc_record.pdf_modification_date = metadata.get("pdf_modification_date")
                doc_record.pdf_version = metadata.get("pdf_version")
                doc_record.is_encrypted = 1 if metadata.get("is_encrypted") else 0
                doc_record.file_size_bytes = metadata.get("file_size_bytes")

                logger.info(f"Metadata extracted: Author={metadata.get('pdf_author')}, "
                          f"Creator={metadata.get('pdf_creator')}")
            else:
                logger.warning(f"Could not extract PDF metadata: {metadata['error']}")

        except Exception as e:
            logger.warning(f"PDF metadata extraction failed: {str(e)}")
            # Don't fail the entire job if metadata extraction fails

        # Create output directory for pages
        # Use file_hash as folder name for stability
        doc_hash = doc_record.file_hash
        pages_dir = os.path.join(RAW_PAGES_DIR, doc_hash)
        os.makedirs(pages_dir, exist_ok=True)

        # 1. Extract Images & Enqueue OCR Jobs
        for page_num in range(num_pages):
            page = pdf.load_page(page_num)
            pix = page.get_pixmap(dpi=DPI)
            image_path = os.path.join(pages_dir, f"page_{page_num + 1:04d}.png")
            pix.save(image_path)

            # Enqueue OCR job for this page
            # We pass doc_id (int), doc_hash (str), page_num (1-based), and image_path
            q.enqueue(
                "backend.workers.ocr_worker.process_page_job",
                doc_id=doc_id,
                doc_hash=doc_hash,
                page_num=page_num + 1,
                image_path=image_path,
                ocr_mode=ocr_mode,
            )

        # 2. Create MiniDoc Records
        # Fixed size splitting
        for i in range(0, num_pages, MINIDOC_SIZE):
            start_page = i + 1
            end_page = min(i + MINIDOC_SIZE, num_pages)
            part_num = (i // MINIDOC_SIZE) + 1
            minidoc_id = f"{doc_hash}__part_{part_num:03d}"

            # Check if exists
            existing = session.query(MiniDoc).filter_by(minidoc_id=minidoc_id).first()
            if not existing:
                minidoc = MiniDoc(
                    document_id=doc_id,
                    minidoc_id=minidoc_id,
                    page_start=start_page,
                    page_end=end_page,
                    status="pending_ocr",
                )
                session.add(minidoc)

        session.commit()
        logger.info(
            f"Split job complete for {doc_id}. Created {num_pages} page images."
        )

    except Exception as e:
        logger.error(f"Split job CRITICAL FAILURE for doc {doc_id}: {e}", exc_info=True)
        try:
            doc_record.status = "failed"
            session.commit()
        except Exception:
            pass
        session.rollback()
    finally:
        session.close()
