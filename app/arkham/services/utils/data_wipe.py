import logging
import shutil
import time
import sys
from typing import Dict, List

from config.settings import DATA_SILO_PATH, DATABASE_URL

logger = logging.getLogger(__name__)


class WipeResult:
    """Result of a nuclear wipe operation."""

    def __init__(self):
        self.steps_completed: List[str] = []
        self.steps_failed: List[str] = []
        self.warnings: List[str] = []
        self.success: bool = False
        self.total_files_deleted: int = 0
        self.total_size_freed_mb: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "warnings": self.warnings,
            "total_files_deleted": self.total_files_deleted,
            "total_size_freed_mb": round(self.total_size_freed_mb, 2),
        }


def get_data_silo_stats() -> Dict:
    """
    Get statistics about what will be deleted.

    Returns:
        Dict with file counts and sizes for each DataSilo subdirectory.
    """
    stats = {
        "total_files": 0,
        "total_size_mb": 0.0,
        "directories": {},
    }

    if not DATA_SILO_PATH.exists():
        return stats

    for subdir in ["documents", "pages", "temp", "logs"]:
        subdir_path = DATA_SILO_PATH / subdir
        if subdir_path.exists():
            file_count = 0
            size_bytes = 0

            for item in subdir_path.rglob("*"):
                if item.is_file():
                    file_count += 1
                    try:
                        size_bytes += item.stat().st_size
                    except (OSError, PermissionError):
                        pass

            stats["directories"][subdir] = {
                "files": file_count,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
            }
            stats["total_files"] += file_count
            stats["total_size_mb"] += size_bytes / (1024 * 1024)

    stats["total_size_mb"] = round(stats["total_size_mb"], 2)
    return stats


def clear_database_tables() -> bool:
    """
    Clear all data from database tables without dropping them.

    This is faster than destroying Docker volumes and preserves the schema.
    """
    try:
        from sqlalchemy import create_engine, text, inspect

        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # List of all tables we want to clear.
        # We include everything to be thorough.
        tables_to_clear = [
            "contradiction_evidence",
            "contradictions",
            "ingestion_errors",
            "timeline_events",
            "anomalies",
            "date_mentions",
            "sensitive_data_matches",
            "extracted_tables",
            "entity_relationships",
            "entities",
            "page_ocr",
            "minidocs",
            "chunks",
            "documents",
            "clusters",
            "canonical_entities",
            "entity_analysis_cache",
            "entity_filter_rules",
            "entity_merge_audit",
            "projects",
        ]

        # Filter to only tables that actually exist
        target_tables = [t for t in existing_tables if t in tables_to_clear]

        with engine.connect() as conn:
            if not target_tables:
                logger.info("No tables to clear.")
                return True

            logger.info(f"Clearing tables: {', '.join(target_tables)}")

            # Construct a single TRUNCATE statement for all tables
            # This is more efficient and avoids transaction state issues
            tables_str = ", ".join([f'"{t}"' for t in target_tables])
            stmt = text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE;")

            conn.execute(stmt)
            conn.commit()

        logger.info("✓ Database tables cleared")
        return True

    except Exception as e:
        logger.error(f"Failed to clear database: {e}")
        return False


