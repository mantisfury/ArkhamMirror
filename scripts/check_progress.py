import os
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from backend.db.models import Document, MiniDoc, PageOCR, Chunk
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()

try:
    print("--- System State ---")

    # Documents
    docs = session.query(Document).all()
    print(f"Documents: {len(docs)}")
    for d in docs:
        print(
            f"  - ID: {d.id}, Title: {d.title}, Status: {d.status}, Pages: {d.num_pages}"
        )

    # MiniDocs
    minidocs = session.query(MiniDoc).all()
    print(f"MiniDocs: {len(minidocs)}")
    for m in minidocs:
        print(f"  - ID: {m.minidoc_id}, Status: {m.status}")

    # PageOCR
    page_ocr_count = session.query(PageOCR).count()
    print(f"PageOCR Records: {page_ocr_count}")

    # Chunks
    chunks_count = session.query(Chunk).count()
    print(f"Chunks: {chunks_count}")

except Exception as e:
    print(f"Error: {e}")
finally:
    session.close()
