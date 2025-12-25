"""Evidence management for ACH matrices."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EvidenceAnalyzer:
    """
    Analyze and manage evidence in ACH matrices.

    Provides utilities for evidence quality assessment,
    linking to documents, and identifying gaps.
    """

    @staticmethod
    def assess_quality(
        source: str,
        evidence_type: str,
        credibility: float,
        relevance: float,
    ) -> dict[str, Any]:
        """
        Assess the quality of an evidence item.

        Args:
            source: Source of the evidence
            evidence_type: Type of evidence
            credibility: Credibility score (0-1)
            relevance: Relevance score (0-1)

        Returns:
            Quality assessment report
        """
        issues = []
        warnings = []
        quality_score = 0.0

        # Check credibility
        if credibility < 0.3:
            issues.append("Very low credibility - consider verifying source")
        elif credibility < 0.5:
            warnings.append("Low credibility - use caution in analysis")
        elif credibility >= 0.8:
            quality_score += 0.4

        # Check relevance
        if relevance < 0.3:
            issues.append("Low relevance to hypotheses")
        elif relevance < 0.5:
            warnings.append("Moderate relevance - may be tangential")
        elif relevance >= 0.8:
            quality_score += 0.4

        # Check source
        if not source or source.strip() == "":
            warnings.append("No source provided - consider documenting")
        else:
            quality_score += 0.2

        # Overall quality
        base_quality = (credibility + relevance) / 2.0
        final_quality = (base_quality + quality_score) / 2.0

        if final_quality >= 0.8:
            quality_level = "high"
        elif final_quality >= 0.5:
            quality_level = "medium"
        else:
            quality_level = "low"

        return {
            "quality_score": final_quality,
            "quality_level": quality_level,
            "credibility": credibility,
            "relevance": relevance,
            "issues": issues,
            "warnings": warnings,
        }

    @staticmethod
    def identify_gaps(matrix) -> dict[str, Any]:
        """
        Identify gaps in evidence coverage.

        Looks for:
        - Hypotheses with little evidence
        - Evidence areas that need more coverage
        - Missing critical evidence types

        Args:
            matrix: ACHMatrix instance

        Returns:
            Gap analysis report
        """
        from .models import EvidenceType

        gaps = []

        # Check hypothesis coverage
        for hypothesis in matrix.hypotheses:
            ratings = [
                r for r in matrix.ratings if r.hypothesis_id == hypothesis.id
            ]

            # Filter out N/A ratings
            from .models import ConsistencyRating

            substantive_ratings = [
                r for r in ratings if r.rating != ConsistencyRating.NOT_APPLICABLE
            ]

            if len(substantive_ratings) < 3:
                gaps.append(
                    {
                        "type": "hypothesis_coverage",
                        "hypothesis_id": hypothesis.id,
                        "hypothesis_title": hypothesis.title,
                        "rating_count": len(substantive_ratings),
                        "severity": "high" if len(substantive_ratings) == 0 else "medium",
                        "recommendation": f"Add more evidence relevant to '{hypothesis.title}'",
                    }
                )

        # Check evidence type diversity
        evidence_types = set(e.evidence_type for e in matrix.evidence)
        missing_types = set(EvidenceType) - evidence_types

        if missing_types:
            gaps.append(
                {
                    "type": "evidence_diversity",
                    "missing_types": [t.value for t in missing_types],
                    "severity": "low",
                    "recommendation": "Consider adding diverse evidence types for robust analysis",
                }
            )

        # Check for evidence with no ratings
        for evidence in matrix.evidence:
            ratings = [r for r in matrix.ratings if r.evidence_id == evidence.id]

            if len(ratings) == 0:
                gaps.append(
                    {
                        "type": "unrated_evidence",
                        "evidence_id": evidence.id,
                        "description": evidence.description,
                        "severity": "medium",
                        "recommendation": "Rate this evidence against all hypotheses",
                    }
                )

        # Check for low-quality evidence concentration
        low_quality_count = sum(
            1 for e in matrix.evidence if e.credibility < 0.5 or e.relevance < 0.5
        )

        if low_quality_count > len(matrix.evidence) * 0.3:
            gaps.append(
                {
                    "type": "quality_concern",
                    "low_quality_count": low_quality_count,
                    "total_evidence": len(matrix.evidence),
                    "severity": "high",
                    "recommendation": "High proportion of low-quality evidence - verify sources and relevance",
                }
            )

        return {
            "gaps": gaps,
            "gap_count": len(gaps),
            "severity_breakdown": {
                "high": len([g for g in gaps if g.get("severity") == "high"]),
                "medium": len([g for g in gaps if g.get("severity") == "medium"]),
                "low": len([g for g in gaps if g.get("severity") == "low"]),
            },
        }

    @staticmethod
    def suggest_evidence(
        matrix,
        hypothesis_id: str,
        max_suggestions: int = 5,
    ) -> list[str]:
        """
        Suggest additional evidence to seek for a hypothesis.

        This is a simple rule-based system. In production, this could
        use LLM to generate smarter suggestions.

        Args:
            matrix: ACHMatrix instance
            hypothesis_id: Hypothesis to suggest evidence for
            max_suggestions: Maximum number of suggestions

        Returns:
            List of evidence suggestions
        """
        hypothesis = matrix.get_hypothesis(hypothesis_id)
        if not hypothesis:
            return []

        suggestions = []

        # Generic evidence types to consider
        from .models import EvidenceType

        evidence_types = set(e.evidence_type for e in matrix.evidence)

        # Suggest different evidence types
        type_suggestions = {
            EvidenceType.DOCUMENT: f"Look for documents that support or refute '{hypothesis.title}'",
            EvidenceType.TESTIMONY: f"Seek witness testimony regarding '{hypothesis.title}'",
            EvidenceType.PHYSICAL: f"Examine physical evidence related to '{hypothesis.title}'",
            EvidenceType.CIRCUMSTANTIAL: f"Consider circumstantial evidence surrounding '{hypothesis.title}'",
        }

        for ev_type, suggestion in type_suggestions.items():
            if ev_type not in evidence_types:
                suggestions.append(suggestion)

        # Check if hypothesis has conflicting evidence
        ratings = [r for r in matrix.ratings if r.hypothesis_id == hypothesis_id]
        has_positive = any(
            r.rating.value in ("++", "+") for r in ratings
        )
        has_negative = any(
            r.rating.value in ("--", "-") for r in ratings
        )

        if has_positive and has_negative:
            suggestions.append(
                f"Conflicting evidence exists - seek additional evidence to clarify '{hypothesis.title}'"
            )

        # If hypothesis has very little evidence
        if len(ratings) < 3:
            suggestions.append(
                f"Limited evidence for '{hypothesis.title}' - conduct broader information gathering"
            )

        return suggestions[:max_suggestions]

    @staticmethod
    def compare_evidence(
        evidence1_id: str,
        evidence2_id: str,
        matrix,
    ) -> dict[str, Any] | None:
        """
        Compare two evidence items.

        Args:
            evidence1_id: First evidence ID
            evidence2_id: Second evidence ID
            matrix: ACHMatrix instance

        Returns:
            Comparison report or None if evidence not found
        """
        ev1 = matrix.get_evidence(evidence1_id)
        ev2 = matrix.get_evidence(evidence2_id)

        if not ev1 or not ev2:
            return None

        # Get ratings for both
        ratings1 = {
            r.hypothesis_id: r.rating.value
            for r in matrix.ratings
            if r.evidence_id == evidence1_id
        }
        ratings2 = {
            r.hypothesis_id: r.rating.value
            for r in matrix.ratings
            if r.evidence_id == evidence2_id
        }

        # Find agreements and disagreements
        agreements = []
        disagreements = []

        for hyp_id in ratings1:
            if hyp_id in ratings2:
                hypothesis = matrix.get_hypothesis(hyp_id)
                hyp_title = hypothesis.title if hypothesis else hyp_id

                if ratings1[hyp_id] == ratings2[hyp_id]:
                    agreements.append(
                        {
                            "hypothesis_id": hyp_id,
                            "hypothesis_title": hyp_title,
                            "rating": ratings1[hyp_id],
                        }
                    )
                else:
                    disagreements.append(
                        {
                            "hypothesis_id": hyp_id,
                            "hypothesis_title": hyp_title,
                            "evidence1_rating": ratings1[hyp_id],
                            "evidence2_rating": ratings2[hyp_id],
                        }
                    )

        return {
            "evidence1": {
                "id": ev1.id,
                "description": ev1.description,
                "type": ev1.evidence_type.value,
                "credibility": ev1.credibility,
            },
            "evidence2": {
                "id": ev2.id,
                "description": ev2.description,
                "type": ev2.evidence_type.value,
                "credibility": ev2.credibility,
            },
            "agreements": agreements,
            "disagreements": disagreements,
            "agreement_count": len(agreements),
            "disagreement_count": len(disagreements),
        }
