"""
LLM Enrichment Worker - Document enrichment using LLMs.

Pool: llm-enrich
Purpose: Extract summaries, keywords, metadata, entities, and structured info from text.

Supports any OpenAI-compatible text endpoint:
- LM Studio (default): http://localhost:1234/v1
- Ollama: http://localhost:11434/v1
- vLLM: http://localhost:8000/v1
- Any OpenAI-compatible API

Best for: document intelligence, metadata extraction, automated classification.
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
DEFAULT_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120"))
MAX_CONTEXT_TOKENS = int(os.environ.get("LLM_MAX_CONTEXT", "4000"))


# System prompts for different operations
SYSTEM_PROMPTS = {
    "summarize": """You are a professional summarization engine. Your job is to create concise, accurate summaries that capture the essential information and main points of the text.""",

    "extract_keywords": """You are a keyword extraction engine. Identify the most important terms, concepts, and phrases from the text. Return results as JSON array.""",

    "extract_metadata": """You are a metadata extraction engine. Analyze the text and extract structured metadata fields. Return results as JSON object.""",

    "classify": """You are a document classification engine. Analyze the text and determine its category/type. Return results as JSON object.""",

    "extract_entities": """You are an entity extraction engine. Identify people, organizations, locations, dates, monetary values, and other named entities. Return results as JSON array.""",

    "generate_questions": """You are a question generation engine. Create insightful questions that this document answers or relates to.""",
}


class EnrichWorker(BaseWorker):
    """
    Worker for LLM-powered document enrichment.

    Supports multiple enrichment operations:
    - summarize: Generate summaries (brief, detailed, bullets)
    - extract_keywords: Extract key terms and concepts
    - extract_metadata: Extract structured metadata
    - classify: Document classification
    - extract_entities: Named entity extraction
    - generate_questions: Generate relevant questions
    - enrich: Full enrichment pipeline (multiple operations)

    Payload format:
    {
        "operation": "summarize|extract_keywords|extract_metadata|classify|extract_entities|generate_questions|enrich",
        "text": "document text to analyze",

        # Operation-specific parameters:
        # For summarize:
        "max_length": 200,           # Max summary length
        "style": "brief|detailed|bullets",  # Summary style

        # For extract_keywords:
        "max_keywords": 10,           # Max number of keywords
        "include_scores": true,       # Include confidence scores

        # For extract_metadata:
        "fields": ["title", "author", "date", "type", "language"],

        # For classify:
        "categories": ["legal", "financial", "technical", ...],  # Or auto: true

        # For extract_entities:
        "entity_types": ["person", "org", "location", "date", "money"],

        # For generate_questions:
        "max_questions": 5,

        # For enrich (pipeline):
        "operations": ["summarize", "extract_keywords", "classify"],

        # Optional API config:
        "endpoint": "http://localhost:1234/v1",
        "model": "qwen2.5-7b-instruct",
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    Returns:
    Operation-specific result dict with:
    - summary, keywords, metadata, category, entities, or questions
    - metadata about the operation
    - success status
    """

    pool = "llm-enrich"
    name = "EnrichWorker"
    job_timeout = 180.0  # LLM calls can be slow

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
        Process an enrichment job.

        Args:
            job_id: Unique job identifier
            payload: Job data with operation and text

        Returns:
            Dict with enrichment results
        """
        operation = payload.get("operation")
        if not operation:
            raise ValueError("Missing required field: 'operation'")

        text = payload.get("text")
        if not text:
            raise ValueError("Missing required field: 'text'")

        # Route to appropriate handler
        if operation == "summarize":
            return await self._summarize(job_id, text, payload)
        elif operation == "extract_keywords":
            return await self._extract_keywords(job_id, text, payload)
        elif operation == "extract_metadata":
            return await self._extract_metadata(job_id, text, payload)
        elif operation == "classify":
            return await self._classify(job_id, text, payload)
        elif operation == "extract_entities":
            return await self._extract_entities(job_id, text, payload)
        elif operation == "generate_questions":
            return await self._generate_questions(job_id, text, payload)
        elif operation == "enrich":
            return await self._enrich_pipeline(job_id, text, payload)
        else:
            raise ValueError(f"Unknown operation: {operation}")

    async def _summarize(
        self, job_id: str, text: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate document summary.

        Args:
            job_id: Job ID
            text: Text to summarize
            payload: Parameters

        Returns:
            Summary result dict
        """
        max_length = payload.get("max_length", 200)
        style = payload.get("style", "brief")

        # Build prompt based on style
        if style == "brief":
            user_prompt = f"Summarize this text in 1-2 sentences (max {max_length} words):\n\n{text}"
        elif style == "detailed":
            user_prompt = f"Provide a detailed summary of this text (max {max_length} words):\n\n{text}"
        elif style == "bullets":
            user_prompt = f"Summarize this text as bullet points (max 5-7 bullets):\n\n{text}"
        else:
            user_prompt = f"Summarize this text (max {max_length} words):\n\n{text}"

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["summarize"],
            user_prompt=user_prompt,
            payload=payload,
        )

        summary = response.strip()

        return {
            "summary": summary,
            "original_length": len(text.split()),
            "summary_length": len(summary.split()),
            "style": style,
            "success": True,
        }

    async def _extract_keywords(
        self, job_id: str, text: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract keywords and key phrases.

        Args:
            job_id: Job ID
            text: Text to analyze
            payload: Parameters

        Returns:
            Keywords result dict
        """
        max_keywords = payload.get("max_keywords", 10)
        include_scores = payload.get("include_scores", True)

        if include_scores:
            user_prompt = f"""Extract the top {max_keywords} most important keywords/phrases from this text.
Return as JSON array with term and confidence score (0-1):
[{{"term": "keyword", "score": 0.95}}, ...]

Text:
{text}"""
        else:
            user_prompt = f"""Extract the top {max_keywords} most important keywords/phrases from this text.
Return as JSON array: ["keyword1", "keyword2", ...]

Text:
{text}"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["extract_keywords"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        keywords = self._parse_json_response(response)

        if not keywords:
            keywords = []

        return {
            "keywords": keywords,
            "count": len(keywords),
            "include_scores": include_scores,
            "success": True,
        }

    async def _extract_metadata(
        self, job_id: str, text: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract structured metadata.

        Args:
            job_id: Job ID
            text: Text to analyze
            payload: Parameters

        Returns:
            Metadata result dict
        """
        fields = payload.get("fields", ["title", "author", "date", "type", "language"])

        user_prompt = f"""Extract the following metadata fields from this text:
{', '.join(fields)}

Return as JSON object:
{{
    "title": "...",
    "author": "...",
    "date": "...",
    "type": "...",
    "language": "...",
    "confidence": 0.85
}}

If a field cannot be determined, use null.
Add a "confidence" field (0-1) indicating overall extraction confidence.

Text:
{text}"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["extract_metadata"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        metadata = self._parse_json_response(response)

        if not metadata:
            metadata = {field: None for field in fields}
            metadata["confidence"] = 0.0

        confidence = metadata.get("confidence", 0.5)

        return {
            "metadata": metadata,
            "confidence": confidence,
            "fields": fields,
            "success": True,
        }

    async def _classify(
        self, job_id: str, text: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Classify document type/topic.

        Args:
            job_id: Job ID
            text: Text to classify
            payload: Parameters

        Returns:
            Classification result dict
        """
        categories = payload.get("categories")
        auto = payload.get("auto", False)

        if auto or not categories:
            user_prompt = f"""Analyze this text and determine its category/type.
Return as JSON object:
{{
    "category": "primary category",
    "subcategory": "subcategory if applicable",
    "confidence": 0.92,
    "reasoning": "brief explanation"
}}

Text:
{text}"""
        else:
            user_prompt = f"""Classify this text into one of these categories:
{', '.join(categories)}

Return as JSON object:
{{
    "category": "selected category",
    "confidence": 0.92,
    "all_scores": {{"cat1": 0.92, "cat2": 0.05, ...}}
}}

Text:
{text}"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["classify"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        classification = self._parse_json_response(response)

        if not classification:
            classification = {"category": "unknown", "confidence": 0.0}

        return {
            "category": classification.get("category", "unknown"),
            "confidence": classification.get("confidence", 0.5),
            "all_scores": classification.get("all_scores", {}),
            "subcategory": classification.get("subcategory"),
            "reasoning": classification.get("reasoning"),
            "success": True,
        }

    async def _extract_entities(
        self, job_id: str, text: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract named entities.

        Args:
            job_id: Job ID
            text: Text to analyze
            payload: Parameters

        Returns:
            Entities result dict
        """
        entity_types = payload.get(
            "entity_types", ["person", "org", "location", "date", "money"]
        )

        user_prompt = f"""Extract named entities from this text.
Types to extract: {', '.join(entity_types)}

Return as JSON array:
[
    {{"text": "John Smith", "type": "person", "context": "CEO of Company X"}},
    {{"text": "Company X", "type": "org", "context": "mentioned as employer"}},
    ...
]

Text:
{text}"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["extract_entities"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse JSON response
        entities = self._parse_json_response(response)

        if not entities:
            entities = []

        return {
            "entities": entities,
            "count": len(entities),
            "entity_types": entity_types,
            "success": True,
        }

    async def _generate_questions(
        self, job_id: str, text: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate questions that the document answers.

        Args:
            job_id: Job ID
            text: Text to analyze
            payload: Parameters

        Returns:
            Questions result dict
        """
        max_questions = payload.get("max_questions", 5)

        user_prompt = f"""Generate {max_questions} insightful questions that this document answers or relates to.
Questions should be:
- Specific to the content
- Useful for search/discovery
- Well-formed and clear

Return as plain text, one question per line.

Text:
{text}"""

        # Call LLM
        response = await self._call_llm(
            job_id=job_id,
            system_prompt=SYSTEM_PROMPTS["generate_questions"],
            user_prompt=user_prompt,
            payload=payload,
        )

        # Parse questions (one per line)
        questions = [
            q.strip().lstrip("0123456789.-) ")
            for q in response.strip().split("\n")
            if q.strip()
        ]

        return {
            "questions": questions[:max_questions],
            "count": len(questions[:max_questions]),
            "success": True,
        }

    async def _enrich_pipeline(
        self, job_id: str, text: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run multiple enrichment operations in sequence.

        Args:
            job_id: Job ID
            text: Text to enrich
            payload: Parameters

        Returns:
            Combined enrichment results
        """
        operations = payload.get("operations", ["summarize", "extract_keywords"])

        if not operations:
            raise ValueError("Pipeline mode requires 'operations' list")

        results = {}
        errors = []

        for operation in operations:
            try:
                op_payload = {**payload, "operation": operation}

                if operation == "summarize":
                    result = await self._summarize(job_id, text, op_payload)
                    results["summary"] = result.get("summary")
                elif operation == "extract_keywords":
                    result = await self._extract_keywords(job_id, text, op_payload)
                    results["keywords"] = result.get("keywords")
                elif operation == "extract_metadata":
                    result = await self._extract_metadata(job_id, text, op_payload)
                    results["metadata"] = result.get("metadata")
                elif operation == "classify":
                    result = await self._classify(job_id, text, op_payload)
                    results["category"] = result.get("category")
                    results["category_confidence"] = result.get("confidence")
                elif operation == "extract_entities":
                    result = await self._extract_entities(job_id, text, op_payload)
                    results["entities"] = result.get("entities")
                elif operation == "generate_questions":
                    result = await self._generate_questions(job_id, text, op_payload)
                    results["questions"] = result.get("questions")
                else:
                    logger.warning(f"Unknown operation in pipeline: {operation}")

            except Exception as e:
                logger.error(f"Pipeline operation {operation} failed: {e}")
                errors.append({"operation": operation, "error": str(e)})

        return {
            **results,
            "operations_completed": list(results.keys()),
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
        max_tokens = payload.get("max_tokens", 2048)

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


def run_enrich_worker(database_url: str = None, worker_id: str = None):
    """
    Convenience function to run an EnrichWorker.

    Environment variables:
    - LLM_ENDPOINT: API endpoint (default: http://localhost:1234/v1)
    - LLM_MODEL: Model ID (default: qwen2.5-7b-instruct)
    - LLM_TIMEOUT: Request timeout in seconds (default: 120)
    - LLM_MAX_CONTEXT: Max context tokens (default: 4000)

    Args:
        database_url: PostgreSQL connection URL (defaults to env var)
        worker_id: Optional worker ID (auto-generated if not provided)

    Example:
        # Default (LM Studio)
        python -m arkham_frame.workers.enrich_worker

        # With Ollama
        LLM_ENDPOINT=http://localhost:11434/v1 LLM_MODEL=qwen2.5 python -m arkham_frame.workers.enrich_worker
    """
    import asyncio
    worker = EnrichWorker(database_url=database_url, worker_id=worker_id)
    asyncio.run(worker.run())


if __name__ == "__main__":
    run_enrich_worker()
