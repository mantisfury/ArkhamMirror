import os
import sys
from rq import Queue
from redis import Redis
from dotenv import load_dotenv
from backend.db.models import Document

load_dotenv()

redis_conn = Redis.from_url(os.getenv("REDIS_URL"))
q = Queue(connection=redis_conn)

doc_id = 2
doc_hash = "1db59435fb87e9676eecb50044df88cf55fc921ba4bce7a87d76b30d7836fde9"
missing_pages = [4, 7, 8]

print(f"Requeuing missing pages {missing_pages} for Doc {doc_id}...")

for page_num in missing_pages:
    image_path = f"./data/raw_pdf_pages/{doc_hash}/page_{page_num:04d}.png"
    if not os.path.exists(image_path):
        print(f"Warning: Image not found: {image_path}")
        continue

    print(f"Enqueuing Page {page_num}...")
    q.enqueue(
        "backend.workers.ocr_worker.process_page_job",
        doc_id=doc_id,
        doc_hash=doc_hash,
        page_num=page_num,
        image_path=image_path,
    )

print("Done.")
