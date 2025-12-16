import os
import shutil
import sys
from pathlib import Path
from typing import List, Dict
import logging

from config.settings import DATABASE_URL, QDRANT_URL, REDIS_URL, DOCUMENTS_DIR, PAGES_DIR

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from rq import Queue
from redis import Redis
from qdrant_client import QdrantClient

from app.arkham.services.db.models import (
    Document,
    MiniDoc,
    PageOCR,
    Chunk,
    Entity,
    EntityRelationship,
    Anomaly,
    TimelineEvent,
    DateMention,
    SensitiveDataMatch,
    ExtractedTable,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QDRANT_COLLECTION = "arkham_mirror_hybrid"

# File paths now come from central config (DataSilo)
# DOCUMENTS_DIR = DataSilo/documents (imported from config)
# PAGES_DIR = DataSilo/pages (imported from config, was RAW_PAGES_DIR)
RAW_PAGES_DIR = PAGES_DIR  # Alias for backward compatibility


class DocumentManagementService:
    """Service for managing document lifecycle with proper cleanup."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        self.qdrant_client = QdrantClient(url=QDRANT_URL)
        self.redis_conn = Redis.from_url(REDIS_URL)
        self.queue = Queue(connection=self.redis_conn)

    def delete_document(self, doc_id: int) -> Dict[str, any]:
        """
        Delete a document and all associated data.

        Cleanup includes:
        - Database: Document + all child tables (CASCADE)
        - Files: Original file, converted PDF, page images
        - Vectors: Qdrant embeddings
        - Queue: Related RQ jobs (if any)

        Args:
            doc_id: Document ID to delete

        Returns:
            Dict with deletion results and counts
        """
        session = self.Session()
        results = {
            "success": False,
            "doc_id": doc_id,
            "files_deleted": [],
            "vectors_deleted": 0,
            "database_entries": 0,
            "errors": [],
        }

        try:
            # Get document info before deletion
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                results["errors"].append(f"Document {doc_id} not found")
                return results

            doc_hash = doc.file_hash
            file_path = doc.path

            # 1. Delete from Qdrant (vector store)
            try:
                # Delete all chunks associated with this document using correct filter syntax
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                # Check if collection exists first
                try:
                    collections = self.qdrant_client.get_collections()
                    collection_exists = any(
                        c.name == QDRANT_COLLECTION for c in collections.collections
                    )
                except Exception as check_error:
                    logger.warning(f"Could not check Qdrant collections: {check_error}")
                    collection_exists = False

                if not collection_exists:
                    logger.info(
                        f"Qdrant collection '{QDRANT_COLLECTION}' doesn't exist, skipping vector deletion"
                    )
                    results["vectors_deleted"] = 0
                else:
                    # Attempt deletion with retry logic for transient errors
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            self.qdrant_client.delete(
                                collection_name=QDRANT_COLLECTION,
                                points_selector=Filter(
                                    must=[
                                        FieldCondition(
                                            key="doc_id", match=MatchValue(value=doc_id)
                                        )
                                    ]
                                ),
                            )
                            results["vectors_deleted"] = 1
                            logger.info(f"Deleted Qdrant vectors for doc {doc_id}")
                            break  # Success, exit retry loop
                        except Exception as retry_error:
                            if attempt < max_retries - 1:
                                logger.warning(
                                    f"Qdrant deletion attempt {attempt + 1} failed, retrying: {retry_error}"
                                )
                                import time

                                time.sleep(0.5)  # Brief delay before retry
                            else:
                                raise  # Final attempt failed, propagate error

            except Exception as e:
                # Log but don't fail the entire deletion if Qdrant fails
                # The database deletion is more critical
                results["errors"].append(f"Qdrant deletion failed: {str(e)}")
                logger.error(f"Qdrant deletion failed for doc {doc_id}: {e}")
                # Continue with file and database deletion

            # 2. Delete files
            files_to_delete = []

            # Original file
            if file_path and Path(file_path).exists():
                files_to_delete.append(Path(file_path))

            # Converted PDF
            if file_path:
                converted_pdf = (
                    Path(file_path).parent / f"{Path(file_path).stem}.converted.pdf"
                )
                if converted_pdf.exists():
                    files_to_delete.append(converted_pdf)

            # Page images (hash-based directory)
            if doc_hash:
                page_images_dir = RAW_PAGES_DIR / doc_hash
                if page_images_dir.exists():
                    for page_img in page_images_dir.glob("*.png"):
                        files_to_delete.append(page_img)
                    files_to_delete.append(page_images_dir)  # Directory itself

            # Delete files
            for file_path_obj in files_to_delete:
                try:
                    if file_path_obj.is_file():
                        file_path_obj.unlink()
                        results["files_deleted"].append(str(file_path_obj))
                        logger.info(f"Deleted file: {file_path_obj}")
                    elif file_path_obj.is_dir():
                        shutil.rmtree(file_path_obj)
                        results["files_deleted"].append(str(file_path_obj))
                        logger.info(f"Deleted directory: {file_path_obj}")
                except Exception as e:
                    results["errors"].append(
                        f"File deletion failed ({file_path_obj.name}): {e}"
                    )
                    logger.error(f"File deletion failed for {file_path_obj}: {e}")

            # 3. Delete from database - explicitly delete child records first to avoid foreign key violations
            try:
                # Delete all child records in proper order
                # CRITICAL: Order matters - delete children before parents to avoid FK violations

                # Import ContradictionEvidence if it exists
                try:
                    from app.arkham.services.db.models import ContradictionEvidence

                    contradiction_evidence_deleted = (
                        session.query(ContradictionEvidence)
                        .filter(ContradictionEvidence.document_id == doc_id)
                        .delete()
                    )
                except (ImportError, AttributeError):
                    contradiction_evidence_deleted = 0

                # Delete items that reference chunks FIRST (before deleting chunks themselves)
                # These have chunk_id foreign keys, so must be deleted before chunks
                date_mentions_deleted = (
                    session.query(DateMention)
                    .filter(DateMention.doc_id == doc_id)
                    .delete()
                )
                sensitive_deleted = (
                    session.query(SensitiveDataMatch)
                    .filter(SensitiveDataMatch.doc_id == doc_id)
                    .delete()
                )

                # Timeline events have chunk_id FK - must delete before chunks
                timeline_deleted = (
                    session.query(TimelineEvent)
                    .filter(TimelineEvent.doc_id == doc_id)
                    .delete()
                )

                # Delete anomalies (references chunks via chunk_id)
                # Must delete before chunks since Anomaly.chunk_id → chunks.id
                anomalies_deleted = (
                    session.query(Anomaly)
                    .filter(
                        Anomaly.chunk_id.in_(
                            session.query(Chunk.id).filter(Chunk.doc_id == doc_id)
                        )
                    )
                    .delete(synchronize_session=False)
                )

                # Delete ingestion errors if the table exists
                try:
                    from app.arkham.services.db.models import IngestionError

                    session.query(IngestionError).filter(
                        IngestionError.document_id == doc_id
                    ).delete()
                except Exception:
                    pass  # Table may not exist

                # Now safe to delete chunks (no more FK dependencies pointing to chunks)
                chunks_deleted = (
                    session.query(Chunk).filter(Chunk.doc_id == doc_id).delete()
                )

                # Delete page_ocr (no dependencies)
                page_ocr_deleted = (
                    session.query(PageOCR)
                    .filter(PageOCR.document_id == doc_id)
                    .delete()
                )

                # Delete minidocs (references document)
                minidocs_deleted = (
                    session.query(MiniDoc)
                    .filter(MiniDoc.document_id == doc_id)
                    .delete()
                )

                # Delete entities (references document)
                entities_deleted = (
                    session.query(Entity).filter(Entity.doc_id == doc_id).delete()
                )

                # Note: timeline_events already deleted earlier (before chunks)

                # Delete extracted tables (references document)
                tables_deleted = (
                    session.query(ExtractedTable)
                    .filter(ExtractedTable.doc_id == doc_id)
                    .delete()
                )

                # Delete entity relationships (references document via doc_id)
                relationships_deleted = (
                    session.query(EntityRelationship)
                    .filter(EntityRelationship.doc_id == doc_id)
                    .delete()
                )

                # Finally delete the document itself
                session.delete(doc)
                session.commit()

                total_deleted = (
                    chunks_deleted
                    + page_ocr_deleted
                    + minidocs_deleted
                    + entities_deleted
                    + timeline_deleted
                    + date_mentions_deleted
                    + anomalies_deleted
                    + sensitive_deleted
                    + tables_deleted
                    + relationships_deleted
                    + contradiction_evidence_deleted
                    + 1
                )

                results["database_entries"] = total_deleted
                results["success"] = True
                logger.info(
                    f"Deleted document {doc_id} and {total_deleted} related records from database"
                )
            except Exception as db_error:
                session.rollback()
                results["errors"].append(f"Database deletion failed: {db_error}")
                logger.error(f"Database deletion failed for doc {doc_id}: {db_error}")
                import traceback

                traceback.print_exc()

        except Exception as e:
            # Catch any other errors not already handled
            logger.error(f"Document deletion failed for doc {doc_id}: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        return results

    def get_documents_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """Get list of documents by status."""
        session = self.Session()
        try:
            docs = (
                session.query(Document)
                .filter(Document.status == status)
                .order_by(Document.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "status": doc.status,
                    "file_path": doc.path,
                    "num_pages": doc.num_pages or 0,
                    "created_at": doc.created_at.isoformat()
                    if doc.created_at
                    else None,
                    "document_hash": doc.file_hash,
                }
                for doc in docs
            ]
        finally:
            session.close()

    def requeue_document(self, doc_id: int) -> Dict[str, any]:
        """
        Requeue a document for reprocessing.

        Sets status back to 'uploaded' and enqueues splitter job.
        NOTE: This assumes the file already exists in permanent storage.
        """
        session = self.Session()
        results = {"success": False, "doc_id": doc_id, "errors": []}

        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                results["errors"].append(f"Document {doc_id} not found")
                return results

            # Check if file exists
            if not os.path.exists(doc.path):
                results["errors"].append(f"File not found: {doc.path}")
                logger.error(f"Cannot requeue doc {doc_id}: file missing at {doc.path}")
                return results

            # Determine which file to process (converted PDF or original)
            file_to_process = doc.path
            ext = os.path.splitext(doc.path)[1].lower()

            # Check for converted PDF
            if ext != ".pdf":
                converted_path = doc.path.rsplit(".", 1)[0] + ".converted.pdf"
                if os.path.exists(converted_path):
                    file_to_process = converted_path
                    logger.info(f"Found converted PDF: {converted_path}")

            # Reset document state
            doc.status = "uploaded"
            doc.num_pages = 0  # Reset to trigger full reprocessing
            session.commit()

            # Enqueue splitter job directly (file already in permanent storage)
            # This is the same job that ingest_worker enqueues after moving the file
            job = self.queue.enqueue(
                "app.arkham.services.workers.splitter_worker.split_pdf_job",
                doc_id=doc.id,
                file_path=file_to_process,
                ocr_mode="paddle",  # Default to paddle, user can change in config
                description=f"Reprocess: {doc.title}",
            )

            results["success"] = True
            results["job_id"] = job.id
            logger.info(f"Requeued document {doc_id} with job {job.id}")

        except Exception as e:
            session.rollback()
            results["errors"].append(f"Requeue failed: {e}")
            logger.error(f"Requeue failed for doc {doc_id}: {e}")

        finally:
            session.close()

        return results

    def clear_completed_documents(self) -> Dict[str, any]:
        """Delete all completed documents and their data."""
        session = self.Session()
        results = {"success": False, "deleted_count": 0, "errors": []}

        try:
            completed_docs = (
                session.query(Document).filter(Document.status == "complete").all()
            )

            for doc in completed_docs:
                del_result = self.delete_document(doc.id)
                if del_result["success"]:
                    results["deleted_count"] += 1
                else:
                    results["errors"].extend(del_result["errors"])

            results["success"] = True
            logger.info(f"Cleared {results['deleted_count']} completed documents")

        except Exception as e:
            results["errors"].append(f"Clear completed failed: {e}")
            logger.error(f"Clear completed failed: {e}")

        finally:
            session.close()

        return results

    def wipe_all_data(self) -> Dict[str, any]:
        """
        DANGER: Wipe entire database and all files.

        Use with extreme caution!
        """
        session = self.Session()
        results = {
            "success": False,
            "documents_deleted": 0,
            "vectors_deleted": False,
            "files_deleted": 0,
            "errors": [],
        }

        try:
            # 1. Delete all vectors from Qdrant
            try:
                self.qdrant_client.delete_collection(QDRANT_COLLECTION)
                # Recreate empty collection
                from app.arkham.services.db.vector_store import (
                    create_hybrid_collection,
                )

                create_hybrid_collection()
                results["vectors_deleted"] = True
                logger.info("Wiped Qdrant collection")
            except Exception as e:
                results["errors"].append(f"Qdrant wipe failed: {e}")

            # 2. Delete all database entries
            doc_count = session.query(Document).count()
            session.query(Document).delete()
            session.commit()
            results["documents_deleted"] = doc_count
            logger.info(f"Wiped {doc_count} documents from database")

            # 3. Delete all files
            if DOCUMENTS_DIR.exists():
                for file_path in DOCUMENTS_DIR.glob("*"):
                    try:
                        if file_path.is_file():
                            file_path.unlink()
                            results["files_deleted"] += 1
                    except Exception as e:
                        results["errors"].append(f"File deletion failed: {e}")

            # 4. Delete all page images
            if RAW_PAGES_DIR.exists():
                for hash_dir in RAW_PAGES_DIR.iterdir():
                    if hash_dir.is_dir():
                        for page_img in hash_dir.glob("*.png"):
                            try:
                                page_img.unlink()
                                results["files_deleted"] += 1
                            except Exception as e:
                                results["errors"].append(
                                    f"Page image deletion failed: {e}"
                                )
                        try:
                            hash_dir.rmdir()
                        except Exception:
                            pass

            # 5. Clear RQ queue
            self.queue.empty()
            logger.info("Cleared RQ queue")

            results["success"] = True
            logger.info("Database wipe complete")

        except Exception as e:
            session.rollback()
            results["errors"].append(f"Wipe failed: {e}")
            logger.error(f"Database wipe failed: {e}")
            import traceback

            traceback.print_exc()

        finally:
            session.close()

        return results


# Singleton instance
_service_instance = None


def get_document_service() -> DocumentManagementService:
    """Get singleton document management service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = DocumentManagementService()
    return _service_instance
