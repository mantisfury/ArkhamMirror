"""
LLM Analysis Worker - Deep document analysis using LLMs.

Pool: llm-analysis
Purpose: Deep LLM-powered document analysis including contradictions, speculation,
fact-checking, credibility assessment, and narrative reconstruction.

Supports any OpenAI-compatible text endpoint:
- LM Studio (default): http://localhost:1234/v1
- Ollama: http://localhost:11434/v1
- vLLM: http://localhost:8000/v1
- Any OpenAI-compatible API

Best for: investigative journalism, contradiction detection, fact verification,
credibility assessment, and multi-document narrative analysis.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from .base import BaseWorker

logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://localhost:1234/v1")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "qwen2.5-7b-instruct")
DEFAULT_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "180"))
MAX_CONTEXT_TOKENS = int(os.environ.get("LLM_MAX_CONTEXT", "8000"))


# System prompts for different operations
SYSTEM_PROMPTS = {
    "find_contradictions": """You are an expert analytical engine specialized in identifying logical contradictions, factual inconsistencies, and conflicting claims across texts.

Your role:
- Identify direct contradictions (A says X, B says not-X)
- Find logical inconsistencies (mutually exclusive claims)
- Detect factual conflicts (different values, dates, names, events)
- Assess severity (high: direct contradiction, medium: inconsistency, low: tension)

Be precise, cite specific claims, and explain why they conflict.""",

    "verify_claims": """You are a rigorous fact-checking engine for investigative journalism.

Your role:
- Verify claims against provided evidence
- Quote specific evidence passages
- Determine verdict: supported, refuted, or uncertain
- Express confidence levels honestly
- Distinguish between evidence and inference

Always be skeptical, thorough, and transparent about uncertainty.""",

    "speculate": """You are an analytical speculation engine for investigative research.

Your role:
- Generate informed hypotheses based on available facts
- Clearly label all speculation as such
- List supporting facts and required assumptions
- Assess confidence/plausibility of each hypothesis
- Identify what additional evidence would confirm or refute

CRITICAL: Distinguish between facts (what is known) and speculation (what might be true).
Never present speculation as fact.""",

    "find_gaps": """You are an information gap analysis engine.

Your role:
- Identify missing information and context
- Highlight expected topics that aren't addressed
- Assess importance of each gap
- Suggest specific questions to fill gaps
- Detect evasions and omissions

Focus on what's notably absent, unexplained, or under-addressed.""",

    "compare_narratives": """You are a narrative comparison engine for multi-source analysis.

Your role:
- Compare multiple accounts of the same event/topic
- Identify common facts (agreement across sources)
- Find discrepancies (conflicting accounts)
- Extract unique information from each source
- Assess timeline consistency
- Evaluate source reliability factors

Be objective and systematic in comparing narratives.""",

    "extract_timeline": """You are a chronological event extraction engine.

Your role:
- Extract all temporal events from text
- Normalize dates and times
- Order events chronologically
- Assess confidence for each date/event
- Quote source text for verification
- Flag timeline inconsistencies

Be precise about dates and distinguish certainty from approximation.""",

    "assess_credibility": """You are a source credibility assessment engine using journalistic standards.

Your role:
- Evaluate objectivity vs. bias
- Assess specificity and verifiability
- Identify red flags (vague claims, emotional language, circular logic)
- Highlight strengths (citations, specific details, balanced view)
- Score credibility factors on 0-1 scale
- Consider source context (author, date, type)

Apply rigorous journalistic skepticism.""",

    "analyze": """You are a comprehensive document analysis engine.

Your role:
- Execute multiple analytical operations on text
- Provide structured, detailed analysis
- Combine insights from different analytical approaches
- Maintain consistency across operations

Be thorough, systematic, and precise.""",
}


