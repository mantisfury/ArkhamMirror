"""
AI Junior Analyst Service - Shared infrastructure for AI-powered analysis.

Provides context-aware analysis across all shards with:
- Shard-specific system prompts
- Conversation history support for follow-ups
- Streaming responses
- Structured output extraction
"""

from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import lru_cache
import logging
import uuid
import json
import hashlib
import time

logger = logging.getLogger(__name__)


class ResponseCache:
    """Simple time-based response cache for AI analysis."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple[str, float]] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds

    def _make_key(self, shard: str, target_id: str, context: Dict[str, Any], depth: str) -> str:
        """Create a cache key from request parameters."""
        context_str = json.dumps(context, sort_keys=True, default=str)
        key_data = f"{shard}:{target_id}:{context_str}:{depth}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def get(self, shard: str, target_id: str, context: Dict[str, Any], depth: str) -> Optional[str]:
        """Get cached response if available and not expired."""
        key = self._make_key(shard, target_id, context, depth)
        if key in self._cache:
            response, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return response
            # Expired, remove from cache
            del self._cache[key]
        return None

    def set(self, shard: str, target_id: str, context: Dict[str, Any], depth: str, response: str) -> None:
        """Cache a response."""
        # Evict oldest entries if at capacity
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        key = self._make_key(shard, target_id, context, depth)
        self._cache[key] = (response, time.time())

    def clear(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
        }


class AnalysisDepth(str, Enum):
    """Analysis depth options."""
    QUICK = "quick"
    DETAILED = "detailed"


@dataclass
class Message:
    """A message in a conversation."""
    role: str  # "user", "assistant", or "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AnalysisRequest:
    """Request for AI Junior Analyst analysis."""
    shard: str
    target_id: str
    context: Dict[str, Any]
    depth: AnalysisDepth = AnalysisDepth.QUICK
    session_id: Optional[str] = None
    message: Optional[str] = None  # Follow-up question
    conversation_history: Optional[List[Dict[str, str]]] = None

    def __post_init__(self):
        if isinstance(self.depth, str):
            self.depth = AnalysisDepth(self.depth)


@dataclass
class AnalysisResponse:
    """Response from AI Junior Analyst."""
    session_id: str
    analysis: str
    key_findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.8
    sources_cited: List[str] = field(default_factory=list)
    model_used: str = ""
    processing_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "analysis": self.analysis,
            "key_findings": self.key_findings,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "sources_cited": self.sources_cited,
            "model_used": self.model_used,
            "processing_time_ms": self.processing_time_ms,
        }


# Default system prompt for shards without custom prompts
DEFAULT_SYSTEM_PROMPT = """You are a junior intelligence analyst helping interpret data.
Your role is to explain patterns and findings in plain language that a non-expert can understand.

Provide:
1. A clear summary of what the data shows
2. Key patterns or anomalies worth noting
3. Suggested next steps for investigation

Keep your analysis concise and actionable. Reference specific items by name when relevant."""


# Shard-specific system prompts
SHARD_PROMPTS: Dict[str, str] = {
    "graph": """You are a junior network analyst helping interpret relationship graphs.
Your role is to identify patterns that might not be obvious to someone unfamiliar with
network analysis concepts.

For the current graph view, analyze:
1. Central vs peripheral nodes (who are the key players?)
2. Broker positions (who connects otherwise separate groups?)
3. Cluster patterns (what groups exist and how are they connected?)
4. Unusual connection patterns (unexpected relationships)
5. Information flow implications (how might info spread through this network?)

Provide plain-language insights a non-expert can understand.
Reference specific nodes by name when discussing patterns.""",

    "timeline": """You are a junior investigative analyst helping interpret event timelines.
Your role is to spot temporal patterns that might indicate coordination, causation, or gaps.

For the current timeline view, analyze:
1. Activity clusters (what periods had concentrated activity?)
2. Suspicious gaps (what periods are unexpectedly quiet?)
3. Sequences suggesting coordination (events too close to be coincidence)
4. Before/after patterns (what changed around key events?)
5. Temporal anomalies (dates that seem incorrect or inconsistent)

Highlight patterns an expert investigator would notice.
Reference specific dates and events when discussing findings.""",

    "ach": """You are a junior intelligence analyst assisting with Analysis of
Competing Hypotheses (ACH). Your role is to help the analyst review their matrix.

