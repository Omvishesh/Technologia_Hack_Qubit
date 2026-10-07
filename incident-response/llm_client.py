"""
LLM Client — Shared interface for calling the language model.

Supports Gemini (default) and OpenAI as providers.
All agents use this single client for LLM calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import get_settings

logger = logging.getLogger("incident-response.llm")

# ─────────────────────────────────────────────────────────────
# Lazy-loaded SDK clients
# ─────────────────────────────────────────────────────────────

_gemini_model = None
_openai_client = None


def _get_gemini_model():
    """Lazy-init the Gemini GenerativeModel."""
    global _gemini_model
    if _gemini_model is None:
        import google.generativeai as genai

        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        _gemini_model = genai.GenerativeModel(settings.llm_model)
        logger.info("Gemini model initialized: %s", settings.llm_model)
    return _gemini_model


def _get_openai_client():
    """Lazy-init the OpenAI client."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        settings = get_settings()
        _openai_client = OpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI client initialized: %s", settings.llm_model)
    return _openai_client


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """
    Call the configured LLM provider and return the text response.

    Args:
        system_prompt: The system/role instruction.
        user_prompt: The user's query/input.
        temperature: Sampling temperature (lower = more deterministic).
        max_tokens: Maximum response length.

    Returns:
        The LLM's text response.
    """
    settings = get_settings()

    if settings.llm_provider.lower() == "gemini":
        return await _call_gemini(system_prompt, user_prompt, temperature, max_tokens)
    elif settings.llm_provider.lower() == "openai":
        return await _call_openai(system_prompt, user_prompt, temperature, max_tokens)
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> dict[str, Any] | list[Any]:
    """
    Call the LLM and parse the response as JSON.

    The system prompt should instruct the model to output valid JSON.
    Handles markdown code fences (```json ... ```) in the response.
    """
    raw = await call_llm(system_prompt, user_prompt, temperature, max_tokens)

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON response: %s\nRaw: %s", exc, raw[:500])
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc


# ─────────────────────────────────────────────────────────────
# Provider implementations
# ─────────────────────────────────────────────────────────────

async def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call the Google Gemini API."""
    import asyncio

    model = _get_gemini_model()

    # Gemini uses a combined prompt approach
    full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

    # Gemini SDK is synchronous, run in executor
    def _generate():
        response = model.generate_content(
            full_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return response.text

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _generate)
    logger.debug("Gemini response length: %d chars", len(result))
    return result


async def _call_openai(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call the OpenAI API."""
    import asyncio

    client = _get_openai_client()
    settings = get_settings()

    def _generate():
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _generate)
    logger.debug("OpenAI response length: %d chars", len(result))
    return result