class AnalysisWorker(BaseWorker):
    """
    Worker for deep LLM-powered document analysis.

    Supports multiple analysis operations:
    - find_contradictions: Find contradictions between two texts
    - verify_claims: Fact-check claims against evidence
    - speculate: Generate informed speculation/hypotheses
    - find_gaps: Identify information gaps
    - compare_narratives: Compare multiple accounts
    - extract_timeline: Extract chronological events
    - assess_credibility: Assess document/source credibility
    - analyze: Full analysis pipeline (multiple operations)

    Payload format:
    {
        "operation": "find_contradictions|verify_claims|speculate|...",

        # For find_contradictions:
        "text_a": "first text",
        "text_b": "second text",
        "context": "optional context",

        # For verify_claims:
        "claims": ["claim1", "claim2"],
        "evidence": "evidence text",
        "context": "optional context",

        # For speculate:
        "facts": ["fact1", "fact2"],
        "question": "What might explain...",
        "constraints": ["must be X", "cannot be Y"],

        # For find_gaps:
        "text": "document text",
        "expected_topics": ["topic1", "topic2"],

        # For compare_narratives:
        "narratives": [
            {"source": "A", "text": "..."},
            {"source": "B", "text": "..."}
        ],

        # For extract_timeline:
        "text": "document text",
        "reference_date": null,  # Optional: reference date for relative dates

        # For assess_credibility:
        "text": "document text",
        "source_info": {
            "author": "...",
            "date": "...",
            "type": "report|article|memo|..."
        },

        # For analyze (pipeline):
        "text": "document text",
        "operations": ["find_gaps", "extract_timeline", "assess_credibility"],

        # Optional API config:
        "endpoint": "http://localhost:1234/v1",
        "model": "qwen2.5-7b-instruct",
        "temperature": 0.1,
        "max_tokens": 4096,
    }

    Returns:
    Operation-specific result dict with analysis results, metadata, and success status.
    """

    pool = "llm-analysis"
    name = "AnalysisWorker"
    job_timeout = 300.0  # Complex analysis takes time

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        return self._client

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an analysis job.

        Args:
            job_id: Unique job identifier
            payload: Job data with operation and parameters

        Returns:
            Dict with analysis results
        """
        operation = payload.get("operation")
        if not operation:
            raise ValueError("Missing required field: 'operation'")

        # Route to appropriate handler
        if operation == "find_contradictions":
            return await self._find_contradictions(job_id, payload)
        elif operation == "verify_claims":
            return await self._verify_claims(job_id, payload)
        elif operation == "speculate":
            return await self._speculate(job_id, payload)
        elif operation == "find_gaps":
            return await self._find_gaps(job_id, payload)
        elif operation == "compare_narratives":
            return await self._compare_narratives(job_id, payload)
        elif operation == "extract_timeline":
            return await self._extract_timeline(job_id, payload)
        elif operation == "assess_credibility":
            return await self._assess_credibility(job_id, payload)
        elif operation == "analyze":
            return await self._analyze_pipeline(job_id, payload)
        else:
            raise ValueError(f"Unknown operation: {operation}")

    async def _find_contradictions(
        self, job_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Find contradictions between two texts.

        Args:
            job_id: Job ID
            payload: Parameters with text_a, text_b, context

        Returns:
            Contradictions result dict
        """
        text_a = payload.get("text_a")
        text_b = payload.get("text_b")
        context = payload.get("context", "")

        if not text_a or not text_b:
            raise ValueError("Both 'text_a' and 'text_b' are required")

        context_section = f"\n\nContext: {context}\n" if context else ""

        user_prompt = f"""Compare these two texts and identify all contradictions, inconsistencies, and conflicting claims.

Text A:
{text_a}

Text B:
{text_b}
{context_section}
Return your analysis as JSON:
{{
    "contradictions": [
        {{
            "claim_a": "specific claim from text A",
            "claim_b": "conflicting claim from text B",
            "explanation": "why these contradict",
            "severity": "high|medium|low"
        }}
    ],
    "count": N
}}

Severity levels:
- high: Direct factual contradiction (mutually exclusive)
- medium: Logical inconsistency or conflicting implications
- low: Tension or discrepancy but not necessarily contradictory"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["find_contradictions"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        result = self._parse_json_response(response)

        if not result or "contradictions" not in result:
            result = {"contradictions": [], "count": 0}

        if "count" not in result:
            result["count"] = len(result.get("contradictions", []))

        return {
            **result,
            "success": True,
        }

    async def _verify_claims(
        self, job_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fact-check claims against evidence.

        Args:
            job_id: Job ID
            payload: Parameters with claims, evidence, context

        Returns:
            Verification result dict
        """
        claims = payload.get("claims")
        evidence = payload.get("evidence")
        context = payload.get("context", "")

        if not claims or not evidence:
            raise ValueError("Both 'claims' and 'evidence' are required")

        if not isinstance(claims, list):
            claims = [claims]

        claims_text = "\n".join([f"{i+1}. {claim}" for i, claim in enumerate(claims)])
        context_section = f"\n\nContext: {context}\n" if context else ""

        user_prompt = f"""Fact-check these claims against the provided evidence.

Claims to verify:
{claims_text}

Evidence:
{evidence}
{context_section}
For each claim, return as JSON:
{{
    "results": [
        {{
            "claim": "the claim being verified",
            "verdict": "supported|refuted|uncertain",
            "evidence_quote": "specific quote from evidence",
            "confidence": 0.85,
            "reasoning": "explanation of verdict"
        }}
    ]
}}

Verdicts:
- supported: Evidence directly confirms the claim
- refuted: Evidence contradicts the claim
- uncertain: Insufficient or ambiguous evidence

Be rigorous. Quote exact evidence. Express uncertainty honestly."""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["verify_claims"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        result = self._parse_json_response(response)

        if not result or "results" not in result:
            result = {
                "results": [
                    {
                        "claim": claim,
                        "verdict": "uncertain",
                        "confidence": 0.0,
                        "error": "Failed to verify"
                    }
                    for claim in claims
                ]
            }

        return {
            **result,
            "claims_checked": len(result.get("results", [])),
            "success": True,
        }

    async def _speculate(
        self, job_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate informed speculation/hypotheses.

        Args:
            job_id: Job ID
            payload: Parameters with facts, question, constraints

        Returns:
            Speculation result dict
        """
        facts = payload.get("facts")
        question = payload.get("question")
        constraints = payload.get("constraints", [])

        if not facts or not question:
            raise ValueError("Both 'facts' and 'question' are required")

        if not isinstance(facts, list):
            facts = [facts]

        facts_text = "\n".join([f"- {fact}" for fact in facts])
        constraints_section = ""
        if constraints:
            constraints_text = "\n".join([f"- {c}" for c in constraints])
            constraints_section = f"\n\nConstraints:\n{constraints_text}"

        user_prompt = f"""Based on these known facts, generate informed hypotheses to answer the question.

Known Facts:
{facts_text}

Question: {question}
{constraints_section}

Return as JSON:
{{
    "hypotheses": [
        {{
            "hypothesis": "clear statement of hypothesis",
            "supporting_facts": ["fact1", "fact2"],
            "assumptions": ["assumption1", "assumption2"],
            "confidence": 0.7,
            "reasoning": "why this hypothesis is plausible"
        }}
    ]
}}

CRITICAL:
- Clearly distinguish facts from speculation
- List all assumptions explicitly
- Be honest about confidence levels
- Mark as hypothesis, not fact"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["speculate"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        result = self._parse_json_response(response)

        if not result or "hypotheses" not in result:
            result = {"hypotheses": []}

        return {
            **result,
            "hypothesis_count": len(result.get("hypotheses", [])),
            "question": question,
            "success": True,
        }

    async def _find_gaps(
        self, job_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Identify information gaps and missing context.

        Args:
            job_id: Job ID
            payload: Parameters with text, expected_topics

        Returns:
            Gaps result dict
        """
        text = payload.get("text")
        expected_topics = payload.get("expected_topics", [])

        if not text:
            raise ValueError("Missing required field: 'text'")

        topics_section = ""
        if expected_topics:
            topics_text = ", ".join(expected_topics)
            topics_section = f"\n\nExpected topics: {topics_text}"

        user_prompt = f"""Analyze this text and identify information gaps, missing context, and unexplained elements.
{topics_section}

Text:
{text}

Return as JSON:
{{
    "gaps": [
        {{
            "topic": "what's missing",
            "importance": "high|medium|low",
            "suggested_questions": ["question1", "question2"],
            "reasoning": "why this gap matters"
        }}
    ]
}}

Focus on:
- Expected information that's absent
- Claims without supporting details
- Unexplained references or context
- Evasions or omissions
- Questions left unanswered"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["find_gaps"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        result = self._parse_json_response(response)

        if not result or "gaps" not in result:
            result = {"gaps": []}

        return {
            **result,
            "gap_count": len(result.get("gaps", [])),
            "success": True,
        }

    async def _compare_narratives(
        self, job_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare multiple accounts of same event.

        Args:
            job_id: Job ID
            payload: Parameters with narratives list

        Returns:
            Comparison result dict
        """
        narratives = payload.get("narratives")

        if not narratives or not isinstance(narratives, list):
            raise ValueError("'narratives' must be a list of {source, text} objects")

        if len(narratives) < 2:
            raise ValueError("At least 2 narratives required for comparison")

        # Build narratives section
        narratives_text = ""
        for narr in narratives:
            source = narr.get("source", "Unknown")
            text = narr.get("text", "")
            narratives_text += f"\n\n=== Source: {source} ===\n{text}"

        sources_list = [n.get("source", "Unknown") for n in narratives]

        user_prompt = f"""Compare these accounts of the same event/topic.

{narratives_text}

Return as JSON:
{{
    "common_facts": ["fact1", "fact2"],
    "discrepancies": [
        {{
            "topic": "what differs",
            "accounts": {{
                "Source A": "what A says",
                "Source B": "what B says"
            }},
            "significance": "high|medium|low"
        }}
    ],
    "unique_to_each": {{
        "Source A": ["unique fact1", "unique fact2"],
        "Source B": ["unique fact1"]
    }},
    "timeline_consistent": true,
    "reliability_assessment": "brief overall assessment"
}}

Focus on:
- What all sources agree on (common facts)
- Where sources conflict (discrepancies)
- What's unique to each source
- Timeline consistency across accounts
- Overall reliability patterns"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["compare_narratives"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        result = self._parse_json_response(response)

        if not result:
            result = {
                "common_facts": [],
                "discrepancies": [],
                "unique_to_each": {src: [] for src in sources_list},
                "timeline_consistent": None,
            }

        return {
            **result,
            "sources_compared": sources_list,
            "success": True,
        }

    async def _extract_timeline(
        self, job_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract chronological events.

        Args:
            job_id: Job ID
            payload: Parameters with text, reference_date

        Returns:
            Timeline result dict
        """
        text = payload.get("text")
        reference_date = payload.get("reference_date")

        if not text:
            raise ValueError("Missing required field: 'text'")

        reference_section = ""
        if reference_date:
            reference_section = f"\n\nReference date (for relative dates): {reference_date}"

        user_prompt = f"""Extract all temporal events from this text in chronological order.
{reference_section}

Text:
{text}

Return as JSON:
{{
    "events": [
        {{
            "date": "YYYY-MM-DD or approximate date",
            "time": "HH:MM if available",
            "event": "what happened",
            "confidence": 0.9,
            "source_quote": "exact quote from text",
            "certainty": "exact|approximate|inferred"
        }}
    ],
    "timeline_valid": true,
    "inconsistencies": ["any timeline issues"]
}}

Guidelines:
- Extract all dates and events
- Normalize to YYYY-MM-DD format where possible
- Order chronologically
- Distinguish exact vs approximate dates
- Quote source text for verification
- Flag any timeline inconsistencies"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["extract_timeline"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        result = self._parse_json_response(response)

        if not result or "events" not in result:
            result = {"events": [], "timeline_valid": None}

        return {
            **result,
            "event_count": len(result.get("events", [])),
            "success": True,
        }

    async def _assess_credibility(
        self, job_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess document/source credibility.

        Args:
            job_id: Job ID
            payload: Parameters with text, source_info

        Returns:
            Credibility assessment dict
        """
        text = payload.get("text")
        source_info = payload.get("source_info", {})

        if not text:
            raise ValueError("Missing required field: 'text'")

        source_section = ""
        if source_info:
            source_section = "\n\nSource Information:"
            if source_info.get("author"):
                source_section += f"\n- Author: {source_info['author']}"
            if source_info.get("date"):
                source_section += f"\n- Date: {source_info['date']}"
            if source_info.get("type"):
                source_section += f"\n- Type: {source_info['type']}"

        user_prompt = f"""Assess the credibility of this document using journalistic standards.
{source_section}

Text:
{text}

Return as JSON:
{{
    "credibility_score": 0.75,
    "factors": {{
        "objectivity": 0.8,
        "specificity": 0.7,
        "verifiability": 0.6,
        "consistency": 0.9,
        "transparency": 0.7
    }},
    "red_flags": [
        "vague claims without evidence",
        "emotional/loaded language"
    ],
    "strengths": [
        "specific dates and details",
        "cites sources"
    ],
    "overall_assessment": "brief credibility assessment"
}}

Evaluation criteria:
- Objectivity: Bias, emotional language, loaded terms
- Specificity: Concrete details vs vague claims
- Verifiability: Citations, sources, checkable facts
- Consistency: Internal logical consistency
- Transparency: Clear attribution, methodology

Use 0-1 scale for all scores."""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["assess_credibility"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        result = self._parse_json_response(response)

        if not result or "credibility_score" not in result:
            result = {
                "credibility_score": 0.5,
                "factors": {},
                "red_flags": [],
                "strengths": [],
                "overall_assessment": "Unable to assess"
            }

        return {
            **result,
            "success": True,
        }

    async def _analyze_pipeline(
        self, job_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run multiple analysis operations in sequence.

        Args:
            job_id: Job ID
            payload: Parameters with text and operations list

        Returns:
            Combined analysis results
        """
        text = payload.get("text")
        operations = payload.get("operations")

        if not text:
            raise ValueError("Missing required field: 'text'")

        if not operations or not isinstance(operations, list):
            raise ValueError("Pipeline mode requires 'operations' list")

        results = {}
        errors = []

        for operation in operations:
            try:
                # Build operation-specific payload
                op_payload = {**payload, "operation": operation}

                if operation == "find_gaps":
                    result = await self._find_gaps(job_id, op_payload)
                    results["gaps"] = result.get("gaps")
                    results["gap_count"] = result.get("gap_count")

                elif operation == "extract_timeline":
                    result = await self._extract_timeline(job_id, op_payload)
                    results["timeline"] = result.get("events")
                    results["timeline_valid"] = result.get("timeline_valid")

                elif operation == "assess_credibility":
                    result = await self._assess_credibility(job_id, op_payload)
                    results["credibility"] = result

                else:
                    logger.warning(f"Unknown operation in pipeline: {operation}")

            except Exception as e:
                logger.error(f"Pipeline operation {operation} failed: {e}")
                errors.append({"operation": operation, "error": str(e)})

        return {
            **results,
            "operations_completed": [
                op for op in operations
                if op not in [e["operation"] for e in errors]
            ],
            "operations_failed": errors,
            "success": len(errors) == 0,
        }

    async def _call_llm(
        self,
        job_id: str,
        system_prompt: str,
        user_prompt: str,
        payload: Dict[str, Any],
    ) -> str:
        """
        Call LLM API.

        Args:
            job_id: Job ID
            system_prompt: System message
            user_prompt: User message
            payload: Job payload with API config

        Returns:
            LLM response text
        """
        endpoint = payload.get("endpoint", DEFAULT_ENDPOINT)
        model = payload.get("model", DEFAULT_MODEL)
        temperature = payload.get("temperature", 0.1)
        max_tokens = payload.get("max_tokens", 4096)

        # Truncate text if needed (rough estimate: 4 chars per token)
        if len(user_prompt) > MAX_CONTEXT_TOKENS * 4:
            logger.warning(f"Job {job_id}: Text truncated to fit context window")
            user_prompt = user_prompt[:MAX_CONTEXT_TOKENS * 4] + "\n\n[Text truncated...]"

        api_url = f"{endpoint.rstrip('/')}/chat/completions"

        request_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        client = await self._get_client()

        try:
            response = await client.post(api_url, json=request_body)
            response.raise_for_status()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Failed to connect to LLM endpoint: {endpoint}. "
                f"Make sure LM Studio/Ollama/vLLM is running."
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"LLM API error: {e.response.status_code} - {e.response.text}"
            )

        result = response.json()

        # Extract response text
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            return message.get("content", "")

        return ""

    def _parse_json_response(self, response: str) -> Any:
        """
        Parse JSON from LLM response.

        Handles markdown code blocks and graceful fallback.

        Args:
            response: LLM response text

        Returns:
            Parsed JSON object or None
        """
        try:
            # Clean markdown code blocks
            cleaned = re.sub(r"```json?\s*", "", response)
            cleaned = re.sub(r"```\s*$", "", cleaned)
            cleaned = cleaned.strip()

            if cleaned:
                return json.loads(cleaned)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response[:200]}")

        return None

    async def cleanup(self):
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None


def run_analysis_worker(database_url: str = None, worker_id: str = None):
    """
    Convenience function to run an AnalysisWorker.

    Environment variables:
    - LLM_ENDPOINT: API endpoint (default: http://localhost:1234/v1)
    - LLM_MODEL: Model ID (default: qwen2.5-7b-instruct)
    - LLM_TIMEOUT: Request timeout in seconds (default: 180)
    - LLM_MAX_CONTEXT: Max context tokens (default: 8000)

    Args:
        database_url: PostgreSQL connection URL (defaults to env var)
        worker_id: Optional worker ID (auto-generated if not provided)

    Example:
        # Default (LM Studio)
        python -m arkham_frame.workers.analysis_worker

        # With Ollama
        LLM_ENDPOINT=http://localhost:11434/v1 LLM_MODEL=qwen2.5 python -m arkham_frame.workers.analysis_worker
    """
    import asyncio
    worker = AnalysisWorker(database_url=database_url, worker_id=worker_id)
    asyncio.run(worker.run())


if __name__ == "__main__":
    run_analysis_worker()
