"""
Metadata Forensics State Management

Manages state for the Metadata Forensics Dashboard including document analysis,
software distribution, and temporal patterns.
"""

import reflex as rx
from typing import List, Dict, Optional
import logging

from app.arkham.services.metadata_forensics_service import (
    get_metadata_forensics_service,
)
from app.arkham.models import (
    ProducerInfo,
    CreatorInfo,
    AuthorInfo,
    YearInfo,
    MonthInfo,
)

logger = logging.getLogger(__name__)


class MetadataForensicsState(rx.State):
    """State for Metadata Forensics Dashboard."""

    # Summary data
    metadata_summary: Dict = {}
    software_distribution: Dict = {}
    temporal_distribution: Dict = {}
    author_analysis: Dict = {}

    # Selected document details
    selected_document_id: Optional[int] = None
    selected_document_metadata: Dict = {}
    show_document_modal: bool = False

    # UI state
    is_loading: bool = False
    error_message: str = ""
    success_message: str = ""

    # Active tab
    active_tab: str = "overview"  # overview, software, timeline, authors, documents

    # Session cache flag - prevents auto-reload when navigating back
    _has_loaded: bool = False

    @rx.var
    def has_data(self) -> bool:
        """Check if metadata data has been loaded."""
        return bool(self.metadata_summary)

    # Flattened computed properties to avoid nested .get() on Vars
    @rx.var
    def total_documents(self) -> int:
        return self.metadata_summary.get("total_documents", 0)

    @rx.var
    def with_metadata(self) -> int:
        return self.metadata_summary.get("with_metadata", 0)

    @rx.var
    def encrypted_count(self) -> int:
        return self.metadata_summary.get("encrypted_count", 0)

    @rx.var
    def backdated_count(self) -> int:
        date_anomalies = self.metadata_summary.get("date_anomalies", {})
        return (
            date_anomalies.get("backdated", 0)
            if isinstance(date_anomalies, dict)
            else 0
        )

    @rx.var
    def missing_creation_date(self) -> int:
        missing = self.metadata_summary.get("missing_metadata", {})
        return missing.get("no_creation_date", 0) if isinstance(missing, dict) else 0

    @rx.var
    def missing_modification_date(self) -> int:
        missing = self.metadata_summary.get("missing_metadata", {})
        return (
            missing.get("no_modification_date", 0) if isinstance(missing, dict) else 0
        )

    @rx.var
    def missing_author(self) -> int:
        missing = self.metadata_summary.get("missing_metadata", {})
        return missing.get("no_author", 0) if isinstance(missing, dict) else 0

    @rx.var
    def missing_producer(self) -> int:
        missing = self.metadata_summary.get("missing_metadata", {})
        return missing.get("no_producer", 0) if isinstance(missing, dict) else 0

    @rx.var
    def missing_creator(self) -> int:
        missing = self.metadata_summary.get("missing_metadata", {})
        return missing.get("no_creator", 0) if isinstance(missing, dict) else 0

    @rx.var
    def future_dates_count(self) -> int:
        date_anomalies = self.metadata_summary.get("date_anomalies", {})
        return (
            date_anomalies.get("future_dates", 0)
            if isinstance(date_anomalies, dict)
            else 0
        )

    @rx.var
    def very_old_count(self) -> int:
        date_anomalies = self.metadata_summary.get("date_anomalies", {})
        return (
            date_anomalies.get("very_old", 0) if isinstance(date_anomalies, dict) else 0
        )

    @rx.var
    def same_create_modify_count(self) -> int:
        date_anomalies = self.metadata_summary.get("date_anomalies", {})
        return (
            date_anomalies.get("same_create_modify", 0)
            if isinstance(date_anomalies, dict)
            else 0
        )

    @rx.var
    def producers_list(self) -> List[ProducerInfo]:
        """Convert producers dict list to typed list."""
        producers = self.software_distribution.get("producers", [])
        return [
            ProducerInfo(
                name=p.get("name", ""),
                count=p.get("count", 0),
                percentage=p.get("percentage", 0.0),
                suspicion=p.get("suspicion", "NORMAL"),
            )
            for p in producers
        ]

    @rx.var
    def creators_list(self) -> List[CreatorInfo]:
        """Convert creators dict list to typed list."""
        creators = self.software_distribution.get("creators", [])
        return [
            CreatorInfo(
                name=c.get("name", ""),
                count=c.get("count", 0),
                percentage=c.get("percentage", 0.0),
            )
            for c in creators
        ]

    @rx.var
    def authors_list(self) -> List[AuthorInfo]:
        """Convert authors dict list to typed list."""
        authors = self.author_analysis.get("top_authors", [])
        return [
            AuthorInfo(
                name=a.get("name", ""),
                count=a.get("count", 0),
                percentage=a.get("percentage", 0.0),
            )
            for a in authors
        ]

    @rx.var
    def years_list(self) -> List[YearInfo]:
        """Convert years dict list to typed list."""
        years = self.temporal_distribution.get("by_year", [])
        return [
            YearInfo(
                year=y.get("year", 0),
                count=y.get("count", 0),
                percentage=y.get("percentage", 0.0),
            )
            for y in years
        ]

    @rx.var
    def recent_months_list(self) -> List[MonthInfo]:
        """Convert recent months dict list to typed list."""
        months = self.temporal_distribution.get("recent_months", [])
        return [
            MonthInfo(
                month=m.get("month", ""),
                created=m.get("created", 0),
                modified=m.get("modified", 0),
            )
            for m in months
        ]

    def load_dashboard_data(self):
        """Load all dashboard data on mount."""
        # Skip if already loaded (session cache)
        if self._has_loaded and self.metadata_summary:
            return

        self.is_loading = True
        self.error_message = ""

        try:
            from app.arkham.services.metadata_forensics_service import (
                get_metadata_forensics_service,
            )

            service = get_metadata_forensics_service()

            # Load summary
            self.metadata_summary = service.get_metadata_summary()

            # Load software distribution
            self.software_distribution = service.get_software_distribution()

            # Load temporal distribution
            self.temporal_distribution = service.get_temporal_distribution()

            # Load author analysis
            self.author_analysis = service.get_author_analysis()

            self._has_loaded = True  # Mark as loaded for session cache
            logger.info("Metadata forensics dashboard data loaded")

        except Exception as e:
            logger.error(f"Failed to load dashboard data: {e}")
            self.error_message = f"Failed to load data: {str(e)}"

        finally:
            self.is_loading = False

    def set_active_tab(self, tab: str):
        """Set the active dashboard tab."""
        self.active_tab = tab

    def show_document_details(self, doc_id: int):
        """Show detailed metadata for a specific document."""
        self.selected_document_id = doc_id
        self.is_loading = True

        try:
            from app.arkham.services.metadata_forensics_service import (
                get_metadata_forensics_service,
            )

            service = get_metadata_forensics_service()
            self.selected_document_metadata = (
                service.get_document_metadata(doc_id) or {}
            )
            self.show_document_modal = True

        except Exception as e:
            logger.error(f"Failed to load document metadata: {e}")
            self.error_message = f"Failed to load document: {str(e)}"

        finally:
            self.is_loading = False

    def close_document_modal(self):
        """Close the document details modal."""
        self.show_document_modal = False
        self.selected_document_id = None
        self.selected_document_metadata = {}

    @rx.var
    def selected_doc_authenticity_score(self) -> int:
        forensics = self.selected_document_metadata.get("forensics", {})
        return (
            forensics.get("authenticity_score", 0) if isinstance(forensics, dict) else 0
        )

    @rx.var
    def selected_doc_risk_level(self) -> str:
        forensics = self.selected_document_metadata.get("forensics", {})
        return (
            forensics.get("risk_level", "LOW") if isinstance(forensics, dict) else "LOW"
        )

    @rx.var
    def selected_doc_filename(self) -> str:
        return self.selected_document_metadata.get("filename", "N/A")

    @rx.var
    def selected_doc_author(self) -> str:
        return self.selected_document_metadata.get("author", "N/A")

    @rx.var
    def selected_doc_creator(self) -> str:
        return self.selected_document_metadata.get("pdf_creator", "N/A")

    @rx.var
    def selected_doc_producer(self) -> str:
        return self.selected_document_metadata.get("pdf_producer", "N/A")

    @rx.var
    def selected_doc_creation_date(self) -> str:
        return self.selected_document_metadata.get("pdf_creation_date", "N/A")

    @rx.var
    def selected_doc_modification_date(self) -> str:
        return self.selected_document_metadata.get("pdf_modification_date", "N/A")

    @rx.var
    def selected_doc_anomalies(self) -> List[Dict]:
        forensics = self.selected_document_metadata.get("forensics", {})
        return forensics.get("anomalies", []) if isinstance(forensics, dict) else []

    @rx.var
    def selected_doc_suspicious_indicators(self) -> List[Dict]:
        forensics = self.selected_document_metadata.get("forensics", {})
        return (
            forensics.get("suspicious_indicators", [])
            if isinstance(forensics, dict)
            else []
        )

    def refresh_data(self):
        """Refresh all dashboard data, clearing cache."""
        self._has_loaded = False
        self.load_dashboard_data()

    def get_risk_color(self, risk_level: str) -> str:
        """Get color for risk level badge."""
        colors = {
            "CRITICAL": "red",
            "HIGH": "orange",
            "MEDIUM": "yellow",
            "LOW": "green",
        }
        return colors.get(risk_level, "gray")

    def get_authenticity_color(self, score: int) -> str:
        """Get color for authenticity score."""
        if score >= 85:
            return "green"
        elif score >= 70:
            return "yellow"
        elif score >= 50:
            return "orange"
        else:
            return "red"

    def clear_messages(self):
        """Clear success/error messages."""
        self.success_message = ""
        self.error_message = ""
