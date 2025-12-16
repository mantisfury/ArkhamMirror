import reflex as rx
import logging
from pydantic import BaseModel
from typing import List

logger = logging.getLogger(__name__)


class DocumentPair(BaseModel):
    doc1_id: int
    doc1_filename: str
    doc2_id: int
    doc2_filename: str
    similarity: float
    hamming_distance: int
    match_type: str


class ClusterDocument(BaseModel):
    id: int
    filename: str


class DocumentCluster(BaseModel):
    cluster_id: int
    size: int
    documents: List[ClusterDocument] = []


class SharedPattern(BaseModel):
    pattern_hash: str
    occurrences: int
    sample_text: str


# Stylometry models
class StyleMatch(BaseModel):
    doc1_id: int
    doc1_filename: str
    doc2_id: int
    doc2_filename: str
    style_similarity: float
    key_similarities: List[str] = []


class StyleProfile(BaseModel):
    document_id: int
    filename: str
    word_count: int
    sentence_count: int
    avg_word_length: float
    vocabulary_richness: float
    avg_sentence_length: float
    punctuation_per_sentence: float


class AuthorCluster(BaseModel):
    cluster_id: int
    size: int
    label: str
    documents: List[ClusterDocument] = []


# Unmask Author models
class SelectableDocument(BaseModel):
    id: int
    filename: str
    file_type: str


class AuthorshipResult(BaseModel):
    document_id: int
    filename: str
    probability: float
    verdict: str
    key_matches: List[str] = []
    key_differences: List[str] = []


class PseudonymGroup(BaseModel):
    group_id: int
    match_to_reference: float
    size: int
    documents: List[ClusterDocument] = []


class UnmaskSummary(BaseModel):
    likely_matches: int
    possible_matches: int
    unlikely_matches: int


