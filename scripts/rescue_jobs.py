import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from redis import Redis
from rq import Queue
from dotenv import load_dotenv
from backend.db.models import Document, MiniDoc, PageOCR

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()

redis_conn = Redis.from_url(os.getenv("REDIS_URL"))
q = Queue(connection=redis_conn)


def rescue_stuck_minidocs():
    # Find all documents that are processing
    docs = session.query(Document).filter(Document.status == "processing").all()

    for doc in docs:
        print(f"Checking Doc {doc.id}: {doc.title}...")

        # Find MiniDocs that are NOT parsed
        stuck_minidocs = (
            session.query(MiniDoc)
            .filter(MiniDoc.document_id == doc.id, MiniDoc.status != "parsed")
            .all()
        )

        if not stuck_minidocs:
            print("  - All MiniDocs parsed. Marking doc as complete.")
            doc.status = "complete"
            session.add(doc)
            continue

        for md in stuck_minidocs:
            # Check how many pages we have for this MiniDoc
            page_count = (
                session.query(PageOCR)
                .filter(
                    PageOCR.document_id == doc.id,
                    PageOCR.page_num >= md.page_start,
                    PageOCR.page_num <= md.page_end,
                )
                .count()
            )

            expected_pages = md.page_end - md.page_start + 1

            print(
                f"  - MiniDoc {md.id} (Pages {md.page_start}-{md.page_end}): Status '{md.status}', Found {page_count}/{expected_pages} pages."
            )

            # If we have pages (even if not all), let's force parse it to unblock
            if page_count > 0:
                print(f"    -> Enqueuing rescue parse job for MiniDoc {md.id}...")
                q.enqueue(
                    "backend.workers.parser_worker.parse_minidoc_job",
                    minidoc_db_id=md.id,
                )
            else:
                print(
                    "    -> No pages found. OCR likely failed completely for this batch."
                )

    session.commit()
    print("Rescue mission complete.")


if __name__ == "__main__":
    rescue_stuck_minidocs()
