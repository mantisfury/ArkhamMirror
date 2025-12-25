"""
DocumentService - Read-only document access.
"""

from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DocumentNotFoundError(Exception):
    """Document not found."""
    def __init__(self, doc_id: str):
        super().__init__(f"Document not found: {doc_id}")


class DocumentService:
    """
    Read-only document access service.

    Provides access to documents stored by Frame.
    """

    def __init__(self, db=None, vectors=None, config=None):
        self.db = db
        self.vectors = vectors
        self.config = config

    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        # Placeholder - actual implementation needs models
        return None

    async def list_documents(
        self,
        offset: int = 0,
        limit: int = 50,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List documents with pagination."""
        return []

    async def get_document_text(self, doc_id: str) -> Optional[str]:
        """Get full text of a document."""
        return None

    async def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search documents by text."""
        return []