class DuplicatesState(rx.State):
    """State for Fingerprint Duplicate Detection and Authorship Analysis."""

    # Summary stats
    total_similar_pairs: int = 0
    exact_duplicates: int = 0
    near_duplicates: int = 0
    similar_content: int = 0
    partial_overlap: int = 0
    total_clusters: int = 0
    shared_patterns_count: int = 0

    # Results lists
    similar_pairs: List[DocumentPair] = []
    clusters: List[DocumentCluster] = []
    shared_patterns: List[SharedPattern] = []

    # Authorship/Stylometry state
    style_matches: List[StyleMatch] = []
    author_clusters: List[AuthorCluster] = []
    style_profiles: List[StyleProfile] = []
    is_analyzing_style: bool = False
    has_style_results: bool = False
    style_threshold: float = 60.0

    # Unmask Author state
    available_documents: List[SelectableDocument] = []
    known_doc_ids: List[int] = []
    unknown_doc_ids: List[int] = []
    unmask_results: List[AuthorshipResult] = []
    pseudonym_groups: List[PseudonymGroup] = []
    unmask_summary: UnmaskSummary = UnmaskSummary(
        likely_matches=0, possible_matches=0, unlikely_matches=0
    )
    is_unmasking: bool = False
    has_unmask_results: bool = False
    reference_doc_count: int = 0

    # UI state
    is_scanning: bool = False
    active_tab: str = "duplicates"
    has_results: bool = False
    similarity_threshold: float = 0.7

    @rx.var
    def similarity_threshold_str(self) -> str:
        """Return threshold as string for dropdown binding."""
        return str(round(self.similarity_threshold, 1))

    @rx.var
    def style_threshold_str(self) -> str:
        """Return style threshold as string for dropdown binding."""
        return str(int(self.style_threshold))

    def run_scan(self):
        """Scan corpus for duplicate documents."""
        self.is_scanning = True
        yield

        try:
            from app.arkham.services.duplicates_service import (
                get_duplicates_service,
            )

            service = get_duplicates_service()

            # Get summary
            summary = service.get_duplicate_summary()
            self.total_similar_pairs = summary["total_similar_pairs"]
            self.exact_duplicates = summary["exact_duplicates"]
            self.near_duplicates = summary["near_duplicates"]
            self.similar_content = summary["similar_content"]
            self.partial_overlap = summary["partial_overlap"]
            self.total_clusters = summary["total_clusters"]
            self.shared_patterns_count = summary["shared_patterns"]

            # Get similar pairs
            pairs = service.find_similar_documents(threshold=self.similarity_threshold)
            self.similar_pairs = [
                DocumentPair(
                    doc1_id=p["doc1_id"],
                    doc1_filename=p["doc1_filename"],
                    doc2_id=p["doc2_id"],
                    doc2_filename=p["doc2_filename"],
                    similarity=p["similarity"],
                    hamming_distance=p["hamming_distance"],
                    match_type=p["match_type"],
                )
                for p in pairs
            ]

            # Get clusters
            clusters = service.cluster_similar_documents()
            self.clusters = [
                DocumentCluster(
                    cluster_id=c["cluster_id"],
                    size=c["size"],
                    documents=[
                        ClusterDocument(id=d["id"], filename=d["filename"])
                        for d in c["documents"]
                    ],
                )
                for c in clusters
            ]

            # Get shared patterns
            patterns = service.find_copy_paste_patterns()
            self.shared_patterns = [
                SharedPattern(
                    pattern_hash=p["pattern_hash"],
                    occurrences=p["occurrences"],
                    sample_text=p["sample_text"],
                )
                for p in patterns
            ]

            self.has_results = True

        except Exception as e:
            logger.error(f"Error scanning for duplicates: {e}")
        finally:
            self.is_scanning = False

    def run_authorship_scan(self):
        """Analyze documents for authorship/writing style patterns."""
        self.is_analyzing_style = True
        yield

        try:
            from app.arkham.services.duplicates_service import (
                get_duplicates_service,
            )

            service = get_duplicates_service()

            # Get style matches (documents with similar writing voice)
            matches = service.find_style_matches(threshold=self.style_threshold)
            self.style_matches = [
                StyleMatch(
                    doc1_id=m["doc1_id"],
                    doc1_filename=m["doc1_filename"],
                    doc2_id=m["doc2_id"],
                    doc2_filename=m["doc2_filename"],
                    style_similarity=m["style_similarity"],
                    key_similarities=m.get("key_similarities", []),
                )
                for m in matches
            ]

            # Get author clusters
            clusters = service.cluster_by_authorship(threshold=self.style_threshold)
            self.author_clusters = [
                AuthorCluster(
                    cluster_id=c["cluster_id"],
                    size=c["size"],
                    label=c.get("label", f"Author Group {c['cluster_id']}"),
                    documents=[
                        ClusterDocument(id=d["id"], filename=d["filename"])
                        for d in c["documents"]
                    ],
                )
                for c in clusters
            ]

            # Get style profiles for display
            profiles = service.get_all_style_profiles()
            self.style_profiles = [
                StyleProfile(
                    document_id=p["document_id"],
                    filename=p["filename"],
                    word_count=p["word_count"],
                    sentence_count=p["sentence_count"],
                    avg_word_length=p["avg_word_length"],
                    vocabulary_richness=p["vocabulary_richness"],
                    avg_sentence_length=p["avg_sentence_length"],
                    punctuation_per_sentence=p["punctuation_per_sentence"],
                )
                for p in profiles
            ]

            self.has_style_results = True

        except Exception as e:
            logger.error(f"Error analyzing authorship: {e}")
        finally:
            self.is_analyzing_style = False

    def set_style_threshold(self, value: str):
        """Set style similarity threshold."""
        try:
            self.style_threshold = float(value)
        except ValueError:
            pass

    def set_threshold(self, value: str):
        """Set similarity threshold."""
        try:
            self.similarity_threshold = float(value)
        except ValueError:
            pass

    def set_active_tab(self, tab: str):
        self.active_tab = tab

    async def compare_pair(
        self, doc1_id: int, doc1_name: str, doc2_id: int, doc2_name: str
    ):
        """Navigate to comparison page with this pair pre-selected."""
        from app.arkham.state.comparison_state import ComparisonState

        # Get the comparison state (async)
        comparison_state = await self.get_state(ComparisonState)

        # Set the comparison pair
        comparison_state.doc1_id = doc1_id
        comparison_state.doc1_name = doc1_name
        comparison_state.doc2_id = doc2_id
        comparison_state.doc2_name = doc2_name
        comparison_state.has_comparison = False

        # Navigate to comparison page
        return rx.redirect("/comparison")

    # ========== UNMASK AUTHOR METHODS ==========

    def load_documents_for_unmask(self):
        """Load all documents for selection in Unmask Author."""
        try:
            from app.arkham.services.duplicates_service import (
                get_duplicates_service,
            )

            service = get_duplicates_service()
            docs = service.get_all_documents_for_selection()
            self.available_documents = [
                SelectableDocument(
                    id=d["id"],
                    filename=d["filename"],
                    file_type=d["file_type"],
                )
                for d in docs
            ]
        except Exception as e:
            logger.error(f"Error loading documents: {e}")

    def toggle_known_doc(self, doc_id: int):
        """Toggle a document in the known (reference) set."""
        if doc_id in self.known_doc_ids:
            self.known_doc_ids = [d for d in self.known_doc_ids if d != doc_id]
        else:
            # Remove from unknown if present
            if doc_id in self.unknown_doc_ids:
                self.unknown_doc_ids = [d for d in self.unknown_doc_ids if d != doc_id]
            self.known_doc_ids = self.known_doc_ids + [doc_id]

    def toggle_unknown_doc(self, doc_id: int):
        """Toggle a document in the unknown (test) set."""
        if doc_id in self.unknown_doc_ids:
            self.unknown_doc_ids = [d for d in self.unknown_doc_ids if d != doc_id]
        else:
            # Remove from known if present
            if doc_id in self.known_doc_ids:
                self.known_doc_ids = [d for d in self.known_doc_ids if d != doc_id]
            self.unknown_doc_ids = self.unknown_doc_ids + [doc_id]

    def clear_selections(self):
        """Clear all document selections."""
        self.known_doc_ids = []
        self.unknown_doc_ids = []
        self.has_unmask_results = False
        self.unmask_results = []
        self.pseudonym_groups = []

    def select_all_as_unknown(self):
        """Select all documents as unknown (except those already known)."""
        self.unknown_doc_ids = [
            d.id for d in self.available_documents if d.id not in self.known_doc_ids
        ]

    def run_unmask_author(self):
        """Run authorship attribution analysis."""
        if not self.known_doc_ids:
            return
        if not self.unknown_doc_ids:
            return

        self.is_unmasking = True
        yield

        try:
            from app.arkham.services.duplicates_service import (
                get_duplicates_service,
            )

            service = get_duplicates_service()
            result = service.unmask_author(self.known_doc_ids, self.unknown_doc_ids)

            if "error" in result:
                logger.error(f"Unmask error: {result['error']}")
                return

            # Store results
            self.unmask_results = [
                AuthorshipResult(
                    document_id=r["document_id"],
                    filename=r["filename"],
                    probability=r["probability"],
                    verdict=r["verdict"],
                    key_matches=r.get("key_matches", []),
                    key_differences=r.get("key_differences", []),
                )
                for r in result["results"]
            ]

            # Store pseudonym groups
            self.pseudonym_groups = [
                PseudonymGroup(
                    group_id=g["group_id"],
                    match_to_reference=g["match_to_reference"],
                    size=g["size"],
                    documents=[
                        ClusterDocument(id=d["id"], filename=d["filename"])
                        for d in g["documents"]
                    ],
                )
                for g in result.get("pseudonym_groups", [])
            ]

            # Summary
            summary = result.get("summary", {})
            self.unmask_summary = UnmaskSummary(
                likely_matches=summary.get("likely_matches", 0),
                possible_matches=summary.get("possible_matches", 0),
                unlikely_matches=summary.get("unlikely_matches", 0),
            )

            self.reference_doc_count = result.get("reference_profile", {}).get(
                "document_count", len(self.known_doc_ids)
            )
            self.has_unmask_results = True

        except Exception as e:
            logger.error(f"Error in unmask author: {e}")
        finally:
            self.is_unmasking = False
