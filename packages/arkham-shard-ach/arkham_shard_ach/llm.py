"""LLM integration for ACH analysis.

Provides AI-assisted features:
- Hypothesis generation from focus question
- Evidence suggestion based on hypotheses
- Rating suggestions for evidence-hypothesis pairs
- Devil's advocate challenges
- Analysis insights and conclusions
- Milestone/indicator suggestions
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .models import (
    ACHMatrix,
    ConsistencyRating,
    DevilsAdvocateChallenge,
    Evidence,
    EvidenceType,
    Hypothesis,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Response Models
# =============================================================================


@dataclass
class HypothesisSuggestion:
    """A suggested hypothesis from LLM."""
    title: str
    description: str = ""


@dataclass
class EvidenceSuggestion:
    """A suggested evidence item from LLM."""
    description: str
    evidence_type: EvidenceType = EvidenceType.FACT
    source: str = ""


@dataclass
class RatingSuggestion:
    """A suggested rating for evidence-hypothesis pair."""
    hypothesis_id: str
    hypothesis_label: str
    rating: ConsistencyRating
    explanation: str = ""


@dataclass
class Challenge:
    """A devil's advocate challenge for a hypothesis."""
    hypothesis_id: str
    hypothesis_label: str
    counter_argument: str
    disproof_evidence: str
    alternative_angle: str


@dataclass
class MilestoneSuggestion:
    """A suggested future indicator/milestone."""
    hypothesis_id: str
    hypothesis_label: str
    description: str


@dataclass
class AnalysisInsights:
    """LLM-generated analysis insights."""
    leading_hypothesis: str
    key_evidence: list[str]
    evidence_gaps: list[str]
    cognitive_biases: list[str]
    recommendations: list[str]
    full_text: str


# =============================================================================
# System Prompts
# =============================================================================

SYSTEM_PROMPTS = {
    "hypotheses": """You are an intelligence analyst helping with Analysis of Competing Hypotheses (ACH).
Your role is to generate plausible, mutually exclusive hypotheses that could explain the situation.

Guidelines:
- Generate 3-5 distinct hypotheses
- Each hypothesis should be testable with evidence
- Hypotheses should be mutually exclusive where possible
- Keep titles concise (1-2 sentences)
- Provide brief descriptions when helpful
- Consider both obvious and non-obvious explanations
- Avoid confirmation bias - include unlikely but possible alternatives""",

    "evidence": """You are an intelligence analyst helping with Analysis of Competing Hypotheses (ACH).
Your role is to suggest specific, concrete evidence items that could help distinguish between hypotheses.

Guidelines:
- Generate 3-5 specific evidence items (facts, documents, statements, physical items)
- Each item should be a concrete piece of evidence, NOT an investigation method
- Focus on evidence that would be INCONSISTENT with some hypotheses
- Write each as a factual statement about what the evidence shows
- Example format: "Witness testimony from John Smith stating he saw X on Y date (testimony)"
- NOT: "Interview witnesses to determine..." - that's an investigation method, not evidence
- Be specific and concrete - name sources, dates, locations when relevant""",

    "ratings": """You are an intelligence analyst helping with Analysis of Competing Hypotheses (ACH).
Your role is to rate how consistent evidence is with each hypothesis.

Rating Scale:
- ++ (Highly Consistent): Strong support for the hypothesis
- + (Consistent): Moderate support for the hypothesis
- N (Neutral): Neither supports nor contradicts
- - (Inconsistent): Moderate contradiction with hypothesis
- -- (Highly Inconsistent): Strong contradiction with hypothesis

Guidelines:
- Focus on DISCONFIRMING evidence (ACH best practice)
- Consider the reliability and credibility of the evidence
- Provide brief reasoning for each rating
- Be objective - don't favor any hypothesis""",

    "devils_advocate": """You are a devil's advocate analyst. Your job is to challenge hypotheses and find weaknesses.

For each hypothesis, you must provide:
1. Counter-argument: The strongest argument AGAINST this hypothesis
2. Disproof evidence: What evidence would definitively disprove it
3. Alternative angle: A consideration that may have been missed

Guidelines:
- Be critical but fair
- Focus on logical weaknesses
- Identify hidden assumptions
- Consider alternative interpretations of evidence
- Highlight confirmation bias risks""",

    "insights": """You are an intelligence analyst providing insights on an ACH matrix analysis.

Provide analysis covering:
1. Which hypothesis has the strongest support and why
2. Key distinguishing evidence (what matters most)
3. Evidence gaps that should be filled
4. Potential cognitive biases to watch for
5. Recommended next steps for investigation

Be objective, thorough, and actionable.""",

    "milestones": """You are an intelligence analyst helping identify future indicators and milestones.

For each relevant hypothesis, suggest 2-3 observable events or indicators that would:
- Confirm the hypothesis if they occur
- Refute the hypothesis if they don't occur

Guidelines:
- Be specific and observable
- Include timeframes where relevant
- Focus on testable predictions
- Consider leading indicators""",
}


