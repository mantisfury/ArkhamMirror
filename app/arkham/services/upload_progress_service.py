"""
Upload Progress Service

Tracks document processing progress through the ingestion pipeline:
Uploaded → Splitting → OCR → Parsing → Embedding → Complete
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from config.settings import DATABASE_URL

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.arkham.services.db.models import Document, MiniDoc, PageOCR, Chunk


class UploadProgressService:
    """Service for tracking document processing progress."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_document_progress(self, doc_id: int) -> Dict:
        """
        Get detailed progress for a specific document.

        Returns dict with:
        - doc_id: int
        - title: str
        - status: str (uploaded, processing, complete, failed)
        - stage: str (splitting, ocr, parsing, embedding, complete)
        - progress_pct: int (0-100)
        - details: str (human-readable progress description)
        - num_pages: int
        - pages_ocr_complete: int
        - chunks_created: int
        - created_at: datetime
        """
        session = self.Session()
        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                return None

            # Count progress indicators
            num_pages = doc.num_pages or 0
            pages_ocr_complete = (
                session.query(func.count(PageOCR.id))
                .filter(PageOCR.document_id == doc_id)
                .scalar()
                or 0
            )
            chunks_created = (
                session.query(func.count(Chunk.id))
                .filter(Chunk.doc_id == doc_id)
                .scalar()
                or 0
            )

            # Determine current stage and progress
            stage, progress_pct, details = self._calculate_stage_progress(
                doc.status, num_pages, pages_ocr_complete, chunks_created
            )

            return {
                "doc_id": doc.id,
                "title": doc.title or "Untitled",
                "status": doc.status,
                "stage": stage,
                "progress_pct": progress_pct,
                "details": details,
                "num_pages": num_pages,
                "pages_ocr_complete": pages_ocr_complete,
                "chunks_created": chunks_created,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
        finally:
            session.close()

    def get_active_uploads(self, limit: int = 20) -> List[Dict]:
        """
        Get list of documents currently being processed.

        Returns documents with status in: uploaded, processing
        Sorted by creation time (newest first)
        """
        session = self.Session()
        try:
            docs = (
                session.query(Document)
                .filter(Document.status.in_(["uploaded", "processing", "pending"]))
                .order_by(Document.created_at.desc())
                .limit(limit)
                .all()
            )

            results = []
            for doc in docs:
                progress = self.get_document_progress(doc.id)
                if progress:
                    results.append(progress)

            return results
        finally:
            session.close()

    def get_recently_completed(self, limit: int = 10) -> List[Dict]:
        """Get recently completed documents for display."""
        session = self.Session()
        try:
            docs = (
                session.query(Document)
                .filter(Document.status == "complete")
                .order_by(Document.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "doc_id": doc.id,
                    "title": doc.title or "Untitled",
                    "status": "complete",
                    "stage": "complete",
                    "progress_pct": 100,
                    "details": "Processing complete",
                    "num_pages": doc.num_pages or 0,
                    "created_at": doc.created_at.isoformat()
                    if doc.created_at
                    else None,
                }
                for doc in docs
            ]
        finally:
            session.close()

    def _calculate_stage_progress(
        self, status: str, num_pages: int, pages_ocr: int, chunks: int
    ) -> tuple[str, int, str]:
        """
        Calculate current stage, progress percentage, and human-readable details.

        Pipeline stages:
        1. Uploaded (0-10%): File saved, waiting for worker
        2. Splitting (10-20%): PDF being split into minidocs
        3. OCR (20-60%): Text extraction from pages
        4. Parsing (60-80%): Chunking and NER
        5. Embedding (80-95%): Vector embeddings
        6. Complete (100%): All done

        Returns: (stage, progress_pct, details)
        """
        if status == "failed":
            return ("failed", 0, "Processing failed")

        if status == "complete":
            return ("complete", 100, f"Complete - {num_pages} pages, {chunks} chunks")

        # Document is uploaded but not yet processing
        if status in ["uploaded", "pending"]:
            return ("uploaded", 5, "Waiting for worker to pick up...")

        # Document is being processed
        if status == "processing":
            # No pages yet - still splitting
            if num_pages == 0:
                return ("splitting", 15, "Splitting document into pages...")

            # Pages exist, OCR in progress
            if pages_ocr == 0:
                return ("ocr", 20, f"Starting OCR on {num_pages} pages...")

            if pages_ocr < num_pages:
                ocr_pct = int((pages_ocr / num_pages) * 40) + 20  # 20-60%
                return ("ocr", ocr_pct, f"OCR progress: {pages_ocr}/{num_pages} pages")

            # OCR done, parsing in progress
            if chunks == 0:
                return ("parsing", 65, "Starting text chunking and NER...")

            # Chunks exist, likely in parsing or embedding
            if chunks > 0:
                # Estimate: reasonable chunk count is ~10-50 per page
                expected_chunks = num_pages * 20  # Middle estimate
                if chunks < expected_chunks:
                    parse_pct = int((chunks / expected_chunks) * 15) + 60  # 60-75%
                    return (
                        "parsing",
                        min(parse_pct, 75),
                        f"Parsing: {chunks} chunks created",
                    )
                else:
                    # Likely in embedding stage
                    return (
                        "embedding",
                        85,
                        f"Creating embeddings for {chunks} chunks...",
                    )

        # Fallback
        return ("processing", 50, "Processing...")


# Singleton instance
_service_instance = None


def get_progress_service() -> UploadProgressService:
    """Get singleton upload progress service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = UploadProgressService()
    return _service_instance
