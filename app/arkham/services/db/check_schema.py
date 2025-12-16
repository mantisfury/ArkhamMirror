# Add project root to path for central config
from pathlib import Path
import sys
project_root = Path(__file__).resolve()
while project_root.name != 'ArkhamMirror' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import os
import sys
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

load_dotenv()


def check_schema():
    database_url = DATABASE_URL
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