Analyze the current matrix state:
1. Evidence quality - are key items strong discriminators between hypotheses?
2. Hypothesis comparison - which are most/least supported and why?
3. Diagnostic value - which evidence most effectively distinguishes hypotheses?
4. Rating anomalies - any unusual or inconsistent rating patterns?
5. Evidence gaps - what critical evidence is missing?
6. Confidence assessment - how confident should the analyst be in the leading hypothesis?

Keep response concise (2-3 paragraphs). Use specific hypothesis/evidence references.""",

    "anomalies": """You are a data quality analyst helping interpret anomalies.
Your role is to explain what makes items unusual and suggest interpretations.

For the anomalies displayed:
1. Pattern recognition - are anomalies clustered by type? What does that suggest?
2. Contextual analysis - given the anomaly types, what are likely explanations?
3. Risk assessment - how concerning are these? Critical vs informational?
4. Next steps - should items be confirmed, dismissed, or investigated further?

For each major anomaly type present, explain typical causes and suggest follow-up.""",

    "contradictions": """You are an investigative analyst helping interpret
contradictions in evidence. Your role is to explain conflicts and suggest resolutions.

Analyze the contradictions:
1. Conflict types - which types dominate? What does that pattern suggest?
2. Severity assessment - which conflicts have serious implications if unresolved?
3. Chain analysis - if contradictions are related, what's the root cause?
4. Resolution approaches - which should be prioritized? What evidence would help?

Use plain language and reference specific contradiction types and severities.""",

    "patterns": """You are a pattern analyst helping interpret detected patterns.
Your role is to explain significance and contextualize findings.

For the patterns displayed:
1. Pattern significance - which are most important and why?
2. Coverage assessment - how comprehensively are patterns represented?
3. Relationships - do patterns cluster or relate to each other?
4. False positives - which might be noise vs genuine patterns?
5. Recommendations - which patterns warrant deeper investigation?

Focus on 2-3 key patterns with specific examples.""",

    "entities": """You are a junior analyst helping understand entity significance.
Your role is to summarize an entity's importance across the document corpus.

Analyze:
1. Overall significance - what role does this entity play?
2. Key relationships - who/what are they connected to?
3. Mention patterns - concentrated in certain documents or spread widely?
4. Reliability - how confident are we in entity identification?
5. Gaps - what related entities might be missing?""",

    "claims": """You are a fact-checking analyst helping assess claim plausibility.
Your role is to evaluate claims based on available evidence.

Assess:
1. Overall plausibility - given evidence, how likely is the claim true?
2. Evidence strength - what supports or refutes the claim?
3. Contradictions - does this conflict with other claims?
4. Missing evidence - what would strengthen or weaken the claim?
5. Credibility rating - HIGH/MEDIUM/LOW with reasoning.""",

    "credibility": """You are a credibility analyst explaining source assessments.
Your role is to make credibility ratings understandable to non-experts.

Explain:
1. The overall credibility score and what it means
2. Most important contributing factors
3. Any deception risk indicators (if applicable)
4. What would improve the credibility rating
5. Actionable recommendations for the analyst""",

    "provenance": """You are a provenance analyst explaining data lineage.
Your role is to trace information chains and assess reliability at each step.

Trace:
1. Information chain from source to current artifact
2. Critical transformation steps
3. Reliability assessment at each step
4. Single points of failure in the chain
5. Recommended verification steps""",

    "documents": """You are a document analyst helping summarize document significance.
Your role is to provide quick document summaries and identify key themes.

