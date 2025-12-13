import reflex as rx
import logging
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)


class DocOption(BaseModel):
    id: int
    filename: str
    file_type: str


class EntityInfo(BaseModel):
    id: int
    name: str
    type: str


class ComparisonState(rx.State):
    """State for Document Comparison."""

    # Available documents
    documents: List[DocOption] = []

    # Selected documents
    doc1_id: int = 0
    doc2_id: int = 0
    doc1_name: str = ""
    doc2_name: str = ""

    # Comparison results
    text_similarity: float = 0.0
    entity_similarity: float = 0.0
    shared_entities: List[EntityInfo] = []
    doc1_only_entities: List[EntityInfo] = []
    doc2_only_entities: List[EntityInfo] = []
    diff_text: str = ""
    common_phrases: List[str] = []

    # Document stats
    doc1_chunks: int = 0
    doc1_entities: int = 0
    doc2_chunks: int = 0
    doc2_entities: int = 0

    # UI state
    is_loading: bool = False
    has_comparison: bool = False

    def load_documents(self):
        """Load available documents."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.comparison_service import get_comparison_service

            service = get_comparison_service()
            docs = service.get_available_documents()

            self.documents = [
                DocOption(
                    id=d["id"],
                    filename=d["filename"],
                    file_type=d["file_type"] or "",
                )
                for d in docs
            ]

        except Exception as e:
            logger.error(f"Error loading documents: {e}")
        finally:
            self.is_loading = False

    def select_doc1(self, doc_id: str):
        """Select first document."""
        try:
            self.doc1_id = int(doc_id)
            for d in self.documents:
                if d.id == self.doc1_id:
                    self.doc1_name = d.filename
                    break
        except ValueError:
            pass

    def select_doc2(self, doc_id: str):
        """Select second document."""
        try:
            self.doc2_id = int(doc_id)
            for d in self.documents:
                if d.id == self.doc2_id:
                    self.doc2_name = d.filename
                    break
        except ValueError:
            pass

    def compare_documents(self):
        """Run comparison between selected documents."""
        if self.doc1_id == 0 or self.doc2_id == 0:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.comparison_service import get_comparison_service

            service = get_comparison_service()
            result = service.full_comparison(self.doc1_id, self.doc2_id)

            if "error" in result:
                return

            # Document stats
            self.doc1_chunks = result["doc1"]["chunk_count"]
            self.doc1_entities = result["doc1"]["entity_count"]
            self.doc2_chunks = result["doc2"]["chunk_count"]
            self.doc2_entities = result["doc2"]["entity_count"]

            # Text comparison
            self.text_similarity = result["text"]["similarity"]
            self.diff_text = result["text"]["diff"]
            self.common_phrases = result["text"]["common_phrases"]

            # Entity comparison
            self.entity_similarity = result["entities"]["similarity_score"]

            self.shared_entities = [
                EntityInfo(id=e["id"], name=e["name"], type=e["type"])
                for e in result["entities"]["shared"]
            ]
            self.doc1_only_entities = [
                EntityInfo(id=e["id"], name=e["name"], type=e["type"])
                for e in result["entities"]["only_doc1"]
            ]
            self.doc2_only_entities = [
                EntityInfo(id=e["id"], name=e["name"], type=e["type"])
                for e in result["entities"]["only_doc2"]
            ]

            self.has_comparison = True

        except Exception as e:
            logger.error(f"Error comparing: {e}")
        finally:
            self.is_loading = False

    @rx.var
    def entity_count(self) -> int:
        return len(self.documents)

    @rx.var
    def document_select_items(self) -> List[List[str]]:
        return [[d.filename, str(d.id)] for d in self.documents]

    def clear_comparison(self):
        self.has_comparison = False
        self.doc1_id = 0
        self.doc2_id = 0
        self.doc1_name = ""
        self.doc2_name = ""

    def set_comparison_pair(
        self, doc1_id: int, doc1_name: str, doc2_id: int, doc2_name: str
    ):
        """Pre-select two documents for comparison (called from external pages)."""
        self.doc1_id = doc1_id
        self.doc1_name = doc1_name
        self.doc2_id = doc2_id
        self.doc2_name = doc2_name
        # Auto-run comparison when pair is set
        return ComparisonState.compare_documents
