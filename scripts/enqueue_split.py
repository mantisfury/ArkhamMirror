import os
from redis import Redis
from rq import Queue
from dotenv import load_dotenv
from backend.db.models import Document
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()

redis_conn = Redis.from_url(os.getenv("REDIS_URL"))
q = Queue(connection=redis_conn)

# Find Doc 1
doc = session.query(Document).get(1)

if doc:
    print(f"Enqueuing Split Job for Doc {doc.id} ({doc.title})...")
    q.enqueue(
        "backend.workers.splitter_worker.split_pdf_job",
        doc_id=doc.id,
        file_path=doc.path,
        ocr_mode="qwen",  # Assuming user wants Qwen since they selected it
    )
else:
    print("Doc 1 not found")

session.close()
print("Done.")
