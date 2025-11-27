import sys
import os
import argparse
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.config import get_db_session
from backend.geocoding_service import get_geocoder


def main():
    parser = argparse.ArgumentParser(description="Geocode entities in the database.")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of entities to geocode per run",
    )
    args = parser.parse_args()

    print(f"🚀 Starting geocoding process (limit={args.limit})...")

    db: Session = get_db_session()
    try:
        geocoder = get_geocoder()
        geocoder.batch_process_entities(db, limit=args.limit)
    except Exception as e:
        print(f"❌ Error during geocoding: {e}")
    finally:
        db.close()
        print("🏁 Geocoding process finished.")


if __name__ == "__main__":
    main()
