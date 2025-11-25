import base64
import os
import logging
import requests
# import json # Removed

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LM Studio Configuration
# User provided: http://172.17.144.1:1234
# We append /v1/chat/completions for the standard chat endpoint
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_URL", "http://172.17.144.1:1234/v1")
CHAT_ENDPOINT = f"{LM_STUDIO_BASE_URL}/chat/completions"
MODEL_ID = "qwen/qwen3-vl-8b"


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

        response = requests.post(CHAT_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        return result["choices"][0]["message"]["content"]

    except Exception as e:
        logger.error(f"LLM Transcription failed: {e}")
        return None


def describe_image(image_path):
    """
    Asks the LLM to describe the image for semantic search.
    """
    prompt = "Describe this image in detail. List any visible text, objects, and the general setting."
    return transcribe_image(image_path, prompt=prompt)
