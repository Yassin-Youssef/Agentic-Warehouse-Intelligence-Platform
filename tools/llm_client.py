# =============================================================================
# LLM CLIENT
# This is the bridge between our agents and the LLM (Claude).
# Instead of calling Anthropic directly, we go through OpenRouter —
# a gateway that forwards our request to Claude and returns the response.
# Same model, same quality, different URL.
# How it works:
#   1. Load the API key from .env file (never hardcoded)
#   2. Build a request with a system prompt (role) and user prompt (data)
#   3. POST it to OpenRouter's endpoint
#   4. Parse the response and return the text
#   5. If it fails, retry up to 2 times with a 3-second delay
#   6. If all retries fail, return a safe fallback string
#
# OpenRouter uses the OpenAI-compatible format:
#   - "messages" array with "role" and "content"
#   - Response at response["choices"][0]["message"]["content"]
# This is different from Anthropic's native format but Claude
# behaves the same way regardless of which door you go through.
# =============================================================================

import logging
import os
import time
import requests  # HTTP library for making API calls
from dotenv import load_dotenv # reads .env file into environment variables
from config.agent_config import DEFAULT_MODEL, MAX_TOKENS

# load .env file — this puts OPENROUTER_API_KEY into os.environ
# so we can access it with os.getenv() below
load_dotenv()

logger = logging.getLogger(__name__)

# load API key once when the module is imported
# this way we don't read .env on every single LLM call
_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# OpenRouter's endpoint — same format as OpenAI's API
_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """Send a prompt to Claude via OpenRouter and return the response text.

    Args:
        system_prompt: tells the LLM what role to play (e.g. "You are a warehouse analyst")
        user_prompt: the actual data and question (e.g. the metrics + "analyze this")
        model: which model to use on OpenRouter (default: Claude Sonnet)
        max_tokens: max length of the response

    Returns:
        The LLM's text response, or a fallback error string if all retries fail.
    """
    # check that we actually have an API key
    if not _API_KEY:
        logger.error("OPENROUTER_API_KEY not found in .env file")
        return "Analysis unavailable — API key not configured."

    # OpenRouter uses Bearer token auth (same as OpenAI)
    headers = {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type": "application/json",
    }

    # the request body follows OpenAI's chat completion format
    # system message = what role the LLM plays
    # user message = the actual data + question
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    # retry logic: try up to 3 times total (1 original + 2 retries)
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            # time the call so we can log latency
            start_time = time.time()
            # send the POST request to OpenRouter, timeout after 60 seconds
            response = requests.post(_BASE_URL, headers=headers, json=body, timeout=60)
            latency = round(time.time() - start_time, 2)

            # check if the request was successful
            if response.status_code != 200:
                logger.warning(
                    "LLM call failed (attempt %d/%d): status %d — %s",
                    attempt + 1, max_retries + 1, response.status_code, response.text[:200],
                )
                if attempt < max_retries:
                    time.sleep(3)  # wait 3 seconds before retrying
                    continue
                return "Analysis unavailable — LLM call failed."

            # parse the response JSON
            # OpenRouter returns: {"choices": [{"message": {"content": "the text"}}]}
            data = response.json()
            text = data["choices"][0]["message"]["content"]

            logger.info(
                "LLM call success — prompt: %d chars, response: %d chars, latency: %.1fs",
                len(system_prompt) + len(user_prompt), len(text), latency,
            )
            return text

        except requests.exceptions.Timeout:
            logger.warning("LLM call timed out (attempt %d/%d)", attempt + 1, max_retries + 1)
            if attempt < max_retries:
                time.sleep(3)
                continue

        except Exception as e:
            logger.error("LLM call error (attempt %d/%d): %s", attempt + 1, max_retries + 1, str(e))
            if attempt < max_retries:
                time.sleep(3)
                continue

    # all retries exhausted
    return "Analysis unavailable — LLM call failed after retries."