"""
ACH (Analysis of Competing Hypotheses) Service Layer.

Implements Heuer's 8-step ACH methodology:
1. Identify Hypotheses
2. List Evidence
3. Create Matrix
4. Analyze Diagnosticity
5. Refine the Matrix
6. Draw Tentative Conclusions
7. Sensitivity Analysis
8. Report & Set Milestones
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

# Silence the FutureWarning about downcasting in replace()
# This opts into the future behavior where downcasting is not automatic
pd.set_option("future.no_silent_downcasting", True)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import DATABASE_URL
from app.arkham.services.db.models import (
    ACHAnalysis,
    ACHHypothesis,
    ACHEvidence,
    ACHRating,
    ACHMilestone,
    ACHAnalysisSnapshot,
)

logger = logging.getLogger(__name__)

# Note: LLM service is imported lazily inside methods to avoid slow startup
# from app.arkham.services.llm_service import chat_with_llm

# Rating scale numeric values for calculations
# Inconsistency-focused: positive values count against hypothesis
RATING_VALUES = {
    "CC": -2,  # Very Consistent (supports hypothesis)
    "C": -1,  # Consistent
    "N": 0,  # Neutral
    "I": 1,  # Inconsistent (counts against)
    "II": 2,  # Very Inconsistent (strongly counts against)
    "-": 0,  # Unrated treated as neutral (new format)
    "": 0,  # Unrated treated as neutral (legacy)
}

# Default hypothesis colors for charts
HYPOTHESIS_COLORS = [
    "#3b82f6",  # Blue
    "#ef4444",  # Red
    "#22c55e",  # Green
    "#f59e0b",  # Amber
    "#8b5cf6",  # Violet
    "#ec4899",  # Pink
    "#06b6d4",  # Cyan
    "#84cc16",  # Lime
]


class ACHService:
    """Service for ACH analysis operations."""

    def __init__(self):
        """Initialize with database connection."""
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    # =========================================================================
    # STEP 1: IDENTIFY HYPOTHESES - Analysis CRUD
    # =========================================================================

    def create_analysis(
        self,
        title: str,
        focus_question: str,
        description: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new ACH analysis."""
        session = self.Session()
        try:
            analysis = ACHAnalysis(
                title=title,
                focus_question=focus_question,
                description=description,
                project_id=project_id,
                status="draft",
                current_step=1,
                steps_completed="[]",
            )
            session.add(analysis)
            session.commit()
            session.refresh(analysis)
            logger.info(f"Created ACH analysis: {analysis.id} - {title}")
            return self._analysis_to_dict(analysis)
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating analysis: {e}")
            raise
        finally:
            session.close()

    def get_analysis(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        """Get a single analysis with all nested data."""
        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            if not analysis:
                return None

            result = self._analysis_to_dict(analysis)

            # Load hypotheses
            hypotheses = (
                session.query(ACHHypothesis)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHHypothesis.display_order)
                .all()
            )
            result["hypotheses"] = [self._hypothesis_to_dict(h) for h in hypotheses]
            result["hypothesis_count"] = len(hypotheses)

            # Load evidence with ratings
            evidence_list = (
                session.query(ACHEvidence)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHEvidence.display_order)
                .all()
            )

            # Get all ratings for this analysis
            ratings = session.query(ACHRating).filter_by(analysis_id=analysis_id).all()
            ratings_map = {}
            for r in ratings:
                key = (r.evidence_id, r.hypothesis_id)
                ratings_map[key] = r.rating

            evidence_dicts = []
            for e in evidence_list:
                e_dict = self._evidence_to_dict(e)
                # Add ratings keyed by hypothesis_id
                e_dict["ratings"] = {}
                for h in hypotheses:
                    key = (e.id, h.id)
                    e_dict["ratings"][h.id] = ratings_map.get(key, "")
                evidence_dicts.append(e_dict)

            result["evidence"] = evidence_dicts
            result["evidence_count"] = len(evidence_list)

            return result
        except Exception as e:
            logger.error(f"Error getting analysis {analysis_id}: {e}")
            return None
        finally:
            session.close()

    def get_analysis_list(
        self, project_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get list of all analyses (summary view)."""
        session = self.Session()
        try:
            query = session.query(ACHAnalysis)
            if project_id is not None:
                query = query.filter_by(project_id=project_id)
            query = query.order_by(ACHAnalysis.updated_at.desc())
            analyses = query.all()

            results = []
            for a in analyses:
                # Get counts
                h_count = (
                    session.query(ACHHypothesis).filter_by(analysis_id=a.id).count()
                )
                e_count = session.query(ACHEvidence).filter_by(analysis_id=a.id).count()

                result = {
                    "id": a.id,
                    "title": a.title,
                    "focus_question": a.focus_question,
                    "status": a.status,
                    "current_step": a.current_step,
                    "hypothesis_count": h_count,
                    "evidence_count": e_count,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                }
                results.append(result)

            return results
        except Exception as e:
            logger.error(f"Error listing analyses: {e}")
            return []
        finally:
            session.close()

    def update_analysis(
        self,
        analysis_id: int,
        title: Optional[str] = None,
        focus_question: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        current_step: Optional[int] = None,
        sensitivity_notes: Optional[str] = None,
        key_assumptions: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an analysis."""
        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            if not analysis:
                return None

            if title is not None:
                analysis.title = title
            if focus_question is not None:
                analysis.focus_question = focus_question
            if description is not None:
                analysis.description = description
            if status is not None:
                analysis.status = status
            if current_step is not None:
                analysis.current_step = current_step
            if sensitivity_notes is not None:
                analysis.sensitivity_notes = sensitivity_notes
            if key_assumptions is not None:
                analysis.key_assumptions = json.dumps(key_assumptions)

            session.commit()
            session.refresh(analysis)
            return self._analysis_to_dict(analysis)
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating analysis {analysis_id}: {e}")
            return None
        finally:
            session.close()

    def delete_analysis(self, analysis_id: int) -> bool:
        """Delete an analysis and all related data."""
        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            if not analysis:
                return False

            # Cascade deletes handle related records
            session.delete(analysis)
            session.commit()
            logger.info(f"Deleted ACH analysis: {analysis_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting analysis {analysis_id}: {e}")
            return False
        finally:
            session.close()

    def mark_step_complete(self, analysis_id: int, step: int) -> bool:
        """Mark a step as complete."""
        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            if not analysis:
                return False

            completed = json.loads(analysis.steps_completed or "[]")
            if step not in completed:
                completed.append(step)
                completed.sort()
                analysis.steps_completed = json.dumps(completed)

            # Move to next step if this was current
            if analysis.current_step == step and step < 8:
                analysis.current_step = step + 1

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error marking step complete: {e}")
            return False
        finally:
            session.close()

    # =========================================================================
    # HYPOTHESIS CRUD (Step 1)
    # =========================================================================

    def add_hypothesis(
        self,
        analysis_id: int,
        description: str,
        label: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add a hypothesis to an analysis."""
        session = self.Session()
        try:
            # Get next label and order
            existing = (
                session.query(ACHHypothesis).filter_by(analysis_id=analysis_id).count()
            )

            if label is None:
                label = f"H{existing + 1}"

            # Pick color
            color_idx = existing % len(HYPOTHESIS_COLORS)

            hypothesis = ACHHypothesis(
                analysis_id=analysis_id,
                label=label,
                description=description,
                display_order=existing,
                color=HYPOTHESIS_COLORS[color_idx],
            )
            session.add(hypothesis)
            session.commit()
            session.refresh(hypothesis)

            # Create empty ratings for all existing evidence
            evidence_items = (
                session.query(ACHEvidence).filter_by(analysis_id=analysis_id).all()
            )
            for e in evidence_items:
                rating = ACHRating(
                    analysis_id=analysis_id,
                    hypothesis_id=hypothesis.id,
                    evidence_id=e.id,
                    rating="",
                )
                session.add(rating)
            session.commit()

            logger.info(f"Added hypothesis {label} to analysis {analysis_id}")
            return self._hypothesis_to_dict(hypothesis)
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding hypothesis: {e}")
            return None
        finally:
            session.close()

    def update_hypothesis(
        self,
        hypothesis_id: int,
        description: Optional[str] = None,
        label: Optional[str] = None,
        future_indicators: Optional[str] = None,
        indicator_timeframe: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a hypothesis."""
        session = self.Session()
        try:
            h = session.query(ACHHypothesis).filter_by(id=hypothesis_id).first()
            if not h:
                return None

            if description is not None:
                h.description = description
            if label is not None:
                h.label = label
            if future_indicators is not None:
                h.future_indicators = future_indicators
            if indicator_timeframe is not None:
                h.indicator_timeframe = indicator_timeframe

            session.commit()
            session.refresh(h)
            return self._hypothesis_to_dict(h)
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating hypothesis {hypothesis_id}: {e}")
            return None
        finally:
            session.close()

    def delete_hypothesis(self, hypothesis_id: int) -> bool:
        """Delete a hypothesis and its ratings."""
        session = self.Session()
        try:
            h = session.query(ACHHypothesis).filter_by(id=hypothesis_id).first()
            if not h:
                return False

            session.delete(h)
            session.commit()
            logger.info(f"Deleted hypothesis: {hypothesis_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting hypothesis {hypothesis_id}: {e}")
            return False
        finally:
            session.close()

    # =========================================================================
    # EVIDENCE CRUD (Step 2)
    # =========================================================================

    def add_evidence(
        self,
        analysis_id: int,
        description: str,
        label: Optional[str] = None,
        evidence_type: str = "fact",
        reliability: str = "medium",
        source: Optional[str] = None,
        source_document_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add evidence to an analysis."""
        session = self.Session()
        try:
            existing = (
                session.query(ACHEvidence).filter_by(analysis_id=analysis_id).count()
            )

            if label is None:
                label = f"E{existing + 1}"

            evidence = ACHEvidence(
                analysis_id=analysis_id,
                label=label,
                description=description,
                display_order=existing,
                evidence_type=evidence_type,
                reliability=reliability,
                source=source,
                source_document_id=source_document_id,
            )
            session.add(evidence)
            session.commit()
            session.refresh(evidence)

            # Create empty ratings for all existing hypotheses
            hypotheses = (
                session.query(ACHHypothesis).filter_by(analysis_id=analysis_id).all()
            )
            for h in hypotheses:
                rating = ACHRating(
                    analysis_id=analysis_id,
                    hypothesis_id=h.id,
                    evidence_id=evidence.id,
                    rating="",
                )
                session.add(rating)
            session.commit()

            logger.info(f"Added evidence {label} to analysis {analysis_id}")
            return self._evidence_to_dict(evidence)
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding evidence: {e}")
            return None
        finally:
            session.close()

    def update_evidence(
        self,
        evidence_id: int,
        description: Optional[str] = None,
        label: Optional[str] = None,
        evidence_type: Optional[str] = None,
        reliability: Optional[str] = None,
        source: Optional[str] = None,
        is_critical: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update evidence."""
        session = self.Session()
        try:
            e = session.query(ACHEvidence).filter_by(id=evidence_id).first()
            if not e:
                return None

            if description is not None:
                e.description = description
            if label is not None:
                e.label = label
            if evidence_type is not None:
                e.evidence_type = evidence_type
            if reliability is not None:
                e.reliability = reliability
            if source is not None:
                e.source = source
            if is_critical is not None:
                e.is_critical = 1 if is_critical else 0

            session.commit()
            session.refresh(e)
            return self._evidence_to_dict(e)
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating evidence {evidence_id}: {e}")
            return None
        finally:
            session.close()

    def delete_evidence(self, evidence_id: int) -> bool:
        """Delete evidence and its ratings."""
        session = self.Session()
        try:
            e = session.query(ACHEvidence).filter_by(id=evidence_id).first()
            if not e:
                return False

            session.delete(e)
            session.commit()
            logger.info(f"Deleted evidence: {evidence_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting evidence {evidence_id}: {e}")
            return False
        finally:
            session.close()

    # =========================================================================
    # RATING OPERATIONS (Step 3)
    # =========================================================================

    def set_rating(
        self,
        analysis_id: int,
        hypothesis_id: int,
        evidence_id: int,
        rating: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Set or update a rating in the matrix."""
        session = self.Session()
        try:
            # Validate rating value
            if rating not in RATING_VALUES:
                logger.warning(f"Invalid rating value: {rating}")
                return False

            # Find or create rating
            r = (
                session.query(ACHRating)
                .filter_by(hypothesis_id=hypothesis_id, evidence_id=evidence_id)
                .first()
            )

            if r:
                r.rating = rating
                if notes is not None:
                    r.notes = notes
            else:
                r = ACHRating(
                    analysis_id=analysis_id,
                    hypothesis_id=hypothesis_id,
                    evidence_id=evidence_id,
                    rating=rating,
                    notes=notes,
                )
                session.add(r)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting rating: {e}")
            return False
        finally:
            session.close()

    def get_matrix(self, analysis_id: int) -> Dict[str, Any]:
        """
        Get the full ACH matrix as a structured object.

        Returns:
            {
                "hypotheses": [...],
                "evidence": [...],
                "ratings": {(evidence_id, hypothesis_id): rating, ...},
                "completion_pct": float
            }
        """
        session = self.Session()
        try:
            hypotheses = (
                session.query(ACHHypothesis)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHHypothesis.display_order)
                .all()
            )

            evidence = (
                session.query(ACHEvidence)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHEvidence.display_order)
                .all()
            )

            ratings = session.query(ACHRating).filter_by(analysis_id=analysis_id).all()

            # Build ratings map
            ratings_map = {}
            rated_count = 0
            total_cells = len(hypotheses) * len(evidence)

            for r in ratings:
                ratings_map[(r.evidence_id, r.hypothesis_id)] = r.rating
                if r.rating:  # Non-empty rating
                    rated_count += 1

            completion_pct = (rated_count / total_cells * 100) if total_cells > 0 else 0

            return {
                "hypotheses": [self._hypothesis_to_dict(h) for h in hypotheses],
                "evidence": [self._evidence_to_dict(e) for e in evidence],
                "ratings": {
                    f"{eid}_{hid}": rating for (eid, hid), rating in ratings_map.items()
                },
                "completion_pct": round(completion_pct, 1),
                "total_cells": total_cells,
                "rated_cells": rated_count,
            }
        except Exception as e:
            logger.error(f"Error getting matrix: {e}")
            return {
                "hypotheses": [],
                "evidence": [],
                "ratings": {},
                "completion_pct": 0,
            }
        finally:
            session.close()

    def get_matrix_dataframe(
        self, analysis_id: int
    ) -> Tuple[pd.DataFrame, Dict[str, int], Dict[str, int]]:
        """
        Get the ACH matrix as a Pandas DataFrame.

        Phase 4: Enables vectorized calculations for scores and diagnosticity.

        Returns:
            Tuple of:
            - DataFrame with evidence labels as rows, hypothesis labels as columns
            - Dict mapping evidence labels to IDs
            - Dict mapping hypothesis labels to IDs
        """
        session = self.Session()
        try:
            hypotheses = (
                session.query(ACHHypothesis)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHHypothesis.display_order)
                .all()
            )

            evidence = (
                session.query(ACHEvidence)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHEvidence.display_order)
                .all()
            )

            ratings = session.query(ACHRating).filter_by(analysis_id=analysis_id).all()

            if not hypotheses or not evidence:
                return pd.DataFrame(), {}, {}

            # Build label-to-ID mappings
            evidence_ids = {e.label: e.id for e in evidence}
            hypothesis_ids = {h.label: h.id for h in hypotheses}

            # Build ratings lookup
            ratings_map = {(r.evidence_id, r.hypothesis_id): r.rating for r in ratings}

            # Create DataFrame with labels as indices
            df = pd.DataFrame(
                index=[e.label for e in evidence],
                columns=[h.label for h in hypotheses],
                dtype=str,
            ).fillna("")

            # Populate ratings
            for e in evidence:
                for h in hypotheses:
                    rating = ratings_map.get((e.id, h.id), "")
                    df.loc[e.label, h.label] = rating

            return df, evidence_ids, hypothesis_ids

        except Exception as e:
            logger.error(f"Error creating matrix DataFrame: {e}")
            return pd.DataFrame(), {}, {}
        finally:
            session.close()

    def get_numeric_matrix(self, analysis_id: int) -> pd.DataFrame:
        """
        Get the ACH matrix with numeric values for calculations.

        Returns DataFrame with RATING_VALUES applied.
        """
        df, _, _ = self.get_matrix_dataframe(analysis_id)
        if df.empty:
            return df
        # Replace rating strings with numeric values
        numeric_df = df.replace(RATING_VALUES)
        # Ensure all values are float (handles any remaining strings)
        return numeric_df.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    # =========================================================================
    # STEP 4: ANALYZE DIAGNOSTICITY
    # =========================================================================

    def calculate_diagnosticity(self, analysis_id: int) -> List[Dict[str, Any]]:
        """
        Calculate diagnosticity scores for all evidence using Pandas.

        Diagnosticity = how much an evidence item discriminates between hypotheses.
        Higher variance in ratings = higher diagnostic value.

        Phase 4: Refactored to use vectorized Pandas operations.

        Returns list of evidence with diagnosticity scores, sorted by score.
        """
        session = self.Session()
        try:
            # Get numeric matrix
            numeric_df = self.get_numeric_matrix(analysis_id)
            if numeric_df.empty:
                return []

            # Calculate standard deviation per row (evidence)
            # This is the key vectorized operation - replaces manual variance calc
            std_series = numeric_df.std(axis=1, ddof=0)  # Population std
            var_series = numeric_df.var(axis=1, ddof=0)  # Population variance

            # Get evidence from database for metadata
            evidence = (
                session.query(ACHEvidence)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHEvidence.display_order)
                .all()
            )

            results = []
            for e in evidence:
                # Safely get std_dev and variance
                try:
                    if e.label in std_series.index:
                        val = std_series[e.label]
                        std_dev = (
                            float(val.iloc[0])
                            if isinstance(val, pd.Series)
                            else float(val)
                        )
                    else:
                        std_dev = 0.0
                except (TypeError, ValueError, IndexError):
                    std_dev = 0.0

                try:
                    if e.label in var_series.index:
                        val = var_series[e.label]
                        variance = (
                            float(val.iloc[0])
                            if isinstance(val, pd.Series)
                            else float(val)
                        )
                    else:
                        variance = 0.0
                except (TypeError, ValueError, IndexError):
                    variance = 0.0

                # Handle NaN values
                if pd.isna(std_dev):
                    std_dev = 0.0
                if pd.isna(variance):
                    variance = 0.0

                # Determine diagnostic level
                is_high = std_dev >= 1.0  # Significant variance
                is_low = std_dev < 0.5  # Little to no variance

                # Update cached score in database
                e.diagnosticity_score = std_dev
                session.add(e)

                results.append(
                    {
                        "evidence_id": e.id,
                        "label": e.label,
                        "description": e.description,
                        "diagnosticity_score": round(std_dev, 3),
                        "is_high_diagnostic": is_high,
                        "is_low_diagnostic": is_low,
                        "rating_variance": round(variance, 3),
                    }
                )

            session.commit()

            # Sort by diagnosticity (highest first)
            results.sort(key=lambda x: x["diagnosticity_score"], reverse=True)
            return results
        except Exception as e:
            session.rollback()
            logger.error(f"Error calculating diagnosticity: {e}")
            return []
        finally:
            session.close()

    # =========================================================================
    # STEP 6: DRAW TENTATIVE CONCLUSIONS (Calculate Scores)
    # =========================================================================

    def calculate_scores(self, analysis_id: int) -> List[Dict[str, Any]]:
        """
        Calculate inconsistency scores for all hypotheses using Pandas.

        The hypothesis with the LOWEST score is the best fit.
        Only inconsistencies (I, II) count positively against a hypothesis.
        Consistencies (C, CC) count negatively (support the hypothesis).

        Phase 4: Refactored to use vectorized Pandas operations.

        Returns list of hypotheses with scores, sorted by score (best first).
        """
        session = self.Session()
        try:
            # Get numeric matrix
            numeric_df = self.get_numeric_matrix(analysis_id)
            if numeric_df.empty:
                return []

            # Calculate scores per hypothesis (column)
            # Only count positive values (inconsistencies) - This is the Heuer method
            # df.clip(lower=0) sets all negative values to 0, then sum per column
            scores_series = numeric_df.clip(lower=0).sum()

            # Get hypotheses from database for metadata
            hypotheses = (
                session.query(ACHHypothesis)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHHypothesis.display_order)
                .all()
            )

            if not hypotheses:
                return []

            results = []
            for h in hypotheses:
                # Safely get score, handling missing columns and Series edge cases
                try:
                    if h.label in scores_series.index:
                        score_val = scores_series[h.label]
                        # Ensure it's a scalar, not a Series
                        if isinstance(score_val, pd.Series):
                            score = (
                                float(score_val.iloc[0]) if len(score_val) > 0 else 0.0
                            )
                        else:
                            score = float(score_val)
                    else:
                        score = 0.0
                except (TypeError, ValueError, IndexError):
                    score = 0.0

                # Handle NaN
                if pd.isna(score):
                    score = 0.0

                # Update cached score
                h.inconsistency_score = score
                session.add(h)

                results.append(
                    {
                        "hypothesis_id": h.id,
                        "label": h.label,
                        "description": h.description,
                        "color": h.color,
                        "inconsistency_score": score,
                        "rank": 0,  # Will be set after sorting
                    }
                )

            session.commit()

            # Sort by score (lowest first = best fit)
            results.sort(key=lambda x: x["inconsistency_score"])

            # Assign ranks
            for i, r in enumerate(results):
                r["rank"] = i + 1

            return results
        except Exception as e:
            session.rollback()
            logger.error(f"Error calculating scores: {e}")
            return []
        finally:
            session.close()

    def get_score_chart(self, analysis_id: int) -> Dict[str, Any]:
        """
        Generate a Plotly bar chart configuration for hypothesis scores.

        Phase 4: Returns Plotly figure config for use with rx.plotly().
        Color scale: Red (high/bad) to Green (low/good).

        Returns:
            Dict with Plotly figure data and layout that can be serialized.
        """
        try:
            scores = self.calculate_scores(analysis_id)
            if not scores:
                return {}

            # Prepare data for Plotly
            labels = [s["label"] for s in scores]
            values = [s["inconsistency_score"] for s in scores]
            descriptions = [
                s["description"][:40] + "..."
                if len(s["description"]) > 40
                else s["description"]
                for s in scores
            ]

            # Build Plotly figure configuration
            figure = {
                "data": [
                    {
                        "type": "bar",
                        "x": values,
                        "y": labels,
                        "orientation": "h",
                        "text": [f"{v:.1f}" for v in values],
                        "textposition": "outside",
                        "hovertext": descriptions,
                        "hoverinfo": "text+x",
                        "marker": {
                            "color": values,
                            "colorscale": [
                                [0, "#22c55e"],  # Green (low score = good)
                                [0.5, "#eab308"],  # Yellow (medium)
                                [1, "#ef4444"],  # Red (high score = bad)
                            ],
                            "cmin": 0,
                            "cmax": max(values) if values else 1,
                        },
                    }
                ],
                "layout": {
                    "title": {
                        "text": "Hypothesis Inconsistency Scores",
                        "font": {"size": 16},
                    },
                    "xaxis": {
                        "title": "Inconsistency Score (Lower = Better)",
                        "tickfont": {"size": 12},
                    },
                    "yaxis": {
                        "categoryorder": "total ascending",
                        "tickfont": {"size": 12},
                    },
                    "height": max(200, len(scores) * 60),
                    "margin": {"l": 80, "r": 40, "t": 50, "b": 50},
                    "showlegend": False,
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                },
            }

            return figure
        except Exception as e:
            logger.error(f"Error creating score chart: {e}")
            return {}

    def check_close_race(
        self, analysis_id: int, threshold: float = 1.0
    ) -> Dict[str, Any]:
        """
        Check if top hypotheses are in a close race.

        Returns warning if the score difference between top 2 is within threshold.
        """
        scores = self.calculate_scores(analysis_id)
        if len(scores) < 2:
            return {"is_close": False, "message": "Need at least 2 hypotheses"}

        diff = abs(scores[1]["inconsistency_score"] - scores[0]["inconsistency_score"])
        is_close = diff <= threshold

        return {
            "is_close": is_close,
            "score_difference": diff,
            "top_hypothesis": scores[0]["label"],
            "second_hypothesis": scores[1]["label"],
            "message": (
                f"Close race detected: {scores[0]['label']} and {scores[1]['label']} "
                f"differ by only {diff:.1f} points. Consider gathering more discriminating evidence."
                if is_close
                else f"{scores[0]['label']} leads by {diff:.1f} points."
            ),
        }

    # =========================================================================
    # CONSISTENCY CHECKS
    # =========================================================================

    def run_consistency_checks(self, analysis_id: int) -> List[Dict[str, Any]]:
        """
        Run all consistency checks for an analysis.

        Returns list of check results.
        """
        checks = []

        # Check 1: Null hypothesis present
        checks.append(self._check_null_hypothesis(analysis_id))

        # Check 2: Incomplete ratings
        checks.append(self._check_incomplete_ratings(analysis_id))

        # Check 3: Low diagnostic evidence
        checks.append(self._check_low_diagnostic_evidence(analysis_id))

        # Check 4: Single-source evidence
        checks.append(self._check_evidence_diversity(analysis_id))

        return checks

    def _check_null_hypothesis(self, analysis_id: int) -> Dict[str, Any]:
        """Check if a null/baseline hypothesis exists."""
        session = self.Session()
        try:
            hypotheses = (
                session.query(ACHHypothesis).filter_by(analysis_id=analysis_id).all()
            )

            # Look for keywords suggesting null hypothesis
            null_keywords = [
                "null",
                "nothing",
                "no",
                "coincidence",
                "normal",
                "baseline",
            ]
            has_null = any(
                any(kw in h.description.lower() for kw in null_keywords)
                for h in hypotheses
            )

            return {
                "check_type": "null_hypothesis",
                "passed": has_null,
                "message": (
                    "Good: Analysis includes a null/baseline hypothesis."
                    if has_null
                    else "Consider adding a 'null hypothesis' - what if nothing unusual happened?"
                ),
            }
        finally:
            session.close()

    def _check_incomplete_ratings(self, analysis_id: int) -> Dict[str, Any]:
        """Check for unrated cells in the matrix."""
        matrix = self.get_matrix(analysis_id)
        total = matrix["total_cells"]
        rated = matrix["rated_cells"]
        pct = matrix["completion_pct"]

        return {
            "check_type": "incomplete_ratings",
            "passed": pct >= 100,
            "message": (
                "All matrix cells have been rated."
                if pct >= 100
                else f"Matrix is {pct:.0f}% complete ({rated}/{total} cells rated)."
            ),
            "details": {
                "total_cells": total,
                "rated_cells": rated,
                "completion_pct": pct,
            },
        }

    def _check_low_diagnostic_evidence(self, analysis_id: int) -> Dict[str, Any]:
        """Check for evidence with low diagnostic value."""
        diagnosticity = self.calculate_diagnosticity(analysis_id)
        low_diagnostic = [e for e in diagnosticity if e["is_low_diagnostic"]]

        passed = len(low_diagnostic) == 0

        return {
            "check_type": "low_diagnostic_evidence",
            "passed": passed,
            "message": (
                "All evidence items have diagnostic value."
                if passed
                else f"{len(low_diagnostic)} evidence items have low diagnostic value. "
                "Consider whether they help distinguish between hypotheses."
            ),
            "details": {
                "low_diagnostic_count": len(low_diagnostic),
                "low_diagnostic_labels": [e["label"] for e in low_diagnostic],
            },
        }

    def _check_evidence_diversity(self, analysis_id: int) -> Dict[str, Any]:
        """Check for evidence type diversity."""
        session = self.Session()
        try:
            evidence = (
                session.query(ACHEvidence).filter_by(analysis_id=analysis_id).all()
            )

            if not evidence:
                return {
                    "check_type": "evidence_diversity",
                    "passed": False,
                    "message": "No evidence added yet.",
                }

            types = set(e.evidence_type for e in evidence)
            has_diversity = len(types) >= 2

            return {
                "check_type": "evidence_diversity",
                "passed": has_diversity,
                "message": (
                    f"Good: Evidence includes multiple types: {', '.join(types)}."
                    if has_diversity
                    else f"Consider adding different types of evidence. Currently only: {', '.join(types)}."
                ),
                "details": {"evidence_types": list(types)},
            }
        finally:
            session.close()

    # =========================================================================
    # STEP 7: SENSITIVITY ANALYSIS (Phase 4)
    # =========================================================================

    def toggle_evidence_excluded(
        self, analysis_id: int, evidence_id: int, excluded: bool
    ) -> bool:
        """
        Toggle whether evidence is excluded from calculations.

        This is the core sensitivity analysis mechanism - users can exclude
        evidence items to see how conclusions change.
        """
        session = self.Session()
        try:
            evidence = session.query(ACHEvidence).get(evidence_id)
            if evidence and evidence.analysis_id == analysis_id:
                # Use is_critical as the exclusion flag (repurposing for now)
                # 0 = included, 1 = excluded
                evidence.is_critical = 1 if excluded else 0
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error toggling evidence exclusion: {e}")
            return False
        finally:
            session.close()

    def calculate_scores_excluding(
        self, analysis_id: int, exclude_evidence_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        Calculate scores excluding specific evidence items.

        Returns the same structure as calculate_scores but ignores
        specified evidence items.
        """
        session = self.Session()
        try:
            # Get numeric matrix but filter out excluded evidence
            df, evidence_ids, hypothesis_ids = self.get_matrix_dataframe(analysis_id)
            if df.empty:
                return []

            # Get evidence labels to exclude
            evidence_to_exclude = set()
            for e_id in exclude_evidence_ids:
                for label, eid in evidence_ids.items():
                    if eid == e_id:
                        evidence_to_exclude.add(label)
                        break

            # Filter DataFrame
            if evidence_to_exclude:
                df_filtered = df.drop(labels=list(evidence_to_exclude), errors="ignore")
            else:
                df_filtered = df

            if df_filtered.empty:
                return []

            # Calculate scores on filtered data
            numeric_df = df_filtered.replace(RATING_VALUES)
            scores_series = numeric_df.clip(lower=0).sum()

            # Get hypotheses from database for metadata
            hypotheses = (
                session.query(ACHHypothesis)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHHypothesis.display_order)
                .all()
            )

            if not hypotheses:
                return []

            results = []
            for h in hypotheses:
                score = float(scores_series.get(h.label, 0.0))
                if pd.isna(score):
                    score = 0.0

                results.append(
                    {
                        "hypothesis_id": h.id,
                        "label": h.label,
                        "description": h.description,
                        "color": h.color,
                        "inconsistency_score": score,
                        "rank": 0,
                    }
                )

            # Sort by score (lowest first = best fit)
            results.sort(key=lambda x: x["inconsistency_score"])

            # Assign ranks
            for i, r in enumerate(results):
                r["rank"] = i + 1

            return results
        except Exception as e:
            logger.error(f"Error calculating scores with exclusions: {e}")
            return []
        finally:
            session.close()

    def run_sensitivity_analysis(self, analysis_id: int) -> List[Dict[str, Any]]:
        """
        Run full sensitivity analysis.

        For each evidence item, calculates what would happen if it were wrong/excluded.
        Returns a list of sensitivity scenarios sorted by impact.
        """
        session = self.Session()
        try:
            # Get baseline scores
            baseline_scores = self.calculate_scores(analysis_id)
            if not baseline_scores:
                return []

            baseline_winner = baseline_scores[0]["hypothesis_id"]
            baseline_rankings = {s["hypothesis_id"]: s["rank"] for s in baseline_scores}

            # Get all evidence
            evidence = (
                session.query(ACHEvidence)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHEvidence.display_order)
                .all()
            )

            results = []
            for e in evidence:
                # Calculate scores without this evidence
                alt_scores = self.calculate_scores_excluding(analysis_id, [e.id])
                if not alt_scores:
                    continue

                alt_winner = alt_scores[0]["hypothesis_id"]
                alt_rankings = {s["hypothesis_id"]: s["rank"] for s in alt_scores}

                # Compare rankings
                ranking_changes = {}
                for h_id, baseline_rank in baseline_rankings.items():
                    alt_rank = alt_rankings.get(h_id, baseline_rank)
                    if alt_rank != baseline_rank:
                        ranking_changes[h_id] = alt_rank - baseline_rank

                # Determine impact level
                winner_changed = alt_winner != baseline_winner
                any_rank_changed = len(ranking_changes) > 0

                impact = "none"
                if winner_changed:
                    impact = "critical"
                elif any_rank_changed:
                    impact = "moderate"

                # Generate a meaningful description
                if winner_changed:
                    description = "If this evidence is wrong, the winner would change!"
                elif any_rank_changed:
                    description = (
                        "If this evidence is wrong, hypothesis rankings would shift."
                    )
                else:
                    description = "This evidence has minimal impact on conclusions."

                results.append(
                    {
                        "evidence_id": e.id,
                        "evidence_label": e.label,
                        "evidence_description": e.description[:50]
                        + ("..." if len(e.description) > 50 else ""),
                        "description": description,  # For display
                        "impact": impact,
                        "winner_changed": winner_changed,
                        "ranking_changes": ranking_changes,
                        "baseline_winner_id": baseline_winner,
                        "alt_winner_id": alt_winner,
                        "diagnosticity_score": e.diagnosticity_score or 0,
                    }
                )

            # Sort by impact (critical first, then moderate, then none)
            impact_order = {"critical": 0, "moderate": 1, "none": 2}
            results.sort(
                key=lambda x: (
                    impact_order.get(x["impact"], 3),
                    -x["diagnosticity_score"],
                )
            )

            return results
        except Exception as e:
            logger.error(f"Error running sensitivity analysis: {e}")
            return []
        finally:
            session.close()

    def get_critical_evidence(self, analysis_id: int) -> List[Dict[str, Any]]:
        """
        Get evidence items that would change the conclusion if removed.

        Quick helper to find the most impactful evidence.
        """
        sensitivity = self.run_sensitivity_analysis(analysis_id)
        return [s for s in sensitivity if s["impact"] == "critical"]

    # =========================================================================
    # STEP 8: MILESTONES (Phase 5)
    # =========================================================================

    def add_milestone(
        self,
        analysis_id: int,
        hypothesis_id: int,
        description: str,
        expected_by: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add a future indicator/milestone to a hypothesis."""
        session = self.Session()
        try:
            milestone = ACHMilestone(
                analysis_id=analysis_id,
                hypothesis_id=hypothesis_id,
                description=description,
                expected_by=expected_by,
                observed=0,  # Pending
            )
            session.add(milestone)
            session.commit()
            session.refresh(milestone)

            logger.info(f"Added milestone to hypothesis {hypothesis_id}")
            return self._milestone_to_dict(milestone)
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding milestone: {e}")
            return None
        finally:
            session.close()

    def update_milestone(
        self,
        milestone_id: int,
        observed: Optional[int] = None,
        observation_notes: Optional[str] = None,
        observed_date: Optional[datetime] = None,
        description: Optional[str] = None,
        expected_by: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a milestone status or details."""
        session = self.Session()
        try:
            m = session.query(ACHMilestone).filter_by(id=milestone_id).first()
            if not m:
                return None

            if observed is not None:
                m.observed = observed
                # potential auto-set observed date if changing to observed/contradicted
                if observed != 0 and observed_date is None and m.observed_date is None:
                    m.observed_date = datetime.utcnow()

            if observed_date is not None:
                m.observed_date = observed_date

            if observation_notes is not None:
                m.observation_notes = observation_notes

            if description is not None:
                m.description = description

            if expected_by is not None:
                m.expected_by = expected_by

            session.commit()
            session.refresh(m)
            return self._milestone_to_dict(m)
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating milestone {milestone_id}: {e}")
            return None
        finally:
            session.close()

    def delete_milestone(self, milestone_id: int) -> bool:
        """Delete a milestone."""
        session = self.Session()
        try:
            m = session.query(ACHMilestone).filter_by(id=milestone_id).first()
            if not m:
                return False

            session.delete(m)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting milestone {milestone_id}: {e}")
            return False
        finally:
            session.close()

    def get_analysis_milestones(self, analysis_id: int) -> List[Dict[str, Any]]:
        """Get all milestones for an analysis."""
        session = self.Session()
        try:
            milestones = (
                session.query(ACHMilestone)
                .filter_by(analysis_id=analysis_id)
                .order_by(
                    ACHMilestone.expected_by.asc().nullslast(), ACHMilestone.created_at
                )
                .all()
            )
            return [self._milestone_to_dict(m) for m in milestones]
        finally:
            session.close()

    # =========================================================================
    # STEP 8: EXPORT

    # =========================================================================

    def export_markdown(self, analysis_id: int) -> str:
        """Export analysis as Markdown document."""
        analysis = self.get_analysis(analysis_id)
        if not analysis:
            return ""

        scores = self.calculate_scores(analysis_id)
        diagnosticity = self.calculate_diagnosticity(analysis_id)
        checks = self.run_consistency_checks(analysis_id)

        lines = []

        # Header
        lines.append(f"# ACH Analysis: {analysis['title']}")
        lines.append("")
        lines.append(f"**Focus Question:** {analysis['focus_question']}")
        lines.append("")
        if analysis.get("description"):
            lines.append(f"**Description:** {analysis['description']}")
            lines.append("")
        lines.append(f"**Status:** {analysis['status']}")
        lines.append(f"**Created:** {analysis.get('created_at', 'N/A')}")
        lines.append("")

        # Hypotheses
        lines.append("## Hypotheses")
        lines.append("")
        for h in analysis.get("hypotheses", []):
            lines.append(f"### {h['label']}: {h['description']}")
            if h.get("future_indicators"):
                lines.append(f"**Future Indicators:** {h['future_indicators']}")
            lines.append("")

        # Evidence
        lines.append("## Evidence")
        lines.append("")
        for e in analysis.get("evidence", []):
            rel_badge = f"[{e['reliability'].upper()}]"
            type_badge = f"({e['evidence_type']})"
            lines.append(
                f"### {e['label']}: {e['description']} {rel_badge} {type_badge}"
            )
            if e.get("source"):
                lines.append(f"> {e['source']}")
            lines.append("")

        # Matrix
        lines.append("## Analysis Matrix")
        lines.append("")

        hypotheses = analysis.get("hypotheses", [])
        evidence_list = analysis.get("evidence", [])

        if hypotheses and evidence_list:
            # Header row
            header = "| Evidence |"
            divider = "|----------|"
            for h in hypotheses:
                header += f" {h['label']} |"
                divider += "------|"
            lines.append(header)
            lines.append(divider)

            # Data rows
            for e in evidence_list:
                row = f"| {e['label']} |"
                for h in hypotheses:
                    rating = e.get("ratings", {}).get(h["id"], "")
                    row += f" {rating or '-'} |"
                lines.append(row)
            lines.append("")

        # Scores
        lines.append("## Hypothesis Scores")
        lines.append("")
        lines.append("Lower score = fewer inconsistencies = better fit")
        lines.append("")
        for s in scores:
            lines.append(
                f"- **{s['label']}** (Rank #{s['rank']}): {s['inconsistency_score']:.1f} points"
            )
        lines.append("")

        # Diagnosticity
        lines.append("## Evidence Diagnosticity")
        lines.append("")
        lines.append("Higher score = better at discriminating between hypotheses")
        lines.append("")
        for d in diagnosticity[:5]:  # Top 5
            level = (
                "HIGH"
                if d["is_high_diagnostic"]
                else "LOW"
                if d["is_low_diagnostic"]
                else "MED"
            )
            lines.append(
                f"- **{d['label']}** [{level}]: {d['diagnosticity_score']:.2f}"
            )
        lines.append("")

        # Consistency Checks
        lines.append("## Consistency Checks")
        lines.append("")
        for c in checks:
            status = "[PASS]" if c["passed"] else "[WARN]"
            lines.append(f"- {status} {c['message']}")
        lines.append("")

        # Sensitivity Notes
        if analysis.get("sensitivity_notes"):
            lines.append("## Sensitivity Analysis")
            lines.append("")
            lines.append(analysis["sensitivity_notes"])
            lines.append("")

        # Key Assumptions
        if analysis.get("key_assumptions"):
            lines.append("## Key Assumptions")
            lines.append("")
            for a in analysis["key_assumptions"]:
                lines.append(f"- {a}")
            lines.append("")

        # Milestones (Step 8)
        milestones = self.get_analysis_milestones(analysis_id)
        if milestones:
            lines.append("## Milestones & Future Indicators")
            lines.append("")
            lines.append("| Status | Milestone | Expected By | Observed Date |")
            lines.append("|--------|-----------|-------------|---------------|")
            for m in milestones:
                status = "PENDING"
                if m.get("observed") == 1:
                    status = "OBSERVED"
                elif m.get("observed") == -1:
                    status = "CONTRADICTED"

                expected = (
                    m.get("expected_by").split("T")[0] if m.get("expected_by") else "-"
                )
                observed_date = (
                    m.get("observed_date").split("T")[0]
                    if m.get("observed_date")
                    else "-"
                )

                lines.append(
                    f"| {status} | {m['description']} | {expected} | {observed_date} |"
                )
                if m.get("observation_notes"):
                    lines.append(f"> Notes: {m['observation_notes']}")
            lines.append("")

        # Phase 4: AI Disclosure
        ai_items = []
        # Check for AI-suggested hypotheses (high_diagnostic or future: ai_origin field)
        for h in analysis.get("hypotheses", []):
            if h.get("ai_origin"):
                ai_items.append(f"- Hypothesis **{h['label']}**: AI-suggested")
        # Check for AI-suggested evidence
        for e in analysis.get("evidence", []):
            if e.get("ai_origin"):
                ai_items.append(f"- Evidence **{e['label']}**: AI-suggested")

        if ai_items:
            lines.append("## AI Disclosure")
            lines.append("")
            lines.append(
                "*This analysis includes elements suggested or assisted by AI. "
                "All AI suggestions were reviewed and accepted by the analyst.*"
            )
            lines.append("")
            for item in ai_items:
                lines.append(item)
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(
            f"*Exported from ArkhamMirror ACH on {datetime.utcnow().isoformat()}*"
        )

        return "\n".join(lines)

    def export_json(self, analysis_id: int) -> Dict[str, Any]:
        """Export analysis as JSON."""
        analysis = self.get_analysis(analysis_id)
        if not analysis:
            return {}

        # Phase 4: AI Disclosure
        ai_disclosure = []
        for h in analysis.get("hypotheses", []):
            if h.get("ai_origin"):
                ai_disclosure.append(
                    {
                        "type": "hypothesis",
                        "label": h["label"],
                        "ai_origin": h["ai_origin"],
                    }
                )
        for e in analysis.get("evidence", []):
            if e.get("ai_origin"):
                ai_disclosure.append(
                    {
                        "type": "evidence",
                        "label": e["label"],
                        "ai_origin": e["ai_origin"],
                    }
                )

        return {
            "analysis": analysis,
            "scores": self.calculate_scores(analysis_id),
            "diagnosticity": self.calculate_diagnosticity(analysis_id),
            "consistency_checks": self.run_consistency_checks(analysis_id),
            "ai_disclosure": ai_disclosure,
            "exported_at": datetime.utcnow().isoformat(),
        }

    def export_pdf(self, analysis_id: int, output_path: str) -> str:
        """
        Export analysis as PDF using ReportLab Platypus.

        Phase 4: Professional PDF export with full descriptions and evidence legend.

        Args:
            analysis_id: The analysis to export
            output_path: Full path where to save the PDF

        Returns:
            The output path if successful, empty string on error.
        """
        try:
            from reportlab.platypus import (
                SimpleDocTemplate,
                Table,
                TableStyle,
                Paragraph,
                Spacer,
                PageBreak,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.units import inch

            # Get data
            analysis = self.get_analysis(analysis_id)
            if not analysis:
                return ""

            scores = self.calculate_scores(analysis_id)
            df, evidence_ids, hypothesis_ids = self.get_matrix_dataframe(analysis_id)
            consistency_checks = self.run_consistency_checks(analysis_id)

            # Get full evidence and hypothesis data for legend
            session = self.Session()
            hypotheses = (
                session.query(ACHHypothesis)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHHypothesis.display_order)
                .all()
            )
            evidence_items = (
                session.query(ACHEvidence)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHEvidence.display_order)
                .all()
            )

            # Create document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=0.5 * inch,
                leftMargin=0.5 * inch,
                topMargin=0.5 * inch,
                bottomMargin=0.5 * inch,
            )

            styles = getSampleStyleSheet()
            elements = []

            # Custom styles
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=20,
                spaceAfter=12,
                textColor=colors.HexColor("#1f2937"),
            )
            h2_style = ParagraphStyle(
                "H2",
                parent=styles["Heading2"],
                fontSize=14,
                spaceBefore=12,
                spaceAfter=8,
                textColor=colors.HexColor("#374151"),
            )
            body_style = ParagraphStyle(
                "Body",
                parent=styles["Normal"],
                fontSize=10,
                leading=14,
            )
            small_style = ParagraphStyle(
                "Small",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#6b7280"),
            )

            # === PAGE 1: Title & Executive Summary ===
            elements.append(Paragraph("ACH Analysis Report", title_style))
            elements.append(
                Paragraph(f"<b>{analysis['title']}</b>", styles["Heading2"])
            )
            elements.append(Spacer(1, 8))

            # Focus Question
            elements.append(
                Paragraph(
                    f"<b>Focus Question:</b> {analysis['focus_question']}",
                    body_style,
                )
            )
            elements.append(Spacer(1, 16))

            # Executive Summary Box
            if scores:
                winner = scores[0]
                elements.append(Paragraph("Executive Summary", h2_style))
                elements.append(
                    Paragraph(
                        f"Based on the analysis of <b>{len(evidence_items)}</b> pieces of evidence "
                        f"against <b>{len(hypotheses)}</b> hypotheses, the most consistent hypothesis is:",
                        body_style,
                    )
                )
                elements.append(Spacer(1, 8))
                elements.append(
                    Paragraph(
                        f"<b>{winner['label']}: {winner['description']}</b>",
                        ParagraphStyle(
                            "Winner", parent=body_style, fontSize=11, leftIndent=20
                        ),
                    )
                )
                elements.append(
                    Paragraph(
                        f"Inconsistency Score: {winner['inconsistency_score']:.1f} (lower is better)",
                        small_style,
                    )
                )
                elements.append(Spacer(1, 16))

            # === Key Sensitivity Factors ===
            sensitivity = self.run_sensitivity_analysis(analysis_id)
            critical_factors = [s for s in sensitivity if s["impact"] == "critical"]

            if critical_factors:
                elements.append(Paragraph("Key Sensitivity Factors", h2_style))
                elements.append(
                    Paragraph(
                        "<b>STRATEGIC ALERT:</b> The conclusion relies heavily on the accuracy of the following evidence. "
                        "If these items are incorrect or misinterpreted, the leading hypothesis would change.",
                        ParagraphStyle(
                            "Alert",
                            parent=body_style,
                            textColor=colors.HexColor("#b91c1c"),  # Red text for alert
                            backColor=colors.HexColor(
                                "#fef2f2"
                            ),  # Light red background
                            borderColor=colors.HexColor("#fca5a5"),
                            borderWidth=1,
                            borderPadding=8,
                            borderRadius=4,
                        ),
                    )
                )
                elements.append(Spacer(1, 8))

                for factor in critical_factors:
                    elements.append(
                        Paragraph(
                            f"• <b>{factor['evidence_label']}</b>: {factor['description']}",
                            ParagraphStyle(
                                "CriticalFactor",
                                parent=body_style,
                                leftIndent=10,
                                bulletIndent=0,
                            ),
                        )
                    )
                elements.append(Spacer(1, 16))
            elif sensitivity:
                # If no critical factors but moderate ones exist, maybe mention them?
                # User specifically asked for "Vulnerability Note" style for critical ones.
                # We can add a "Robustness" note if no critical factors exist.
                elements.append(Paragraph("Key Sensitivity Factors", h2_style))
                elements.append(
                    Paragraph(
                        "<b>Robustness Note:</b> The conclusion appears robust. No single piece of evidence, "
                        "if removed or re-evaluated, would currently change the leading hypothesis.",
                        ParagraphStyle(
                            "Robust",
                            parent=body_style,
                            textColor=colors.HexColor("#15803d"),  # Green text
                        ),
                    )
                )
                elements.append(Spacer(1, 16))

            # === Hypothesis Rankings with Full Descriptions ===
            elements.append(Paragraph("Hypothesis Rankings", h2_style))
            elements.append(
                Paragraph(
                    "<i>Ranked by consistency with evidence (most consistent first)</i>",
                    small_style,
                )
            )
            elements.append(Spacer(1, 8))

            for i, s in enumerate(scores):
                rank_color = "#22c55e" if i == 0 else "#6b7280"
                elements.append(
                    Paragraph(
                        f"<b>#{s['rank']} - {s['label']}: {s['description']}</b>",
                        ParagraphStyle(
                            f"Rank{i}",
                            parent=body_style,
                            fontSize=10,
                            textColor=colors.HexColor(rank_color),
                        ),
                    )
                )
                elements.append(
                    Paragraph(
                        f"Score: {s['inconsistency_score']:.1f}",
                        ParagraphStyle("Score", parent=small_style, leftIndent=20),
                    )
                )
                elements.append(Spacer(1, 6))

            elements.append(Spacer(1, 12))

            # === PAGE 2: Evidence Legend ===
            elements.append(PageBreak())
            elements.append(Paragraph("Evidence Legend", h2_style))
            elements.append(
                Paragraph(
                    "<i>Full descriptions for evidence items shown in the matrix</i>",
                    small_style,
                )
            )
            elements.append(Spacer(1, 8))

            for e in evidence_items:
                reliability = e.reliability or "unknown"
                source_text = f" | Source: {e.source}" if e.source else ""
                elements.append(
                    Paragraph(
                        f"<b>{e.label}</b>: {e.description}",
                        body_style,
                    )
                )
                elements.append(
                    Paragraph(
                        f"Type: {e.evidence_type} | Reliability: {reliability}{source_text}",
                        small_style,
                    )
                )
                elements.append(Spacer(1, 8))

            # === PAGE 3: Matrix ===
            elements.append(PageBreak())
            elements.append(Paragraph("ACH Rating Matrix", h2_style))
            elements.append(
                Paragraph(
                    "<i>CC = Very Consistent, C = Consistent, N = Neutral, "
                    "I = Inconsistent, II = Very Inconsistent</i>",
                    small_style,
                )
            )
            elements.append(Spacer(1, 12))

            if not df.empty:
                # Build matrix data
                matrix_data = [["Evidence"] + list(df.columns)]
                for idx in df.index:
                    row = [idx] + list(df.loc[idx])
                    matrix_data.append(row)

                # Calculate column widths dynamically
                num_cols = len(df.columns)
                ev_width = 1 * inch
                remaining = 7 * inch - ev_width
                hyp_width = remaining / max(1, num_cols)
                col_widths = [ev_width] + [hyp_width] * num_cols

                matrix_table = Table(matrix_data, colWidths=col_widths)

                # Build style with rating colors
                table_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e5e7eb")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]

                # Add rating-based colors
                rating_colors = {
                    "CC": colors.HexColor("#d4edda"),
                    "C": colors.HexColor("#e7f3e9"),
                    "N": colors.HexColor("#ffffff"),
                    "I": colors.HexColor("#ffe5e5"),
                    "II": colors.HexColor("#f8d7da"),
                    "-": colors.HexColor("#f3f4f6"),
                }

                for r_idx, row in enumerate(matrix_data[1:], 1):
                    for c_idx, cell in enumerate(row[1:], 1):
                        if cell in rating_colors:
                            table_style.append(
                                (
                                    "BACKGROUND",
                                    (c_idx, r_idx),
                                    (c_idx, r_idx),
                                    rating_colors[cell],
                                )
                            )

                matrix_table.setStyle(TableStyle(table_style))
                elements.append(matrix_table)
                elements.append(Spacer(1, 18))

            # Consistency Issues
            if consistency_checks:
                elements.append(Paragraph("Consistency Notes", h2_style))
                for check in consistency_checks:
                    icon = "✓" if check["passed"] else "⚠"
                    elements.append(Paragraph(f"{icon} {check['message']}", body_style))
                elements.append(Spacer(1, 12))

            # === AI Disclosure Section ===
            elements.append(Spacer(1, 20))
            elements.append(
                Paragraph(
                    "<b>AI Assistance Disclosure</b>",
                    ParagraphStyle(
                        "Disclosure",
                        parent=small_style,
                        fontSize=9,
                        textColor=colors.HexColor("#9ca3af"),
                    ),
                )
            )
            elements.append(
                Paragraph(
                    "This analysis may have been assisted by AI-powered features including: "
                    "hypothesis generation, evidence suggestions, matrix rating recommendations, "
                    "devil's advocate challenges, and milestone suggestions. All AI outputs were "
                    "subject to human review and modification.",
                    small_style,
                )
            )

            # Footer
            elements.append(Spacer(1, 12))
            elements.append(
                Paragraph(
                    f"<i>Generated by ArkhamMirror ACH • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>",
                    small_style,
                )
            )

            # Build PDF
            doc.build(elements)
            session.close()
            return output_path

        except Exception as e:
            logger.error(f"Error exporting PDF: {e}")
            return ""

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _analysis_to_dict(self, a: ACHAnalysis) -> Dict[str, Any]:
        """Convert ACHAnalysis ORM object to dictionary."""
        return {
            "id": a.id,
            "project_id": a.project_id,
            "title": a.title,
            "focus_question": a.focus_question,
            "description": a.description,
            "status": a.status,
            "sensitivity_notes": a.sensitivity_notes,
            "key_assumptions": json.loads(a.key_assumptions)
            if a.key_assumptions
            else [],
            "current_step": a.current_step,
            "steps_completed": json.loads(a.steps_completed)
            if a.steps_completed
            else [],
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            "hypotheses": [],
            "evidence": [],
            "hypothesis_count": 0,
            "evidence_count": 0,
        }

    def _hypothesis_to_dict(self, h: ACHHypothesis) -> Dict[str, Any]:
        """Convert ACHHypothesis ORM object to dictionary."""
        return {
            "id": h.id,
            "label": h.label,
            "description": h.description,
            "display_order": h.display_order,
            "color": h.color,
            "inconsistency_score": h.inconsistency_score,
            "future_indicators": h.future_indicators,
            "indicator_timeframe": h.indicator_timeframe,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }

    def _evidence_to_dict(self, e: ACHEvidence) -> Dict[str, Any]:
        """Convert ACHEvidence ORM object to dictionary."""
        return {
            "id": e.id,
            "label": e.label,
            "description": e.description,
            "display_order": e.display_order,
            "evidence_type": e.evidence_type,
            "reliability": e.reliability,
            "source": e.source,
            "source_document_id": e.source_document_id,
            "diagnosticity_score": e.diagnosticity_score,
            "is_critical": bool(e.is_critical),
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "ratings": {},
        }

    # =========================================================================
    # PHASE 2: AI ASSISTANCE
    # =========================================================================

    def suggest_hypotheses(
        self,
        analysis_id: int,
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to suggest hypotheses based on the focus question.

        Args:
            analysis_id: The ACH analysis ID
            count: Number of suggestions to generate (default 3)

        Returns:
            List of hypothesis suggestions with description and rationale
        """
        # Lazy import to avoid slow startup
        from app.arkham.services.llm_service import chat_with_llm

        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            if not analysis:
                logger.warning(f"Analysis {analysis_id} not found")
                return []

            # Get existing hypotheses to avoid duplicates
            existing = (
                session.query(ACHHypothesis).filter_by(analysis_id=analysis_id).all()
            )
            existing_descriptions = [h.description for h in existing]

            # Build prompt
            prompt = f"""You are an intelligence analyst helping with Analysis of Competing Hypotheses (ACH).

FOCUS QUESTION:
{analysis.focus_question}

{"EXISTING HYPOTHESES (avoid duplicates):" + chr(10) + chr(10).join(f"- {d}" for d in existing_descriptions) if existing_descriptions else "No hypotheses yet."}

Generate {count} NEW competing hypotheses that could explain the focus question.

Requirements:
- Each hypothesis should be a distinct, plausible explanation
- Include at least one "null hypothesis" (nothing unusual happened) if not already present
- Consider adversarial perspectives (what would a skeptic argue?)
- Be specific and testable

Return JSON only:
{{
  "hypotheses": [
    {{
      "description": "Clear statement of the hypothesis",
      "rationale": "Why this is a plausible alternative worth considering",
      "is_null": false
    }}
  ]
}}"""

            response = chat_with_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
                json_mode=True,
                use_cache=False,  # Don't cache suggestions
            )

            # Parse response
            try:
                # Clean up markdown if present
                cleaned = response
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0]
                elif "```" in cleaned:
                    parts = cleaned.split("```")
                    if len(parts) > 1:
                        cleaned = parts[1]

                data = json.loads(cleaned)
                suggestions = data.get("hypotheses", [])
                logger.info(
                    f"Generated {len(suggestions)} hypothesis suggestions for analysis {analysis_id}"
                )
                return suggestions
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response: {e}")
                return []

        except Exception as e:
            logger.error(f"Error suggesting hypotheses: {e}")
            return []
        finally:
            session.close()

    def challenge_hypotheses(
        self,
        analysis_id: int,
        hypothesis_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to generate devil's advocate challenges to hypotheses.

        Args:
            analysis_id: The ACH analysis ID
            hypothesis_id: Optional - if provided, only challenge this hypothesis

        Returns challenges/counter-arguments for the specified hypothesis(es).
        """
        from app.arkham.services.llm_service import chat_with_llm

        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            if not analysis:
                return []

            # Get hypotheses - either single or all
            if hypothesis_id:
                hypotheses = (
                    session.query(ACHHypothesis).filter_by(id=hypothesis_id).all()
                )
            else:
                hypotheses = (
                    session.query(ACHHypothesis)
                    .filter_by(analysis_id=analysis_id)
                    .order_by(ACHHypothesis.display_order)
                    .all()
                )

            if not hypotheses:
                return []

            hypotheses_text = "\n".join(
                [f"{h.label}: {h.description}" for h in hypotheses]
            )

            prompt = f"""You are a devil's advocate challenging an intelligence analysis.

FOCUS QUESTION:
{analysis.focus_question}

CURRENT HYPOTHESES:
{hypotheses_text}

Generate a challenge for EACH hypothesis listed above. For each hypothesis, provide:
1. The strongest counter-argument
2. What evidence would DISPROVE this hypothesis
3. A possible alternative they haven't considered

You MUST generate one entry per hypothesis. Return JSON only:
{{
  "challenges": [
    {{
      "hypothesis_label": "H1",
      "counter_argument": "The main weakness of this hypothesis...",
      "disproof_evidence": "This hypothesis would be disproved if...",
      "alternative_angle": "Consider instead that..."
    }},
    {{
      "hypothesis_label": "H2",
      "counter_argument": "...",
      "disproof_evidence": "...",
      "alternative_angle": "..."
    }}
  ]
}}"""

            response = chat_with_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
                json_mode=True,
                use_cache=False,
            )

            try:
                cleaned = response
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0]
                elif "```" in cleaned:
                    parts = cleaned.split("```")
                    if len(parts) > 1:
                        cleaned = parts[1]

                data = json.loads(cleaned)
                return data.get("challenges", [])
            except json.JSONDecodeError:
                return []

        except Exception as e:
            logger.error(f"Error challenging hypotheses: {e}")
            return []
        finally:
            session.close()

    def suggest_evidence(
        self,
        analysis_id: int,
        count: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to suggest evidence items to consider for the analysis.

        Args:
            analysis_id: The ACH analysis ID
            count: Number of suggestions (default 5)

        Returns:
            List of evidence suggestions with description, type, and importance
        """
        from app.arkham.services.llm_service import chat_with_llm

        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            if not analysis:
                return []

            hypotheses = (
                session.query(ACHHypothesis).filter_by(analysis_id=analysis_id).all()
            )

            existing_evidence = (
                session.query(ACHEvidence).filter_by(analysis_id=analysis_id).all()
            )

            hypotheses_text = (
                "\n".join([f"- {h.description}" for h in hypotheses])
                if hypotheses
                else "None yet"
            )
            evidence_text = (
                "\n".join([f"- {e.description}" for e in existing_evidence])
                if existing_evidence
                else "None yet"
            )

            prompt = f"""You are an intelligence analyst helping with Analysis of Competing Hypotheses (ACH).

FOCUS QUESTION:
{analysis.focus_question}

HYPOTHESES BEING EVALUATED:
{hypotheses_text}

EXISTING EVIDENCE (avoid duplicates):
{evidence_text}

Suggest {count} NEW pieces of evidence or information that would help discriminate between the hypotheses.

Focus on:
- Evidence that would DISPROVE one or more hypotheses (most valuable)
- Observable facts that differ depending on which hypothesis is true
- Key assumptions that should be verified
- Missing information that would be diagnostic

Return JSON only:
{{
  "evidence": [
    {{
      "description": "Clear description of the evidence item",
      "evidence_type": "fact|testimony|document|assumption|argument",
      "importance": "Why this evidence would help discriminate between hypotheses",
      "would_support": ["H1", "H2"],
      "would_contradict": ["H3"]
    }}
  ]
}}"""

            response = chat_with_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
                json_mode=True,
                use_cache=False,
            )

            try:
                cleaned = response
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json")[1].split("```")[0]
                elif "```" in cleaned:
                    parts = cleaned.split("```")
                    if len(parts) > 1:
                        cleaned = parts[1]

                data = json.loads(cleaned)
                suggestions = data.get("evidence", [])
                logger.info(
                    f"Generated {len(suggestions)} evidence suggestions for analysis {analysis_id}"
                )
                return suggestions
            except json.JSONDecodeError:
                return []

        except Exception as e:
            logger.error(f"Error suggesting evidence: {e}")
            return []
        finally:
            session.close()

    def suggest_ratings(
        self,
        analysis_id: int,
        evidence_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to suggest ratings for a specific evidence item against all hypotheses.

        Makes individual requests per hypothesis for reliability.

        Args:
            analysis_id: The ACH analysis ID
            evidence_id: The specific evidence item to rate

        Returns:
            List of rating suggestions for each hypothesis with explanation
        """
        from app.arkham.services.llm_service import chat_with_llm

        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            evidence = session.query(ACHEvidence).filter_by(id=evidence_id).first()

            if not analysis or not evidence:
                return []

            hypotheses = (
                session.query(ACHHypothesis)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHHypothesis.display_order)
                .all()
            )

            if not hypotheses:
                return []

            # Make individual requests for each hypothesis for reliability
            all_ratings = []
            for h in hypotheses:
                prompt = f"""You are an intelligence analyst helping with Analysis of Competing Hypotheses (ACH).

FOCUS QUESTION:
{analysis.focus_question}

HYPOTHESIS TO EVALUATE:
{h.label}: {h.description}

EVIDENCE TO RATE:
Description: {evidence.description}
Type: {evidence.evidence_type}
Reliability: {evidence.reliability}
{f"Source: {evidence.source}" if evidence.source else ""}

Rate how CONSISTENT or INCONSISTENT this evidence is with the hypothesis above:

Rating Scale:
- CC (Very Consistent): If hypothesis is true, we would strongly expect to see this evidence
- C (Consistent): If hypothesis is true, this evidence is likely
- N (Neutral): Evidence neither supports nor contradicts the hypothesis
- I (Inconsistent): If hypothesis is true, this evidence is unlikely
- II (Very Inconsistent): If hypothesis is true, this evidence is very unlikely

KEY PRINCIPLE: Ask "If this hypothesis is TRUE, how likely would we be to observe this evidence?"

Return JSON only:
{{
  "rating": "CC|C|N|I|II",
  "explanation": "Brief explanation of why this rating"
}}"""

                try:
                    response = chat_with_llm(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=300,  # Much smaller for single rating
                        json_mode=True,
                        use_cache=True,  # Can cache individual ratings
                    )

                    # Parse response
                    cleaned = response
                    if "```json" in cleaned:
                        cleaned = cleaned.split("```json")[1].split("```")[0]
                    elif "```" in cleaned:
                        parts = cleaned.split("```")
                        if len(parts) > 1:
                            cleaned = parts[1]

                    data = json.loads(cleaned.strip())
                    rating = data.get("rating", "N")
                    explanation = data.get("explanation", "")

                    # Validate rating
                    if rating not in ["CC", "C", "N", "I", "II"]:
                        rating = "N"

                    all_ratings.append(
                        {
                            "hypothesis_label": h.label,
                            "hypothesis_id": h.id,
                            "rating": rating,
                            "explanation": explanation,
                        }
                    )

                except Exception as e:
                    logger.warning(f"Failed to get rating for {h.label}: {e}")
                    # Add neutral as fallback
                    all_ratings.append(
                        {
                            "hypothesis_label": h.label,
                            "hypothesis_id": h.id,
                            "rating": "N",
                            "explanation": "Could not generate suggestion",
                        }
                    )

            logger.info(
                f"Generated {len(all_ratings)} rating suggestions for evidence {evidence_id}"
            )
            return all_ratings

        except Exception as e:
            logger.error(f"Error suggesting ratings: {e}")
            return []
        finally:
            session.close()

    def suggest_all_ratings(
        self,
        analysis_id: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Use LLM to suggest ratings for ALL unrated evidence items.

        Returns:
            Dict mapping evidence_id to list of rating suggestions
        """
        session = self.Session()
        try:
            # Get all evidence with unrated cells
            evidence_list = (
                session.query(ACHEvidence).filter_by(analysis_id=analysis_id).all()
            )

            results = {}
            for e in evidence_list:
                suggestions = self.suggest_ratings(analysis_id, e.id)
                if suggestions:
                    results[e.id] = suggestions

            return results
        except Exception as e:
            logger.error(f"Error suggesting all ratings: {e}")
            return {}
        finally:
            session.close()

    def suggest_milestones(
        self,
        analysis_id: int,
        hypothesis_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to suggest observable milestones for tracking hypotheses.

        Args:
            analysis_id: The ACH analysis ID
            hypothesis_id: Optional specific hypothesis to suggest milestones for

        Returns:
            List of milestone suggestions with description and expected timeframe
        """
        from app.arkham.services.llm_service import chat_with_llm

        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            if not analysis:
                return []

            # Get hypotheses to suggest milestones for
            if hypothesis_id:
                hypotheses = (
                    session.query(ACHHypothesis)
                    .filter_by(id=hypothesis_id, analysis_id=analysis_id)
                    .all()
                )
            else:
                hypotheses = (
                    session.query(ACHHypothesis)
                    .filter_by(analysis_id=analysis_id)
                    .order_by(ACHHypothesis.display_order)
                    .all()
                )

            if not hypotheses:
                return []

            all_milestones = []
            for h in hypotheses:
                prompt = f"""You are an intelligence analyst helping with Analysis of Competing Hypotheses (ACH).

FOCUS QUESTION:
{analysis.focus_question}

HYPOTHESIS TO TRACK:
{h.label}: {h.description}
{f"Future indicators: {h.future_indicators}" if h.future_indicators else ""}

Suggest 2-3 OBSERVABLE MILESTONES that would help track whether this hypothesis is gaining or losing support over time.

A good milestone is:
- Observable and measurable (not vague)
- Time-bound (has an expected timeframe)
- Diagnostic (helps distinguish this hypothesis from others)

Examples:
- "If H1 is true, we expect to see X announcement within 30 days"
- "If H1 is false, Y metric should NOT exceed Z by next quarter"

Return JSON only:
{{
  "milestones": [
    {{
      "description": "Clear, observable milestone description",
      "expected_timeframe": "e.g., '30 days', '3 months', 'by Q2 2025'",
      "supports_if_observed": true,
      "rationale": "Why this milestone is diagnostic"
    }}
  ]
}}"""

                try:
                    response = chat_with_llm(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=800,
                        json_mode=True,
                        use_cache=True,
                    )

                    # Parse response
                    cleaned = response
                    if "```json" in cleaned:
                        cleaned = cleaned.split("```json")[1].split("```")[0]
                    elif "```" in cleaned:
                        parts = cleaned.split("```")
                        if len(parts) > 1:
                            cleaned = parts[1]

                    data = json.loads(cleaned.strip())
                    milestones = data.get("milestones", [])

                    for m in milestones:
                        m["hypothesis_id"] = h.id
                        m["hypothesis_label"] = h.label
                        all_milestones.append(m)

                except Exception as e:
                    logger.warning(f"Failed to get milestones for {h.label}: {e}")

            logger.info(
                f"Generated {len(all_milestones)} milestone suggestions for analysis {analysis_id}"
            )
            return all_milestones

        except Exception as e:
            logger.error(f"Error suggesting milestones: {e}")
            return []
        finally:
            session.close()

    # =========================================================================
    # PHASE 3: CORPUS INTEGRATION
    # =========================================================================

    def get_analysis_project_id(self, analysis_id: int) -> Optional[int]:
        """Get the project_id for an analysis (for import filtering)."""
        session = self.Session()
        try:
            analysis = session.query(ACHAnalysis).filter_by(id=analysis_id).first()
            return analysis.project_id if analysis else None
        finally:
            session.close()

    def import_search_result(
        self,
        analysis_id: int,
        text: str,
        doc_id: int,
        doc_title: str,
        score: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Import a search result as evidence.

        Args:
            analysis_id: ACH analysis ID
            text: The text content (will be truncated if too long)
            doc_id: Source document ID
            doc_title: Source document title
            score: Search relevance score

        Returns:
            Created evidence dict or None if failed
        """
        # Truncate description if too long
        description = text[:500] + "..." if len(text) > 500 else text

        return self.add_evidence(
            analysis_id=analysis_id,
            description=description,
            evidence_type="document",
            reliability="medium",
            source=f"Search result from: {doc_title} (score: {score:.2f})",
            source_document_id=doc_id,
        )

    def import_contradiction(
        self,
        analysis_id: int,
        contradiction_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Import a contradiction as evidence.

        Args:
            analysis_id: ACH analysis ID
            contradiction_id: Contradiction record ID

        Returns:
            Created evidence dict or None if failed
        """
        session = self.Session()

        try:
            # Fetch the contradiction
            from app.arkham.services.db.models import (
                Contradiction,
                ContradictionEvidence,
                CanonicalEntity,
            )

            contradiction = (
                session.query(Contradiction).filter_by(id=contradiction_id).first()
            )

            if not contradiction:
                logger.warning(f"Contradiction {contradiction_id} not found")
                return None

            # Get entity name
            entity = (
                session.query(CanonicalEntity)
                .filter_by(id=contradiction.entity_id)
                .first()
            )
            entity_name = entity.canonical_name if entity else "Unknown"

            # Get evidence chunks
            evidence_records = (
                session.query(ContradictionEvidence)
                .filter_by(contradiction_id=contradiction_id)
                .all()
            )

            # Build description
            description = (
                f"CONTRADICTION ({contradiction.severity}): {contradiction.description}"
            )

            if evidence_records:
                description += "\n\nConflicting claims:"
                for i, e in enumerate(evidence_records[:2]):  # Max 2 evidence chunks
                    text_preview = (
                        e.text_chunk[:200] + "..."
                        if len(e.text_chunk) > 200
                        else e.text_chunk
                    )
                    description += f'\n  [{i + 1}] "{text_preview}"'

            # Truncate if too long
            if len(description) > 800:
                description = description[:800] + "..."

            # Map severity to reliability
            reliability_map = {"high": "high", "medium": "medium", "low": "low"}
            reliability = reliability_map.get(contradiction.severity, "medium")

            # Get first evidence doc_id
            source_doc_id = (
                evidence_records[0].document_id if evidence_records else None
            )

            return self.add_evidence(
                analysis_id=analysis_id,
                description=description,
                evidence_type="fact",  # Contradictions are factual conflicts
                reliability=reliability,
                source=f"Contradiction detected for entity: {entity_name}",
                source_document_id=source_doc_id,
            )

        except Exception as e:
            logger.error(f"Error importing contradiction {contradiction_id}: {e}")
            return None
        finally:
            session.close()

    def import_timeline_event(
        self,
        analysis_id: int,
        event_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Import a timeline event as evidence.

        Args:
            analysis_id: ACH analysis ID
            event_id: TimelineEvent record ID

        Returns:
            Created evidence dict or None if failed
        """
        session = self.Session()

        try:
            from app.arkham.services.db.models import TimelineEvent, Document

            event = session.query(TimelineEvent).filter_by(id=event_id).first()

            if not event:
                logger.warning(f"Timeline event {event_id} not found")
                return None

            # Format date
            date_str = (
                event.event_date.strftime("%Y-%m-%d")
                if event.event_date
                else "Unknown date"
            )

            # Build description
            description = f"[{date_str}] {event.description}"
            if event.event_type:
                description = f"[{event.event_type.upper()}] {description}"

            # Get document title
            doc = session.query(Document).filter_by(id=event.doc_id).first()
            doc_title = doc.title if doc else f"Document #{event.doc_id}"

            # Map confidence to reliability
            if event.confidence and event.confidence >= 0.8:
                reliability = "high"
            elif event.confidence and event.confidence >= 0.5:
                reliability = "medium"
            else:
                reliability = "low"

            return self.add_evidence(
                analysis_id=analysis_id,
                description=description,
                evidence_type="fact",  # Timeline events are factual
                reliability=reliability,
                source=f"Timeline event from: {doc_title}",
                source_document_id=event.doc_id,
            )

        except Exception as e:
            logger.error(f"Error importing timeline event {event_id}: {e}")
            return None
        finally:
            session.close()

    def check_evidence_exists(
        self,
        analysis_id: int,
        source_document_id: int,
        description_prefix: str = None,
    ) -> bool:
        """
        Check if evidence from a source already exists (for deduplication).

        Args:
            analysis_id: ACH analysis ID
            source_document_id: Document ID to check
            description_prefix: Optional prefix to also match description

        Returns:
            True if similar evidence exists
        """
        session = self.Session()
        try:
            query = session.query(ACHEvidence).filter_by(
                analysis_id=analysis_id,
                source_document_id=source_document_id,
            )

            # If prefix provided, also check description starts with it
            if description_prefix:
                query = query.filter(
                    ACHEvidence.description.startswith(description_prefix)
                )

            return query.first() is not None
        finally:
            session.close()

    def _milestone_to_dict(self, m: ACHMilestone) -> Dict[str, Any]:
        """Convert ACHMilestone ORM object to dictionary."""
        return {
            "id": m.id,
            "analysis_id": m.analysis_id,
            "hypothesis_id": m.hypothesis_id,
            "description": m.description,
            "expected_by": m.expected_by.isoformat() if m.expected_by else None,
            "observed": m.observed,
            "observed_date": m.observed_date.isoformat() if m.observed_date else None,
            "observation_notes": m.observation_notes,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }

    # =========================================================================
    # HISTORY & VERSIONING (Phase 5)
    # =========================================================================

    def _build_snapshot_data(self, analysis_id: int) -> Dict[str, Any]:
        """
        Build snapshot data dict without persisting.
        Reusable helper for both create_snapshot and compare_to_current.
        """
        analysis = self.get_analysis(analysis_id)
        if not analysis:
            raise ValueError("Analysis not found")

        # Ensure scores are fresh
        scores = self.calculate_scores(analysis_id)
        analysis["scores"] = scores

        # Ensure milestones are included
        milestones = self.get_analysis_milestones(analysis_id)
        analysis["milestones"] = milestones

        return analysis

    def create_snapshot(
        self, analysis_id: int, label: str, description: str = None
    ) -> ACHAnalysisSnapshot:
        """Create a version snapshot of the complete analysis state."""
        # Build the snapshot data
        analysis = self._build_snapshot_data(analysis_id)

        # Store snapshot
        session = self.Session()
        try:
            snapshot = ACHAnalysisSnapshot(
                analysis_id=analysis_id,
                label=label,
                description=description,
                data=json.dumps(analysis, default=str),
            )
            session.add(snapshot)
            session.commit()

            # Detach for return
            session.refresh(snapshot)
            session.expunge(snapshot)
            return snapshot
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating snapshot: {e}")
            return None
        finally:
            session.close()

    def get_snapshots(self, analysis_id: int) -> List[Dict[str, Any]]:
        """Get list of snapshots for an analysis."""
        session = self.Session()
        try:
            snapshots = (
                session.query(ACHAnalysisSnapshot)
                .filter_by(analysis_id=analysis_id)
                .order_by(ACHAnalysisSnapshot.created_at.desc())
                .all()
            )

            return [
                {
                    "id": s.id,
                    "label": s.label,
                    "description": s.description,
                    "created_at": s.created_at.isoformat(),
                    "snapshot_at": s.snapshot_at.isoformat(),
                }
                for s in snapshots
            ]
        finally:
            session.close()

    def get_snapshot_diff(
        self, snapshot_id_1: int, snapshot_id_2: int
    ) -> Dict[str, Any]:
        """Compare two snapshots and return differences."""
        session = self.Session()
        try:
            s1 = session.get(ACHAnalysisSnapshot, snapshot_id_1)
            s2 = session.get(ACHAnalysisSnapshot, snapshot_id_2)

            if not s1 or not s2:
                return {"error": "Snapshot not found"}

            data1 = json.loads(s1.data)
            data2 = json.loads(s2.data)

            # Use enhanced diff for full comparison
            diff = self._enhanced_diff(data1, data2)
            diff["meta"] = {
                "s1_label": s1.label,
                "s2_label": s2.label,
                "s1_date": s1.created_at.isoformat(),
                "s2_date": s2.created_at.isoformat(),
            }
            return diff
        finally:
            session.close()

    def _diff_list(
        self, list1: List[dict], list2: List[dict], key: str
    ) -> Dict[str, List[str]]:
        """Helper to diff two lists of dictionaries by a key."""
        keys1 = {item[key] for item in list1}
        keys2 = {item[key] for item in list2}

        added = list(keys2 - keys1)
        removed = list(keys1 - keys2)
        common = keys1.intersection(keys2)

        modified = []
        for k in common:
            item1 = next(i for i in list1 if i[key] == k)
            item2 = next(i for i in list2 if i[key] == k)

            # Simple content check (description/text)
            desc1 = item1.get("description", "")
            desc2 = item2.get("description", "")
            if desc1 != desc2:
                modified.append(
                    {"key": k, "type": "description", "old": desc1, "new": desc2}
                )

        return {"added": added, "removed": removed, "modified": modified}

    def _diff_scores(self, scores1: List[dict], scores2: List[dict]) -> Dict[str, Any]:
        """Diff scoring ranking."""
        if not scores1 or not scores2:
            return {}

        winner1 = scores1[0]["label"] if scores1 else None
        winner2 = scores2[0]["label"] if scores2 else None

        changes = []
        for s2 in scores2:
            label = s2["label"]
            s1 = next((s for s in scores1 if s["label"] == label), None)
            if s1:
                diff = s2["inconsistency_score"] - s1["inconsistency_score"]
                if diff != 0:
                    changes.append(
                        {
                            "label": label,
                            "old": s1["inconsistency_score"],
                            "new": s2["inconsistency_score"],
                            "delta": diff,
                        }
                    )

        return {
            "winner_changed": winner1 != winner2,
            "old_winner": winner1,
            "new_winner": winner2,
            "score_changes": changes,
        }

    def _diff_ratings(
        self,
        evidence1: List[dict],
        evidence2: List[dict],
        hypotheses1: List[dict],
        hypotheses2: List[dict],
    ) -> List[Dict[str, Any]]:
        """
        Compare ratings between two states.
        Returns list of rating changes with hypothesis labels resolved.
        """
        changes = []

        # Build hypothesis ID -> label maps for both states
        hyp1_labels = {h["id"]: h["label"] for h in hypotheses1}
        hyp2_labels = {h["id"]: h["label"] for h in hypotheses2}
        # Merged map for label lookup (prefer newer labels)
        hyp_labels = {**hyp1_labels, **hyp2_labels}

        # Build lookup for evidence by label
        ev1_map = {e["label"]: e for e in evidence1}
        ev2_map = {e["label"]: e for e in evidence2}

        # Check common evidence items for rating changes
        common_labels = set(ev1_map.keys()) & set(ev2_map.keys())

        for label in common_labels:
            ratings1 = ev1_map[label].get("ratings", {})
            ratings2 = ev2_map[label].get("ratings", {})

            # Convert string keys to int for comparison (JSON keys are strings)
            # Handle potential non-numeric keys gracefully
            try:
                ratings1_int = {int(k): v for k, v in ratings1.items()}
            except (ValueError, TypeError):
                ratings1_int = {}
            try:
                ratings2_int = {int(k): v for k, v in ratings2.items()}
            except (ValueError, TypeError):
                ratings2_int = {}

            # Compare ratings for each hypothesis
            all_hyp_ids = set(ratings1_int.keys()) | set(ratings2_int.keys())
            for hyp_id in all_hyp_ids:
                old_rating = ratings1_int.get(hyp_id, "")
                new_rating = ratings2_int.get(hyp_id, "")
                if old_rating != new_rating:
                    hyp_label = hyp_labels.get(hyp_id, f"H{hyp_id}")
                    changes.append({
                        "evidence_label": label,
                        "hypothesis_label": hyp_label,
                        "old": old_rating or "(empty)",
                        "new": new_rating or "(empty)",
                    })

        return changes

    def _diff_milestones(
        self,
        milestones1: List[dict],
        milestones2: List[dict],
    ) -> Dict[str, Any]:
        """
        Compare milestones between two states.
        """
        # By description (since milestones don't have unique labels)
        desc1 = {m["description"]: m for m in milestones1}
        desc2 = {m["description"]: m for m in milestones2}

        added = [m["description"] for m in milestones2 if m["description"] not in desc1]
        removed = [m["description"] for m in milestones1 if m["description"] not in desc2]

        # Status changes for common milestones
        status_changes = []
        status_map = {0: "Pending", 1: "Observed", -1: "Contradicted"}

        for desc in set(desc1.keys()) & set(desc2.keys()):
            m1, m2 = desc1[desc], desc2[desc]
            old_observed = m1.get("observed", 0)
            new_observed = m2.get("observed", 0)
            if old_observed != new_observed:
                # Truncate long descriptions for display
                display_desc = desc[:50] + "..." if len(desc) > 50 else desc
                status_changes.append({
                    "description": display_desc,
                    "old_status": status_map.get(old_observed, "?"),
                    "new_status": status_map.get(new_observed, "?"),
                })

        return {
            "added": added,
            "removed": removed,
            "status_changes": status_changes,
        }

    def _enhanced_diff(
        self,
        data1: Dict[str, Any],
        data2: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Enhanced diff with ratings and milestones.
        data1 = old state, data2 = new state
        """
        hypotheses1 = data1.get("hypotheses", [])
        hypotheses2 = data2.get("hypotheses", [])
        evidence1 = data1.get("evidence", [])
        evidence2 = data2.get("evidence", [])

        return {
            "hypotheses": self._diff_list(
                hypotheses1,
                hypotheses2,
                key="label",
            ),
            "evidence": self._diff_list(
                evidence1,
                evidence2,
                key="label",
            ),
            "ratings": self._diff_ratings(
                evidence1,
                evidence2,
                hypotheses1,
                hypotheses2,
            ),
            "milestones": self._diff_milestones(
                data1.get("milestones", []),
                data2.get("milestones", []),
            ),
            "scores": self._diff_scores(
                data1.get("scores", []),
                data2.get("scores", []),
            ),
        }

    def compare_to_current(
        self, analysis_id: int, snapshot_id: int
    ) -> Dict[str, Any]:
        """
        Compare a saved snapshot to the current analysis state.
        Creates a temporary snapshot of current state for comparison.
        """
        from datetime import datetime

        # Build current state data (not persisted)
        try:
            current_data = self._build_snapshot_data(analysis_id)
        except ValueError as e:
            return {"error": f"Analysis not found: {e}"}

        # Load the saved snapshot
        session = self.Session()
        try:
            saved_snapshot = session.get(ACHAnalysisSnapshot, snapshot_id)
            if not saved_snapshot:
                return {"error": "Snapshot not found"}

            saved_data = json.loads(saved_snapshot.data)

            # Run enhanced diff (saved = old, current = new)
            diff = self._enhanced_diff(saved_data, current_data)
            diff["meta"] = {
                "s1_label": saved_snapshot.label,
                "s2_label": "Current State",
                "s1_date": saved_snapshot.created_at.isoformat(),
                "s2_date": datetime.utcnow().isoformat(),
            }
            return diff
        finally:
            session.close()


# =============================================================================
# SINGLETON PATTERN
# =============================================================================

_ach_service_instance = None


def get_ach_service() -> ACHService:
    """Get or create singleton ACH service instance."""
    global _ach_service_instance
    if _ach_service_instance is None:
        _ach_service_instance = ACHService()
    return _ach_service_instance
