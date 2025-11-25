import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from backend.db.models import Document, MiniDoc

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()

# Find all documents that are 'processing' but have all MiniDocs 'parsed'
docs = session.query(Document).filter(Document.status == "processing").all()

for doc in docs:
    pending = (
        session.query(MiniDoc)
        .filter(MiniDoc.document_id == doc.id, MiniDoc.status != "parsed")
        .count()
    )

    if pending == 0:
        print(f"Fixing status for Doc {doc.id} ({doc.title})...")
        doc.status = "complete"
        session.add(doc)

session.commit()
session.close()
print("Done.")
