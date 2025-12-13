import reflex as rx
import logging
from pydantic import BaseModel
from typing import List, Optional

logger = logging.getLogger(__name__)


class FileAnomaly(BaseModel):
    type: str
    severity: str
    description: str


class ScanResult(BaseModel):
    document_id: int = 0
    document_name: str = ""
    filename: str = ""
    path: str = ""
    size: int = 0
    risk_score: int = 0
    anomaly_count: int = 0
    warning_count: int = 0


class DetailedResult(BaseModel):
    path: str = ""
    filename: str = ""
    size: int = 0
    risk_score: int = 0
    anomalies: List[FileAnomaly] = []
    warnings: List[FileAnomaly] = []
    metadata: dict = {}
    signature_match: bool = True
    has_appended_data: bool = False
    extra_bytes: int = 0


class HiddenContentState(rx.State):
    """State for Hidden Content Detection."""

    # Scan results
    scan_results: List[ScanResult] = []

    # Summary stats
    total_scanned: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    clean_count: int = 0

    # Selected file detail
    selected_result: Optional[DetailedResult] = None

    # UI state
    is_scanning: bool = False
    is_analyzing: bool = False
    show_detail: bool = False
    filter_risk: str = "all"

    def run_library_scan(self):
        """Scan the document library for hidden content."""
        self.is_scanning = True
        self.scan_results = []
        yield

        try:
            from app.arkham.services.hidden_content_service import (
                get_hidden_content_service,
            )

            service = get_hidden_content_service()
            results = service.scan_document_library(limit=50)

            # Get summary stats
            stats = service.get_summary_stats(results)
            self.total_scanned = stats["total_scanned"]
            self.high_risk_count = stats["high_risk"]
            self.medium_risk_count = stats["medium_risk"]
            self.low_risk_count = stats["low_risk"]
            self.clean_count = stats["clean"]

            # Convert to state objects
            self.scan_results = [
                ScanResult(
                    document_id=r.get("document_id", 0),
                    document_name=r.get("document_name", ""),
                    filename=r.get("filename", ""),
                    path=r.get("path", ""),
                    size=r.get("size", 0),
                    risk_score=r.get("risk_score", 0),
                    anomaly_count=len(r.get("anomalies", [])),
                    warning_count=len(r.get("warnings", [])),
                )
                for r in results
            ]

        except Exception as e:
            logger.error(f"Error scanning library: {e}")
        finally:
            self.is_scanning = False

    def analyze_file(self, path: str):
        """Analyze a specific file for hidden content."""
        self.is_analyzing = True
        self.show_detail = True
        yield

        try:
            from app.arkham.services.hidden_content_service import (
                get_hidden_content_service,
            )

            service = get_hidden_content_service()
            result = service.analyze_file(path)

            self.selected_result = DetailedResult(
                path=result.get("path", ""),
                filename=result.get("filename", ""),
                size=result.get("size", 0),
                risk_score=result.get("risk_score", 0),
                anomalies=[
                    FileAnomaly(
                        type=a.get("type", ""),
                        severity=a.get("severity", ""),
                        description=a.get("description", ""),
                    )
                    for a in result.get("anomalies", [])
                ],
                warnings=[
                    FileAnomaly(
                        type=w.get("type", ""),
                        severity=w.get("severity", ""),
                        description=w.get("description", ""),
                    )
                    for w in result.get("warnings", [])
                ],
                metadata=result.get("metadata", {}),
                signature_match=result.get("signature_check", {}).get("match", True),
                has_appended_data=result.get("appended_data", {}).get(
                    "has_appended_data", False
                ),
                extra_bytes=result.get("appended_data", {}).get("extra_bytes", 0),
            )

        except Exception as e:
            logger.error(f"Error analyzing file: {e}")
        finally:
            self.is_analyzing = False

    def close_detail(self):
        self.show_detail = False
        self.selected_result = None

    def set_filter(self, risk: str):
        self.filter_risk = risk

    @rx.var
    def filtered_results(self) -> List[ScanResult]:
        if self.filter_risk == "all":
            return self.scan_results
        elif self.filter_risk == "high":
            return [r for r in self.scan_results if r.risk_score >= 50]
        elif self.filter_risk == "medium":
            return [r for r in self.scan_results if 20 <= r.risk_score < 50]
        elif self.filter_risk == "low":
            return [r for r in self.scan_results if 0 < r.risk_score < 20]
        else:  # clean
            return [r for r in self.scan_results if r.risk_score == 0]

    @rx.var
    def has_results(self) -> bool:
        return len(self.scan_results) > 0

    @rx.var
    def has_selected(self) -> bool:
        return self.selected_result is not None
