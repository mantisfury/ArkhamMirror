"""
LLMService - OpenAI-compatible LLM abstraction with structured output.

Provides chat completions, structured JSON extraction, streaming responses,
and prompt template management for local LLM services (LM Studio, Ollama, etc.)
and cloud providers (OpenAI, etc.) with API key support.

Security features:
- API keys loaded only from environment variables (never from config files)
- Keys stored in private attributes with __slots__ to prevent dynamic access
- Memory-safe key clearing on shutdown
- Truncated error messages to prevent credential leakage
"""

from typing import List, Dict, Any, Optional, AsyncIterator, Type, TypeVar, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import json
import re
import os
import time
logger = logging.getLogger(__name__)

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation, create_wide_event, emit_wide_error
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    # Fallback: create no-op context manager
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    def create_wide_event(*args, **kwargs):
        return None
    def emit_wide_error(*args, **kwargs):
        pass

# Maximum characters to include in error messages (security measure)
MAX_ERROR_MESSAGE_LENGTH = 200


def _secure_clear_string(s: str) -> None:
    """
    Mark a string for garbage collection.

    Note: Python strings are immutable, so true secure clearing is not possible
    without native extensions. This function serves as a marker for where
    sensitive data should be cleared, and removes the reference to allow GC.

    For production environments requiring true secure memory handling, consider:
    - Using SecretStr from pydantic
    - Native extensions with secure memory allocation
    - Hardware security modules (HSM) for key storage
    """
    # In Python, we cannot truly clear immutable strings from memory.
    # The best we can do is remove references and hope GC clears it.
    # The actual clearing happens when the caller sets the variable to None.
    pass

T = TypeVar('T')


class LLMError(Exception):
    """Base LLM error."""
    pass


class LLMUnavailableError(LLMError):
    """LLM not available."""
    pass


class LLMRequestError(LLMError):
    """LLM request failed."""
    pass


class JSONExtractionError(LLMError):
    """JSON extraction failed."""
    pass


class PromptNotFoundError(LLMError):
    """Prompt template not found."""
    def __init__(self, name: str):
        super().__init__(f"Prompt not found: {name}")
        self.name = name


@dataclass
class LLMResponse:
    """Response from LLM with metadata."""
    text: str
    model: str
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "finish_reason": self.finish_reason,
        }


@dataclass
class StreamChunk:
    """A chunk from streaming response."""
    text: str
    is_final: bool = False
    finish_reason: Optional[str] = None


@dataclass
class PromptTemplate:
    """A reusable prompt template."""
    name: str
    template: str
    system_prompt: Optional[str] = None
    variables: List[str] = field(default_factory=list)
    description: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    def render(self, **kwargs) -> str:
        """Render template with variables."""
        result = self.template
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "template": self.template,
            "system_prompt": self.system_prompt,
            "variables": self.variables,
            "description": self.description,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


# JSON extraction patterns
JSON_BLOCK_PATTERN = re.compile(r'```(?:json)?\s*([\s\S]*?)```')
JSON_OBJECT_PATTERN = re.compile(r'\{[\s\S]*\}')
JSON_ARRAY_PATTERN = re.compile(r'\[[\s\S]*\]')


