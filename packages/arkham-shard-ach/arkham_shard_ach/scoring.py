"""ACH scoring algorithms."""

import logging
from datetime import datetime

from .models import ACHMatrix, HypothesisScore, ConsistencyRating

logger = logging.getLogger(__name__)


class ACHScorer:
    """
    Calculate scores for hypotheses in an ACH matrix.

    The ACH method focuses on disconfirming evidence rather than confirming.
    The hypothesis with the LEAST inconsistent evidence is often the best.
    """

    @staticmethod
    def calculate_scores(matrix: ACHMatrix) -> list[HypothesisScore]:
        """
        Calculate scores for all hypotheses in a matrix.

        Scoring approach:
        1. Count inconsistencies (- and --) for each hypothesis
        2. Calculate weighted consistency score
        3. Rank hypotheses (lower inconsistency count = better)

        Args:
            matrix: The ACH matrix to score

        Returns:
            List of HypothesisScore objects, sorted by rank
        """
        if not matrix.hypotheses:
            return []

        scores = []

        for hypothesis in matrix.hypotheses:
            score = ACHScorer._score_hypothesis(matrix, hypothesis.id)
            scores.append(score)

        # Sort by inconsistency count (primary) and weighted score (secondary)
        # Lower inconsistency = better rank
        scores.sort(key=lambda s: (s.inconsistency_count, -s.weighted_score))

        # Assign ranks
        for rank, score in enumerate(scores, start=1):
            score.rank = rank

        # Mark leading hypothesis
        if scores:
            leading_id = scores[0].hypothesis_id
            for h in matrix.hypotheses:
                h.is_lead = h.id == leading_id

        # Update matrix scores
        matrix.scores = scores

        return scores

    @staticmethod
    def _score_hypothesis(matrix: ACHMatrix, hypothesis_id: str) -> HypothesisScore:
        """Calculate score for a single hypothesis."""
        hypothesis = matrix.get_hypothesis(hypothesis_id)
        if not hypothesis:
            return HypothesisScore(hypothesis_id=hypothesis_id)

        # Get all ratings for this hypothesis
        hypothesis_ratings = [
            r for r in matrix.ratings if r.hypothesis_id == hypothesis_id
        ]

        if not hypothesis_ratings:
            return HypothesisScore(
                hypothesis_id=hypothesis_id,
                evidence_count=0,
            )

        # Calculate basic scores
        consistency_sum = 0.0
        inconsistency_count = 0
        weighted_sum = 0.0
        total_weight = 0.0

        for rating in hypothesis_ratings:
            # Skip N/A ratings
            if rating.rating == ConsistencyRating.NOT_APPLICABLE:
                continue

            # Get evidence for weighting
            evidence = matrix.get_evidence(rating.evidence_id)
            if not evidence:
                continue

            # Basic consistency score
            consistency_sum += rating.rating.score

            # Count inconsistencies (- and --)
            if rating.rating in (
                ConsistencyRating.INCONSISTENT,
                ConsistencyRating.HIGHLY_INCONSISTENT,
            ):
                inconsistency_count += 1

            # Weighted score (by evidence credibility and relevance)
            evidence_weight = evidence.credibility * evidence.relevance
            weighted_sum += rating.rating.score * evidence_weight * rating.confidence
            total_weight += evidence_weight

        # Calculate normalized weighted score (0-100 scale)
        if total_weight > 0:
            weighted_score = weighted_sum / total_weight
            # Normalize to 0-100 (raw scores are -2 to +2)
            normalized = ((weighted_score + 2.0) / 4.0) * 100.0
        else:
            weighted_score = 0.0
            normalized = 50.0

        return HypothesisScore(
            hypothesis_id=hypothesis_id,
            consistency_score=consistency_sum,
            inconsistency_count=inconsistency_count,
            weighted_score=weighted_score,
            normalized_score=normalized,
            evidence_count=len(hypothesis_ratings),
            calculation_timestamp=datetime.utcnow(),
        )

    @staticmethod
    def get_diagnosticity_report(matrix: ACHMatrix) -> dict:
        """
        Generate a diagnosticity report.

        Identifies which evidence is most diagnostic (differentiates hypotheses).

        Returns:
            Report with diagnostic evidence items
        """
        if not matrix.evidence or not matrix.hypotheses:
            return {"diagnostic_evidence": []}

        diagnostic_items = []

        for evidence in matrix.evidence:
            # Get all ratings for this evidence
            evidence_ratings = [
                r for r in matrix.ratings if r.evidence_id == evidence.id
            ]

            if len(evidence_ratings) < 2:
                continue

            # Calculate variance in ratings across hypotheses
            rating_values = [r.rating.score for r in evidence_ratings]
            if not rating_values:
                continue

            mean = sum(rating_values) / len(rating_values)
            variance = sum((x - mean) ** 2 for x in rating_values) / len(rating_values)

            # High variance = diagnostic (differentiates hypotheses)
            if variance > 0.5:
                diagnostic_items.append(
                    {
                        "evidence_id": evidence.id,
                        "description": evidence.description,
                        "variance": variance,
                        "mean_consistency": mean,
                        "rating_count": len(evidence_ratings),
                    }
                )

        # Sort by variance (most diagnostic first)
        diagnostic_items.sort(key=lambda x: x["variance"], reverse=True)

        return {
            "diagnostic_evidence": diagnostic_items,
            "total_evidence": len(matrix.evidence),
            "diagnostic_count": len(diagnostic_items),
        }

    @staticmethod
    def get_sensitivity_analysis(matrix: ACHMatrix) -> dict:
        """
        Perform sensitivity analysis.

        Shows how scores would change if uncertain evidence were removed.

        Returns:
            Sensitivity analysis report
        """
        if not matrix.scores:
            ACHScorer.calculate_scores(matrix)

        original_scores = {s.hypothesis_id: s.rank for s in matrix.scores}

        # Identify low-credibility evidence
        uncertain_evidence = [
            e for e in matrix.evidence if e.credibility < 0.7 or e.relevance < 0.7
        ]

        if not uncertain_evidence:
            return {
                "sensitivity": "low",
                "uncertain_evidence_count": 0,
                "rank_changes": [],
            }

        # Temporarily remove low-credibility ratings
        original_ratings = matrix.ratings.copy()
        uncertain_ids = {e.id for e in uncertain_evidence}

        matrix.ratings = [
            r for r in matrix.ratings if r.evidence_id not in uncertain_ids
        ]

        # Recalculate scores
        new_scores = ACHScorer.calculate_scores(matrix)
        new_ranks = {s.hypothesis_id: s.rank for s in new_scores}

        # Restore original ratings
        matrix.ratings = original_ratings
        ACHScorer.calculate_scores(matrix)

        # Find rank changes
        rank_changes = []
        for hyp_id in original_scores:
            old_rank = original_scores[hyp_id]
            new_rank = new_ranks.get(hyp_id, old_rank)

            if old_rank != new_rank:
                hypothesis = matrix.get_hypothesis(hyp_id)
                rank_changes.append(
                    {
                        "hypothesis_id": hyp_id,
                        "hypothesis_title": hypothesis.title if hypothesis else "",
                        "original_rank": old_rank,
                        "new_rank": new_rank,
                        "change": new_rank - old_rank,
                    }
                )

        # Determine sensitivity level
        max_change = max((abs(rc["change"]) for rc in rank_changes), default=0)
        if max_change == 0:
            sensitivity = "low"
        elif max_change == 1:
            sensitivity = "moderate"
        else:
            sensitivity = "high"

        return {
            "sensitivity": sensitivity,
            "uncertain_evidence_count": len(uncertain_evidence),
            "rank_changes": rank_changes,
            "max_rank_change": max_change,
        }
