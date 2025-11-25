import os
from backend.db.models import Document
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()

doc = session.query(Document).get(2)
if doc and doc.status != "complete":
    print(f"Fixing status for Doc {doc.id}...")
    doc.status = "complete"
    session.commit()

session.close()
print("Done.")
