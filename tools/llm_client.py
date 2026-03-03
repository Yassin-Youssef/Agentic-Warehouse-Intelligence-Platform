"""LLM client — thin wrapper around the Anthropic Claude Messages API."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from the project root
load_dotenv()

_API_URL = "https://api.anthropic.com/v1/messages"
_MAX_RETRIES = 2
_RETRY_DELAY = 3  # seconds


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 1500,
) -> str:
    """Send a prompt to the Anthropic Claude API and return the response text.

    Args:
        system_prompt: System-level instruction for the model.
        user_prompt: The user message containing data and questions.
        model: Anthropic model identifier.
        max_tokens: Maximum tokens in the response.

    Returns:
        The model's text response, or a fallback error string on failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your_key_here":
        logger.error("ANTHROPIC_API_KEY not set or still placeholder.")
        return "Analysis unavailable — ANTHROPIC_API_KEY not configured."

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    prompt_len = len(system_prompt) + len(user_prompt)
    last_error: Optional[str] = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(
                "LLM call attempt %d/%d — prompt length: %d chars, model: %s",
                attempt, _MAX_RETRIES, prompt_len, model,
            )
            t0 = time.time()
            resp = requests.post(_API_URL, headers=headers, json=body, timeout=60)
            latency = round(time.time() - t0, 2)

            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"]
                logger.info(
                    "LLM response received — %d chars in %.2fs", len(text), latency,
                )
                return text
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning("LLM call failed (attempt %d): %s", attempt, last_error)
        except Exception as exc:
            last_error = str(exc)
            logger.warning("LLM call exception (attempt %d): %s", attempt, last_error)

        if attempt < _MAX_RETRIES:
            logger.info("Retrying in %ds …", _RETRY_DELAY)
            time.sleep(_RETRY_DELAY)

    logger.error("All LLM retries exhausted. Last error: %s", last_error)
    return "Analysis unavailable — LLM call failed."
