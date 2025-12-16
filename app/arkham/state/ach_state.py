"""
ACH (Analysis of Competing Hypotheses) State Management.

Implements Heuer's 8-step ACH methodology with full UI state tracking.
"""

import reflex as rx
import logging
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# NOTE: Service import moved inside methods to prevent slow startup (lazy loading)


# =============================================================================
# PYDANTIC MODELS FOR STATE
# =============================================================================


class ACHHypothesisDisplay(BaseModel):
    """Hypothesis for display in UI."""

    id: int
    label: str
    description: str
    display_order: int = 0
    color: str = "#3b82f6"
    inconsistency_score: float = 0.0
    future_indicators: Optional[str] = None
    indicator_timeframe: Optional[str] = None


class ACHEvidenceDisplay(BaseModel):
    """Evidence for display in UI."""

    id: int
    label: str
    description: str
    display_order: int = 0
    evidence_type: str = "fact"
    reliability: str = "medium"
    source: Optional[str] = None
    source_document_id: Optional[int] = None
    diagnosticity_score: float = 0.0
    is_critical: bool = False
    is_high_diagnostic: bool = False
    is_low_diagnostic: bool = False
    ratings: Dict[int, str] = {}


class ACHScoreDisplay(BaseModel):
    """Score result for display."""

    hypothesis_id: int
    label: str
    description: str
    color: str
    inconsistency_score: float
    rank: int


class ACHConsistencyCheckDisplay(BaseModel):
    """Consistency check result for display."""

    check_type: str
    passed: bool
    message: str


class ACHAnalysisSummaryDisplay(BaseModel):
    """Analysis summary for list display."""

    id: int
    title: str
    focus_question: str
    status: str
    current_step: int
    hypothesis_count: int
    evidence_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ACHMilestoneDisplay(BaseModel):
    """Milestone for display in UI (Phase 5)."""

    id: int
    analysis_id: int
    hypothesis_id: int
    description: str
    expected_by: Optional[str] = None
    observed: int = 0  # 0=pending, 1=observed, -1=contradicted
    observed_date: Optional[str] = None
    observation_notes: Optional[str] = None


class ACHSnapshotDisplay(BaseModel):
    """Snapshot for display in UI (Phase 5 Version History)."""

    id: int
    label: str
    description: Optional[str] = None
    created_at: str
    snapshot_at: str


# =============================================================================
# ACH STATE CLASS
# =============================================================================


