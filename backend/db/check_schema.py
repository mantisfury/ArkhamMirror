import os
import sys
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

load_dotenv()


def check_schema():
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url)
    inspector = inspect(engine)

    columns = inspector.get_columns("documents")
    col_names = [c["name"] for c in columns]
    print(f"Columns in 'documents': {col_names}")

    if "status" in col_names and "num_pages" in col_names:
        print("SUCCESS: Schema is correct.")
    else:
        print("FAILURE: Schema is missing columns.")


if __name__ == "__main__":
    check_schema()