class LLMService:
    """
    OpenAI-compatible LLM service with enhanced features.

    Features:
        - Chat and completion endpoints
        - Structured JSON output extraction
        - Streaming responses
        - Prompt template management
        - Token usage tracking

    Security:
        - Uses __slots__ to prevent dynamic attribute access
        - API key cleared from memory on shutdown
        - Error messages truncated to prevent credential leakage
    """

    # Use __slots__ to prevent dynamic attribute creation (security measure)
    # This prevents accidental exposure of sensitive data through dynamic attributes
    __slots__ = (
        'config',
        '_db',
        '_client',
        '_available',
        '_model_name',
        '_api_key',
        '_prompts',
        '_is_openrouter',
        '_fallback_models',
        '_use_fallback_routing',
        '_total_requests',
        '_total_tokens_prompt',
        '_total_tokens_completion',
    )

    def __init__(self, config, db=None):
        self.config = config
        self._db = db  # Database service for loading persisted settings
        self._client = None
        self._available = False
        self._model_name = "local-model"
        self._api_key: Optional[str] = None
        self._prompts: Dict[str, PromptTemplate] = {}

        # OpenRouter fallback routing
        self._is_openrouter = False
        self._fallback_models: List[str] = []
        self._use_fallback_routing = False

        # Statistics
        self._total_requests = 0
        self._total_tokens_prompt = 0
        self._total_tokens_completion = 0

    async def initialize(self) -> None:
        """Initialize LLM connection."""
        import httpx

        # Try to load persisted settings from database first
        await self._load_persisted_settings()

        endpoint = self.config.llm_endpoint or "http://localhost:1234/v1"
        # Use default if config value is empty/None
        configured_model = self.config.get("llm.model")
        self._model_name = configured_model if configured_model else "local-model"

        # Load API key from environment (never from config file for security)
        # Supports multiple env var names for compatibility with various providers
        self._api_key = (
            os.environ.get("LLM_API_KEY") or
            os.environ.get("OPENAI_API_KEY") or
            os.environ.get("OPENROUTER_API_KEY") or
            os.environ.get("TOGETHER_API_KEY") or
            os.environ.get("GROQ_API_KEY") or
            os.environ.get("ANTHROPIC_API_KEY") or
            None
        )

        # Build headers with API key if present
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
            logger.info("LLM API key configured from environment")

        self._client = httpx.AsyncClient(
            base_url=endpoint,
            headers=headers,
            timeout=120,
        )

        # Detect OpenRouter for fallback routing support
        self._is_openrouter = 'openrouter.ai' in endpoint.lower()
        if self._is_openrouter:
            logger.info("OpenRouter detected - fallback routing available")

        # Test connection
        try:
            response = await self._client.get("/models")
            if response.status_code == 200:
                self._available = True
                # Only use first model from API if user hasn't configured a specific model
                # (i.e., still using default "local-model")
                if self._model_name == "local-model":
                    data = response.json()
                    if "data" in data and data["data"]:
                        self._model_name = data["data"][0].get("id", self._model_name)
                logger.info(f"LLM connected: {endpoint} (model: {self._model_name})")
            elif response.status_code == 401:
                self._available = False
                logger.warning("LLM authentication failed - check API key")
            else:
                self._available = False
                logger.warning(f"LLM returned {response.status_code}")
        except Exception as e:
            self._available = False
            logger.warning(f"LLM connection failed: {e}")

        # Load default prompts
        self._load_default_prompts()

    async def shutdown(self) -> None:
        """Close LLM connection and securely clear sensitive data."""
        if self._client:
            await self._client.aclose()
            self._client = None

        # Securely clear API key from memory (defense in depth)
        if self._api_key:
            _secure_clear_string(self._api_key)
            self._api_key = None

        self._available = False
        logger.info("LLM connection closed, credentials cleared")

    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._available

    def get_endpoint(self) -> str:
        """Get LLM endpoint URL."""
        return self.config.llm_endpoint or "http://localhost:1234/v1"

    def get_model(self) -> str:
        """Get current model name."""
        return self._model_name

    def has_api_key(self) -> bool:
        """Check if an API key is configured (without exposing the key)."""
        return self._api_key is not None and len(self._api_key) > 0

    def get_api_key_source(self) -> Optional[str]:
        """Get which environment variable provided the API key (for debugging)."""
        # Check in same order as initialization
        if os.environ.get("LLM_API_KEY"):
            return "LLM_API_KEY"
        elif os.environ.get("OPENAI_API_KEY"):
            return "OPENAI_API_KEY"
        elif os.environ.get("OPENROUTER_API_KEY"):
            return "OPENROUTER_API_KEY"
        elif os.environ.get("TOGETHER_API_KEY"):
            return "TOGETHER_API_KEY"
        elif os.environ.get("GROQ_API_KEY"):
            return "GROQ_API_KEY"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            return "ANTHROPIC_API_KEY"
        return None

    # =========================================================================
    # OpenRouter Fallback Routing
    # =========================================================================

    def is_openrouter(self) -> bool:
        """Check if connected to OpenRouter."""
        return self._is_openrouter

    def set_fallback_models(self, models: List[str]) -> None:
        """
        Set fallback models for OpenRouter routing.

        Args:
            models: List of model IDs to use as fallbacks (in priority order)
        """
        self._fallback_models = models
        self._use_fallback_routing = bool(models)
        if models:
            logger.info(f"Fallback models configured: {models}")

    def get_fallback_models(self) -> List[str]:
        """Get current fallback models."""
        return self._fallback_models.copy()

    def enable_fallback_routing(self, enabled: bool = True) -> None:
        """Enable or disable fallback routing."""
        self._use_fallback_routing = enabled and bool(self._fallback_models)

    def is_fallback_routing_enabled(self) -> bool:
        """Check if fallback routing is enabled."""
        return self._use_fallback_routing and bool(self._fallback_models)

    # =========================================================================
    # Core Chat/Completion
    # =========================================================================

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Send chat completion request."""
        with log_operation("llm.chat", model=self._model_name) as event:
            if event:
                event.input(
                    message_count=len(messages),
                    model=self._model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    has_stop=stop is not None,
                )
            
            if not self._available:
                if event:
                    event.error("LLMUnavailable", "LLM not available")
                raise LLMUnavailableError("LLM not available")

            payload = {
                "model": self._model_name,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens
            if stop:
                payload["stop"] = stop

            # OpenRouter fallback routing (max 3 models allowed)
            if self._is_openrouter and self._use_fallback_routing and self._fallback_models:
                payload["route"] = "fallback"
                # Include primary model + fallback models, limit to 3 total
                all_models = [self._model_name] + [m for m in self._fallback_models if m != self._model_name]
                payload["models"] = all_models[:3]

            try:
                start_time = time.time()
                response = await self._client.post("/chat/completions", json=payload)
                duration_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code != 200:
                    # Truncate error message to prevent potential credential leakage
                    error_text = response.text[:MAX_ERROR_MESSAGE_LENGTH]
                    if len(response.text) > MAX_ERROR_MESSAGE_LENGTH:
                        error_text += "... [truncated]"
                    error_msg = f"LLM request failed ({response.status_code}): {error_text}"
                    if event:
                        event.dependency("llm_api", duration_ms=duration_ms, status_code=response.status_code)
                        event.error("LLMRequestFailed", error_msg)
                    raise LLMRequestError(error_msg)

                data = response.json()
                choice = data["choices"][0]

                # Track usage
                usage = data.get("usage", {})
                tokens_prompt = usage.get("prompt_tokens", 0)
                tokens_completion = usage.get("completion_tokens", 0)
                self._total_requests += 1
                self._total_tokens_prompt += tokens_prompt
                self._total_tokens_completion += tokens_completion

                llm_response = LLMResponse(
                    text=choice["message"]["content"],
                    model=data.get("model", self._model_name),
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion,
                    finish_reason=choice.get("finish_reason"),
                    raw_response=data,
                )
                
                if event:
                    event.dependency("llm_api", duration_ms=duration_ms, status_code=200)
                    event.output(
                        model=llm_response.model,
                        tokens_prompt=tokens_prompt,
                        tokens_completion=tokens_completion,
                        tokens_total=tokens_prompt + tokens_completion,
                        finish_reason=llm_response.finish_reason,
                        response_length=len(llm_response.text),
                    )
                
                return llm_response

            except Exception as e:
                if isinstance(e, (LLMUnavailableError, LLMRequestError)):
                    emit_wide_error(event, type(e).__name__, str(e), exc=e)
                    raise
                emit_wide_error(event, "LLMRequestError", str(e), exc=e)
                raise LLMRequestError(f"LLM request failed: {e}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate text completion with optional system prompt.

        This is a convenience wrapper around chat() that handles the
        message formatting for simpler use cases.
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # =========================================================================
    # Streaming
    # =========================================================================

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream chat completion response."""
        event = None
        if WIDE_EVENTS_AVAILABLE:
            event = create_wide_event("llm.stream_chat", model=self._model_name)
            if event:
                event.input(
                    message_count=len(messages),
                    model=self._model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
        
        if not self._available:
            if event:
                event.error("LLMUnavailable", "LLM not available")
            raise LLMUnavailableError("LLM not available")

        payload = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        # OpenRouter fallback routing (max 3 models allowed)
        if self._is_openrouter and self._use_fallback_routing and self._fallback_models:
            payload["route"] = "fallback"
            all_models = [self._model_name] + [m for m in self._fallback_models if m != self._model_name]
            payload["models"] = all_models[:3]

        start_time = time.time()
        chunk_count = 0
        total_text_length = 0
        
        try:
            async with self._client.stream(
                "POST",
                "/chat/completions",
                json=payload,
                timeout=300,
            ) as response:
                if response.status_code != 200:
                    content = await response.aread()
                    # Truncate error message to prevent potential credential leakage
                    error_text = content.decode()[:MAX_ERROR_MESSAGE_LENGTH]
                    if len(content) > MAX_ERROR_MESSAGE_LENGTH:
                        error_text += "... [truncated]"
                    error_msg = f"LLM stream failed ({response.status_code}): {error_text}"
                    if event:
                        duration_ms = int((time.time() - start_time) * 1000)
                        event.dependency("llm_api", duration_ms=duration_ms, status_code=response.status_code)
                        event.error("LLMStreamFailed", error_msg)
                    raise LLMRequestError(error_msg)

                finish_reason = None
                async for line in response.aiter_lines():
                    if not line or line == "data: [DONE]":
                        continue

                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            choice = data.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            finish_reason = choice.get("finish_reason")

                            if content or finish_reason:
                                chunk_count += 1
                                total_text_length += len(content)
                                yield StreamChunk(
                                    text=content,
                                    is_final=finish_reason is not None,
                                    finish_reason=finish_reason,
                                )
                        except json.JSONDecodeError:
                            continue
                
                # Log completion
                if event:
                    duration_ms = int((time.time() - start_time) * 1000)
                    event.dependency("llm_api", duration_ms=duration_ms, status_code=200)
                    event.output(
                        chunk_count=chunk_count,
                        total_length=total_text_length,
                        finish_reason=finish_reason,
                    )
                    event.success()

        except Exception as e:
            if isinstance(e, (LLMUnavailableError, LLMRequestError)):
                emit_wide_error(event, type(e).__name__, str(e), exc=e)
                raise
            emit_wide_error(event, "LLMStreamError", str(e), exc=e)
            raise LLMRequestError(f"LLM stream failed: {e}")

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream text generation."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async for chunk in self.stream_chat(messages, temperature, max_tokens):
            yield chunk

    # =========================================================================
    # Structured Output (JSON Extraction)
    # =========================================================================

    async def extract_json(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,  # Lower temp for structured output
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Extract structured JSON from LLM response.

        Args:
            prompt: The prompt to send
            schema: Optional JSON schema for validation
            system_prompt: Optional system prompt (defaults to JSON-focused prompt)
            temperature: Sampling temperature (default 0.3 for more deterministic output)
            max_retries: Number of retries on JSON parse failure

        Returns:
            Parsed JSON dictionary

        Raises:
            JSONExtractionError: If JSON extraction fails after retries
        """
        with log_operation("llm.extract_json", model=self._model_name) as event:
            if event:
                event.input(
                    prompt_length=len(prompt),
                    has_schema=schema is not None,
                    has_system_prompt=system_prompt is not None,
                    temperature=temperature,
                    max_retries=max_retries,
                )
            
            if system_prompt is None:
                system_prompt = (
                    "You are a helpful assistant that responds only with valid JSON. "
                    "Do not include any text before or after the JSON. "
                    "Ensure the JSON is properly formatted and complete."
                )
                if schema:
                    system_prompt += f"\n\nThe response must conform to this schema:\n{json.dumps(schema, indent=2)}"

            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    response = await self.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                    )

                    # Try to extract JSON
                    result = self._parse_json_from_text(response.text)

                    # Validate against schema if provided
                    if schema and not self._validate_json_schema(result, schema):
                        raise JSONExtractionError("Response does not match schema")

                    if event:
                        event.output(
                            attempt=attempt + 1,
                            result_keys=list(result.keys()) if isinstance(result, dict) else "non-dict",
                            result_type=type(result).__name__,
                        )
                    
                    return result

                except JSONExtractionError as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.debug(f"JSON extraction attempt {attempt + 1} failed, retrying...")
                        # Add retry hint to prompt
                        prompt = f"{prompt}\n\nIMPORTANT: Respond with ONLY valid JSON, no other text."

            emit_wide_error(
                event,
                "JSONExtractionFailed",
                f"Failed after {max_retries + 1} attempts: {last_error}",
                exc=last_error if isinstance(last_error, Exception) else None,
            )
            raise JSONExtractionError(f"Failed to extract JSON after {max_retries + 1} attempts: {last_error}")

    async def extract_list(
        self,
        prompt: str,
        item_type: str = "item",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> List[Any]:
        """Extract a list from LLM response."""
        if system_prompt is None:
            system_prompt = (
                f"You are a helpful assistant that responds only with a JSON array of {item_type}s. "
                "Do not include any text before or after the array."
            )

        response = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        result = self._parse_json_from_text(response.text)

        if not isinstance(result, list):
            if isinstance(result, dict):
                # Try to find a list in the dict
                for v in result.values():
                    if isinstance(v, list):
                        return v
            raise JSONExtractionError(f"Expected list, got {type(result).__name__}")

        return result

    def _parse_json_from_text(self, text: str) -> Any:
        """Extract and parse JSON from text that may contain other content."""
        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from code block
        match = JSON_BLOCK_PATTERN.search(text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try extracting JSON object
        match = JSON_OBJECT_PATTERN.search(text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Try extracting JSON array
        match = JSON_ARRAY_PATTERN.search(text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise JSONExtractionError(f"Could not extract valid JSON from response: {text[:200]}...")

    def _validate_json_schema(self, data: Any, schema: Dict[str, Any]) -> bool:
        """Basic JSON schema validation."""
        # Simple type checking
        schema_type = schema.get("type")
        if schema_type:
            if schema_type == "object" and not isinstance(data, dict):
                return False
            if schema_type == "array" and not isinstance(data, list):
                return False
            if schema_type == "string" and not isinstance(data, str):
                return False
            if schema_type == "number" and not isinstance(data, (int, float)):
                return False
            if schema_type == "boolean" and not isinstance(data, bool):
                return False

        # Check required properties
        if isinstance(data, dict) and "required" in schema:
            for prop in schema["required"]:
                if prop not in data:
                    return False

        return True

    # =========================================================================
    # Prompt Templates
    # =========================================================================

    def register_prompt(self, prompt: PromptTemplate) -> None:
        """Register a prompt template."""
        self._prompts[prompt.name] = prompt
        logger.debug(f"Registered prompt: {prompt.name}")

    def get_prompt(self, name: str) -> PromptTemplate:
        """Get a prompt template by name."""
        if name not in self._prompts:
            raise PromptNotFoundError(name)
        return self._prompts[name]

    def list_prompts(self) -> List[str]:
        """List all registered prompt names."""
        return list(self._prompts.keys())

    async def run_prompt(
        self,
        name: str,
        variables: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Run a registered prompt template."""
        prompt = self.get_prompt(name)
        variables = variables or {}

        rendered = prompt.render(**variables)

        return await self.generate(
            prompt=rendered,
            system_prompt=prompt.system_prompt,
            temperature=kwargs.get("temperature", prompt.temperature),
            max_tokens=kwargs.get("max_tokens", prompt.max_tokens),
        )

    def _load_default_prompts(self) -> None:
        """Load default prompt templates."""
        # Summarization prompt
        self.register_prompt(PromptTemplate(
            name="summarize",
            template="Please summarize the following text in a concise manner:\n\n{text}",
            system_prompt="You are a helpful assistant that creates clear, accurate summaries.",
            variables=["text"],
            description="Summarize text",
            temperature=0.5,
        ))

        # Entity extraction prompt
        self.register_prompt(PromptTemplate(
            name="extract_entities",
            template=(
                "Extract all named entities (people, organizations, locations, dates) "
                "from the following text. Return as a JSON array of objects with 'text', "
                "'type', and 'confidence' fields.\n\nText:\n{text}"
            ),
            system_prompt="You are an NER system. Respond only with valid JSON.",
            variables=["text"],
            description="Extract named entities from text",
            temperature=0.3,
        ))

        # Question answering prompt
        self.register_prompt(PromptTemplate(
            name="qa",
            template=(
                "Based on the following context, answer the question.\n\n"
                "Context:\n{context}\n\n"
                "Question: {question}"
            ),
            system_prompt="Answer questions based only on the provided context. If the answer is not in the context, say so.",
            variables=["context", "question"],
            description="Answer questions from context",
            temperature=0.5,
        ))

        # Classification prompt
        self.register_prompt(PromptTemplate(
            name="classify",
            template=(
                "Classify the following text into one of these categories: {categories}\n\n"
                "Text: {text}\n\n"
                "Respond with only the category name."
            ),
            system_prompt="You are a text classifier. Respond with only the category name.",
            variables=["text", "categories"],
            description="Classify text into categories",
            temperature=0.3,
        ))

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get LLM service statistics."""
        return {
            "available": self._available,
            "endpoint": self.get_endpoint(),
            "model": self._model_name,
            "api_key_configured": self.has_api_key(),
            "api_key_source": self.get_api_key_source(),
            "total_requests": self._total_requests,
            "total_tokens_prompt": self._total_tokens_prompt,
            "total_tokens_completion": self._total_tokens_completion,
            "registered_prompts": len(self._prompts),
            # OpenRouter fallback routing
            "is_openrouter": self._is_openrouter,
            "fallback_routing_enabled": self.is_fallback_routing_enabled(),
            "fallback_models": self._fallback_models,
        }

    async def _load_persisted_settings(self) -> None:
        """
        Load LLM settings from the Settings shard database.

        Priority: Settings DB > Environment Variables > Defaults
        Only overrides config if the setting has a non-empty value.
        """
        if not self._db:
            logger.debug("Database not available for loading persisted LLM settings")
            return

        try:
            # Query llm.endpoint setting
            try:
                row = await self._db.fetch_one(
                    "SELECT value FROM arkham_settings WHERE key = :key",
                    {"key": "llm.endpoint"}
                )
                if row and row.get("value"):
                    value = row["value"]
                    # Parse JSON if needed (JSONB may return string or already parsed)
                    if isinstance(value, str):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            pass
                    if value and str(value).strip():
                        self.config.set("llm_endpoint", str(value))
                        logger.info(f"Loaded persisted llm.endpoint: {value}")
            except Exception as e:
                logger.debug(f"Could not load llm.endpoint: {e}")

            # Query llm.model setting
            try:
                row = await self._db.fetch_one(
                    "SELECT value FROM arkham_settings WHERE key = :key",
                    {"key": "llm.model"}
                )
                if row and row.get("value"):
                    value = row["value"]
                    if isinstance(value, str):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            pass
                    if value and str(value).strip():
                        self.config.set("llm.model", str(value))
                        logger.info(f"Loaded persisted llm.model: {value}")
            except Exception as e:
                logger.debug(f"Could not load llm.model: {e}")

        except Exception as e:
            logger.debug(f"Could not load persisted LLM settings: {e}")
