"""
Phase 5.2: Ingestion Error Logging Service

Provides centralized error tracking for all ingestion stages.
No silent failures - every error is persisted to the database.
"""

# Add project root to path for central config
from pathlib import Path
import sys
project_root = Path(__file__).resolve()
while project_root.name != 'ArkhamMirror' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import logging
import traceback
import os
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from .db.models import IngestionError

load_dotenv()
logger = logging.getLogger(__name__)




class IngestionErrorService:
    """Service for logging and managing ingestion errors."""

    STAGES = [
        "ocr",
        "chunking",
        "embedding",
        "entity",
        "llm_enrich",
        "table",
        "general",
    ]
    ERROR_TYPES = ["timeout", "parse_error", "connection", "validation", "unknown"]

    def __init__(self):
        # Robust connection pool settings to prevent hanging
        self.engine = create_engine(
            DATABASE_URL,
            pool_size=3,
            max_overflow=2,
            pool_timeout=10,  # Wait max 10s for connection
            pool_recycle=300,  # Recycle connections after 5 min
            pool_pre_ping=True,  # Test connection before use
        )
        self.Session = sessionmaker(bind=self.engine)

    def log_error(
        self,
        stage: str,
        error_type: str,
        error_message: str,
        document_id: Optional[int] = None,
        chunk_id: Optional[int] = None,
        include_traceback: bool = True,
    ) -> int:
        """
        Log an ingestion error to the database.

        Args:
            stage: Processing stage (ocr, chunking, embedding, entity, llm_enrich, table)
            error_type: Type of error (timeout, parse_error, connection, validation)
            error_message: Human-readable error message
            document_id: Optional associated document ID
            chunk_id: Optional associated chunk ID
            include_traceback: Whether to capture the current stack trace

        Returns:
            ID of the created error record
        """
        session = self.Session()
        try:
            stack_trace = None
            if include_traceback:
                stack_trace = traceback.format_exc()
                # Don't include "NoneType: None" if there's no active exception
                if "NoneType: None" in stack_trace:
                    stack_trace = None

            error = IngestionError(
                document_id=document_id,
                chunk_id=chunk_id,
                stage=stage if stage in self.STAGES else "general",
                error_type=error_type if error_type in self.ERROR_TYPES else "unknown",
                error_message=str(error_message)[:4000],  # Truncate if too long
                stack_trace=stack_trace,
            )
            session.add(error)
            session.commit()

            error_id = error.id
            logger.warning(
                f"Ingestion error logged: [{stage}] {error_type} - {error_message[:100]}... (ID: {error_id})"
            )
            return error_id

        except Exception as e:
            logger.error(f"Failed to log ingestion error: {e}")
            session.rollback()
            return -1
        finally:
            session.close()

    def log_exception(
        self,
        stage: str,
        exception: Exception,
        document_id: Optional[int] = None,
        chunk_id: Optional[int] = None,
    ) -> int:
        """
        Convenience method to log an exception with automatic type detection.
        """
        error_type = self._classify_exception(exception)
        error_message = str(exception)

        return self.log_error(
            stage=stage,
            error_type=error_type,
            error_message=error_message,
            document_id=document_id,
            chunk_id=chunk_id,
            include_traceback=True,
        )

    def _classify_exception(self, exception: Exception) -> str:
        """Classify an exception into an error type."""
        exception_name = type(exception).__name__.lower()

        if "timeout" in exception_name or "timedout" in exception_name:
            return "timeout"
        elif (
            "parse" in exception_name
            or "json" in exception_name
            or "decode" in exception_name
        ):
            return "parse_error"
        elif (
            "connection" in exception_name
            or "socket" in exception_name
            or "network" in exception_name
        ):
            return "connection"
        elif (
            "validation" in exception_name
            or "value" in exception_name
            or "type" in exception_name
        ):
            return "validation"
        else:
            return "unknown"

    def get_errors_for_document(self, document_id: int) -> List[Dict[str, Any]]:
        """Get all errors for a specific document."""
        session = self.Session()
        try:
            errors = (
                session.query(IngestionError)
                .filter(IngestionError.document_id == document_id)
                .order_by(IngestionError.created_at.desc())
                .all()
            )
            return [
                {
                    "id": e.id,
                    "stage": e.stage,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "is_resolved": bool(e.is_resolved),
                    "retry_count": e.retry_count,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in errors
            ]
        finally:
            session.close()

    def get_unresolved_errors(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all unresolved errors across all documents."""
        session = self.Session()
        try:
            errors = (
                session.query(IngestionError)
                .filter(IngestionError.is_resolved == 0)
                .order_by(IngestionError.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": e.id,
                    "document_id": e.document_id,
                    "chunk_id": e.chunk_id,
                    "stage": e.stage,
                    "error_type": e.error_type,
                    "error_message": e.error_message[:200] + "..."
                    if len(e.error_message) > 200
                    else e.error_message,
                    "retry_count": e.retry_count,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in errors
            ]
        finally:
            session.close()

    def get_error_counts_by_stage(self) -> Dict[str, int]:
        """Get count of unresolved errors grouped by stage."""
        session = self.Session()
        try:
            results = (
                session.query(IngestionError.stage, func.count(IngestionError.id))
                .filter(IngestionError.is_resolved == 0)
                .group_by(IngestionError.stage)
                .all()
            )
            return {stage: count for stage, count in results}
        finally:
            session.close()

    def mark_resolved(self, error_id: int, increment_retry: bool = False) -> bool:
        """Mark an error as resolved."""
        session = self.Session()
        try:
            error = (
                session.query(IngestionError)
                .filter(IngestionError.id == error_id)
                .first()
            )
            if error:
                error.is_resolved = 1
                if increment_retry:
                    error.retry_count += 1
                session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to mark error resolved: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_error_detail(self, error_id: int) -> Optional[Dict[str, Any]]:
        """Get full details of an error including stack trace."""
        session = self.Session()
        try:
            error = (
                session.query(IngestionError)
                .filter(IngestionError.id == error_id)
                .first()
            )
            if error:
                return {
                    "id": error.id,
                    "document_id": error.document_id,
                    "chunk_id": error.chunk_id,
                    "stage": error.stage,
                    "error_type": error.error_type,
                    "error_message": error.error_message,
                    "stack_trace": error.stack_trace,
                    "is_resolved": bool(error.is_resolved),
                    "retry_count": error.retry_count,
                    "created_at": error.created_at.isoformat()
                    if error.created_at
                    else None,
                }
            return None
        finally:
            session.close()


# Singleton instance for easy import
_error_service: Optional[IngestionErrorService] = None


def get_error_service() -> IngestionErrorService:
    """Get the singleton error service instance."""
    global _error_service
    if _error_service is None:
        _error_service = IngestionErrorService()
    return _error_service


def log_ingestion_error(
    stage: str,
    error_type: str,
    message: str,
    document_id: Optional[int] = None,
    chunk_id: Optional[int] = None,
) -> int:
    """Convenience function for logging errors without instantiating service."""
    return get_error_service().log_error(
        stage=stage,
        error_type=error_type,
        error_message=message,
        document_id=document_id,
        chunk_id=chunk_id,
    )


def log_ingestion_exception(
    stage: str,
    exception: Exception,
    document_id: Optional[int] = None,
    chunk_id: Optional[int] = None,
) -> int:
    """Convenience function for logging exceptions."""
    return get_error_service().log_exception(
        stage=stage,
        exception=exception,
        document_id=document_id,
        chunk_id=chunk_id,
    )
