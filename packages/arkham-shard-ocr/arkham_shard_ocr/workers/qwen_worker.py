"""
Qwen-VL OCR Worker - Intelligent VLM-based OCR.

Pool: gpu-qwen
Purpose: Extract text from images using Vision Language Models.

Supports any OpenAI-compatible vision endpoint:
- LM Studio (default): http://localhost:1234/v1
- Ollama: http://localhost:11434/v1
- vLLM: http://localhost:8000/v1
- Any OpenAI-compatible API

Best for: handwritten text, complex layouts, degraded documents.
"""

import base64
import io
import logging
import os
from typing import Any, Dict, Optional

import httpx

from arkham_frame.workers.base import BaseWorker

logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_ENDPOINT = os.environ.get("VLM_ENDPOINT", "http://localhost:1234/v1")
DEFAULT_MODEL = os.environ.get("VLM_MODEL", "qwen2.5-vl-7b-instruct")
DEFAULT_TIMEOUT = float(os.environ.get("VLM_TIMEOUT", "120"))
DEFAULT_API_KEY = os.environ.get("VLM_API_KEY") or os.environ.get("LLM_API_KEY")

# System prompt for OCR mode
OCR_SYSTEM_PROMPT = """You are a robotic OCR engine. Your ONLY job is to transcribe text from the image exactly as it appears.

Rules:
- Transcribe ALL text exactly as shown
- Maintain the original layout structure
- Do NOT correct typos or spelling errors
- Do NOT summarize or paraphrase
- Do NOT add commentary or interpretation
- If a word is illegible, write [illegible]
- If a section is unclear, write [unclear]
- Output in plain text format"""

# Default user prompt
DEFAULT_OCR_PROMPT = "Transcribe all text in this image exactly as it appears. Maintain the layout."