def clear_qdrant_collection() -> bool:
    """
    Delete and recreate the Qdrant collection with correct Hybrid Search schema.
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import VectorParams, Distance, SparseVectorParams
        from config.settings import QDRANT_URL
        from app.arkham.services.db.db_init import _get_embedding_dimension

        collection_name = "arkham_mirror_hybrid"
        client = QdrantClient(url=QDRANT_URL, timeout=10.0)

        # Delete collection if it exists
        try:
            client.delete_collection(collection_name)
            logger.debug(f"Deleted Qdrant collection: {collection_name}")
        except Exception:
            pass  # Collection might not exist

        # Get correct dimension (384 or 1024)
        vector_dimension = _get_embedding_dimension()

        # Recreate collection with NAMED VECTORS for hybrid search
        # matches app/arkham/services/db/db_init.py
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=vector_dimension,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(),
            },
        )

        logger.info(
            f"✓ Qdrant collection cleared and recreated (Hybrid, dim={vector_dimension})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to clear Qdrant: {e}")
        return False


def clear_redis_queue() -> bool:
    """
    Flush all Redis data (job queue).
    """
    try:
        import redis
        from config.settings import REDIS_URL

        # Parse Redis URL
        r = redis.from_url(REDIS_URL)
        r.flushall()

        logger.info("✓ Redis queue flushed")
        return True

    except Exception as e:
        logger.error(f"Failed to flush Redis: {e}")
        return False


def delete_data_silo_contents() -> tuple[int, float, List[str]]:
    """
    Delete all contents of DataSilo directory.

    Returns:
        Tuple of (files_deleted, size_freed_mb, warnings)
    """
    files_deleted = 0
    size_freed = 0
    warnings = []

    if not DATA_SILO_PATH.exists():
        return 0, 0.0, []

    for subdir in ["documents", "pages", "temp", "logs"]:
        subdir_path = DATA_SILO_PATH / subdir
        if not subdir_path.exists():
            continue

        for item in list(subdir_path.iterdir()):
            try:
                if item.is_dir():
                    # Count files before deletion
                    for f in item.rglob("*"):
                        if f.is_file():
                            files_deleted += 1
                            try:
                                size_freed += f.stat().st_size
                            except OSError:
                                pass
                    shutil.rmtree(item)
                else:
                    files_deleted += 1
                    try:
                        size_freed += item.stat().st_size
                    except OSError:
                        pass
                    item.unlink()
            except PermissionError as e:
                warnings.append(f"Could not delete {item.name}: file in use")
                logger.warning(f"Could not delete {item}: {e}")
            except Exception as e:
                warnings.append(f"Error deleting {item.name}: {str(e)}")
                logger.warning(f"Error deleting {item}: {e}")

    logger.info(
        f"✓ Deleted {files_deleted} files ({size_freed / (1024 * 1024):.1f} MB)"
    )
    return files_deleted, size_freed / (1024 * 1024), warnings


def nuclear_wipe(
    clear_files: bool = True,
    clear_database: bool = True,
    clear_vectors: bool = True,
    clear_queue: bool = True,
) -> WipeResult:
    """
    Permanently destroy all user data.

    WARNING: This action is IRREVERSIBLE!

    On Windows, some files may be locked if the app is running.
    The function will attempt to delete as much as possible and
    report any files that couldn't be deleted.

    Args:
        clear_files: Delete DataSilo contents
        clear_database: Clear database tables
        clear_vectors: Clear Qdrant collection
        clear_queue: Flush Redis queue

    Returns:
        WipeResult with details of what was deleted
    """
    result = WipeResult()

    logger.warning("⚠️ NUCLEAR WIPE INITIATED - This will destroy all data!")

    # Step 1: Flush Redis queue (stops any pending jobs)
    if clear_queue:
        if clear_redis_queue():
            result.steps_completed.append("Redis queue flushed")
        else:
            result.steps_failed.append("Redis queue flush failed")

    # Step 2: Shutdown logging to release file handles
    # (We'll reinitialize after)
    logging.shutdown()
    time.sleep(0.5)  # Brief pause for handles to release

    # Step 3: Delete DataSilo contents
    if clear_files:
        files_deleted, size_freed, warnings = delete_data_silo_contents()
        result.total_files_deleted = files_deleted
        result.total_size_freed_mb = size_freed
        result.warnings.extend(warnings)

        if files_deleted > 0 or not warnings:
            result.steps_completed.append(f"Deleted {files_deleted} files")
        if warnings:
            result.steps_failed.append(
                f"Some files could not be deleted ({len(warnings)} warnings)"
            )

    # Step 4: Clear database tables
    if clear_database:
        if clear_database_tables():
            result.steps_completed.append("Database cleared")
        else:
            result.steps_failed.append("Database clear failed")

    # Step 5: Clear Qdrant collection
    if clear_vectors:
        if clear_qdrant_collection():
            result.steps_completed.append("Vector store cleared")
        else:
            result.steps_failed.append("Vector store clear failed")

    # Reinitialize logging
    logging.basicConfig(level=logging.INFO)

    # Recreate DataSilo directories
    for subdir in ["documents", "pages", "temp", "logs"]:
        (DATA_SILO_PATH / subdir).mkdir(parents=True, exist_ok=True)

    # Determine overall success
    result.success = len(result.steps_failed) == 0

    if result.success:
        logger.info("✓ Nuclear wipe complete - all data destroyed")
    else:
        logger.warning(f"⚠️ Nuclear wipe completed with issues: {result.steps_failed}")

    return result


# Allow running as standalone script for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Nuclear Wipe - Destroy all ArkhamMirror data"
    )
    parser.add_argument(
        "--confirm", action="store_true", help="Confirm you want to delete all data"
    )
    parser.add_argument(
        "--stats-only", action="store_true", help="Show stats without deleting"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.stats_only:
        stats = get_data_silo_stats()
        print("\n📊 DataSilo Statistics:")
        print(f"   Total files: {stats['total_files']}")
        print(f"   Total size: {stats['total_size_mb']:.2f} MB")
        print("\n   By directory:")
        for name, info in stats.get("directories", {}).items():
            print(f"   - {name}: {info['files']} files ({info['size_mb']:.2f} MB)")
    elif args.confirm:
        print("\n⚠️  WARNING: This will permanently delete ALL data!")
        print("    Press Ctrl+C within 5 seconds to cancel...")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n❌ Cancelled.")
            sys.exit(0)

        result = nuclear_wipe()
        print(f"\n{'✓' if result.success else '⚠️'} Wipe complete:")
        print(f"   Files deleted: {result.total_files_deleted}")
        print(f"   Space freed: {result.total_size_freed_mb:.2f} MB")
        if result.warnings:
            print(f"   Warnings: {len(result.warnings)}")
            for w in result.warnings[:5]:
                print(f"      - {w}")
    else:
        print("Usage: python data_wipe.py --confirm")
        print("       python data_wipe.py --stats-only")