class ACHState(rx.State):
    """State for ACH analysis."""

    # =========================================================================
    # ANALYSIS LIST STATE
    # =========================================================================

    analyses: List[ACHAnalysisSummaryDisplay] = []
    is_loading: bool = False
    _analyses_loaded: bool = False

    # =========================================================================
    # CURRENT ANALYSIS STATE
    # =========================================================================

    # Core analysis data
    current_analysis_id: Optional[int] = None
    analysis_title: str = ""
    focus_question: str = ""
    description: str = ""
    status: str = "draft"
    current_step: int = 1
    steps_completed: List[int] = []

    # Step 7: Sensitivity
    sensitivity_notes: str = ""
    key_assumptions: List[str] = []

    # Phase 4: Sensitivity Analysis Results
    sensitivity_results: List[Dict[str, Any]] = []
    show_sensitivity_dialog: bool = False
    is_sensitivity_loading: bool = False

    # Phase 5: Milestones
    milestones: List[ACHMilestoneDisplay] = []

    show_add_milestone_dialog: bool = False
    new_milestone_description: str = ""
    new_milestone_expected_by: str = ""
    new_milestone_hypothesis_id: str = ""  # ID as string for select

    # Phase 5: History
    snapshots: List[ACHSnapshotDisplay] = []
    selected_snapshot_id: str = ""
    comparison_snapshot_id: str = ""
    diff_data: Dict[str, Any] = {}

    show_snapshot_dialog: bool = False
    new_snapshot_label: str = ""
    new_snapshot_description: str = ""
    show_comparison_dialog: bool = False

    show_edit_milestone_dialog: bool = False
    editing_milestone_id: Optional[int] = None
    edit_milestone_description: str = ""
    edit_milestone_expected_by: str = ""
    edit_milestone_observed: str = "0"  # "0", "1", "-1"
    edit_milestone_notes: str = ""

    # Hypotheses and Evidence
    hypotheses: List[ACHHypothesisDisplay] = []
    evidence: List[ACHEvidenceDisplay] = []

    # Scores and Diagnosticity
    scores: List[ACHScoreDisplay] = []
    consistency_checks: List[ACHConsistencyCheckDisplay] = []

    # Matrix completion
    matrix_completion_pct: float = 0.0
    total_cells: int = 0
    rated_cells: int = 0
    score_chart: Dict[str, Any] = {}

    # =========================================================================
    # UI STATE
    # =========================================================================

    # Dialogs
    show_new_analysis_dialog: bool = False
    show_add_hypothesis_dialog: bool = False
    show_add_evidence_dialog: bool = False
    show_edit_hypothesis_dialog: bool = False
    show_edit_evidence_dialog: bool = False
    show_delete_confirm_dialog: bool = False
    show_export_dialog: bool = False
    show_pdf_preview_dialog: bool = False

    # Phase 4: Keyboard navigation - focused matrix cell
    focused_evidence_id: Optional[int] = None
    focused_hypothesis_id: Optional[int] = None

    # Form inputs
    new_analysis_title: str = ""
    new_focus_question: str = ""
    new_analysis_description: str = ""

    new_hypothesis_description: str = ""

    new_evidence_description: str = ""
    new_evidence_type: str = "fact"
    new_evidence_reliability: str = "medium"
    new_evidence_source: str = ""

    # Editing
    editing_hypothesis_id: Optional[int] = None
    editing_evidence_id: Optional[int] = None
    edit_hypothesis_description: str = ""
    edit_hypothesis_future_indicators: str = ""
    edit_evidence_description: str = ""
    edit_evidence_type: str = "fact"
    edit_evidence_reliability: str = "medium"
    edit_evidence_source: str = ""

    # Delete confirmation
    delete_type: str = ""  # "analysis", "hypothesis", "evidence"
    delete_id: Optional[int] = None
    delete_label: str = ""

    # Step guidance visibility
    show_step_guidance: bool = True

    # View mode
    sort_evidence_by: str = "order"  # "order" or "diagnosticity"
    evidence_filter: str = "all"  # "all", "unrated", "has_ai", "high_diagnostic"

    # Phase 4: Plotly chart for scores
    score_chart: Dict[str, Any] = {}
    show_plotly_chart: bool = True  # Toggle between progress bars and Plotly chart

    # Sensitivity notes expanded view
    notes_expanded: bool = False

    def toggle_notes_expanded(self):
        """Toggle between collapsed and expanded notes view."""
        self.notes_expanded = not self.notes_expanded

    # =========================================================================
    # COMPUTED VARIABLES
    # =========================================================================

    @rx.var
    def has_analysis(self) -> bool:
        """Check if an analysis is loaded."""
        return self.current_analysis_id is not None

    @rx.var
    def has_hypotheses(self) -> bool:
        """Check if hypotheses exist."""
        return len(self.hypotheses) > 0

    @rx.var
    def has_evidence(self) -> bool:
        """Check if evidence exists."""
        return len(self.evidence) > 0

    @rx.var
    def hypothesis_count(self) -> int:
        """Number of hypotheses."""
        return len(self.hypotheses)

    @rx.var
    def evidence_count(self) -> int:
        """Number of evidence items."""
        return len(self.evidence)

    @rx.var
    def filtered_evidence_count(self) -> int:
        """Count of evidence matching current filter."""
        return len(self.displayed_evidence)

    @rx.var
    def is_step_complete(self) -> Dict[int, bool]:
        """Check if each step is complete."""
        return {i: i in self.steps_completed for i in range(1, 9)}

    @rx.var
    def can_proceed_to_step(self) -> Dict[int, bool]:
        """Check if user can proceed to each step."""
        return {
            1: True,  # Always can start
            2: len(self.hypotheses) >= 2,  # Need hypotheses
            3: len(self.evidence) >= 1,  # Need evidence
            4: self.rated_cells > 0,  # Need some ratings
            5: self.rated_cells > 0,  # Need ratings to refine
            6: self.matrix_completion_pct >= 50,  # Need half rated
            7: True,  # Can always do sensitivity
            8: True,  # Can always report
        }

    @rx.var
    def displayed_evidence(self) -> List[ACHEvidenceDisplay]:
        """Get evidence filtered and sorted by current mode."""
        # Start with all evidence
        filtered = list(self.evidence)

        # Apply filter
        if self.evidence_filter == "unrated":
            # Evidence with any unrated cells
            filtered = [
                e
                for e in filtered
                if any(r == "" for r in e.ratings.values())
                or len(e.ratings) < len(self.hypotheses)
            ]
        elif self.evidence_filter == "has_ai":
            # Evidence with AI suggestions (is_high_diagnostic is used for now)
            # In future, could track actual AI origins
            filtered = [e for e in filtered if e.is_high_diagnostic]
        elif self.evidence_filter == "high_diagnostic":
            # Only high diagnostic evidence
            filtered = [e for e in filtered if e.diagnosticity_score >= 1.0]

        # Apply sort
        if self.sort_evidence_by == "diagnosticity":
            return sorted(
                filtered,
                key=lambda e: e.diagnosticity_score,
                reverse=True,
            )
        return sorted(filtered, key=lambda e: e.display_order)

    @rx.var
    def best_hypothesis(self) -> Optional[str]:
        """Get the label of the best-scoring hypothesis."""
        if self.scores:
            return self.scores[0].label
        return None

    @rx.var
    def close_race_warning(self) -> Optional[str]:
        """Check for close race between top hypotheses."""
        if len(self.scores) >= 2:
            diff = abs(
                self.scores[1].inconsistency_score - self.scores[0].inconsistency_score
            )
            if diff <= 1.0:
                return (
                    f"Close race: {self.scores[0].label} and {self.scores[1].label} "
                    f"differ by only {diff:.1f} points."
                )
        return None

    @rx.var
    def step_names(self) -> Dict[int, str]:
        """Step number to name mapping."""
        return {
            1: "Identify Hypotheses",
            2: "List Evidence",
            3: "Create Matrix",
            4: "Analyze Diagnosticity",
            5: "Refine the Matrix",
            6: "Draw Conclusions",
            7: "Sensitivity Analysis",
            8: "Report & Milestones",
        }

    # =========================================================================
    # DIFF DATA COMPUTED VARS (for snapshot comparison dialog)
    # =========================================================================

    @rx.var
    def diff_meta_s1_label(self) -> str:
        """Get s1_label from diff_data safely."""
        return self.diff_data.get("meta", {}).get("s1_label", "")

    @rx.var
    def diff_meta_s2_label(self) -> str:
        """Get s2_label from diff_data safely."""
        return self.diff_data.get("meta", {}).get("s2_label", "")

    @rx.var
    def diff_scores_winner_changed(self) -> bool:
        """Check if winner changed in comparison."""
        return self.diff_data.get("scores", {}).get("winner_changed", False)

    @rx.var
    def diff_scores_old_winner(self) -> str:
        """Get old winner from diff_data."""
        return self.diff_data.get("scores", {}).get("old_winner", "")

    @rx.var
    def diff_scores_new_winner(self) -> str:
        """Get new winner from diff_data."""
        return self.diff_data.get("scores", {}).get("new_winner", "")

    @rx.var
    def diff_hypotheses_added(self) -> List[str]:
        """Get added hypotheses from diff_data."""
        return self.diff_data.get("hypotheses", {}).get("added", [])

    @rx.var
    def diff_hypotheses_removed(self) -> List[str]:
        """Get removed hypotheses from diff_data."""
        return self.diff_data.get("hypotheses", {}).get("removed", [])

    @rx.var
    def diff_evidence_added(self) -> List[str]:
        """Get added evidence from diff_data."""
        return self.diff_data.get("evidence", {}).get("added", [])

    @rx.var
    def diff_evidence_removed(self) -> List[str]:
        """Get removed evidence from diff_data."""
        return self.diff_data.get("evidence", {}).get("removed", [])

    # Max rating changes to display before showing "and X more..."
    RATING_CHANGES_LIMIT: int = 10

    @rx.var
    def diff_ratings_changes(self) -> List[Dict[str, Any]]:
        """Get rating changes from diff_data (limited for display)."""
        all_changes = self.diff_data.get("ratings", [])
        return all_changes[:self.RATING_CHANGES_LIMIT]

    @rx.var
    def diff_ratings_total_count(self) -> int:
        """Get total count of rating changes."""
        return len(self.diff_data.get("ratings", []))

    @rx.var
    def diff_ratings_has_more(self) -> bool:
        """Check if there are more rating changes than displayed."""
        return len(self.diff_data.get("ratings", [])) > self.RATING_CHANGES_LIMIT

    @rx.var
    def diff_ratings_remaining_count(self) -> int:
        """Get count of rating changes not displayed."""
        total = len(self.diff_data.get("ratings", []))
        return max(0, total - self.RATING_CHANGES_LIMIT)

    @rx.var
    def diff_milestones_added(self) -> List[str]:
        """Get added milestones from diff_data."""
        return self.diff_data.get("milestones", {}).get("added", [])

    @rx.var
    def diff_milestones_removed(self) -> List[str]:
        """Get removed milestones from diff_data."""
        return self.diff_data.get("milestones", {}).get("removed", [])

    @rx.var
    def diff_milestones_status_changes(self) -> List[Dict[str, Any]]:
        """Get milestone status changes from diff_data."""
        return self.diff_data.get("milestones", {}).get("status_changes", [])

    @rx.var
    def diff_has_changes(self) -> bool:
        """Check if there are any changes in the diff."""
        if not self.diff_data:
            return False
        h = self.diff_data.get("hypotheses", {})
        e = self.diff_data.get("evidence", {})
        r = self.diff_data.get("ratings", [])
        m = self.diff_data.get("milestones", {})
        s = self.diff_data.get("scores", {})
        return bool(
            h.get("added") or h.get("removed") or h.get("modified") or
            e.get("added") or e.get("removed") or e.get("modified") or
            r or
            m.get("added") or m.get("removed") or m.get("status_changes") or
            s.get("winner_changed") or s.get("score_changes")
        )

    # =========================================================================
    # SNAPSHOT SELECT HELPERS (for rx.select component)
    # =========================================================================

    @rx.var
    def snapshot_labels(self) -> List[str]:
        """Get list of snapshot labels for select dropdown."""
        return [s.label for s in self.snapshots]

    @rx.var
    def comparison_snapshot_label(self) -> str:
        """Get the label for the currently selected comparison snapshot."""
        if not self.comparison_snapshot_id:
            return ""
        for s in self.snapshots:
            if str(s.id) == self.comparison_snapshot_id:
                return s.label
        return ""

    @rx.var
    def selected_snapshot_label(self) -> str:
        """Get the label for the currently selected snapshot."""
        if not self.selected_snapshot_id:
            return ""
        for s in self.snapshots:
            if str(s.id) == self.selected_snapshot_id:
                return s.label
        return ""

    def set_comparison_by_label(self, label: str):
        """Set comparison snapshot ID by looking up the label."""
        if not label:
            self.comparison_snapshot_id = ""
            return
        for s in self.snapshots:
            if s.label == label:
                self.comparison_snapshot_id = str(s.id)
                return
        # Label not found, clear selection
        self.comparison_snapshot_id = ""

    def set_selected_by_label(self, label: str):
        """Set selected snapshot ID by looking up the label."""
        if not label:
            self.selected_snapshot_id = ""
            return
        for s in self.snapshots:
            if s.label == label:
                self.selected_snapshot_id = str(s.id)
                return
        # Label not found, clear selection
        self.selected_snapshot_id = ""

    # =========================================================================
    # ANALYSIS LIST METHODS
    # =========================================================================

    def load_analyses(self):
        """Load list of all analyses."""
        if self._analyses_loaded and self.analyses:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            data = service.get_analysis_list()
            self.analyses = [ACHAnalysisSummaryDisplay(**a) for a in data]
            self._analyses_loaded = True
        except Exception as e:
            logger.error(f"Error loading analyses: {e}")
        finally:
            self.is_loading = False

    def refresh_analyses(self):
        """Force refresh analysis list."""
        self._analyses_loaded = False
        return ACHState.load_analyses

    # =========================================================================
    # ANALYSIS CRUD
    # =========================================================================

    def open_new_analysis_dialog(self):
        """Open dialog to create new analysis."""
        self.new_analysis_title = ""
        self.new_focus_question = ""
        self.new_analysis_description = ""
        self.show_new_analysis_dialog = True

    def close_new_analysis_dialog(self):
        """Close new analysis dialog."""
        self.show_new_analysis_dialog = False

    def set_new_analysis_title(self, value: str):
        """Set new analysis title."""
        self.new_analysis_title = value

    def set_new_focus_question(self, value: str):
        """Set new focus question."""
        self.new_focus_question = value

    def set_new_analysis_description(self, value: str):
        """Set new analysis description."""
        self.new_analysis_description = value

    def create_analysis(self):
        """Create a new ACH analysis."""
        if not self.new_analysis_title.strip() or not self.new_focus_question.strip():
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            result = service.create_analysis(
                title=self.new_analysis_title.strip(),
                focus_question=self.new_focus_question.strip(),
                description=self.new_analysis_description.strip() or None,
            )

            if result:
                self.current_analysis_id = result["id"]
                self._load_analysis_data(result)
                self.show_new_analysis_dialog = False
                self._analyses_loaded = False  # Refresh list
                logger.info(f"Created analysis: {result['id']}")
        except Exception as e:
            logger.error(f"Error creating analysis: {e}")
        finally:
            self.is_loading = False

    def load_analysis(self, analysis_id: int):
        """Load a specific analysis."""
        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            data = service.get_analysis(analysis_id)
            if data:
                self.current_analysis_id = analysis_id
                self._load_analysis_data(data)
        except Exception as e:
            logger.error(f"Error loading analysis {analysis_id}: {e}")
        finally:
            self.is_loading = False

    def _load_analysis_data(self, data: Dict[str, Any]):
        """Load analysis data into state."""
        self.analysis_title = data.get("title", "")
        self.focus_question = data.get("focus_question", "")
        self.description = data.get("description", "") or ""
        self.status = data.get("status", "draft")
        self.current_step = data.get("current_step", 1)
        self.steps_completed = data.get("steps_completed", [])
        self.sensitivity_notes = data.get("sensitivity_notes", "") or ""
        self.key_assumptions = data.get("key_assumptions", []) or []

        # Load hypotheses
        self.hypotheses = [
            ACHHypothesisDisplay(**h) for h in data.get("hypotheses", [])
        ]

        # Load evidence with ratings
        evidence_list = []
        for e in data.get("evidence", []):
            e_display = ACHEvidenceDisplay(**e)
            evidence_list.append(e_display)
        self.evidence = evidence_list

        # Calculate scores and diagnosticity
        self._refresh_calculations()

    def _load_milestones(self):
        """Load milestones for current analysis."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            milestone_data = service.get_analysis_milestones(self.current_analysis_id)
            self.milestones = [ACHMilestoneDisplay(**m) for m in milestone_data]
        except Exception as e:
            logger.error(f"Error loading milestones: {e}")

    def _refresh_calculations(self):
        """Refresh scores, diagnosticity, matrix completion, and milestones."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()

            # Refresh milestones
            milestone_data = service.get_analysis_milestones(self.current_analysis_id)
            self.milestones = [ACHMilestoneDisplay(**m) for m in milestone_data]

            # Get scores
            scores = service.calculate_scores(self.current_analysis_id)
            self.scores = [ACHScoreDisplay(**s) for s in scores]

            # Get diagnosticity and update evidence
            diagnosticity = service.calculate_diagnosticity(self.current_analysis_id)
            diag_map = {d["evidence_id"]: d for d in diagnosticity}
            for e in self.evidence:
                if e.id in diag_map:
                    d = diag_map[e.id]
                    e.diagnosticity_score = d["diagnosticity_score"]
                    e.is_high_diagnostic = d["is_high_diagnostic"]
                    e.is_low_diagnostic = d["is_low_diagnostic"]

            # Get matrix completion
            matrix = service.get_matrix(self.current_analysis_id)
            self.matrix_completion_pct = matrix.get("completion_pct", 0)
            self.total_cells = matrix.get("total_cells", 0)
            self.rated_cells = matrix.get("rated_cells", 0)

            # Get consistency checks
            checks = service.run_consistency_checks(self.current_analysis_id)
            self.consistency_checks = [ACHConsistencyCheckDisplay(**c) for c in checks]

            # Phase 4: Generate Plotly score chart
            self.score_chart = service.get_score_chart(self.current_analysis_id)

        except Exception as e:
            logger.error(f"Error refreshing calculations: {e}")

    def close_analysis(self):
        """Close current analysis and return to list."""
        self.current_analysis_id = None
        self.analysis_title = ""
        self.focus_question = ""
        self.hypotheses = []
        self.evidence = []
        self.scores = []
        self.consistency_checks = []
        self.score_chart = {}

    def toggle_plotly_chart(self):
        """Toggle between Plotly chart and progress bar views."""
        self.show_plotly_chart = not self.show_plotly_chart

    def delete_analysis_confirm(self, analysis_id: int, title: str):
        """Show delete confirmation for analysis."""
        self.delete_type = "analysis"
        self.delete_id = analysis_id
        self.delete_label = title
        self.show_delete_confirm_dialog = True

    def confirm_delete(self):
        """Confirm and execute delete."""
        if not self.delete_id:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()

            if self.delete_type == "analysis":
                service.delete_analysis(self.delete_id)
                if self.current_analysis_id == self.delete_id:
                    self.close_analysis()
                self._analyses_loaded = False
            elif self.delete_type == "hypothesis":
                service.delete_hypothesis(self.delete_id)
                self.hypotheses = [h for h in self.hypotheses if h.id != self.delete_id]
                self._refresh_calculations()
            elif self.delete_type == "evidence":
                service.delete_evidence(self.delete_id)
                self.evidence = [e for e in self.evidence if e.id != self.delete_id]
                self._refresh_calculations()
            elif self.delete_type == "milestone":
                service.delete_milestone(self.delete_id)
                self.milestones = [m for m in self.milestones if m.id != self.delete_id]

            self.show_delete_confirm_dialog = False
            self.delete_id = None
            self.delete_type = ""
            self.delete_label = ""
        except Exception as e:
            logger.error(f"Error deleting: {e}")
        finally:
            self.is_loading = False

    def cancel_delete(self):
        """Cancel delete operation."""
        self.show_delete_confirm_dialog = False
        self.delete_id = None
        self.delete_type = ""
        self.delete_label = ""

    # =========================================================================
    # HISTORY METHODS (Phase 5)
    # =========================================================================

    def load_snapshots(self):
        """Load snapshots for current analysis."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            snapshot_dicts = service.get_snapshots(self.current_analysis_id)
            self.snapshots = [ACHSnapshotDisplay(**s) for s in snapshot_dicts]
        except Exception as e:
            logger.error(f"Error loading snapshots: {e}")

    def open_snapshot_dialog(self):
        """Open snapshot creation dialog."""
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.new_snapshot_label = f"Snapshot {timestamp}"
        self.new_snapshot_description = ""
        self.show_snapshot_dialog = True

    def close_snapshot_dialog(self):
        """Close snapshot dialog."""
        self.show_snapshot_dialog = False

    def set_new_snapshot_label(self, value: str):
        self.new_snapshot_label = value

    def set_new_snapshot_description(self, value: str):
        self.new_snapshot_description = value

    def save_snapshot(self):
        """Create a new snapshot."""
        if not self.current_analysis_id or not self.new_snapshot_label:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            service.create_snapshot(
                self.current_analysis_id,
                self.new_snapshot_label,
                self.new_snapshot_description,
            )
            self.show_snapshot_dialog = False
            self.load_snapshots()
            logger.info("Snapshot created")
        except Exception as e:
            logger.error(f"Error creating snapshot: {e}")
        finally:
            self.is_loading = False

    def compare_snapshots(self):
        """Compare two selected snapshots."""
        if not self.selected_snapshot_id or not self.comparison_snapshot_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            self.diff_data = service.get_snapshot_diff(
                int(self.selected_snapshot_id), int(self.comparison_snapshot_id)
            )
            self.show_comparison_dialog = True
        except Exception as e:
            logger.error(f"Error comparing snapshots: {e}")

    def close_comparison_dialog(self):
        self.show_comparison_dialog = False

    def set_selected_snapshot_id(self, value):
        # Convert to string to handle int values from select component
        self.selected_snapshot_id = str(value) if value else ""

    def set_comparison_snapshot_id(self, value):
        # Convert to string to handle int values from select component
        self.comparison_snapshot_id = str(value) if value else ""

    def compare_snapshot_to_current(self, snapshot_id: int):
        """Compare a specific snapshot to the current analysis state."""
        if not self.current_analysis_id:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            self.diff_data = service.compare_to_current(
                self.current_analysis_id,
                snapshot_id
            )
            self.show_comparison_dialog = True
        except Exception as e:
            logger.error(f"Error comparing to current: {e}")
        finally:
            self.is_loading = False

    def open_add_hypothesis_dialog(self):
        """Open dialog to add hypothesis."""
        self.new_hypothesis_description = ""
        self.show_add_hypothesis_dialog = True

    def close_add_hypothesis_dialog(self):
        """Close add hypothesis dialog."""
        self.show_add_hypothesis_dialog = False

    def set_new_hypothesis_description(self, value: str):
        """Set new hypothesis description."""
        self.new_hypothesis_description = value

    def add_hypothesis(self):
        """Add a new hypothesis."""
        if not self.current_analysis_id or not self.new_hypothesis_description.strip():
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            result = service.add_hypothesis(
                analysis_id=self.current_analysis_id,
                description=self.new_hypothesis_description.strip(),
            )

            if result:
                self.hypotheses = self.hypotheses + [ACHHypothesisDisplay(**result)]
                self.show_add_hypothesis_dialog = False
                self._refresh_calculations()
        except Exception as e:
            logger.error(f"Error adding hypothesis: {e}")
        finally:
            self.is_loading = False

    def edit_hypothesis(self, hypothesis_id: int):
        """Open edit dialog for hypothesis."""
        h = next((h for h in self.hypotheses if h.id == hypothesis_id), None)
        if h:
            self.editing_hypothesis_id = hypothesis_id
            self.edit_hypothesis_description = h.description
            self.edit_hypothesis_future_indicators = h.future_indicators or ""
            self.show_edit_hypothesis_dialog = True

    def close_edit_hypothesis_dialog(self):
        """Close edit hypothesis dialog."""
        self.show_edit_hypothesis_dialog = False
        self.editing_hypothesis_id = None

    def set_edit_hypothesis_description(self, value: str):
        """Set edit hypothesis description."""
        self.edit_hypothesis_description = value

    def set_edit_hypothesis_future_indicators(self, value: str):
        """Set edit hypothesis future indicators."""
        self.edit_hypothesis_future_indicators = value

    def save_hypothesis(self):
        """Save hypothesis changes."""
        if not self.editing_hypothesis_id:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            result = service.update_hypothesis(
                hypothesis_id=self.editing_hypothesis_id,
                description=self.edit_hypothesis_description.strip(),
                future_indicators=self.edit_hypothesis_future_indicators.strip()
                or None,
            )

            if result:
                # Update in list
                for i, h in enumerate(self.hypotheses):
                    if h.id == self.editing_hypothesis_id:
                        self.hypotheses[i] = ACHHypothesisDisplay(**result)
                        break
                self.show_edit_hypothesis_dialog = False
                self.editing_hypothesis_id = None
        except Exception as e:
            logger.error(f"Error updating hypothesis: {e}")
        finally:
            self.is_loading = False

    def delete_hypothesis_confirm(self, hypothesis_id: int, label: str):
        """Show delete confirmation for hypothesis."""
        self.delete_type = "hypothesis"
        self.delete_id = hypothesis_id
        self.delete_label = label
        self.show_delete_confirm_dialog = True

    # =========================================================================
    # EVIDENCE METHODS (Step 2)
    # =========================================================================

    def open_add_evidence_dialog(self):
        """Open dialog to add evidence."""
        self.new_evidence_description = ""
        self.new_evidence_type = "fact"
        self.new_evidence_reliability = "medium"
        self.new_evidence_source = ""
        self.show_add_evidence_dialog = True

    def close_add_evidence_dialog(self):
        """Close add evidence dialog."""
        self.show_add_evidence_dialog = False

    def set_new_evidence_description(self, value: str):
        """Set new evidence description."""
        self.new_evidence_description = value

    def set_new_evidence_type(self, value: str):
        """Set new evidence type."""
        self.new_evidence_type = value

    def set_new_evidence_reliability(self, value: str):
        """Set new evidence reliability."""
        self.new_evidence_reliability = value

    def set_new_evidence_source(self, value: str):
        """Set new evidence source."""
        self.new_evidence_source = value

    def add_evidence(self):
        """Add new evidence."""
        if not self.current_analysis_id or not self.new_evidence_description.strip():
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            result = service.add_evidence(
                analysis_id=self.current_analysis_id,
                description=self.new_evidence_description.strip(),
                evidence_type=self.new_evidence_type,
                reliability=self.new_evidence_reliability,
                source=self.new_evidence_source.strip() or None,
            )

            if result:
                self.evidence = self.evidence + [ACHEvidenceDisplay(**result)]
                self.show_add_evidence_dialog = False
                self._refresh_calculations()
        except Exception as e:
            logger.error(f"Error adding evidence: {e}")
        finally:
            self.is_loading = False

    def edit_evidence(self, evidence_id: int):
        """Open edit dialog for evidence."""
        e = next((e for e in self.evidence if e.id == evidence_id), None)
        if e:
            self.editing_evidence_id = evidence_id
            self.edit_evidence_description = e.description
            self.edit_evidence_type = e.evidence_type
            self.edit_evidence_reliability = e.reliability
            self.edit_evidence_source = e.source or ""
            self.show_edit_evidence_dialog = True

    def show_evidence_context(self, evidence_id: int):
        """Show context for corpus-linked evidence."""
        e = next((e for e in self.evidence if e.id == evidence_id), None)
        if e and e.source_document_id:
            return rx.redirect(f"/documents/{e.source_document_id}")

    def close_edit_evidence_dialog(self):
        """Close edit evidence dialog."""
        self.show_edit_evidence_dialog = False
        self.editing_evidence_id = None

    def set_edit_evidence_description(self, value: str):
        """Set edit evidence description."""
        self.edit_evidence_description = value

    def set_edit_evidence_type(self, value: str):
        """Set edit evidence type."""
        self.edit_evidence_type = value

    def set_edit_evidence_reliability(self, value: str):
        """Set edit evidence reliability."""
        self.edit_evidence_reliability = value

    def set_edit_evidence_source(self, value: str):
        """Set edit evidence source."""
        self.edit_evidence_source = value

    def save_evidence(self):
        """Save evidence changes."""
        if not self.editing_evidence_id:
            return

        self.is_loading = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            result = service.update_evidence(
                evidence_id=self.editing_evidence_id,
                description=self.edit_evidence_description.strip(),
                evidence_type=self.edit_evidence_type,
                reliability=self.edit_evidence_reliability,
                source=self.edit_evidence_source.strip() or None,
            )

            if result:
                for i, e in enumerate(self.evidence):
                    if e.id == self.editing_evidence_id:
                        self.evidence[i] = ACHEvidenceDisplay(**result)
                        break
                self.show_edit_evidence_dialog = False
                self.editing_evidence_id = None
        except Exception as e:
            logger.error(f"Error updating evidence: {e}")
        finally:
            self.is_loading = False

    def delete_evidence_confirm(self, evidence_id: int, label: str):
        """Show delete confirmation for evidence."""
        self.delete_type = "evidence"
        self.delete_id = evidence_id
        self.delete_label = label
        self.show_delete_confirm_dialog = True

    # =========================================================================
    # RATING METHODS (Step 3)
    # =========================================================================

    def set_rating(self, evidence_id: int, hypothesis_id: int, rating: str):
        """Set a rating in the matrix."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            success = service.set_rating(
                analysis_id=self.current_analysis_id,
                hypothesis_id=hypothesis_id,
                evidence_id=evidence_id,
                rating=rating,
            )

            if success:
                # Update local state
                for e in self.evidence:
                    if e.id == evidence_id:
                        e.ratings[hypothesis_id] = rating
                        break

                # Refresh calculations (debounced in production)
                self._refresh_calculations()
        except Exception as e:
            logger.error(f"Error setting rating: {e}")

    # =========================================================================
    # STEP NAVIGATION
    # =========================================================================

    def go_to_step(self, step: int):
        """Navigate to a specific step."""
        if 1 <= step <= 8:
            self.current_step = step

    def next_step(self):
        """Go to next step."""
        if self.current_step < 8:
            self.current_step += 1

    def prev_step(self):
        """Go to previous step."""
        if self.current_step > 1:
            self.current_step -= 1

    def toggle_step_guidance(self):
        """Toggle step guidance visibility."""
        self.show_step_guidance = not self.show_step_guidance

    def mark_current_step_complete(self):
        """Mark current step as complete."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            service.mark_step_complete(self.current_analysis_id, self.current_step)

            if self.current_step not in self.steps_completed:
                self.steps_completed = self.steps_completed + [self.current_step]
        except Exception as e:
            logger.error(f"Error marking step complete: {e}")

    # =========================================================================
    # STEP 7: SENSITIVITY
    # =========================================================================

    def set_sensitivity_notes(self, value: str):
        """Set sensitivity notes."""
        self.sensitivity_notes = value

    def save_sensitivity_notes(self):
        """Save sensitivity notes to database."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            service.update_analysis(
                analysis_id=self.current_analysis_id,
                sensitivity_notes=self.sensitivity_notes,
            )
        except Exception as e:
            logger.error(f"Error saving sensitivity notes: {e}")

    # =========================================================================
    # STEP 8: MILESTONES (Phase 5)
    # =========================================================================

    def open_add_milestone_dialog(self, hypothesis_id: int = None):
        """Open dialog to add a milestone."""
        self.new_milestone_description = ""
        self.new_milestone_expected_by = ""
        self.new_milestone_hypothesis_id = str(hypothesis_id) if hypothesis_id else ""
        self.show_add_milestone_dialog = True

    def close_add_milestone_dialog(self):
        """Close add milestone dialog."""
        self.show_add_milestone_dialog = False

    def set_new_milestone_description(self, value: str):
        self.new_milestone_description = value

    def set_new_milestone_expected_by(self, value: str):
        self.new_milestone_expected_by = value

    def set_new_milestone_hypothesis_id(self, value):
        """Set hypothesis ID for new milestone (handles both str and int from UI)."""
        self.new_milestone_hypothesis_id = str(value) if value is not None else ""

    def add_milestone(self):
        """Add a new milestone."""
        if not self.current_analysis_id or not self.new_milestone_description.strip():
            return

        if not self.new_milestone_hypothesis_id:
            return

        self.is_loading = True
        yield

        try:
            from datetime import datetime
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()

            # Parse date if provided
            expected_by = None
            if self.new_milestone_expected_by:
                try:
                    expected_by = datetime.strptime(
                        self.new_milestone_expected_by, "%Y-%m-%d"
                    )
                except ValueError:
                    pass

            result = service.add_milestone(
                analysis_id=self.current_analysis_id,
                hypothesis_id=int(self.new_milestone_hypothesis_id),
                description=self.new_milestone_description.strip(),
                expected_by=expected_by,
            )

            if result:
                # Add to state
                self.milestones = self.milestones + [ACHMilestoneDisplay(**result)]
                self.show_add_milestone_dialog = False
        except Exception as e:
            logger.error(f"Error adding milestone: {e}")
        finally:
            self.is_loading = False

    def edit_milestone(self, milestone_id: int):
        """Open edit dialog for milestone."""
        m = next((m for m in self.milestones if m.id == milestone_id), None)
        if m:
            self.editing_milestone_id = milestone_id
            self.edit_milestone_description = m.description
            # Handle date for input (YYYY-MM-DD or empty)
            self.edit_milestone_expected_by = (
                m.expected_by.split("T")[0] if m.expected_by else ""
            )
            self.edit_milestone_observed = str(m.observed)
            self.edit_milestone_notes = m.observation_notes or ""
            self.show_edit_milestone_dialog = True

    def close_edit_milestone_dialog(self):
        """Close edit milestone dialog."""
        self.show_edit_milestone_dialog = False
        self.editing_milestone_id = None

    def set_edit_milestone_description(self, value: str):
        self.edit_milestone_description = value

    def set_edit_milestone_expected_by(self, value: str):
        self.edit_milestone_expected_by = value

    def set_edit_milestone_observed(self, value: str):
        self.edit_milestone_observed = value

    def set_edit_milestone_notes(self, value: str):
        self.edit_milestone_notes = value

    def save_milestone(self):
        """Save milestone changes."""
        if not self.editing_milestone_id:
            return

        self.is_loading = True
        yield

        try:
            from datetime import datetime
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()

            # Parse date if provided
            expected_by = None
            if self.edit_milestone_expected_by:
                try:
                    expected_by = datetime.strptime(
                        self.edit_milestone_expected_by, "%Y-%m-%d"
                    )
                except ValueError:
                    pass

            result = service.update_milestone(
                milestone_id=self.editing_milestone_id,
                description=self.edit_milestone_description.strip(),
                expected_by=expected_by,
                observed=int(self.edit_milestone_observed),
                observation_notes=self.edit_milestone_notes.strip() or None,
            )

            if result:
                # Update in list
                updated = ACHMilestoneDisplay(**result)
                self.milestones = [
                    updated if m.id == self.editing_milestone_id else m
                    for m in self.milestones
                ]
                self.show_edit_milestone_dialog = False
                self.editing_milestone_id = None
        except Exception as e:
            logger.error(f"Error updating milestone: {e}")
        finally:
            self.is_loading = False

    def delete_milestone_confirm(self, milestone_id: int):
        """Show delete confirmation for milestone."""
        m = next((m for m in self.milestones if m.id == milestone_id), None)
        label = m.description[:30] + "..." if m else "Milestone"

        self.delete_type = "milestone"
        self.delete_id = milestone_id
        self.delete_label = label
        self.show_delete_confirm_dialog = True

    # =========================================================================
    # STEP 8: EXPORT
    # =========================================================================

    def open_export_dialog(self):
        """Open export dialog."""
        self.show_export_dialog = True

    def close_export_dialog(self):
        """Close export dialog."""
        self.show_export_dialog = False

    def export_markdown(self):
        """Export analysis as Markdown."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            content = service.export_markdown(self.current_analysis_id)

            filename = f"ach_analysis_{self.current_analysis_id}.md"
            return rx.download(data=content, filename=filename)
        except Exception as e:
            logger.error(f"Error exporting markdown: {e}")

    def export_json(self):
        """Export analysis as JSON."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            data = service.export_json(self.current_analysis_id)

            content = json.dumps(data, indent=2)
            filename = f"ach_analysis_{self.current_analysis_id}.json"
            return rx.download(data=content, filename=filename)
        except Exception as e:
            logger.error(f"Error exporting JSON: {e}")

    def open_pdf_preview_dialog(self):
        """Open PDF preview dialog."""
        self.show_pdf_preview_dialog = True

    def close_pdf_preview_dialog(self):
        """Close PDF preview dialog."""
        self.show_pdf_preview_dialog = False

    def confirm_export_pdf(self):
        """Export analysis as PDF using ReportLab."""
        if not self.current_analysis_id:
            return

        try:
            import tempfile
            import os
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            self.show_pdf_preview_dialog = False

            # Create temp file for PDF
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".pdf", delete=False
            ) as temp_file:
                temp_path = temp_file.name

            # Generate PDF
            result_path = service.export_pdf(self.current_analysis_id, temp_path)

            if result_path:
                # Read PDF and trigger download
                with open(result_path, "rb") as f:
                    pdf_data = f.read()

                filename = f"ach_analysis_{self.current_analysis_id}.pdf"

                # Clean up temp file
                try:
                    os.unlink(result_path)
                except Exception:
                    pass

                return rx.download(data=pdf_data, filename=filename)
            else:
                logger.error("PDF export failed - no file generated")
        except Exception as e:
            logger.error(f"Error exporting PDF: {e}")

    # =========================================================================
    # SORTING
    # =========================================================================

    def set_sort_evidence_by(self, value: str):
        """Set evidence sort mode."""
        self.sort_evidence_by = value

    def set_evidence_filter(self, value: str):
        """Set evidence filter mode."""
        self.evidence_filter = value

    # =========================================================================
    # PHASE 4: KEYBOARD NAVIGATION
    # =========================================================================

    def focus_cell(self, evidence_id: int, hypothesis_id: int):
        """Focus a specific matrix cell for keyboard input."""
        self.focused_evidence_id = evidence_id
        self.focused_hypothesis_id = hypothesis_id

    def clear_focus(self):
        """Clear the focused cell."""
        self.focused_evidence_id = None
        self.focused_hypothesis_id = None

    def quick_rate(self, rating_key: str):
        """
        Set rating on focused cell using keyboard shortcut.

        Keys: 1=CC, 2=C, 3=N, 4=I, 5=II
        """
        if not self.focused_evidence_id or not self.focused_hypothesis_id:
            return

        rating_map = {
            "1": "CC",
            "2": "C",
            "3": "N",
            "4": "I",
            "5": "II",
        }

        rating = rating_map.get(rating_key)
        if rating:
            self.set_rating(
                self.focused_evidence_id, self.focused_hypothesis_id, rating
            )
            # Move to next cell after rating
            self._move_to_next_cell()

    def _move_to_next_cell(self):
        """Move focus to the next cell (right, then down)."""
        if not self.hypotheses or not self.evidence:
            return

        # Find current positions
        hyp_ids = [h.id for h in self.hypotheses]
        ev_ids = [e.id for e in self.evidence]

        if self.focused_hypothesis_id in hyp_ids and self.focused_evidence_id in ev_ids:
            h_idx = hyp_ids.index(self.focused_hypothesis_id)
            e_idx = ev_ids.index(self.focused_evidence_id)

            # Move right
            if h_idx < len(hyp_ids) - 1:
                self.focused_hypothesis_id = hyp_ids[h_idx + 1]
            # Move down to first column
            elif e_idx < len(ev_ids) - 1:
                self.focused_evidence_id = ev_ids[e_idx + 1]
                self.focused_hypothesis_id = hyp_ids[0]
            # At end - wrap to start
            else:
                self.focused_evidence_id = ev_ids[0]
                self.focused_hypothesis_id = hyp_ids[0]

    def navigate_matrix(self, direction: str):
        """Navigate the matrix with arrow keys or Tab."""
        if not self.hypotheses or not self.evidence:
            return

        hyp_ids = [h.id for h in self.hypotheses]
        ev_ids = [e.id for e in self.evidence]

        # Initialize focus if not set
        if not self.focused_hypothesis_id or not self.focused_evidence_id:
            self.focused_evidence_id = ev_ids[0] if ev_ids else None
            self.focused_hypothesis_id = hyp_ids[0] if hyp_ids else None
            return

        h_idx = (
            hyp_ids.index(self.focused_hypothesis_id)
            if self.focused_hypothesis_id in hyp_ids
            else 0
        )
        e_idx = (
            ev_ids.index(self.focused_evidence_id)
            if self.focused_evidence_id in ev_ids
            else 0
        )

        if direction == "right" or direction == "tab":
            if h_idx < len(hyp_ids) - 1:
                self.focused_hypothesis_id = hyp_ids[h_idx + 1]
            elif e_idx < len(ev_ids) - 1:
                self.focused_evidence_id = ev_ids[e_idx + 1]
                self.focused_hypothesis_id = hyp_ids[0]
        elif direction == "left":
            if h_idx > 0:
                self.focused_hypothesis_id = hyp_ids[h_idx - 1]
            elif e_idx > 0:
                self.focused_evidence_id = ev_ids[e_idx - 1]
                self.focused_hypothesis_id = hyp_ids[-1]
        elif direction == "down":
            if e_idx < len(ev_ids) - 1:
                self.focused_evidence_id = ev_ids[e_idx + 1]
        elif direction == "up":
            if e_idx > 0:
                self.focused_evidence_id = ev_ids[e_idx - 1]

    # =========================================================================
    # PHASE 4: SENSITIVITY ANALYSIS
    # =========================================================================

    def run_sensitivity_analysis(self):
        """Run sensitivity analysis and show results in dialog."""
        if not self.current_analysis_id:
            return

        self.is_sensitivity_loading = True
        self.show_sensitivity_dialog = True
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            self.sensitivity_results = service.run_sensitivity_analysis(
                self.current_analysis_id
            )
        except Exception as e:
            logger.error(f"Error running sensitivity analysis: {e}")
            self.sensitivity_results = []
        finally:
            self.is_sensitivity_loading = False

    def close_sensitivity_dialog(self):
        """Close sensitivity analysis dialog."""
        self.show_sensitivity_dialog = False

    # =========================================================================
    # PHASE 2: AI ASSISTANCE
    # =========================================================================

    # AI suggestion state
    ai_hypothesis_suggestions: List[Dict[str, Any]] = []
    ai_evidence_suggestions: List[Dict[str, Any]] = []
    ai_rating_suggestions: List[Dict[str, Any]] = []
    ai_challenges: List[Dict[str, Any]] = []
    ai_milestone_suggestions: List[Dict[str, Any]] = []

    is_ai_loading: bool = False
    ai_error_message: str = ""

    # Dialog state
    show_ai_hypothesis_dialog: bool = False
    show_ai_evidence_dialog: bool = False
    show_ai_rating_dialog: bool = False
    show_ai_challenge_dialog: bool = False
    show_ai_milestone_dialog: bool = False

    # Rating suggestion context
    ai_rating_evidence_id: Optional[int] = None
    ai_rating_evidence_label: str = ""

    # Challenge context - which hypothesis to challenge
    challenge_hypothesis_id: str = "all"  # "all" = all hypotheses, or specific ID
    saved_challenges: List[Dict[str, Any]] = []  # Persisted challenges

    # Milestone suggestion context
    milestone_hypothesis_id: str = "all"  # "all" = all hypotheses, or specific label

    def set_milestone_hypothesis_id(self, value):
        """Set hypothesis to suggest milestones for."""
        self.milestone_hypothesis_id = str(value) if value is not None else "all"

    def set_challenge_hypothesis_id(self, value):
        """Set the hypothesis to challenge (handles both str and int from UI)."""
        self.challenge_hypothesis_id = str(value) if value is not None else "all"

    def request_hypothesis_suggestions(self):
        """Request AI hypothesis suggestions."""
        if not self.current_analysis_id:
            return

        self.is_ai_loading = True
        self.ai_error_message = ""
        self.ai_hypothesis_suggestions = []
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            suggestions = service.suggest_hypotheses(self.current_analysis_id, count=3)

            if suggestions:
                self.ai_hypothesis_suggestions = suggestions
                self.show_ai_hypothesis_dialog = True
            else:
                self.ai_error_message = (
                    "No suggestions generated. Is LM Studio running?"
                )
        except Exception as e:
            logger.error(f"Error getting hypothesis suggestions: {e}")
            self.ai_error_message = str(e)
        finally:
            self.is_ai_loading = False

    def close_ai_hypothesis_dialog(self):
        """Close AI hypothesis dialog."""
        self.show_ai_hypothesis_dialog = False
        self.ai_hypothesis_suggestions = []

    def accept_hypothesis_suggestion(self, index: int):
        """Accept and add a hypothesis suggestion."""
        if index < 0 or index >= len(self.ai_hypothesis_suggestions):
            return

        suggestion = self.ai_hypothesis_suggestions[index]
        self.new_hypothesis_description = suggestion.get("description", "")

        # Remove from suggestions
        self.ai_hypothesis_suggestions = [
            s for i, s in enumerate(self.ai_hypothesis_suggestions) if i != index
        ]

        # Add the hypothesis
        yield from self.add_hypothesis()

    def accept_all_hypothesis_suggestions(self):
        """Accept all hypothesis suggestions."""
        for suggestion in self.ai_hypothesis_suggestions:
            self.new_hypothesis_description = suggestion.get("description", "")
            yield from self.add_hypothesis()

        self.close_ai_hypothesis_dialog()

    def request_challenge_hypotheses(self):
        """Request devil's advocate challenges for selected or all hypotheses."""
        if not self.current_analysis_id or not self.hypotheses:
            return

        self.is_ai_loading = True
        self.ai_error_message = ""
        self.ai_challenges = []
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()

            # Find hypothesis ID by label if one is chosen (not "all")
            hypothesis_id = None
            if self.challenge_hypothesis_id and self.challenge_hypothesis_id != "all":
                # Look up the ID from our hypotheses list by matching label
                for h in self.hypotheses:
                    if h.label == self.challenge_hypothesis_id:
                        hypothesis_id = h.id
                        break

            challenges = service.challenge_hypotheses(
                self.current_analysis_id,
                hypothesis_id=hypothesis_id,
            )

            if challenges:
                self.ai_challenges = challenges
                self.show_ai_challenge_dialog = True
            else:
                self.ai_error_message = "No challenges generated. Is LM Studio running?"
        except Exception as e:
            logger.error(f"Error getting challenges: {e}")
            self.ai_error_message = str(e)
        finally:
            self.is_ai_loading = False

    def save_challenges_to_notes(self):
        """Save current challenges to sensitivity notes for future reference."""
        if not self.ai_challenges or not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            # Format challenges as text
            challenge_text = "\n\n--- AI Challenges (saved) ---\n"
            for c in self.ai_challenges:
                label = c.get("hypothesis_label", "?")
                counter = c.get("counter_argument", "")
                disproof = c.get("disproof_evidence", "")
                alt = c.get("alternative_angle", "")
                challenge_text += f"\n[{label}] Counter: {counter}\n"
                challenge_text += f"    Disproof: {disproof}\n"
                challenge_text += f"    Alternative: {alt}\n"

            # Append to sensitivity notes
            service = get_ach_service()
            analysis = service.get_analysis(self.current_analysis_id)
            if analysis:
                current_notes = analysis.get("sensitivity_notes", "") or ""
                new_notes = current_notes + challenge_text
                service.update_analysis(
                    self.current_analysis_id,
                    sensitivity_notes=new_notes,
                )
                # Also add to local saved_challenges list
                self.saved_challenges = self.saved_challenges + self.ai_challenges
                self.sensitivity_notes = new_notes

            self.close_ai_challenge_dialog()
            # Show confirmation
            self.show_save_confirmation = True
        except Exception as e:
            logger.error(f"Error saving challenges: {e}")

    # Confirmation dialog state
    show_save_confirmation: bool = False

    def close_save_confirmation(self):
        """Close the save confirmation dialog."""
        self.show_save_confirmation = False

    def close_ai_challenge_dialog(self):
        """Close AI challenge dialog."""
        self.show_ai_challenge_dialog = False
        self.ai_challenges = []

    def request_milestone_suggestions(self):
        """Request AI milestone suggestions."""
        if not self.current_analysis_id:
            return

        self.is_ai_loading = True
        self.ai_error_message = ""
        self.ai_milestone_suggestions = []
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()

            # Find hypothesis ID by label if specific one is chosen
            hypothesis_id = None
            if self.milestone_hypothesis_id and self.milestone_hypothesis_id != "all":
                for h in self.hypotheses:
                    if h.label == self.milestone_hypothesis_id:
                        hypothesis_id = h.id
                        break

            suggestions = service.suggest_milestones(
                self.current_analysis_id,
                hypothesis_id=hypothesis_id,
            )

            if suggestions:
                self.ai_milestone_suggestions = suggestions
                self.show_ai_milestone_dialog = True
            else:
                self.ai_error_message = (
                    "No suggestions generated. Is LM Studio running?"
                )
        except Exception as e:
            logger.error(f"Error getting milestone suggestions: {e}")
            self.ai_error_message = str(e)
        finally:
            self.is_ai_loading = False

    def accept_milestone_suggestion(self, suggestion: Dict[str, Any]):
        """Accept a milestone suggestion and add it."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            description = suggestion.get("description", "")
            expected = suggestion.get("expected_timeframe", "")
            hypothesis_id = suggestion.get("hypothesis_id")

            if description and hypothesis_id:
                # Add the milestone
                milestone = service.add_milestone(
                    analysis_id=self.current_analysis_id,
                    description=f"{description} (Expected: {expected})",
                    hypothesis_id=hypothesis_id,
                )
                if milestone:
                    # Refresh milestones list
                    self._load_milestones()
        except Exception as e:
            logger.error(f"Error accepting milestone suggestion: {e}")

    def accept_all_milestone_suggestions(self):
        """Accept all milestone suggestions and add them."""
        if not self.current_analysis_id:
            return

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            added = 0

            for suggestion in self.ai_milestone_suggestions:
                description = suggestion.get("description", "")
                expected = suggestion.get("expected_timeframe", "")
                hypothesis_id = suggestion.get("hypothesis_id")

                if description and hypothesis_id:
                    milestone = service.add_milestone(
                        analysis_id=self.current_analysis_id,
                        description=f"{description} (Expected: {expected})",
                        hypothesis_id=hypothesis_id,
                    )
                    if milestone:
                        added += 1

            # Refresh milestones list
            self._load_milestones()
            logger.info(f"Added {added} milestones from suggestions")

            # Close the dialog
            self.close_ai_milestone_dialog()
        except Exception as e:
            logger.error(f"Error accepting all milestone suggestions: {e}")

    def close_ai_milestone_dialog(self):
        """Close AI milestone dialog."""
        self.show_ai_milestone_dialog = False
        self.ai_milestone_suggestions = []

    def request_evidence_suggestions(self):
        """Request AI evidence suggestions."""
        if not self.current_analysis_id:
            return

        self.is_ai_loading = True
        self.ai_error_message = ""
        self.ai_evidence_suggestions = []
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            suggestions = service.suggest_evidence(self.current_analysis_id, count=5)

            if suggestions:
                self.ai_evidence_suggestions = suggestions
                self.show_ai_evidence_dialog = True
            else:
                self.ai_error_message = (
                    "No suggestions generated. Is LM Studio running?"
                )
        except Exception as e:
            logger.error(f"Error getting evidence suggestions: {e}")
            self.ai_error_message = str(e)
        finally:
            self.is_ai_loading = False

    def close_ai_evidence_dialog(self):
        """Close AI evidence dialog."""
        self.show_ai_evidence_dialog = False
        self.ai_evidence_suggestions = []

    def accept_evidence_suggestion(self, index: int):
        """Accept and add an evidence suggestion."""
        if index < 0 or index >= len(self.ai_evidence_suggestions):
            return

        suggestion = self.ai_evidence_suggestions[index]
        self.new_evidence_description = suggestion.get("description", "")
        self.new_evidence_type = suggestion.get("evidence_type", "fact")

        # Remove from suggestions
        self.ai_evidence_suggestions = [
            s for i, s in enumerate(self.ai_evidence_suggestions) if i != index
        ]

        # Add the evidence
        yield from self.add_evidence()

    def request_rating_suggestions(self, evidence_id: int):
        """Request AI rating suggestions for a specific evidence item."""
        if not self.current_analysis_id:
            return

        # Find evidence label
        e = next((e for e in self.evidence if e.id == evidence_id), None)
        if not e:
            return

        self.ai_rating_evidence_id = evidence_id
        self.ai_rating_evidence_label = e.label
        self.is_ai_loading = True
        self.ai_error_message = ""
        self.ai_rating_suggestions = []
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()
            suggestions = service.suggest_ratings(self.current_analysis_id, evidence_id)

            if suggestions:
                self.ai_rating_suggestions = suggestions
                self.show_ai_rating_dialog = True
            else:
                self.ai_error_message = (
                    "No suggestions generated. Is LM Studio running?"
                )
        except Exception as e:
            logger.error(f"Error getting rating suggestions: {e}")
            self.ai_error_message = str(e)
        finally:
            self.is_ai_loading = False

    def close_ai_rating_dialog(self):
        """Close AI rating dialog."""
        self.show_ai_rating_dialog = False
        self.ai_rating_suggestions = []
        self.ai_rating_evidence_id = None
        self.ai_rating_evidence_label = ""

    def accept_rating_suggestion(self, hypothesis_id: int, rating: str):
        """Accept a single rating suggestion."""
        if not self.ai_rating_evidence_id:
            return

        self.set_rating(self.ai_rating_evidence_id, hypothesis_id, rating)

    def accept_all_rating_suggestions(self):
        """Accept all rating suggestions for the current evidence."""
        if not self.ai_rating_evidence_id:
            return

        for suggestion in self.ai_rating_suggestions:
            hypothesis_id = suggestion.get("hypothesis_id")
            rating = suggestion.get("rating", "N")
            if hypothesis_id and rating in ["CC", "C", "N", "I", "II"]:
                self.set_rating(self.ai_rating_evidence_id, hypothesis_id, rating)

        self.close_ai_rating_dialog()

    # =========================================================================
    # PHASE 3: CORPUS INTEGRATION
    # =========================================================================

    # Import dialog state
    show_import_dialog: bool = False
    import_tab: str = "search"  # "search", "contradictions", "timeline"
    is_import_loading: bool = False
    import_error: str = ""

    # Search tab
    import_search_query: str = ""
    import_search_results: List[Dict[str, Any]] = []

    # Contradictions tab
    import_contradictions: List[Dict[str, Any]] = []
    import_contradictions_loaded: bool = False

    # Timeline tab
    import_timeline_events: List[Dict[str, Any]] = []
    import_timeline_loaded: bool = False

    # Selection tracking - format: "search_123", "contradiction_45", "timeline_67"
    import_selected_ids: List[str] = []

    # Project ID for current analysis (for strict project filtering)
    analysis_project_id: Optional[int] = None

    def open_import_dialog(self):
        """Open the corpus import dialog."""
        if not self.current_analysis_id:
            return

        # Get project_id for filtering
        from app.arkham.services.ach_service import get_ach_service

        service = get_ach_service()
        self.analysis_project_id = service.get_analysis_project_id(
            self.current_analysis_id
        )

        # Reset state
        self.import_tab = "search"
        self.import_search_query = ""
        self.import_search_results = []
        self.import_contradictions = []
        self.import_contradictions_loaded = False
        self.import_timeline_events = []
        self.import_timeline_loaded = False
        self.import_selected_ids = []
        self.import_error = ""

        self.show_import_dialog = True

    def close_import_dialog(self):
        """Close the corpus import dialog."""
        self.show_import_dialog = False
        self.import_selected_ids = []

    def set_import_tab(self, tab: str):
        """Switch import tab and load data if needed."""
        self.import_tab = tab

        if tab == "contradictions" and not self.import_contradictions_loaded:
            yield from self.load_import_contradictions()
        elif tab == "timeline" and not self.import_timeline_loaded:
            yield from self.load_import_timeline()

    def set_import_search_query(self, value: str):
        """Set search query."""
        self.import_search_query = value

    def execute_import_search(self):
        """Execute search for import."""
        if not self.import_search_query.strip():
            return

        self.is_import_loading = True
        self.import_error = ""
        yield

        try:
            from app.arkham.services.search_service import hybrid_search

            # Search with project filter for strict isolation
            results = hybrid_search(
                query=self.import_search_query.strip(),
                project_id=self.analysis_project_id,
                limit=20,
            )

            self.import_search_results = [
                {
                    "id": f"search_{r.get('id', i)}",
                    "text": r.get("text", "")[:300] + "..."
                    if len(r.get("text", "")) > 300
                    else r.get("text", ""),
                    "full_text": r.get("text", ""),
                    "doc_id": r.get("doc_id"),
                    "doc_title": r.get("metadata", {}).get(
                        "title", f"Document #{r.get('doc_id')}"
                    ),
                    "score": r.get("score", 0),
                }
                for i, r in enumerate(results)
            ]

            if not self.import_search_results:
                self.import_error = "No results found. Try a different query."

        except Exception as e:
            logger.error(f"Import search failed: {e}")
            self.import_error = f"Search failed: {str(e)}"
        finally:
            self.is_import_loading = False

    def load_import_contradictions(self):
        """Load contradictions for import."""
        self.is_import_loading = True
        self.import_error = ""
        yield

        try:
            from app.arkham.services.contradiction_service import ContradictionService
            from app.arkham.services.db.models import Document
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from config.settings import DATABASE_URL

            service = ContradictionService()
            all_contradictions = service.get_contradictions(limit=100)

            # Filter to only contradictions from documents in the same project
            if self.analysis_project_id:
                engine = create_engine(DATABASE_URL)
                Session = sessionmaker(bind=engine)
                session = Session()
                try:
                    # Get all doc_ids in this project
                    project_docs = (
                        session.query(Document.id)
                        .filter_by(project_id=self.analysis_project_id)
                        .all()
                    )
                    project_doc_ids = {d.id for d in project_docs}

                    # Filter contradictions to those with evidence from project docs
                    filtered = []
                    for c in all_contradictions:
                        # Check if any evidence is from a project document
                        for e in c.get("evidence", []):
                            if e.get("document_id") in project_doc_ids:
                                filtered.append(c)
                                break

                    all_contradictions = filtered
                finally:
                    session.close()

            self.import_contradictions = [
                {
                    "id": f"contradiction_{c['id']}",
                    "contradiction_id": c["id"],
                    "entity_name": c.get("entity_name", "Unknown"),
                    "description": c.get("description", "")[:200] + "..."
                    if len(c.get("description", "")) > 200
                    else c.get("description", ""),
                    "full_description": c.get("description", ""),
                    "severity": c.get("severity", "medium"),
                    "evidence": c.get("evidence", []),
                }
                for c in all_contradictions
            ]

            self.import_contradictions_loaded = True

            if not self.import_contradictions:
                self.import_error = "No contradictions found in this project."

        except Exception as e:
            logger.error(f"Load contradictions failed: {e}")
            self.import_error = f"Failed to load contradictions: {str(e)}"
        finally:
            self.is_import_loading = False

    def load_import_timeline(self):
        """Load timeline events for import."""
        self.is_import_loading = True
        self.import_error = ""
        yield

        try:
            from app.arkham.services.timeline_service import get_timeline_events

            # Get timeline events with project filter
            events = get_timeline_events(
                project_id=self.analysis_project_id,
                limit=100,
            )

            self.import_timeline_events = [
                {
                    "id": f"timeline_{e['id']}",
                    "event_id": e["id"],
                    "date": e.get("date", "Unknown"),
                    "description": e.get("description", "")[:200] + "..."
                    if len(e.get("description", "")) > 200
                    else e.get("description", ""),
                    "full_description": e.get("description", ""),
                    "event_type": e.get("type", ""),
                    "doc_id": e.get("doc_id"),
                }
                for e in events
            ]

            self.import_timeline_loaded = True

            if not self.import_timeline_events:
                self.import_error = "No timeline events found in this project."

        except Exception as e:
            logger.error(f"Load timeline failed: {e}")
            self.import_error = f"Failed to load timeline: {str(e)}"
        finally:
            self.is_import_loading = False

    def toggle_import_selection(self, item_id: str):
        """Toggle selection of an import item."""
        if item_id in self.import_selected_ids:
            self.import_selected_ids = [
                i for i in self.import_selected_ids if i != item_id
            ]
        else:
            self.import_selected_ids = self.import_selected_ids + [item_id]

    def import_selected_items(self):
        """Import all selected items as evidence."""
        if not self.current_analysis_id or not self.import_selected_ids:
            return

        self.is_import_loading = True
        self.import_error = ""
        yield

        try:
            from app.arkham.services.ach_service import get_ach_service

            service = get_ach_service()

            imported_count = 0

            for item_id in self.import_selected_ids:
                parts = item_id.split("_", 1)
                if len(parts) != 2:
                    continue

                item_type, raw_id = parts

                if item_type == "search":
                    # Find the search result
                    result = next(
                        (r for r in self.import_search_results if r["id"] == item_id),
                        None,
                    )
                    if result:
                        evidence = service.import_search_result(
                            analysis_id=self.current_analysis_id,
                            text=result["full_text"],
                            doc_id=result["doc_id"],
                            doc_title=result["doc_title"],
                            score=result["score"],
                        )
                        if evidence:
                            imported_count += 1

                elif item_type == "contradiction":
                    # Find the contradiction
                    contradiction = next(
                        (c for c in self.import_contradictions if c["id"] == item_id),
                        None,
                    )
                    if contradiction:
                        evidence = service.import_contradiction(
                            analysis_id=self.current_analysis_id,
                            contradiction_id=contradiction["contradiction_id"],
                        )
                        if evidence:
                            imported_count += 1

                elif item_type == "timeline":
                    # Find the timeline event
                    event = next(
                        (e for e in self.import_timeline_events if e["id"] == item_id),
                        None,
                    )
                    if event:
                        evidence = service.import_timeline_event(
                            analysis_id=self.current_analysis_id,
                            event_id=event["event_id"],
                        )
                        if evidence:
                            imported_count += 1

            # Refresh evidence list
            data = service.get_analysis(self.current_analysis_id)
            if data:
                self._load_analysis_data(data)

            # Close dialog
            self.close_import_dialog()

            logger.info(f"Imported {imported_count} evidence items")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            self.import_error = f"Import failed: {str(e)}"
        finally:
            self.is_import_loading = False

    @rx.var
    def import_selected_count(self) -> int:
        """Number of items selected for import."""
        return len(self.import_selected_ids)

    def is_import_selected(self, item_id: str) -> bool:
        """Check if an item is selected for import."""
        return item_id in self.import_selected_ids
