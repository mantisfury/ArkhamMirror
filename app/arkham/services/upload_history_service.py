"""
Upload History Service

Track document uploads with timestamps and status.
"""

# Add project root to path for central config
from pathlib import Path
import sys
project_root = Path(__file__).resolve()
while project_root.name != 'ArkhamMirror' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import os
import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    desc,
    func,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)



Base = declarative_base()


class UploadRecord(Base):
    """Upload history record."""

    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)  # bytes
    status = Column(
        String(50), default="pending"
    )  # pending, processing, completed, failed
    document_id = Column(Integer)  # Reference to documents table
    error_message = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class UploadHistoryService:
    """Service for managing upload history."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        # Create table if not exists
        Base.metadata.create_all(self.engine)

    def record_upload(
        self, filename: str, file_type: str = None, file_size: int = 0
    ) -> Dict[str, Any]:
        """Record a new upload."""
        session = self.Session()
        try:
            record = UploadRecord(
                filename=filename,
                file_type=file_type,
                file_size=file_size,
                status="pending",
            )
            session.add(record)
            session.commit()

            return {
                "id": record.id,
                "filename": record.filename,
                "status": record.status,
            }
        finally:
            session.close()

    def update_status(
        self,
        record_id: int,
        status: str,
        document_id: int = None,
        error_message: str = None,
    ) -> Dict[str, Any]:
        """Update upload status."""
        session = self.Session()
        try:
            record = session.query(UploadRecord).filter_by(id=record_id).first()
            if not record:
                return {"error": "Record not found"}

            record.status = status
            if document_id:
                record.document_id = document_id
            if error_message:
                record.error_message = error_message
            if status in ["completed", "failed"]:
                record.completed_at = datetime.utcnow()

            session.commit()

            return {
                "id": record.id,
                "status": record.status,
            }
        finally:
            session.close()

    def get_history(self, status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get upload history."""
        session = self.Session()
        try:
            query = session.query(UploadRecord)

            if status:
                query = query.filter(UploadRecord.status == status)

            records = query.order_by(desc(UploadRecord.uploaded_at)).limit(limit).all()

            return [
                {
                    "id": r.id,
                    "filename": r.filename,
                    "file_type": r.file_type,
                    "file_size": r.file_size,
                    "status": r.status,
                    "document_id": r.document_id,
                    "error_message": r.error_message,
                    "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
                    "completed_at": r.completed_at.isoformat()
                    if r.completed_at
                    else None,
                }
                for r in records
            ]
        finally:
            session.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get upload statistics."""
        session = self.Session()
        try:
            total = session.query(func.count(UploadRecord.id)).scalar() or 0

            by_status = {}
            for status in ["pending", "processing", "completed", "failed"]:
                count = session.query(UploadRecord).filter_by(status=status).count()
                by_status[status] = count

            # Recent uploads (last 24 hours)
            from datetime import timedelta

            yesterday = datetime.utcnow() - timedelta(hours=24)
            recent = (
                session.query(func.count(UploadRecord.id))
                .filter(UploadRecord.uploaded_at >= yesterday)
                .scalar()
            ) or 0

            # Total size
            total_size = (session.query(func.sum(UploadRecord.file_size)).scalar()) or 0

            return {
                "total": total,
                "by_status": by_status,
                "recent_24h": recent,
                "total_size_bytes": total_size,
            }
        finally:
            session.close()

    def delete_record(self, record_id: int) -> bool:
        """Delete an upload record."""
        session = self.Session()
        try:
            record = session.query(UploadRecord).filter_by(id=record_id).first()
            if record:
                session.delete(record)
                session.commit()
                return True
            return False
        finally:
            session.close()

    def clear_old_records(self, days: int = 30) -> int:
        """Clear records older than N days."""
        session = self.Session()
        try:
            from datetime import timedelta

            cutoff = datetime.utcnow() - timedelta(days=days)

            count = (
                session.query(UploadRecord)
                .filter(UploadRecord.uploaded_at < cutoff)
                .delete()
            )
            session.commit()
            return count
        finally:
            session.close()


# Singleton
_service_instance = None


def get_upload_history_service() -> UploadHistoryService:
    global _service_instance
    if _service_instance is None:
        _service_instance = UploadHistoryService()
    return _service_instance
