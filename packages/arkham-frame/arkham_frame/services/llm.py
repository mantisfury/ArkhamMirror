"""
LLMService - OpenAI-compatible LLM abstraction.
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


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


class LLMService:
    """
    OpenAI-compatible LLM service.
    """

    def __init__(self, config):
        self.config = config
        self._client = None
        self._available = False

    async def initialize(self) -> None:
        """Initialize LLM connection."""
        import httpx

        self._client = httpx.AsyncClient(
            base_url=self.config.llm_endpoint,
            timeout=120,
        )

        # Test connection
        try:
            response = await self._client.get("/models")
            if response.status_code == 200:
                self._available = True
                logger.info(f"LLM connected: {self.config.llm_endpoint}")
            else:
                self._available = False
                logger.warning(f"LLM returned {response.status_code}")
        except Exception as e:
            self._available = False
            logger.warning(f"LLM connection failed: {e}")

    async def shutdown(self) -> None:
        """Close LLM connection."""
        if self._client:
            await self._client.aclose()
        self._available = False
        logger.info("LLM connection closed")

    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._available

    def get_endpoint(self) -> str:
        """Get LLM endpoint URL."""
        return self.config.llm_endpoint

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send chat completion request."""
        if not self._available:
            raise LLMUnavailableError("LLM not available")

        model = self.config.get("llm.model", "local-model")

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            response = await self._client.post("/chat/completions", json=payload)
            if response.status_code != 200:
                raise LLMRequestError(f"LLM request failed: {response.text}")

            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            if isinstance(e, (LLMUnavailableError, LLMRequestError)):
                raise
            raise LLMRequestError(f"LLM request failed: {e}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate text completion with optional system prompt.

        This is a convenience wrapper around chat() that handles the
        message formatting for simpler use cases.

        Args:
            prompt: The user prompt/query
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Dict with 'text' key containing the response
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        text = await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return {
            "text": text,
            "model": self.config.get("llm.model", "local-model"),
        }
