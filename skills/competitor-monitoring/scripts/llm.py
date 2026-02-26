#!/usr/bin/env python3
"""Central OpenAI API client for LLM-powered analysis.

Provides a unified interface for all scripts that need LLM reasoning.
Gracefully falls back (returns None) when OPENAI_API_KEY is missing.

Usage:
    import llm
    if llm.is_available():
        result = llm.analyze("Analyze this pricing change", context_text)
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
from dotenv import load_dotenv
load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client = None
_API_KEY = os.environ.get("OPENAI_API_KEY", "")

DEFAULT_MODEL = "gpt-4o"
FAST_MODEL = "gpt-4o-mini"
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubles each retry


def _get_client():
    """Lazy-init the OpenAI client."""
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=_API_KEY)
    return _client


def is_available() -> bool:
    """Check if the OpenAI API key is configured."""
    return bool(_API_KEY) and _API_KEY.startswith("sk-")


# ---------------------------------------------------------------------------
# Core API functions
# ---------------------------------------------------------------------------

def analyze(
    prompt: str,
    context: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> dict | None:
    """Call OpenAI with a prompt and return structured JSON output.

    Args:
        prompt: The analysis instruction (system-level guidance).
        context: The data to analyze (user message).
        model: Model ID to use.
        max_tokens: Max response tokens.
        temperature: Sampling temperature (lower = more focused).

    Returns:
        Parsed dict from the JSON response, or None on failure.
    """
    if not is_available():
        return None

    messages = []
    if context:
        messages.append({"role": "system", "content": prompt})
        messages.append({"role": "user", "content": context})
    else:
        messages.append({"role": "user", "content": prompt})

    for attempt in range(MAX_RETRIES):
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = response.choices[0].message.content

            # Try to extract JSON from the response
            parsed = _extract_json(text)
            if parsed is not None:
                return parsed

            # If no JSON found, return the raw text wrapped in a dict
            return {"raw_response": text}

        except Exception as e:
            error_str = str(e)
            # Retry on rate limits and server errors
            if any(code in error_str for code in ["429", "500", "503"]):
                wait = RETRY_BACKOFF * (2 ** attempt)
                time.sleep(wait)
                continue
            # Don't retry on auth or bad request errors
            print(f"[llm] API error: {e}", flush=True)
            return None

    print("[llm] Max retries exceeded", flush=True)
    return None


def generate(
    prompt: str,
    context: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> str | None:
    """Call OpenAI and return raw text response (not JSON).

    Use this when you want free-form text (summaries, narratives, etc.)
    """
    if not is_available():
        return None

    messages = []
    if context:
        messages.append({"role": "system", "content": prompt})
        messages.append({"role": "user", "content": context})
    else:
        messages.append({"role": "user", "content": prompt})

    for attempt in range(MAX_RETRIES):
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e)
            if any(code in error_str for code in ["429", "500", "503"]):
                wait = RETRY_BACKOFF * (2 ** attempt)
                time.sleep(wait)
                continue
            print(f"[llm] API error: {e}", flush=True)
            return None

    print("[llm] Max retries exceeded", flush=True)
    return None


def summarize(text: str, max_tokens: int = 500) -> str | None:
    """Summarize text into concise bullet points."""
    if not is_available():
        return None

    return generate(
        prompt="Summarize the following into 2-3 concise bullet points. Be specific — include numbers, names, and key facts. No preamble.",
        context=text,
        model=FAST_MODEL,
        max_tokens=max_tokens,
        temperature=0.2,
    )


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | list | None:
    """Extract JSON from the response text.

    Handles: raw JSON, JSON in markdown code blocks, JSON embedded in prose.
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown code block
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    # Try finding JSON object/array in text
    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                pass

    return None


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"LLM available: {is_available()}")
    if is_available():
        result = analyze(
            prompt="You are a JSON bot. Return a JSON object with key 'status' set to 'ok'.",
            context="Test message",
        )
        print(f"Test result: {result}")
    else:
        print("No OPENAI_API_KEY set — LLM features will be disabled.")