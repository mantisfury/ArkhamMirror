import base64
import logging
import requests
import json
import hashlib
from typing import List, Dict, Any, Optional
from redis import Redis

from config.settings import LM_STUDIO_URL, REDIS_URL

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Redis for caching
redis_client = None
if REDIS_URL:
    try:
        redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning(f"Failed to connect to Redis for caching: {e}")

# LM Studio Configuration from central config
LM_STUDIO_BASE_URL = LM_STUDIO_URL
if not LM_STUDIO_BASE_URL.endswith("/v1"):
    LM_STUDIO_BASE_URL = f"{LM_STUDIO_BASE_URL}/v1"
CHAT_ENDPOINT = f"{LM_STUDIO_BASE_URL}/chat/completions"
MODEL_ID = "qwen/qwen3-vl-8b"

logger.info(f"LM Studio configured: {LM_STUDIO_BASE_URL}")


def encode_image(image_path):
    """Encodes a local image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def transcribe_image(
    image_path,
    prompt="Transcribe the text in this image exactly as it appears. Maintain the layout structure. Do not summarize. Output in Markdown format.",
):
    """
    Sends an image to the local LLM (Qwen-VL via LM Studio) for transcription using raw HTTP requests.
    No OpenAI SDK involved.

    Returns:
        Transcribed text on success, None on failure (LM Studio not running, timeout, etc.)
    """
    try:
        base64_image = encode_image(image_path)

        payload = {
            "model": MODEL_ID,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a robotic OCR engine. Your ONLY job is to transcribe text from the image exactly as it appears. Do not correct typos. Do not summarize. Do not add commentary. If a word is illegible, write [illegible].",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                },
            ],
            "temperature": 0.0,
            "max_tokens": 2048,
            "stream": False,
        }

        headers = {"Content-Type": "application/json"}

        response = requests.post(
            CHAT_ENDPOINT, headers=headers, json=payload, timeout=180
        )
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]

    except requests.exceptions.ConnectionError:
        logger.warning(
            "LLM Transcription failed: LM Studio not running. Falling back to PaddleOCR if available."
        )
        return None
    except requests.exceptions.Timeout:
        logger.warning(
            "LLM Transcription failed: Request timed out. The image may be too large or complex."
        )
        return None
    except Exception as e:
        logger.error(f"LLM Transcription failed: {e}")
        return None


def describe_image(image_path):
    """
    Asks the LLM to describe the image for semantic search.
    """
    prompt = "Describe this image in detail. List any visible text, objects, and the general setting."
    return transcribe_image(image_path, prompt=prompt)


def chat_with_llm(
    messages,
    temperature=0.3,
    max_tokens=1000,
    json_mode=False,
    json_schema=None,
    use_cache=True,
):
    """
    Chat with the LLM.

    Args:
        messages: Either a string prompt OR a list of message dicts [{"role": "user", "content": "..."}]
        temperature: Creativity (0.0 - 1.0)
        max_tokens: Max response length
        json_mode: If True with no schema, relies on prompt engineering for JSON output
        json_schema: Dict containing JSON schema to enforce structured output.
                     Example: {"name": "my_schema", "schema": {"type": "object", "properties": {...}}}
        use_cache: Whether to use Redis caching (default True)

    Returns:
        String response content
    """
    try:
        # Handle both string prompts and message arrays
        if isinstance(messages, str):
            # Convert string prompt to proper message format
            messages = [{"role": "user", "content": messages}]

        payload = {
            "model": MODEL_ID,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        # LM Studio Structured Output:
        # Use "json_schema" type with an actual schema for enforced structure
        # See: https://lmstudio.ai/docs/advanced/structured-output
        if json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }
        # Note: LM Studio doesn't support "json_object" type.
        # When json_mode=True but no schema, we rely on prompt engineering
        # (the prompts already ask for JSON output explicitly)

        # Check cache
        cache_key = ""
        if use_cache and redis_client:
            try:
                # Create deterministic hash of the payload
                payload_str = json.dumps(payload, sort_keys=True)
                cache_key = (
                    f"llm_cache:{hashlib.md5(payload_str.encode('utf-8')).hexdigest()}"
                )
                cached_response = redis_client.get(cache_key)
                if cached_response:
                    logger.info("Returning cached LLM response")
                    return cached_response
            except Exception as e:
                logger.warning(f"Cache check failed: {e}")

        headers = {"Content-Type": "application/json"}

        response = requests.post(
            CHAT_ENDPOINT, headers=headers, json=payload, timeout=120
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # Save to cache
        if use_cache and redis_client and cache_key and content:
            try:
                # Cache for 24 hours
                redis_client.setex(cache_key, 86400, content)
            except Exception as e:
                logger.warning(f"Cache save failed: {e}")

        return content

    except requests.exceptions.ConnectionError:
        # LM Studio not running or not reachable
        logger.warning("LM Studio not available - connection refused")
        return (
            "[LM Studio not running]\n\n"
            "To use AI features, please:\n"
            "1. Start LM Studio (https://lmstudio.ai)\n"
            "2. Load a model (e.g., Qwen3-VL-8B)\n"
            "3. Start the local server (port 1234)\n\n"
            "The rest of ArkhamMirror works without LM Studio."
        )
    except requests.exceptions.Timeout:
        logger.warning("LM Studio request timed out")
        return (
            "[LM Studio timeout]\n\n"
            "The AI request took too long. This could mean:\n"
            "• The model is still loading\n"
            "• The request was too complex\n"
            "• LM Studio is overloaded\n\n"
            "Try again in a moment, or use a smaller/faster model."
        )
    except requests.exceptions.HTTPError as http_err:
        # Log more details for debugging
        logger.error(f"LLM Chat HTTP error: {http_err}")
        if hasattr(http_err, "response") and http_err.response is not None:
            logger.error(f"Response body: {http_err.response.text[:500]}")
        return f"Error: {str(http_err)}"
    except Exception as e:
        logger.error(f"LLM Chat failed: {e}")
        return f"Error: {str(e)}"


# Pre-defined schemas for common use cases
SPECULATION_SCENARIOS_SCHEMA = {
    "name": "speculation_scenarios",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "scenarios": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "hypothesis": {"type": "string"},
                        "basis": {"type": "string"},
                        "evidence_needed": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "significance": {"type": "string"},
                        "significance_explanation": {"type": "string"},
                        "investigation_steps": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["id", "hypothesis", "basis", "significance"],
                },
            }
        },
        "required": ["scenarios"],
    },
}

GAPS_SCHEMA = {
    "name": "investigation_gaps",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "gaps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "importance": {"type": "string"},
                        "indicators": {"type": "array", "items": {"type": "string"}},
                        "suggested_sources": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["id", "type", "description", "importance"],
                },
            }
        },
        "required": ["gaps"],
    },
}

QUESTIONS_SCHEMA = {
    "name": "investigation_questions",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "question": {"type": "string"},
                        "priority": {"type": "string"},
                        "rationale": {"type": "string"},
                        "related_entities": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "potential_sources": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["id", "question", "priority", "rationale"],
                },
            }
        },
        "required": ["questions"],
    },
}

# Narrative reconstruction schema
NARRATIVE_SCHEMA = {
    "name": "narrative_reconstruction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "narrative": {"type": "string"},
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string"},
                        "date": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                    "required": ["event"],
                },
            },
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "entity": {"type": "string"},
                        "relationship": {"type": "string"},
                        "nature": {"type": "string"},
                    },
                    "required": ["entity", "relationship"],
                },
            },
            "gaps": {"type": "array", "items": {"type": "string"}},
            "overall_confidence": {"type": "string"},
        },
        "required": ["narrative", "events", "overall_confidence"],
    },
}

# Motive inference schema
MOTIVE_SCHEMA = {
    "name": "motive_inference",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "hypotheses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hypothesis": {"type": "string"},
                        "supporting_evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "contradicting_evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "confidence": {"type": "string"},
                        "verification_needed": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["hypothesis", "confidence"],
                },
            },
            "behavioral_patterns": {"type": "array", "items": {"type": "string"}},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
            "speculation_warning": {"type": "string"},
        },
        "required": ["hypotheses"],
    },
}

# Investigation brief schema
INVESTIGATION_BRIEF_SCHEMA = {
    "name": "investigation_brief",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "subjects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "profile": {"type": "string"},
                        "risk_level": {"type": "string"},
                    },
                    "required": ["name", "profile"],
                },
            },
            "connections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from": {"type": "string"},
                        "to": {"type": "string"},
                        "nature": {"type": "string"},
                    },
                    "required": ["from", "to", "nature"],
                },
            },
            "key_events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string"},
                        "date": {"type": "string"},
                        "significance": {"type": "string"},
                    },
                    "required": ["event", "date"],
                },
            },
            "evidence_strength": {"type": "string"},
            "hypotheses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hypothesis": {"type": "string"},
                        "confidence": {"type": "string"},
                        "supporting_evidence": {"type": "string"},
                    },
                    "required": ["hypothesis", "confidence"],
                },
            },
            "priority_actions": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "title",
            "subjects",
            "connections",
            "key_events",
            "evidence_strength",
            "hypotheses",
            "priority_actions",
            "risks",
        ],
    },
}

# Timeline events schema
TIMELINE_EVENTS_SCHEMA = {
    "name": "timeline_events",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "event": {"type": "string"},
                        "source": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                    "required": ["date", "event"],
                },
            }
        },
        "required": ["events"],
    },
}

# Facts extraction schema
FACTS_SCHEMA = {
    "name": "extracted_facts",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "doc_id": {"type": "integer"},
                        "chunk_id": {"type": "integer"},
                        "confidence": {"type": "string"},
                        "category": {"type": "string"},
                    },
                    "required": ["claim", "confidence"],
                },
            }
        },
        "required": ["facts"],
    },
}

# Fact comparison schema
FACT_COMPARISON_SCHEMA = {
    "name": "fact_comparison",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "corroborating": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "facts": {"type": "array", "items": {"type": "integer"}},
                        "explanation": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                    "required": ["facts", "explanation"],
                },
            },
            "conflicting": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "facts": {"type": "array", "items": {"type": "integer"}},
                        "explanation": {"type": "string"},
                        "severity": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                    "required": ["facts", "explanation"],
                },
            },
            "unique": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["corroborating", "conflicting", "unique"],
    },
}

# Contradictions schema
CONTRADICTIONS_SCHEMA = {
    "name": "contradictions",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "contradictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_a": {"type": "string"},
                        "source_a": {"type": "string"},
                        "claim_b": {"type": "string"},
                        "source_b": {"type": "string"},
                        "nature": {"type": "string"},
                        "severity": {"type": "string"},
                        "explanation": {"type": "string"},
                        "category": {
                            "type": "string"
                        },  # Phase 3: timeline, financial, factual, identity, attribution
                        "confidence": {"type": "number"},  # Phase 3: 0.0-1.0
                        # NEW: List of all entity names involved in this contradiction
                        "involved_entities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "All entity names involved in this contradiction (e.g. both the person who made claim_a and claim_b)",
                        },
                    },
                    "required": ["claim_a", "claim_b", "severity"],
                },
            }
        },
        "required": ["contradictions"],
    },
}

# Big picture / executive summary schema
BIG_PICTURE_SCHEMA = {
    "name": "executive_summary",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "executive_summary": {"type": "string"},
            "key_themes": {"type": "array", "items": {"type": "string"}},
            "central_figures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "significance": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            "network_insights": {"type": "string"},
            "timeline_patterns": {"type": "string"},
            "red_flags": {"type": "array", "items": {"type": "string"}},
            "information_gaps": {"type": "array", "items": {"type": "string"}},
            "focus_areas": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["executive_summary"],
    },
}

# Power structure schema
POWER_STRUCTURE_SCHEMA = {
    "name": "power_structure",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "power_centers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "entity": {"type": "string"},
                        "power_type": {"type": "string"},
                        "influence_spheres": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "evidence": {"type": "string"},
                    },
                    "required": ["entity", "power_type"],
                },
            },
            "hierarchies": {"type": "array", "items": {"type": "string"}},
            "conflicts": {"type": "array", "items": {"type": "string"}},
            "alliances": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["power_centers"],
    },
}

# LLM events array schema (timeline_service uses array format)
LLM_EVENTS_ARRAY_SCHEMA = {
    "name": "llm_events_array",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "date": {"type": "string"},
                        "event_type": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["description", "date"],
                },
            }
        },
        "required": ["events"],
    },
}


def extract_tables_from_image(image_path: str) -> List[Dict[str, Any]]:
    """
    Asks the LLM to extract tables from the image in structured JSON format.
    Returns a list of dicts: {'headers': [...], 'rows': [[...], ...]}
    """
    prompt = """
    Extract all tables from this image.
    For each table, identify the headers and the row data.
    
    Output structured JSON ONLY:
    {
      "tables": [
        {
          "headers": ["Col1", "Col2", ...],
          "rows": [
            ["Row1Col1", "Row1Col2", ...],
            ["Row2Col1", "Row2Col2", ...]
          ]
        }
      ]
    }
    """

    response = transcribe_image(image_path, prompt=prompt)
    if not response:
        return []

    try:
        # Clean up markdown code blocks if present
        cleaned = response
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            parts = cleaned.split("```")
            if len(parts) > 1:
                cleaned = parts[1]

        # Parse JSON
        data = json.loads(cleaned)
        return data.get("tables", [])
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Failed to parse table extraction JSON: {e}")
        # logger.debug(f"Raw response: {response}")
        return []