class QwenWorker(BaseWorker):
    """
    Worker for OCR using Vision Language Models (VLMs).

    Uses OpenAI-compatible vision API (works with LM Studio, Ollama, vLLM, etc.)
    Best for handwritten text, complex layouts, or degraded documents.

    Payload formats:
    - Image path: {"image_path": "/path/to/image.png"}
    - Base64: {"image_base64": "...", "filename": "page.png"}
    - Batch: {"images": [{"path": "..."}, {"base64": "..."}], "batch": True}

    Optional params:
    - prompt: Custom OCR prompt (default: transcribe exactly)
    - endpoint: VLM API endpoint (default: LM Studio localhost:1234)
    - model: Model ID to use (default: qwen2.5-vl-7b-instruct)
    - temperature: Sampling temperature (default: 0.1 for OCR)
    - max_tokens: Max response tokens (default: 4096)
    - extract_tables: Also extract tables as structured data (default: False)

    Returns:
    - text: Extracted text
    - model: Model used
    - endpoint: Endpoint used
    - tables: Extracted tables (if extract_tables=True)
    """

    pool = "gpu-qwen"
    name = "QwenWorker"
    job_timeout = 180.0  # VLM can be slow

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client: Optional[httpx.AsyncClient] = None

    def _resolve_path(self, file_path: str) -> str:
        """
        Resolve file path using DATA_SILO_PATH for Docker/portable deployments.

        Args:
            file_path: Path from payload (may be relative or absolute)

        Returns:
            Resolved absolute path as string
        """
        if not os.path.isabs(file_path):
            data_silo = os.environ.get("DATA_SILO_PATH", ".")
            return os.path.join(data_silo, file_path)
        return file_path

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with optional auth."""
        if self._client is None:
            headers = {}
            if DEFAULT_API_KEY:
                headers["Authorization"] = f"Bearer {DEFAULT_API_KEY}"
            self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=headers)
        return self._client

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a VLM OCR job.

        Args:
            job_id: Unique job identifier
            payload: Job data

        Returns:
            Dict with text and metadata
        """
        # Get configuration
        endpoint = payload.get("endpoint", DEFAULT_ENDPOINT)
        model = payload.get("model", DEFAULT_MODEL)
        prompt = payload.get("prompt", DEFAULT_OCR_PROMPT)
        temperature = payload.get("temperature", 0.1)  # Low temp for OCR
        max_tokens = payload.get("max_tokens", 4096)
        extract_tables = payload.get("extract_tables", False)

        # Check if batch mode
        is_batch = payload.get("batch", False)

        if is_batch:
            images = payload.get("images", [])
            if not images:
                raise ValueError("Batch mode requires 'images' field")

            results = []
            for i, img_data in enumerate(images):
                try:
                    result = await self._process_single_image(
                        job_id=job_id,
                        payload=img_data,
                        endpoint=endpoint,
                        model=model,
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        extract_tables=extract_tables,
                        index=i,
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to process image {i}: {e}")
                    results.append({"error": str(e), "success": False})

            return {
                "results": results,
                "count": len(results),
                "success": all(r.get("success", False) for r in results),
                "endpoint": endpoint,
                "model": model,
            }

        else:
            return await self._process_single_image(
                job_id=job_id,
                payload=payload,
                endpoint=endpoint,
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                extract_tables=extract_tables,
            )

    async def _process_single_image(
        self,
        job_id: str,
        payload: Dict[str, Any],
        endpoint: str,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        extract_tables: bool,
        index: int = 0,
    ) -> Dict[str, Any]:
        """
        Process a single image through VLM.

        Args:
            job_id: Job ID
            payload: Image data
            endpoint: API endpoint
            model: Model ID
            prompt: OCR prompt
            temperature: Sampling temperature
            max_tokens: Max tokens
            extract_tables: Extract tables
            index: Image index

        Returns:
            OCR result dict
        """
        # Load and encode image
        # Check image_path first, then path, then file_path (used by JobDispatcher)
        image_path = payload.get("image_path") or payload.get("path") or payload.get("file_path")
        image_base64 = payload.get("image_base64") or payload.get("base64")

        if image_path:
            # Resolve relative path using DATA_SILO_PATH
            resolved_path = self._resolve_path(image_path)
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(f"Image not found: {resolved_path}")

            logger.info(f"Job {job_id}: VLM OCR on file {resolved_path}")
            with open(resolved_path, "rb") as f:
                image_data = f.read()
            image_b64 = base64.b64encode(image_data).decode("utf-8")
            source = resolved_path

            # Detect image type
            if resolved_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif resolved_path.lower().endswith((".jpg", ".jpeg")):
                mime_type = "image/jpeg"
            elif resolved_path.lower().endswith(".gif"):
                mime_type = "image/gif"
            elif resolved_path.lower().endswith(".webp"):
                mime_type = "image/webp"
            else:
                mime_type = "image/png"  # Default

        elif image_base64:
            logger.info(f"Job {job_id}: VLM OCR on base64 image (index {index})")
            image_b64 = image_base64
            source = payload.get("filename", f"base64_image_{index}")
            mime_type = payload.get("mime_type", "image/png")

        else:
            raise ValueError("Must provide 'image_path' or 'image_base64'")

        # Build API request (OpenAI-compatible format)
        api_url = f"{endpoint.rstrip('/')}/chat/completions"

        request_body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": OCR_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_b64}"
                            },
                        },
                    ],
                },
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Make API request
        client = await self._get_client()

        try:
            response = await client.post(api_url, json=request_body)
            response.raise_for_status()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Failed to connect to VLM endpoint: {endpoint}. "
                f"Make sure LM Studio/Ollama/vLLM is running."
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"VLM API error: {e.response.status_code} - {e.response.text}")

        result = response.json()

        # Extract text from response
        text = ""
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            text = message.get("content", "")

        # Optionally extract tables
        tables = []
        if extract_tables and text:
            tables = await self._extract_tables(
                job_id=job_id,
                image_b64=image_b64,
                mime_type=mime_type,
                endpoint=endpoint,
                model=model,
                max_tokens=max_tokens,
            )

        return {
            "text": text,
            "char_count": len(text),
            "source": source,
            "endpoint": endpoint,
            "model": model,
            "tables": tables,
            "success": True,
        }

    async def _extract_tables(
        self,
        job_id: str,
        image_b64: str,
        mime_type: str,
        endpoint: str,
        model: str,
        max_tokens: int,
    ) -> list:
        """
        Extract tables from image using VLM.

        Returns list of tables with headers and rows.
        """
        table_prompt = """Analyze this image for tables. For each table found, extract:
1. Column headers
2. Row data

Return as JSON array:
[
  {
    "headers": ["Col1", "Col2", ...],
    "rows": [["val1", "val2", ...], ...]
  }
]

If no tables found, return: []
Only output the JSON, nothing else."""

        api_url = f"{endpoint.rstrip('/')}/chat/completions"

        request_body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a table extraction engine. Extract tables from images as JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": table_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_b64}"
                            },
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }

        try:
            client = await self._get_client()
            response = await client.post(api_url, json=request_body)
            response.raise_for_status()

            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")

                # Try to parse JSON
                import json
                import re

                # Clean markdown code blocks
                content = re.sub(r"```json?\s*", "", content)
                content = re.sub(r"```\s*$", "", content)
                content = content.strip()

                if content:
                    tables = json.loads(content)
                    if isinstance(tables, list):
                        return tables

        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")

        return []

    async def cleanup(self):
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None


def run_qwen_worker(database_url: str = None, worker_id: str = None):
    """
    Convenience function to run a QwenWorker.

    Environment variables:
    - VLM_ENDPOINT: API endpoint (default: http://localhost:1234/v1)
    - VLM_MODEL: Model ID (default: qwen2.5-vl-7b-instruct)
    - VLM_TIMEOUT: Request timeout in seconds (default: 120)

    Args:
        database_url: PostgreSQL connection URL (defaults to env var)
        worker_id: Optional worker ID (auto-generated if not provided)

    Example:
        # Default (LM Studio)
        python -m arkham_shard_ocr.workers.qwen_worker

        # With Ollama
        VLM_ENDPOINT=http://localhost:11434/v1 VLM_MODEL=llava python -m arkham_shard_ocr.workers.qwen_worker
    """
    import asyncio
    worker = QwenWorker(database_url=database_url, worker_id=worker_id)
    asyncio.run(worker.run())


if __name__ == "__main__":
    run_qwen_worker()
