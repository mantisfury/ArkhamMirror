import os
from backend.db.models import Base
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
print(f"Connecting to {db_url}...")
engine = create_engine(db_url)

print("Dropping all tables...")
Base.metadata.drop_all(engine)

print("Recreating all tables...")
Base.metadata.create_all(engine)

print("Database wiped and recreated successfully.")