# =============================================================================
# LLM Integration Class
# =============================================================================


class ACHLLMIntegration:
    """
    LLM integration for ACH analysis features.

    Works with Frame's LLM service to provide AI-assisted analysis.
    """

    def __init__(self, llm_service=None):
        """
        Initialize LLM integration.

        Args:
            llm_service: Frame's LLM service instance
        """
        self.llm_service = llm_service

    @property
    def is_available(self) -> bool:
        """Check if LLM service is available."""
        return self.llm_service is not None

    async def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """
        Generate LLM response.

        Args:
            system_prompt: System prompt defining behavior
            user_prompt: User's request
            temperature: Sampling temperature
            max_tokens: Maximum response tokens

        Returns:
            Response dict with 'text' and 'model' keys
        """
        if not self.llm_service:
            raise RuntimeError("LLM service not available")

        try:
            response = await self.llm_service.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    # =========================================================================
    # Hypothesis Generation
    # =========================================================================

    async def suggest_hypotheses(
        self,
        focus_question: str,
        existing_hypotheses: list[Hypothesis] | None = None,
        context: str = "",
    ) -> list[HypothesisSuggestion]:
        """
        Generate hypothesis suggestions based on focus question.

        Args:
            focus_question: The question or situation to analyze
            existing_hypotheses: Current hypotheses (to avoid duplication)
            context: Additional context about the situation

        Returns:
            List of HypothesisSuggestion objects
        """
        # Build user prompt
        prompt_parts = [
            f"Focus Question: {focus_question}",
        ]

        if context:
            prompt_parts.append(f"\nContext: {context}")

        if existing_hypotheses:
            existing = "\n".join(
                f"- H{i+1}: {h.title}"
                for i, h in enumerate(existing_hypotheses)
            )
            prompt_parts.append(f"\nExisting Hypotheses (avoid duplicating):\n{existing}")

        prompt_parts.append(
            "\nGenerate 3-5 additional hypotheses. "
            "Format: Number each hypothesis, one per line."
        )

        user_prompt = "\n".join(prompt_parts)

        response = await self._generate(
            system_prompt=SYSTEM_PROMPTS["hypotheses"],
            user_prompt=user_prompt,
        )

        return self._parse_hypotheses(response.get("text", ""))

    def _parse_hypotheses(self, text: str) -> list[HypothesisSuggestion]:
        """Parse numbered hypotheses from LLM response."""
        suggestions = []

        # Match numbered items: "1. hypothesis text" or "1) hypothesis text"
        pattern = r'^\s*\d+[\.\)]\s*(.+)$'

        for line in text.strip().split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                title = match.group(1).strip()
                if title:
                    suggestions.append(HypothesisSuggestion(title=title))

        return suggestions

    # =========================================================================
    # Evidence Suggestion
    # =========================================================================

    async def suggest_evidence(
        self,
        focus_question: str,
        hypotheses: list[Hypothesis],
        existing_evidence: list[Evidence] | None = None,
    ) -> list[EvidenceSuggestion]:
        """
        Suggest diagnostic evidence items.

        Args:
            focus_question: The focus question
            hypotheses: Current hypotheses
            existing_evidence: Existing evidence (to avoid duplication)

        Returns:
            List of EvidenceSuggestion objects
        """
        if not hypotheses:
            return []

        # Build hypotheses list
        hyp_list = "\n".join(
            f"- H{i+1}: {h.title}"
            for i, h in enumerate(hypotheses)
        )

        prompt_parts = [
            f"Focus Question: {focus_question}",
            f"\nHypotheses:\n{hyp_list}",
        ]

        if existing_evidence:
            existing = "\n".join(
                f"- {e.description}"
                for e in existing_evidence[:10]  # Limit for context
            )
            prompt_parts.append(f"\nExisting Evidence (avoid duplicating):\n{existing}")

        prompt_parts.append(
            "\nSuggest 3-5 diagnostic evidence items that would help distinguish "
            "between hypotheses. Format each as:\n"
            "1. Evidence description (TYPE)\n"
            "Where TYPE is one of: fact, testimony, document, physical, circumstantial, inference"
        )

        user_prompt = "\n".join(prompt_parts)

        response = await self._generate(
            system_prompt=SYSTEM_PROMPTS["evidence"],
            user_prompt=user_prompt,
        )

        return self._parse_evidence(response.get("text", ""))

    def _parse_evidence(self, text: str) -> list[EvidenceSuggestion]:
        """Parse evidence suggestions from LLM response."""
        suggestions = []

        # Split into numbered sections (handles multi-line evidence items)
        # Match patterns like "1. Evidence description (type)" or "1) Evidence..."
        sections = re.split(r'\n(?=\s*\d+[\.\)])', text.strip())

        for section in sections:
            if not section.strip():
                continue

            # Extract the type from the header line
            header_match = re.match(
                r'^\s*\d+[\.\)]\s*(?:Evidence\s+description\s*)?\((\w+)\)',
                section.strip(),
                re.IGNORECASE
            )
            type_str = header_match.group(1) if header_match else None

            # Get the full text after the header
            lines = section.strip().split('\n')
            if len(lines) > 1:
                # Multi-line: description is in subsequent lines
                description_lines = []
                for line in lines[1:]:
                    # Clean up em-dashes, bullets, and leading whitespace
                    cleaned = re.sub(r'^[\s\-\u2014\u2013\*\u2022]+', '', line.strip())
                    if cleaned:
                        description_lines.append(cleaned)
                description = ' '.join(description_lines)
            else:
                # Single line: extract description from the line itself
                single_match = re.match(
                    r'^\s*\d+[\.\)]\s*(.+?)(?:\((\w+)\))?\s*$',
                    section.strip()
                )
                if single_match:
                    description = single_match.group(1).strip()
                    if not type_str:
                        type_str = single_match.group(2)
                else:
                    description = ''

            if description and description.lower() != 'evidence description':
                evidence_type = self._parse_evidence_type(type_str)
                suggestions.append(EvidenceSuggestion(
                    description=description,
                    evidence_type=evidence_type,
                ))

        return suggestions

    def _parse_evidence_type(self, type_str: str | None) -> EvidenceType:
        """Parse evidence type from string."""
        if not type_str:
            return EvidenceType.FACT

        type_map = {
            "fact": EvidenceType.FACT,
            "testimony": EvidenceType.TESTIMONY,
            "document": EvidenceType.DOCUMENT,
            "physical": EvidenceType.PHYSICAL,
            "circumstantial": EvidenceType.CIRCUMSTANTIAL,
            "inference": EvidenceType.INFERENCE,
        }

        return type_map.get(type_str.lower(), EvidenceType.FACT)

    # =========================================================================
    # Rating Suggestions
    # =========================================================================

    async def suggest_ratings(
        self,
        evidence: Evidence,
        hypotheses: list[Hypothesis],
    ) -> list[RatingSuggestion]:
        """
        Suggest consistency ratings for evidence against all hypotheses.

        Args:
            evidence: The evidence item to rate
            hypotheses: List of hypotheses to rate against

        Returns:
            List of RatingSuggestion objects
        """
        if not hypotheses:
            return []

        # Build hypotheses list with labels
        hyp_list = "\n".join(
            f"- H{i+1}: {h.title}"
            for i, h in enumerate(hypotheses)
        )

        prompt = f"""Evidence to rate:
Description: {evidence.description}
Type: {evidence.evidence_type.value}
Source: {evidence.source or "Not specified"}
Credibility: {evidence.credibility:.1f}

Hypotheses:
{hyp_list}

Rate how consistent this evidence is with each hypothesis.
Format each rating as:
H1: [RATING] - [Brief explanation]
H2: [RATING] - [Brief explanation]
...

Where RATING is: ++, +, N, -, or --"""

        response = await self._generate(
            system_prompt=SYSTEM_PROMPTS["ratings"],
            user_prompt=prompt,
        )

        return self._parse_ratings(response.get("text", ""), hypotheses)

    def _parse_ratings(
        self,
        text: str,
        hypotheses: list[Hypothesis],
    ) -> list[RatingSuggestion]:
        """Parse rating suggestions from LLM response."""
        suggestions = []

        # Map hypothesis labels to IDs
        hyp_map = {f"H{i+1}": h for i, h in enumerate(hypotheses)}

        # Match patterns like "H1: ++ - explanation" or "H1: -- (explanation)"
        pattern = r'^\s*(H\d+)\s*:\s*(\+\+|\+|N|-|--)\s*[-:]*\s*(.*)$'

        for line in text.strip().split('\n'):
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match:
                label = match.group(1).upper()
                rating_str = match.group(2)
                explanation = match.group(3).strip()

                if label in hyp_map:
                    rating = self._parse_rating(rating_str)
                    suggestions.append(RatingSuggestion(
                        hypothesis_id=hyp_map[label].id,
                        hypothesis_label=label,
                        rating=rating,
                        explanation=explanation,
                    ))

        return suggestions

    def _parse_rating(self, rating_str: str) -> ConsistencyRating:
        """Parse rating string to ConsistencyRating."""
        rating_map = {
            "++": ConsistencyRating.HIGHLY_CONSISTENT,
            "+": ConsistencyRating.CONSISTENT,
            "n": ConsistencyRating.NEUTRAL,
            "-": ConsistencyRating.INCONSISTENT,
            "--": ConsistencyRating.HIGHLY_INCONSISTENT,
        }
        return rating_map.get(rating_str.lower(), ConsistencyRating.NEUTRAL)

    # =========================================================================
    # Devil's Advocate
    # =========================================================================

    async def challenge_hypotheses(
        self,
        matrix: ACHMatrix,
        hypothesis_id: str | None = None,
    ) -> list[Challenge]:
        """
        Generate devil's advocate challenges for hypotheses.

        Args:
            matrix: The ACH matrix
            hypothesis_id: Specific hypothesis to challenge, or None for all

        Returns:
            List of Challenge objects
        """
        if hypothesis_id:
            hypothesis = matrix.get_hypothesis(hypothesis_id)
            if not hypothesis:
                return []
            hypotheses = [hypothesis]
        else:
            hypotheses = matrix.hypotheses

        if not hypotheses:
            return []

        # Build context
        context_parts = [
            f"Matrix: {matrix.title}",
            f"Description: {matrix.description or 'N/A'}",
            "\nHypotheses to challenge:",
        ]

        for i, h in enumerate(hypotheses):
            label = f"H{matrix.hypotheses.index(h) + 1}"
            context_parts.append(f"\n{label}: {h.title}")
            if h.description:
                context_parts.append(f"   Description: {h.description}")

            # Add relevant evidence
            relevant_ratings = [
                r for r in matrix.ratings
                if r.hypothesis_id == h.id
            ]
            if relevant_ratings:
                context_parts.append("   Evidence ratings:")
                for r in relevant_ratings[:5]:
                    evidence = matrix.get_evidence(r.evidence_id)
                    if evidence:
                        context_parts.append(
                            f"   - [{r.rating.value}] {evidence.description[:100]}"
                        )

        context_parts.append("""

Provide devil's advocate challenges. Return as JSON:
{
  "challenges": [
    {
      "hypothesis_label": "H1",
      "counter_argument": "The strongest argument against this hypothesis",
      "disproof_evidence": "What would definitively disprove it",
      "alternative_angle": "A consideration they may have missed"
    }
  ]
}""")

        response = await self._generate(
            system_prompt=SYSTEM_PROMPTS["devils_advocate"],
            user_prompt="\n".join(context_parts),
            temperature=0.8,  # Slightly higher for creativity
        )

        return self._parse_challenges(response.get("text", ""), matrix)

    def _parse_challenges(
        self,
        text: str,
        matrix: ACHMatrix,
    ) -> list[Challenge]:
        """Parse devil's advocate challenges from LLM response."""
        challenges = []

        # Map hypothesis labels to IDs
        hyp_map = {f"H{i+1}": h for i, h in enumerate(matrix.hypotheses)}

        # Try to extract JSON
        try:
            # Clean markdown code blocks
            cleaned = re.sub(r'```json?\s*', '', text)
            cleaned = re.sub(r'```\s*$', '', cleaned)

            data = json.loads(cleaned)

            for c in data.get("challenges", []):
                label = c.get("hypothesis_label", "").upper()
                if label in hyp_map:
                    challenges.append(Challenge(
                        hypothesis_id=hyp_map[label].id,
                        hypothesis_label=label,
                        counter_argument=c.get("counter_argument", ""),
                        disproof_evidence=c.get("disproof_evidence", ""),
                        alternative_angle=c.get("alternative_angle", ""),
                    ))
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON challenges, using text fallback")
            # Fallback: try to extract from unstructured text
            # This is a simplified fallback
            pass

        return challenges

    async def generate_full_challenge(
        self,
        matrix: ACHMatrix,
        hypothesis_id: str | None = None,
    ) -> DevilsAdvocateChallenge | None:
        """
        Generate a comprehensive devil's advocate challenge.

        This creates the full DevilsAdvocateChallenge model used by the API.

        Args:
            matrix: The ACH matrix
            hypothesis_id: Target hypothesis (or leading if None)

        Returns:
            DevilsAdvocateChallenge or None
        """
        # Determine target hypothesis
        if hypothesis_id:
            hypothesis = matrix.get_hypothesis(hypothesis_id)
        else:
            # Try leading hypothesis first, fall back to first hypothesis
            hypothesis = matrix.leading_hypothesis
            if not hypothesis and matrix.hypotheses:
                hypothesis = matrix.hypotheses[0]

        if not hypothesis:
            return None

        # Get challenges
        challenges = await self.challenge_hypotheses(matrix, hypothesis.id)

        if not challenges:
            return None

        challenge = challenges[0]

        # Build comprehensive challenge text
        challenge_text = f"""Devil's Advocate Analysis for: {hypothesis.title}

## Counter-Argument
{challenge.counter_argument}

## What Would Disprove This Hypothesis
{challenge.disproof_evidence}

## Alternative Considerations
{challenge.alternative_angle}"""

        return DevilsAdvocateChallenge(
            matrix_id=matrix.id,
            hypothesis_id=hypothesis.id,
            challenge_text=challenge_text,
            alternative_interpretation=challenge.alternative_angle,
            weaknesses_identified=[challenge.counter_argument],
            evidence_gaps=[challenge.disproof_evidence],
            recommended_investigations=[
                f"Investigate: {challenge.disproof_evidence}"
            ],
            model_used=self.llm_service.model if hasattr(self.llm_service, 'model') else "unknown",
        )

    # =========================================================================
    # Analysis Insights
    # =========================================================================

    async def get_analysis_insights(
        self,
        matrix: ACHMatrix,
    ) -> AnalysisInsights:
        """
        Generate comprehensive analysis insights.

        Args:
            matrix: The ACH matrix

        Returns:
            AnalysisInsights object
        """
        # Build matrix summary
        summary_parts = [
            f"Matrix: {matrix.title}",
            f"Description: {matrix.description or 'N/A'}",
            f"\nHypotheses ({len(matrix.hypotheses)}):",
        ]

        for i, h in enumerate(matrix.hypotheses):
            score = matrix.get_score(h.id)
            score_info = f" (Score: {score.normalized_score:.1f}, Rank: {score.rank})" if score else ""
            summary_parts.append(f"  H{i+1}: {h.title}{score_info}")

        summary_parts.append(f"\nEvidence ({len(matrix.evidence)}):")
        for i, e in enumerate(matrix.evidence[:10]):
            summary_parts.append(f"  E{i+1}: {e.description[:80]}")
        if len(matrix.evidence) > 10:
            summary_parts.append(f"  ... and {len(matrix.evidence) - 10} more")

        summary_parts.append("\nRating Summary:")
        for h in matrix.hypotheses:
            label = f"H{matrix.hypotheses.index(h) + 1}"
            ratings = [r for r in matrix.ratings if r.hypothesis_id == h.id]
            if ratings:
                counts = {}
                for r in ratings:
                    counts[r.rating.value] = counts.get(r.rating.value, 0) + 1
                counts_str = ", ".join(f"{v}: {c}" for v, c in counts.items())
                summary_parts.append(f"  {label}: {counts_str}")

        prompt = "\n".join(summary_parts)
        prompt += "\n\nProvide comprehensive analysis insights."

        response = await self._generate(
            system_prompt=SYSTEM_PROMPTS["insights"],
            user_prompt=prompt,
            max_tokens=3000,
        )

        return self._parse_insights(response.get("text", ""))

    def _parse_insights(self, text: str) -> AnalysisInsights:
        """Parse analysis insights from LLM response."""
        # For now, return the full text and let the UI format it
        return AnalysisInsights(
            leading_hypothesis="",  # Could extract from text
            key_evidence=[],
            evidence_gaps=[],
            cognitive_biases=[],
            recommendations=[],
            full_text=text,
        )

    # =========================================================================
    # Milestone Suggestions
    # =========================================================================

    async def suggest_milestones(
        self,
        matrix: ACHMatrix,
    ) -> list[MilestoneSuggestion]:
        """
        Suggest future indicators/milestones for hypotheses.

        Args:
            matrix: The ACH matrix

        Returns:
            List of MilestoneSuggestion objects
        """
        if not matrix.hypotheses:
            return []

        # Build hypotheses list
        hyp_list = "\n".join(
            f"- H{i+1}: {h.title}"
            for i, h in enumerate(matrix.hypotheses)
        )

        prompt = f"""Matrix: {matrix.title}
Description: {matrix.description or 'N/A'}

Hypotheses:
{hyp_list}

For each hypothesis, suggest 2-3 specific, observable future events or indicators that would either support or contradict that hypothesis.

Format each milestone with the hypothesis label followed by the specific observable event:
H1: By [timeframe], [specific observable event that would confirm or refute hypothesis]

Example format:
H1: Within 6 months, financial records show payments to the contractor
H1: By end of year, witness testimony corroborates the timeline
H2: Within 3 months, forensic analysis reveals the document was altered

Be specific about what would be observable and when."""

        response = await self._generate(
            system_prompt=SYSTEM_PROMPTS["milestones"],
            user_prompt=prompt,
        )

        return self._parse_milestones(response.get("text", ""), matrix)

    def _parse_milestones(
        self,
        text: str,
        matrix: ACHMatrix,
    ) -> list[MilestoneSuggestion]:
        """Parse milestone suggestions from LLM response."""
        suggestions = []

        # Map hypothesis labels to IDs
        hyp_map = {f"H{i+1}": h for i, h in enumerate(matrix.hypotheses)}

        # Split into hypothesis sections (H1:, H2:, etc.)
        sections = re.split(r'\n(?=\s*H\d+\s*[:\-])', text.strip())

        for section in sections:
            if not section.strip():
                continue

            # Match the hypothesis label at the start
            header_match = re.match(r'^\s*(H\d+)\s*[:\-]\s*(.*)$', section.strip(), re.IGNORECASE)
            if not header_match:
                continue

            label = header_match.group(1).upper()
            if label not in hyp_map:
                continue

            # Get the rest after the header
            first_line_content = header_match.group(2).strip()
            remaining_lines = section.strip().split('\n')[1:]

            # If first line has content, it's a single-line milestone
            if first_line_content and not first_line_content.startswith('-'):
                # Filter out placeholder text from prompt format examples
                lower_desc = first_line_content.lower()
                is_placeholder = (
                    lower_desc in ('description of milestone/indicator', '...')
                    or lower_desc.startswith('by [timeframe]')
                    or '[specific observable event' in lower_desc
                )
                if not is_placeholder:
                    suggestions.append(MilestoneSuggestion(
                        hypothesis_id=hyp_map[label].id,
                        hypothesis_label=label,
                        description=first_line_content,
                    ))

            # Parse bullet points as individual milestones
            for line in remaining_lines:
                line = line.strip()
                # Match bullet points: "- milestone" or "* milestone"
                bullet_match = re.match(r'^[\-\*\u2022]\s*(.+)$', line)
                if bullet_match:
                    description = bullet_match.group(1).strip()
                    if description:
                        lower_desc = description.lower()
                        is_placeholder = (
                            lower_desc == 'description of milestone/indicator'
                            or lower_desc.startswith('by [timeframe]')
                            or '[specific observable event' in lower_desc
                        )
                        if not is_placeholder:
                            suggestions.append(MilestoneSuggestion(
                                hypothesis_id=hyp_map[label].id,
                                hypothesis_label=label,
                                description=description,
                            ))

        return suggestions

    # =========================================================================
    # Evidence from Documents
    # =========================================================================

    async def extract_evidence_from_text(
        self,
        text: str,
        hypotheses: list[Hypothesis],
        max_items: int = 5,
    ) -> list[EvidenceSuggestion]:
        """
        Extract potential evidence from document text.

        This can be used to automatically identify relevant evidence
        from ingested documents.

        Args:
            text: Document text to analyze
            hypotheses: Current hypotheses
            max_items: Maximum evidence items to extract

        Returns:
            List of EvidenceSuggestion objects
        """
        if not hypotheses:
            return []

        # Truncate text if too long
        max_chars = 4000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        hyp_list = "\n".join(
            f"- H{i+1}: {h.title}"
            for i, h in enumerate(hypotheses)
        )

        prompt = f"""Hypotheses under consideration:
{hyp_list}

Document text:
{text}

Extract up to {max_items} pieces of evidence from this document that are relevant
to the hypotheses. Focus on facts, dates, names, and specific claims.

Format each as:
1. Evidence description (TYPE)
Where TYPE is: fact, testimony, document, physical, circumstantial, inference"""

        response = await self._generate(
            system_prompt=SYSTEM_PROMPTS["evidence"],
            user_prompt=prompt,
        )

        return self._parse_evidence(response.get("text", ""))