Summarize:
1. Main topics and themes in the document
2. Key entities mentioned
3. Important claims or assertions
4. Notable dates or events referenced
5. Suggested follow-up actions""",
}


class AIJuniorAnalystService:
    """
    Shared service for AI Junior Analyst features across all shards.

    Provides:
    - Shard-specific system prompts
    - Conversation history management
    - Streaming analysis responses
    - Consistent response formatting
    - Event publishing for audit trail
    """

    def __init__(self, llm_service, event_bus=None, cache_enabled: bool = True):
        """
        Initialize the AI Junior Analyst service.

        Args:
            llm_service: The frame's LLM service instance
            event_bus: Optional event bus for publishing audit events
            cache_enabled: Whether to enable response caching
        """
        self._llm = llm_service
        self._event_bus = event_bus
        self._custom_prompts: Dict[str, str] = {}
        self._sessions: Dict[str, List[Message]] = {}
        self._analysis_count = 0
        self._total_tokens = 0
        self._cache_enabled = cache_enabled
        self._cache = ResponseCache(max_size=100, ttl_seconds=300)
        self._cache_hits = 0
        self._cache_misses = 0

    def set_event_bus(self, event_bus) -> None:
        """Set the event bus for publishing audit events."""
        self._event_bus = event_bus
        logger.debug("Event bus connected to AI Analyst service")

    async def _emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit an event to the event bus if available."""
        if self._event_bus:
            try:
                await self._event_bus.emit(
                    event_type=event_type,
                    payload=payload,
                    source="ai-analyst",
                )
            except Exception as e:
                logger.warning(f"Failed to emit event {event_type}: {e}")

    def register_shard_prompt(self, shard: str, system_prompt: str) -> None:
        """
        Register a custom system prompt for a shard.

        This allows shards to override the default prompts with custom ones.

        Args:
            shard: The shard name (e.g., "graph", "timeline")
            system_prompt: The system prompt to use for this shard
        """
        self._custom_prompts[shard] = system_prompt
        logger.info(f"Registered custom prompt for shard: {shard}")

    def get_shard_prompt(self, shard: str) -> str:
        """
        Get the system prompt for a shard.

        Priority: custom registered > built-in > default

        Args:
            shard: The shard name

        Returns:
            The system prompt to use
        """
        if shard in self._custom_prompts:
            return self._custom_prompts[shard]
        return SHARD_PROMPTS.get(shard, DEFAULT_SYSTEM_PROMPT)

    def list_registered_shards(self) -> List[str]:
        """Get list of shards with registered prompts."""
        all_shards = set(SHARD_PROMPTS.keys()) | set(self._custom_prompts.keys())
        return sorted(all_shards)

    def _format_context(self, request: AnalysisRequest) -> str:
        """
        Format the context data into a prompt-friendly string.

        Args:
            request: The analysis request

        Returns:
            Formatted context string
        """
        context = request.context
        parts = []

        # Format based on what's in the context
        if "selected_item" in context:
            item = context["selected_item"]
            parts.append(f"**Selected Item:**\n{json.dumps(item, indent=2, default=str)}")

        if "related_items" in context:
            items = context["related_items"]
            parts.append(f"**Related Items ({len(items)} total):**")
            # Limit to first 20 for context window management
            for item in items[:20]:
                parts.append(f"- {json.dumps(item, default=str)}")
            if len(items) > 20:
                parts.append(f"... and {len(items) - 20} more")

        if "statistics" in context:
            stats = context["statistics"]
            parts.append(f"**Statistics:**\n{json.dumps(stats, indent=2, default=str)}")

        if "filters_applied" in context:
            filters = context["filters_applied"]
            parts.append(f"**Filters Applied:**\n{json.dumps(filters, indent=2, default=str)}")

        if "metadata" in context:
            meta = context["metadata"]
            parts.append(f"**Metadata:**\n{json.dumps(meta, indent=2, default=str)}")

        # Add any remaining keys not explicitly handled
        handled_keys = {"selected_item", "related_items", "statistics", "filters_applied", "metadata"}
        for key, value in context.items():
            if key not in handled_keys:
                parts.append(f"**{key}:**\n{json.dumps(value, indent=2, default=str)}")

        return "\n\n".join(parts) if parts else "No context data provided."

    def _build_messages(
        self,
        request: AnalysisRequest,
        system_prompt: str
    ) -> List[Dict[str, str]]:
        """
        Build the messages array for the LLM call.

        Args:
            request: The analysis request
            system_prompt: The system prompt to use

        Returns:
            List of message dictionaries for the LLM
        """
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history if present
        if request.conversation_history:
            for msg in request.conversation_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # Build the current user message
        if request.message:
            # This is a follow-up question
            user_content = request.message
        else:
            # This is an initial analysis request
            context_str = self._format_context(request)
            depth_instruction = (
                "Provide a quick, focused analysis."
                if request.depth == AnalysisDepth.QUICK
                else "Provide a detailed, comprehensive analysis."
            )

            user_content = f"""Please analyze the following data from the {request.shard} view.

{context_str}

{depth_instruction}

Provide your analysis with:
1. A clear summary of what you observe
2. Key findings or patterns
3. Recommendations for next steps"""

        messages.append({"role": "user", "content": user_content})

        return messages

    async def analyze(
        self,
        request: AnalysisRequest,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        use_cache: bool = True
    ) -> AnalysisResponse:
        """
        Perform non-streaming analysis.

        Args:
            request: The analysis request
            temperature: LLM temperature (default 0.7)
            max_tokens: Maximum tokens in response
            use_cache: Whether to use cached responses (default True)

        Returns:
            Complete analysis response
        """
        start_time = time.time()

        # Generate or use existing session ID
        session_id = request.session_id or str(uuid.uuid4())
        is_followup = bool(request.message)

        # Check cache for initial requests only (not follow-ups)
        if use_cache and self._cache_enabled and not is_followup:
            cached = self._cache.get(
                request.shard, request.target_id, request.context, request.depth.value
            )
            if cached:
                self._cache_hits += 1
                logger.debug(f"Cache hit for {request.shard}:{request.target_id}")
                return AnalysisResponse(
                    session_id=session_id,
                    analysis=cached,
                    model_used="cached",
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )
            self._cache_misses += 1

        # Emit analysis started event
        await self._emit_event(
            "ai.analysis.started",
            {
                "session_id": session_id,
                "shard": request.shard,
                "target_id": request.target_id,
                "depth": request.depth.value,
                "is_followup": is_followup,
            }
        )

        # Get system prompt and build messages
        system_prompt = self.get_shard_prompt(request.shard)
        messages = self._build_messages(request, system_prompt)

        try:
            # Call LLM
            response = await self._llm.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            processing_time = int((time.time() - start_time) * 1000)
            self._analysis_count += 1

            # Emit analysis completed event
            await self._emit_event(
                "ai.analysis.completed",
                {
                    "session_id": session_id,
                    "shard": request.shard,
                    "target_id": request.target_id,
                    "processing_time_ms": processing_time,
                    "model_used": response.model,
                    "is_followup": is_followup,
                }
            )

            # Cache the response for initial requests
            if self._cache_enabled and not is_followup:
                self._cache.set(
                    request.shard, request.target_id, request.context,
                    request.depth.value, response.text
                )

            return AnalysisResponse(
                session_id=session_id,
                analysis=response.text,
                model_used=response.model,
                processing_time_ms=processing_time,
            )
        except Exception as e:
            # Emit analysis failed event
            await self._emit_event(
                "ai.analysis.failed",
                {
                    "session_id": session_id,
                    "shard": request.shard,
                    "target_id": request.target_id,
                    "error": str(e),
                }
            )
            raise

    async def stream_analyze(
        self,
        request: AnalysisRequest,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Stream analysis response.

        Args:
            request: The analysis request
            temperature: LLM temperature (default 0.7)
            max_tokens: Maximum tokens in response

        Yields:
            Text chunks as they're generated
        """
        import time
        start_time = time.time()

        # Generate or use existing session ID
        session_id = request.session_id or str(uuid.uuid4())
        is_followup = bool(request.message)

        # Emit analysis started event
        await self._emit_event(
            "ai.analysis.started",
            {
                "session_id": session_id,
                "shard": request.shard,
                "target_id": request.target_id,
                "depth": request.depth.value,
                "is_followup": is_followup,
                "streaming": True,
            }
        )

        # Yield session ID first (as JSON line for parsing)
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        # Get system prompt and build messages
        system_prompt = self.get_shard_prompt(request.shard)
        messages = self._build_messages(request, system_prompt)

        try:
            # Stream from LLM
            async for chunk in self._llm.stream_chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                if chunk.text:
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk.text})}\n\n"

                if chunk.is_final:
                    processing_time = int((time.time() - start_time) * 1000)
                    self._analysis_count += 1

                    # Emit analysis completed event
                    await self._emit_event(
                        "ai.analysis.completed",
                        {
                            "session_id": session_id,
                            "shard": request.shard,
                            "target_id": request.target_id,
                            "processing_time_ms": processing_time,
                            "is_followup": is_followup,
                            "streaming": True,
                        }
                    )

                    yield f"data: {json.dumps({'type': 'done', 'finish_reason': chunk.finish_reason})}\n\n"
        except Exception as e:
            # Emit analysis failed event
            await self._emit_event(
                "ai.analysis.failed",
                {
                    "session_id": session_id,
                    "shard": request.shard,
                    "target_id": request.target_id,
                    "error": str(e),
                    "streaming": True,
                }
            )
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    def is_available(self) -> bool:
        """Check if the AI Analyst service is available (LLM is connected)."""
        return self._llm.is_available() if self._llm else False

    async def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        cache_stats = self._cache.stats()
        total_cache_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0

        return {
            "available": self.is_available(),
            "registered_shards": self.list_registered_shards(),
            "custom_prompts_count": len(self._custom_prompts),
            "active_sessions": len(self._sessions),
            "total_analyses": self._analysis_count,
            "event_bus_connected": self._event_bus is not None,
            "cache": {
                "enabled": self._cache_enabled,
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "hit_rate_pct": round(hit_rate, 1),
                **cache_stats,
            },
        }

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("AI Analyst cache cleared")
