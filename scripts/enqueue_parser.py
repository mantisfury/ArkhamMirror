import os
from redis import Redis
from rq import Queue
from dotenv import load_dotenv
from backend.db.models import MiniDoc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()

redis_conn = Redis.from_url(os.getenv("REDIS_URL"))
q = Queue(connection=redis_conn)

# Find the MiniDoc for Doc 3 (Latest)
minidoc = session.query(MiniDoc).filter(MiniDoc.document_id == 3).first()

if minidoc:
    print(f"Enqueuing Parser Job for MiniDoc {minidoc.id} ({minidoc.minidoc_id})...")
    q.enqueue(
        "backend.workers.parser_worker.parse_minidoc_job",
        minidoc_db_id=minidoc.id,
    )
else:
    print("MiniDoc not found for Doc 2")

session.close()
print("Done.")
