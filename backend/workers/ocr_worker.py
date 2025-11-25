import os
import json
import logging
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from rq import Queue
from redis import Redis
from dotenv import load_dotenv

from backend.db.models import PageOCR, MiniDoc
from backend.llm_service import transcribe_image

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup DB & Redis
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
redis_conn = Redis.from_url(os.getenv("REDIS_URL"))
q = Queue(connection=redis_conn)

# Config
OCR_PAGES_DIR = "./data/ocr_pages"

# Lazy-load PaddleOCR to save VRAM if using LLM mode
_paddle_engine = None


def get_paddle_engine():
    global _paddle_engine
    if _paddle_engine is None:
        logger.info("Initializing PaddleOCR Engine...")
        _paddle_engine = PaddleOCR(use_angle_cls=True, lang="en")
    return _paddle_engine


def process_page_job(doc_id, doc_hash, page_num, image_path, ocr_mode="paddle"):
    """
    Runs OCR on a single page image and saves the result.
    ocr_mode: 'paddle' or 'qwen'
    """
    session = Session()
    try:
        logger.info(f"OCR Job: Doc {doc_id} Page {page_num} Mode: {ocr_mode}")

        page_text = ""
        ocr_meta = []

        if ocr_mode == "qwen":
            # --- Qwen-VL / LLM Strategy ---
            try:
                logger.info(f"Transcribing {image_path} with Qwen-VL...")
                text = transcribe_image(image_path)
                if text:
                    page_text = text
                    # No bounding boxes for LLM mode
                    ocr_meta = []
                else:
                    logger.warning(f"Qwen-VL returned empty text for {image_path}")
            except Exception as e:
                logger.error(f"LLM OCR failed: {e}")
                return

        else:
            # --- PaddleOCR Strategy ---
            try:
                ocr_engine = get_paddle_engine()
                image = Image.open(image_path)
                img_np = np.array(image)
                result = ocr_engine.ocr(img_np)
            except Exception as e:
                import traceback

                logger.error(
                    f"PaddleOCR Engine failed for {image_path}: {e}\n{traceback.format_exc()}"
                )
                return

            # Extract text and metadata
            if result and result[0]:
                # Handle PaddleX / New PaddleOCR structure
                ocr_res = result[0]

                # Check if it has the new keys
                if hasattr(ocr_res, "keys") and "rec_texts" in ocr_res:
                    texts = ocr_res["rec_texts"]
                    scores = ocr_res["rec_scores"]
                    boxes = ocr_res["rec_polys"]  # These are numpy arrays

                    for box, text, score in zip(boxes, texts, scores):
                        # Convert box to list for JSON serialization
                        box_list = box.tolist() if hasattr(box, "tolist") else box
                        page_text += text + "\n"
                        ocr_meta.append(
                            {"box": box_list, "text": text, "conf": float(score)}
                        )

                # Fallback for old list-of-lists structure
                elif isinstance(ocr_res, list):
                    for line in ocr_res:
                        # line structure: [[x1,y1,x2,y2], (text, conf)]
                        if len(line) >= 2:
                            box = line[0]
                            text, conf = line[1]
                            page_text += text + "\n"
                            ocr_meta.append({"box": box, "text": text, "conf": conf})

        # 2. Save JSON Output
        output_dir = os.path.join(OCR_PAGES_DIR, doc_hash)
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, f"page_{page_num:04d}.json")

        output_data = {
            "doc_id": doc_id,
            "page_num": page_num,
            "text": page_text,
            "meta": ocr_meta,
            "mode": ocr_mode,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        # 3. Upsert PageOCR Record
        existing = (
            session.query(PageOCR)
            .filter_by(document_id=doc_id, page_num=page_num)
            .first()
        )
        if existing:
            existing.text = page_text
            existing.ocr_meta = json.dumps(ocr_meta)
        else:
            page_record = PageOCR(
                document_id=doc_id,
                page_num=page_num,
                text=page_text,
                ocr_meta=json.dumps(ocr_meta),
                checksum="TODO",
            )
            session.add(page_record)

        session.commit()

        # 4. Check MiniDoc Completion
        minidoc = (
            session.query(MiniDoc)
            .filter(
                MiniDoc.document_id == doc_id,
                MiniDoc.page_start <= page_num,
                MiniDoc.page_end >= page_num,
            )
            .first()
        )

        if minidoc:
            # Check if all pages in this minidoc are done
            total_pages_in_minidoc = minidoc.page_end - minidoc.page_start + 1
            completed_pages = (
                session.query(PageOCR)
                .filter(
                    PageOCR.document_id == doc_id,
                    PageOCR.page_num >= minidoc.page_start,
                    PageOCR.page_num <= minidoc.page_end,
                )
                .count()
            )

            if completed_pages >= total_pages_in_minidoc:
                logger.info(f"MiniDoc {minidoc.minidoc_id} complete! Enqueuing parser.")
                minidoc.status = "ocr_done"
                session.commit()

                # Enqueue Parser Job
                q.enqueue(
                    "backend.workers.parser_worker.parse_minidoc_job",
                    minidoc_db_id=minidoc.id,
                )

    except Exception as e:
        logger.error(f"OCR Job failed: {e}")
        session.rollback()

        # --- FAILURE HANDLING ---
        # If we fail, we MUST create a placeholder record so the pipeline doesn't hang.
        try:
            # Re-open session since we rolled back
            session = Session()

            error_text = f"[OCR FAILED] Error processing page {page_num}: {str(e)}"

            existing = (
                session.query(PageOCR)
                .filter_by(document_id=doc_id, page_num=page_num)
                .first()
            )
            if existing:
                existing.text = error_text
                existing.ocr_meta = json.dumps({"error": str(e)})
            else:
                page_record = PageOCR(
                    document_id=doc_id,
                    page_num=page_num,
                    text=error_text,
                    ocr_meta=json.dumps({"error": str(e)}),
                    checksum="ERROR",
                )
                session.add(page_record)

            session.commit()

            # Trigger completion check again (copy-paste logic, or refactor)
            # For simplicity, let's just do the check here too
            minidoc = (
                session.query(MiniDoc)
                .filter(
                    MiniDoc.document_id == doc_id,
                    MiniDoc.page_start <= page_num,
                    MiniDoc.page_end >= page_num,
                )
                .first()
            )

            if minidoc:
                total_pages_in_minidoc = minidoc.page_end - minidoc.page_start + 1
                completed_pages = (
                    session.query(PageOCR)
                    .filter(
                        PageOCR.document_id == doc_id,
                        PageOCR.page_num >= minidoc.page_start,
                        PageOCR.page_num <= minidoc.page_end,
                    )
                    .count()
                )

                if completed_pages >= total_pages_in_minidoc:
                    logger.info(
                        f"MiniDoc {minidoc.minidoc_id} complete (with errors)! Enqueuing parser."
                    )
                    minidoc.status = "ocr_done"
                    session.commit()

                    q.enqueue(
                        "backend.workers.parser_worker.parse_minidoc_job",
                        minidoc_db_id=minidoc.id,
                    )

        except Exception as inner_e:
            logger.critical(
                f"CRITICAL: Failed to save error state for page {page_num}: {inner_e}"
            )

    finally:
        session.close()
